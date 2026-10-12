#!/usr/bin/env python3
"""Mandatory private-retirement controls with actual operation arguments.

The C main takes N OPERATION [ARGS]. Broad controls use N=32; system/k1 also
enforces the unchanged 192-unit private bound at N=32/256/2048. This gate never
measures or certifies the separate 1s/2% CPU oracle. Every raw command and source
is retained, including the exact v5 expected-failure control.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from cycle_runtime import publish_engine
from clang_helpers import asan_leak_options, clang_command, windows_host
from test_evidence import Evidence

spec = importlib.util.spec_from_file_location("private_retirement_profile_support",
                                             ROOT / "tests/cycle-additive.py")
additive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(additive)
profile_selection = additive.profile_selection

BASELINE_HASHES = {
    "minyar_cycles.h": "43d0e0c2084d490951b7423eea74454f6c7111c58a1d4cf271468fda77910368",
    "minyar_cycle_bounded_rc.h": "0733390de720af61681de03fd02ef3f66d3e8c2d315de54f26e7c6e258ed29ab",
}
COLLECTOR_HASH = "8f0a89de20ecae298e54b030cea789840c513521771ba35517643a5212fd9b61"
BASIC = ("borrow", "fieldless", "private", "replacement", "remove-live",
         "new-child", "anchor-transfer", "shared-child", "cross-component", "unknown-cycle")
QUEUED = ("phase", "local-mark", "local-sweep", "full-mark", "full-sweep",
          "transfer", "drop", "rebuild")
LOCALITY_NODES = (32, 256, 2048)
HEAP_BYTES = 4194304
TIMEOUT = 180  # Existing additive-driver deadline and shared process-tree cleanup.


def operation_plan(profile, budget):
    commands = []
    for mode in BASIC:
        args = ["32", mode]
        if mode == "private" and profile == "system" and budget == 1:
            args.append("assert-local")
        commands.append(args)
    for mode in ("active-local", "active-full"):
        commands.extend(["32", mode, phase] for phase in ("1", "2", "3"))
    if profile != "eager":
        commands.extend(["32", "queued", mode, recent]
                        for mode in QUEUED for recent in ("0", "1"))
        commands.extend(["32", "certificate", generation] for generation in ("0", "1"))
        commands.extend((["32", "reuse"], ["32", "unknown-after-drop"]))
    if profile == "system" and budget == 1:
        commands.extend([str(n), "private", "assert-local"] for n in LOCALITY_NODES[1:])
    return commands


def validate_failure_control(status, stdout, stderr, timed_out=False):
    # Require the actual final work-bound assertion, not any nonzero process or
    # compiler failure. The source calls exact-cleanup empty() before this gate.
    if status == 0 or timed_out or stdout:
        raise AssertionError("v5 did not fail its locality bound cleanly")
    row = re.search(rb"IDLE label=private n=32 rounds=8 units=(\d+) epochs=(\d+)", stderr)
    if row is None or int(row[1]) <= 192 or int(row[2]) == 0:
        raise AssertionError("v5 failure lacks the private work/epoch counterexample")
    if b"work <= 16u * rounds + 64u" not in stderr:
        raise AssertionError("v5 failed outside the final private locality assertion")



def validate_operation(stdout, stderr, arguments):
    if stdout:
        raise AssertionError("retirement control wrote stdout")
    n, operation = arguments[:2]
    if operation == "certificate":
        if stderr:
            raise AssertionError("certificate exclusion control wrote unexpected stderr")
        return
    if operation in BASIC[:5]:
        prefix = "IDLE label=" + operation + " n=" + n + " rounds=8 "
    elif operation in BASIC[5:]:
        prefix = "POSITIVE label=" + operation + " n=" + n + " "
    elif operation.startswith("active-"):
        prefix = ("ACTIVE n=" + n + " phase=" + arguments[2] + " local=" +
                  ("1" if operation == "active-local" else "0") + " ")
    elif operation == "queued":
        prefix = "QUEUED n=" + n + " mode=" + arguments[2] + " recent=" + arguments[3] + " "
    elif operation == "reuse":
        prefix = "REUSE n=" + n + " rounds=128 "
    elif operation == "unknown-after-drop":
        prefix = "UNKNOWN_AFTER_DROP n=" + n + " "
    else:
        raise AssertionError("unknown retirement operation")
    if not stderr.startswith(prefix.encode("ascii")) or stderr.count(b"\n") != 1:
        raise AssertionError("retirement control lacks its exact operation ledger")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sanitize", action="store_true")
    parser.add_argument("--profiles", nargs="+", choices=("system", "fixed", "lazy", "eager"))
    parser.add_argument("--budgets", type=int, nargs="+", choices=(1, 32, 1024), default=[1, 32, 1024])
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    try:
        profiles, unsupported = profile_selection(args.profiles, windows_host())
    except ValueError as error:
        parser.error(str(error))
    out = args.evidence.resolve()
    out.mkdir(parents=True, exist_ok=False)
    inputs = [Path(__file__), ROOT / "tests/cycle-idle-invalidation.c",
              ROOT / "tests/cycle-additive.c", ROOT / "tests/cycle-additive.py",
              ROOT / "tests/cycle-private-retirement-v5.json",
              ROOT / "tests/fixtures/cycle-private-retirement-v5-collector.h", ROOT / "tools/cycle_runtime.py",
              ROOT / "tests/clang_helpers.py", ROOT / "tests/test_evidence.py",
              ROOT / "runtime/minyar_runtime.c", *sorted((ROOT / "runtime").glob("*.h"))]
    fingerprints = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in inputs}
    for p in inputs:
        target = out / "input-sources" / p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(p.read_bytes())
    generated = publish_engine(ROOT)
    retained_engine = out / "managed-graphs-engine.c"
    retained_engine.write_bytes(generated.read_bytes())
    compiler = Path(shutil.which(os.environ.get("MINYAR_TEST_CLANG", "clang")) or
                    os.environ.get("MINYAR_TEST_CLANG", "clang")).resolve()
    shutil.copyfile(compiler, out / "clang.bin")
    environment = dict(os.environ, ASAN_OPTIONS=asan_leak_options() + ":halt_on_error=1",
                       UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
    os.environ["MINYAR_TEST_EVIDENCE"] = str(out / "commands")
    evidence = Evidence("private-retirement", inputs=inputs,
                        controls={"sanitize": args.sanitize, "heap_bytes": HEAP_BYTES})
    report = dict(schema_version=1, passed=False, sanitize=args.sanitize, profiles=profiles,
                  unsupported_profiles=unsupported, heap_bytes=HEAP_BYTES, cases=[],
                  source_sha256=fingerprints, source_after_mismatches=[],
                  engine_sha256=hashlib.sha256(retained_engine.read_bytes()).hexdigest(),
                  compiler={"path": str(compiler), "sha256": hashlib.sha256(compiler.read_bytes()).hexdigest()},
                  environment={k: environment[k] for k in ("ASAN_OPTIONS", "UBSAN_OPTIONS")},
                  broad_nodes=32, private_locality_nodes=(list(LOCALITY_NODES) if "system" in profiles and 1 in args.budgets else []),
                  budgets=args.budgets,
                  baseline_failure_control=False, scope="Deterministic phase/work/cleanup; no CPU idle certification")
    flags = (["-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
             if args.sanitize else ["-O2"])
    heap_flags = {"system": ["-DMINYAR_SYSTEM_HEAP=1"],
                  "fixed": ["-DMINYAR_BOUNDED_HEAP=1"],
                  "lazy": ["-DMINYAR_BOUNDED_HEAP=1", "-DMINYAR_LAZY_HEAP=1"], "eager": []}

    def save():
        report["commands"] = evidence.commands
        report["tool_hashes"] = [
            {"identity": {"path": identity[0], "size": identity[1],
                          "mtime_ns": identity[2], "inode": identity[3]}, "sha256": digest}
            for identity, digest in evidence.tool_hashes.items()]
        (out / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")

    def observe(label, argv, binary=None):
        index = len(evidence.commands)
        try:
            return evidence.run(argv, capture_output=True, env=environment, cwd=ROOT,
                                timeout=TIMEOUT, phase=label)
        finally:
            if len(evidence.commands) > index:
                row = dict(evidence.commands[-1], label=label)
                for stream in ("stdout", "stderr"):
                    raw = base64.b64decode(row.get(stream + "_base64", ""))
                    (out / (label + "." + stream)).write_bytes(raw)
                    row[stream + "_sha256"] = hashlib.sha256(raw).hexdigest()
                if binary is not None and binary.is_file():
                    row["binary_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
                report["cases"].append(row)
            save()

    def compile_fixture(label, profile, budget, include_dir):
        binary = out / (label + (".exe" if windows_host() else ""))
        command = clang_command([
            str(compiler), *flags, "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-iquote", str(include_dir), *heap_flags[profile],
            "-DMINYAR_BOUNDED_HEAP_BYTES=" + str(HEAP_BYTES),
            "-DMINYAR_RC_POLL_BUDGET=" + str(budget),
            str(ROOT / "tests/cycle-idle-invalidation.c"), "-lm", "-o", str(binary)])
        result = observe(label + "-compile", command, binary)
        assert result.returncode == 0 and not result.stdout and not result.stderr, label
        return binary

    try:
        version = observe("compiler-version", [str(compiler), "--version"])
        assert version.returncode == 0
        report["compiler"]["version"] = version.stdout.decode("utf-8", errors="replace")
        for profile in profiles:
            for budget in ([32] if profile == "eager" else args.budgets):
                label = profile + "-k" + str(budget)
                binary = compile_fixture(label, profile, budget, ROOT / "runtime")
                plan = operation_plan(profile, budget)
                for index, arguments in enumerate(plan):
                    case = observe(label + "-case-" + str(index), [str(binary), *arguments], binary)
                    assert case.returncode == 0, (label, arguments, case.stderr)
                    validate_operation(case.stdout, case.stderr, arguments)
                    print(label + " " + " ".join(arguments) + ": 0", flush=True)

        # A Git-free exact v5 pair, compiled with the same final C and engine.
        baseline = json.loads((ROOT / "tests/cycle-private-retirement-v5.json").read_text())
        assert baseline["schema_version"] == 1 and set(baseline["headers"]) == set(BASELINE_HASHES)
        assert baseline["collector_sha256"] == COLLECTOR_HASH
        # Product collector changes must not rewrite the independent frozen
        # control. Bind the old pair to its exact original collector source.
        assert fingerprints["tests/fixtures/cycle-private-retirement-v5-collector.h"] == COLLECTOR_HASH
        control_headers = out / "failure-control/runtime"
        control_headers.mkdir(parents=True)
        for header in sorted((ROOT / "runtime").glob("*.h")):
            (control_headers / header.name).write_bytes(header.read_bytes())
        for name, digest in BASELINE_HASHES.items():
            row = baseline["headers"][name]
            raw = row["source"].encode("utf-8")
            assert row["sha256"] == digest == hashlib.sha256(raw).hexdigest()
            (control_headers / name).write_bytes(raw)
        frozen_collector = (ROOT / "tests/fixtures/cycle-private-retirement-v5-collector.h").read_bytes()
        assert hashlib.sha256(frozen_collector).hexdigest() == COLLECTOR_HASH
        (control_headers / "minyar_cycles_collect.h").write_bytes(frozen_collector)
        binary = compile_fixture("v5-failure-control", "system", 1, control_headers)
        failure = observe("v5-locality-expected-failure",
                          [str(binary), "32", "private", "assert-local"], binary)
        validate_failure_control(failure.returncode, failure.stdout, failure.stderr,
                                 evidence.commands[-1]["timed_out"])
        report["baseline_failure_control"] = True
        report["cases"][-1]["expected_outcome"] = "v5 runtime locality assertion; not a product pass"
        report["source_after_mismatches"] = [
            name for name, digest in fingerprints.items()
            if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
        assert not report["source_after_mismatches"], report["source_after_mismatches"]
        assert generated.read_bytes() == retained_engine.read_bytes(), "generated engine changed"
        report["passed"] = True
    finally:
        report["source_after_mismatches"] = [
            name for name, digest in fingerprints.items()
            if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
        save()
        # Deliberately keep Evidence workspace and all successful binaries/logs.


if __name__ == "__main__":
    main()
