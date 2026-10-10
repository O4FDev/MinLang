#!/usr/bin/env python3
"""Actual mTLS possession/chain validation before trusted registry binding."""
import argparse
import importlib.util
import os
from pathlib import Path
import socket
import ssl
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tls_fixtures', ROOT / 'tests/tls-local.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sanitize', action='store_true')
    options = parser.parse_args()
    if options.sanitize:
        for name in ('MINYAR_CLANG_FLAGS', 'MINYAR_NATIVE_FLAGS', 'MINYAR_RUNTIME_FLAGS'):
            os.environ[name] = '-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
        os.environ['ASAN_OPTIONS'] = 'detect_leaks=1'
    with tempfile.TemporaryDirectory(prefix='minyar-peer-device-') as directory:
        directory = Path(directory)
        ca = fixtures.Certificates(directory)
        ca.root('root'); ca.root('unknown-root'); ca.leaf('server', 'root')
        cases = [
            ('good', 'root', 'URI:hearth://device/device-a', 'clientAuth', 'valid', 'device-a', 'exit-a', 'live', 'BOUND device-a exit-a'),
            ('wrong-device', 'root', 'URI:hearth://device/device-b', 'clientAuth', 'valid', 'device-a', 'exit-a', 'live', 'BIND_ERROR 11'),
            ('no-uri', 'root', 'DNS:device-a', 'clientAuth', 'valid', 'device-a', 'exit-a', 'live', 'BIND_ERROR 11'),
            ('uri-suffix', 'root', 'URI:hearth://device/device-a/evil', 'clientAuth', 'valid', 'device-a', 'exit-a', 'live', 'BIND_ERROR 11'),
            ('two-uri', 'root', 'URI:hearth://device/device-a,URI:hearth://device/device-b', 'clientAuth', 'valid', 'device-a', 'exit-a', 'live', 'BIND_ERROR 11'),
            ('unknown-ca', 'unknown-root', 'URI:hearth://device/device-a', 'clientAuth', 'valid', 'device-a', 'exit-a', 'live', 'TLS_ERROR'),
            ('wrong-eku', 'root', 'URI:hearth://device/device-a', 'serverAuth', 'valid', 'device-a', 'exit-a', 'live', 'TLS_ERROR'),
            ('expired', 'root', 'URI:hearth://device/device-a', 'clientAuth', 'expired', 'device-a', 'exit-a', 'live', 'TLS_ERROR'),
            ('revoked', 'root', 'URI:hearth://device/device-a', 'clientAuth', 'valid', 'device-a', 'exit-a', 'revoked', 'BIND_ERROR 11'),
            ('revocation-update', 'root', 'URI:hearth://device/device-a', 'clientAuth', 'valid', 'device-a', 'exit-a', 'revoke-after-bind', 'BIND_REVOKED'),
            ('invalid-registry-exit', 'root', 'URI:hearth://device/device-a', 'clientAuth', 'valid', 'device-a', 'exit/a', 'live', 'BIND_ERROR 11'),
        ]
        for name, issuer, san, usage, validity, *_ in cases:
            ca.leaf(name, issuer, san=san, usage=usage, validity=validity, ec=True)
        binary = directory / 'server'
        fixtures.compile_program(ROOT / 'tests/peer-auth-device.min', binary)
        for name, issuer, san, usage, validity, device, exit_id, revoked, expected in cases:
            process = subprocess.Popen([str(binary), str(ca.path('server', 'der')), str(ca.path('server', 'pk8')),
                                        str(ca.path('root', 'der')), device, exit_id, revoked],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                ready = process.stdout.readline().strip()
                assert ready.startswith('READY '), ready
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                context.minimum_version = context.maximum_version = ssl.TLSVersion.TLSv1_3
                context.load_verify_locations(ca.path('root', 'pem'))
                context.set_alpn_protocols(['hearth-peer-test'])
                context.load_cert_chain(ca.path(name, 'pem'), ca.path(name, 'key'))
                response = b''
                try:
                    with socket.create_connection(('127.0.0.1', int(ready.split()[1])), timeout=5) as raw:
                        with context.wrap_socket(raw, server_hostname='localhost') as client:
                            response = client.recv(1024)
                except (ssl.SSLError, OSError):
                    pass
                stdout, stderr = process.communicate(timeout=10)
                assert expected in stdout, (name, process.returncode, stdout, stderr)
                assert process.returncode == (1 if expected == 'TLS_ERROR' else 0), (name, process.returncode, stderr)
                assert response == (b'bound' if expected.startswith('BOUND ') else b''), (name, response)
            finally:
                if process.poll() is None:
                    process.kill(); process.communicate()
        print(f'Peer device auth: {len(cases)} actual independent OpenSSL mTLS/registry/revocation cases passed')


if __name__ == '__main__':
    main()
