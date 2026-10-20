#!/usr/bin/env python3
"""Owned scalar-record helper: exact storage, alias and cleanup controls."""
import argparse
import json
import os
from pathlib import Path
import subprocess

if not __debug__:
    raise SystemExit("scalar record reuse checks require Python assertions")

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--mode", choices=["native", "sanitize"], default="native")
parser.add_argument("--engine", choices=["ordinary", "cycle"], action="append")
parser.add_argument("--profile", choices=["eager", "arena", "system-k1", "system-k32", "fixed-k1", "fixed-k32"], action="append")
parser.add_argument("--optimization", choices=["0", "2"], action="append")
options = parser.parse_args()
cc = os.environ.get("MINYAR_TEST_CLANG", "clang")
root = Path("build/scalar-record-reuse-" + options.mode)
root.mkdir(parents=True, exist_ok=True)
engine = Path("runtime/minyar_runtime.c").read_text()
fixture = Path("tests/scalar-record-reuse.c").read_text()
expected = "Scalar record reuse: identity, copying, owners and cleanup passed\n"
records = []
report_path = root / "results.json"

def run(command, stdout_path, stderr_path):
    environment = dict(os.environ, ASAN_OPTIONS="detect_leaks=0:detect_stack_use_after_return=1:halt_on_error=1",
                       UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
    observed = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=120)
    stdout_path.write_text(observed.stdout)
    stderr_path.write_text(observed.stderr)
    record = {"command": command, "exit": observed.returncode,
              "stdout": observed.stdout, "stderr": observed.stderr}
    records.append(record)
    report_path.write_text(json.dumps({"mode": options.mode, "observations": records}, indent=2) + "\n")
    return record

for name in options.engine or ["ordinary", "cycle"]:
    selected = engine
    if name == "cycle":
        for ordinary, traced in [("minyar_rc.h", "minyar_cycle_rc.h"),
                                 ("minyar_collections.h", "minyar_cycle_collections.h")]:
            before, after = '#include "' + ordinary + '"', '#include "' + traced + '"'
            assert selected.count(before) == 1
            selected = selected.replace(before, after, 1)
        selected = "#define MINYAR_SORT_GRAPH 1\n#define MINYAR_MAP_CYCLE_RUNTIME 1\n#define MINYAR_NOINLINE __attribute__((noinline))\n" + selected
    source = root / (name + ".c")
    marker = '#include "../runtime/minyar_runtime.c"'
    assert fixture.count(marker) == 1
    source.write_text(fixture.replace(marker, selected, 1))
    for profile in options.profile or ["eager", "arena", "system-k1", "system-k32", "fixed-k1", "fixed-k32"]:
        for optimization in options.optimization or ["0", "2"]:
            label = name + "-" + profile + "-O" + optimization
            executable = root / label
            flags = []
            if profile == "arena":
                flags += ["-DMINYAR_COMPILER_ARENA=1"]
            elif profile != "eager":
                backend, budget = profile.split("-k")
                flags += ["-DMINYAR_" + ("SYSTEM" if backend == "system" else "BOUNDED") + "_HEAP=1",
                          "-DMINYAR_RC_POLL_BUDGET=" + budget]
            if options.mode == "sanitize":
                flags += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
            compiled = run([cc, "-std=c11", "-O" + optimization, "-UNDEBUG",
                            "-Wno-override-module", *flags, "-iquote", "runtime",
                            str(source), "-lm", "-o", str(executable)],
                           root / (label + ".build.stdout"), root / (label + ".build.stderr"))
            assert compiled["exit"] == 0, compiled
            observed = run([str(executable.resolve())], root / (label + ".stdout"), root / (label + ".stderr"))
            assert observed["exit"] == 0 and observed["stdout"] == expected and observed["stderr"] == "", observed
            for argument in ["negative", "overflow"] + ([] if profile == "arena" else ["bytes"]):
                failed = run([str(executable.resolve()), argument], root / (label + "." + argument + ".stdout"),
                             root / (label + "." + argument + ".stderr"))
                diagnostic = "the computer ran out of memory." if argument == "bytes" else "this record has too many fields."
                assert failed["exit"] == 1 and failed["stdout"] == "", failed
                assert failed["stderr"].splitlines()[0] == "Minyar stopped: " + diagnostic, failed
                assert "Sanitizer" not in failed["stderr"], failed
            print(label + ": passed", flush=True)
print("Scalar record reuse " + options.mode + ": all selected profiles passed", flush=True)

