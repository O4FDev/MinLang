#!/usr/bin/env python3
"""Idle keep-alive connections stay small in library/httpserver.min.

Builds benchmarks/livepatch/server, completes one request on each of 256
connections, keeps them open and bounds the server's resident growth per
connection. A 64 KiB read reservation once stayed with every idle connection
(66,810 bytes each); the bound is 16 KiB. Needs Linux /proc; skips elsewhere.
"""
import os
from pathlib import Path
import resource
import socket
import subprocess
import sys
import tempfile
import time

CONNECTIONS = 256
LIMIT = 16384


def resident(pid):
    for line in Path("/proc/" + str(pid) + "/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) * 1024
    raise AssertionError("no VmRSS for " + str(pid))


def request(connection):
    connection.sendall(b"GET /hit HTTP/1.1\r\nHost: idle\r\n\r\n")
    data = b""
    while not (b"\r\n\r\n" in data and data.endswith(b"\n") and b"served=" in data):
        chunk = connection.recv(4096)
        assert chunk, "server closed a keep-alive connection"
        data += chunk


def main():
    launcher = Path(sys.argv[1]).resolve()
    if not Path("/proc/self/status").exists():
        print("httpserver idle memory: skipped (needs /proc)")
        return
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft < CONNECTIONS + 64:
        resource.setrlimit(resource.RLIMIT_NOFILE, (min(hard, CONNECTIONS + 64), hard))
    with tempfile.TemporaryDirectory(prefix="minyar-idle-memory-") as temporary:
        binary = Path(temporary) / "server"
        subprocess.run([str(launcher), "--release", str(launcher.parent / "benchmarks/livepatch/server/src/main.min"),
                        "-o", str(binary)], check=True, stdout=subprocess.DEVNULL, timeout=600)
        server = subprocess.Popen([str(binary)], stdout=subprocess.PIPE, env=dict(os.environ, LIVEPATCH_PORT="0"))
        sockets = []
        try:
            port = int(server.stdout.readline().split()[1])
            warm = socket.create_connection(("127.0.0.1", port), timeout=30)
            for _ in range(100):
                request(warm)
            warm.close()
            time.sleep(0.2)
            before = resident(server.pid)
            for _ in range(CONNECTIONS):
                connection = socket.create_connection(("127.0.0.1", port), timeout=30)
                request(connection)
                sockets.append(connection)
            time.sleep(0.3)
            growth = (resident(server.pid) - before) / CONNECTIONS
        finally:
            for connection in sockets:
                connection.close()
            server.kill()
            server.wait()
    assert growth <= LIMIT, "idle keep-alive connection costs %d bytes (limit %d)" % (growth, LIMIT)
    print("httpserver idle memory: %d bytes per idle keep-alive connection (limit %d)" % (growth, LIMIT))


if __name__ == "__main__":
    main()
