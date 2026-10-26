#!/usr/bin/env python3
"""Exact differential empty-Map checks. Builds/executions belong on BX only."""
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
REPO = next(p for p in Path(__file__).resolve().parents if (p / "runtime/minyar_runtime.c").is_file())
KEYS = "    if (!map->values[MAP_LENGTH]) return result;\n"
EQUAL = "    if (!left->values[MAP_LENGTH]) { result = 1; goto done; }\n"
PREFIX = """#define MINYAR_SORT_GRAPH 1
#define MINYAR_MAP_CYCLE_RUNTIME 1
#define MINYAR_NOINLINE __attribute__((noinline))
"""


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hashes(directory):
    return {str(p.relative_to(directory)): digest(p) for p in sorted(directory.rglob("*")) if p.is_file()}


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError("expected exactly one source anchor: " + repr(old))
    return source.replace(old, new)


def choices(allowed):
    def parse(value):
        values = value.split(",")
        if len(set(values)) != len(values) or any(v not in allowed for v in values):
            raise argparse.ArgumentTypeError("choose unique comma-separated values from " + ",".join(allowed))
        return values
    return parse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default=os.environ.get("MINYAR_TEST_CLANG", "clang"))
    parser.add_argument("--runtime-directory", type=Path, default=REPO / "runtime")
    parser.add_argument("--output-dir", type=Path)
    for name, allowed in (("profiles", ("system", "fixed", "lazy", "eager", "arena")),
                          ("runtimes", ("ordinary", "cycle")), ("budgets", ("1", "2", "7", "32")),
                          ("optimizations", ("O0", "O2")), ("modes", ("native", "sanitize"))):
        parser.add_argument("--" + name, type=choices(allowed), default=list(allowed))
    parser.add_argument("--skip-mutants", action="store_true")
    args = parser.parse_args()
    if args.output_dir:
        output = args.output_dir.resolve(); output.mkdir(parents=True, exist_ok=False)
    else:
        (REPO / "build").mkdir(exist_ok=True)
        output = Path(tempfile.mkdtemp(prefix="empty-map-", dir=REPO / "build"))
    original_runtime = args.runtime_directory.resolve()
    inputs = output / "inputs"; inputs.mkdir()
    runtime = inputs / "runtime"
    before = tree_hashes(original_runtime); shutil.copytree(original_runtime, runtime)
    if tree_hashes(runtime) != before or tree_hashes(original_runtime) != before:
        raise ValueError("runtime changed while snapshotting")
    original_fixture = ROOT / "tests/empty-map-traversal.c"
    fixture = inputs / "empty-map-traversal.c"
    before = digest(original_fixture); shutil.copy2(original_fixture, fixture)
    if digest(fixture) != before or digest(original_fixture) != before:
        raise ValueError("fixture changed while snapshotting")
    manifest = {"scope": "logical service/ownership equivalence, not performance certification",
                "fixture_sha256": digest(fixture), "runtime_input_directory": str(original_runtime),
                "driver_sha256": digest(Path(__file__)), "commands": [], "pairs": [],
                "runtime_sha256": tree_hashes(runtime), "executed_engines": {}}
    copies, copied_hashes = {}, {}
    def save():
        (output / "results.json").write_text(json.dumps(manifest, indent=2) + "\n")
    def command(argv, stem, success=True, mutation=False):
        env = os.environ.copy()
        env["ASAN_OPTIONS"] = "detect_leaks=%d:abort_on_error=1" % (not mutation)
        env["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
        record = {"argv": [str(x) for x in argv], "environment": {k: env[k] for k in ("ASAN_OPTIONS", "UBSAN_OPTIONS")}}
        manifest["commands"].append(record); save()
        out, err = stem.with_suffix(".stdout"), stem.with_suffix(".stderr")
        record.update(stdout=str(out), stderr=str(err)); save()
        with out.open("wb") as a, err.open("wb") as b:
            try:
                result = subprocess.run(argv, stdout=a, stderr=b, env=env, timeout=120, check=False)
            except subprocess.TimeoutExpired as error:
                record["timeout"] = 120; save(); raise RuntimeError("timeout is a failure: " + str(stem)) from error
        record["exit"] = result.returncode; save()
        if success and (result.returncode or err.stat().st_size):
            raise RuntimeError("command failed or emitted diagnostics: " + str(stem))
        return result.returncode, out, err
    def engine(variant, kind):
        if (variant, kind) in copies:
            return copies[variant, kind]
        directory = output / (variant + "-" + kind) / "runtime"
        shutil.copytree(runtime, directory)
        if tree_hashes(directory) != manifest["runtime_sha256"]:
            raise ValueError("runtime snapshot changed before engine generation")
        path = directory / "minyar_maps.h"; source = path.read_text()
        if source.count(KEYS) != 1 or source.count(EQUAL) != 1:
            raise ValueError("candidate must contain exactly the two designed empty fast paths")
        if variant == "reference":
            source = source.replace(KEYS, "").replace(EQUAL, "")
        elif variant == "mutant-kind":
            source = source.replace(KEYS, "")
            source = replace_once(source, "    MinyarList *result = minyar_list_new();\n",
                                  "    MinyarList *result = minyar_list_new();\n" + KEYS)
        elif variant == "mutant-guard":
            source = source.replace(EQUAL, "")
            anchor = "    MinyarMapReadGuard guard;\n    map_read_begin(&guard, left, right);\n"
            source = replace_once(source, anchor, "    if (!left->values[MAP_LENGTH]) return 1;\n" + anchor)
        source = replace_once(source, "    map_active_reads = guard;\n", "    map_active_reads = guard;\n    fixture_guard(1);\n")
        source = replace_once(source, "    map_active_reads = guard->previous;\n", "    fixture_guard(0);\n    map_active_reads = guard->previous;\n")
        source = replace_once(source, "    minyar_rc_release((void *)guard->first);\n", "    minyar_rc_release((void *)guard->first);\n    fixture_guard(-1);\n")
        path.write_text(source)
        for name in ("minyar_bounded_rc.h", "minyar_cycle_bounded_rc.h"):
            path = directory / name
            source = replace_once(path.read_text(), "size_t minyar_rc_poll(size_t budget) {",
                                  "static size_t fixture_poll_inner(size_t budget) {")
            path.write_text(source + "\nsize_t minyar_rc_poll(size_t budget) { size_t w = fixture_poll_inner(budget); fixture_poll(budget, w); return w; }\n")
        source = (directory / "minyar_runtime.c").read_text()
        if kind == "cycle":
            for a, b in (("minyar_rc.h", "minyar_cycle_rc.h"), ("minyar_collections.h", "minyar_cycle_collections.h")):
                source = replace_once(source, '#include "' + a + '"', '#include "' + b + '"')
            source = PREFIX + source + '\n#include "minyar_callbacks.h"\n'
        path = directory / "empty-map-engine.c"; path.write_text(source)
        copies[variant, kind] = path; copied_hashes[variant, kind] = tree_hashes(directory)
        manifest["executed_engines"][variant + "-" + kind] = {"directory": str(directory), "sha256": copied_hashes[variant, kind]}; save()
        return path
    def run(variant, config, mutant=False):
        kind, profile, budget, optimization, mode = config
        directory = output / "cases" / ("-".join((variant,) + config)); directory.mkdir(parents=True)
        exe = directory / "fixture"
        source = engine(variant, kind)
        if tree_hashes(source.parent) != copied_hashes[variant, kind] or digest(fixture) != manifest["fixture_sha256"]:
            raise ValueError("executed snapshot changed before compilation")
        # These cells pin exact per-service-point cleanup amounts, so they keep one
        # object queue (MINYAR_RC_BACKLOG_BUDGET=0); tests/backlog-pacing.c and
        # tests/direct-service-transcript.c cover the paced old-object backlog.
        argv = [args.clang, "-std=c11", "-Wall", "-Wextra", "-Werror", "-" + optimization,
                '-DMINYAR_RUNTIME_SOURCE="' + str(source) + '"',
                "-DMINYAR_RC_POLL_BUDGET=" + budget, "-DMINYAR_BOUNDED_HEAP_BYTES=4194304",
                "-DMINYAR_RC_BACKLOG_BUDGET=0"]
        flags = {"system": ["-DMINYAR_SYSTEM_HEAP=1"], "fixed": ["-DMINYAR_BOUNDED_HEAP=1"],
                 "lazy": ["-DMINYAR_BOUNDED_HEAP=1", "-DMINYAR_LAZY_HEAP=1"],
                 "eager": [], "arena": ["-DMINYAR_COMPILER_ARENA=1"]}
        argv += flags[profile] + (["-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"] if mode == "sanitize" else [])
        command(argv + [str(fixture), "-o", str(exe), "-lm"], directory / "compile")
        result = command([str(exe)], directory / "run", success=not mutant)
        if mode == "native" and not mutant:
            status, out, err = command([str(exe), "--mutation"], directory / "mutation", success=False, mutation=True)
            expected = b"Minyar stopped: a Map cannot be mutated from its hash or equality method.\n"
            if status != 1 or out.read_bytes() or err.read_bytes() != expected:
                raise RuntimeError("mutation rejection changed: " + str(directory))
        return result
    print("empty Map evidence: " + str(output), flush=True)
    try:
        for config in itertools.product(args.runtimes, args.profiles, args.budgets, args.optimizations, args.modes):
            if config[1] in ("eager", "arena") and config[2] != args.budgets[0]:
                continue
            reference = run("reference", config); candidate = run("candidate", config)
            equal = reference[1].read_bytes() == candidate[1].read_bytes()
            manifest["pairs"].append({"configuration": config, "equal": equal,
                                      "reference_sha256": digest(reference[1]), "candidate_sha256": digest(candidate[1])}); save()
            if not equal:
                raise RuntimeError("logical transcript differs: " + str(candidate[1]))
            print(" ".join(config) + ": exact transcript, result and recovery", flush=True)
        if not args.skip_mutants:
            config = ("ordinary", "system", "1", "O2", "native")
            for variant in ("mutant-kind", "mutant-guard"):
                result = run(variant, config, mutant=True)
                marker = {"mutant-kind": b"empty-map kind invariant: wrong empty result reference kind\n",
                          "mutant-guard": b"empty-map guard invariant: missing equality read guard\n"}[variant]
                detected = result[0] != 0 and result[2].read_bytes() == marker
                manifest["pairs"].append({"mutant": variant, "rejected": detected, "expected_stderr": marker.decode()}); save()
                if not detected:
                    raise RuntimeError("oracle accepted " + variant)
                print(variant + ": rejected", flush=True)
    except (OSError, RuntimeError, ValueError) as error:
        print(str(error) + "\nevidence retained: " + str(output), file=sys.stderr); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
