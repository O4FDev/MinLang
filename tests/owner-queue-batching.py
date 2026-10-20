#!/usr/bin/env python3
"""Differential owner-queue scheduling checks. Run builds/executions on BX.

The reference is the same runtime with only the explicitly delimited batching
block removed, exposing its original generic scheduler. No runtime flag or
alternate helper is shared by the optimized and reference dispatch paths.
Every command, input hash, transcript, and failure remains in the output tree.
"""

import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
START = "/* Sole owner queue:"
END = "/* End sole owner queue batching. */"
HEADERS = ("minyar_bounded_rc.h", "minyar_cycle_bounded_rc.h")
CYCLE_PREFIX = """#define MINYAR_SORT_GRAPH 1
#define MINYAR_MAP_CYCLE_RUNTIME 1
#if defined(__GNUC__) || defined(__clang__)
#define MINYAR_NOINLINE __attribute__((noinline))
#else
#define MINYAR_NOINLINE
#endif
"""


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def batching_parts(source):
    if source.count(START) != 1 or source.count(END) != 1:
        raise ValueError("scheduler must contain exactly one pair of batching markers")
    first = source.index(START)
    last = source.index(END, first) + len(END)
    return source[:first], source[first:last], source[last:]


def mutate(source, variant):
    before, block, after = batching_parts(source)
    if variant == "reference":
        block = "/* Reference: use the original generic scheduler below. */"
    elif variant == "mutant-stop":
        stop = "rc_pending_count <= pending"
        if block.count(stop) != 2:
            # Also accept retained v1 sources supplied with --runtime-source.
            stop = "!rc_bounded_active && !rc_bounded_head && !rc_bounded_recent_head"
        if block.count(stop) != 2:
            raise ValueError("expected two independent owner-run competitor-stop checks")
        replacement = "((void)pending, 1)" if stop == "rc_pending_count <= pending" else "1"
        block = block.replace(stop, replacement + " /* mutant ignores arriving object tasks */")
    elif variant == "mutant-charge":
        if block.count("work++;") != 2:
            raise ValueError("expected exactly one unit charge per owner-run branch")
        block = block.replace("work++;", "work += 2; /* mutant double charge */")
    elif variant != "candidate":
        raise ValueError("unknown variant: " + variant)
    return before + block + after


def cycle_source(source):
    # Keep this transformation identical to tools/test-runtime.min:cycleSource.
    for ordinary, traced in (("minyar_rc.h", "minyar_cycle_rc.h"),
                             ("minyar_collections.h", "minyar_cycle_collections.h")):
        directive = '#include "' + ordinary + '"'
        if source.count(directive) != 1:
            raise ValueError("cycle source requires one " + directive)
        source = source.replace(directive, '#include "' + traced + '"')
    return CYCLE_PREFIX + source + '\n#include "minyar_callbacks.h"\n'


def choices(value, allowed):
    result = value.split(",")
    if not result or any(item not in allowed for item in result) or len(set(result)) != len(result):
        raise argparse.ArgumentTypeError("choose unique comma-separated values from " + ",".join(allowed))
    return result


def first_difference(left, right):
    sentinel = object()
    with left.open("rb") as a, right.open("rb") as b:
        for number, (expected, actual) in enumerate(itertools.zip_longest(a, b, fillvalue=sentinel), 1):
            if expected != actual:
                def display(line):
                    return "<end>" if line is sentinel else line.decode("utf-8", "replace").rstrip()[:1800]
                return "line %d\nreference: %s\ncandidate: %s" % (number, display(expected), display(actual))
    return None


class Runner:
    def __init__(self, args, output):
        self.args, self.output = args, output
        self.rows = []
        self.commands = []
        self.copies = {}
        self.environment = os.environ.copy()
        self.environment["ASAN_OPTIONS"] = "detect_leaks=0:abort_on_error=1:allocator_may_return_null=1"
        self.environment["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
        runtime = args.runtime_source.resolve()
        self.runtime_directory = args.runtime_directory.resolve() if args.runtime_directory else runtime.parent
        self.source = runtime.read_text()
        self.cycle = args.cycle_runtime_source.read_text() if args.cycle_runtime_source else None
        self.manifest = {
            "scope": "exact per-poll scheduler behavior; no latency or performance certification",
            "runtime_source": str(runtime), "source_sha256": digest(runtime),
            "fixture_sha256": digest(ROOT / "tests/owner-queue-batching.c"),
            "runtime_sha256": {
                str(path.relative_to(self.runtime_directory)): digest(path)
                for path in sorted(self.runtime_directory.rglob("*"))
                if path.is_file() and path.suffix in (".h", ".c")
            },
            "environment": {key: self.environment[key] for key in ("ASAN_OPTIONS", "UBSAN_OPTIONS")},
            "configurations": self.rows, "commands": self.commands,
        }
        self.save()

    def save(self):
        (self.output / "results.json").write_text(json.dumps(self.manifest, indent=2) + "\n")

    def runtime(self, variant, kind):
        key = (variant, kind)
        if key in self.copies:
            return self.copies[key]
        directory = self.output / (variant + "-" + kind) / "runtime"
        shutil.copytree(self.runtime_directory, directory)
        for name in HEADERS:
            path = directory / name
            if name == ("minyar_cycle_bounded_rc.h" if kind == "cycle" else "minyar_bounded_rc.h"):
                path.write_text(mutate(path.read_text(), variant))
        source = self.source if kind == "ordinary" else (self.cycle or cycle_source(self.source))
        engine = directory / "owner-queue-engine.c"
        engine.write_text(source)
        self.copies[key] = engine
        return engine

    def command(self, arguments, stem, timeout, require_success=True):
        stdout, stderr = stem.with_suffix(".stdout"), stem.with_suffix(".stderr")
        record = {"argv": [str(part) for part in arguments], "stdout": str(stdout), "stderr": str(stderr)}
        self.commands.append(record)
        self.save()
        with stdout.open("wb") as out, stderr.open("wb") as err:
            try:
                result = subprocess.run(arguments, cwd=ROOT, env=self.environment, stdout=out,
                                        stderr=err, timeout=timeout, check=False)
            except subprocess.TimeoutExpired as error:
                record["timeout"] = timeout
                self.save()
                raise RuntimeError("timeout is a failure: " + str(stem)) from error
        record["exit"] = result.returncode
        self.save()
        if require_success and result.returncode:
            raise RuntimeError("command failed (%d), see %s" % (result.returncode, stderr))
        return result.returncode, stdout

    def build_run(self, variant, kind, profile, budget, optimization, mode, mutant=False):
        label = "-".join((variant, kind, profile, str(budget), optimization, mode))
        directory = self.output / "cases" / label
        directory.mkdir(parents=True)
        executable = directory / "fixture"
        engine = self.runtime(variant, kind)
        command = [self.args.clang, "-std=c11", "-Wall", "-Wextra", "-Werror", "-" + optimization,
                   "-DMINYAR_RC_POLL_BUDGET=" + str(budget),
                   "-DMINYAR_BOUNDED_HEAP_BYTES=4194304",
                   '-DMINYAR_RUNTIME_SOURCE="' + str(engine) + '"']
        command += ["-DMINYAR_SYSTEM_HEAP=1"] if profile == "system" else ["-DMINYAR_BOUNDED_HEAP=1"]
        if profile == "lazy":
            command.append("-DMINYAR_LAZY_HEAP=1")
        if mode == "sanitize":
            command += ["-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
        command += [str(ROOT / "tests/owner-queue-batching.c"), "-o", str(executable), "-lm"]
        self.command(command, directory / "compile", self.args.compile_timeout)
        status, transcript = self.command([str(executable)], directory / "run", self.args.run_timeout,
                                          require_success=not mutant)
        return status, transcript

    def check_pair(self, kind, profile, budget, optimization, mode):
        reference = self.build_run("reference", kind, profile, budget, optimization, mode)[1]
        candidate = self.build_run("candidate", kind, profile, budget, optimization, mode)[1]
        difference = first_difference(reference, candidate)
        row = {"runtime": kind, "profile": profile, "budget": budget,
               "optimization": optimization, "mode": mode, "reference_sha256": digest(reference),
               "candidate_sha256": digest(candidate), "equal": difference is None}
        self.rows.append(row)
        self.save()
        if difference:
            raise RuntimeError("scheduler transcript changed: " + str(candidate) + "\n" + difference)
        print("%s %s K%d %s %s: exact transcript and full recovery" %
              (kind, profile, budget, optimization, mode), flush=True)

    def check_mutants(self, kind):
        reference_path = self.output / "cases" / ("reference-" + kind + "-system-7-O2-native") / "run.stdout"
        if not reference_path.exists():
            reference_path = self.build_run("reference", kind, "system", 7, "O2", "native")[1]
        for variant in ("mutant-stop", "mutant-charge"):
            status, transcript = self.build_run(variant, kind, "system", 7, "O2", "native", mutant=True)
            difference = first_difference(reference_path, transcript)
            detected = status != 0 or difference is not None
            self.rows.append({"runtime": kind, "mutant": variant, "detected": detected,
                              "exit": status, "difference": difference})
            self.save()
            if not detected:
                raise RuntimeError("scheduler regression oracle accepted " + variant + " in " + kind)
            print(kind + " " + variant + ": rejected", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default=os.environ.get("MINYAR_TEST_CLANG", "clang"))
    parser.add_argument("--runtime-source", type=Path, default=ROOT / "runtime/minyar_runtime.c")
    parser.add_argument("--runtime-directory", type=Path,
                        help="headers used by the supplied source; defaults to its parent")
    parser.add_argument("--cycle-runtime-source", type=Path,
                        help="existing generated cycle engine; otherwise use tools/test-runtime.min's transformation")
    parser.add_argument("--output-dir", type=Path, help="new artifact directory; all evidence is retained")
    parser.add_argument("--profiles", type=lambda value: choices(value, ("system", "fixed", "lazy")),
                        default=["system", "fixed", "lazy"])
    parser.add_argument("--budgets", type=lambda value: choices(value, ("1", "2", "7", "32", "1024")),
                        default=["1", "2", "7", "32", "1024"])
    parser.add_argument("--optimizations", type=lambda value: choices(value, ("O0", "O2")), default=["O0", "O2"])
    parser.add_argument("--modes", type=lambda value: choices(value, ("native", "sanitize")), default=["native", "sanitize"])
    parser.add_argument("--runtimes", type=lambda value: choices(value, ("cycle",)), default=["cycle"])
    parser.add_argument("--compile-timeout", type=int, default=120)
    parser.add_argument("--run-timeout", type=int, default=60)
    args = parser.parse_args()
    if args.output_dir:
        output = args.output_dir.resolve()
        output.mkdir(parents=True, exist_ok=False)
    else:
        (ROOT / "build").mkdir(exist_ok=True)
        output = Path(tempfile.mkdtemp(prefix="owner-queue-batching-", dir=ROOT / "build"))
    print("owner queue evidence: " + str(output), flush=True)
    try:
        runner = Runner(args, output)
        for kind, profile, budget, optimization, mode in itertools.product(
                args.runtimes, args.profiles, args.budgets, args.optimizations, args.modes):
            runner.check_pair(kind, profile, int(budget), optimization, mode)
        for kind in args.runtimes:
            runner.check_mutants(kind)
    except (OSError, RuntimeError, ValueError) as error:
        print(str(error) + "\nevidence retained: " + str(output), file=sys.stderr)
        return 1
    print("owner queue differential matrix and stop/work-charge mutants passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
