#!/usr/bin/env python3
"""A hostile peer cannot make an updater allocate its advertised huge body."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os
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
                subprocess.run([str(ROOT/'minyar'), '--library',str(ROOT/'library'),str(source),'-o',str(binary)],
                    env=dict(os.environ,LIMITED='',SANITIZER_LIMITED=''),check=True,capture_output=True,text=True)
                result = subprocess.run([str(binary)],check=True,capture_output=True,text=True,timeout=10)
                self.assertEqual(result.stdout, '200\ngood\n0\n0\ntrue\n0\ntrue\nstill alive\n')
        finally:
            server.shutdown(); server.server_close(); thread.join()

if __name__=='__main__': unittest.main()
