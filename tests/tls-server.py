#!/usr/bin/env python3
"""Our TLS server vs independent Python/OpenSSL clients; adversarial mTLS."""
import argparse
import importlib.util
import os
from pathlib import Path
import ssl
import socket
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tls_client_tests', ROOT / 'tests/tls-local.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sanitize', action='store_true')
    options = parser.parse_args()
    if options.sanitize:
        for name in ('MINYAR_CLANG_FLAGS', 'MINYAR_NATIVE_FLAGS', 'MINYAR_RUNTIME_FLAGS'):
            os.environ[name] = '-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
    with tempfile.TemporaryDirectory(prefix='minyar-tls-server-') as directory:
        directory = Path(directory)
        ca = fixtures.Certificates(directory)
        ca.root('root'); ca.root('untrusted')
        ca.leaf('server', 'root')
        ca.leaf('client', 'root', usage='clientAuth')
        ca.leaf('ec-client', 'root', usage='clientAuth', ec=True)
        ca.leaf('unknown', 'untrusted', usage='clientAuth')
        ca.leaf('expired', 'root', usage='clientAuth', validity='expired')
        ca.leaf('future', 'root', usage='clientAuth', validity='future')
        ca.leaf('wrong-usage', 'root', usage='serverAuth')
        binary = directory / 'server.exe'
        fixtures.compile_program(ROOT / 'tests/tls-server.min', binary)
        for name, accepted in [('client', True), ('ec-client', True), ('unknown', False),
                               ('expired', False), ('future', False), ('wrong-usage', False), (None, False)]:
            process = subprocess.Popen([str(binary), str(ca.path('server', 'der')), str(ca.path('server', 'pk8')),
                                        str(ca.path('root', 'der'))], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                ready = process.stdout.readline().strip()
                assert ready.startswith('READY '), ready
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                context.minimum_version = context.maximum_version = ssl.TLSVersion.TLSv1_3
                context.load_verify_locations(ca.path('root', 'pem'))
                context.set_alpn_protocols(['http/1.1'])
                if name:
                    context.load_cert_chain(ca.path(name, 'pem'), ca.path(name, 'key'))
                got = b''
                try:
                    with socket.create_connection(('127.0.0.1', int(ready.split()[1])), timeout=5) as raw:
                        with context.wrap_socket(raw, server_hostname='localhost') as client:
                            client.sendall(b'ping')
                            got = client.recv(1024)
                except (ssl.SSLError, OSError):
                    pass
                stdout, stderr = process.communicate(timeout=10)
                if accepted:
                    assert process.returncode == 0 and got == b'pong' and 'verified client certificate' in stdout, (name, got, stdout, stderr)
                else:
                    assert process.returncode != 0 and got == b'' and 'verified client certificate' not in stdout, (name, got, stdout, stderr)
                print(f'TLS server {name or "absent"}: {"accepted" if accepted else "rejected"}')
            finally:
                if process.poll() is None:
                    process.kill(); process.communicate()
        print('TLS server: independent OpenSSL client mTLS cases passed')


if __name__ == '__main__':
    main()
