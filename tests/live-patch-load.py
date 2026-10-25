#!/usr/bin/env python3
"""A function update reaches a serving process without dropping requests or state.

Runs benchmarks/livepatch/server under `minyar run --watch --hot`, keeps several
keep-alive HTTP clients busy, edits reply() mid-load and checks that every
request succeeded, each connection moved from version 1 to version 2 exactly
once, and the server's request counter continued across the update.
"""
import argparse
import os
from pathlib import Path
import selectors
import signal
import socket
import subprocess
import tempfile
import threading
import time

SCALE = int(os.environ.get("MINYAR_TEST_TIMEOUT_SCALE", "1"))
CLIENTS = 4


class Client(threading.Thread):
    def __init__(self, port, stop):
        super().__init__(daemon=True)
        self.port, self.stop = port, stop
        self.responses = []   # (version, served) in completion order
        self.errors = []

    def exchange(self, connection):
        connection.sendall(b"GET /hit HTTP/1.1\r\nHost: livepatch\r\n\r\n")
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = connection.recv(1)
            if not chunk:
                raise ConnectionError("server closed before a response")
            head += chunk
        lines = head.decode("ascii").split("\r\n")
        if " 200 " not in lines[0]:
            raise ConnectionError("unexpected status " + lines[0])
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                name, value = line.split(":", 1)
                headers[name.strip().lower()] = value.strip().lower()
        body = b""
        while len(body) < int(headers["content-length"]):
            chunk = connection.recv(int(headers["content-length"]) - len(body))
            if not chunk:
                raise ConnectionError("server closed during a body")
            body += chunk
        fields = dict(item.split("=", 1) for item in body.decode("ascii").split())
        self.responses.append((int(fields["version"]), int(fields["served"])))
        return headers.get("connection") == "close"

    def run(self):
        connection = None
        while not self.stop.is_set():
            try:
                if connection is None:
                    connection = socket.create_connection(("127.0.0.1", self.port), timeout=30 * SCALE)
                if self.exchange(connection):
                    connection.close()
                    connection = None
            except (OSError, ValueError, KeyError) as error:
                self.errors.append(repr(error))
                if connection is not None:
                    connection.close()
                connection = None
        if connection is not None:
            connection.close()


def wait_for(process, selector, output, marker, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if marker in output["stdout"] or marker in output["stderr"]:
            return
        assert process.poll() is None, ("watcher exited", output)
        for key, _ in selector.select(0.1):
            output[key.data] += key.fileobj.read() or b""
    raise AssertionError(("timed out waiting for", marker, output))


def check(launcher, release):
    source = launcher.parent / "benchmarks/livepatch/server"
    with tempfile.TemporaryDirectory(prefix="minyar-live-patch-") as temporary:
        project = Path(temporary) / "server"
        (project / "src").mkdir(parents=True)
        (project / "Minyar.toml").write_text((source / "Minyar.toml").read_text())
        main = project / "src/main.min"
        main.write_text((source / "src/main.min").read_text())
        command = [str(launcher), "run", "--watch", "--hot", "--manifest-path", str(project)]
        if release:
            command.append("--release")
        process = subprocess.Popen(command, cwd=project, env=dict(os.environ, LIVEPATCH_PORT="0"),
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True)
        selector = selectors.DefaultSelector()
        output = {"stdout": b"", "stderr": b""}
        for name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        stop = threading.Event()
        clients = []
        try:
            wait_for(process, selector, output, b"LISTENING ", 300 * SCALE)
            wait_for(process, selector, output, b"Watching for changes", 60 * SCALE)
            port = int(output["stdout"].split(b"LISTENING ", 1)[1].split(b"\n", 1)[0])
            clients = [Client(port, stop) for _ in range(CLIENTS)]
            for client in clients:
                client.start()
            time.sleep(1.0)
            replacement = main.with_name("main.min.replacement")
            replacement.write_text(main.read_text().replace('"version=1 served="', '"version=2 served="'))
            replacement.replace(main)
            deadline = time.monotonic() + 300 * SCALE
            while not all(c.responses and c.responses[-1][0] == 2 for c in clients):
                assert time.monotonic() < deadline, ("update never reached every client", output)
                assert all(not c.errors for c in clients), [c.errors for c in clients]
                for key, _ in selector.select(0.1):
                    output[key.data] += key.fileobj.read() or b""
            time.sleep(0.5)
        finally:
            stop.set()
            for client in clients:
                client.join(30 * SCALE)
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(30 * SCALE)
        errors = [error for client in clients for error in client.errors]
        assert not errors, errors
        for client in clients:
            versions = [version for version, _ in client.responses]
            assert versions == sorted(versions) and versions[0] == 1 and versions[-1] == 2, versions[:3]
        responses = [response for client in clients for response in client.responses]
        last_v1 = max(served for version, served in responses if version == 1)
        first_v2 = min(served for version, served in responses if version == 2)
        assert first_v2 == last_v1 + 1, (last_v1, first_v2)
        served = sorted(served for _, served in responses)
        assert served == list(range(1, len(served) + 1)), "every request is counted exactly once"
        assert b"program state preserved" in output["stderr"], output["stderr"][-2000:]
        print("live patch under load (" + ("release" if release else "debug") + "): " + str(len(responses)) +
              " requests, 0 errors, update at request " + str(first_v2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("launcher", type=Path)
    parser.add_argument("--profile", choices=("debug", "release"), default="debug")
    args = parser.parse_args()
    check(args.launcher.resolve(), args.profile == "release")


if __name__ == "__main__":
    main()
