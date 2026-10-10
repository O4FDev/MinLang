#!/usr/bin/env python3
"""Adversarial loopback TLS 1.3 interop. Independent CAs, constraints and keys.
Method derived from Go crypto/x509 verify_test.go and TLS handshake_client_test.go.
No OS trust store is modified; no external network or paid services.
"""
from datetime import datetime, timedelta, timezone
import argparse
from pathlib import Path
import os
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
from clang_helpers import windows_host

ROOT = Path(__file__).resolve().parents[1]
BODY = 'Minyar spoke authenticated TLS 1.3: ' + 'é' * 3 + ' ' + 'x' * 40000


def openssl_config_path(path):
    value = Path(path).as_posix()
    # MSYS converts command arguments, not paths embedded in config files.
    if windows_host() and os.name != 'nt':
        cygpath = shutil.which('cygpath')
        if not cygpath:
            raise RuntimeError('native Windows OpenSSL fixtures require cygpath')
        value = subprocess.check_output([cygpath, '-m', value], text=True, timeout=10).rstrip('\r\n')
    if '\n' in value or '\r' in value or '\0' in value:
        raise ValueError('OpenSSL fixture path contains a line break or NUL')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$') + '"'


def openssl(*args):
    # MSYS2 must convert fixture paths for native OpenSSL, but a /CN= subject
    # is certificate syntax, not a drive-relative filesystem path. The MSYS
    # spawn layer reads the PARENT environment before creating the child.
    existing = os.environ.get('MSYS2_ARG_CONV_EXCL')
    os.environ['MSYS2_ARG_CONV_EXCL'] = '*' if existing == '*' else (existing + ';' if existing else '') + '/CN='
    try:
        result = subprocess.run(['openssl', *map(str, args)], capture_output=True, text=True, timeout=30)
    finally:
        if existing is None:
            os.environ.pop('MSYS2_ARG_CONV_EXCL', None)
        else:
            os.environ['MSYS2_ARG_CONV_EXCL'] = existing
    if result.returncode:
        raise RuntimeError(result.stderr[-2000:])


class Certificates:
    def __init__(self, directory):
        self.directory, self.serial = Path(directory), 1

    def path(self, name, suffix):
        return self.directory / f'{name}.{suffix}'

    def root(self, name):
        openssl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '2',
                '-subj', f'/CN={name}', '-addext', 'basicConstraints=critical,CA:TRUE,pathlen:2',
                '-addext', 'keyUsage=critical,keyCertSign,cRLSign',
                '-keyout', self.path(name, 'key'), '-out', self.path(name, 'pem'))
        self.der(name)

    def der(self, name):
        openssl('x509', '-in', self.path(name, 'pem'), '-outform', 'DER', '-out', self.path(name, 'der'))

    def leaf(self, name, issuer, san='DNS:localhost,IP:127.0.0.1', usage='serverAuth',
             validity='valid', ca=False, ec=False, extra=''):
        curve = ec if isinstance(ec, str) else 'P-256'
        options = ['EC', '-pkeyopt', f'ec_paramgen_curve:{curve}'] if ec else ['RSA', '-pkeyopt', 'rsa_keygen_bits:2048']
        openssl('genpkey', '-algorithm', *options, '-out', self.path(name, 'key'))
        openssl('req', '-new', '-key', self.path(name, 'key'), '-subj', '/CN=localhost', '-out', self.path(name, 'csr'))
        index, serial = self.path(name, 'index'), self.path(name, 'serial')
        index.touch()
        serial.write_text(f'{self.serial:02X}\n')
        self.serial += 1
        extensions = ('basicConstraints=critical,CA:TRUE,pathlen:0\nkeyUsage=critical,keyCertSign,cRLSign\n' if ca else
                      f'basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage={usage}\n')
        if san:
            extensions += f'subjectAltName={san}\n'
        if extra:
            extensions += extra + '\n'
        config = self.path(name, 'cnf')
        config.write_text(f'''[ca]
default_ca=issuer
[issuer]
database={openssl_config_path(index)}
serial={openssl_config_path(serial)}
new_certs_dir={openssl_config_path(self.directory)}
certificate={openssl_config_path(self.path(issuer, 'pem'))}
private_key={openssl_config_path(self.path(issuer, 'key'))}
default_md=sha256
default_days=2
policy=policy
x509_extensions=extensions
[policy]
commonName=supplied
[extensions]
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
{extensions}''')
        now = datetime.now(timezone.utc)
        start, end = now - timedelta(hours=1), now + timedelta(days=1)
        if validity == 'expired':
            start, end = now - timedelta(days=2), now - timedelta(days=1)
        if validity == 'future':
            start, end = now + timedelta(days=1), now + timedelta(days=2)
        openssl('ca', '-batch', '-notext', '-config', config, '-startdate', start.strftime('%y%m%d%H%M%SZ'),
                '-enddate', end.strftime('%y%m%d%H%M%SZ'), '-in', self.path(name, 'csr'), '-out', self.path(name, 'pem'))
        self.der(name)
        openssl('pkcs8', '-topk8', '-nocrypt', '-in', self.path(name, 'key'), '-outform', 'DER', '-out', self.path(name, 'pk8'))


class Server:
    def __init__(self, fixtures, certificate, intermediate=None, mutual=False):
        self.errors, self.peer = [], None
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.minimum_version = self.context.maximum_version = ssl.TLSVersion.TLSv1_3
        self.context.set_alpn_protocols(['http/1.1'])
        chain = fixtures.path(certificate, 'pem')
        if intermediate:
            chain = fixtures.path(certificate, 'chain')
            chain.write_bytes(fixtures.path(certificate, 'pem').read_bytes() + fixtures.path(intermediate, 'pem').read_bytes())
        self.context.load_cert_chain(chain, fixtures.path(certificate, 'key'))
        if mutual:
            self.context.verify_mode = ssl.CERT_REQUIRED
            self.context.load_verify_locations(fixtures.path('root', 'pem'))
        self.socket = socket.socket()
        self.socket.bind(('127.0.0.1', 0))
        self.socket.listen()
        self.socket.settimeout(10)
        self.port = self.socket.getsockname()[1]
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self):
        try:
            connection, _ = self.socket.accept()
            connection.settimeout(10)
            with connection, self.context.wrap_socket(connection, server_side=True) as tls:
                self.peer = tls.getpeercert()
                request = b''
                while b'\r\n\r\n' not in request:
                    data = tls.recv(65536)
                    if not data:
                        return
                    request += data
                body = BODY.encode()
                tls.sendall(b'HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body)
                try:
                    tls.unwrap()
                except (ssl.SSLError, OSError):
                    pass
        except (ssl.SSLError, OSError) as error:
            self.errors.append(str(error))
        finally:
            self.socket.close()

    def finish(self):
        self.thread.join(12)
        if self.thread.is_alive():
            raise AssertionError('local TLS server did not shut down')


def compile_program(source, output):
    command = [str(ROOT / 'minyar'), '--library', str(ROOT / 'library'), str(source), '-o', str(output)]
    if os.name == 'nt':
        shell = shutil.which('bash')
        if not shell:
            raise AssertionError('TLS tests on Windows require the MSYS2 bash/Clang toolchain')
        command.insert(0, shell)
    result = subprocess.run(command,
                            capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise AssertionError(f'compile {source}: {result.stdout} {result.stderr}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sanitize', action='store_true', help='Compile generated code, runtime, and provider with ASan/UBSan')
    arguments = parser.parse_args()
    if arguments.sanitize:
        sanitizer = '-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer'
        os.environ['MINYAR_CLANG_FLAGS'] = sanitizer + ' -Wno-override-module'
        os.environ['MINYAR_NATIVE_FLAGS'] = sanitizer
        os.environ['MINYAR_RUNTIME_FLAGS'] = sanitizer
    with tempfile.TemporaryDirectory(prefix='minyar-tls-') as temporary:
        fixtures = Certificates(temporary)
        fixtures.root('root')
        fixtures.root('untrusted')
        openssl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1', '-subj', '/CN=localhost',
                '-addext', 'basicConstraints=critical,CA:FALSE', '-addext', 'keyUsage=critical,digitalSignature',
                '-addext', 'extendedKeyUsage=serverAuth', '-addext', 'subjectAltName=DNS:localhost',
                '-keyout', fixtures.path('self-signed', 'key'), '-out', fixtures.path('self-signed', 'pem'))
        for name, options in [('valid', {}), ('ec', {'ec': True}), ('wrong-host', {'san': 'DNS:attacker.invalid'}),
                              ('expired', {'validity': 'expired'}), ('future', {'validity': 'future'}),
                              ('client-only', {'usage': 'clientAuth'}), ('cn-only', {'san': None}),
                              ('wildcard', {'san': 'DNS:*.example.test'}), ('intermediate', {'ca': True}),
                              ('device', {'usage': 'clientAuth'}), ('ec-device', {'usage': 'clientAuth', 'ec': True})]:
            fixtures.leaf(name, 'root', **options)
        fixtures.leaf('unknown-issuer', 'untrusted')
        fixtures.leaf('via-intermediate', 'intermediate')
        fixtures.leaf('not-ca', 'root')
        fixtures.leaf('via-not-ca', 'not-ca')
        fixtures.leaf('expired-intermediate', 'root', ca=True, validity='expired')
        fixtures.leaf('via-expired-intermediate', 'expired-intermediate')
        fixtures.leaf('untrusted-device', 'untrusted', usage='clientAuth')
        fixtures.leaf('p384', 'root', ec='P-384')
        fixtures.leaf('p521', 'root', ec='P-521')
        fixtures.leaf('p384-device', 'root', usage='clientAuth', ec='P-384')
        fixtures.leaf('p521-device', 'root', usage='clientAuth', ec='P-521')
        fixtures.leaf('unknown-critical', 'root', extra='1.2.3.4=critical,DER:05:00')
        fixtures.leaf('constrained-intermediate', 'root', ca=True,
                      extra='nameConstraints=critical,permitted;DNS:.example.test')
        fixtures.leaf('violates-constraints', 'constrained-intermediate')
        fixtures.leaf('satisfies-constraints', 'constrained-intermediate', san='DNS:device.example.test')
        # Preserve the leaf public/private key and all DER syntax while
        # invalidating only the issuer signature.
        corrupted = bytearray(fixtures.path('valid', 'der').read_bytes())
        corrupted[-1] ^= 1
        fixtures.path('bad-signature', 'der').write_bytes(corrupted)
        fixtures.path('bad-signature', 'key').write_bytes(fixtures.path('valid', 'key').read_bytes())
        openssl('x509', '-inform', 'DER', '-in', fixtures.path('bad-signature', 'der'),
                '-out', fixtures.path('bad-signature', 'pem'))
        program, fetch = Path(temporary) / 'client.exe', Path(temporary) / 'fetch.exe'
        compile_program(ROOT / 'tests/tls-client.min', program)
        compile_program(ROOT / 'examples/fetch/main.min', fetch)
        cases = [
            ('trusted RSA', 'valid', 'localhost', True, None, False, None),
            ('trusted ECDSA', 'ec', 'localhost', True, None, False, None),
            ('trusted ECDSA P-384', 'p384', 'localhost', True, None, False, None),
            ('trusted ECDSA P-521', 'p521', 'localhost', True, None, False, None),
            ('IP subjectAltName', 'valid', '127.0.0.1', True, None, False, None),
            ('wildcard single label', 'wildcard', 'device.example.test', True, None, False, None),
            ('full intermediate chain', 'via-intermediate', 'localhost', True, 'intermediate', False, None),
            ('permitted name constraint', 'satisfies-constraints', 'device.example.test', True, 'constrained-intermediate', False, None),
            ('wrong hostname', 'wrong-host', 'localhost', False, None, False, None),
            ('expired leaf', 'expired', 'localhost', False, None, False, None),
            ('not yet valid leaf', 'future', 'localhost', False, None, False, None),
            ('wrong extended key usage', 'client-only', 'localhost', False, None, False, None),
            ('unknown issuer', 'unknown-issuer', 'localhost', False, None, False, None),
            ('untrusted self-signed leaf', 'self-signed', 'localhost', False, None, False, None),
            ('missing intermediate', 'via-intermediate', 'localhost', False, None, False, None),
            ('issuer is not a CA', 'via-not-ca', 'localhost', False, 'not-ca', False, None),
            ('expired intermediate', 'via-expired-intermediate', 'localhost', False, 'expired-intermediate', False, None),
            ('forged certificate issuer signature', 'bad-signature', 'localhost', False, None, False, None),
            ('unknown critical extension', 'unknown-critical', 'localhost', False, None, False, None),
            ('violated name constraint', 'violates-constraints', 'localhost', False, 'constrained-intermediate', False, None),
            ('common name without SAN', 'cn-only', 'localhost', False, None, False, None),
            ('wildcard multiple labels', 'wildcard', 'a.b.example.test', False, None, False, None),
            ('wildcard bare suffix', 'wildcard', 'example.test', False, None, False, None),
            ('required client certificate absent', 'valid', 'localhost', False, None, True, None),
            ('RSA mutual TLS', 'valid', 'localhost', True, None, True, 'device'),
            ('ECDSA mutual TLS', 'valid', 'localhost', True, None, True, 'ec-device'),
            ('ECDSA P-384 mutual TLS', 'valid', 'localhost', True, None, True, 'p384-device'),
            ('ECDSA P-521 mutual TLS', 'valid', 'localhost', True, None, True, 'p521-device'),
            ('untrusted client identity', 'valid', 'localhost', False, None, True, 'untrusted-device'),
            ('client identity has server-only usage', 'valid', 'localhost', False, None, True, 'valid'),
            ('client certificate/key mismatch', 'valid', 'localhost', False, None, True, 'device'),
        ]
        for name, certificate, host, accepted, intermediate, mutual, identity in cases:
            server = Server(fixtures, certificate, intermediate, mutual)
            command = [str(program), str(server.port), host, str(fixtures.path('root', 'der'))]
            if identity:
                key = 'valid' if name == 'client certificate/key mismatch' else identity
                command += [str(fixtures.path(identity, 'der')), str(fixtures.path(key, 'pk8'))]
            result = subprocess.run(command, capture_output=True, text=True, timeout=20)
            server.finish()
            success = result.returncode == 0 and '200 OK' in result.stdout and BODY in result.stdout
            if success != accepted or (not accepted and (result.returncode < 0 or result.stderr)):
                raise AssertionError(f'{name}: acceptance={success}, expected={accepted}, code={result.returncode}\n'
                                     f'{result.stdout[:500]}\n{result.stderr[:500]}\n{server.errors}')
            if accepted and mutual and not server.peer:
                raise AssertionError(f'{name}: server saw no client certificate')
            print(f'TLS {name}: {"accepted" if accepted else "rejected"}', flush=True)
        server = Server(fixtures, 'unknown-issuer')
        result = subprocess.run([fetch, f'https://localhost:{server.port}/'], capture_output=True, text=True, timeout=20)
        server.finish()
        if result.returncode != 1 or '200 OK' in result.stdout or 'TLS failed:' not in result.stdout:
            raise AssertionError(f'portable HTTP accepted an untrusted issuer: {result.stdout[:400]}')
        print('TLS portable HTTP default OS trust: untrusted issuer rejected', flush=True)
        protocol = Path(temporary) / 'protocol.exe'
        compile_program(ROOT / 'tests/tls-protocol.min', protocol)
        result = subprocess.run([protocol, fixtures.path('root', 'der'), fixtures.path('valid', 'der'),
                                 fixtures.path('valid', 'pk8'), fixtures.path('ec', 'der')], capture_output=True, text=True, timeout=60)
        if result.returncode or result.stderr:
            raise AssertionError(f'TLS protocol regressions: {result.stdout[:800]} {result.stderr[:800]}')
        print(result.stdout.strip(), flush=True)
    print('TLS 1.3 certificate, mutual authentication, and adversarial protocol checks passed')


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'TLS check failed: {error}', file=sys.stderr)
        sys.exit(1)
