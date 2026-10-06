#!/usr/bin/env python3
"""Reject plausible corrupted evidence, not merely exercise happy paths."""
import copy
import unittest
from run_study import percentile, validate
from variants import transform


class EvidenceChecks(unittest.TestCase):
    def setUp(self):
        self.data = dict(shape='chain', nodes=2, seed=7, mode='diagnostic', checksum=2,
                         final_bytes=0, prepared_bytes=100, samples=3, polls=2,
                         diagnostic_total_work=4)
        self.rows = [dict(sample=str(i), kind='poll' if i else 'retire', ns='0',
                          work=str(w), pending=str(p), managed_bytes=str(b))
                     for i, (w, p, b) in enumerate([(1, 1, 75), (2, 1, 50), (1, 0, 24)])]

    def check(self, data=None, rows=None):
        return validate(self.data if data is None else data, self.rows if rows is None else rows,
                        'current', 'chain', 2, 7, 'diagnostic', 2)

    def test_reference_trace(self):
        self.assertEqual(self.check()['post_retire_dead_managed_bytes'], 51)

    def test_corrupted_traces_rejected(self):
        for row, key, value in [(0, 'work', '3'), (1, 'work', '0'), (2, 'pending', '1'),
                                (1, 'sample', '99'), (1, 'ns', '10'), (1, 'kind', 'retire'),
                                (1, 'managed_bytes', '90')]:
            with self.subTest(key=key, value=value):
                rows = copy.deepcopy(self.rows); rows[row][key] = value
                with self.assertRaises(ValueError): self.check(rows=rows)

    def test_missing_reclamation_or_wrong_checksum_rejected(self):
        for key, value in [('final_bytes', 1), ('checksum', 3), ('diagnostic_total_work', 5)]:
            data = dict(self.data); data[key] = value
            with self.assertRaises(ValueError): self.check(data=data)
        with self.assertRaises(ValueError): self.check(rows=self.rows[:-1])

    def test_nearest_rank(self):
        self.assertEqual(percentile([40, 10, 20, 30], .5), 20)
        self.assertEqual(percentile([40, 10, 20, 30], .99), 40)
        self.assertIsNone(percentile([], .99))

    def test_transformation_fails_closed_on_unknown_runtime(self):
        with self.assertRaises(ValueError): transform('unrecognized runtime', 'fifo')


if __name__ == '__main__':
    unittest.main(verbosity=2)
