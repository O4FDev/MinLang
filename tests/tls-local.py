#!/usr/bin/env python3
"""Fetch from a local TLS 1.3 server with the Minyar `http` and `tls` packages.

A throwaway self-signed certificate is generated with the openssl command; the
Minyar client offers only TLS_CHACHA20_POLY1305_SHA256 with X25519, so this
also checks that OpenSSL accepts that offer.
"""
import http.server
import os
import ssl
import subprocess
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BODY = 'Minyar spoke TLS 1.3: ' + 'é' * 3 + ' ' + 'x' * 40000


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        data = BODY.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *arguments):
        pass


def main():
    with tempfile.TemporaryDirectory() as directory:
        key = os.path.join(directory, 'key.pem')
        certificate = os.path.join(directory, 'certificate.pem')
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                        '-subj', '/CN=localhost', '-keyout', key, '-out', certificate],
                       check=True, capture_output=True)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.load_cert_chain(certificate, key)
        server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        program = os.path.join(ROOT, 'build', 'tls-fetch')
        subprocess.run([os.path.join(ROOT, 'minyar'), os.path.join(ROOT, 'examples/fetch/main.min'), '-o', program],
                       check=True, capture_output=True)
        result = subprocess.run([program, f'https://localhost:{port}/'], capture_output=True, text=True, timeout=60)
        server.shutdown()
    output = result.stdout
    if result.returncode != 0 or '200 OK' not in output or BODY not in output:
        print('TLS fetch failed:', output[:400], result.stderr[:400], file=sys.stderr)
        sys.exit(1)
    print('TLS 1.3 exchange with a local OpenSSL server verified')


main()
