#!/usr/bin/env python3
"""Finite real-socket regressions for the portable HTTP server package."""
import argparse
import os
from contextlib import contextmanager
from pathlib import Path
import socket
import subprocess
import time

from clang_helpers import launcher_command, windows_host

ROOT = Path(__file__).resolve().parents[1]


class Wire:
    def __init__(self, port, receive_buffer=None):
        self.socket = socket.socket()
        if receive_buffer is not None:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, receive_buffer)
        self.socket.settimeout(2)
        self.socket.connect(('127.0.0.1', port))
        self.input = b''

    def send(self, data):
        self.socket.sendall(data)

    def response(self, *, head=False):
        while b'\r\n\r\n' not in self.input:
            part = self.socket.recv(65536)
            assert part, ('EOF before headers', self.input)
            self.input += part
        header, self.input = self.input.split(b'\r\n\r\n', 1)
        lines = header.split(b'\r\n')
        status = int(lines[0].split()[1])
        fields = {}
        for line in lines[1:]:
            name, value = line.split(b':', 1)
            name = name.lower()
            assert name not in fields, ('duplicate response field', name)
            fields[name] = value.strip()
        assert b'transfer-encoding' not in fields
        length = 0 if head or status in (204, 205, 304) else int(fields[b'content-length'])
        while len(self.input) < length:
            part = self.socket.recv(65536)
            assert part, 'truncated response'
            self.input += part
        body, self.input = self.input[:length], self.input[length:]
        return status, fields, body

    def eof(self):
        assert not self.input, ('unexpected trailing bytes', self.input[:80])
        try:
            assert self.socket.recv(1) == b'', 'socket remained open or sent extra bytes'
        except ConnectionResetError:
            pass

    def close(self):
        self.socket.close()


def request(target='/', *, method='GET', fields=b'', body=b'', close=False):
    return (f'{method} {target} HTTP/1.1\r\nHost: localhost\r\n'.encode() + fields
            + (b'Connection: close\r\n' if close else b'') + b'\r\n' + body)


@contextmanager
def peer(port):
    client = Wire(port)
    try:
        yield client
    finally:
        client.close()


def regressions(port):
    with peer(port) as client:
        data = request(fields=b'Content-Length: 8\r\n', body=b'\x00\xff\r\nbody')
        # Every header delimiter and binary body boundary can be fragmented.
        for byte in data:
            client.send(bytes([byte]))
        assert client.response()[2] == b'\x00\xff\r\nbody'
        client.send(request('/head', method='HEAD') + request('/204')
                    + request('/205') + request('/304') + request('/stale', close=True))
        status, fields, body = client.response(head=True)
        assert status == 200 and fields[b'content-length'] == b'5' and body == b''
        status, fields, body = client.response()
        assert status == 204 and b'content-length' not in fields and body == b''
        status, fields, body = client.response()
        assert status == 205 and fields[b'content-length'] == b'0' and body == b''
        assert client.response()[0] == 304
        assert client.response()[2] == b'safe'
        client.eof()
    invalid = [
        (b'GET / HTTP/1.1\r\n\r\n', 400),
        (request(fields=b'Host: duplicate\r\n'), 400),
        (b'GET / HTTP/1.1\r\nHost: bad host\r\n\r\n', 400),
        (b'GET / HTTP/1.1\r\nHost: [not-ipv6]\r\n\r\n', 400),
        (b'GET / HTTP/1.1\r\nHost: local:999999999999999999999\r\n\r\n', 400),
        (request(fields=b'Content-Length: 0\r\nContent-Length: 0\r\n'), 400),
        (request(fields=b'Content-Length: 0, 0\r\n'), 400),
        (request(fields=b'Content-Length: +1\r\n'), 400),
        (request(fields=b'Content-Length: 999999999999999999999\r\n'), 413),
        (request(fields=b'Transfer-Encoding: chunked\r\nContent-Length: 0\r\n'), 400),
        (request(fields=b'Transfer-Encoding: chunked\r\nTransfer-Encoding: chunked\r\n'), 400),
        (request(fields=b'Transfer-Encoding: chunked\r\n', body=b'0\r\n\r\n'), 501),
        (request(fields=b'Expect: 100-continue\r\nContent-Length: 5\r\n'), 417),
        (request(fields=b'Content-Length : 0\r\n'), 400),
        (request(fields=b' folded: x\r\n'), 400),
        (request(fields=b'X-Bad: \xff\r\n'), 400),
        (request(fields=b'X-Bad: \x00\r\n'), 400),
        (b'GET / HTTP/1.1\nHost: localhost\n\n', 400),
        (request(fields=b'X-Large: ' + b'x' * 1024 + b'\r\n'), 431),
    ]
    for raw, expected in invalid:
        with peer(port) as client:
            client.send(raw + request('/stale'))
            status, fields, _ = client.response()
            assert status == expected, (raw[:100], expected, status)
            assert fields[b'connection'] == b'close'
            client.eof()
    with peer(port) as client:
        client.send(request(method='HEAD', fields=b'Transfer-Encoding: chunked\r\n'))
        assert client.response(head=True)[0] == 501
        client.eof()
    with peer(port) as client:
        client.send(b'OPTIONS * HTTP/1.1\r\nHost: [::1]:80\r\nConnection: close\r\n\r\n')
        assert client.response()[0] == 200
    # Header progress never extends the fixed phase deadline.
    with peer(port) as client:
        client.send(b'GET / HTTP/1.1\r\nHost: localhost\r\nX-Slow: ')
        for _ in range(7):
            time.sleep(0.035)
            try:
                client.send(b'a')
            except (BrokenPipeError, ConnectionResetError):
                break
        assert client.response()[0] == 408
        client.eof()
    with peer(port) as client:
        client.send(request('/injection', close=True))
        assert client.response()[2] == b'rejected'
    with peer(port) as client:
        body = bytes(range(256)) * 256
        client.send(request(fields=b'Content-Length: 65536\r\n', body=body, close=True))
        assert client.response()[2] == body
    # Exact binary replies straddle the packing boundary in an ordered pipeline.
    # The final borrowed body must remain alive across partial range writes.
    with peer(port) as client:
        pattern = bytes(range(256)) * 257
        bodies = [b''] + [pattern[:length] for length in (65535, 65536, 65537)]
        for index, body in enumerate(bodies):
            client.send(request(method='POST', fields=f'Content-Length: {len(body)}\r\n'.encode(),
                                body=body, close=index == len(bodies)-1))
        for body in bodies:
            status, fields, observed = client.response()
            assert status == 200 and fields[b'content-length'] == str(len(body)).encode()
            assert observed == body, ('binary packing boundary or pipeline ordering', len(body))
        client.eof()
    with peer(port) as client:
        client.send(request('/large', close=True))
        assert client.response()[2] == bytes(3145728)
    with peer(port) as client:
        client.send(request(fields=b'Content-Length: 10\r\n', body=b'short'))
        client.socket.shutdown(socket.SHUT_WR)
        assert client.response()[0] == 400
        client.eof()
    with peer(port) as client:
        client.send(request('/head', close=True))
        client.socket.shutdown(socket.SHUT_WR)
        assert client.response()[2] == b'hello'
    # Partial writes and a slow receiver cannot block an unrelated small reply.
    with peer(port) as slow:
        slow.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
        slow.send(request('/large', close=True))
        with peer(port) as fast:
            fast.send(request('/head', close=True))
            assert fast.response()[2] == b'hello'
    for prefix in (b'GET / HTTP/1.1\r\nHost: loca',
                   request(fields=b'Content-Length: 10\r\n', body=b'one'),
                   request('/wait')):
        with peer(port) as slow:
            slow.send(prefix)
            with peer(port) as fast:
                fast.send(request('/head', close=True))
                assert fast.response()[2] == b'hello'
            started = time.monotonic()
            try:
                while slow.socket.recv(65536):
                    pass
            except ConnectionResetError:
                pass
            assert time.monotonic() - started < 1.5, 'deadline did not terminate client'
    # Connection slot reuse and disconnects must remain bounded.
    for _ in range(20):
        with peer(port) as client:
            client.send(request('/head', close=True))
            assert client.response()[2] == b'hello'
    occupied = [Wire(port) for _ in range(4)]
    try:
        for client in occupied:
            client.send(request('/wait'))
        time.sleep(0.025)
        with peer(port) as queued:
            queued.send(request('/head', close=True))
            # The pending backlog is accepted after one application deadline frees a slot.
            assert queued.response()[2] == b'hello'
    finally:
        for client in occupied:
            client.close()
    with peer(port) as client:
        client.send(request('/stats', close=True))
        active, slots = map(int, client.response()[2].split(b':'))
        assert active == 1 and slots <= 4, (active, slots)


def write_wait_regressions(binary, build, environment):
    import queue
    import threading
    observations = []
    for half_close, resume in ((False, False), (True, False), (True, True)):
        with (build/'write-wait-stderr.log').open('w+') as log:
            process = subprocess.Popen([binary], stdout=subprocess.PIPE, stderr=log, text=True, env=environment)
            client = None
            try:
                ready = queue.Queue()
                threading.Thread(target=lambda: ready.put(process.stdout.readline()), daemon=True).start()
                port = int(ready.get(timeout=5))
                client = Wire(port, receive_buffer=4096)
                client.send(request('/large', close=True))
                if half_close:
                    client.socket.shutdown(socket.SHUT_WR)
                # Keep the response backpressured while another client makes progress.
                time.sleep(0.05)
                with peer(port) as fast:
                    fast.send(request('/small', close=True))
                    assert fast.response()[2] == b'ok'
                if resume:
                    client.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4194304)
                    assert client.response()[2] == bytes(4194304), 'valid half-close truncated a response'
                    client.eof()
                output, _ = process.communicate(timeout=3)
                assert process.returncode == 0, process.returncode
                waits, closed_only, ticks, active = map(int, output.strip().split(':'))
                row = dict(half_close=half_close, resume=resume, waits=waits,
                           closed_nonwritable_events=closed_only, timer_ticks=ticks, active=active)
                observations.append(row)
                assert waits <= 300, ('backpressured writer busy-spun', row)
                assert closed_only <= 4, ('persistent nonwritable HUP readiness', row)
                assert ticks >= 5 and active == 0, ('shared timer/deadline/cleanup failed', row)
            finally:
                if client is not None:
                    client.close()
                if process.poll() is None:
                    process.terminate(); process.wait(timeout=3)
                log.seek(0)
                diagnostics = log.read()
                assert not diagnostics, diagnostics
    print('Half-close backpressure observations: ' + repr(observations))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, help='test an already-built fixture')
    parser.add_argument('--write-binary', type=Path, help='already-built shared-loop writer observer')
    parser.add_argument('--write-only', action='store_true', help='run the focused backpressure regression')
    parser.add_argument('--mode', choices=('debug', 'release'), default='debug')
    parser.add_argument('--sanitize', action='store_true')
    args = parser.parse_args()
    if args.binary and not args.write_binary:
        parser.error('--binary requires --write-binary so the mandatory regression is included')
    environment = os.environ.copy()
    if args.sanitize:
        flags = '-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
        environment.update(MINYAR_CLANG_FLAGS=flags, MINYAR_RUNTIME_FLAGS=flags, MINYAR_NATIVE_FLAGS=flags,
                           ASAN_OPTIONS='detect_leaks=' + ('1' if os.sys.platform.startswith('linux') else '0'),
                           UBSAN_OPTIONS='halt_on_error=1')
    build = ROOT / 'build/httpserver'
    build.mkdir(parents=True, exist_ok=True)
    binary = args.binary or build / ('server-' + args.mode + ('.exe' if windows_host() else ''))
    write_binary = args.write_binary or build / ('write-wait-' + args.mode + ('.exe' if windows_host() else ''))
    if not args.binary:
        sources = [(ROOT/'tests/httpserver-write-wait.min', write_binary)]
        if not args.write_only:
            sources.append((ROOT/'tests/httpserver.min', binary))
        for source, program in sources:
            subprocess.run([*launcher_command(ROOT), '--' + args.mode, source,
                            '-o', program], check=True, cwd=ROOT, env=environment, timeout=90)
    write_wait_regressions(write_binary, build, environment)
    if args.write_only:
        return
    with (build / 'stderr.log').open('w+') as log:
        process = subprocess.Popen([binary], stdout=subprocess.PIPE, stderr=log, text=True, env=environment)
        try:
            # Startup is bounded on Windows too; readline lives in a daemon helper.
            import queue
            import threading
            ready = queue.Queue()
            threading.Thread(target=lambda: ready.put(process.stdout.readline()), daemon=True).start()
            port = int(ready.get(timeout=5))
            regressions(port)
            with peer(port) as client:
                client.send(request('/quit', close=True))
                assert client.response()[0] == 200
            assert process.wait(timeout=3) == 0
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=3)
            log.seek(0)
            diagnostics = log.read()
            assert not diagnostics, diagnostics
    print('HTTP server framing, pipeline, deadlines, fairness and cleanup verified')


if __name__ == '__main__':
    main()
