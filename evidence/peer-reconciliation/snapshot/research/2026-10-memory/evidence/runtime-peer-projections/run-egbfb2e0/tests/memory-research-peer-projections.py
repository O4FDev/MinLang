#!/usr/bin/env python3
"""Original Minyar ownership projections from the read-only peer rounds.

Default: shared regression helper, using its compiler/runtime environment.
--matrix: isolated current sources, native system/fixed and generated ASan.
These are coverage additions; they do not presume an existing defect.
"""
import argparse
from decimal import Decimal, localcontext
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from clang_helpers import clang_command
from regressions import CompilerTestCase, LINK_FLAGS

ROOT = Path(__file__).resolve().parents[1]
OBSERVED = []


class PeerProjections(CompilerTestCase):
    def executes(self, source, expected, status=0):
        commands = []
        original_run = subprocess.run

        def record_run(*args, **kwargs):
            result = original_run(*args, **kwargs)
            command = [str(value) for value in args[0]]
            optimizations = [flag for flag in command if re.fullmatch(r'-O(?:[0123szg]|fast)', flag)]
            kind = 'link' if '-o' in command and any(value.endswith('.ll') for value in command) else 'compile' if any(value.endswith('.min') for value in command) else 'execute'
            output = result.stdout.encode() if isinstance(result.stdout, str) else result.stdout
            commands.append({'kind': kind, 'argv': command, 'returncode': result.returncode,
                             'effective_last_optimization_flag': optimizations[-1] if optimizations else None,
                             'stdout_sha256': hashlib.sha256(output or b'').hexdigest()})
            return result

        with mock.patch('regressions.subprocess.run', side_effect=record_run):
            llvm = super().executes(source, expected, status)
        headers = re.findall(r'^define[^\n]*', llvm.read_text(), re.M)
        sanitized = sum(' sanitize_address ' in header for header in headers)
        if any('address' in flag for flag in LINK_FLAGS):
            self.assertEqual(sanitized, len(headers))
            self.assertGreater(sanitized, 0)
        OBSERVED.append({'test': self.id(), 'source': source, 'expected_stdout': expected,
                         'linked_optimizations': ['O0', 'O2'],
                         'effective_optimizations': [next((flag[1:] for flag in reversed(LINK_FLAGS)
                                                          if flag.startswith('-O')), requested)
                                                     for requested in ['O0', 'O2']],
                         'commands': commands,
                         'generated_definitions': len(headers),
                         'asan_definitions': sanitized})
        return llvm

    def test_shared_bytes_and_independent_slice_survive_replacement(self):
        self.executes('''function copyAndWrite(source: Bytes): Bytes {
source[1] = 122
let copy = source.slice(2, 3)
copy[0] = 121
return copy
}
let source = Bytes(4)
for i in 0..4 { source[i] = 97 }
let alias = source
let copy = copyAndWrite(source)
for b in source { print(b) }
for b in alias { print(b) }
print(copy[0])
source[2] = 121
for b in alias { print(b) }
source = Bytes()
alias = Bytes()
print(copy.length)
print(copy[0])
''', '97\n122\n97\n97\n97\n122\n97\n97\n121\n97\n122\n121\n97\n1\n121\n')

    def test_shared_row_and_explicit_snapshot_survive_outer_replacement(self):
        self.executes('''let row = [0, 0, 0]
let rows = [row, [4, 5, 6]]
let alias = rows[0]
let snapshot: List<Integer> = []
for value in alias { snapshot.add(value) }
rows[0][1] = 15
print(alias[1])
print(snapshot[1])
print(rows[1][1])
rows[0] = [7, 8, 9]
rows = []
row = []
print(alias[1])
print(snapshot[1])
print(alias.length)
print(snapshot.length)
''', '15\n0\n5\n15\n0\n3\n3\n')

    def test_unused_literal_effects_and_ordered_shared_state(self):
        self.executes('''function touch(state: List<Integer>): Integer {
state[0] = state[0] + 1
return 0
}
function weighted(state: List<Integer>, weight: Integer, digit: Integer): Integer {
state[0] = state[0] + weight
state[1] = state[1] * 10 + digit
return weight
}
let state = [0, 0]
let unused = [touch(state), touch(state)]
print(state[0])
state[0] = 0
let values = [weighted(state, 1, 1), weighted(state, 2, 2), weighted(state, 4, 3), weighted(state, 8, 4)]
for value in values { print(value) }
print(state[0])
print(state[1])
''', '2\n1\n2\n4\n8\n15\n1234\n')

    def test_effectful_iterables_evaluate_once_and_retain_body_storage(self):
        self.executes('''function listSource(state: List<Integer>, empty: Boolean): List<Integer> {
state[0] = state[0] + 1
state[1] = state[1] * 10 + 1
if empty { return [] }
return [1, 2, 3, 4, 5]
}
function byteSource(state: List<Integer>, empty: Boolean): Bytes {
state[0] = state[0] + 1
state[1] = state[1] * 10 + 2
if empty { return Bytes() }
let bytes = Bytes(5)
for i in 0..5 { bytes[i] = i + 1 }
return bytes
}
function textSource(state: List<Integer>, empty: Boolean): Text {
state[0] = state[0] + 1
state[1] = state[1] * 10 + 3
if empty { return "" + "" }
return "abcd" + Text('☺')
}
function body(state: List<Integer>, value: Integer) {
let churn = ["body:" + Text(value), Text(value)]
state[2] = state[2] + 1
state[3] = state[3] + value
state[4] = state[4] + churn[0].length
}
let state = [0, 0, 0, 0, 0]
for value in listSource(state, false) { print(value); body(state, value) }
for value in state { print(value) }
state[2] = 0
state[3] = 0
state[4] = 0
for value in byteSource(state, false) { print(value); body(state, value) }
for value in state { print(value) }
state[2] = 0
state[3] = 0
state[4] = 0
for value in textSource(state, false) { print(Integer(value)); body(state, Integer(value)) }
for value in state { print(value) }
state[2] = 0
state[3] = 0
state[4] = 0
for value in listSource(state, true) { body(state, value) }
for value in byteSource(state, true) { body(state, value) }
for value in textSource(state, true) { body(state, Integer(value)) }
for value in state { print(value) }
''', '\n'.join(str(value) for value in [
            1, 2, 3, 4, 5, 1, 1, 5, 15, 30,
            1, 2, 3, 4, 5, 2, 12, 5, 15, 30,
            97, 98, 99, 100, 9786, 3, 123, 5, 10180, 38,
            6, 123123, 0, 0, 0]) + '\n')

    def test_nan_ordered_comparisons_negation_and_boolean_returns(self):
        operators = [('equal', '==', False), ('unequal', '!=', True),
                     ('less', '<', False), ('greater', '>', False),
                     ('atMost', '<=', False), ('atLeast', '>=', False)]
        source = [f'function {name}(left: Float, right: Float): Boolean {{ return left {operator} right }}'
                  for name, operator, _ in operators]
        source.extend(['let nan = 0.0 / 0.0', 'let one = 1.0'])
        expected = []
        for helper in (False, True):
            for left, right in [('nan', 'nan'), ('one', 'nan'), ('nan', 'one')]:
                for name, operator, answer in operators:
                    expression = f'{name}({left}, {right})' if helper else f'{left} {operator} {right}'
                    source.extend([f'print({expression})', f'print(!({expression}))', f'print(!(!({expression})))'])
                    expected.extend(['true' if value else 'false' for value in [answer, not answer, answer]])
        source.extend(['print(less(1.0, 2.0))', 'print(!less(1.0, 2.0))',
                       '''function left(state: List<Integer>): Float {
state[0] = state[0] * 10 + 1
return 0.0 / 0.0
}
function right(state: List<Integer>): Float {
state[0] = state[0] * 10 + 2
return 1.0
}
let state = [0]
print(left(state) < right(state))
print(state[0])'''])
        expected.extend(['true', 'false', 'false', '12'])
        self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')

    def test_source_underflow_and_signed_zero_have_exact_binary64_bits(self):
        # Exact decimal arithmetic certifies these are opposite sides of the
        # half-minimum boundary; neither expected result relies on Float print.
        with localcontext() as context:
            context.prec = 1100
            half_minimum = Decimal(2) ** -1075
            self.assertLess(Decimal('2.4703282292062327e-324'), half_minimum)
            self.assertGreater(Decimal('2.4703282292062328e-324'), half_minimum)
        literals = ['2.4703282292062327e-324', '2.4703282292062328e-324',
                    '-2.4703282292062327e-324', '-2.4703282292062328e-324',
                    '0.0e123', '-0.0e123']
        expected_bits = [0, 1, -9223372036854775808, -9223372036854775807,
                         0, -9223372036854775808]
        source = [f'function value{index}(): Float {{ return {literal} }}'
                  for index, literal in enumerate(literals)]
        source.append('let bytes = Bytes()')
        source.extend(f'bytes.addFloat64({literal})' for literal in literals)
        source.extend(f'bytes.addFloat64(value{index}())' for index in range(len(literals)))
        source.extend(f'print(bytes.getInt64({offset * 8}))' for offset in range(2 * len(literals)))
        self.executes('\n'.join(source) + '\n', '\n'.join(str(value) for value in expected_bits * 2) + '\n')

    def test_middle_boolean_literal_preserves_all_prior_effects(self):
        self.executes('''function observe(events: List<Integer>, id: Integer, result: Boolean): Boolean {
events.add(id)
return result
}
function decisive(events: List<Integer>, result: Boolean): Boolean {
let temporary = Text(3) + "!"
events.add(3)
if temporary.length != 2 { fail("the decisive helper lost its temporary") }
return result
}
let events: List<Integer> = []
print(observe(events, 1, true) && observe(events, 2, true) && false && observe(events, 9, true))
print(events.length)
for id in events { print(id) }
events = []
print(observe(events, 1, true) && observe(events, 2, true) && decisive(events, false) && observe(events, 9, true))
print(events.length)
for id in events { print(id) }
events = []
print(observe(events, 1, false) || observe(events, 2, false) || true || observe(events, 9, false))
print(events.length)
for id in events { print(id) }
events = []
print(observe(events, 1, false) || observe(events, 2, false) || decisive(events, true) || observe(events, 9, false))
print(events.length)
for id in events { print(id) }
''', 'false\n2\n1\n2\nfalse\n3\n1\n2\n3\ntrue\n2\n1\n2\ntrue\n3\n1\n2\n3\n')

    def test_binary64_halfway_even_addition_at_unit_spacing_boundary(self):
        # At 2^53, adjacent binary64 values differ by 2. The halfway +1
        # rounds to the even endpoint; +2 reaches the next value. The bit
        # constants are explicit independent expectations, not helper equality.
        self.executes('''function add(left: Float, right: Float): Float {
return left + right
}
let x = 9007199254740992.0
print(x + 1.0 == x)
print(x + 2.0 == 9007199254740994.0)
print((x + 2.0) - x)
print(add(x, 1.0) == x)
print(add(x, 2.0) == 9007199254740994.0)
print(add(x, 2.0) - x)
let bits = Bytes()
bits.addFloat64(x + 1.0)
bits.addFloat64(x + 2.0)
bits.addFloat64(add(x, 1.0))
bits.addFloat64(add(x, 2.0))
for i in 0..4 { print(bits.getInt64(i * 8)) }
''', 'true\ntrue\n2.0\ntrue\ntrue\n2.0\n4845873199050653696\n4845873199050653697\n4845873199050653696\n4845873199050653697\n')


    def test_wide_returned_record_preserves_fields_effect_order_and_retained_alias(self):
        # Slot positions, source-order effects, and scalar snapshots have
        # independent expected values; no Swift struct-copy rule is asserted.
        self.executes('''record Wide { a: Integer; b: Integer; c: Integer; d: Integer; e: Integer; f: Integer; g: Integer; h: Integer }
function initial(): Wide {
return Wide { a: 1; b: 2; c: 3; d: 4; e: 5; f: 6; g: 7; h: 8 }
}
function show(value: Wide) {
print(value.a); print(value.b); print(value.c); print(value.d)
print(value.e); print(value.f); print(value.g); print(value.h)
}
function mark(trace: List<Integer>, digit: Integer): Integer {
trace[0] = trace[0] * 10 + digit
return digit * 11
}
function make(trace: List<Integer>): Wide {
return Wide {
h: mark(trace, 8); g: mark(trace, 7); f: mark(trace, 6); e: mark(trace, 5)
d: mark(trace, 4); c: mark(trace, 3); b: mark(trace, 2); a: mark(trace, 1)
}
}
function echo(value: Wide): Wide { return value }
show(initial())
let trace = [0]
let holder = [make(trace)]
let kept = echo(holder[0])
let scalar = kept.a
show(kept)
print(trace[0])
holder[0].a = 111
print(kept.a)
print(scalar)
holder[0] = initial()
holder = []
for i in 0..8 { let temporary = initial(); print(temporary.h) }
show(kept)
''', '\n'.join(str(value) for value in [
            *range(1, 9), *[11 * digit for digit in range(1, 9)],
            87654321, 111, 11, *([8] * 8), 111,
            *[11 * digit for digit in range(2, 9)]]) + '\n')


    def test_text_equality_after_nul_at_every_short_mismatch_position(self):
        sizes = [*range(18), 31, 32, 33]
        source = '''function build(size: Integer, changed: Integer): Text {
let result = ""
for position in 0..size {
let code = 65
if position == size / 2 { code = 0 }
if position == changed { code = 66 }
result = result + Text(Character(code))
}
return result
}
let sizes = [''' + ', '.join(map(str, sizes)) + ''']
for size in sizes {
let left = build(size, -1)
let right = build(size, -1)
print(left == right)
print(left != right)
print(left.length)
print(left.byteLength)
print(left == right + "C")
for position in 0..size {
print(left == build(size, position))
print(left != build(size, position))
}
}
let zero = Text(Character(0))
let left = "é" + zero + "🙂"
let equal = Text(Character(233)) + zero + Text(Character(128578))
let different = "é" + zero + "🙃"
print(left == equal)
print(left != equal)
print(left == different)
print(left != different)
print(left.length)
print(left.byteLength)
print(Integer(left[1]))
print(left.slice(1, 3) == zero + "🙂")
'''
        expected = []
        for size in sizes:
            # ASCII including NUL has exactly one byte/scalar per position.
            # Every replacement is B, different from either A or the NUL.
            expected.extend(['true', 'false', str(size), str(size), 'false'])
            expected.extend(['false', 'true'] * size)
        expected.extend(['true', 'false', 'false', 'true', '3', '7', '0', 'true'])
        self.executes(source, '\n'.join(expected) + '\n')

    def test_scalar_loop_capture_survives_mutation_continue_and_break(self):
        self.executes('''let source = [4, 7, 9, 13]
let alias = source
let position = 0
let visits = 0
let tail = 0
let captured = 0
let rebound = 0
let trace = 0
let allocated = 0
for value in source {
let index = position
position += 1
visits += 1
trace = trace * 10 + index + 1
source[index] += 100
captured = captured * 100 + value
value = 900 + index
rebound += value
let pieces = ["Q", "R", "S"]
allocated += joinText(pieces).length
if index == 0 { continue }
if index == 2 { break }
tail += 1
}
print(captured)
print(visits)
print(position)
print(tail)
print(rebound)
print(trace)
print(allocated)
source = []
for value in alias { print(value) }
''', '\n'.join(map(str, [40709, 3, 3, 1, 2703, 123, 9, 104, 107, 109, 13])) + '\n')


def matrix(test_name=None):
    parent = ROOT / 'build/memory-research-peer-projections'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent))
    report = {'status': 'running', 'checks': [], 'sources': [], 'coverage': []}
    for directory, names in [('runtime', [p.name for p in (ROOT / 'runtime').glob('minyar_*') if p.is_file()]),
                             ('tests', [Path(__file__).name, 'regressions.py', 'clang_helpers.py', 'llvm_sanitizer.py'])]:
        for name in names:
            source = ROOT / directory / name
            target = evidence / directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            report['sources'].append({'source': str(source), 'snapshot': str(target.relative_to(evidence)),
                                      'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    compiler = evidence / 'minyarc'
    shutil.copy2(ROOT / 'build/minyarc', compiler)
    report['compiler_sha256'] = hashlib.sha256(compiler.read_bytes()).hexdigest()
    report['scope'] = ('Original Minyar projections, not peer feature equivalence. '
                       'Generated ASan and runtime C ASan/UBSan; no generated UBSan or LSan claim. No timing claim.')
    environment = {**os.environ, 'MINYAR_TEST_COMPILER': str(compiler),
                   'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1',
                   'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}

    def save():
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    def execute(label, command, env):
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=90)
        report['checks'].append({'label': label, 'command': command, 'returncode': result.returncode,
                                 'stdout': result.stdout, 'stderr': result.stderr})
        save()
        assert result.returncode == 0, (label, result.stderr)

    print('Evidence: ' + str(evidence), flush=True)
    try:
        expected_methods = 1 if test_name else unittest.defaultTestLoader.loadTestsFromTestCase(PeerProjections).countTestCases()
        for label, defines, flags in [
            ('system-k32', ['-DMINYAR_SYSTEM_HEAP=1', '-DMINYAR_RC_POLL_BUDGET=32'], ['-O2']),
            ('fixed-k1', ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_BOUNDED_HEAP_BYTES=8388608', '-DMINYAR_RC_POLL_BUDGET=1'], ['-O2']),
            ('system-k32-sanitize', ['-DMINYAR_SYSTEM_HEAP=1', '-DMINYAR_RC_POLL_BUDGET=32'],
             ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer'])]:
            runtime = evidence / (label + '.o')
            execute(label + '-runtime', clang_command(['clang', *flags, *defines, '-c',
                    str(evidence / 'runtime/minyar_runtime.c'), '-o', str(runtime)]), environment)
            record = evidence / (label + '-coverage.json')
            execute(label + '-tests', [sys.executable, str(evidence / 'tests' / Path(__file__).name),
                    '--run-record', str(record), *(['--test-name', test_name] if test_name else [])], {**environment, 'MINYAR_TEST_RUNTIME': str(runtime),
                    'MINYAR_TEST_LINK_FLAGS': ' '.join(flag for flag in flags
                                                     if 'sanitize' in label and not flag.startswith('-O'))})
            coverage = json.loads(record.read_text())
            assert coverage['tests_run'] == expected_methods and len(coverage['observed']) == expected_methods
            assert all(case['effective_optimizations'] == ['O0', 'O2'] for case in coverage['observed'])
            assert all([command['effective_last_optimization_flag'] for command in case['commands']
                        if command['kind'] == 'link'] == ['-O0', '-O2'] for case in coverage['observed'])
            report['coverage'].append({'configuration': label, **coverage})
            print('PASS ' + label, flush=True)
        report['summary'] = {'test_methods': expected_methods, 'configurations': len(report['coverage']),
                             'selected_test_name': test_name,
                             'generated_executions': sum(len(case['linked_optimizations'])
                                                        for run in report['coverage'] for case in run['observed'])}
        report['status'] = 'passed'
    except Exception as error:
        report['status'] = 'failed'
        report['failure'] = str(error)
        raise
    finally:
        save()
        print('Results: ' + str(evidence / 'results.json'), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--matrix', action='store_true')
    parser.add_argument('--run-record', type=Path)
    parser.add_argument('--test-name', help='Run only one named original method, also in the matrix.')
    args = parser.parse_args()
    if args.test_name and (not args.test_name.startswith('test_') or not hasattr(PeerProjections, args.test_name)):
        parser.error('Unknown test method')
    if args.matrix:
        matrix(args.test_name)
    else:
        suite = (unittest.TestSuite([PeerProjections(args.test_name)]) if args.test_name else
                 unittest.defaultTestLoader.loadTestsFromTestCase(PeerProjections))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        if args.run_record:
            args.run_record.write_text(json.dumps({'tests_run': result.testsRun, 'observed': OBSERVED,
                                                  'successful': result.wasSuccessful()}, indent=2) + '\n')
        sys.exit(0 if result.wasSuccessful() else 1)
