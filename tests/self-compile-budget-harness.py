#!/usr/bin/env python3
"""A failed measurement must never look like a cheap successful compilation."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('budget', ROOT / 'tests/self-compile-budget.py')
budget = importlib.util.module_from_spec(spec)
spec.loader.exec_module(budget)


class BudgetHarness(unittest.TestCase):
    def test_failed_counter_run_cannot_win_the_instruction_budget(self):
        success = subprocess.CompletedProcess([], 0, '', '100000000 instructions retired\n')
        failure = subprocess.CompletedProcess([], 1, '',
            'Minyar stopped: incomplete compilation\n10 instructions retired\n')
        for failed_at in (0, 2, 4):
            measurements = [success] * 5
            measurements[failed_at] = failure
            with self.subTest(failed_at=failed_at), \
                 mock.patch.object(budget.sys, 'platform', 'darwin'), \
                 mock.patch.object(budget.Path, 'exists', return_value=True), \
                 mock.patch.object(budget.subprocess, 'run', side_effect=measurements):
                with self.assertRaisesRegex(SystemExit, 'incomplete compilation'):
                    budget.retired_instructions()

    def test_successful_counter_batch_keeps_existing_minimum_policy(self):
        measurements = [subprocess.CompletedProcess([], 0, '',
            f'{count} instructions retired\n') for count in (91, 87, 93, 89, 90)]
        with mock.patch.object(budget.sys, 'platform', 'darwin'), \
             mock.patch.object(budget.Path, 'exists', return_value=True), \
             mock.patch.object(budget.subprocess, 'run', side_effect=measurements):
            self.assertEqual(budget.retired_instructions(), 87)


if __name__ == '__main__':
    unittest.main()
