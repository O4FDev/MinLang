#!/usr/bin/env python3
"""A hostile peer cannot make an updater allocate its advertised huge body."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import ExitStack
from pathlib import Path
import os
import queue
import socket
import subprocess
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]

class Peer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Length', '999999999999999999999' if self.path == '/huge' else '4')
        self.end_headers()
        try:
            if self.path == '/drip':
                for byte in b'good':
                    self.wfile.write(bytes([byte])); self.wfile.flush(); time.sleep(0.04)
            else:
                self.wfile.write(b'x' * 131072 if self.path == '/huge' else b'good')
        except (BrokenPipeError, ConnectionResetError):
            pass
    def log_message(self, *args):
        pass

class BoundedHTTP(unittest.TestCase):
    def test_small_response_succeeds_and_over_limit_response_is_recoverable(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Peer)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix='minyar-bounded-http-') as temporary:
                temp = Path(temporary)
                source = temp/'test.min'
                source.write_text('use "http" as http\n'
                    f'let base = "http://127.0.0.1:{server.server_port}"\n'
                    'let small = http.getBounded(base + "/small", [], 4)\n'
                    'print(small.status); print(small.body)\n'
                    'let huge = http.getBounded(base + "/huge", [], 32)\n'
                    'print(huge.status); print(huge.body.length); print(huge.error != "")\n'
                    'let drip = http.getBoundedWithin(base + "/drip", [], 4, 60)\n'
                    'print(drip.status); print(drip.error != "")\n'
                    'print("still alive")\n')
                binary = temp/('test.exe' if os.name=='nt' else 'test')
                environment = dict(os.environ, LIMITED='', SANITIZER_LIMITED='')
                if environment.get('MINYAR_LINK_ARTIFACTS'):
                    environment['MINYAR_LINK_ARTIFACTS'] = str(Path(environment['MINYAR_LINK_ARTIFACTS'])/'bounded')
                subprocess.run([str(ROOT/'minyar'), '--library',str(ROOT/'library'),str(source),'-o',str(binary)],
                    env=environment,check=True,capture_output=True,text=True)
                result = subprocess.run([str(binary)],check=True,capture_output=True,text=True,timeout=10)
                self.assertEqual(result.stdout, '200\ngood\n0\n0\ntrue\n0\ntrue\nstill alive\n')
                self.assertEqual(result.stderr, '')
        finally:
            server.shutdown(); server.server_close(); thread.join()


class AuthorityPeer(BaseHTTPRequestHandler):
    """Observe the actual HTTP request, independently of Minyar's URL parser."""
    def do_GET(self):
        self.server.requests.put((self.path, self.headers.get('Host')))
        self.send_response(200)
        self.send_header('Content-Length', '4')
        self.end_headers()
        self.wfile.write(b'good')

    def log_message(self, *args):
        pass


class IPv6HTTPServer(ThreadingHTTPServer):
    address_family = socket.AF_INET6


class HTTPAuthority(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resources = ExitStack()
        try:
            cls.servers = []
            for server_type, host in [(ThreadingHTTPServer, '127.0.0.1'),
                                      (IPv6HTTPServer, '::1')]:
                server = server_type((host, 0), AuthorityPeer)
                server.requests = queue.Queue()
                cls.resources.callback(server.server_close)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                cls.resources.callback(thread.join, 2)
                cls.resources.callback(server.shutdown)
                cls.servers.append(server)
            temporary = cls.resources.enter_context(
                tempfile.TemporaryDirectory(prefix='minyar-http-authority-'))
            temp = Path(temporary)
            source = temp/'authority.min'
            source.write_text('use "http" as http\nuse "net" as net\n'
                'if argumentCount() == 2 {\n'
                'let address = argument(0)\n'
                'if argument(1) == "nul" { let bytes = Bytes(address); bytes.add(0); bytes.addBytes(Bytes("suffix")); address = Text(bytes) }\n'
                'print(net.ipVersion(address))\n} else {\n'
                'let response = http.getBoundedWithin(argument(0), [], 4, 500)\n'
                'print(response.status); print(response.body)\n'
                'print(response.error != ""); print("still alive")\n}\n')
            cls.binary = temp/('authority.exe' if os.name == 'nt' else 'authority')
            environment = dict(os.environ, LIMITED='', SANITIZER_LIMITED='')
            if environment.get('MINYAR_LINK_ARTIFACTS'):
                environment['MINYAR_LINK_ARTIFACTS'] = str(Path(environment['MINYAR_LINK_ARTIFACTS'])/'authority')
            subprocess.run([str(ROOT/'minyar'), '--library', str(ROOT/'library'),
                            str(source), '-o', str(cls.binary)],
                env=environment, check=True, capture_output=True, text=True)
        except BaseException:
            cls.resources.close()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.resources.close()

    def request(self, url):
        result = subprocess.run([str(self.binary), url], capture_output=True,
                                text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        return result.stdout

    def test_numeric_literal_classification_uses_strict_ip_syntax(self):
        cases = [('127.0.0.1', 4), ('::1', 6), ('0:0:0:0:0:0:0:1', 6),
                 ('::ffff:127.0.0.1', 6), ('localhost', 0), ('127.1', 0),
                 ('1234', 0), ('256.0.0.1', 0), ('[::1]', 0),
                 ('[127.0.0.1]', 0), ('::gg', 0), ('::1%lo', 0),
                 ('', 0), ('1' * 256, 0)]
        for address, expected in cases:
            with self.subTest(address=address):
                result = subprocess.run([str(self.binary), address, 'literal'],
                    capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, '')
                self.assertEqual(result.stdout, f'{expected}\n')
        for address in ['127.0.0.1', '::1']:
            with self.subTest(address=address, embedded_nul=True):
                result = subprocess.run([str(self.binary), address, 'nul'],
                    capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, '')
                self.assertEqual(result.stdout, '0\n')

    def test_literal_hosts_preserve_wire_authority_and_request_target(self):
        ipv4, ipv6 = self.servers
        cases = [
            (ipv4, '127.0.0.1', '/small', '/small'),
            (ipv4, 'localhost', '/small', '/small'),
            (ipv4, '[::ffff:127.0.0.1]', '/small', '/small'),
            (ipv4, '127.0.0.1', '/encoded%3Apart?key=value%3Apart', '/encoded%3Apart?key=value%3Apart'),
            (ipv4, '127.0.0.1', '/path:part?key=value:part', '/path:part?key=value:part'),
            (ipv4, '127.0.0.1', '?key=value:part', '/?key=value:part'),
            (ipv4, '127.0.0.1', '/small?key=value:part#local:fragment', '/small?key=value:part'),
            (ipv4, '127.0.0.1', '#local:fragment', '/'),
            (ipv6, '[::1]', '/small', '/small'),
            (ipv6, '[0:0:0:0:0:0:0:1]', '/path:part?key=value:part', '/path:part?key=value:part'),
            (ipv6, '[::1]', '?key=value:part', '/?key=value:part'),
            (ipv6, '[::1]', '/small?key=value:part#local:fragment', '/small?key=value:part'),
            (ipv6, '[::1]', '#local:fragment', '/'),
        ]
        for server, host, suffix, target in cases:
            authority = f'{host}:{server.server_port}'
            with self.subTest(url=f'http://{authority}{suffix}'):
                try:
                    self.assertEqual(self.request(f'http://{authority}{suffix}'),
                                     '200\ngood\nfalse\nstill alive\n')
                    self.assertEqual(server.requests.get(timeout=2),
                                     (target, authority))
                finally:
                    # Keep one failing case from contaminating the next oracle.
                    while not server.requests.empty():
                        server.requests.get_nowait()

    def test_malformed_authorities_are_recoverable_and_send_no_request(self):
        ipv4, ipv6 = self.servers
        port = ipv6.server_port
        # This nondecimal port evaluates to our listening port under the old
        # unchecked character arithmetic; accepting it must reach our oracle.
        confused_port = (str(ipv4.server_port // 10 - 4) +
                         chr(88 + ipv4.server_port % 10))
        invalid = [
            f'http://::1:{port}/small',
            f'http://[::1:{port}/small',
            f'http://::1]:{port}/small',
            f'http://[[::1]]:{port}/small',
            f'http://[::1]extra:{port}/small',
            f'http://[localhost]:{port}/small',
            f'http://[::gg]:{port}/small',
            f'http://[127.0.0.1]:{ipv4.server_port}/small',
            f'http://[::1]:{port}:80/small',
            'http://[::1]:abc/small',
            'http://[::1]:-1/small',
            'http://[::1]:0/small',
            'http://[::1]:65536/small',
            'http://[::1]:' + '9' * 80 + '/small',
            'http://127.0.0.1:abc/small',
            f'http://127.0.0.1:{confused_port}/small',
            'http://127.0.0.1:0/small',
            'http://127.0.0.1:65536/small',
            'http://127.0.0.1:' + '9' * 80 + '/small',
            f'http://user@127.0.0.1:{ipv4.server_port}/small',
            f'http://127.0.0.1:{ipv4.server_port}@127.0.0.1/small',
        ]
        for url in invalid:
            with self.subTest(url=url):
                try:
                    self.assertEqual(self.request(url), '0\n\ntrue\nstill alive\n')
                    self.assertTrue(ipv4.requests.empty())
                    self.assertTrue(ipv6.requests.empty())
                finally:
                    for server in self.servers:
                        while not server.requests.empty():
                            server.requests.get_nowait()

if __name__=='__main__': unittest.main()
