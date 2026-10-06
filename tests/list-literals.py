#!/usr/bin/env python3
"""Constant List lowering: value semantics, effects, diagnostics and module identity."""
from clang_helpers import clang_command
import os
from pathlib import Path
import re
import unittest
from regressions import CompilerTestCase, ROOT, CLANG, RUNTIME, LINK_FLAGS
from llvm_sanitizer import prepare_llvm_for_link
from test_evidence import digest

MODULE_COMPILER = Path(os.environ.get('MINYAR_TEST_MODULE_COMPILER', ROOT / 'build/minyarc-modules')).resolve()


class ListLiterals(CompilerTestCase):
    def test_fresh_storage_signed_limits_and_nested_owners(self):
        self.executes('''record Box { values: List<Integer> }
function make(): List<Integer> { return [-9223372036854775808, -0002, 0, 9223372036854775807] }
let first = make()
let alias = first
let second = make()
alias[0] = 99
print(first[0])
print(second[0])
print(second[1])
print(second[3])
let boxes = [Box { values: [10, 11] }, Box { values: [20, 21] }]
let nested = [[1, 2], [3, 4]]
let boxValues = boxes[0].values
let inner = nested[0]
boxValues[0] = 42
inner[0] = 8
print(boxes[0].values[0])
print(nested[0][0])
print(boxes[1].values[0])
print(nested[1][0])
let pass = 0
while pass < 2 {
let local = [5, 6]
print(local[0])
local[0] = 0
pass = pass + 1
}
''', '99\n-9223372036854775808\n-2\n9223372036854775807\n42\n8\n20\n3\n5\n5\n')

    def test_constants_flush_before_dynamic_effects(self):
        llvm = self.executes('''function observe(value: Integer): Integer { print(value); return value }
let values = [1, 2, observe(3), 4, 5, observe(6), -7, 8]
let i = 0
while i < values.length { print(values[i]); i = i + 1 }
let folded = [10, 20, 1 + observe(2), (4), 5 * 2, -3 + 1]
print(folded[2])
print(folded[3])
print(folded[4])
print(folded[5])
''', '3\n6\n1\n2\n3\n4\n5\n6\n-7\n8\n2\n3\n4\n10\n-2\n')
        main = llvm.read_text().split('define i32 @main(', 1)[1]
        # An effectful expression must not move ahead of its preceding run.
        self.assertLess(main.index('call void @minyar_list_append_scalars'), main.index('call i64 @.minyar.fn.observe'))
        self.executes('''function stop(): Integer { fail("literal stop") }
function later(): Integer { print(999); return 9 }
let values = [1, 2, stop(), 3, 4, later()]
print(values.length)
''', '', status=1, stderr='Minyar stopped: literal stop\n')

    def test_user_functions_cannot_interpose_runtime_or_system_symbols(self):
        names = ('minyar_list_append_scalars', 'minyar_list_new', 'minyar_rc_enter',
                 'malloc', 'realloc', 'free', 'memcpy', 'printf')
        source = ''.join(f'function {name}(): Integer {{ return {i} }}\n' for i, name in enumerate(names))
        source += 'let values = [1, 2, 3]\nvalues.add(4)\nprint(values.length)\n'
        source += ''.join(f'print({name}())\n' for name in names)
        self.executes(source, '4\n' + ''.join(f'{i}\n' for i in range(len(names))))

    def test_empty_singleton_comments_and_type_errors(self):
        self.executes('''let empty: List<Integer> = []
let one = [-0]
let pair = [1 // first
, // separator
2,
]
print(empty.length)
print(one[0])
print(pair[1])
''', '0\n0\n2\n')
        for source, message in (
            ('let a = [1, 9223372036854775808]', 'Integer literal is outside the supported range'),
            ('let a = [1, -9223372036854775809]', 'Integer literal is outside the supported range'),
            ('let a = [1, 2, true]', 'all values in a List literal must have the same type'),
            ('let a: List<Boolean> = [1, 2]', 'all values in a List literal must have the same type'),
            ('let a = [1, 2 3]', "expected ','"),
            ('let a = [1, 2', "expected ','"),
        ):
            with self.subTest(source=source): self.rejects(source, message)

    def test_large_literal_has_bounded_instruction_count(self):
        count = 16384
        source = 'let values = [' + ','.join(map(str, range(count))) + ']\n'
        source += 'let i = 0\nwhile i < values.length { if values[i] != i { fail("literal position") }; i = i + 1 }\nprint(i)\n'
        llvm = self.executes(source, f'{count}\n')
        ir = llvm.read_text()
        self.assertEqual(ir.count('call void @minyar_list_append_scalars('), 1)
        self.assertNotIn('call void @minyar_list_add(', ir)
        self.assertRegex(ir, rf'private unnamed_addr constant \[{count} x i64\]')
        # Shared runtime helpers can grow without changing literal lowering.
        main = ir.split('define i32 @main(', 1)[1].split('\n}', 1)[0]
        self.assertLess(len(re.findall(r'^  (?:%[^=]+ = |(?:call|br|ret) )', main, re.M)), 100)

    def test_module_literal_names_and_cached_fragments(self):
        self.evidence.inputs[str(MODULE_COMPILER)] = digest(MODULE_COMPILER)
        # Identical token positions in two modules must have distinct globals.
        for name, values in (('first', '1, 2, 3'), ('second', '4, 5, 6')):
            (self.directory / f'{name}.min').write_text(f'public function make(): List<Integer> {{ return [{values}] }}\n')
        entry = self.directory / 'main.min'
        entry.write_text('''use "./first.min" as first
use "./second.min" as second
let a = first.make()
let b = first.make()
a[0] = 99
print(a[0])
print(b[0])
print(second.make()[0])
''')
        empty = self.directory / 'empty'; empty.write_text('')
        state = self.directory / 'state'
        prior = empty
        for iteration in range(2):
            llvm = self.directory / f'modules-{iteration}.ll'
            next_state = self.directory / f'state-{iteration}'
            stats = self.directory / f'stats-{iteration}'
            result = self.evidence.run([str(MODULE_COMPILER), str(entry), str(llvm), '--module-state', str(prior), str(next_state), str(stats)], capture_output=True, text=True, timeout=30, phase='compile-module')
            self.assertEqual(result.returncode, 0, result.stderr)
            ir = llvm.read_text()
            declarations = re.findall(r'^(@[^\n]+?) = private unnamed_addr constant \[3 x i64\]', ir, re.M)
            self.assertEqual(len(set(declarations)), 2)
            prepare_llvm_for_link(llvm, LINK_FLAGS)
            for opt in ('-O0', '-O2'):
                exe = llvm.with_suffix('.' + opt[1:])
                result = self.evidence.run(clang_command([CLANG, opt, *LINK_FLAGS, '-Wno-override-module', str(llvm), str(RUNTIME), '-o', str(exe)]), capture_output=True, timeout=30, phase='link')
                self.assertEqual(result.returncode, 0, result.stderr)
                result = self.evidence.run([str(exe)], capture_output=True, timeout=30, phase='execute')
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'99\n1\n4\n', b''))
            if iteration == 0:
                state.write_bytes(next_state.read_bytes()); prior = state
            else:
                self.assertEqual(stats.read_text().split()[:2], ['3', '0'])


if __name__ == '__main__': unittest.main(verbosity=2)
