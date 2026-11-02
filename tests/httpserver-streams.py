#!/usr/bin/env python3
"""Streamed httpserver responses through real clients over loopback.

Builds tests/httpserver-streams.min and checks that `curl --no-buffer` and a
WHATWG EventSource (Node's, when available) receive each event as it is written,
that 1,000 concurrent streams stay small in the server, and that closing
clients releases their streams promptly while the rest keep streaming.
"""
import os
from pathlib import Path
import resource
import select
import shutil
import socket
import subprocess
import sys
import tempfile
import time

STREAMS = 1000
PER_STREAM = 16384


def resident(pid):
    status = Path("/proc/" + str(pid) + "/status")
    if status.exists():
        for line in status.read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    return int(subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], check=True, capture_output=True, text=True).stdout) * 1024


def get(port, target):
    with socket.create_connection(("127.0.0.1", port), timeout=30) as connection:
        connection.sendall(("GET " + target + " HTTP/1.1\r\nHost: test\r\nConnection: close\r\n\r\n").encode())
        data = b""
        while True:
            part = connection.recv(65536)
            if not part:
                break
            data += part
    head, _, body = data.partition(b"\r\n\r\n")
    assert head.startswith(b"HTTP/1.1 200"), head
    return body.decode()


def read_until(read, needle, seconds=10):
    data = b""
    deadline = time.monotonic() + seconds
    while needle not in data:
        remaining = deadline - time.monotonic()
        assert remaining > 0, "timed out waiting for %r; received %r" % (needle, data)
        part = read(remaining)
        assert part, "stream closed before %r; received %r" % (needle, data)
        data += part
    return data


def pipe_reader(stream):
    def read(remaining):
        ready, _, _ = select.select([stream], [], [], remaining)
        return os.read(stream.fileno(), 65536) if ready else b"?"
    return read


def socket_reader(connection):
    def read(remaining):
        connection.settimeout(remaining)
        return connection.recv(65536)
    return read


def curl(port):
    process = subprocess.Popen(["curl", "-sS", "--no-buffer", "http://127.0.0.1:%d/events" % port], stdout=subprocess.PIPE)
    try:
        read = pipe_reader(process.stdout)
        first = read_until(read, b"data: 0\n\n")
        assert b"data: 1" not in first
        assert get(port, "/tick") == "1"
        read_until(read, b"data: 1\n\n")
        assert get(port, "/finish") == "1"
        assert process.wait(timeout=10) == 0, "curl did not see the stream end cleanly"
    finally:
        process.kill()
    print("curl --no-buffer: each event arrived before the next was written")


EVENTSOURCE = """
const base = process.argv[1];
const source = new EventSource(base + "/events");
const seen = [];
const timer = setTimeout(() => { console.error("timed out after " + JSON.stringify(seen)); process.exit(2); }, 10000);
source.onmessage = async (event) => {
    seen.push(event.data);
    if (seen.length === 1) { await fetch(base + "/tick"); return; }
    source.close();
    clearTimeout(timer);
    console.log(JSON.stringify(seen));
};
source.onerror = () => { console.error("EventSource error after " + JSON.stringify(seen)); process.exit(1); };
"""


def eventsource(port):
    node = shutil.which("node")
    probe = subprocess.run([node, "--experimental-eventsource", "-e", "process.exit(typeof EventSource === 'function' ? 0 : 1)"],
                           capture_output=True) if node else None
    if not probe or probe.returncode != 0:
        print("EventSource: skipped (needs Node with --experimental-eventsource)")
        return
    result = subprocess.run([node, "--experimental-eventsource", "-e", EVENTSOURCE, "http://127.0.0.1:%d" % port],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    seen = result.stdout.strip()
    assert seen.startswith('["0","') and seen.count(",") == 1, seen
    get(port, "/finish")
    print("EventSource: received " + seen)


def stats(port):
    return [int(value) for value in get(port, "/stats").split()]


def many(port, pid):
    connections = []
    try:
        before = resident(pid)
        for _ in range(STREAMS):
            connection = socket.create_connection(("127.0.0.1", port), timeout=30)
            connection.sendall(b"GET /events HTTP/1.1\r\nHost: test\r\n\r\n")
            connections.append(connection)
        for connection in connections:
            head = read_until(socket_reader(connection), b"data: 0\n\n")
            assert head.startswith(b"HTTP/1.1 200 OK\r\n") and b"transfer-encoding: chunked\r\n" in head, head
        time.sleep(0.2)
        growth = (resident(pid) - before) / STREAMS
        open_streams, released, _ = stats(port)
        assert open_streams == STREAMS, "open streams %d" % open_streams
        assert growth <= PER_STREAM, "an open stream costs %d bytes (limit %d)" % (growth, PER_STREAM)
        event = int(get(port, "/tick"))
        assert event == STREAMS, "tick reached %d streams" % event
        for connection in connections:
            read_until(socket_reader(connection), b"data: ")
        leaving = connections[: STREAMS // 2]
        connections = connections[STREAMS // 2:]
        for connection in leaving:
            connection.close()
        deadline = time.monotonic() + 5
        while True:
            open_streams, now_released, active = stats(port)
            if now_released - released == len(leaving) or time.monotonic() > deadline:
                break
            time.sleep(0.01)
        assert now_released - released == len(leaving) and open_streams == len(connections), \
            "released %d of %d, %d open" % (now_released - released, len(leaving), open_streams)
        assert active == len(connections) + 1, "connections %d" % active
        assert int(get(port, "/tick")) == len(connections)
        assert int(get(port, "/finish")) == len(connections)
        for connection in connections:
            read_until(socket_reader(connection), b"0\r\n\r\n")
    finally:
        for connection in connections:
            connection.close()
    print("%d concurrent streams: %d bytes each (limit %d); %d closed clients released, %d kept streaming"
          % (STREAMS, growth, PER_STREAM, STREAMS // 2, STREAMS - STREAMS // 2))


def main():
    launcher = Path(sys.argv[1]).resolve()
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    wanted = 2 * STREAMS + 256
    if soft < wanted:
        resource.setrlimit(resource.RLIMIT_NOFILE, (wanted if hard == resource.RLIM_INFINITY else min(hard, wanted), hard))
    with tempfile.TemporaryDirectory(prefix="minyar-streams-") as temporary:
        binary = Path(temporary) / "server"
        subprocess.run([str(launcher), "--release", str(launcher.parent / "tests/httpserver-streams.min"), "-o", str(binary)],
                       check=True, stdout=subprocess.DEVNULL, timeout=600)
        server = subprocess.Popen([str(binary)], stdout=subprocess.PIPE)
        try:
            port = int(server.stdout.readline())
            curl(port)
            eventsource(port)
            many(port, server.pid)
            get(port, "/quit")
            assert server.wait(timeout=10) == 0
        finally:
            server.kill()
            server.wait()


if __name__ == "__main__":
    main()
