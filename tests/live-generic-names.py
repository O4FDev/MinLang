#!/usr/bin/env python3
"""A hot patch that reorders the first uses of two generic instances keeps stored function values on their type.

Instance names used to be numbered in first-use order, so swapping the two `describe` calls in `warm` swapped
`minyar_generic_function_0_describe` and `..._1_describe`. The closure stored in STATE lives in the original
executable and calls its instance by name through the live wrapper, so it then ran Pear's body on an Apple.
"""
import argparse
import os
from pathlib import Path
import re
import tempfile

from importlib.util import module_from_spec, spec_from_file_location
_spec = spec_from_file_location("live_hot", Path(__file__).with_name("live-hot.py"))
_hot = module_from_spec(_spec)
_spec.loader.exec_module(_hot)
publish, begin = _hot.publish, _hot.begin

APPLE = "    let first = describe(Apple { seeds: 5 })\n"
PEAR = "    let second = describe(Pear { label: \"conference\" })\n"


def program(revision, pear_first):
    uses = PEAR + APPLE if pear_first else APPLE + PEAR
    return '''use "system" as system
capability Named { function name(): Text }
record Apple { seeds: Integer }
function Apple.name(): Text { return "apple" }
conform Apple to Named
record Pear { label: Text }
function Pear.name(): Text { return "pear" }
conform Pear to Named
function describe<Item: Named>(item: Item): Text { return "a " + item.name() }
function warm(): Text {
''' + uses + '''    return first + "/" + second + " REVISION"
}
record State { count: Integer; keep: (Apple) -> Text }
global STATE: State = State { count: 0; keep: function(apple: Apple): Text { return describe(apple) } }
function step() {
    STATE.count += 1
    print("VALUE " + warm() + " kept " + STATE.keep(Apple { seeds: 1 }) + " " + Text(STATE.count))
}
print("PID " + Text(system.processId()))
while true {
    let child = system.spawn("/bin/cat", ["cat", system.getenv("MINYAR_HOT_FIFO")], system.environment(), "")
    if child < 0 { fail("cannot launch FIFO reader") }
    print("WAIT " + Text(system.childProcessId(child)))
    system.wait(child)
    step()
}
'''.replace("REVISION", revision)


def check(launcher, release):
    with tempfile.TemporaryDirectory(prefix="minyar-hot-generic-") as temporary:
        project = Path(temporary)
        (project / "src").mkdir()
        (project / "Minyar.toml").write_text(
            '[package]\nname = "hot-generic"\nversion = "0.1.0"\nkind = "bin"\n', encoding="utf-8"
        )
        source = project / "src/main.min"
        publish(source, program("first", False))
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
                os.close(os.open(fifo, os.O_WRONLY))
                value = watch.wait(re.compile(rb"VALUE ([^\n]*)\n"), since=waiting.end())
                position = value.end()
                assert value.group(1).decode() == expected, (value.group(1), expected, watch.diagnostics())
                watch.assert_alive({pid})

            step("a apple/a pear first kept a apple 1")
            errors = len(watch.output["stderr"])
            publish(source, program("second", True))
            watch.wait(b"Reload ready", "stderr", errors)
            step("a apple/a pear second kept a apple 2")
            errors = len(watch.output["stderr"])
            publish(source, program("third", False))
            watch.wait(b"Reload ready", "stderr", errors)
            step("a apple/a pear third kept a apple 3")
            assert len(re.findall(rb"(?m)^PID ", watch.output["stdout"])) == 1, watch.diagnostics()
            watch.stop()
            print(f"hot generic names {'O2' if release else 'O0'}: reordered first uses keep the stored "
                  f"closure on its own instance across two patches in one process")
        finally:
            watch.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("launcher", type=Path)
    args = parser.parse_args()
    launcher = args.launcher.resolve()
    check(launcher, False)
    check(launcher, True)


if __name__ == "__main__":
    main()
