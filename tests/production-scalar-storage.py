#!/usr/bin/env python3
"""Independent escape, evaluation-order and dominance tests for scalar storage."""
import re
import unittest
from regressions import CompilerTestCase


class ProductionScalarStorage(CompilerTestCase):
    def function_body(self, source, name):
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        match = re.search(r'^define[^\n]*@' + name + r'\([^\n]*\)[^{]*\{(.*?)^}',
                          llvm.read_text(), re.M | re.S)
        self.assertIsNotNone(match)
        return match[1]

    def test_nested_control_flow_does_not_end_escape_proof(self):
        source = '''record Cell { value: Integer }
function save(flag: Boolean, values: List<Cell>): Integer {
let cell = Cell { value: 71 }
if flag {
if cell.value > 0 { print(cell.value) }
}
values.add(cell)
return cell.value
}
let values: List<Cell> = []
print(save(true, values))
print(values[0].value)
print(save(false, values))
print(values[1].value)
'''
        self.assertIn('@minyar_record_new_scalar', self.function_body(source, 'save'))
        self.executes(source, '71\n71\n71\n71\n71\n')

    def test_nested_container_and_parenthesized_escapes_remain_managed(self):
        source = '''record Cell { value: Integer }
record Box { cells: List<Cell> }
function make(): Box {
let cell = Cell { value: 83 }
let boxes = [Box { cells: [(cell)] }]
return boxes[0]
}
let result = make()
print(result.cells[0].value)
'''
        self.assertIn('@minyar_record_new_scalar', self.function_body(source, 'make'))
        self.executes(source, '83\n')

    def test_short_circuit_fields_keep_effect_order_and_scalar_snapshots(self):
        source = '''record Flags { first: Boolean; second: Boolean; before: Integer; after: Integer }
function bump(state: List<Integer>): Boolean {
state[0] = state[0] + 1
return true
}
function work(flag: Boolean, state: List<Integer>): Integer {
let item = Flags {
before: state[0]
first: flag && bump(state)
second: !flag || bump(state)
after: state[0]
}
state[0] = 99
if item.first { print(1) } else { print(0) }
if item.second { print(1) } else { print(0) }
return item.before * 100 + item.after
}
let state = [4]
print(work(true, state))
state[0] = 4
print(work(false, state))
'''
        self.assertNotIn('@minyar_record_', self.function_body(source, 'work'))
        self.executes(source, '1\n1\n406\n0\n1\n404\n')

    def test_shadow_initializers_and_field_names_resolve_independently(self):
        self.executes('''record Pair { item: Integer; value: Integer }
function work(): Integer {
let item = Pair { item: 3; value: 7 }
if item.item > 0 {
let item = Pair { value: item.item; item: item.value }
print(item.item)
print(item.value)
}
let second = Pair { item: item.item; value: item.value }
return second.item * 10 + second.value
}
print(work())
''', '7\n3\n37\n')

    def test_generation_reuse_does_not_replace_managed_parameters(self):
        source = '''record Cell { value: Integer }
function first(input: Integer): Integer {
let cell = Cell { value: input + 1 }
return cell.value
}
function second(cell: Cell): Integer { return cell.value }
function third(input: Integer): Integer {
let cell = Cell { value: input * 3 }
return cell.value
}
function fourth(input: Integer): Cell {
let cell = Cell { value: input + 9 }
return cell
}
print(first(4))
print(second(fourth(2)))
print(third(7))
print(second(fourth(8)))
'''
        self.assertIn('@minyar_record_get', self.function_body(source, 'second'))
        self.assertIn('@minyar_record_new_scalar', self.function_body(source, 'fourth'))
        self.executes(source, '5\n11\n21\n17\n')

    def test_branch_and_loop_scalar_values_dominate_all_uses(self):
        source = '''record Cell { value: Integer }
function work(count: Integer, stop: Boolean): Integer {
let total = 0
let index = 0
while index < count {
if index % 2 == 0 {
let cell = Cell { value: index + 10 }
if stop && index == 2 { return cell.value }
total = total + cell.value
} else {
let cell = Cell { value: index * 2 }
total = total + cell.value
}
index = index + 1
}
return total
}
print(work(0, false))
print(work(5, false))
print(work(5, true))
'''
        self.assertNotIn('@minyar_record_', self.function_body(source, 'work'))
        self.executes(source, '0\n44\n12\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
