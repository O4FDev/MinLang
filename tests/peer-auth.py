#!/usr/bin/env python3
"""Hearth grant policy tested with independent cryptography/OpenSSL fixtures.

Test-only signing is pyca cryptography, not Minyar or Monocypher. Fixed Ed25519
key and direct-provider fixture are from RFC 8032 §7.1 / RFC 8037 Appendix A.
All executions belong on the authorised remote Linux lab, never a laptop.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:
    Ed25519PrivateKey = None

ROOT = Path(__file__).resolve().parents[1]
SEED = bytes.fromhex('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60')
PUBLIC = bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
KEY = Ed25519PrivateKey.from_private_bytes(SEED) if Ed25519PrivateKey else None
HEADER = {'alg': 'EdDSA', 'typ': 'hearth-dial-grant', 'kid': 'pop-1'}
CLAIMS = {'iss': 'proxy-gateway', 'exit_id': 'exit-a', 'conn_id': 'conn-1',
          'target_host': 'example.com', 'port': 443, 'iat': 1000, 'exp': 1060}


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=')


def compact(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=False).encode()


def token(claims=None, header=None, payload=None, raw_header=None):
    signing = b64(raw_header if raw_header is not None else compact(HEADER if header is None else header)) + b'.' + b64(payload if payload is not None else compact(CLAIMS if claims is None else claims))
    return signing + b'.' + b64(KEY.sign(signing))


def jwks(key=None):
    return compact({'keys': [dict(kty='OKP', crv='Ed25519', kid='pop-1', alg='EdDSA', use='sig', x=b64(PUBLIC).decode()) if key is None else key]})


class OpenSSLSigner:
    # RFC 8410 §7 PKCS#8 wrapper for the public RFC 8032 test seed. This is a
    # test fixture only. Existing TLS tests already require the OpenSSL CLI.
    def __init__(self, directory):
        self.directory = directory
        self.executable = os.environ.get('MINYAR_TEST_OPENSSL', 'openssl')
        if 'MINYAR_TEST_OPENSSL' not in os.environ:
            # The macOS portable CI already installs this provider for TLS.
            for prefix in ('/opt/homebrew', '/usr/local'):
                candidate = Path(prefix) / 'opt/openssl@3/bin/openssl'
                if candidate.is_file():
                    self.executable = str(candidate)
                    break
        (directory / 'fixture-key.der').write_bytes(bytes.fromhex('302e020100300506032b657004220420') + SEED)

    def sign(self, data):
        (self.directory / 'fixture-message').write_bytes(data)
        result = subprocess.run([self.executable, 'pkeyutl', '-sign', '-rawin', '-keyform', 'DER',
                                 '-inkey', str(self.directory / 'fixture-key.der'),
                                 '-in', str(self.directory / 'fixture-message')], capture_output=True, timeout=10)
        assert result.returncode == 0 and len(result.stdout) == 64, result.stderr
        return result.stdout


def main():
    global KEY
    parser = argparse.ArgumentParser()
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--red', action='store_true', help='expect the initial stub to reject the independent valid grant')
    parser.add_argument('--library', type=Path, help='test-only isolated mutation library')
    parser.add_argument('--openssl-signer', action='store_true', help='exercise the no-extra-Python-dependency fixture signer')
    options = parser.parse_args()
    expected_hashes = {'monocypher.c': 'f1f838cdd483bdebe0df0ff5c5ed60535e496f769c6a2f933ac4c0b114207123',
                       'monocypher-ed25519.c': 'ce0d2f8e32ca8f66398ba5b3456cc74327c3eff14e7b950ce7d57be9025cc453'}
    for name, expected in expected_hashes.items():
        assert hashlib.sha256((ROOT / 'vendor/monocypher' / name).read_bytes()).hexdigest() == expected
    env = dict(os.environ, MINYAR_CLANG=os.environ.get('MINYAR_TEST_CLANG', 'clang'))
    if options.sanitize:
        for name in ('MINYAR_CLANG_FLAGS', 'MINYAR_RUNTIME_FLAGS', 'MINYAR_NATIVE_FLAGS'):
            env[name] = '-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
        env['ASAN_OPTIONS'] = 'detect_leaks=1'
    with tempfile.TemporaryDirectory(prefix='minyar-peer-auth-') as directory:
        directory = Path(directory)
        if options.openssl_signer or KEY is None:
            KEY = OpenSSLSigner(directory)
        binary = directory / 'probe'
        compiler = [str(ROOT / 'minyar')]
        if options.library:
            compiler += ['--library', str(options.library)]
        subprocess.run([*compiler, str(ROOT / 'tests/peer-auth.min'), '-o', str(binary)], env=env, check=True, timeout=240)
        counter = 0

        def check(name, raw=None, *, bundle=None, accepted=False, now=1000, deadline=1060,
                  authenticated='exit-a', requested='exit-a', connection='conn-1', trap=False, expected=None):
            nonlocal counter
            counter += 1
            (directory / 'keys').write_bytes(jwks() if bundle is None else bundle)
            (directory / 'grant').write_bytes(token() if raw is None else raw)
            process = subprocess.run([str(binary), 'trap' if trap else 'grant', str(directory / 'keys'),
                                      str(directory / 'grant'), authenticated, requested, connection, str(now), str(deadline)],
                                     env=env, capture_output=True, text=True, timeout=10)
            if trap:
                assert process.returncode != 0 and 'cannot read a rejected grant' in process.stderr, (name, process)
            else:
                assert process.returncode == 0, (name, process.returncode, process.stderr)
                if accepted:
                    assert process.stdout.strip() == (expected or 'OK exit-a conn-1 example.com  443 1060'), (name, process.stdout, process.stderr)
                else:
                    assert process.stdout.startswith(('GRANT_ERROR ', 'KEY_ERROR ')), (name, process.stdout)
                    assert process.stdout.strip().split()[-1] in ('6', '8', '10', '11'), (name, process.stdout)

        if options.red:
            check('independent valid grant is rejected by initial stub')
            print('RED: independent valid grant rejected by verifier stub')
            return
        check('independent valid grant', accepted=True)
        check('minimum port', token(claims=dict(CLAIMS, port=1)), accepted=True, expected='OK exit-a conn-1 example.com  1 1060')
        check('maximum port', token(claims=dict(CLAIMS, port=65535)), accepted=True, expected='OK exit-a conn-1 example.com  65535 1060')
        check('issued at positive skew boundary', token(claims=dict(CLAIMS, iat=1030)), accepted=True)
        exact_payload = compact(dict(CLAIMS, padding=''))
        exact_payload = compact(dict(CLAIMS, padding='x' * (4096 - len(exact_payload))))
        assert len(exact_payload) == 4096
        check('exact payload byte limit', token(payload=exact_payload), accepted=True)
        check('payload one byte over limit', token(payload=exact_payload + b' '))
        exact_header = compact(HEADER) + b' ' * (1024 - len(compact(HEADER)))
        check('exact protected header byte limit', token(raw_header=exact_header), accepted=True)
        check('protected header one byte over limit', token(raw_header=exact_header + b' '))
        check('paired Unicode escape remains valid metadata', token(payload=compact(CLAIMS)[:-1] + b',"extra":"\\ud83d\\ude00"}'), accepted=True)
        longest_host = '.'.join(['a' * 63, 'b' * 63, 'c' * 63, 'd' * 61])
        check('maximum DNS name', token(claims=dict(CLAIMS, target_host=longest_host)), accepted=True, expected='OK exit-a conn-1 ' + longest_host + '  443 1060')
        check('DNS name one byte too long', token(claims=dict(CLAIMS, target_host=longest_host + 'd')))
        check('DNS label one byte too long', token(claims=dict(CLAIMS, target_host='a' * 64 + '.example')))
        check('iat skew boundary', accepted=True, now=970)
        check('iat beyond skew', now=969)
        # Skew permits JWT validation, but an open cannot be established after exp.
        check('expiry boundary remains an establishment deadline', now=1060, deadline=1060)
        check('expiry skew boundary is still too late to establish', now=1090, deadline=1090)
        check('expiry beyond skew', now=1091, deadline=1091)
        check('deadline after expiry', deadline=1061)
        check('deadline at current time', deadline=1000)
        check('wrong authenticated exit', authenticated='exit-b')
        check('wrong requested exit', requested='exit-b')
        check('wrong connection', connection='conn-2')
        check('overflow time is recoverable', now=9223372036854775807, deadline=9223372036854775807)
        check('maximum safe time is recoverable', now=9223372036854775777, deadline=9223372036854775777)
        check('claim key ID mismatch', token(claims=dict(CLAIMS, kid='other')))
        for field, bad in [('alg', 'none'), ('alg', 'HS256'), ('typ', 'JWT'), ('kid', 'unknown')]:
            check('header ' + field + ' ' + bad, token(header=dict(HEADER, **{field: bad})))
        for field in HEADER:
            header = dict(HEADER); del header[field]
            check('missing header ' + field, token(header=header))
        for extra in ({'crit': ['x']}, {'b64': False}, {'jwk': {}}, {'jku': 'https://example.com/keys'}):
            check('unsupported protected header', token(header=dict(HEADER, **extra)))
        for field, bad in [('iss', 'hearth-control'), ('exit_id', 'exit-b'), ('conn_id', 'conn-2'),
                           ('target_host', ''), ('target_host', 'a..b'), ('target_host', '-bad.example'),
                           ('target_host', '127.0.0.1'), ('target_host', 'example.com\x00evil'),
                           ('target_host', 'é.example'), ('port', 0), ('port', 65536), ('port', '443'),
                           ('port', 443.0), ('iat', -1), ('iat', 1031), ('exp', 1061), ('exp', 1000),
                           ('exp', 999), ('exp', 9223372036854775807)]:
            check('claim ' + field + ' ' + repr(bad), token(claims=dict(CLAIMS, **{field: bad})))
        for field in CLAIMS:
            claims = dict(CLAIMS); del claims[field]
            check('missing claim ' + field, token(claims=claims))
        check('two targets', token(claims=dict(CLAIMS, target_ip='192.0.2.1')))
        ip_claims = dict(CLAIMS); del ip_claims['target_host']; ip_claims['target_ip'] = '192.0.2.1'
        check('IPv4 target', token(claims=ip_claims), accepted=True, expected='OK exit-a conn-1  192.0.2.1 443 1060')
        ip_claims['target_ip'] = '2001:db8::1'
        check('IPv6 target', token(claims=ip_claims), accepted=True, expected='OK exit-a conn-1  2001:db8::1 443 1060')
        for ip in ['::', '::1', '::ffff:192.0.2.1', '1:2:3:4:5:6:192.0.2.1', '1:2:3:4:5:6:7:8']:
            check('valid IPv6 ' + ip, token(claims=dict(ip_claims, target_ip=ip)), accepted=True, expected='OK exit-a conn-1  ' + ip + ' 443 1060')
        for bad in ['192.0.2.256', '192.000.2.1', '[::1]', 'fe80::1%eth0', '::::', '2001:db8::1::2', '1:2:3:4:5:6:7:8:9', 'example.com']:
            check('bad IP ' + bad, token(claims=dict(ip_claims, target_ip=bad)))
        for raw in [b'', b'a', b'a.b.c.d', b'.a.b', b'a..b', b'a.b.', token() + b'=',
                    b'\xff' + token(), token().replace(b'.', b'.\n', 1)]:
            check('malformed compact JWS', raw)
        head, payload, signature = token().split(b'.')
        check('signature bit mutation', head + b'.' + payload + b'.' + b64(bytes([KEY.sign(head + b'.' + payload)[0] ^ 1]) + KEY.sign(head + b'.' + payload)[1:]))
        check('payload bit mutation', head + b'.' + payload[:-1] + (b'A' if payload[-1:] != b'A' else b'B') + b'.' + signature)
        # Signature has four unused low bits. Changing only those decodes identically.
        alphabet = b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
        noncanonical = signature[:-1] + bytes([alphabet[alphabet.index(signature[-1]) | 1]])
        check('noncanonical signature pad bits', head + b'.' + payload + b'.' + noncanonical)
        for raw in [b'{"alg":"EdDSA","typ":"hearth-dial-grant","kid":"pop-1","k\\u0069d":"pop-1"}',
                    b'{"alg":"EdDSA","typ":"hearth-dial-grant","kid":"pop-1","kid":"pop-1"}']:
            check('duplicate decoded header key', token(raw_header=raw))
        for raw in [compact(CLAIMS)[:-1] + b',"exit\\u005fid":"exit-a"}',
                    compact(CLAIMS)[:-1] + b',"extra":{"x":1,"\\u0078":2}}',
                    compact(CLAIMS).replace(b'example.com', b'\xff'),
                    compact(CLAIMS).replace(b'example.com', b'\\ud800'),
                    b'[' + compact(CLAIMS) + b']', b'{', compact(CLAIMS) + b' null',
                    compact(CLAIMS).replace(b'1000', b'1e3'),
                    compact(CLAIMS)[:-1] + b',"extra":' + b'[' * 65 + b'0' + b']' * 65 + b'}']:
            check('invalid strict grant metadata', token(payload=raw))
        check('token size bound', b'a' * 8193)
        good_key = json.loads(jwks())['keys'][0]
        check('maximum key count', bundle=compact({'keys': [good_key] + [dict(good_key, kid='extra-' + str(i)) for i in range(63)]}), accepted=True)
        check('verify-only key operations', bundle=jwks(dict(good_key, key_ops=['verify'])), accepted=True)
        for field, bad in [('kty', 'EC'), ('crv', 'X25519'), ('alg', 'HS256'), ('use', 'enc'),
                           ('x', b64(b'\0' * 32).decode()), ('x', 'A'), ('kid', '')]:
            check('key policy ' + field, bundle=jwks(dict(good_key, **{field: bad})))
        check('wrong key', bundle=jwks(dict(good_key, x=b64(bytes(range(32))).decode())))
        for key in [b'\x01' + b'\0' * 31, b'\x01' + b'\0' * 30 + b'\x80', b'\xed' + b'\xff' * 30 + b'\x7f', b'\xec' + b'\xff' * 30 + b'\x7f']:
            check('low-order or noncanonical key', bundle=jwks(dict(good_key, x=b64(key).decode())))
        check('private key rejected', bundle=jwks(dict(good_key, d=b64(SEED).decode())))
        check('wrong key operations', bundle=jwks(dict(good_key, key_ops=['sign'])))
        check('duplicate key ID', bundle=compact({'keys': [good_key, good_key]}))
        check('duplicate decoded JWKS key', bundle=jwks()[:-1] + b',"k\\u0065ys":[]}')
        check('JWKS UTF-8 invalid', bundle=b'{"keys":[],"x":"\xff"}')
        check('JWKS size bound', bundle=b' ' * 65537)
        check('empty key list', bundle=b'{"keys":[]}')
        check('too many keys', bundle=compact({'keys': [dict(good_key, kid='pop-' + str(i)) for i in range(65)]}))
        check('wrong use of failed result traps', b'bad', trap=True)
        signing = b'eyJhbGciOiJFZERTQSJ9.RXhhbXBsZSBvZiBFZDI1NTE5IHNpZ25pbmc'
        sig = bytes.fromhex('860c98d2297f3060a33f42739672d61b53cf3adefed3d3c672f320dc021b411e9d59b8628dc351e248b88b29468e0e41855b0fb7d83bb15be902bfccb8cd0a02')
        assert KEY.sign(signing) == sig, 'independent signer disagrees with fixed RFC 8037 fixture'
        for name, data in [('message', signing), ('signature', sig), ('public', PUBLIC)]:
            (directory / name).write_bytes(data)
        command = [str(binary), 'crypto', *map(str, [directory / 'message', directory / 'signature', directory / 'public'])]
        assert subprocess.check_output(command, env=env, text=True).strip() == 'OK'
        for offset in range(64):
            mutation = bytearray(sig); mutation[offset] ^= 1
            (directory / 'signature').write_bytes(mutation)
            assert subprocess.check_output(command, env=env, text=True).strip() == 'ERROR', offset
        print(f'Peer auth: {counter} policy cases + RFC 8037 signature + 64 signature mutations passed')


if __name__ == '__main__':
    main()
