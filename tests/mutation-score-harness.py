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
    def campaign(self, outcomes, *, source="if 1 == 2 {}", minimum=85, baseline=True):
        with tempfile.TemporaryDirectory(prefix="minyar-mutation-harness-") as directory:
            root = Path(directory)
            compiler_source = root / "compiler.min"
            compiler_source.write_text(source)
            output, error = io.StringIO(), io.StringIO()
            with (
                patch.object(mutation_score, "ROOT", root),
                patch.object(mutation_score, "SOURCE", compiler_source),
                patch.object(mutation_score, "run", side_effect=(
                    [subprocess.CompletedProcess([], 0)] * len(mutation_score.CHECKS) + list(outcomes)
                    if baseline else outcomes)),
                patch.object(sys, "argv", ["mutation-score.py", "--minimum-score", str(minimum)]),
                contextlib.redirect_stdout(output),
                contextlib.redirect_stderr(error),
            ):
                status = mutation_score.main()
            report = json.loads((root / "build/mutation-score.json").read_text())
            return status, report, error.getvalue()

    def test_failing_baseline_cannot_be_counted_as_killed_mutant(self):
        success = subprocess.CompletedProcess([], 0)
        failure = subprocess.CompletedProcess([], 1, "", "broken baseline")
        status, report, error = self.campaign([success, success, failure], baseline=False)
        self.assertEqual(status, 1)
        self.assertEqual(report["killed_mutants"], 0)
        self.assertIn("baseline", error)

    def test_no_viable_mutants_fail_even_without_a_score_floor(self):
        success = subprocess.CompletedProcess([], 0)
        failure = subprocess.CompletedProcess([], 1)
        for outcomes in ([failure], [None], [success, failure], [success, None]):
            with self.subTest(outcomes=outcomes):
                status, report, error = self.campaign(outcomes, minimum=0)
                self.assertEqual(status, 1)
                self.assertEqual(report["viable_mutants"], 0)
                self.assertIsNone(report["score_percent"])
                self.assertIn("incomplete" if None in outcomes else "no viable mutants", error)

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
        status, report, error = self.campaign([success] * (2 + len(mutation_score.CHECKS)))
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

    def test_timed_out_baseline_fails_before_mutation(self):
        status, report, error = self.campaign([None], baseline=False)
        self.assertEqual(status, 1)
        self.assertFalse(report["baseline_passed"])
        self.assertEqual(report["outcomes"], [])
        self.assertIn("baseline", error)

    def test_timeout_preserves_partial_diagnostics(self):
        result = subprocess.CompletedProcess([], -9, "started", "partial diagnostic")
        result.timed_out = True
        status, report, _ = self.campaign([result], baseline=False)
        self.assertEqual(status, 1)
        self.assertTrue(report["commands"][0]["timed_out"])
        self.assertEqual(report["commands"][0]["stderr"], "partial diagnostic")

    def test_missing_tool_is_infrastructure_failure(self):
        status, report, error = self.campaign([FileNotFoundError("missing compiler")], baseline=False)
        self.assertEqual(status, 1)
        self.assertEqual(report["killed_mutants"], 0)
        self.assertIn("infrastructure", error)
        self.assertEqual(report["commands"][0]["error"], "missing compiler")

    def test_build_timeout_cannot_disappear_behind_a_killed_mutant(self):
        success = subprocess.CompletedProcess([], 0)
        failure = subprocess.CompletedProcess([], 1)
        status, report, error = self.campaign([None, success, success, failure], source="if 1 == 2 {}\nif 3 == 4 {}")
        self.assertEqual(status, 1)
        self.assertEqual(report["build_timeouts"], 1)
        self.assertEqual(report["score_percent"], 100)
        self.assertIn("incomplete", error)

    def test_mutant_environment_reaches_every_suite(self):
        success = subprocess.CompletedProcess([], 0)
        status, report, _ = self.campaign([success] * (2 + len(mutation_score.CHECKS)), minimum=0)
        self.assertEqual(status, 0)
        mutant_checks = [row for row in report["commands"] if row["phase"].endswith(":test")]
        self.assertEqual(len(mutant_checks), len(mutation_score.CHECKS))
        for row in mutant_checks:
            self.assertTrue(row["compiler"].endswith("mutant-0"))

    def test_internal_compiler_units_receive_the_candidate_source(self):
        success = subprocess.CompletedProcess([], 0)
        status, report, _ = self.campaign([success] * (2 + len(mutation_score.CHECKS)), minimum=0)
        self.assertEqual(status, 0)
        for row in report["commands"]:
            if row["phase"] == "baseline":
                self.assertTrue(row.get("compiler_source", "").endswith("/compiler.min"))
            elif row["phase"].endswith(":test"):
                self.assertTrue(row.get("compiler_source", "").endswith("/mutant-0.min"))

    def test_campaign_includes_internal_units_and_parameter_optimization(self):
        scripts = {command[1] for command in mutation_score.CHECKS}
        self.assertIn("tests/source-map.py", scripts)
        self.assertIn("tests/symbol-order.py", scripts)
        self.assertIn("tests/readonly-parameters.py", scripts)

    def test_discovery_excludes_literals_comments_and_list_types(self):
        source = 'let values: List<Integer> = []\n// == !=\n/* >= */\nprint("<= &&")\nif 1 <= 2 && 3 > 2 {}'
        sites = mutation_score.discover(source)
        self.assertEqual([site.operator for site in sites], ["<=", "&&", ">"])
        self.assertTrue(all(site.line == 5 for site in sites))


if __name__ == "__main__":
    unittest.main(verbosity=2)
