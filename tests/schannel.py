#!/usr/bin/env python3
"""Mandatory native Windows SChannel/OpenSSL adversarial interoperability.

Certificate cases share the independent Go-inspired fixtures used by tls-local.
No trust roots are installed. Mutual TLS uses a nonexportable Windows KSP key.
"""
import importlib.util
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
from clang_helpers import windows_host

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tls_local', ROOT/'tests/tls-local.py')
tls_local = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tls_local)


class Server(tls_local.Server):
    def __init__(self, fixtures, certificate, intermediate=None, mutual=False,
                 client_ca=None, version=ssl.TLSVersion.TLSv1_3, truncated=False):
        # Configure before opening the listener/thread; the base starts eagerly.
        self.errors, self.peer = [], None
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.minimum_version = self.context.maximum_version = version
        chain = fixtures.path(certificate, 'pem')
        if intermediate:
            chain = fixtures.path(certificate, 'chain')
            chain.write_bytes(chain_for(fixtures, certificate, intermediate))
        self.context.load_cert_chain(chain, fixtures.path(certificate, 'key'))
        if mutual:
            self.context.verify_mode = ssl.CERT_REQUIRED
            self.context.load_verify_locations(client_ca or fixtures.path('root', 'pem'))
        self.truncated = truncated
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
                    if len(request) > 65536:
                        raise AssertionError('unexpected huge request')
                body = tls_local.BODY.encode()
                tls.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body)
                if self.truncated:
                    # Closing a detached TCP fd omits authenticated close_notify.
                    descriptor = tls.detach()
                    socket.socket(fileno=descriptor).close()
                else:
                    tls.unwrap().close()
        except (ssl.SSLError, OSError) as error:
            self.errors.append(str(error))
        finally:
            self.socket.close()


def chain_for(fixtures, certificate, intermediate):
    return fixtures.path(certificate, 'pem').read_bytes() + fixtures.path(intermediate, 'pem').read_bytes()


def native_compile(source, output, providers=()):
    subprocess.run([os.environ.get('MINYAR_TEST_CLANG', 'clang'), '-std=c11', '-O2',
        '-Wall', '-Wextra', '-Werror', '-DMINYAR_SYSTEM_HEAP=1', ROOT/'tests'/source,
        ROOT/'runtime/minyar_runtime.c', *(ROOT/'runtime/native'/p for p in providers),
        '-lsecur32', '-lcrypt32', '-lncrypt', '-lbcrypt', '-lws2_32', '-lm', '-o', output],
        check=True, timeout=60)


def case(program, fixtures, label, certificate='valid', host='localhost', accepted=True,
         intermediate=None, root='root', identity='', fragment='', **server_options):
    server = Server(fixtures, certificate, intermediate, **server_options)
    result = subprocess.run([program, str(server.port), host,
        fixtures.path(root, 'der') if root else '', identity, fragment],
        capture_output=True, text=True, timeout=20)
    server.finish()
    expected = 'HTTP/1.1 200 OK\nContent-Length: ' + str(len(tls_local.BODY.encode())) + '\n\n' + tls_local.BODY + '\n'
    success = result.returncode == 0 and result.stdout == expected
    if success != accepted or result.stderr or result.returncode not in (0, 1):
        raise AssertionError(f'{label}: expected={accepted} exit={result.returncode}\n'
            f'{result.stdout[:500]}\n{result.stderr[:500]}\n{server.errors}')
    if not accepted and ('200 OK' in result.stdout or tls_local.BODY in result.stdout):
        raise AssertionError(f'{label}: untrusted/truncated plaintext was exposed')
    if accepted and server_options.get('mutual') and not server.peer:
        raise AssertionError(f'{label}: server did not authenticate client certificate')
    print(f'SChannel {label}: {"accepted" if accepted else "rejected"}', flush=True)


def main():
    if not windows_host():
        raise SystemExit('SChannel correctness gate requires actual Windows APIs')
    ROOT.joinpath('build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='schannel-', dir=ROOT/'build') as directory:
        temporary = Path(directory)
        native = temporary/'native.exe'
        native_compile('schannel-native.c', native, ['tlsverify.c'])
        subprocess.run([native], check=True, timeout=30)
        wrong_thread = subprocess.run([native, 'thread'], capture_output=True, text=True, timeout=30)
        assert wrong_thread.returncode == 1 and 'require their owning thread' in wrong_thread.stderr, wrong_thread
        for mode in ['--debug', '--release']:
            contract = temporary/('contract-'+mode[2:]+'.exe')
            command = [ROOT/'minyar', mode, ROOT/'tests/schannel-contract.min', '-o', contract]
            if os.name == 'nt':
                shell = shutil.which('bash')
                if not shell:
                    raise AssertionError('SChannel Minyar tests require the MSYS2 toolchain')
                command.insert(0, shell)
            subprocess.run(command, check=True, timeout=120)
            result = subprocess.run([contract], capture_output=True, text=True, check=True, timeout=30)
            assert result.stdout == 'Windows SChannel result, trust, authentication and lifetime contracts verified\n', result
        program = temporary/'client.exe'
        tls_local.compile_program(ROOT/'tests/schannel-client.min', program)
        fixtures = tls_local.Certificates(temporary)
        fixtures.root('root')
        fixtures.root('untrusted')
        for name, options in [('valid', {}), ('ec', {'ec': True}),
                ('wrong-host', {'san': 'DNS:attacker.invalid'}), ('expired', {'validity': 'expired'}),
                ('future', {'validity': 'future'}), ('client-only', {'usage': 'clientAuth'}),
                ('cn-only', {'san': None}), ('intermediate', {'ca': True}),
                ('unknown-critical', {'extra': '1.2.3.4=critical,DER:05:00'}),
                ('expired-intermediate', {'ca': True, 'validity': 'expired'}),
                ('not-ca', {}), ('wildcard', {'san': 'DNS:*.example.test'}),
                ('constrained-intermediate', {'ca': True,
                    'extra': 'nameConstraints=critical,permitted;DNS:.example.test'})]:
            fixtures.leaf(name, 'root', **options)
        fixtures.leaf('unknown-issuer', 'untrusted')
        fixtures.leaf('via-intermediate', 'intermediate')
        fixtures.leaf('via-expired-intermediate', 'expired-intermediate')
        fixtures.leaf('via-not-ca', 'not-ca')
        fixtures.leaf('violates-constraints', 'constrained-intermediate')
        fixtures.leaf('satisfies-constraints', 'constrained-intermediate', san='DNS:device.example.test')
        corrupted = bytearray(fixtures.path('valid', 'der').read_bytes())
        corrupted[-1] ^= 1
        fixtures.path('bad-signature', 'der').write_bytes(corrupted)
        fixtures.path('bad-signature', 'key').write_bytes(fixtures.path('valid', 'key').read_bytes())
        tls_local.openssl('x509', '-inform', 'DER', '-in', fixtures.path('bad-signature', 'der'),
                          '-out', fixtures.path('bad-signature', 'pem'))
        case(program, fixtures, 'TLS 1.3 RSA')
        case(program, fixtures, 'TLS 1.2 RSA', version=ssl.TLSVersion.TLSv1_2)
        case(program, fixtures, 'TLS 1.3 ECDSA', 'ec')
        case(program, fixtures, 'IP SAN', host='127.0.0.1')
        case(program, fixtures, 'one-byte record fragments', fragment='fragment')
        case(program, fixtures, 'full intermediate chain', 'via-intermediate', intermediate='intermediate')
        case(program, fixtures, 'wildcard single label', 'wildcard', host='device.example.test')
        case(program, fixtures, 'permitted name constraint', 'satisfies-constraints', host='device.example.test',
             intermediate='constrained-intermediate')
        for label, certificate in [('wrong hostname', 'wrong-host'), ('expired leaf', 'expired'),
                ('future leaf', 'future'), ('wrong EKU', 'client-only'), ('CN without SAN', 'cn-only'),
                ('unknown critical extension', 'unknown-critical'), ('untrusted issuer', 'unknown-issuer'),
                ('missing intermediate', 'via-intermediate'), ('forged certificate signature', 'bad-signature')]:
            case(program, fixtures, label, certificate, accepted=False)
        case(program, fixtures, 'expired intermediate', 'via-expired-intermediate',
             intermediate='expired-intermediate', accepted=False)
        case(program, fixtures, 'issuer is not a CA', 'via-not-ca', intermediate='not-ca', accepted=False)
        case(program, fixtures, 'violated name constraint', 'violates-constraints',
             intermediate='constrained-intermediate', accepted=False)
        case(program, fixtures, 'wildcard multiple labels', 'wildcard', host='a.b.example.test', accepted=False)
        case(program, fixtures, 'wildcard bare suffix', 'wildcard', host='example.test', accepted=False)
        case(program, fixtures, 'OS roots reject private CA', root=None, accepted=False)
        case(program, fixtures, 'required identity absent', mutual=True, accepted=False)
        case(program, fixtures, 'TCP truncation after authenticated data', truncated=True, accepted=False)
        helper = temporary/'identity.exe'
        native_compile('schannel-identity.c', helper)
        public_der = temporary/'identity-public.der'
        identity = subprocess.Popen([helper, public_der], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            fingerprint = identity.stdout.readline().strip()
            if len(fingerprint) != 64 or not all(c in '0123456789abcdef' for c in fingerprint):
                raise AssertionError(f'nonexportable identity fixture failed: {fingerprint}')
            client_ca = temporary/'identity-public.pem'
            tls_local.openssl('x509', '-inform', 'DER', '-in', public_der, '-out', client_ca)
            case(program, fixtures, 'nonexportable CNG mutual TLS 1.3', identity=fingerprint,
                 mutual=True, client_ca=client_ca)
            case(program, fixtures, 'nonexportable CNG mutual TLS 1.2', identity=fingerprint,
                 mutual=True, client_ca=client_ca, version=ssl.TLSVersion.TLSv1_2)
            case(program, fixtures, 'untrusted client identity', identity=fingerprint, mutual=True, accepted=False)
        finally:
            stdout, stderr = identity.communicate('\n', timeout=20)
            if identity.returncode or stderr:
                raise AssertionError(f'identity cleanup failed: {identity.returncode} {stdout} {stderr}')
        print('SChannel independent peer, certificate rejection, CNG mTLS and truncation verified')


if __name__ == '__main__':
    main()
