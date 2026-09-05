#!/usr/bin/env python3
"""Conservative scalar-record storage inference: semantics and optimized IR."""
import re
import subprocess
import unittest
from regressions import CLANG, ROOT, CompilerTestCase


def body_of(llvm, name):
    match = re.search(r'^define\b[^\n]*@' + re.escape(name) + r'\([^\n]*\)[^{]*\{(.*?)^}', llvm, re.M | re.S)
    if not match:
        raise AssertionError(f'missing function {name}')
    return match[1]


class ScalarRecordStorage(CompilerTestCase):
    def compiled_body(self, source, name):
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        return body_of(llvm.read_text(), name), llvm

    def test_critical_records_have_no_allocation_or_ownership_calls(self):
        source = (ROOT / 'experiments/memory/critical-path.min').read_text()
        body, llvm = self.compiled_body(source, 'criticalRecords')
        self.assertNotIn('@minyar_record_', body)
        self.assertNotIn('@minyar_rc_', body)
        self.assertEqual(body.count('; scalar record '), 1)
        optimized = llvm.with_suffix('.optimized.ll')
        result = subprocess.run([CLANG, '-O2', '-S', '-emit-llvm', '-Wno-override-module',
            str(llvm), '-o', str(optimized)], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        hot = body_of(optimized.read_text(), 'criticalRecords')
        self.assertNotIn('alloca ', hot)
        self.assertNotIn('@minyar_record_', hot)
        self.assertNotIn('@minyar_rc_', hot)

    def test_loop_local_records_and_scalar_field_kinds(self):
        source = '''record Pair { x: Integer; y: Integer }
record Flags { yes: Boolean; character: Character }
function work(count: Integer): Integer {
let i = 0
let total = 0
while i < count {
let p = Pair { x: i; y: i * 2 }
total = total + p.x + p.y
i = i + 1
}
return total
}
print(work(5))
let flag = Flags { yes: true; character: 'é' }
print(flag.yes)
print(flag.character)
'''
        body, _ = self.compiled_body(source, 'work')
        self.assertNotIn('@minyar_record_', body)
        self.executes(source, '30\ntrue\né\n')

    def test_field_initializer_order_and_side_effects(self):
        source = '''record Pair { x: Integer; y: Integer }
function bump(state: List<Integer>, delta: Integer): Integer {
state[0] = state[0] + delta
return state[0]
}
function side(state: List<Integer>): Integer {
let p = Pair { y: bump(state, 10); x: bump(state, 1) }
return p.x * 100 + p.y
}
let state = [0]
print(side(state))
print(state[0])
'''
        body, _ = self.compiled_body(source, 'side')
        self.assertNotIn('@minyar_record_', body)
        self.executes(source, '1110\n11\n')

    def test_shadowing_and_conditional_scopes(self):
        self.executes('''record Pair { x: Integer; y: Integer }
function scoped(flag: Boolean): Integer {
let p = Pair { x: 1; y: 2 }
if flag {
let p = Pair { x: p.y; y: p.x }
print(p.x)
print(p.y)
} else {
let q = Pair { x: 7; y: 8 }
print(q.x)
}
return p.x * 10 + p.y
}
print(scoped(true))
print(scoped(false))
''', '2\n1\n12\n7\n12\n')

    def test_alias_return_and_container_escapes_stay_managed(self):
        sources = (
            '''record Pair { x: Integer; y: Integer }
function escaped(): Pair {
let p = Pair { x: 5; y: 6 }
return p
}
print(escaped().x)
''',
            '''record Pair { x: Integer; y: Integer }
function escaped(): Integer {
let p = Pair { x: 5; y: 6 }
let alias = p
return alias.x
}
print(escaped())
''',
            '''record Pair { x: Integer; y: Integer }
function escaped(values: List<Pair>) {
let p = Pair { x: 5; y: 6 }
values.add(p)
}
let values: List<Pair> = []
escaped(values)
print(values[0].x)
''',
        )
        for source in sources:
            body, _ = self.compiled_body(source, 'escaped')
            self.assertIn('@minyar_record_new_scalar', body)
            self.executes(source, '5\n')

    def test_scalar_returning_helper_can_still_escape_argument(self):
        source = '''record Pair { x: Integer; y: Integer }
function save(p: Pair, values: List<Pair>): Integer {
values.add(p)
return p.x
}
function escaped(values: List<Pair>): Integer {
let p = Pair { x: 9; y: 4 }
return save(p, values)
}
let values: List<Pair> = []
print(escaped(values))
print(values[0].y)
'''
        body, _ = self.compiled_body(source, 'escaped')
        self.assertIn('@minyar_record_new_scalar', body)
        self.executes(source, '9\n4\n')

    def test_reassignment_does_not_overwrite_previous_initializer_inputs(self):
        source = '''record Pair { x: Integer; y: Integer }
function swap(count: Integer): Integer {
let p = Pair { x: 1; y: 2 }
let i = 0
while i < count {
p = Pair { x: p.y; y: p.x }
i = i + 1
}
return p.x * 10 + p.y
}
print(swap(1))
print(swap(2))
'''
        body, _ = self.compiled_body(source, 'swap')
        self.assertEqual(body.count('@minyar_record_new_scalar'), 2)
        self.executes(source, '21\n12\n')

    def test_reference_fields_and_projected_constructor_remain_managed(self):
        source = '''record Label { text: Text }
record Pair { x: Integer; y: Integer }
function label(): Integer {
let value = Label { text: "abc" + "!" }
return value.text.length
}
function direct(): Integer {
let value = Pair { x: 7; y: 8 }.x
return value
}
print(label())
print(direct())
'''
        label, _ = self.compiled_body(source, 'label')
        direct, _ = self.compiled_body(source, 'direct')
        self.assertIn('@minyar_record_new(', label)
        self.assertIn('@minyar_record_new_scalar', direct)
        self.executes(source, '4\n7\n')

    def test_scalar_replacement_has_a_fixed_per_function_budget(self):
        source = 'record Cell { value: Integer }\nfunction many(): Integer {\n'
        source += '\n'.join(f'let cell{i} = Cell {{ value: {i} }}' for i in range(66))
        source += '\nreturn ' + ' + '.join(f'cell{i}.value' for i in range(66)) + '\n}\nprint(many())\n'
        body, _ = self.compiled_body(source, 'many')
        self.assertEqual(body.count('; scalar record '), 64)
        self.assertEqual(body.count('@minyar_record_new_scalar'), 2)
        self.executes(source, '2145\n')

    def test_dead_and_unused_values_keep_initializer_effects(self):
        source = '''record Pair { x: Integer; y: Integer }
function effect(): Integer { print("effect"); return 4 }
function unused(): Integer {
let p = Pair { x: effect(); y: 2 }
return 7
}
print(unused())
'''
        body, _ = self.compiled_body(source, 'unused')
        self.assertNotIn('@minyar_record_', body)
        self.executes(source, 'effect\n7\n')


if __name__ == '__main__':
    unittest.main()
