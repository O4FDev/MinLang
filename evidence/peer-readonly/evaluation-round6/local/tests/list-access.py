#!/usr/bin/env python3
"""Checked List fast paths preserve bounds, evaluation order and ownership."""
import re
import subprocess
import unittest
from regressions import CLANG, RUNTIME, LINK_FLAGS, RUN_TIMEOUT, CompilerTestCase
from clang_helpers import clang_command


class ListAccess(CompilerTestCase):
    def test_inline_access_helpers_preserve_checked_fallback(self):
        llvm = self.executes('let values = [42]\nvalues[0] = 42\nprint(values[0])\nprint(values.length)\n',
                             '42\n1\n')
        generated = llvm.read_text()
        self.assertIn('define internal i64 @.minyar.list.get.checked', generated)
        self.assertIn('define internal void @.minyar.list.set.scalar.checked', generated)
        self.assertIn('define internal i64 @.minyar.list.length', generated)
        self.assertIn('%get.valid = icmp ult i64 %position, %length', generated)
        self.assertIn('%set.valid = icmp ult i64 %position, %length', generated)
        self.assertIn('%fallback = call i64 @minyar_list_get(ptr %list, i64 %position)\n  ret i64 %fallback', generated)
        self.assertIn('call void @minyar_list_set(ptr %list, i64 %position, i64 %value)\n  ret void', generated)
        list_helpers = re.findall(r'^define internal [^\n]* @\.minyar\.list\.[^\n]*\n.*?^}',
                                  generated, re.M | re.S)
        self.assertEqual(len(list_helpers), 3)
        for helper in list_helpers:
            self.assertNotIn('unreachable', helper)
        self.assertNotIn('noalias', generated)

    def test_scalar_slots_keep_integer_float_boolean_character_values(self):
        self.executes('''let integers = [0]
integers[0] = -9223372036854775808
print(integers[0])
let floats = [1.0]
floats[0] = -0.0
print(floats[0])
floats[0] = 2.5
floats[0] *= 4.0
print(floats[0])
let booleans = [false]
booleans[0] = true
print(booleans[0])
let characters = ['a']
characters[0] = '🙂'
print(characters[0])
''', '-9223372036854775808\n-0.0\n10.0\ntrue\n🙂\n')

    def test_bad_getters_and_setters_keep_exact_runtime_diagnostics(self):
        for length, declaration in ((0, 'let values: List<Integer> = []'),
                                    (2, 'let values = [7, 8]')):
            for index in (-9223372036854775808, -1, length, 9223372036854775807):
                for operation in (f'print(values[{index}])', f'values[{index}] = 42'):
                    with self.subTest(length=length, index=index, operation=operation):
                        result, llvm = self.compile(declaration + '\n' + operation + '\n')
                        self.assertEqual(result.returncode, 0, result.stderr)
                        for optimization in ('-O0', '-O2'):
                            executable = llvm.with_suffix('.' + optimization[1:])
                            linked = subprocess.run(clang_command([CLANG, optimization, *LINK_FLAGS,
                                '-Wno-override-module', str(llvm), str(RUNTIME), '-o', str(executable)]),
                                capture_output=True, text=True, timeout=30)
                            self.assertEqual(linked.returncode, 0, linked.stderr)
                            run = subprocess.run([str(executable)], capture_output=True,
                                                 text=True, timeout=RUN_TIMEOUT)
                            self.assertEqual(run.returncode, 1, run.stderr)
                            self.assertEqual(run.stdout, '')
                            self.assertIn(f'List position {index} is outside its length of {length}.',
                                          run.stderr)

    def test_growth_during_index_and_rhs_reloads_storage_and_length(self):
        self.executes('''function grow(values: List<Integer>, count: Integer): Integer {
let position = 0
while position < count { values.add(position); position += 1 }
return 0
}
function replacement(values: List<Integer>): Integer {
let ignored = grow(values, 2048)
return values.length
}
let values = [7]
let alias = values
values[grow(alias, 2048)] = replacement(alias)
print(values[0])
print(values.length)
print(alias.length)
''', '4097\n4097\n4097\n')

    def test_receiver_is_captured_before_index_and_rhs_replace_its_owner(self):
        self.executes('''record Holder { values: List<Integer> }
function index(holder: Holder): Integer { holder.values = [6]; return 0 }
function replacement(holder: Holder): Integer { holder.values = [7]; return 99 }
let holder = Holder { values: [5] }
let alias = holder.values
holder.values[index(holder)] = replacement(holder)
print(alias[0])
print(holder.values[0])
let lonely = Holder { values: [8] }
lonely.values[index(lonely)] = replacement(lonely)
print(lonely.values[0])
''', '99\n7\n7\n')

    def test_reference_read_survives_replacement_and_growth_during_compound_rhs(self):
        llvm = self.executes('''function replace(values: List<Text>): Text {
values[0] = Text(456)
let position = 0
while position < 512 { values.add(Text(position)); position += 1 }
return "-suffix"
}
let values = [Text(123)]
values[0] += replace(values)
print(values[0])
print(values.length)
''', '123-suffix\n513\n')
        main = llvm.read_text().split('define i32 @main(', 1)[1]
        self.assertNotIn('call void @.minyar.list.set.scalar.checked(', main)
        self.assertIn('call void @minyar_list_set_take(', main)


if __name__ == '__main__':
    unittest.main()
