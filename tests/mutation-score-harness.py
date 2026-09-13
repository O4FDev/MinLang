#!/usr/bin/env python3
"""Verify that mutation scoring rejects empty campaigns and preserves its gate."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "mutation_score", Path(__file__).with_name("mutation-score.py")
)
mutation_score = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mutation_score
SPEC.loader.exec_module(mutation_score)


class MutationScoreHarness(unittest.TestCase):
    def campaign(self, outcomes, *, source="if 1 == 2 {}", minimum=85):
        with tempfile.TemporaryDirectory(prefix="minyar-mutation-harness-") as directory:
            root = Path(directory)
            compiler_source = root / "compiler.min"
            compiler_source.write_text(source)
            output, error = io.StringIO(), io.StringIO()
            with (
                patch.object(mutation_score, "ROOT", root),
                patch.object(mutation_score, "SOURCE", compiler_source),
                patch.object(mutation_score, "run", side_effect=outcomes),
                patch.object(sys, "argv", ["mutation-score.py", "--minimum-score", str(minimum)]),
                contextlib.redirect_stdout(output),
                contextlib.redirect_stderr(error),
            ):
                status = mutation_score.main()
            report = json.loads((root / "build/mutation-score.json").read_text())
            return status, report, error.getvalue()

    def test_no_viable_mutants_fail_even_without_a_score_floor(self):
        success = subprocess.CompletedProcess([], 0)
        failure = subprocess.CompletedProcess([], 1)
        for outcomes in ([failure], [None], [success, failure], [success, None]):
            with self.subTest(outcomes=outcomes):
                status, report, error = self.campaign(outcomes, minimum=0)
                self.assertEqual(status, 1)
                self.assertEqual(report["viable_mutants"], 0)
                self.assertIsNone(report["score_percent"])
                self.assertIn("no viable mutants", error)

    def test_no_discovered_sites_fail(self):
        status, report, _ = self.campaign([], source='print("no operators")')
        self.assertEqual(status, 1)
        self.assertEqual(report["selected_sites"], 0)
        self.assertIsNone(report["score_percent"])

    def test_killed_mutant_passes(self):
        success = subprocess.CompletedProcess([], 0)
        failure = subprocess.CompletedProcess([], 1)
        status, report, _ = self.campaign([success, success, failure])
        self.assertEqual(status, 0)
        self.assertEqual(report["killed_mutants"], 1)
        self.assertEqual(report["score_percent"], 100)

    def test_surviving_mutant_fails_score_floor(self):
        success = subprocess.CompletedProcess([], 0)
        status, report, error = self.campaign([success] * 8)
        self.assertEqual(status, 1)
        self.assertEqual(report["viable_mutants"], 1)
        self.assertEqual(report["score_percent"], 0)
        self.assertIn("below required", error)

    def test_stillborn_mutants_are_excluded_from_score(self):
        success = subprocess.CompletedProcess([], 0)
        failure = subprocess.CompletedProcess([], 1)
        status, report, _ = self.campaign(
            [failure, success, success, failure], source="if 1 == 2 {}\nif 3 == 4 {}",
        )
        self.assertEqual(status, 0)
        self.assertEqual(report["selected_sites"], 2)
        self.assertEqual(report["viable_mutants"], 1)
        self.assertEqual(report["score_percent"], 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
