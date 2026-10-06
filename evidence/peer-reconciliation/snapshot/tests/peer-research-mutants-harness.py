#!/usr/bin/env python3
"""Source-anchor and outcome accounting for bounded reachability mutants."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('reachability_mutants', ROOT / 'scripts/peer-research-mutants.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MutationAccounting(unittest.TestCase):
    def test_unique_anchor_changes_only_the_named_site(self):
        self.assertEqual(module.apply_mutation('abc before xyz', {'before': 'before', 'after': 'after', 'anchor_occurrences': 1}), 'abc after xyz')

    def test_stale_or_ambiguous_anchor_is_incomplete(self):
        for source in ('absent', 'anchor and anchor'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                module.apply_mutation(source, {'before': 'anchor', 'after': '', 'anchor_occurrences': 1})

    def test_calibrated_assertion_failure_is_a_semantic_kill(self):
        report = {'tests_run': 17, 'failures': ['caseA'], 'errors': []}
        self.assertEqual(module.classify_suite(report, 17), 'semantic_kill')

    def test_survivor_requires_the_entire_calibrated_suite(self):
        self.assertEqual(module.classify_suite({'tests_run': 17, 'failures': [], 'errors': []}, 17), 'survived')
        self.assertEqual(module.classify_suite({'tests_run': 0, 'failures': [], 'errors': []}, 17), 'incomplete_suite')

    def test_timeout_and_setup_errors_cannot_be_kills(self):
        for kind in ('timeout', 'infrastructure_error', 'unexpected_error'):
            with self.subTest(kind=kind):
                report = {'tests_run': 17, 'failures': ['caseA'], 'errors': [{'kind': kind}]}
                self.assertEqual(module.classify_suite(report, 17), kind)

    def test_denominator_excludes_incomplete_and_stillborn_mutants(self):
        report = module.mutation_score(['semantic_kill', 'survived', 'build_failed', 'timeout', 'incomplete_suite'])
        self.assertEqual(report, {'viable': 2, 'killed': 1, 'survived': 1, 'excluded': 3, 'percent': 50.0})
        self.assertIsNone(module.mutation_score(['build_failed'])['percent'])


if __name__ == '__main__':
    unittest.main()
