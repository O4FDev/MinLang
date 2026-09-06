#!/usr/bin/env python3
"""Ownership budgets, module cache policy identities, and edited delta replay.

Uses prebuilt project tools; all generated sources, states, and native artifacts
are temporary. Direct module replay deliberately bypasses driver cold retries.
"""
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILER = ROOT / 'build/minyarc'
MODULE_COMPILER = ROOT / 'build/minyarc-modules'
DRIVER = ROOT / 'build/minyar-module-build'
BUDGETS = ('1', '2', '8', '9', '32')
INVALID = ('', '0', '000', '-1', '+1', '2x', '9x', '1.0', '１２')


def owners_source(public=False):
    return ''.join(
        ('public ' if public else '') + f'function owners{n}(seed: Integer): Text {{\n' +
        ''.join(f'let value{i} = Text(seed + {i})\n' for i in range(n)) +
        'return ' + ' + '.join(f'value{i}' for i in range(n)) + '\n}\n'
        for n in range(1, 10))


def pack(fields):
    return ''.join(str(len(field)) + '\n' + field for field in fields)


class OwnershipPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='minyar-ownership-policy-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.work = Path(cls.temporary.name)
        cls.runtime_objects = {}

    def run_tool(self, command, success=True):
        command = list(map(str, command))
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode == 0, success,
                         shlex.join(command) + '\n' + result.stdout + result.stderr)
        return result

    def native(self, llvm, budget, expected):
        # Compile each matching system runtime once for the whole test file.
        if budget not in self.runtime_objects:
            wrapper = self.work / f'runtime-{budget}.c'
            wrapper.write_text('#include "minyar_runtime.c"\n' +
                               ('#include "minyar_stack_frames.h"\n' if budget != '1' else ''))
            runtime = wrapper.with_suffix('.o')
            self.run_tool(['clang', '-O1', '-DMINYAR_SYSTEM_HEAP=1',
                           '-DMINYAR_RC_POLL_BUDGET=' + budget, '-iquote', ROOT / 'runtime',
                           '-c', wrapper, '-o', runtime])
            self.runtime_objects[budget] = runtime
        binary = llvm.with_suffix('.program')
        self.run_tool(['clang', '-O1', '-Wno-override-module', llvm,
                       self.runtime_objects[budget], '-o', binary])
        result = self.run_tool([binary])
        self.assertEqual((result.stdout, result.stderr), (expected, ''))

    def selected(self, llvm, budget, modules=False):
        pattern = (r'^define .*? @"minyar.module\|(owners\d+)\|[^\n]+ noinline \{'
                   if modules else r'^define .*? @(owners\d+)\([^\n]*\) noinline \{')
        actual = set(re.findall(pattern, llvm.read_text(), re.M))
        limit = 0 if budget is None else min(8, int(budget) - 1)
        self.assertEqual(actual, {f'owners{n}' for n in range(1, limit + 1)})
        for function in actual:
            body_pattern = (r'^define [^\n]* @"minyar.module\|' + function + r'\|[^\n]+ noinline \{\n.*?^\}'
                            if modules else r'^define [^\n]* @' + function + r'\([^\n]*\) noinline \{\n.*?^\}')
            body = re.search(body_pattern, llvm.read_text(), re.M | re.S)
            self.assertIsNotNone(body)
            self.assertEqual(body.group(0).count('call void @minyar_stack_enter()'), 1)
            self.assertEqual(body.group(0).count('call void @minyar_rc_enter_stack_v1('), 1)
            self.assertNotIn('call void @minyar_rc_enter(i64', body.group(0),
                             'stack ownership must replace, not duplicate, the heap frame')
        caller_name = r'@"minyar.module\|caller\|[^"\n]+"' if modules else r'@caller'
        caller = re.search(r'^define [^\n]* ' + caller_name +
                           r'\([^\n]*\)[^\n]*\{\n.*?^\}', llvm.read_text(), re.M | re.S)
        self.assertIsNotNone(caller, 'calling fixture must be emitted')
        self.assertNotIn('noinline', caller.group(0).splitlines()[0])
        self.assertNotIn('@minyar_rc_enter_stack_v1', caller.group(0))
        self.assertNotIn('@minyar_rc_leave_stack_v1', caller.group(0))
        self.assertIn('@minyar_rc_enter(', caller.group(0))

    def test_ordinary_budget_selection_and_errors(self):
        source = self.work / 'ordinary.min'
        source.write_text(owners_source() +
                          'function caller(seed: Integer): Text { let value = owners8(seed); return value }\n'
                          'print(caller(40000))\n')
        ordinary = self.work / 'ordinary.ll'
        self.run_tool([COMPILER, source, ordinary])
        for budget in (*BUDGETS, '1024', '0002', '9' * 100):
            with self.subTest(budget=budget):
                llvm = self.work / ('budget-' + budget + '.ll')
                self.run_tool([COMPILER, source, llvm, '--bounded-owners', budget])
                self.selected(llvm, budget)
                if budget == '1':
                    self.assertEqual(llvm.read_bytes(), ordinary.read_bytes())
                if budget in BUDGETS:
                    self.native(llvm, budget, ''.join(str(40000 + i) for i in range(8)) + '\n')
        # Both frontends must reject malformed budgets before writing output.
        for compiler in (COMPILER, MODULE_COMPILER):
            for index, budget in enumerate(INVALID):
                with self.subTest(compiler=compiler.name, invalid=budget):
                    llvm = self.work / f'invalid-{compiler.name}-{index}.ll'
                    result = self.run_tool([compiler, source, llvm, '--bounded-owners', budget], False)
                    self.assertIn('cleanup budget must be a positive decimal integer',
                                  result.stdout + result.stderr)
                self.assertFalse(llvm.exists())

    def test_loop_backedges_service_debt_only_in_ownership_functions(self):
        source = self.work / 'loop-service.min'
        source.write_text('''function owned(count: Integer): Integer {
 let text = Text(count)
 let position = 0
 while position < count { position = position + 1 }
 print(text)
 return position
}
function scalar(count: Integer): Integer {
 let position = 0
 while position < count { position = position + 1 }
 return position
}
print(owned(3))
print(scalar(3))
''')
        llvm = self.work / 'loop-service.ll'
        self.run_tool([COMPILER, source, llvm])
        generated = llvm.read_text()
        owned = re.search(r'^define [^\n]* @owned\([^\n]*\)[^\n]*\{\n.*?^\}', generated, re.M | re.S)
        scalar = re.search(r'^define [^\n]* @scalar\([^\n]*\)[^\n]*\{\n.*?^\}', generated, re.M | re.S)
        self.assertIsNotNone(owned)
        self.assertIsNotNone(scalar)
        self.assertIn('@minyar_rc_step()', owned.group(0))
        self.assertNotIn('@minyar_rc_step()', scalar.group(0))

    def test_module_policy_transitions_and_native_output(self):
        directory = self.work / 'policy'
        directory.mkdir()
        (directory / 'owners.min').write_text(owners_source(public=True))
        entry = directory / 'main.min'
        entry.write_text('use "./owners.min" as owners\n'
                         'function caller(seed: Integer): Text { let value = owners.owners8(seed); return value }\n'
                         'print(caller(40000))\n' +
                         ''.join(f'print(owners.owners{n}(40000))\n' for n in range(1, 10)))
        state = directory / 'empty'
        state.write_text('')
        sequence = [('ordinary-cold', None, 0), ('ordinary-warm', None, 2),
                    ('k1', '1', 2), ('k2', '2', 0), ('k2-warm', '2', 2),
                    ('k8', '8', 0), ('k9', '9', 0), ('k32', '32', 2),
                    ('ordinary-return', None, 0)]
        expected = ''.join(''.join(str(40000 + i) for i in range(n)) + '\n'
                           for n in [8, *range(1, 10)])
        ordinary = None
        for label, budget, reused in sequence:
            llvm, newstate, stats = [directory / (label + suffix) for suffix in ('.ll', '.state', '.stats')]
            command = [MODULE_COMPILER, entry, llvm, '--module-state', state, newstate, stats]
            if budget is not None:
                command += ['--bounded-owners', budget]
            self.run_tool(command)
            self.selected(llvm, budget, modules=True)
            self.assertEqual(list(map(int, stats.read_text().split()[:2])), [reused, 2 - reused], label)
            if ordinary is None:
                ordinary = llvm.read_bytes()
            if label in ('ordinary-warm', 'k1', 'ordinary-return'):
                self.assertEqual(llvm.read_bytes(), ordinary, label)
            if not label.endswith('warm') and label != 'ordinary-return':
                self.native(llvm, budget or '32', expected)
            # Empty state is the no-change marker, not a replacement cache.
            if newstate.stat().st_size:
                state = newstate

    def test_source_edit_delta_direct_and_driver(self):
        for budget in BUDGETS:
            with self.subTest(budget=budget):
                directory = self.work / ('delta-' + budget)
                directory.mkdir()
                library, entry, empty = [directory / n for n in ('library.min', 'main.min', 'empty')]
                original = 'public function value(n: Integer): Text { let text = Text(n); return text }\n'
                library.write_text(original)
                entry.write_text('use "./library.min" as lib\nprint(lib.value(40))\n')
                empty.write_text('')
                base, delta, warm, plan = [directory / n for n in ('base', 'delta', 'warm', 'plan')]

                def direct(label, previous, state, expected):
                    llvm, stats = directory / (label + '.ll'), directory / (label + '.stats')
                    self.run_tool([MODULE_COMPILER, entry, llvm, '--module-state', previous,
                                   state, stats, '--bounded-owners', budget])
                    self.assertEqual(list(map(int, stats.read_text().split()[:2])), expected)
                    return llvm

                direct('cold', empty, base, [0, 2])
                library.write_text(original.replace('Text(n)', 'Text(n + 1)'))
                plan.write_text(pack(['minyar-module-plan-v1', str(base), str(empty), 'opaque-test-base-identity']))
                edited = direct('edit', plan, delta, [1, 1])
                self.assertTrue(delta.read_text().startswith(pack(['minyar-module-delta-v2'])))
                plan.write_text(pack(['minyar-module-plan-v1', str(base), str(delta), 'opaque-test-base-identity']))
                replayed = direct('warm', plan, warm, [2, 0])
                self.assertEqual(edited.read_bytes(), replayed.read_bytes())

                # Also exercise public driver forwarding and its persistent overlay.
                library.write_text(original)
                llvm, cache, stats = [directory / n for n in ('driver.ll', 'cache', 'driver.stats')]
                command = [DRIVER, MODULE_COMPILER, entry, llvm, cache, stats, '--bounded-owners', budget]
                for stage, expected in [('cold', [0, 2]), ('edit', [1, 1]), ('warm', [2, 0])]:
                    if stage == 'edit':
                        library.write_text(original.replace('Text(n)', 'Text(n + 1)'))
                    self.run_tool(command)
                    self.assertEqual(list(map(int, stats.read_text().split()[:2])), expected)
                    self.assertFalse(list(cache.glob('invocation.*')))
                    if stage != 'cold':
                        self.assertEqual(llvm.read_bytes(), edited.read_bytes())
                if budget == '32':
                    self.native(llvm, budget, '41\n')
        for index, budget in enumerate(INVALID):
            llvm = self.work / f'driver-invalid-{index}.ll'
            result = self.run_tool([DRIVER, MODULE_COMPILER, entry, llvm, self.work / 'invalid-cache',
                                   '--bounded-owners', budget], False)
            self.assertIn('ownership budget must be a positive ASCII decimal integer', result.stderr)
            self.assertFalse(llvm.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
