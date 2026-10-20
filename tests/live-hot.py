#!/usr/bin/env python3
"""Function updates preserve the actual process, global roots and heap aliases."""
import argparse
import os
from pathlib import Path
import re
import selectors
import subprocess
import tempfile
import time

from importlib.util import module_from_spec, spec_from_file_location
_spec = spec_from_file_location("watch_checks", Path(__file__).with_name("live-programming.py"))
_watch = module_from_spec(_spec)
_spec.loader.exec_module(_watch)
Watch, publish, SCALE = _watch.Watch, _watch.publish, _watch.SCALE


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


def begin(launcher, project, fifo, release):
    watch = Watch.__new__(Watch)
    command = [str(launcher), "run", "--watch", "--hot", "--manifest-path", str(project)]
    if release:
        command += ["--release"]
    watch.process = subprocess.Popen(
        command, cwd=project, env=dict(os.environ, MINYAR_HOT_FIFO=str(fifo)),
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
        project = Path(temporary)
        (project / "src").mkdir()
        (project / "Minyar.toml").write_text(
            '[package]\nname = "hot-probe"\nversion = "0.1.0"\nkind = "bin"\n', encoding="utf-8"
        )
        source = project / "src/main.min"
        publish(source, program("first"))
        fifo = project / "tick"
        os.mkfifo(fifo)
        watch = begin(launcher, project, fifo, release)
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
            started = time.monotonic()
            publish(source, program("second"))
            watch.wait(b"Reload ready", "stderr", errors)
            step("second 2 2 first")
            latency = time.monotonic() - started
            watch.wait(b"program state preserved", "stderr", errors)
            errors = len(watch.output["stderr"])
            publish(source, program("second").replace('STATE.count += 1', 'STATE.count += "invalid"'))
            watch.wait(re.compile(rb"(?i)build failed"), "stderr", errors)
            step("second 3 3 first")
            errors = len(watch.output["stderr"])
            publish(source, program("third"))
            watch.wait(b"Reload ready", "stderr", errors)
            step("third 4 4 first")
            errors = len(watch.output["stderr"])
            publish(source, program("third").replace('count: Integer;', 'count: Float;'))
            watch.wait(re.compile(rb"(?i)build failed"), "stderr", errors)
            watch.wait(b"function-body edits only", "stderr", errors)
            step("third 5 5 first")
            assert len(re.findall(rb"(?m)^PID ", watch.output["stdout"])) == 1, watch.diagnostics()
            watch.stop()
            print(f"hot reload {'O2' if release else 'O0'}: same PID, heap roots, five state transitions, rejection recovery; edit-to-observation {latency:.3f}s")
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
