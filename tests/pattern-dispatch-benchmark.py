#!/usr/bin/env python3
"""Retain compiler/IR identities and real randomized 20-case dispatch samples.

Run through the lane's remote bx command, after building minyarc/runtime.
The before directory is immutable; after links the identical frozen runtime.
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys


def run(command, **kwargs):
    result = subprocess.run(command, text=True, capture_output=True,
                            timeout=180, **kwargs)
    if result.returncode:
        sys.stderr.write(result.stdout + result.stderr)
        result.check_returncode()
    return result.stdout


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


phase = sys.argv[1]
if phase not in ("before", "after"):
    raise SystemExit("phase must be before or after")
if hasattr(os, "sched_getaffinity"):
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
root = Path("build/pattern-dispatch-benchmark")
destination = root / phase
destination.mkdir(parents=True, exist_ok=False)
fixture = Path("tests/pattern-dispatch-benchmark.min")
clang = os.environ.get("LLVM_CC") or run(["sh", "tools/toolchain.sh", "default-clang"]).strip()
runtime = root / "runtime.o"
system = root / "system.o"
if phase == "before":
    shutil.copy2("build/minyar-runtime.o", runtime)
    shutil.copy2("build/minyarc", root / "minyarc-before")
    run([clang, "-O2", "-c", "runtime/native/system.c", "-o", str(system)])
shutil.copy2(fixture, destination / "fixture.min")
ir = destination / "dispatch.ll"
compile_command = ["./build/minyarc", str(fixture), str(ir), "--library", "library"]
run(compile_command)
rounds = int(os.environ.get("PATTERN_DISPATCH_ROUNDS", "4096"))
seed = 1729
primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71]
checksum = 0
for _ in range(4096):
    seed = seed * 48271 % 2147483647
    tag = seed % 20
    checksum += seed % 97 * primes[tag] + tag * tag + 17
checksum *= rounds
report = {"phase": phase, "host": platform.platform(), "clang": run([clang, "--version"]),
          "cpu_affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
          "rounds": rounds, "matches": rounds * 4096, "seed": 1729,
          "expected_checksum": checksum, "compile_command": compile_command,
          "source_hashes": {}, "samples": {}}
for folder in ("compiler", "runtime", "bootstrap", "library", "build-support"):
    for path in sorted(Path(folder).rglob("*")):
        if path.is_file():
            report["source_hashes"][str(path)] = digest(path)
for path in (fixture, Path(__file__), Path("build/minyarc"),
             Path("build/compiler.min"), runtime, system, ir):
    report["source_hashes"][str(path)] = digest(path)
if phase == "after":
    before = json.loads((root / "before/report.json").read_text())
    assert digest(fixture) == before["source_hashes"][str(fixture)]
    assert digest(runtime) == before["source_hashes"][str(runtime)]
    assert digest(system) == before["source_hashes"][str(system)]
for level in ("O0", "O2"):
    executable = destination / level
    link = [clang, "-" + level, "-Wno-override-module", str(ir), str(runtime), str(system), "-lm", "-o", str(executable)]
    run(link)
    run([clang, "-" + level, "-S", "-Wno-override-module", str(ir), "-o", str(destination / (level + ".s"))])
    if level == "O2":
        run([clang, "-O2", "-S", "-emit-llvm", "-Wno-override-module", str(ir), "-o", str(destination / "optimized.ll")])
    samples = []
    for repeat in range(10):
        output = run([str(executable), str(rounds), "1729"])
        (destination / (level + "-" + str(repeat) + ".stdout")).write_text(output)
        elapsed, actual = map(int, output.split())
        assert actual == checksum, (actual, checksum)
        samples.append(elapsed)
    report["samples"][level] = {"warmup_ns": samples[0], "raw_ns": samples[1:],
                                  "median_ns": statistics.median(samples[1:]),
                                  "link_command": link, "binary_sha256": digest(executable)}
    if phase == "after":
        pairs = []
        for repeat in range(9):
            pair = {}
            order = ("before", "after") if repeat % 2 == 0 else ("after", "before")
            for version in order:
                output = run([str(root / version / level), str(rounds), "1729"])
                elapsed, actual = map(int, output.split())
                assert actual == checksum
                pair[version] = elapsed
            pairs.append(pair)
        report["samples"][level]["alternating_pairs_ns"] = pairs
(destination / "report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({"phase": phase, "matches": report["matches"], "checksum": checksum,
                  "samples": report["samples"]}, indent=2))
