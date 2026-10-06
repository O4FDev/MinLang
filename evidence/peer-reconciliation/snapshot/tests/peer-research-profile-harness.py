#!/usr/bin/env python3
"""Fault injection for the isolated phase profiler; never a timing gate."""

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "peer_profile", ROOT / "scripts/peer-research-profile.py"
)
PROFILE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROFILE)


class PhaseProfilerHarness(unittest.TestCase):
    def test_failed_native_command_is_retained_as_failed_evidence(self):
        result = PROFILE.resource_probe([sys.executable, "-c", "import sys; sys.exit(7)"], 2)
        self.assertEqual(result["returncode"], 7)
        self.assertFalse(result["timed_out"])

    def test_native_timeout_is_retained_and_terminated(self):
        result = PROFILE.resource_probe([sys.executable, "-c", "import time; time.sleep(10)"], 0.05)
        self.assertTrue(result["timed_out"])
        self.assertNotEqual(result["returncode"], 0)

    def test_every_return_is_instrumented_after_the_entry_label(self):
        source = """define i64 @.minyar.fn.work(i1 %condition) {
entry:
  br i1 %condition, label %yes, label %no
yes:
  ret i64 1
no:
  ret i64 0
}
"""
        result = PROFILE.instrument_ir(source, ["work"])
        self.assertIn("entry:\n  call void @peer_profile_enter(i32 0)\n", result)
        self.assertEqual(result.count("call void @peer_profile_leave(i32 0)"), 2)
        self.assertEqual(result.count("declare void @peer_profile_enter(i32)"), 1)

    def test_missing_function_cannot_silently_produce_an_empty_profile(self):
        with self.assertRaisesRegex(ValueError, "missing.*absent"):
            PROFILE.instrument_ir("define void @main() {\nentry:\n  ret void\n}\n", ["absent"])

    def test_duplicate_function_selection_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            PROFILE.instrument_ir("", ["work", "work"])

    def test_missing_or_incomplete_measurements_are_rejected(self):
        for diagnostic in ("", "peer-profile {bad json}", 'peer-profile {"schema":1}'):
            with self.subTest(diagnostic=diagnostic):
                with self.assertRaises(ValueError):
                    PROFILE.parse_profile(diagnostic, ["work"])

    def test_stack_or_elapsed_accounting_failures_cannot_pass(self):
        for observation in (
            '{"schema":1,"complete":false,"phases":[{"id":0,"calls":1,"inclusive_ns":1,"exclusive_ns":1}]}',
            '{"schema":1,"complete":true,"phases":[{"id":0,"calls":1,"inclusive_ns":1,"exclusive_ns":2}]}',
            '{"schema":1,"complete":true,"phases":[{"id":1,"calls":1,"inclusive_ns":1,"exclusive_ns":1}]}',
        ):
            with self.subTest(observation=observation):
                with self.assertRaises(ValueError):
                    PROFILE.parse_profile("peer-profile " + observation, ["work"])

    def test_valid_measurement_retains_zero_call_phases(self):
        observation = 'peer-profile {"schema":1,"complete":true,"phases":[{"id":0,"calls":0,"inclusive_ns":0,"exclusive_ns":0}]}'
        result = PROFILE.parse_profile(observation, ["work"])
        self.assertEqual(result["phases"][0]["name"], "work")
        self.assertEqual(result["phases"][0]["calls"], 0)


if __name__ == "__main__":
    unittest.main()
