#!/usr/bin/env python3
"""Finite Go audit-domain validation and deliberate corruption controls."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from peer_go_domains import SUPPORTED_DOMAIN_PATHS, validate_inline_domain


class GoDomainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = {}
        with (ROOT / 'docs/research/exhaustive/go/decisions.jsonl').open() as stream:
            for line in stream:
                row = json.loads(line)
                if (row['path'] in SUPPORTED_DOMAIN_PATHS
                        and 'generated_domain' in row and 'artifact' not in row['generated_domain']):
                    cls.rows[(row['path'], row['case_id'])] = row

    def case(self, path, identity):
        return copy.deepcopy(self.rows[(path, identity)])

    def reject(self, row):
        with self.assertRaises(ValueError):
            validate_inline_domain(row)

    def test_all_recorded_families_validate(self):
        self.assertEqual(len(self.rows), 111)
        for key, row in self.rows.items():
            with self.subTest(case=key):
                self.assertIs(validate_inline_domain(row), True)

    def test_rotate_cartesian_cardinality_and_axis_corruption(self):
        rows = [r for (path, _), r in self.rows.items() if path == 'test/rotate.go']
        self.assertEqual(sum(r['generated_domain']['instances'] for r in rows), 90944)
        for field, value in [('instances', 16384), ('left_shift_inclusive', [0, 63]),
                             ('join', ['|']), ('unsigned', True), ('bits', True),
                             ('individually_read_generated_source', True)]:
            row = self.case('test/rotate.go', 'mode0/bits64/exhaustive-rule')
            row['generated_domain'][field] = value
            self.reject(row)

    def test_driver_mode_is_tied_to_source(self):
        row = self.case('test/rotate2.go', 'driver-mode2')
        row['generated_domain']['mode'] = 3
        self.reject(row)

    def test_slice_filter_count_and_tokens(self):
        rows = [r for (path, _), r in self.rows.items() if path == 'test/slice3.go']
        self.assertEqual(sum(r['generated_domain']['instances'] for r in rows), 3150)
        row = self.case('test/slice3.go', 'array/exhaustive-rule')
        row['generated_domain']['instances'] += 1
        self.reject(row)
        row = self.case('test/slice3.go', 'slice/exhaustive-rule')
        row['generated_domain']['index_tokens'][6] = 'vminus2'
        self.reject(row)
        row = self.case('test/slice3.go', 'array/exhaustive-rule')
        row['generated_domain']['filter'] = 'no exclusions'
        self.reject(row)

    def test_range_counts_do_not_drop_duplicate_inputs(self):
        row = self.case('test/rangegen.go', 'long/depth2/double1/exhaustive-rule')
        self.assertEqual(row['generated_domain']['code_count'], 136)
        row['generated_domain']['total_trace_comparisons'] -= 136
        self.reject(row)
        row = self.case('test/rangegen.go', 'short/depth5/double-1/exhaustive-rule')
        row['generated_domain']['all_function_inputs_inclusive'][1] += 1
        self.reject(row)
        row = self.case('test/rangegen.go', 'long/depth2/double0/exhaustive-rule')
        row['generated_domain']['double'] = 3
        self.reject(row)

    def test_arithmetic_domain_exclusions_and_values(self):
        identity = 'int64/var-var///exhaustive-rule'
        # Literal '/' operator makes three adjacent slashes in the case ID.
        row = self.case('test/64bit.go', identity)
        row['generated_domain']['exclude_pairs'].pop()
        row['generated_domain']['instances'] += 1
        self.reject(row)
        row = self.case('test/64bit.go', identity)
        row['generated_domain']['exclude_pairs'].append(row['generated_domain']['exclude_pairs'][0])
        self.reject(row)
        row = self.case('test/64bit.go', 'int64/const-var/+/exhaustive-rule')
        row['generated_domain']['left_values'][-1] *= -1
        self.reject(row)
        row = self.case('test/64bit.go', 'int64/unary/-')
        row['generated_domain']['values'][0] = False
        self.reject(row)
        row = self.case('test/64bit.go', 'int64/var-var/+/exhaustive-rule')
        row['generated_domain']['oracle'] = 'wrap every overflow modulo 2**64'
        self.reject(row)

    def test_shift_guards_and_host_width(self):
        row = self.case('test/64bit.go', 'int64/var-var/shifts/host32/exhaustive-rule')
        row['generated_domain']['shift_operand_types']['uint'] = 64
        self.reject(row)
        row = self.case('test/64bit.go', 'uint64/const-var/shifts/host64/exhaustive-rule')
        row['generated_domain']['instances'] += 44
        self.reject(row)

    def test_select_dynamic_tree_not_flat_boolean_product(self):
        counts = {r['generated_domain']['family']: r['generated_domain']['instances']
                  for (path, _), r in self.rows.items() if path == 'test/chan/select5.go'}
        self.assertEqual(counts, {'recv': 241, 'send': 49, 'recvOrder': 194,
                                  'sendOrder': 49, 'nonblock': 512})
        self.assertEqual(sum(counts.values()), 1045)
        row = self.case('test/chan/select5.go', 'recv/exhaustive-rule')
        row['generated_domain']['instances'] = 1 + 4 * 5 * 16
        self.reject(row)

    def test_disposition_cannot_hide_required_adaptation(self):
        row = self.case('test/64bit.go', 'int64/var-const/*/exhaustive-rule')
        row['disposition'] = 'reject'
        row['implementation_needed'] = False
        row['generated_domain']['per_instance_disposition'] = 'reject'
        self.reject(row)
        row = self.case('test/rotate.go', 'mode1/bits8/exhaustive-rule')
        row['disposition'] = 'covered'
        row['generated_domain']['per_instance_disposition'] = 'covered'
        self.reject(row)

    def test_unknown_or_external_schema_remains_unchecked(self):
        self.assertIs(validate_inline_domain({}), False)
        self.assertIs(validate_inline_domain({'path': 'test/unknown.go', 'generated_domain': {}}), False)
        self.assertIs(validate_inline_domain({'path': 'test/64bit.go',
                                              'generated_domain': {'artifact': 'somewhere'}}), False)

    def test_missing_fields_and_wrong_revision_are_contradictions(self):
        row = self.case('test/rotate.go', 'mode0/bits8/exhaustive-rule')
        del row['generated_domain']['instances']
        self.reject(row)
        row = self.case('test/rangegen.go', 'short/depth1/double-1/exhaustive-rule')
        row['revision'] = 'different revision'
        self.reject(row)


if __name__ == '__main__':
    unittest.main()
