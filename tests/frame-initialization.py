#!/usr/bin/env python3
"""Differential frame initialization proof; run exclusively on parent bx.

The default candidate is ROOT/runtime. Without --control-runtime, reconstruct
the control by four exact, fail-closed source inversions. Logical transcripts
must match; only the candidate must satisfy the stronger physical NULL oracle.
"""

import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
REPO = next(p for p in Path(__file__).resolve().parents if (p / "runtime/minyar_runtime.c").is_file())
ENTRY_NEW = """        frame->local_capacity = count;
#ifdef MINYAR_BOUNDED_RC
        /* Retired cached slots are NULL. Growth can discard storage or move
         * old index words into this value region, so clear its whole extent. */
        memset(frame->locals, 0, count * sizeof(*frame->locals));
#endif
    }
#ifndef MINYAR_BOUNDED_RC
    if (count)
        memset(frame->locals, 0, count * sizeof(*frame->locals));
#endif
    frame->local_count = count;
"""
ENTRY_OLD = """        frame->local_capacity = count;
    }
    if (count)
        memset(frame->locals, 0, count * sizeof(*frame->locals));
    frame->local_count = count;
"""
OWNER_NEW = """    if (frame->local_count) {
        size_t index = rc_bounded_local_indices(frame)[--frame->local_count];
        void *value = rc_bounded_local_value(frame, index);
        /* A completed frame is already initialized for its next activation. */
        frame->locals[index] = NULL;
        rc_drop(value);
        return;
    }
"""
OWNER_OLD = """    if (frame->local_count) {
        rc_drop(rc_bounded_pending_local_value(frame, --frame->local_count));
        return;
    }
"""
INVERSES = (("minyar_rc.h", ENTRY_NEW, ENTRY_OLD), ("minyar_cycle_rc.h", ENTRY_NEW, ENTRY_OLD),
            ("minyar_bounded_rc.h", OWNER_NEW, OWNER_OLD), ("minyar_cycle_bounded_rc.h", OWNER_NEW, OWNER_OLD))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hashes(directory):
    return {str(p.relative_to(directory)): digest(p) for p in sorted(directory.rglob("*")) if p.is_file()}


def snapshot(source, destination):
    if not (source / "minyar_runtime.c").is_file():
        raise ValueError("runtime directory lacks minyar_runtime.c: " + str(source))
    before = tree_hashes(source)
    shutil.copytree(source, destination)
    if tree_hashes(destination) != before or tree_hashes(source) != before:
        raise ValueError("runtime input changed while snapshotting: " + str(source))


def reconstruct(directory):
    sites = []
    for name, candidate, control in INVERSES:
        path = directory / name
        source = path.read_text()
        if source.count(candidate) != 1 or control in source:
            raise ValueError("inverse requires exactly one complete candidate block: " + name)
        before = digest(path)
        path.write_text(source.replace(candidate, control))
        sites.append({"file": name, "candidate_sha256": before, "control_sha256": digest(path),
                      "candidate_block_sha256": hashlib.sha256(candidate.encode()).hexdigest(),
                      "control_block_sha256": hashlib.sha256(control.encode()).hexdigest()})
    return {"method": "four exact complete-block inverse transformations; no external patch tool", "sites": sites}


def choices(value, allowed):
    result = value.split(",")
    if not result or len(result) != len(set(result)) or any(item not in allowed for item in result):
        raise argparse.ArgumentTypeError("choose unique comma-separated values from " + ",".join(allowed))
    return result


def cycle_source(source):
    for ordinary, traced in (("minyar_rc.h", "minyar_cycle_rc.h"),
                             ("minyar_collections.h", "minyar_cycle_collections.h")):
        before = '#include "' + ordinary + '"'
        if source.count(before) != 1:
            raise ValueError("expected exactly one " + before)
        source = source.replace(before, '#include "' + traced + '"')
    return ("#define MINYAR_SORT_GRAPH 1\n#define MINYAR_MAP_CYCLE_RUNTIME 1\n"
            "#if defined(__GNUC__) || defined(__clang__)\n"
            "#define MINYAR_NOINLINE __attribute__((noinline))\n#else\n#define MINYAR_NOINLINE\n#endif\n"
            + source + '\n#include "minyar_callbacks.h"\n')


def first_difference(control, candidate):
    sentinel = object()
    with control.open("rb") as left, candidate.open("rb") as right:
        for number, (old, new) in enumerate(itertools.zip_longest(left, right, fillvalue=sentinel), 1):
            if old != new:
                def render(value):
                    return "<end>" if value is sentinel else value.decode("utf-8", "replace").rstrip()[:1800]
                return "line %d\ncontrol: %s\ncandidate: %s" % (number, render(old), render(new))
    return None


class Runner:
    def __init__(self, args, output):
        self.args, self.output = args, output
        self.rows, self.commands, self.engines = [], [], {}
        self.engine_hashes = {}
        inputs = output / "inputs"; inputs.mkdir()
        self.fixture = inputs / "frame-initialization.c"
        fixture = ROOT / "tests/frame-initialization.c"
        before = digest(fixture); shutil.copy2(fixture, self.fixture)
        if digest(self.fixture) != before or digest(fixture) != before:
            raise ValueError("fixture changed while snapshotting")
        self.sources = {role: inputs / (role + "-runtime") for role in ("candidate", "control")}
        snapshot(args.candidate_runtime.resolve(), self.sources["candidate"])
        if args.control_runtime:
            snapshot(args.control_runtime.resolve(), self.sources["control"])
            reconstruction = {"method": "explicit frozen control", "input_directory": str(args.control_runtime.resolve())}
        else:
            shutil.copytree(self.sources["candidate"], self.sources["control"])
            reconstruction = reconstruct(self.sources["control"])
        self.environment = os.environ.copy()
        self.environment["ASAN_OPTIONS"] = "detect_leaks=0:abort_on_error=1"
        self.environment["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
        self.manifest = {
            "scope": "semantic/poll equivalence plus stronger retired-slot invariant; no performance claim",
            "fixture_sha256": digest(self.fixture), "driver_sha256": digest(Path(__file__)),
            "control_reconstruction": reconstruction,
            "candidate_input_directory": str(args.candidate_runtime.resolve()),
            "activated_matrix": args.activated_matrix,
            "environment": {k: self.environment[k] for k in ("ASAN_OPTIONS", "UBSAN_OPTIONS")},
            "runtime_inputs": {role: {"directory": str(directory), "sha256": tree_hashes(directory)}
                for role, directory in self.sources.items()},
            "commands": self.commands, "configurations": self.rows, "executed_engines": {},
        }
        for directory in self.sources.values():
            if not (directory / "minyar_runtime.c").is_file():
                raise ValueError("runtime directory lacks minyar_runtime.c: " + str(directory))
        self.save()

    def save(self):
        (self.output / "results.json").write_text(json.dumps(self.manifest, indent=2) + "\n")

    def engine(self, role, kind):
        source_role = "control" if role.startswith("control") else "candidate"
        key = (source_role, kind)
        if key not in self.engines:
            directory = self.output / (source_role + "-" + kind) / "runtime"
            shutil.copytree(self.sources[source_role], directory)
            if tree_hashes(directory) != self.manifest["runtime_inputs"][source_role]["sha256"]:
                raise ValueError("runtime snapshot changed before engine generation: " + source_role)
            source = (directory / "minyar_runtime.c").read_text()
            if kind == "cycle":
                source = cycle_source(source)
            engine = directory / "frame-initialization-engine.c"
            engine.write_text(source)
            self.engines[key] = engine
            self.engine_hashes[key] = tree_hashes(directory)
            self.manifest["executed_engines"][source_role + "-" + kind] = {
                "directory": str(directory), "sha256": self.engine_hashes[key]}
            self.save()
        return self.engines[key]

    def command(self, argv, stem, timeout, success=True):
        stdout, stderr = stem.with_suffix(".stdout"), stem.with_suffix(".stderr")
        row = {"argv": [str(value) for value in argv], "stdout": str(stdout), "stderr": str(stderr)}
        self.commands.append(row)
        self.save()
        with stdout.open("wb") as out, stderr.open("wb") as err:
            try:
                result = subprocess.run(argv, cwd=ROOT, env=self.environment, stdout=out,
                                        stderr=err, timeout=timeout, check=False)
            except subprocess.TimeoutExpired as error:
                row["timeout"] = timeout
                self.save()
                raise RuntimeError("timeout is a failure: " + str(stem)) from error
        row["exit"] = result.returncode
        self.save()
        if success and (result.returncode or stderr.stat().st_size):
            raise RuntimeError("command failed or emitted diagnostics (%d), see %s" % (result.returncode, stderr))
        return result.returncode, stdout, stderr

    def run(self, role, kind, profile, budget, optimization, mode, case):
        label = "-".join((role, kind, profile, str(budget), optimization, mode, case))
        directory = self.output / "cases" / label
        directory.mkdir(parents=True)
        engine = self.engine(role, kind)
        source_role = "control" if role.startswith("control") else "candidate"
        if tree_hashes(engine.parent) != self.engine_hashes[source_role, kind] or digest(self.fixture) != self.manifest["fixture_sha256"]:
            raise ValueError("executed snapshot changed before compilation")
        executable = directory / "fixture"
        argv = [self.args.clang, "-std=c11", "-Wall", "-Wextra", "-Werror", "-" + optimization,
                "-DMINYAR_RC_POLL_BUDGET=" + str(budget),
                "-DFRAME_CLEAN_EXPECT=" + ("0" if role == "control" else "1"),
                "-DMINYAR_BOUNDED_HEAP_BYTES=" + ("4096" if case == "lower" else "4194304"),
                "-DMINYAR_FRAME_CACHE_BYTES=" + ("1088" if case == "lower" else "262144"),
                '-DMINYAR_RUNTIME_SOURCE="' + str(engine) + '"']
        argv += ["-DMINYAR_SYSTEM_HEAP=1"] if profile == "system" else ["-DMINYAR_BOUNDED_HEAP=1"]
        if profile == "lazy":
            argv.append("-DMINYAR_LAZY_HEAP=1")
        if mode == "sanitize":
            argv += ["-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
        argv += [str(self.fixture), "-o", str(executable), "-lm"]
        self.command(argv, directory / "compile", self.args.compile_timeout)
        return self.command([str(executable), case], directory / "run", self.args.run_timeout,
                            success=role != "control-strong")

    def compare(self, kind, profile, budget, optimization, mode, case):
        control = self.run("control", kind, profile, budget, optimization, mode, case)[1]
        candidate = self.run("candidate", kind, profile, budget, optimization, mode, case)[1]
        difference = first_difference(control, candidate)
        self.rows.append({"runtime": kind, "profile": profile, "budget": budget, "optimization": optimization,
                          "mode": mode, "case": case, "equal": difference is None,
                          "control_sha256": digest(control), "candidate_sha256": digest(candidate)})
        self.save()
        if difference:
            raise RuntimeError("frame semantic transcript changed: " + str(candidate) + "\n" + difference)
        print("%s %s K%d %s %s %s: exact semantic transcript and stronger candidate NULL invariant" %
              (kind, profile, budget, optimization, mode, case), flush=True)

    def negative(self, kind):
        status, _, stderr = self.run("control-strong", kind, "system", 1, "O2", "native", "main")
        payload = stderr.read_bytes()
        detected = status != 0 and re.fullmatch(
            rb"frame-clean invariant: retired/cached capacity slot [0-9]+ is non-NULL\n", payload) is not None
        self.rows.append({"runtime": kind, "negative": "frozen-control-with-stronger-invariant", "detected": detected})
        self.save()
        if not detected:
            raise RuntimeError("stronger cached-slot oracle did not reject the frozen implementation")
        print(kind + ": frozen control rejected by stronger physical invariant", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-runtime", type=Path, help="optional frozen control; otherwise invert the four exact candidate sites")
    parser.add_argument("--candidate-runtime", type=Path, default=REPO / "runtime")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--clang", default=os.environ.get("MINYAR_TEST_CLANG", "clang"))
    parser.add_argument("--profiles", type=lambda value: choices(value, ("system", "fixed", "lazy")), default=["system", "fixed", "lazy"])
    parser.add_argument("--budgets", type=lambda value: choices(value, ("1", "2", "7", "32", "1024")), default=["1", "2", "7", "32", "1024"])
    parser.add_argument("--optimizations", type=lambda value: choices(value, ("O0", "O2")), default=["O0", "O2"])
    parser.add_argument("--modes", type=lambda value: choices(value, ("native", "sanitize")), default=["native", "sanitize"])
    parser.add_argument("--runtimes", type=lambda value: choices(value, ("ordinary", "cycle")), default=["ordinary", "cycle"])
    parser.add_argument("--cases", type=lambda value: choices(value, ("main", "lower", "activated")), default=["main", "lower", "activated"])
    parser.add_argument("--activated-matrix", choices=("reduced", "full"), default="reduced",
                        help="reduced: cycle native/O2 K1/7/32; full: every selected configuration")
    parser.add_argument("--skip-negative", action="store_true",
                        help="skip the frozen-control physical negative; another piece of the same check runs it")
    parser.add_argument("--compile-timeout", type=int, default=120)
    parser.add_argument("--run-timeout", type=int, default=60)
    args = parser.parse_args()
    if args.output_dir:
        output = args.output_dir.resolve()
        output.mkdir(parents=True, exist_ok=False)
    else:
        (ROOT / "build").mkdir(exist_ok=True)
        output = Path(tempfile.mkdtemp(prefix="frame-initialization-", dir=ROOT / "build"))
    print("frame initialization evidence: " + str(output), flush=True)
    try:
        runner = Runner(args, output)
        for kind, profile, budget, optimization, mode, case in itertools.product(
                args.runtimes, args.profiles, args.budgets, args.optimizations, args.modes, args.cases):
            if case == "lower" and profile == "system":
                continue
            if case == "activated" and (kind != "cycle" or (args.activated_matrix == "reduced" and
                    (mode != "native" or optimization != "O2" or budget not in ("1", "7", "32")))):
                continue
            runner.compare(kind, profile, int(budget), optimization, mode, case)
        if not runner.rows:
            raise ValueError("selected filters contain no applicable configuration; activated O0/sanitize/K2/K1024 requires --activated-matrix full")
        if not args.skip_negative:
            for kind in args.runtimes:
                runner.negative(kind)
    except (OSError, RuntimeError, ValueError) as error:
        print(str(error) + "\nevidence retained: " + str(output), file=sys.stderr)
        return 1
    print("frame initialization differential/physical/negative models passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
