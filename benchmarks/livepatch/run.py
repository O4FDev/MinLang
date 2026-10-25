#!/usr/bin/env python3
"""Live-patch experiment: change a running HTTP server's code under load.

Modes (run from the repository root on Linux with go on PATH):
  hot      minyar run --watch --hot --release; edit reply() mid-load.
  restart  build v1 and v2 release binaries; mid-load stop v1 and start v2
           on the same port (what a process-per-version deploy does).
  steady   no edit: hot-mode server versus the plain release binary.
  watch    no edit: minyar run --watch --release without --hot.
Prints one JSON summary per run.
"""
import json
import os
import selectors
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path.cwd()
HERE = ROOT / "benchmarks/livepatch"
LAUNCHER = ROOT / "minyar"
CONNECTIONS = int(os.environ.get("LIVEPATCH_CONNECTIONS", "8"))
SECONDS = float(os.environ.get("LIVEPATCH_SECONDS", "6"))
EDIT_AT = float(os.environ.get("LIVEPATCH_EDIT_AT", "2"))
CPUS = os.environ.get("LIVEPATCH_SERVER_CPUS", "0-3")
LOAD_CPUS = os.environ.get("LIVEPATCH_LOAD_CPUS", "4-7")


def edited(source, version):
    return source.replace('"version=1 served="', '"version=' + str(version) + ' served="')


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Process:
    def __init__(self, command, environment, cwd):
        self.process = subprocess.Popen(
            ["taskset", "-c", CPUS, *command], cwd=cwd, env=dict(os.environ, **environment),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True)
        self.selector = selectors.DefaultSelector()
        self.text = {"stdout": b"", "stderr": b""}
        for name, stream in (("stdout", self.process.stdout), ("stderr", self.process.stderr)):
            os.set_blocking(stream.fileno(), False)
            self.selector.register(stream, selectors.EVENT_READ, name)

    def pump(self, seconds):
        for key, _ in self.selector.select(seconds):
            chunk = key.fileobj.read()
            if chunk:
                self.text[key.data] += chunk

    def wait_for(self, marker, seconds=600):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            for name in ("stdout", "stderr"):
                if marker in self.text[name]:
                    return self.text[name]
            if self.process.poll() is not None:
                self.pump(0)
                raise SystemExit("process exited: " + repr(self.text))
            self.pump(0.05)
        raise SystemExit("timed out waiting for " + repr(marker) + ": " + repr(self.text))

    def port(self):
        line = self.wait_for(b"LISTENING ").split(b"LISTENING ", 1)[1].split(b"\n", 1)[0]
        return int(line)

    def stop(self):
        if self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(10)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait()


def server_pid(process, hot):
    if not hot:
        return process.process.pid
    found = subprocess.run(["pgrep", "-s", str(process.process.pid), "-f", "target/release/livepatch-server"],
                           capture_output=True, text=True).stdout.split()
    return int(found[0]) if found else None


def count_instructions(pid):
    """With LIVEPATCH_PERF=1, count the server's user-mode instructions during the load."""
    if os.environ.get("LIVEPATCH_PERF") != "1" or pid is None:
        return None
    return subprocess.Popen(["perf", "stat", "-x,", "-e", "instructions:u", "-p", str(pid)],
                            stderr=subprocess.PIPE, text=True)


def instructions(counter):
    if counter is None:
        return None
    counter.send_signal(signal.SIGINT)
    for line in counter.communicate()[1].splitlines():
        fields = line.split(",")
        if len(fields) > 2 and fields[2].startswith("instructions") and fields[0].isdigit():
            return int(fields[0])
    return None


def load(port, output):
    return subprocess.Popen(["taskset", "-c", LOAD_CPUS, str(load_binary), "127.0.0.1:" + str(port),
                             str(CONNECTIONS), str(SECONDS), str(output)])


def percentile(values, fraction):
    if not values:
        return None
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * fraction))]


def summarize(mode, output, edit_unix_ns, retired=None):
    rows = []
    origin = 0
    for line in Path(output).read_text().splitlines():
        if line.startswith("# origin_unix_ns="):
            origin = int(line.split("=", 1)[1])
            continue
        conn, start, latency, status, version, served = line.split(",")
        rows.append((int(start) + origin, int(latency), status == "ok", int(version), int(served)))
    ok = [r for r in rows if r[2]]
    summary = {"mode": mode, "connections": CONNECTIONS, "seconds": SECONDS,
               "ok": len(ok), "errors": len(rows) - len(ok),
               "requests_per_second": round(len(ok) / SECONDS),
               "p50_us": percentile([r[1] for r in ok], 0.5) // 1000,
               "p99_us": percentile([r[1] for r in ok], 0.99) // 1000,
               "max_us": max(r[1] for r in ok) // 1000}
    if retired:
        summary["server_instructions_per_request"] = round(retired / len(ok))
    if edit_unix_ns:
        v2 = [r for r in ok if r[3] == 2]
        v1 = [r for r in ok if r[3] == 1]
        first_v2 = min((r[0] + r[1] for r in v2), default=None)
        window = [r for r in rows if edit_unix_ns - 500_000_000 <= r[0] <= edit_unix_ns + 2_000_000_000]
        summary.update({
            "v1_responses": len(v1), "v2_responses": len(v2),
            "edit_to_first_v2_ms": None if first_v2 is None else round((first_v2 - edit_unix_ns) / 1e6, 1),
            "v1_completed_after_first_v2": sum(1 for r in v1 if first_v2 and r[0] + r[1] > first_v2),
            "last_v1_served": max((r[4] for r in v1), default=None),
            "first_v2_served": min((r[4] for r in v2), default=None),
            "errors_in_window": sum(1 for r in window if not r[2]),
            "window_max_ms": round(max((r[1] for r in window if r[2]), default=0) / 1e6, 2),
            "longest_gap_ms": round(longest_gap(ok) / 1e6, 1),
        })
    print(json.dumps(summary), flush=True)


def longest_gap(ok):
    ends = sorted(r[0] + r[1] for r in ok)
    return max((b - a for a, b in zip(ends, ends[1:])), default=0)


def project_copy(base):
    project = base / "server"
    (project / "src").mkdir(parents=True)
    (project / "Minyar.toml").write_text((HERE / "server/Minyar.toml").read_text())
    (project / "src/main.min").write_text((HERE / "server/src/main.min").read_text())
    return project


def publish(path, contents):
    temporary = path.with_name(path.name + ".replacement")
    temporary.write_text(contents)
    temporary.replace(path)


def run_hot(base, edit, hot=True):
    project = project_copy(base)
    server = Process([str(LAUNCHER), "run", "--watch", *(["--hot"] if hot else []), "--release",
                      "--manifest-path", str(project)], {"LIVEPATCH_PORT": "0"}, project)
    try:
        port = server.port()
        server.wait_for(b"Watching for changes")
        output = base / "hot.csv"
        counter = count_instructions(server_pid(server, True))
        client = load(port, output)
        edit_ns = 0
        if edit:
            time.sleep(EDIT_AT)
            source = (project / "src/main.min").read_text()
            edit_ns = time.time_ns()
            publish(project / "src/main.min", edited(source, 2))
        while client.poll() is None:
            server.pump(0.05)
        summarize("hot" if edit else "steady-hot" if hot else "steady-watch", output, edit_ns, instructions(counter))
    finally:
        server.stop()


def build(base, version):
    source = base / ("v" + str(version) + ".min")
    source.write_text(edited((HERE / "server/src/main.min").read_text(), version))
    binary = base / ("server-v" + str(version))
    subprocess.run([str(LAUNCHER), "--release", str(source), "-o", str(binary)], check=True,
                   stdout=subprocess.DEVNULL)
    return binary


def run_restart(base, edit):
    v1 = build(base, 1)
    v2 = build(base, 2) if edit else None
    port = free_port()
    environment = {"LIVEPATCH_PORT": str(port)}
    server = Process([str(v1)], environment, base)
    try:
        server.port()
        output = base / "restart.csv"
        counter = None if edit else count_instructions(server_pid(server, False))
        client = load(port, output)
        edit_ns = 0
        if edit:
            time.sleep(EDIT_AT)
            edit_ns = time.time_ns()
            server.stop()
            server = Process([str(v2)], environment, base)
            server.port()
        while client.poll() is None:
            server.pump(0.05)
        summarize("restart" if edit else "steady-release", output, edit_ns, instructions(counter))
    finally:
        server.stop()


if __name__ == "__main__":
    modes = sys.argv[1:] or ["hot", "restart", "steady"]
    with tempfile.TemporaryDirectory(prefix="livepatch-") as temporary:
        base = Path(temporary)
        load_binary = base / "load"
        subprocess.run(["go", "build", "-o", str(load_binary), str(HERE / "load.go")], check=True,
                       env=dict(os.environ, GOFLAGS="-buildvcs=false"))
        for mode in modes:
            work = base / mode
            work.mkdir()
            if mode == "hot":
                run_hot(work, True)
            elif mode == "restart":
                run_restart(work, True)
            elif mode == "watch":
                run_hot(work, False, hot=False)
            elif mode == "steady":
                run_hot(work, False)
                (work / "plain").mkdir()
                run_restart(work / "plain", False)
