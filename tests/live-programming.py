#!/usr/bin/env python3
"""Real run --watch acceptance checks, synchronized by output and FIFO handshakes."""

import argparse
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import tempfile
import time


if not __debug__:
    raise SystemExit("live programming checks require Python assertions; remove -O")


ARGUMENTS = [
    "a value with spaces",
    "$(touch SHOULD_NOT_EXIST); 'quoted' \"$HOME\"",
    "",
    "--watch",
    "line one\nline two",
    "a lantern · λ",
]


def timeout_scale():
    try:
        scale = int(os.environ.get("MINYAR_TEST_TIMEOUT_SCALE", "1"))
    except ValueError:
        raise SystemExit("MINYAR_TEST_TIMEOUT_SCALE must be an integer from 1 to 20")
    if not 1 <= scale <= 20:
        raise SystemExit("MINYAR_TEST_TIMEOUT_SCALE must be an integer from 1 to 20")
    return scale


SCALE = timeout_scale()


def publish(path, contents, atomic=True):
    """Exercise both ordinary writes and editor-style atomic replacements."""
    if atomic:
        temporary = path.with_name(path.name + ".replacement")
        temporary.write_text(contents, encoding="utf-8")
        temporary.replace(path)
    else:
        path.write_text(contents, encoding="utf-8")


def manifest(dependency):
    return (
        '[package]\nname = "live-probe"\nversion = "0.1.0"\nkind = "bin"\n'
        '\n[dependencies]\nleaf = { path = "../' + dependency + '" }\n'
    )


def source(revision):
    return '''use "process" as processInfo
use "system" as system
use "./detail/helper.min" as helper
use "leaf" as leaf

print("LIVE START REVISION:" + helper.message() + ":" + leaf.message() + ":" + Text(system.processId()))
print("LIVE COUNT " + Text(processInfo.argumentCount()))
for index in 0..processInfo.argumentCount() {
    print("LIVE ARG " + Text(index) + ":" + processInfo.argument(index))
}
let child = system.spawn("/bin/cat", ["cat", system.getenv("MINYAR_LIVE_TEST_FIFO")], system.environment(), "")
if child <= 0 { fail("could not start the FIFO descendant") }
print("LIVE CAT " + Text(system.childProcessId(child)))
system.wait(child)
fail("the FIFO descendant exited unexpectedly")
'''.replace("REVISION", revision)


def module(message):
    return 'public function message(): Text { return "' + message + '" }\n'


def process_states(pids):
    result = subprocess.run(
        ["ps", "-p", ",".join(str(pid) for pid in sorted(pids)), "-o", "pid=,stat="],
        capture_output=True, text=True, timeout=10 * SCALE,
    )
    assert result.returncode in (0, 1), (result.returncode, result.stderr)
    return {int(fields[0]): fields[1] for line in result.stdout.splitlines()
            if len(fields := line.split()) == 2}


class Watch:
    def __init__(self, launcher, project, fifo, release):
        command = [str(launcher), "run", "--watch", "--manifest-path", str(project)]
        if release:
            command.append("--release")
        command += ["--", *ARGUMENTS]
        self.process = subprocess.Popen(
            command, cwd=project.parent,
            env=dict(os.environ, MINYAR_LIVE_TEST_FIFO=str(fifo)),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True,
        )
        self.selector = selectors.DefaultSelector()
        self.output = {"stdout": bytearray(), "stderr": bytearray()}
        self.pids = set()
        for name, stream in (("stdout", self.process.stdout), ("stderr", self.process.stderr)):
            os.set_blocking(stream.fileno(), False)
            self.selector.register(stream, selectors.EVENT_READ, name)

    def diagnostics(self):
        return "\n".join(name + ":\n" + bytes(data).decode("utf-8", "replace")
                         for name, data in self.output.items())

    def pump(self, deadline, description):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError("timed out waiting for " + description + "\n" + self.diagnostics())
        events = self.selector.select(remaining)
        if not events:
            raise AssertionError("timed out waiting for " + description + "\n" + self.diagnostics())
        for key, _ in events:
            chunk = os.read(key.fd, 65536)
            if chunk:
                self.output[key.data].extend(chunk)
                assert len(self.output[key.data]) < 2 * 1024 * 1024, "unbounded watch output"
            else:
                self.selector.unregister(key.fileobj)

    def wait(self, pattern, channel="stdout", since=0, seconds=180):
        expression = re.compile(re.escape(pattern) if isinstance(pattern, bytes) else pattern)
        deadline = time.monotonic() + seconds * SCALE
        while True:
            match = expression.search(self.output[channel], since)
            if match:
                return match
            if not self.pids and b"[watch] Build failed" in self.output["stderr"]:
                raise AssertionError("initial watch build failed\n" + self.diagnostics())
            if not self.selector.get_map():
                raise AssertionError("watch exited before " + repr(pattern) + "\n" + self.diagnostics())
            self.pump(deadline, repr(pattern))

    def next_run(self, revision, helper, leaf, since=0):
        prefix = ("LIVE START " + ":".join((revision, helper, leaf)) + ":").encode()
        started = self.wait(re.compile(re.escape(prefix) + rb"([0-9]+)\n"), since=since)
        pid = int(started.group(1))
        self.pids.add(pid)
        arguments = ("LIVE COUNT " + str(len(ARGUMENTS)) + "\n" + "".join(
            "LIVE ARG " + str(index) + ":" + argument + "\n"
            for index, argument in enumerate(ARGUMENTS)
        )).encode()
        self.wait(arguments, since=started.end())
        descendant = self.wait(re.compile(rb"LIVE CAT ([0-9]+)\n"), since=started.end())
        child_pid = int(descendant.group(1))
        self.pids.add(child_pid)
        assert pid != child_pid, "the blocking descendant must be a separate process"
        return {pid, child_pid}

    def assert_gone(self, pids):
        active = {pid: state for pid, state in process_states(pids).items() if not state.startswith("Z")}
        assert not active, "owned processes remain active: " + repr(active) + "\n" + self.diagnostics()

    def assert_alive(self, pids):
        states = process_states(pids)
        assert all(pid in states and not states[pid].startswith("Z") for pid in pids), (
            "the previous program or its FIFO descendant died", pids, states, self.diagnostics()
        )

    def stop(self):
        assert self.process.poll() is None, "watch exited before SIGTERM\n" + self.diagnostics()
        self.process.send_signal(signal.SIGTERM)
        deadline = time.monotonic() + 15 * SCALE
        # EOF proves descendants closed the inherited streams; supervisor exit alone does not.
        while self.selector.get_map():
            self.pump(deadline, "supervisor and descendant stdout/stderr EOF after SIGTERM")
        remaining = max(0.001, deadline - time.monotonic())
        status = self.process.wait(timeout=remaining)
        assert status in (0, -signal.SIGTERM, 128 + signal.SIGTERM), (status, self.diagnostics())
        self.assert_gone(self.pids)

    def close(self):
        # A failed assertion must not leave supervisors, compiled programs, or cats running.
        self.pids.update(int(match.group(1)) for match in re.finditer(
            rb"(?m)^LIVE (?:START [^\n]*:|CAT )([0-9]+)\n", self.output["stdout"]
        ))
        if self.process.poll() is None:
            self.pids.add(self.process.pid)
        for pid in self.pids:
            try:
                group = os.getpgid(pid)
                if group != os.getpgrp():
                    os.killpg(group, signal.SIGKILL)
                else:
                    os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(timeout=15 * SCALE)
        self.selector.close()
        self.process.stdout.close()
        self.process.stderr.close()


def check_profile(launcher, release):
    label = "release/O2" if release else "debug/O0"
    with tempfile.TemporaryDirectory(prefix="minyar live ' $ ") as temporary:
        root = Path(temporary)
        project = root / "project with spaces"
        (project / "src/detail").mkdir(parents=True)
        for name, message in (("leaf one", "leaf-one"), ("leaf two", "leaf-two")):
            dependency = root / name
            (dependency / "src").mkdir(parents=True)
            (dependency / "Minyar.toml").write_text(
                '[package]\nname = "leaf"\nversion = "0.1.0"\nkind = "lib"\n', encoding="utf-8"
            )
            (dependency / "src/leaf.min").write_text(module(message), encoding="utf-8")
        manifest_path = project / "Minyar.toml"
        main_path = project / "src/main.min"
        helper_path = project / "src/detail/helper.min"
        publish(manifest_path, manifest("leaf one"))
        publish(main_path, source("first"))
        publish(helper_path, module("helper-one"))
        fifo = root / "control fifo"
        os.mkfifo(fifo)
        # Keep one read/write endpoint open so probes can be queued without a blocking open.
        control = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
        watcher = None
        try:
            watcher = Watch(launcher, project, fifo, release)
            previous = watcher.next_run("first", "helper-one", "leaf-one")
            watcher.wait(b"Watching for changes", channel="stderr")
            target = project / "target" / ("release" if release else "debug") / "live-probe"
            assert target.is_file(), "watch must use the requested project profile"
            assert not (project / "SHOULD_NOT_EXIST").exists()
            assert not (root / "SHOULD_NOT_EXIST").exists()

            def changed(path, contents, revision, helper, leaf, atomic=True):
                nonlocal previous
                cursor = len(watcher.output["stdout"])
                publish(path, contents, atomic=atomic)
                current = watcher.next_run(revision, helper, leaf, since=cursor)
                assert current.isdisjoint(previous), "a successful rebuild must launch a new program"
                watcher.assert_gone(previous)
                previous = current

            changed(main_path, source("second"), "second", "helper-one", "leaf-one")
            changed(helper_path, module("helper-two"), "second", "helper-two", "leaf-one", atomic=False)
            changed(root / "leaf one/src/leaf.min", module("leaf-edited"),
                    "second", "helper-two", "leaf-edited", atomic=False)

            stdout_cursor = len(watcher.output["stdout"])
            stderr_cursor = len(watcher.output["stderr"])
            publish(main_path, 'let broken =\n')
            watcher.wait(re.compile(rb"(?i)build failed"), channel="stderr", since=stderr_cursor)
            watcher.assert_alive(previous)
            os.write(control, b"LIVE PROBE previous-program-still-running\n")
            watcher.wait(b"LIVE PROBE previous-program-still-running\n", since=stdout_cursor, seconds=15)
            watcher.assert_alive(previous)
            assert b"LIVE START " not in watcher.output["stdout"][stdout_cursor:], (
                "a rejected edit must not restart the previous executable", watcher.diagnostics()
            )

            changed(main_path, source("recovered"), "recovered", "helper-two", "leaf-edited")
            changed(manifest_path, manifest("leaf two"), "recovered", "helper-two", "leaf-two")
            changed(root / "leaf two/src/leaf.min", module("new-leaf-edited"),
                    "recovered", "helper-two", "new-leaf-edited")
            watcher.stop()
            print("Live programming " + label + ": initial run, literal arguments, atomic source saves, "
                  "nested import, external dependency, failed-build survival/recovery, manifest graph "
                  "replacement and SIGTERM process-group cleanup passed", flush=True)
        except BaseException:
            if watcher is not None:
                print(watcher.diagnostics(), file=sys.stderr)
            raise
        finally:
            if watcher is not None:
                watcher.close()
            os.close(control)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("launcher", nargs="?", default=str(Path(__file__).resolve().parents[1] / "minyar"))
    parser.add_argument("--profile", choices=("all", "debug", "release"), default="all")
    options = parser.parse_args()
    if sys.platform not in ("linux", "darwin"):
        raise SystemExit("live programming acceptance checks require Linux or macOS")
    launcher = Path(options.launcher).resolve()
    assert launcher.is_file(), "launcher does not exist: " + str(launcher)
    for release in (False, True):
        if options.profile == "all" or options.profile == ("release" if release else "debug"):
            check_profile(launcher, release)


if __name__ == "__main__":
    main()
