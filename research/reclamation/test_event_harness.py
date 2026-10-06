#!/usr/bin/env python3
"""Adversarial evidence checks: reject false correctness, timing and recovery."""
import copy
import unittest

from event_study import analyze


class EventEvidenceChecks(unittest.TestCase):
    def fixture(self, diagnostic=False):
        spacing = 0 if diagnostic else 10000
        rows, recovery = [], []
        for i in range(512):
            cycle, j = divmod(i, 128)
            arrival = cycle * (128 * spacing + (10000000 if spacing else 0)) + j * spacing
            rows.append(dict(event=i, cycle=cycle, kind='rebuild' if i % 256 == 0 else 'ordinary',
                             result=i, arrival_ns=arrival, start_ns=arrival + 10 if spacing else 0,
                             service_ns=100 if spacing else 0, response_ns=110 if spacing else 0,
                             pending=1, managed_bytes=120 if diagnostic else -1,
                             live_bytes=100 if diagnostic else -1, owner_bytes=64 if diagnostic else -1))
        for cycle in range(4):
            recovery.append(dict(cycle=cycle, pending_before=1, pending_after=0, polls=1,
                                 start_ns=(cycle + 1) * 128 * spacing + cycle * 10000000 if spacing else 0,
                                 duration_ns=100 if spacing else 0, overrun_ns=0,
                                 managed_bytes=100 if diagnostic else -1, live_bytes=100 if diagnostic else -1,
                                 owner_bytes=64 if diagnostic else -1))
        summary = dict(events=512, width=32, seed=7, spacing_ns=spacing, burst=1,
                       total_service_ns=51200 if spacing else 0, lifecycle_ns=45130000 if spacing else 0,
                       pending_before_teardown=0, final_bytes=0 if diagnostic else -1,
                       stack_admissions=0 if diagnostic else -1)
        return summary, rows, recovery, list(range(512)), spacing, 1, diagnostic, 'heap', 32, 7

    def test_valid_timing_and_diagnostic(self):
        self.assertEqual(analyze(*self.fixture())['ordinary']['response_ns']['p99'], 110)
        self.assertEqual(analyze(*self.fixture(True))['max_boundary_dead_managed_bytes'], 20)

    def test_corrupt_event_evidence(self):
        for diagnostic, key, value in [(False, 'arrival_ns', 1), (False, 'result', 42),
                (False, 'kind', 'ordinary'), (False, 'response_ns', 1),
                (False, 'managed_bytes', 0), (False, 'pending', -1),
                (True, 'live_bytes', 121), (True, 'owner_bytes', -1), (True, 'service_ns', 1)]:
            with self.subTest(diagnostic=diagnostic, key=key):
                args = copy.deepcopy(self.fixture(diagnostic)); args[1][0][key] = value
                with self.assertRaises(ValueError): analyze(*args)

    def test_corrupt_recovery_evidence(self):
        for diagnostic, key, value in [(False, 'pending_before', 0), (False, 'start_ns', 0),
                (False, 'overrun_ns', 1), (False, 'pending_after', 1),
                (True, 'managed_bytes', 101), (True, 'pending_after', 1)]:
            with self.subTest(diagnostic=diagnostic, key=key):
                args = copy.deepcopy(self.fixture(diagnostic)); args[2][-1][key] = value
                with self.assertRaises(ValueError): analyze(*args)

    def test_corrupt_summary(self):
        for diagnostic, key, value in [(False, 'total_service_ns', 0), (False, 'lifecycle_ns', 0),
                (False, 'final_bytes', 0), (False, 'events', 513),
                (True, 'final_bytes', 1), (True, 'stack_admissions', 1)]:
            with self.subTest(diagnostic=diagnostic, key=key):
                args = copy.deepcopy(self.fixture(diagnostic)); args[0][key] = value
                with self.assertRaises(ValueError): analyze(*args)

    def test_missing_event_or_recovery_record(self):
        for index in [1, 2]:
            args = copy.deepcopy(self.fixture()); args[index].pop()
            with self.assertRaises(ValueError): analyze(*args)


if __name__ == '__main__':
    unittest.main(verbosity=2)
