#!/usr/bin/env python3
"""Edit-to-observation time for a small HTTP service: Minyar, Rust and Go.

Each round edits the reply text and measures until an HTTP client sees it.
- minyar-hot:   `minyar run --watch --hot` (debug); process and state are kept.
- minyar-watch: `minyar run --watch` (debug); rebuild and restart.
- rust:         `cargo build` (debug, incremental) then restart, as cargo-watch does.
- go:           `go build` then restart.
Run from the repository root on Linux. Usage: run.py [rounds]
"""
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path.cwd()
LAUNCHER = ROOT / "minyar"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def fetch(port):
    data = b""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5) as c:
            c.sendall(b"GET / HTTP/1.1\r\nHost: edit\r\nConnection: close\r\n\r\n")
            while not data.endswith(b"\n") or b"served=" not in data:
                chunk = c.recv(4096)
                if not chunk:
                    break
                data += chunk
    except OSError:
        pass
    return data.decode("latin1")


def wait_for(port, marker, seconds=300):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if marker in fetch(port):
            return time.monotonic()
        time.sleep(0.005)
    raise SystemExit("timed out waiting for " + marker)


def edit(path, old, new):
    text = path.read_text()
    assert old in text, (path, old)
    temporary = path.with_name(path.name + ".edit")
    temporary.write_text(text.replace(old, new))
    temporary.replace(path)


def minyar(base, rounds, hot):
    project = base / "server"
    (project / "src").mkdir(parents=True)
    shutil.copy(ROOT / "benchmarks/livepatch/server/Minyar.toml", project / "Minyar.toml")
    shutil.copy(ROOT / "benchmarks/livepatch/server/src/main.min", project / "src/main.min")
    port = free_port()
    command = [str(LAUNCHER), "run", "--watch", "--manifest-path", str(project)] + (["--hot"] if hot else [])
    watcher = subprocess.Popen(command, env=dict(os.environ, LIVEPATCH_PORT=str(port)), stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        wait_for(port, "version=1 ")
        times = []
        for round in range(rounds):
            started = time.monotonic()
            edit(project / "src/main.min", '"version=' + str(round + 1) + ' served="', '"version=' + str(round + 2) + ' served="')
            times.append(wait_for(port, "version=" + str(round + 2) + " ") - started)
            time.sleep(0.5)
        return times
    finally:
        os.killpg(watcher.pid, signal.SIGTERM)
        watcher.wait()


def rebuild_restart(base, rounds, source, old_template, build, binary, environment):
    port = free_port()
    times = []
    server = None
    try:
        subprocess.run(build, check=True, cwd=base, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        server = subprocess.Popen([str(binary)], env=dict(os.environ, LIVEPATCH_PORT=str(port), **environment),
                                  stdout=subprocess.DEVNULL)
        wait_for(port, "version=1 ")
        for round in range(rounds):
            started = time.monotonic()
            edit(source, old_template.format(round + 1), old_template.format(round + 2))
            subprocess.run(build, check=True, cwd=base, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            server.terminate()
            server.wait()
            server = subprocess.Popen([str(binary)], env=dict(os.environ, LIVEPATCH_PORT=str(port), **environment),
                                      stdout=subprocess.DEVNULL)
            times.append(wait_for(port, "version=" + str(round + 2) + " ") - started)
            time.sleep(0.5)
        return times
    finally:
        if server:
            server.kill()
            server.wait()


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    with tempfile.TemporaryDirectory(prefix="editloop-") as temporary:
        base = Path(temporary)
        results = {}
        for name, hot in (("minyar-hot", True), ("minyar-watch", False)):
            work = base / name
            work.mkdir()
            results[name] = minyar(work, rounds, hot)
        rust = base / "rust"
        shutil.copytree(ROOT / "benchmarks/connections/rust", rust)
        source = rust / "src/main.rs"
        results["rust"] = rebuild_restart(rust, rounds, source, '"version={} served=', ["cargo", "build", "--locked", "--quiet"],
                                          rust / "target/debug/connections-rust", {})
        go = base / "go"
        go.mkdir()
        shutil.copy(ROOT / "benchmarks/connections/server.go", go / "server.go")
        (go / "go.mod").write_text("module editloop\n\ngo 1.21\n")
        results["go"] = rebuild_restart(go, rounds, go / "server.go", '"version={} served=', ["go", "build", "-o", "server", "."],
                                        go / "server", {"GOFLAGS": "-buildvcs=false"})
        for name, times in results.items():
            ordered = sorted(times)
            print(json.dumps({"variant": name, "rounds": len(times), "median_s": round(ordered[len(ordered) // 2], 3),
                              "min_s": round(ordered[0], 3), "max_s": round(ordered[-1], 3),
                              "state_kept": name == "minyar-hot"}), flush=True)


if __name__ == "__main__":
    main()
