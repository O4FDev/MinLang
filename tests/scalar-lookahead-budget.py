#!/usr/bin/env python3
"""Count scalar proof attempts, including rejected candidates."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from regressions import CLANG, COMPILER, ROOT, RUNTIME, LINK_FLAGS

MARKER = 'scalar proof attempt'


class ScalarLookaheadBudget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='minyar-lookahead-proof-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        source = (COMPILER.parent.parent / 'src/compiler.min').read_text()
        begin = source.index('function prepareScalarRecord(')
        end = source.index('\nfunction rootLocal(', begin)
        helper = source[begin:end]
        before = '    let cursor: List<Integer> = []'
        assert helper.count(before) == 1
        helper = helper.replace(before, f'    print("{MARKER}")\n' + before, 1)
        source = source[:begin] + helper + source[end:]
        path = cls.directory / 'instrumented.min'
        path.write_text(source)
        llvm = path.with_suffix('.ll')
        compile_result = subprocess.run([str(COMPILER), str(path), str(llvm)], capture_output=True, text=True, timeout=30)
        assert compile_result.returncode == 0, compile_result.stderr
        cls.compiler = cls.directory / 'instrumented'
        link = subprocess.run([CLANG, '-O1', '-DMINYAR_COMPILER_ARENA', '-Wno-override-module',
            str(llvm), str(ROOT / 'runtime/minyar_runtime.c'), '-o', str(cls.compiler)], capture_output=True, text=True, timeout=60)
        assert link.returncode == 0, link.stderr

    def program(self, fields=1, count=128, functions=1, promoted=0):
        shape = '; '.join(f'f{field}: Integer' for field in range(fields))
        source = f'record Cell {{ {shape} }}\nfunction consume(value: Cell): Integer {{ return ' + ('value.f0' if fields else '1') + ' }\n'
        expected = []
        for fn in range(functions):
            source += f'function work{fn}(): Integer {{\n'
            for n in range(count):
                values = '; '.join(f'f{field}: {n + field}' for field in range(fields))
                source += f'let cell{n} = Cell {{ {values} }}\n'
            terms = [f'cell{n}.f0' if n < promoted else f'consume(cell{n})' for n in range(count)]
            source += 'return ' + ' + '.join(terms) + '\n}\n'
            expected.append(str(sum(range(count)) if fields else count))
        source += ''.join(f'print(work{fn}())\n' for fn in range(functions))
        return source, '\n'.join(expected) + '\n'

    def check_attempts(self, expected_attempts, **options):
        source, expected = self.program(**options)
        path = self.directory / (self.id().split('.')[-1] + '.min')
        path.write_text(source)
        llvm = path.with_suffix('.ll')
        result = subprocess.run([str(self.compiler), str(path), str(llvm)], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [MARKER] * expected_attempts)
        for opt in ('-O0', '-O2'):
            exe = path.with_suffix('.' + opt[1:])
            link = subprocess.run([CLANG, opt, *LINK_FLAGS, '-Wno-override-module', str(llvm), str(RUNTIME), '-o', str(exe)], capture_output=True, text=True, timeout=30)
            self.assertEqual(link.returncode, 0, link.stderr)
            run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(run.stdout, expected)
        return llvm.read_text()

    def test_rejected_small_records_consume_attempt_budget(self):
        self.check_attempts(64)

    def test_field_width_charges_before_rejection(self):
        self.check_attempts(32, fields=2, count=100)

    def test_empty_records_have_nonzero_attempt_cost(self):
        self.check_attempts(64, fields=0, count=100)

    def test_attempt_budget_resets_between_functions(self):
        self.check_attempts(128, count=80, functions=2)

    def test_successes_and_rejections_share_one_budget(self):
        llvm = self.check_attempts(64, promoted=32)
        self.assertEqual(llvm.count('; scalar record '), 32)


if __name__ == '__main__':
    unittest.main()
