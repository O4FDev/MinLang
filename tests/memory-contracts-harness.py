#!/usr/bin/env python3
"""Integration tests for candidate memory-contract evidence and failure detection.

This tests the runner with a real compiler and runtime, then deliberately faulty
inputs. It does not change or invoke the language performance suites. Evidence
is retained, including expected rejection logs, so failures can be replayed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROTECTED = (
    "tests/scaling.py", "tests/self-compile-budget.py", "tests/performance.py",
    "tests/performance/runtime.min", "build/performance-baseline.json",
)
OPTIONS = None


def protected_state():
    return {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        if (ROOT / name).exists() else None
        for name in PROTECTED
    }


class MemoryContractsHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = OPTIONS.output_dir.resolve()
        cls.evidence.mkdir(parents=True, exist_ok=True)
        cls.protected_before = protected_state()
        cls.outcomes = []

    @classmethod
    def tearDownClass(cls):
        after = protected_state()
        (cls.evidence / "harness-results.json").write_text(json.dumps({
            "cases": cls.outcomes,
            "protected_before": cls.protected_before,
            "protected_after": after,
        }, indent=2) + "\n")
        if after != cls.protected_before:
            raise AssertionError("Protected performance files changed during harness tests")

    def run_contracts(self, label, *, compiler=None, runtime=None, timeout=60):
        case = self.evidence / label
        case.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable, str(OPTIONS.runner.resolve()),
            "--compiler", str((compiler or OPTIONS.compiler).resolve()),
            "--runtime-source", str(((runtime / "minyar_runtime.c") if runtime else OPTIONS.runtime_source).resolve()),
            "--level", "smoke", "--profiles", "eager", "--mode", "native",
            "--timeout", str(timeout), "--output-dir", str(case / "runs"),
        ]
        # The outer bound distinguishes a broken runner timeout from a correctly
        # recorded child timeout; a hang is a harness failure, never a success.
        try:
            result = subprocess.run(command, cwd=ROOT, capture_output=True,
                                    text=True, timeout=max(timeout * 3, 30))
        except subprocess.TimeoutExpired as error:
            (case / "runner.log").write_text(str(error) + "\n")
            self.fail("The runner failed to enforce its child timeout")
        (case / "command.json").write_text(json.dumps(command, indent=2) + "\n")
        (case / "runner.log").write_text(result.stdout + result.stderr)
        manifests = list((case / "runs").rglob("results.json"))
        self.assertTrue(manifests, "No retained results.json; see " + str(case / "runner.log"))
        self.assertEqual(len(manifests), 1, "Smoke should retain one unambiguous result manifest")
        data = json.loads(manifests[0].read_text())
        self.outcomes.append({"label": label, "returncode": result.returncode,
                              "manifest": str(manifests[0]), "status": data.get("status")})
        self.assertIn(data.get("status"), ("passed", "failed", "interrupted"))
        self.assertTrue(data.get("sources"), "Evidence must identify the tested inputs")
        self.assertTrue(data.get("checks"), "Evidence must record the executed checks")
        for check in data["checks"]:
            for field in ("label", "command", "returncode", "timed_out", "log"):
                self.assertIn(field, check)
        return result, data, manifests[0].parent

    @staticmethod
    def failure_rows(data):
        return [row for row in data["checks"]
                if row["timed_out"] or row["returncode"] != 0]

    def fake_compiler(self, label, body):
        directory = self.evidence / "inputs"
        directory.mkdir(exist_ok=True)
        executable = directory / label
        executable.write_text("#!/bin/sh\n" + body + "\n")
        executable.chmod(0o755)
        return executable

    def test_real_language_smoke_is_accepted(self):
        result, data, _ = self.run_contracts("normal-smoke")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(data["status"], "passed")
        self.assertFalse(self.failure_rows(data))

    def test_normal_return_leak_is_rejected(self):
        copied = self.evidence / "inputs" / "leaked-runtime"
        shutil.copytree(OPTIONS.runtime_source.parent, copied, dirs_exist_ok=True)
        with (copied / "minyar_runtime.c").open("a") as runtime:
            runtime.write('''
/* Harness mutant: a real allocated object with no owner and no release. */
#ifndef MINYAR_COMPILER_ARENA
static void *volatile memory_contract_orphan;
__attribute__((constructor)) static void memory_contract_leak(void) {
    memory_contract_orphan = rc_allocate_object(64, RC_TEXT);
}
#endif
''')
        result, data, directory = self.run_contracts("normal-return-leak", runtime=copied)
        self.assertNotEqual(result.returncode, 0, "An orphan allocation escaped the cleanup oracle")
        self.assertEqual(data["status"], "failed")
        self.assertTrue(self.failure_rows(data))
        logs = "\n".join(path.read_text(errors="replace") for path in directory.rglob("*.log"))
        self.assertRegex(logs, r"(rc_object_count\s*==\s*rc_immortal_object_count|memory cleanup oracle: leaked objects)",
                             "The rejection should retain its cleanup diagnosis")

    def test_compiler_failure_is_rejected_and_retained(self):
        compiler = self.fake_compiler("failed-compiler", "echo MINYAR_HARNESS_COMPILER_FAILURE >&2\nexit 23")
        result, data, directory = self.run_contracts("compiler-failure", compiler=compiler)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(data["status"], "failed")
        self.assertTrue(self.failure_rows(data))
        logs = "\n".join(path.read_text(errors="replace") for path in directory.rglob("*.log"))
        self.assertIn("MINYAR_HARNESS_COMPILER_FAILURE", logs)

    def test_non_utf8_compiler_failure_is_rejected_and_retained(self):
        compiler = self.fake_compiler(
            "binary-diagnostic-compiler",
            r"printf '\377MINYAR_HARNESS_BINARY_DIAGNOSTIC\n' >&2" + "\nexit 23")
        result, data, directory = self.run_contracts("non-utf8-compiler-failure", compiler=compiler)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(data["status"], "failed",
                         "Malformed diagnostics must not strand the report as running")
        self.assertTrue(self.failure_rows(data))
        logs = "\n".join(path.read_text(errors="replace") for path in directory.rglob("*.log"))
        self.assertIn("MINYAR_HARNESS_BINARY_DIAGNOSTIC", logs)

    def test_compiler_timeout_is_rejected_and_retained(self):
        # exec prevents a shell wrapper from hiding the sleeping process from
        # the runner's termination logic.
        compiler = self.fake_compiler("sleeping-compiler",
                                      "echo MINYAR_HARNESS_COMPILER_SLEEPING >&2\nexec sleep 30")
        result, data, _ = self.run_contracts(
            "compiler-timeout", compiler=compiler, timeout=3)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(data["status"], "failed")
        timed_out = [row for row in data["checks"] if row["timed_out"]]
        self.assertTrue(timed_out,
                        "A killed command must remain distinguishable from an ordinary failure")
        self.assertTrue(any("MINYAR_HARNESS_COMPILER_SLEEPING" in
                            Path(row["log"]).read_text(errors="replace") for row in timed_out),
                        "Timeout must exercise the compiler descendant, not a preceding build")


def main():
    global OPTIONS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", type=Path, default=ROOT / "tests/memory-contracts.py")
    parser.add_argument("--compiler", type=Path, default=ROOT / "build/minyarc")
    parser.add_argument("--runtime-source", type=Path, default=ROOT / "runtime/minyar_runtime.c")
    parser.add_argument("--output-dir", type=Path)
    OPTIONS, remaining = parser.parse_known_args()
    if OPTIONS.runtime_source.is_dir():
        OPTIONS.runtime_source = OPTIONS.runtime_source / "minyar_runtime.c"
    if OPTIONS.output_dir is None:
        OPTIONS.output_dir = Path(tempfile.mkdtemp(prefix="minyar-memory-contract-harness-"))
    print("Harness evidence: " + str(OPTIONS.output_dir.resolve()), flush=True)
    unittest.main(argv=[sys.argv[0], *remaining])


if __name__ == "__main__":
    main()
