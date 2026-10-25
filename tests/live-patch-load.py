#!/usr/bin/env python3
"""A function update reaches a serving process without dropping requests or state.

Serves benchmarks/livepatch/server either under `minyar run --watch --hot` or as
a `minyar build --hot` binary updated by `minyar patch`, keeps several
keep-alive HTTP clients busy, edits reply() mid-load and checks that every
request succeeded, each connection moved from version 1 to version 2 exactly
once, and the server's request counter continued across the update. The patch
mode also checks that an incompatible edit is refused while serving continues,
and that a copy deployed elsewhere (MINYAR_LIVE_STATE) takes a patch shipped as
plain files.
"""
import argparse
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import socket
import struct
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
        assert process.poll() is None, ("server exited", output)
        for key, _ in selector.select(0.1):
            output[key.data] += key.fileobj.read() or b""
    raise AssertionError(("timed out waiting for", marker, output))


def ship(state, host):
    """Ship a patch as files, first out of order: the table and epoch arrive before
    the generation they name, so the load fails; once the generation is there,
    writing the epoch again retries it."""
    shutil.copyfile(state / "current", host / "current.incoming")
    (host / "current.incoming").replace(host / "current")

    def announce(value):
        # The deployed counter is read-only to the program (F8); only the shipper writes it.
        (host / "current.epoch").chmod(0o644)
        with open(host / "current.epoch", "r+b") as epoch:
            epoch.write(value)
        (host / "current.epoch").chmod(0o444)
    announce((state / "current.epoch").read_bytes())
    time.sleep(0.5)
    for generation in state.glob("generation-*"):
        if not (host / generation.name).exists():
            shutil.copytree(generation, host / generation.name)
    announce(struct.pack("<Q", struct.unpack("<Q", (state / "current.epoch").read_bytes())[0] + 1000))


def check(launcher, release, deploy, relocate=False):
    source = launcher.parent / "benchmarks/livepatch/server"
    with tempfile.TemporaryDirectory(prefix="minyar-live-patch-") as temporary:
        project = Path(temporary) / "server"
        (project / "src").mkdir(parents=True)
        (project / "Minyar.toml").write_text((source / "Minyar.toml").read_text())
        main = project / "src/main.min"
        main.write_text((source / "src/main.min").read_text())
        profile = ["--release"] if release else []
        command = [str(launcher), "run", "--watch", "--hot", "--manifest-path", str(project), *profile]
        if deploy:
            built = subprocess.run([str(launcher), "build", "--hot", "--manifest-path", str(project), *profile],
                                   capture_output=True, timeout=600 * SCALE)
            assert built.returncode == 0, built
            command = [str(project / "target" / ("release" if release else "debug") / "livepatch-server")]
        environment = dict(os.environ, LIVEPATCH_PORT="0")
        if not deploy:
            # A relocation setting left in the shell does not redirect the watched program (F7).
            environment["MINYAR_LIVE_STATE"] = str(Path(temporary) / "elsewhere")
        if relocate:
            # A deployed copy: the binary and its live state elsewhere, patched by shipping files.
            built_state = Path((project / "target" / ("release" if release else "debug") / "livepatch-server.live").read_text())
            host = Path(temporary) / "host"
            shutil.copytree(built_state, host / "state")
            shutil.copy2(command[0], host / "server")
            command = [str(host / "server")]
            # Relative, and resolved once: the program may change directory later (F8).
            environment["MINYAR_LIVE_STATE"] = "host/state"
            (host / "state/current.epoch").write_bytes(bytes(8))
            (host / "state/current.epoch").chmod(0o444)
        process = subprocess.Popen(command, cwd=Path(temporary) if relocate else project, env=environment,
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
            if not deploy:
                wait_for(process, selector, output, b"Watching for changes", 60 * SCALE)
            port = int(output["stdout"].split(b"LISTENING ", 1)[1].split(b"\n", 1)[0])
            clients = [Client(port, stop) for _ in range(CLIENTS)]
            for client in clients:
                client.start()
            time.sleep(1.0)
            replacement = main.with_name("main.min.replacement")
            replacement.write_text(main.read_text().replace('"version=1 served="', '"version=2 served="'))
            replacement.replace(main)
            if deploy:
                patched = subprocess.run([str(launcher), "patch", "--manifest-path", str(project), *profile],
                                         capture_output=True, timeout=600 * SCALE)
                assert patched.returncode == 0 and b"Published update" in patched.stderr, patched
                if relocate:
                    ship(built_state, host / "state")
            if deploy and not relocate:
                # A copy started after the publication runs it from its first request.
                late = subprocess.Popen(command, cwd=project, env=environment, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
                try:
                    late_port = int(late.stdout.readline().split()[1])
                    probe = Client(late_port, threading.Event())
                    with socket.create_connection(("127.0.0.1", late_port), timeout=30 * SCALE) as connection:
                        probe.exchange(connection)
                    assert probe.responses == [(2, 1)], probe.responses
                finally:
                    late.kill()
                    late.wait()
                # It started on the update; nothing was reloaded (G6).
                late_errors = late.stderr.read()
                assert b"Reloaded" not in late_errors and b"minyar live:" not in late_errors, late_errors
            deadline = time.monotonic() + 300 * SCALE
            while not all(c.responses and c.responses[-1][0] == 2 for c in clients):
                assert time.monotonic() < deadline, ("update never reached every client", output)
                assert all(not c.errors for c in clients), [c.errors for c in clients]
                for key, _ in selector.select(0.1):
                    output[key.data] += key.fileobj.read() or b""
            time.sleep(0.5)
            if deploy and not relocate:
                # A changed record layout cannot be patched; the old code keeps serving.
                source = main.read_text()
                main.write_text(source.replace("served: Integer; keys", "served: Integer; extra: Integer; keys")
                                .replace("served: 0; keys", "served: 0; extra: 0; keys"))
                refused = subprocess.run([str(launcher), "patch", "--manifest-path", str(project), *profile],
                                         capture_output=True, timeout=600 * SCALE)
                assert refused.returncode != 0 and b"function-body edits and additions" in refused.stderr, refused
                time.sleep(0.3)
                assert all(c.responses[-1][0] == 2 for c in clients) and process.poll() is None
        finally:
            stop.set()
            for client in clients:
                client.join(30 * SCALE)
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(30 * SCALE)
            for name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
                output[name] += stream.read() or b""
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
        print(("shipped patch" if relocate else "minyar patch" if deploy else "live patch") + " under load (" + ("release" if release else "debug") +
              "): " + str(len(responses)) +
              " requests, 0 errors, update at request " + str(first_v2))


def check_idle_patches(launcher, memory=""):
    """Two patches published while the server is idle both take effect: each table is complete.
    With memory set, the package's reclamation profile also applies to the patchable build."""
    source = launcher.parent / "benchmarks/livepatch/server"
    with tempfile.TemporaryDirectory(prefix="minyar-live-idle-") as temporary:
        project = Path(temporary) / "server"
        (project / "src").mkdir(parents=True)
        manifest = (source / "Minyar.toml").read_text()
        if memory:
            manifest = manifest.replace('kind = "bin"\n', 'kind = "bin"\nmemory = "' + memory + '"\n')
        (project / "Minyar.toml").write_text(manifest)
        main = project / "src/main.min"
        main.write_text((source / "src/main.min").read_text())
        built = subprocess.run([str(launcher), "build", "--hot", "--manifest-path", str(project)],
                               capture_output=True, timeout=600 * SCALE)
        assert built.returncode == 0, built
        server = subprocess.Popen([str(project / "target/debug/livepatch-server")], stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, env=dict(os.environ, LIVEPATCH_PORT="0"))
        state = Path((project / "target/debug/livepatch-server.live").read_text())
        try:
            port = int(server.stdout.readline().split()[1])
            client = Client(port, threading.Event())

            def ask():
                with socket.create_connection(("127.0.0.1", port), timeout=30 * SCALE) as connection:
                    client.exchange(connection)
                return client.responses[-1]
            assert ask() == (1, 1)
            main.write_text(main.read_text().replace('"version=1 served="', '"version=9 served="'))
            dry = subprocess.run([str(launcher), "patch", "--dry-run", "--manifest-path", str(project)],
                                 capture_output=True, timeout=600 * SCALE)
            assert dry.returncode == 0 and b"Dry run: nothing published. Image carries 1 function(s): reply" in dry.stderr, dry
            assert ask() == (1, 2), client.responses
            main.write_text(main.read_text().replace('"version=9 served="', '"version=1 served="'))
            for old, new in (('"version=1 served="', '"version=2 served="'), ("STORE.served += 1", "STORE.served += 10")):
                main.write_text(main.read_text().replace(old, new))
                patched = subprocess.run([str(launcher), "patch", "--manifest-path", str(project)],
                                         capture_output=True, timeout=600 * SCALE)
                assert patched.returncode == 0, patched
            # The table is complete: both edited functions, named for the operator.
            assert b"Image carries 2 function(s): " in patched.stderr and b"reply" in patched.stderr and b"remember" in patched.stderr, patched.stderr
            assert ask() == (2, 12), client.responses

            def undo():
                return subprocess.run([str(launcher), "patch", "--undo", "--manifest-path", str(project)],
                                      capture_output=True, timeout=600 * SCALE)
            # Undo restores the previous table without compiling, back to the original program.
            assert undo().returncode == 0 and ask() == (2, 13), client.responses
            assert undo().returncode == 0 and ask() == (1, 14), client.responses
            refused = undo()
            assert refused.returncode != 0 and b"nothing to undo" in refused.stderr, refused
            assert ask() == (1, 15), client.responses
            # Undo sets each entry aside before restoring it; nothing is left behind (G6).
            assert not list(state.glob("history-*")), list(state.iterdir())

            def patch():
                return subprocess.run([str(launcher), "patch", "--manifest-path", str(project)],
                                      capture_output=True, timeout=600 * SCALE)
            # History is bounded and crash leftovers are collected (G6): twenty old
            # entries and an orphaned generation before the next publication.
            # The source still has both edits (version 2, served += 10).
            main.write_text(main.read_text().replace('"version=2 served="', '"version=3 served="'))
            assert patch().returncode == 0 and ask() == (3, 25), client.responses
            table = (state / "current").read_bytes()
            for number in range(1, 21):
                (state / ("history-" + str(number))).write_bytes(table)
            for leftover in ("history-21.pending", "history-4.restoring", "history-2.4242", "current.4242"):
                (state / leftover).write_bytes(b"crash")
            (state / "generation-orphan").mkdir()
            main.write_text(main.read_text().replace('"version=3 served="', '"version=4 served="'))
            published = patch()
            assert published.returncode == 0 and ask() == (4, 35), published
            names = sorted(path.name for path in state.iterdir())
            history = sorted(int(name[len("history-"):]) for name in names if name.startswith("history-"))
            assert history == list(range(6, 22)), names
            assert not any(name.endswith((".pending", ".restoring", ".4242")) for name in names), names
            generations = [name for name in names if name.startswith("generation-")]
            assert "generation-orphan" not in generations and len(generations) == 2, names
            # A malformed session file is named as such (F9).
            main.write_text(main.read_text().replace('"version=4 served="', '"version=5 served="'))
            exports = (state / "exports").read_bytes()
            (state / "exports").write_bytes(b"live-pairs-v1\n9:short\n")
            broken = patch()
            assert broken.returncode != 0 and b"exports file" in broken.stderr and b"malformed" in broken.stderr, broken
            (state / "exports").write_bytes(exports)
            # A table that loads but names a missing function is reported once, however
            # often it is announced (G6).
            (state / "current.next").write_bytes(b"\0".join(table.split(b"\0")[:3] + [b"reply", b"no.such.symbol", b""]))
            (state / "current.next").replace(state / "current")
            for _ in range(2):
                with open(state / "current.epoch", "r+b") as epoch:
                    value = struct.unpack("<Q", epoch.read(8))[0]
                    epoch.seek(0)
                    epoch.write(struct.pack("<Q", value + 1))
                assert ask()[0] == 4, client.responses
            # A binary replaced by an ordinary build ends its session (F9).
            plain = subprocess.run([str(launcher), "build", "--manifest-path", str(project)], capture_output=True,
                                   timeout=600 * SCALE)
            assert plain.returncode == 0, plain
            assert not (project / "target/debug/livepatch-server.live").exists() and not state.exists(), plain
            stale = patch()
            assert stale.returncode != 0 and b"no patchable build" in stale.stderr, stale
        finally:
            server.kill()
            server.wait()
        errors = server.stderr.read()
        assert errors.count(b"invalid function table") == 1, errors
    print("idle patches" + (" (" + memory + ")" if memory else "") + ": two publications without calls between them both apply; undo restores each")


def check_foreign_patch(launcher):
    """A copy pointed at another build's live state keeps its own code."""
    source = launcher.parent / "benchmarks/livepatch/server"
    with tempfile.TemporaryDirectory(prefix="minyar-live-foreign-") as temporary:
        project = Path(temporary) / "server"
        (project / "src").mkdir(parents=True)
        (project / "Minyar.toml").write_text((source / "Minyar.toml").read_text())
        main = project / "src/main.min"
        main.write_text((source / "src/main.min").read_text())
        target = project / "target/debug"

        def build():
            built = subprocess.run([str(launcher), "build", "--hot", "--manifest-path", str(project)],
                                   capture_output=True, timeout=600 * SCALE)
            assert built.returncode == 0, built
        build()
        shutil.copy2(target / "livepatch-server", Path(temporary) / "first-build")
        build()
        main.write_text(main.read_text().replace('"version=1 served="', '"version=2 served="'))
        patched = subprocess.run([str(launcher), "patch", "--manifest-path", str(project)], capture_output=True,
                                 timeout=600 * SCALE)
        assert patched.returncode == 0, patched
        state = Path((target / "livepatch-server.live").read_text())
        server = subprocess.Popen([str(Path(temporary) / "first-build")], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  env=dict(os.environ, LIVEPATCH_PORT="0", MINYAR_LIVE_STATE=str(state)))
        try:
            port = int(server.stdout.readline().split()[1])
            client = Client(port, threading.Event())
            with socket.create_connection(("127.0.0.1", port), timeout=30 * SCALE) as connection:
                client.exchange(connection)
            assert client.responses == [(1, 1)], client.responses
        finally:
            server.kill()
            server.wait()
        refused = server.stderr.read()
        # Tables name the executable they were built for (F7).
        assert b"update was built for another executable" in refused, refused
        assert refused.count(b"minyar live:") == 1, ("a refused update is reported once", refused)
        # A relocation that does not exist is reported, and the copy runs its own code (F8).
        server = subprocess.Popen([str(Path(temporary) / "first-build")], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  env=dict(os.environ, LIVEPATCH_PORT="0", MINYAR_LIVE_STATE=str(Path(temporary) / "missing")))
        try:
            port = int(server.stdout.readline().split()[1])
            client = Client(port, threading.Event())
            with socket.create_connection(("127.0.0.1", port), timeout=30 * SCALE) as connection:
                client.exchange(connection)
            assert client.responses == [(1, 1)], client.responses
        finally:
            server.kill()
            server.wait()
        missing = server.stderr.read()
        assert b"cannot use MINYAR_LIVE_STATE=" in missing and missing.count(b"minyar live:") == 1, missing
    print("foreign patch: a copy pointed at another build's state, or at none, keeps its own code")


def check_build_noise(launcher):
    """Hot builds and patches print no linker-flag warnings, tool diagnostics keep their line
    breaks (A12), and a watch session that replaces a build --hot binary ends its session (G6)."""
    source = launcher.parent / "benchmarks/livepatch/server"
    with tempfile.TemporaryDirectory(prefix="minyar-live-noise-") as temporary:
        project = Path(temporary) / "server"
        (project / "src").mkdir(parents=True)
        (project / "Minyar.toml").write_text((source / "Minyar.toml").read_text())
        main = project / "src/main.min"
        main.write_text((source / "src/main.min").read_text())
        # A private native cache, so every native object really compiles here.
        fresh = dict(os.environ, MINYAR_CACHE_DIR=str(Path(temporary) / "cache"))
        built = subprocess.run([str(launcher), "build", "--hot", "--manifest-path", str(project)],
                               capture_output=True, timeout=600 * SCALE, env=fresh)
        assert built.returncode == 0 and b"input unused" not in built.stderr and b"\\u{" not in built.stderr, built
        main.write_text(main.read_text().replace('"version=1 served="', '"version=2 served="'))
        patched = subprocess.run([str(launcher), "patch", "--manifest-path", str(project)],
                                 capture_output=True, timeout=600 * SCALE, env=fresh)
        assert patched.returncode == 0 and b"input unused" not in patched.stderr and b"\\u{" not in patched.stderr, patched
        session = project / "target/debug/livepatch-server.live"
        state = Path(session.read_text())
        watch = subprocess.Popen([str(launcher), "run", "--watch", "--hot", "--manifest-path", str(project)],
                                 env=dict(os.environ, LIVEPATCH_PORT="0"), stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            assert watch.stdout.readline().startswith(b"LISTENING "), "the watched program did not start"
        finally:
            os.killpg(watch.pid, signal.SIGTERM)
            watch.wait(30 * SCALE)
        assert not session.exists() and not state.exists(), "a watch session replaced the build --hot binary"
        # Explicit native flags with linker-only items: each clang warning on its own line.
        noisy = dict(os.environ, MINYAR_CACHE_DIR=str(Path(temporary) / "noisy"),
                     MINYAR_NATIVE_FLAGS="-O0 -Wl,--as-needed -Wl,-z,now")
        plain = subprocess.run([str(launcher), "build", "--manifest-path", str(project)],
                               capture_output=True, timeout=600 * SCALE, env=noisy)
        assert plain.returncode == 0 and b"\\u{000a}" not in plain.stderr, plain
        assert re.search(rb"-Wl,--as-needed: 'linker' input unused[^\n]*\n[^\n]*-Wl,-z,now: 'linker' input unused", plain.stderr), plain.stderr
    print("build noise: hot builds and patches print no linker warnings; diagnostics keep their lines; watch ends a hot session")


PARALLEL_SERVER = """use "httpserver" as http
use "errors" as errors
use "system" as system
use "text" as text

record Store { served: Integer }
global STORE: Store = Store { served: 0 }

parallel function weight(index: Integer): Integer {
    return index * 1
}

function total(): Integer {
    let values: List<Integer> = []
    let index = 0
    while index < 65536 { values.add(0); index += 1 }
    parallel for slot in 0..values.length {
        values[slot] = weight(slot)
    }
    let sum = 0
    for value in values { sum += value }
    return sum
}

function reply(target: Text): Bytes {
    STORE.served += 1
    return Bytes("version=" + Text(total() / 2147450880) + " served=" + Text(STORE.served) + "\\n")
}

function port(): Integer {
    let raw = system.getenv("LIVEPATCH_PORT")
    if raw == "" { return 0 }
    return text.integer(raw).unwrapOr(0)
}

let server = http.listen("127.0.0.1", port(), http.defaults())
if !http.ok(server) { fail(errors.message(http.serverError(server))) }
print("LISTENING " + Text(http.port(server)))
let running = true
while running {
    let batch = http.poll(server, 20)
    if errors.isError(http.batchError(batch)) { running = false }
    for request in http.requests(batch) {
        http.respond(server, request, http.response(200, "text/plain", reply(request.target)))
    }
}
http.close(server)
"""


def check_parallel_patch(launcher):
    """A program whose requests run a parallel loop takes a patch to the loop's function."""
    with tempfile.TemporaryDirectory(prefix="minyar-live-parallel-") as temporary:
        project = Path(temporary) / "server"
        (project / "src").mkdir(parents=True)
        (project / "Minyar.toml").write_text('[package]\nname = "livepatch-server"\nversion = "0.1.0"\nkind = "bin"\n')
        main = project / "src/main.min"
        main.write_text(PARALLEL_SERVER)
        built = subprocess.run([str(launcher), "build", "--hot", "--manifest-path", str(project)],
                               capture_output=True, timeout=600 * SCALE)
        assert built.returncode == 0, built
        server = subprocess.Popen([str(project / "target/debug/livepatch-server")], stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, env=dict(os.environ, LIVEPATCH_PORT="0",
                                                                      MINYAR_PARALLEL_THREADS="4"))
        try:
            port = int(server.stdout.readline().split()[1])
            client = Client(port, threading.Event())

            def ask():
                with socket.create_connection(("127.0.0.1", port), timeout=30 * SCALE) as connection:
                    client.exchange(connection)
                return client.responses[-1]
            assert ask() == (1, 1), client.responses
            main.write_text(main.read_text().replace("return index * 1", "return index * 2"))
            patched = subprocess.run([str(launcher), "patch", "--manifest-path", str(project)],
                                     capture_output=True, timeout=600 * SCALE)
            assert patched.returncode == 0, patched
            assert ask() == (2, 2), client.responses
            # Patch repeatedly while clients keep the parallel loop busy.
            stop = threading.Event()
            clients = [Client(port, stop) for _ in range(CLIENTS)]
            for each in clients:
                each.start()
            for factor in (3, 4, 5):
                time.sleep(0.3)
                main.write_text(main.read_text().replace("return index * " + str(factor - 1), "return index * " + str(factor)))
                patched = subprocess.run([str(launcher), "patch", "--manifest-path", str(project)],
                                         capture_output=True, timeout=600 * SCALE)
                assert patched.returncode == 0, patched
            deadline = time.monotonic() + 60 * SCALE
            while not all(each.responses and each.responses[-1][0] == 5 for each in clients):
                assert time.monotonic() < deadline and all(not each.errors for each in clients), [c.errors for c in clients]
                time.sleep(0.05)
            stop.set()
            for each in clients:
                each.join(30 * SCALE)
            assert all(not each.errors for each in clients), [each.errors for each in clients]
            for each in clients:
                versions = [version for version, _ in each.responses]
                assert versions == sorted(versions) and set(versions) <= {2, 3, 4, 5}, versions[:5]
        finally:
            server.kill()
            server.wait()
    print("parallel patch: a parallel loop's function is replaced while its workers run, four times")


THREAD_PROGRAM = """use "system" as system
use "process" as process

function weight(seed: Integer): Integer { return seed * 1 }
thread function worker(seed: Integer, input: FrozenBytes, channel: BytesChannel): Integer { return weight(seed) }
record Store { count: Integer }
global STORE: Store = Store { count: 0 }
function round(): Integer {
    let channel = bytesChannel(0, 1)
    let handle = startThread(worker, 21, freezeBytes(Bytes()), channel)
    let result = joinThread(handle)
    closeBytesChannel(channel)
    STORE.count += 1
    return result
}
function main() {
    nativeThreadSetup()
    let i = 0
    while i < 400 {
        print("ROUND " + Text(STORE.count) + " " + Text(round()))
        process.sleepNanoseconds(50000000)
        i += 1
    }
}
"""


def check_thread_patch(launcher, release):
    """A function that managed threads call is replaced; the main thread's state continues."""
    with tempfile.TemporaryDirectory(prefix="minyar-live-thread-") as temporary:
        project = Path(temporary) / "probe"
        (project / "src").mkdir(parents=True)
        (project / "Minyar.toml").write_text('[package]\nname = "threadprobe"\nversion = "0.1.0"\nkind = "bin"\n')
        main = project / "src/main.min"
        main.write_text(THREAD_PROGRAM)
        profile = ["--release"] if release else []
        built = subprocess.run([str(launcher), "build", "--hot", "--manifest-path", str(project), *profile],
                               capture_output=True, timeout=600 * SCALE)
        assert built.returncode == 0, built
        program = subprocess.Popen([str(project / "target" / ("release" if release else "debug") / "threadprobe")],
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        try:
            rounds = []

            def until(value):
                deadline = time.monotonic() + 60 * SCALE
                while time.monotonic() < deadline:
                    words = program.stdout.readline().split()
                    rounds.append((int(words[1]), int(words[2])))
                    if rounds[-1][1] == value:
                        return
                raise AssertionError(rounds[-5:])
            until(21)
            main.write_text(main.read_text().replace("return seed * 1", "return seed * 2"))
            patched = subprocess.run([str(launcher), "patch", "--manifest-path", str(project), *profile],
                                     capture_output=True, timeout=600 * SCALE)
            assert patched.returncode == 0, patched
            until(42)
            until(42)
        finally:
            program.kill()
            program.wait()
        counts = [count for count, _ in rounds]
        assert counts == list(range(counts[0], counts[0] + len(counts))), counts
        results = [value for _, value in rounds]
        assert results == sorted(results) and set(results) <= {21, 42}, results
    print("thread patch (" + ("release" if release else "debug") + "): a function managed threads call is replaced")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("launcher", type=Path)
    parser.add_argument("--profile", choices=("debug", "release"), default="debug")
    parser.add_argument("--mode", choices=("watch", "patch", "both"), default="both")
    args = parser.parse_args()
    if args.mode != "patch":
        check(args.launcher.resolve(), args.profile == "release", False)
    if args.mode != "watch":
        check_build_noise(args.launcher.resolve())
        check_idle_patches(args.launcher.resolve())
        check_idle_patches(args.launcher.resolve(), "eager")
        check_foreign_patch(args.launcher.resolve())
        check_parallel_patch(args.launcher.resolve())
        check_thread_patch(args.launcher.resolve(), args.profile == "release")
        check(args.launcher.resolve(), args.profile == "release", True)
        check(args.launcher.resolve(), args.profile == "release", True, True)


if __name__ == "__main__":
    main()
