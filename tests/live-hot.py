#!/usr/bin/env python3
"""Function updates preserve the actual process, global roots and heap aliases."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import sys
import tempfile
import time

from importlib.util import module_from_spec, spec_from_file_location
_spec = spec_from_file_location("watch_checks", Path(__file__).with_name("live-programming.py"))
_watch = module_from_spec(_spec)
_spec.loader.exec_module(_watch)
Watch, publish, SCALE = _watch.Watch, _watch.publish, _watch.SCALE


class ClangCounter:
    """Count real native work while forwarding the selected Clang unchanged."""
    def __init__(self, launcher, directory):
        support = (launcher.parent / "tools/driver-support.min").read_text(encoding="utf-8")
        version = re.search(r'public constant LLVM_VERSION = "([^"]+)"', support).group(1)
        cached = Path.home() / ".cache/minyar/toolchains" / ("llvm-" + version) / "bin/clang"
        fallback = "clang" if (os.environ.get("MINYAR_TEST_HOST_SYSTEM") == "Darwin" or
                               sys.platform == "darwin") else "clang-23"
        if cached.is_file() and os.access(cached, os.X_OK):
            fallback = str(cached)
        selected = os.environ.get("MINYAR_CLANG", os.environ.get(
            "LLVM_CC", os.environ.get("MINYAR_BUNDLED_CLANG", fallback)))
        real = shutil.which(selected)
        assert real, "selected real Clang is not executable: " + repr(selected)
        real = str(Path(real).resolve())
        self.log = directory / "clang-calls.jsonl"
        self.wrapper = directory / "clang counter.py"
        self.wrapper.write_text(
            "#!" + sys.executable + "\n" +
            "REAL = " + repr(real) + "\nLOG = " + repr(str(self.log)) + "\n" + '''import fcntl, json, os, sys
from pathlib import Path
arguments = sys.argv[1:]
inputs = [item for item in arguments if not item.startswith("-") and
          Path(item).suffix in (".c", ".m", ".ll", ".o", ".a", ".s")]
probe = any(item in ("--version", "-E", "-print-runtime-dir", "-print-search-dirs",
                    "-dumpmachine", "-dumpversion", "-dumpfullversion") or
            item.startswith("-print-file-name=") for item in arguments)
probe = probe or any(Path(item).name in ("probe.c", "probe.ll") for item in inputs)
if inputs and not probe:
    descriptor = os.open(LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        payload = (json.dumps(arguments, ensure_ascii=True) + "\\n").encode("utf-8")
        while payload:
            payload = payload[os.write(descriptor, payload):]
    finally:
        os.close(descriptor)
os.execv(REAL, [REAL, *arguments])
''', encoding="utf-8")
        self.wrapper.chmod(0o755)

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]


def accepted_publication(project, release):
    profile = project / "target" / ("release" if release else "debug")
    current_files = sorted(profile.glob(".live-*/current"))
    assert len(current_files) == 1, ("expected one accepted live publication", current_files)
    current = current_files[0]
    data = current.read_bytes()
    fields = data.split(b"\0")
    assert len(fields) > 2 and fields[0], ("invalid accepted function table", data)
    image = Path(os.fsdecode(fields[0]))
    assert image.name == "update.so" and image.parent.parent == current.parent, image
    sidecar = image.with_name("source-identity")
    identity = sidecar.read_bytes()
    assert re.fullmatch(rb"live-snapshot-v1\n[0-9a-f]{64}\n[0-9a-f]{64}\n[0-9a-f]{64}\n", identity), identity
    assert identity.splitlines()[2].decode("ascii") == hashlib.sha256(image.read_bytes()).hexdigest(), (
        "accepted source identity must authenticate the exact native image", sidecar
    )
    assert identity.splitlines()[3].decode("ascii") == hashlib.sha256(data).hexdigest(), (
        "accepted source identity must authenticate the complete function table", sidecar
    )
    status = current.stat()
    generations = tuple(sorted(path.name for path in current.parent.glob("generation-*") if path.is_dir()))
    return current, image, sidecar, (data, status.st_dev, status.st_ino, generations, identity)


def program(revision):
    return '''use "system" as system
record State { count: Integer; history: List<Text> }
global STATE: State = State { count: 0; history: [] }
function step() {
    STATE.count += 1
    STATE.history.add("REVISION")
    print("VALUE REVISION " + Text(STATE.count) + " " + Text(STATE.history.length) + " " + STATE.history[0])
}
print("PID " + Text(system.processId()))
while true {
    let child = system.spawn("/bin/cat", ["cat", system.getenv("MINYAR_HOT_FIFO")], system.environment(), "")
    if child < 0 { fail("cannot launch FIFO reader") }
    print("WAIT " + Text(system.childProcessId(child)))
    system.wait(child)
    step()
}
'''.replace('REVISION', revision)


def begin(launcher, project, fifo, release, environment=None):
    watch = Watch.__new__(Watch)
    command = [str(launcher), "run", "--watch", "--hot", "--manifest-path", str(project)]
    if release:
        command += ["--release"]
    watch.process = subprocess.Popen(
        command, cwd=project, env=dict(os.environ, MINYAR_HOT_FIFO=str(fifo), **(environment or {})),
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True,
    )
    watch.selector = selectors.DefaultSelector()
    watch.output = {"stdout": bytearray(), "stderr": bytearray()}
    watch.pids = set()
    for name, stream in (("stdout", watch.process.stdout), ("stderr", watch.process.stderr)):
        os.set_blocking(stream.fileno(), False)
        watch.selector.register(stream, selectors.EVENT_READ, name)
    return watch


def check(launcher, release):
    with tempfile.TemporaryDirectory(prefix="minyar-hot-λ ") as temporary:
        directory = Path(temporary)
        project = directory / "project"
        project.mkdir()
        counter = ClangCounter(launcher, directory)
        (project / "src").mkdir()
        (project / "Minyar.toml").write_text(
            '[package]\nname = "hot-probe"\nversion = "0.1.0"\nkind = "bin"\n', encoding="utf-8"
        )
        source = project / "src/main.min"
        publish(source, program("first"))
        fifo = project / "tick"
        os.mkfifo(fifo)
        watch = begin(launcher, project, fifo, release, {"MINYAR_CLANG": str(counter.wrapper)})
        try:
            pid = int(watch.wait(re.compile(rb"PID ([0-9]+)\n")).group(1))
            watch.pids.add(pid)
            position = 0

            def step(expected):
                nonlocal position
                waiting = watch.wait(re.compile(rb"WAIT ([0-9]+)\n"), since=position)
                watch.pids.add(int(waiting.group(1)))
                # The real reader is blocked opening this FIFO. Closing this
                # writer releases cat and triggers precisely one step.
                writer = os.open(fifo, os.O_WRONLY)
                os.close(writer)
                value = watch.wait(("VALUE " + expected + "\n").encode(), since=waiting.end())
                position = value.end()
                watch.assert_alive({pid})

            step("first 1 1 first")
            errors = len(watch.output["stderr"])
            calls = len(counter.calls())
            started = time.monotonic()
            publish(source, program("second"))
            watch.wait(b"Reload ready", "stderr", errors)
            assert len(counter.calls()) > calls, ("a changed body must compile/link a native update", counter.calls())
            accepted_publication(project, release)
            step("second 2 2 first")
            latency = time.monotonic() - started
            watch.wait(b"program state preserved", "stderr", errors)

            def unchanged_save(expected, atomic=True):
                before = accepted_publication(project, release)[3]
                calls = counter.calls()
                errors = len(watch.output["stderr"])
                publish(source, program("second"), atomic=atomic)
                watch.wait(b"Unchanged source; keeping published update", "stderr", errors)
                watch.wait(b"Reload ready", "stderr", errors)
                after = accepted_publication(project, release)[3]
                assert after == before, (
                    "identical source must preserve current bytes/inode, sidecar and generation directories",
                    before, after, watch.diagnostics()
                )
                assert counter.calls() == calls, ("identical source invoked native compile/link", counter.calls())
                step(expected)

            unchanged_save("second 3 3 first")
            unchanged_save("second 4 4 first", atomic=False)
            errors = len(watch.output["stderr"])
            publish(source, program("second").replace('STATE.count += 1', 'STATE.count += "invalid"'))
            watch.wait(re.compile(rb"(?i)build failed"), "stderr", errors)
            step("second 5 5 first")
            # A rejected candidate is never the authority for a later hit.
            unchanged_save("second 6 6 first")
            errors = len(watch.output["stderr"])
            calls = len(counter.calls())
            previous = accepted_publication(project, release)[0].read_bytes()
            publish(source, program("third"))
            watch.wait(b"Reload ready", "stderr", errors)
            current, _, _, _ = accepted_publication(project, release)
            assert current.read_bytes() != previous, "a changed edit must publish a fresh image"
            assert len(counter.calls()) > calls, ("a changed body reused a native update", counter.calls())
            step("third 7 7 first")

            def rebuild_untrusted(expected, damage):
                current, _, sidecar, before = accepted_publication(project, release)
                if damage == "image-digest":
                    # Retain the format/source digest but falsify the image digest.
                    fields = before[4].splitlines()
                    fields[2] = b"0" * 64
                    sidecar.write_bytes(b"\n".join(fields) + b"\n")
                elif damage == "table":
                    # Keep the accepted image path intact: it cannot alone authorize a hit.
                    current.write_bytes(before[0] + b"invalid trailing function table")
                elif damage == "binary-sidecar":
                    sidecar.write_bytes(b"\xffinvalid UTF-8 identity")
                elif damage == "binary-path":
                    current.write_bytes(b"\xff" + before[0])
                else:
                    sidecar.unlink()
                calls = len(counter.calls())
                errors = len(watch.output["stderr"])
                publish(source, program("third"))
                watch.wait(b"Reload ready", "stderr", errors)
                _, image, _, after = accepted_publication(project, release)
                assert after[0] != before[0], ("untrusted publication reused the prior image", damage, image)
                assert len(counter.calls()) > calls, ("untrusted publication skipped native compilation", damage, counter.calls())
                assert b"Unchanged source; keeping published update" not in watch.output["stderr"][errors:], (
                    "an absent or invalid identity/table must force a rebuild", damage, watch.diagnostics()
                )
                step(expected)

            rebuild_untrusted("third 8 8 first", "missing")
            rebuild_untrusted("third 9 9 first", "image-digest")
            rebuild_untrusted("third 10 10 first", "table")
            rebuild_untrusted("third 11 11 first", "binary-sidecar")
            rebuild_untrusted("third 12 12 first", "binary-path")
            errors = len(watch.output["stderr"])
            publish(source, program("third").replace('count: Integer;', 'count: Float;'))
            watch.wait(re.compile(rb"(?i)build failed"), "stderr", errors)
            watch.wait(b"function-body edits only", "stderr", errors)
            step("third 13 13 first")
            assert len(re.findall(rb"(?m)^PID ", watch.output["stdout"])) == 1, watch.diagnostics()
            watch.stop()
            print(f"hot reload {'O2' if release else 'O0'}: same PID, heap roots, thirteen state transitions, "
                  f"identical-save no-ops without native work, trusted-sidecar recovery; edit-to-observation {latency:.3f}s")
        finally:
            watch.close()


def check_exited_program(launcher, release):
    with tempfile.TemporaryDirectory(prefix="minyar-hot-exit-") as temporary:
        project = Path(temporary)
        (project / "src").mkdir()
        (project / "Minyar.toml").write_text(
            '[package]\nname = "hot-exit"\nversion = "0.1.0"\nkind = "bin"\n', encoding="utf-8"
        )
        source = project / "src/main.min"
        before = ('use "system" as system\nrecord State { count: Integer }\n'
                  'global STATE: State = State { count: 1 }\n'
                  'print("FINITE first " + Text(system.processId()))\n')
        publish(source, before)
        watch = begin(launcher, project, project / "unused-fifo", release)
        try:
            first = watch.wait(re.compile(rb"FINITE first ([0-9]+)\n"))
            watch.pids.add(int(first.group(1)))
            watch.wait(b"Program exited", "stderr")
            errors = len(watch.output["stderr"])
            publish(source, before.replace("Integer", "Float").replace("count: 1", "count: 1.0").replace("first", "second"))
            second = watch.wait(re.compile(rb"FINITE second ([0-9]+)\n"), since=first.end())
            watch.pids.add(int(second.group(1)))
            assert first.group(1) != second.group(1), watch.diagnostics()
            watch.wait(b"Program exited", "stderr", errors)
            watch.stop()
        finally:
            watch.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("launcher", type=Path)
    parser.add_argument("--profile", choices=("debug", "release"))
    args = parser.parse_args()
    launcher = args.launcher.resolve()
    with tempfile.TemporaryDirectory(prefix="minyar-lanterns-") as temporary:
        for mode in ("--debug", "--release"):
            output = Path(temporary) / "lanterns"
            subprocess.run([str(launcher), mode, str(launcher.parent / "examples/gallery/lanterns.min"),
                            "-o", str(output)], check=True, capture_output=True, timeout=180 * SCALE)
            result = subprocess.run([str(output)], check=True, capture_output=True, text=True, timeout=10 * SCALE)
            assert result.stdout == ("Ada keeps a light for evening 1\nLin keeps a light for evening 1\n"
                                     "Ada keeps a light for evening 2\nLin keeps a light for evening 2\n"), result
            subprocess.run([str(launcher), mode, str(launcher.parent / "tests/live-programming/globals.min"),
                            "-o", str(output)], check=True, capture_output=True, timeout=180 * SCALE)
            result = subprocess.run([str(output)], check=True, capture_output=True, text=True, timeout=10 * SCALE)
            assert result.stdout == "2\n41\n42\n7\n9\n3\n", result
    if args.profile != "release":
        check(launcher, False)
        check_exited_program(launcher, False)
    if args.profile != "debug":
        check(launcher, True)
        check_exited_program(launcher, True)


if __name__ == "__main__":
    main()
