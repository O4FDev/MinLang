#!/usr/bin/env python3
"""Required built-in late-registration schedules and the Result cycle oracle.

Both C mains take no arguments. They run their complete internal case set once
per heap/budget profile; this driver deliberately has no --nodes or --case flag.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from cycle_runtime import publish_engine
from clang_helpers import asan_leak_options, windows_host


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


additive = load("registration_additive_support", "tests/cycle-additive.py")
profile_selection = additive.profile_selection


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sanitize", action="store_true")
    parser.add_argument("--profiles", nargs="+", choices=("system", "fixed", "lazy", "eager"))
    parser.add_argument("--budgets", type=int, nargs="+", choices=(1, 32, 1024),
                        default=[1, 32, 1024])
    parser.add_argument("--evidence", type=Path, required=True)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        profiles, unsupported = profile_selection(args.profiles, windows_host())
    except ValueError as error:
        parser.error(str(error))
    out = args.evidence.resolve()
    out.mkdir(parents=True, exist_ok=True)
    (ROOT / "build").mkdir(exist_ok=True)
    generated = publish_engine(ROOT)
    fixtures = {
        "cycle-registration-exposure.c":
            "registration exposure owning paths and queue integrity exact cleanup zero\n",
        "cycle-late-registration.c":
            "late registration 96 owning-path schedules exact cleanup zero\n",
    }
    inputs = [
        Path(__file__), ROOT / "tests/cycle-additive.py", ROOT / "tests/cycle-additive.c",
        *(ROOT / "tests" / name for name in fixtures),
        ROOT / "tests/cycle-late-registration.min", ROOT / "tools/cycle_runtime.py",
        ROOT / "tests/clang_helpers.py", ROOT / "tests/test_evidence.py",
        ROOT / "tests/errors-language.py", ROOT / "tests/errors_evidence.py",
        ROOT / "tests/callbacks.py", ROOT / "tests/regressions.py",
        ROOT / "tests/llvm_sanitizer.py", ROOT / "tests/memory-contracts-runtime.c",
        ROOT / "runtime/minyar_runtime.c", *sorted((ROOT / "runtime").glob("*.h")),
    ]
    fingerprints = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in inputs}
    # Retain the exact transitive helper/header bytes, not only their hashes.
    for path in inputs:
        target = out / "input-sources" / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    compiler = os.environ.get("MINYAR_TEST_CLANG", "clang")
    tool = Path(shutil.which(compiler) or compiler).resolve()
    version = subprocess.run([str(tool), "--version"], check=True, text=True,
                             capture_output=True, timeout=10).stdout
    environment = dict(os.environ, ASAN_OPTIONS=asan_leak_options() + ":halt_on_error=1",
                       UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
    report = {
        "schema_version": 1, "passed": False, "sanitize": args.sanitize,
        "profiles": profiles, "unsupported_profiles": unsupported,
        "bounded_heap_bytes": 1048576, "cases": [], "resources": [],
        "source_sha256": fingerprints,
        "generated_engine_sha256": hashlib.sha256(generated.read_bytes()).hexdigest(),
        "compiler": {"path": str(tool), "sha256": hashlib.sha256(tool.read_bytes()).hexdigest(),
                     "version": version},
        "environment": {name: environment[name] for name in ("ASAN_OPTIONS", "UBSAN_OPTIONS")},
        "schedule_mode": "built-in main(void); no runtime graph-size arguments",
        "exposure_controls": {"phase": 96, "fresh": 48, "append": 24, "shared": 8,
                              "reuse": 64, "other": 9,
                              "public_long_list": "2 only at bounded cleanup budget 1"},
        "late_registration_controls": {"phase": 96, "queued_full_root": 1},
        "result_oracle": {"stdout": "42\n41\n", "stderr": "", "status": 0,
                          "optimizations": ["-O0", "-O2"],
                          "runtime_profile": "system", "cleanup_budget": 1},
    }
    options = {
        "system": ["-DMINYAR_SYSTEM_HEAP=1"], "fixed": ["-DMINYAR_BOUNDED_HEAP=1"],
        "lazy": ["-DMINYAR_BOUNDED_HEAP=1", "-DMINYAR_LAZY_HEAP=1"], "eager": [],
    }
    flags = (["-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
             if args.sanitize else ["-O2"])
    groups = [(fixture, expected, profile, budget)
              for profile in profiles
              for budget in ([32] if profile == "eager" else args.budgets)
              for fixture, expected in fixtures.items()]

    def execute(group):
        fixture, expected, profile, budget = group
        label = fixture[:-2] + "-" + profile + "-k" + str(budget)
        binary = out / (label + (".exe" if windows_host() else ""))
        command = [
            str(tool), *flags, "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-iquote", str(ROOT / "runtime"), *options[profile],
            "-DMINYAR_BOUNDED_HEAP_BYTES=1048576",
            "-DMINYAR_RC_POLL_BUDGET=" + str(budget),
            str(ROOT / "tests" / fixture), "-lm", "-o", str(binary),
        ]
        cases, resources = [], []
        for phase, argv in (("compile", command), ("run-built-in", [str(binary)])):
            case = additive.run(argv, environment, out, label + "-" + phase, resources)
            case.update(fixture=fixture, profile=profile, cleanup_budget=budget)
            if binary.is_file():
                case["binary_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
            cases.append(case)
            print(case["label"] + ": " + str(case["status"]), flush=True)
            if case["status"]:
                return cases, resources, case["label"] + ": " + case["stderr"]
            if phase == "run-built-in" and (case["stdout"] != "" or case["stderr"] != expected):
                return cases, resources, label + ": stdout " + repr(case["stdout"]) + \
                    ", stderr " + repr(case["stderr"]) + ", expected " + repr(expected)
        return cases, resources, None

    try:
        failures = []
        for cases, resources, failed in additive.run_groups(groups, execute):
            report["cases"] += cases
            report["resources"] += resources
            if failed:
                failures.append(failed)
        if failures:
            raise AssertionError("\n".join(failures))

        # Reuse the maintained Result allocation/debt ledger, its exact output
        # oracle, and shared process-tree deadlines at both optimization levels.
        os.environ.update(environment)
        os.environ["MINYAR_TEST_EVIDENCE"] = str(out / "result")
        os.environ["MINYAR_ERRORS_EVIDENCE_OBJECTS"] = str(out / "result-inputs")
        os.environ["MINYAR_ERRORS_RUNTIME_FLAGS"] = (
            "-DMINYAR_SYSTEM_HEAP=1 -DMINYAR_RC_POLL_BUDGET=1")
        if args.sanitize:
            os.environ["MINYAR_TEST_LINK_FLAGS"] = "-fsanitize=address,undefined"
        elif os.environ.get("MINYAR_TEST_LINK_FLAGS"):
            raise ValueError("Native registration gate requires uninstrumented link flags")
        language = load("registration_errors_language", "tests/errors-language.py")
        for name in (language.FRONTEND, ROOT / "compiler/errors-compiler.min",
                     ROOT / "build-support/compiler.mk"):
            report.setdefault("frontend_sha256", {})[str(name)] = hashlib.sha256(name.read_bytes()).hexdigest()

        class Fixture(language.ErrorsLanguage):
            def runTest(self):
                fixture = ROOT / "tests/cycle-late-registration.min"
                self.evidence.inputs[str(fixture)] = hashlib.sha256(fixture.read_bytes()).hexdigest()
                self.executes(fixture.read_text(), "42\n41\n")

        suite = unittest.TestSuite([
            Fixture(),
            language.ErrorsLanguage(
                "test_result_callback_cycles_in_both_payload_slots_are_collected"),
        ])
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        report["result_tests"] = {"run": result.testsRun, "failures": len(result.failures),
                                  "errors": len(result.errors), "skipped": len(result.skipped)}
        assert result.wasSuccessful() and result.testsRun == 2 and not result.skipped
        report["source_after_mismatches"] = [
            name for name, digest in fingerprints.items()
            if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
        assert not report["source_after_mismatches"], report["source_after_mismatches"]
        report["passed"] = True
    finally:
        (out / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
