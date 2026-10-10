#!/usr/bin/env python3
"""The http package against a local server: bodies, headers, streaming and failures."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    counted = 0

    def log_message(self, *args):
        pass

    def send(self, status, body, kind='text/plain; charset=utf-8'):
        data = body.encode()
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('X-Minyar', 'yes')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == '/plain':
            self.send(200, 'héllo')
        elif self.path == '/stream':
            self.send_response(200)
            self.send_header('Content-Type', 'application/x-ndjson')
            self.send_header('Transfer-Encoding', 'chunked')
            self.end_headers()
            for piece in [b'caf', b'\xc3', b'\xa9 ', b'done']:
                self.wfile.write(b'%x\r\n%s\r\n' % (len(piece), piece))
                self.wfile.flush()
                time.sleep(0.15)
            self.wfile.write(b'0\r\n\r\n')
        elif self.path == '/counted':
            # Cacheable for ten minutes, and different every time.
            Handler.counted += 1
            data = str(Handler.counted).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'public, max-age=600')
            self.end_headers()
            self.wfile.write(data)
        elif self.path == '/slow':
            time.sleep(2)
            self.send(200, 'late')
        else:
            self.send(404, 'no')

    def do_POST(self):
        body = self.rfile.read(int(self.headers['Content-Length'])).decode()
        self.send(201, json.dumps({'method': 'POST', 'test': self.headers['X-Test'], 'body': json.loads(body)['a']},
                                  ensure_ascii=False), 'application/json')

    def do_DELETE(self):
        self.send(404, 'missing')


if sys.platform != 'darwin':
    print('http tests skipped: the http package currently requires macOS')
    sys.exit(0)
server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
with socket.socket() as unused:
    unused.bind(('127.0.0.1', 0))
    closed = unused.getsockname()[1]
with tempfile.TemporaryDirectory(prefix='http-test-', dir=ROOT / 'build') as directory:
    program = Path(directory) / 'http'
    subprocess.run([ROOT / 'minyar', ROOT / 'tests/http.min', '-o', program], check=True, capture_output=True)
    result = subprocess.run([program, f'http://127.0.0.1:{server.server_port}', f'http://127.0.0.1:{closed}/'],
                            capture_output=True, text=True, timeout=60)
server.shutdown()
expected = '''200 OK héllo []
true
201 {"method": "POST", "test": "é", "body": "ü"}
404 Not Found
200 application/x-ndjson café done true
true cancelled
0 true
0 only http:// and https:// URLs are supported: localhost:8080/health
1 2
'''
assert result.returncode == 0 and result.stdout == expected, (result.stdout, result.stderr)
print('http requests, headers, Unicode bodies, streaming, cancellation, failures and no caching verified')
