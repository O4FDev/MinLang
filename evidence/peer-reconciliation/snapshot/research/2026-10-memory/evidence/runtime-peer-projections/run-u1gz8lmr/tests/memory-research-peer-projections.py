#!/usr/bin/env python3
"""Original Minyar ownership projections from the read-only peer rounds.

Default: shared regression helper, using its compiler/runtime environment.
--matrix: isolated current sources, native system/fixed and generated ASan.
These are coverage additions; they do not presume an existing defect.
"""
import argparse
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

from clang_helpers import clang_command
from regressions import CompilerTestCase, LINK_FLAGS

ROOT = Path(__file__).resolve().parents[1]
OBSERVED = []


class PeerProjections(CompilerTestCase):
    def executes(self, source, expected, status=0):
        llvm = super().executes(source, expected, status)
        headers = re.findall(r'^define[^\n]*', llvm.read_text(), re.M)
        sanitized = sum(' sanitize_address ' in header for header in headers)
        if any('address' in flag for flag in LINK_FLAGS):
            self.assertEqual(sanitized, len(headers))
            self.assertGreater(sanitized, 0)
        OBSERVED.append({'test': self.id(), 'source': source, 'expected_stdout': expected,
                         'linked_optimizations': ['O0', 'O2'],
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


def matrix():
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
    report['scope'] = ('Three original Minyar projections, not peer feature equivalence. '
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
        expected_methods = unittest.defaultTestLoader.loadTestsFromTestCase(PeerProjections).countTestCases()
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
                    '--run-record', str(record)], {**environment, 'MINYAR_TEST_RUNTIME': str(runtime),
                    'MINYAR_TEST_LINK_FLAGS': ' '.join(flags if 'sanitize' in label else [])})
            coverage = json.loads(record.read_text())
            assert coverage['tests_run'] == expected_methods and len(coverage['observed']) == expected_methods
            report['coverage'].append({'configuration': label, **coverage})
            print('PASS ' + label, flush=True)
        report['summary'] = {'test_methods': expected_methods, 'configurations': len(report['coverage']),
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
    args = parser.parse_args()
    if args.matrix:
        matrix()
    else:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PeerProjections))
        if args.run_record:
            args.run_record.write_text(json.dumps({'tests_run': result.testsRun, 'observed': OBSERVED,
                                                  'successful': result.wasSuccessful()}, indent=2) + '\n')
        sys.exit(0 if result.wasSuccessful() else 1)
