#!/usr/bin/env python3
"""Server memory per idle keep-alive HTTP connection: Minyar, Go and Rust (tokio).

Each server answers GET with `version=1 served=N`. The client opens CONNECTIONS
sockets, completes one request on each, keeps them all open, and reads the
server's VmRSS before and after. Run from the repository root on Linux.
Usage: run.py [connections] [rounds]
"""
import json
import os
import resource
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path.cwd()
HERE = ROOT / "benchmarks/connections"


def rss(pid):
    for line in Path("/proc/" + str(pid) + "/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) * 1024
    raise SystemExit("no VmRSS")


def request(connection):
    connection.sendall(b"GET /hit HTTP/1.1\r\nHost: density\r\n\r\n")
    data = b""
    while b"served=" not in data or not data.endswith(b"\n"):
        chunk = connection.recv(4096)
        if not chunk:
            raise SystemExit("server closed a connection")
        data += chunk


def measure(name, command, connections):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, env=dict(os.environ, LIVEPATCH_PORT="0"))
    try:
        port = int(process.stdout.readline().split()[1])
        warm = socket.create_connection(("127.0.0.1", port))
        for _ in range(100):
            request(warm)
        warm.close()
        time.sleep(0.2)
        before = rss(process.pid)
        sockets = []
        for _ in range(connections):
            connection = socket.create_connection(("127.0.0.1", port))
            request(connection)
            sockets.append(connection)
        time.sleep(0.5)
        after = rss(process.pid)
        for connection in sockets:
            connection.close()
        return {"server": name, "connections": connections, "rss_before": before, "rss_after": after,
                "bytes_per_connection": round((after - before) / connections)}
    finally:
        process.kill()
        process.wait()


def main():
    connections = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
    with tempfile.TemporaryDirectory(prefix="connections-") as temporary:
        base = Path(temporary)
        subprocess.run([str(ROOT / "minyar"), "--release", str(ROOT / "benchmarks/livepatch/server/src/main.min"),
                        "-o", str(base / "minyar")], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["go", "build", "-o", str(base / "go"), str(HERE / "server.go")], check=True,
                       env=dict(os.environ, GOFLAGS="-buildvcs=false"))
        subprocess.run(["cargo", "build", "--release", "--locked", "--quiet", "--manifest-path", str(HERE / "rust/Cargo.toml")],
                       check=True, env=dict(os.environ, CARGO_TARGET_DIR=str(base / "cargo")))
        servers = [("minyar", [str(base / "minyar")]), ("go", [str(base / "go")]),
                   ("rust-tokio", [str(base / "cargo/release/connections-rust")])]
        for _ in range(rounds):
            for name, command in servers:
                print(json.dumps(measure(name, command, connections)), flush=True)


if __name__ == "__main__":
    main()
