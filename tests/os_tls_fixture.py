"""Independent OpenSSL mTLS peer and one exact, disposable CI trust anchor.

Installing a root is restricted to GitHub's disposable macOS runner. It never
runs on a developer workstation. Cleanup removes only the generated root.
"""
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import ssl
import subprocess
import sys
import threading


def openssl(*arguments):
    return subprocess.run(['openssl', *map(str, arguments)], check=True, capture_output=True, text=True, timeout=30).stdout


class TLSServer(ThreadingHTTPServer):
    def __init__(self, address, handler, context):
        self.context = context
        super().__init__(address, handler)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(10)
        try:
            return self.context.wrap_socket(connection, server_side=True), address
        except BaseException:
            connection.close()
            raise


class Peer:
    def __init__(self, directory, client_certificate):
        self.directory = Path(directory)
        self.root = self.directory/'os-root.pem'
        self.accepted = 0
        self.spied = 0
        openssl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                '-subj', '/CN=Minyar disposable OS TLS root', '-keyout', self.directory/'os-root.key', '-out', self.root)
        openssl('req', '-new', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=localhost',
                '-keyout', self.directory/'os-server.key', '-out', self.directory/'os-server.csr')
        extensions = self.directory/'os-server.ext'
        extensions.write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\n'
                              'extendedKeyUsage=serverAuth\nsubjectAltName=IP:127.0.0.1\n')
        openssl('x509', '-req', '-in', self.directory/'os-server.csr', '-CA', self.root,
                '-CAkey', self.directory/'os-root.key', '-CAcreateserial', '-days', '1',
                '-extfile', extensions, '-out', self.directory/'os-server.pem')
        expected = hashlib.sha256(ssl.PEM_cert_to_DER_cert(Path(client_certificate).read_text())).digest()
        peer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                assert hashlib.sha256(self.connection.getpeercert(binary_form=True)).digest() == expected
                peer.accepted += 1
                if self.path == '/redirect':
                    self.send_response(302)
                    self.send_header('Location', f'https://127.0.0.1:{peer.spy.server_port}/')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header('Content-Length', '2')
                self.send_header('Connection', 'close')
                self.end_headers()
                self.wfile.write(b'ok')

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.load_cert_chain(self.directory/'os-server.pem', self.directory/'os-server.key')
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(client_certificate)
        self.server = TLSServer(('127.0.0.1', 0), Handler, context)
        class Spy(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                peer.spied += 1
                self.send_response(200)
                self.send_header('Content-Length', '2')
                self.end_headers()
                self.wfile.write(b'ok')

        spy_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        spy_context.load_cert_chain(self.directory/'os-server.pem', self.directory/'os-server.key')
        self.spy = TLSServer(('127.0.0.1', 0), Spy, spy_context)
        self.spy_thread = threading.Thread(target=self.spy.serve_forever, daemon=True)
        self.spy_thread.start()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'https://127.0.0.1:{self.server.server_port}/'

    @contextmanager
    def trusted(self):
        if not (sys.platform == 'darwin' and os.environ.get('GITHUB_ACTIONS') == 'true'
                and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
                and os.environ.get('RUNNER_OS') == 'macOS'):
            raise RuntimeError('OS root installation requires a disposable GitHub macOS runner')
        fingerprint = openssl('x509', '-in', self.root, '-noout', '-fingerprint', '-sha1').strip().split('=')[1].replace(':', '')
        keychain = '/Library/Keychains/System.keychain'
        installed = False
        try:
            subprocess.run(['sudo', '-n', 'security', 'add-trusted-cert', '-d', '-r', 'trustRoot', '-k', keychain, self.root],
                           check=True, capture_output=True, timeout=30)
            installed = True
            yield
        finally:
            # Exact freshly generated certificate only. A cleanup failure fails
            # the test; it cannot turn a failed handshake into a pass.
            failures = []
            for command in (['sudo', '-n', 'security', 'remove-trusted-cert', '-d', self.root],
                            ['sudo', '-n', 'security', 'delete-certificate', '-Z', fingerprint, keychain]):
                try:
                    result = subprocess.run(command, capture_output=True, timeout=30)
                except subprocess.TimeoutExpired as error:
                    failures.append(str(error))
                else:
                    if result.returncode:
                        failures.append(result.stderr.decode(errors='replace'))
            if installed and failures:
                raise RuntimeError('could not remove the disposable OS TLS root: ' + '; '.join(failures))

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.spy.shutdown()
        self.spy.server_close()
        self.spy_thread.join(timeout=5)
