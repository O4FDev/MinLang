#!/usr/bin/env python3
"""Negative controls for the exact pinned Zig generated-domain schema."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from peer_zig_domains import SOURCE, COHORTS, expected_domain, instances, validate_complete, validate_domain, validate_reference


class ZigDomains(unittest.TestCase):
    def setUp(self):
        self.domain = expected_domain()
        self.rows = [dict(**SOURCE, case_id='generated-domain/' + c['id'],
                          disposition=c['disposition'], implementation_needed=c['disposition'] == 'adapt',
                          generated_domain={'domain_id': self.domain['domain_id'], 'cohort': c['id'], 'instances': c['instances']})
                     for c in self.domain['cohorts']]
        self.resolutions = [copy.deepcopy(r) for r in self.rows if r['implementation_needed']]

    def test_complete_exact_domain_and_reference_partition(self):
        self.assertEqual([c['instances'] for c in self.domain['cohorts']], [514804, 210, 65815, 65899])
        self.assertEqual(self.domain['total_instances'], 646728)
        self.assertEqual(tuple(validate_domain(self.domain)), COHORTS)
        validate_complete(self.domain, self.rows, self.resolutions)

    def test_concrete_boundary_identities_and_exclusions(self):
        selected = {}
        wanted = {'bits64/base2/power63/below', 'bits64/base2/power63/at',
                  'bits16/base1025/power1/at', 'bits2/base3/one', 'bits16/n65535'}
        for cohort, identity, base, value, expected in instances():
            if identity in wanted:
                selected[cohort, identity] = (base, value, expected)
        self.assertEqual(selected['boundary-representable', 'bits64/base2/power63/below'], (2, 9223372036854775807, 62))
        self.assertEqual(selected['boundary-outside-integer', 'bits64/base2/power63/at'], (2, 9223372036854775808, 63))
        self.assertEqual(selected['boundary-representable', 'bits16/base1025/power1/at'], (1025, 1025, 1))
        self.assertEqual(selected['boundary-representable', 'bits2/base3/one'], (3, 1, 0))
        self.assertEqual(selected['log2-comparison', 'bits16/n65535'], (2, 65535, 15))
        self.assertEqual(selected['log10-comparison', 'bits16/n65535'], (10, 65535, 4))

    def test_wrong_source_hash_revision_or_domain_is_rejected(self):
        for field in ('source_sha256', 'revision', 'path', 'repo', 'domain_id'):
            with self.subTest(field=field):
                broken = copy.deepcopy(self.domain); broken[field] += 'wrong'
                with self.assertRaises(ValueError): validate_domain(broken)

    def test_missing_extra_duplicate_or_deferred_cohort_is_rejected(self):
        for operation in ('missing', 'extra', 'duplicate', 'defer', 'wrong-adapt'):
            with self.subTest(operation=operation):
                broken = copy.deepcopy(self.domain)
                if operation == 'missing': broken['cohorts'].pop()
                elif operation == 'extra': broken['cohorts'].append(copy.deepcopy(broken['cohorts'][0]))
                elif operation == 'duplicate': broken['cohorts'][1] = copy.deepcopy(broken['cohorts'][0])
                elif operation == 'defer': broken['cohorts'][0]['disposition'] = 'defer'
                else: broken['cohorts'][1]['disposition'] = 'adapt'
                with self.assertRaises(ValueError): validate_domain(broken)

    def test_altered_inputs_or_oracles_counts_and_axes_are_rejected(self):
        for field in ('input_sha256', 'oracle_sha256', 'instances'):
            with self.subTest(field=field):
                broken = copy.deepcopy(self.domain)
                broken['cohorts'][0][field] = 514803 if field == 'instances' else '0' * 64
                with self.assertRaises(ValueError): validate_domain(broken)
        for mutate in (lambda d: d['axes']['base_inclusive'].__setitem__(1, 1024),
                       lambda d: d['axes']['boundary_bits_inclusive'].__setitem__(0, True),
                       lambda d: d.__setitem__('total_instances', 646727),
                       lambda d: d.__setitem__('reviewed_instances', 0),
                       lambda d: d.__setitem__('execution_claim', True),
                       lambda d: d.__setitem__('ignored_unknown_field', [])):
            broken = copy.deepcopy(self.domain); mutate(broken)
            with self.assertRaises(ValueError): validate_domain(broken)

    def test_ledger_mismatch_and_suppressed_implementation_are_rejected(self):
        for mutate in (lambda r: r.__setitem__('source_sha256', '0' * 64),
                       lambda r: r.__setitem__('disposition', 'defer'),
                       lambda r: r.__setitem__('implementation_needed', False),
                       lambda r: r.__setitem__('case_id', 'wrong'),
                       lambda r: r['generated_domain'].__setitem__('instances', 1),
                       lambda r: r['generated_domain'].__setitem__('cohort', 'unknown')):
            row = copy.deepcopy(self.rows[0]); mutate(row)
            with self.assertRaises(ValueError): validate_reference(row, row['generated_domain'], self.domain)

    def test_unreferenced_and_unresolved_cohorts_cannot_complete(self):
        for index in range(4):
            with self.subTest(missing_cohort=index):
                rows = self.rows[:index] + self.rows[index + 1:]
                with self.assertRaises(ValueError): validate_complete(self.domain, rows, self.resolutions)
        with self.assertRaises(ValueError): validate_complete(self.domain, self.rows + self.rows[:1], self.resolutions)
        for index in range(3):
            with self.subTest(missing_resolution=index):
                resolutions = self.resolutions[:index] + self.resolutions[index + 1:]
                with self.assertRaises(ValueError): validate_complete(self.domain, self.rows, resolutions)


if __name__ == '__main__':
    unittest.main()
