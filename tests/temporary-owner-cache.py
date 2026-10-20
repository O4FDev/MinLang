#!/usr/bin/env python3
"""Compile/run cache ownership models on BX and retain every failure.

Default-cap cells cover ordinary/cycle, system/fixed/lazy, K1/2/7/32/1024, O0/O2,
native/ASan+UBSan. Additional cap boundaries run at K1/O2/native. Numeric-domain
and deliberately broken cache/service implementations provide separate checks.
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
CAPS = ("default", "zero", "below", "exact", "shared-below", "shared-exact")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected(value, allowed):
    values = value.split(",")
    if not values or len(set(values)) != len(values) or any(item not in allowed for item in values):
        raise argparse.ArgumentTypeError("choose unique comma-separated values from " + ",".join(allowed))
    return values


def cycle_source(source):
    # tools/test-runtime.min:cycleSource is the authoritative transformation.
    for ordinary, traced in (("minyar_rc.h", "minyar_cycle_rc.h"),
                             ("minyar_collections.h", "minyar_cycle_collections.h")):
        before = '#include "' + ordinary + '"'
        if source.count(before) != 1:
            raise ValueError("expected one " + before)
        source = source.replace(before, '#include "' + traced + '"')
    return ("#define MINYAR_SORT_GRAPH 1\n#define MINYAR_MAP_CYCLE_RUNTIME 1\n"
            "#if defined(__GNUC__) || defined(__clang__)\n"
            "#define MINYAR_NOINLINE __attribute__((noinline))\n#else\n#define MINYAR_NOINLINE\n#endif\n"
            + source + '\n#include "minyar_callbacks.h"\n')


class Runner:
    def __init__(self, args, output):
        self.args, self.output = args, output
        self.commands, self.rows, self.engines = [], [], {}
        self.source = args.runtime_source.resolve()
        self.headers = args.runtime_directory.resolve() if args.runtime_directory else self.source.parent
        self.environment = os.environ.copy()
        self.environment["ASAN_OPTIONS"] = "detect_leaks=0:abort_on_error=1"
        self.environment["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
        self.record = {
            "scope": "deterministic cache storage, work units and ownership; no performance claim",
            "source": str(self.source), "source_sha256": digest(self.source),
            "fixture_sha256": digest(ROOT / "tests/temporary-owner-cache.c"),
            "runtime_sha256": {str(path.relative_to(self.headers)): digest(path)
                               for path in sorted(self.headers.rglob("*"))
                               if path.is_file() and path.suffix in (".h", ".c")},
            "commands": self.commands, "configurations": self.rows,
        }
        self.save()

    def save(self):
        (self.output / "results.json").write_text(json.dumps(self.record, indent=2) + "\n")

    def engine(self, kind, variant):
        key = (kind, variant)
        if key in self.engines:
            return self.engines[key]
        directory = self.output / (kind + "-" + variant) / "runtime"
        shutil.copytree(self.headers, directory)
        for name in ("minyar_bounded_rc.h", "minyar_cycle_bounded_rc.h"):
            path = directory / name
            source = path.read_text()
            before = "size_t minyar_rc_poll(size_t budget) {"
            if source.count(before) != 1:
                raise ValueError("expected one poll implementation in " + name)
            path.write_text(source.replace(before, "size_t cache_probe_poll_impl(size_t budget) {"))
        if variant == "mutant-no-reuse":
            path = directory / "minyar_owner_cache.h"
            source = path.read_text()
            before = "if (!chunk) return rc_heap_allocate(sizeof(*chunk));"
            if source.count(before) != 1:
                raise ValueError("cache allocation mutant lost its insertion point")
            path.write_text(source.replace(before, "if (1) return rc_heap_allocate(sizeof(*chunk));"))
        elif variant == "mutant-pre-service":
            for name in ("minyar_rc.h", "minyar_cycle_rc.h"):
                path = directory / name
                source = path.read_text()
                before = ("rc_service_pending(MINYAR_RC_POLL_BUDGET);\n"
                          "        chunk = rc_bounded_chunk_allocate();")
                if source.count(before) != 1:
                    raise ValueError("keep pre-service mutant lost its insertion point")
                path.write_text(source.replace(before, "chunk = rc_bounded_chunk_allocate();"))
        elif variant != "candidate":
            raise ValueError("unknown runtime variant")
        source = self.source.read_text()
        if kind == "cycle":
            source = self.args.cycle_runtime_source.read_text() if self.args.cycle_runtime_source else cycle_source(source)
        engine = directory / "temporary-cache-engine.c"
        engine.write_text(source)
        self.engines[key] = engine
        return engine

    def command(self, argv, path, timeout, success=True):
        stdout, stderr = path.with_suffix(".stdout"), path.with_suffix(".stderr")
        command = {"argv": [str(part) for part in argv], "stdout": str(stdout), "stderr": str(stderr)}
        self.commands.append(command)
        self.save()
        with stdout.open("wb") as out, stderr.open("wb") as err:
            try:
                result = subprocess.run(argv, cwd=ROOT, env=self.environment, stdout=out,
                                        stderr=err, timeout=timeout, check=False)
            except subprocess.TimeoutExpired as error:
                command["timeout"] = timeout
                self.save()
                raise RuntimeError("timeout is a failure: " + str(path)) from error
        command["exit"] = result.returncode
        self.save()
        if success and result.returncode:
            raise RuntimeError("command failed (%d), see %s" % (result.returncode, stderr))
        return result.returncode, stdout, stderr

    def run(self, kind, profile, budget, optimization, mode, cap, variant="candidate", threaded=False):
        label = "-".join((kind, profile, str(budget), optimization, mode, cap, variant,
                          "threaded" if threaded else "local"))
        directory = self.output / "cases" / label
        directory.mkdir(parents=True)
        engine = self.engine(kind, variant)
        chunk = 80 if profile == "system" else 128
        capacity = {"default": 262144, "zero": 0, "below": chunk - 1, "exact": chunk,
                    "shared-below": chunk + 63, "shared-exact": chunk + 64}[cap]
        executable = directory / "fixture"
        argv = [self.args.clang, "-std=c11", "-Wall", "-Wextra", "-Werror", "-" + optimization,
                "-DMINYAR_RC_POLL_BUDGET=" + str(budget), "-DMINYAR_FRAME_CACHE_BYTES=" + str(capacity),
                "-DMINYAR_BOUNDED_HEAP_BYTES=4194304", '-DMINYAR_RUNTIME_SOURCE="' + str(engine) + '"']
        argv += ["-DMINYAR_SYSTEM_HEAP=1"] if profile == "system" else ["-DMINYAR_BOUNDED_HEAP=1"]
        if profile == "lazy":
            argv.append("-DMINYAR_LAZY_HEAP=1")
        if threaded:
            argv += ["-DMINYAR_THREADED=1", "-pthread"]
        if mode == "sanitize":
            argv += ["-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
        argv += [str(ROOT / "tests/temporary-owner-cache.c"), "-o", str(executable), "-lm"]
        self.command(argv, directory / "compile", self.args.compile_timeout)
        mutant = variant != "candidate"
        status, stdout, _ = self.command([str(executable)], directory / "run", self.args.run_timeout,
                                         success=not mutant)
        row = {"runtime": kind, "profile": profile, "budget": budget, "optimization": optimization,
               "mode": mode, "cap": capacity, "variant": variant, "threaded": threaded,
               "exit": status, "stdout_sha256": digest(stdout)}
        self.rows.append(row)
        self.save()
        if mutant and not status:
            raise RuntimeError("cache oracle accepted " + variant + " in " + kind)
        if threaded and not mutant:
            status, _, stderr = self.command([str(executable), "residual"], directory / "residual",
                                             self.args.run_timeout, success=False)
            if status in (0, 99) or "a thread domain was already initialized" not in stderr.read_text(errors="replace"):
                raise RuntimeError("thread initialization accepted cache-only residual state: " + str(stderr))
        print(label + (": rejected" if mutant else ": passed exact work/reuse/recovery"), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default=os.environ.get("MINYAR_TEST_CLANG", "clang"))
    parser.add_argument("--runtime-source", type=Path, default=ROOT / "runtime/minyar_runtime.c")
    parser.add_argument("--runtime-directory", type=Path)
    parser.add_argument("--cycle-runtime-source", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--profiles", type=lambda value: selected(value, ("system", "fixed", "lazy")),
                        default=["system", "fixed", "lazy"])
    parser.add_argument("--budgets", type=lambda value: selected(value, ("1", "2", "7", "32", "1024")),
                        default=["1", "2", "7", "32", "1024"])
    parser.add_argument("--optimizations", type=lambda value: selected(value, ("O0", "O2")), default=["O0", "O2"])
    parser.add_argument("--modes", type=lambda value: selected(value, ("native", "sanitize")), default=["native", "sanitize"])
    parser.add_argument("--runtimes", type=lambda value: selected(value, ("ordinary", "cycle")), default=["ordinary", "cycle"])
    parser.add_argument("--caps", type=lambda value: selected(value, CAPS), default=list(CAPS))
    parser.add_argument("--compile-timeout", type=int, default=120)
    parser.add_argument("--run-timeout", type=int, default=60)
    args = parser.parse_args()
    if args.output_dir:
        output = args.output_dir.resolve()
        output.mkdir(parents=True, exist_ok=False)
    else:
        (ROOT / "build").mkdir(exist_ok=True)
        output = Path(tempfile.mkdtemp(prefix="temporary-owner-cache-", dir=ROOT / "build"))
    print("temporary cache evidence: " + str(output), flush=True)
    try:
        runner = Runner(args, output)
        for kind, profile, budget, optimization, mode, cap in itertools.product(
                args.runtimes, args.profiles, args.budgets, args.optimizations, args.modes, args.caps):
            if cap != "default" and (budget, optimization, mode) != ("1", "O2", "native"):
                continue
            runner.run(kind, profile, int(budget), optimization, mode, cap)
        for kind in args.runtimes:
            for variant in ("mutant-no-reuse", "mutant-pre-service"):
                runner.run(kind, "system", 1, "O2", "native", "default", variant=variant)
            if "system" in args.profiles:
                for mode in args.modes:
                    runner.run(kind, "system", 1, "O2", mode, "default", threaded=True)
    except (OSError, RuntimeError, ValueError) as error:
        print(str(error) + "\nevidence retained: " + str(output), file=sys.stderr)
        return 1
    print("temporary owner cache models, cap boundaries, numeric domains and mutants passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
