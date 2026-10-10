#!/usr/bin/env python3
"""Tooling tests; these do not establish native runtime correctness."""
import importlib.util
from pathlib import Path
import sys
import unittest

path = Path(__file__).with_name('research-native-model-oracle.py')
spec = importlib.util.spec_from_file_location('native_model_oracle', path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
Oracle = module.Oracle


class LogicalOwnership(unittest.TestCase):
    def new(self, oracle, kind, identity, root, children=()):
        oracle.apply(('new', kind, identity, root, *children))

    def test_shared_dag_reachability_and_external_alias(self):
        o = Oracle()
        self.new(o, 1, 1, 0)
        self.new(o, 2, 2, 1, [1, 1])
        o.apply(('alias', 2, 2))
        o.apply(('drop', 0))
        o.apply(('drop', 1))
        self.assertEqual(o.live(), {1, 2})
        o.apply(('drop', 2))
        self.assertEqual(o.live(), set())

    def test_frame_transfer_move_and_temporary_retirement(self):
        o = Oracle()
        self.new(o, 1, 1, 0)
        o.apply(('enter', 3))
        o.apply(('local_take', 0, 0))
        o.apply(('borrow', 1))
        o.apply(('move', 0, 2))
        o.apply(('drop', 2))
        self.assertEqual(o.live(), {1})
        o.apply(('step',))
        self.assertEqual(o.live(), set())
        o.apply(('leave',))

    def test_parent_child_whole_alias_and_replacement(self):
        o = Oracle()
        self.new(o, 1, 1, 0)
        self.new(o, 1, 2, 1)
        self.new(o, 3, 3, 2, [1, 1])
        o.apply(('drop', 0))
        o.apply(('replace', 3, 0, 2))
        self.assertEqual(o.live(), {1, 2, 3})
        o.apply(('replace', 3, 1, 2))
        self.assertEqual(o.live(), {2, 3})

    def test_invalid_cycle_and_dead_resurrection_rejected(self):
        o = Oracle()
        self.new(o, 1, 1, 0)
        self.new(o, 3, 2, 1, [1])
        with self.assertRaises(ValueError):
            o.apply(('replace', 2, 0, 2))
        o.apply(('drop', 0))
        o.apply(('drop', 1))
        with self.assertRaises(ValueError):
            o.apply(('alias', 1, 4))

    def test_nested_frame_survival(self):
        o = Oracle()
        self.new(o, 1, 1, 0)
        o.apply(('enter', 2))
        o.apply(('local', 1, 1))
        o.apply(('drop', 0))
        o.apply(('enter', 1))
        o.apply(('borrow', 1))
        o.apply(('leave',))
        self.assertEqual(o.live(), {1})
        o.apply(('leave',))
        self.assertEqual(o.live(), set())

    def test_payload_digest_changes_after_edge_mutation(self):
        o = Oracle()
        self.new(o, 1, 1, 0)
        self.new(o, 3, 2, 1, [1])
        before = o.digest()
        o.apply(('replace', 2, 0, 0))
        self.assertNotEqual(before, o.digest())

    def test_trace_generator_deterministic_valid_and_fully_retires(self):
        operations = module.generate(39752, 1200)
        self.assertEqual(operations, module.generate(39752, 1200))
        self.assertNotEqual(operations, module.generate(39753, 1200))
        oracle = Oracle()
        for operation in operations:
            oracle.apply(operation)
        self.assertEqual(oracle.live(), set())
        self.assertFalse(oracle.frames)
        self.assertEqual(module.encode(operations), module.encode(operations))
        self.assertEqual(set(module.OPCODES), {op[0] for op in operations})

    def test_occupied_root_and_invalid_slot_do_not_change_state(self):
        o = Oracle()
        self.new(o, 1, 1, 0)
        before = o.digest()
        for invalid in [('new', 1, 2, 0), ('drop', 63), ('enter', 100)]:
            with self.assertRaises(ValueError):
                o.apply(invalid)
            self.assertEqual(o.digest(), before)

    def test_old_parent_can_reference_new_child_but_indirect_cycle_rejected(self):
        o = Oracle()
        self.new(o, 3, 1, 0)
        self.new(o, 2, 2, 1, [1])
        self.new(o, 1, 3, 2)
        o.apply(('append', 1, 3))
        self.assertEqual(o.live(), {1, 2, 3})
        with self.assertRaises(ValueError):
            o.apply(('append', 1, 2))

    def test_trace_census_is_logical_and_exact(self):
        stats = {}
        module.encode([('new', 1, 1, 0), ('enter', 1), ('borrow', 1),
                       ('drop', 0), ('leave',)], stats)
        self.assertEqual(stats['operations'], 5)
        self.assertEqual(stats['operation_counts'], {'new': 1, 'enter': 1, 'borrow': 1, 'drop': 1, 'leave': 1})
        self.assertEqual(stats['object_kinds'], {'1': 1})
        self.assertEqual(stats['peak_logical_live'], 1)
        self.assertEqual(stats['peak_active_frames'], 1)
        self.assertEqual(stats['peak_active_temporaries'], 1)


if __name__ == '__main__':
    unittest.main()
