#!/usr/bin/env python3
"""Parallel signatures stay scalar even when managed arguments are unused.

Use MINYAR_TEST_COMPILER to exercise the maintained or optional frontend.
MINYAR_PARALLEL_IR_RECORD records accepted LLVM once; MINYAR_PARALLEL_IR_CONTROL
compares a subsequent compiler with those immutable outputs. Fixture paths stay
constant between observations, including imported-module identity.
MINYAR_PARALLEL_OBSERVATIONS retains each raw compiler outcome before cleanup.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import unittest

from regressions import COMPILER, COMPILE_TIMEOUT, ROOT, CompilerTestCase

FIXTURES = ROOT / 'tests/parallel-signatures'
DIAGNOSTIC = "may use only Integer, Float, Boolean and Character values"
REJECTIONS = {
    **{f'unused-{kind}{suffix}': 'bad' for kind in ('text', 'bytes', 'list', 'record')
       for suffix in ('', '-entry')},
    'managed-after-scalars': 'bad',
    'managed-parameter-65': 'bad',
    'managed-implicit-nothing': 'bad',
    'parallel-native-bytes': 'address',
    **{f'return-{kind}': 'bad' for kind in ('text', 'bytes', 'list', 'record')},
}
LEGACY_REJECTIONS = {
    'reference': "parallel function 'bad' " + DIAGNOSTIC,
    'call': "parallel function 'bad' can only call parallel functions, not 'ordinary'",
    'entry': "parallelEntry needs a parallel function, and 'ordinary' is not one",
}
ACCEPTANCES = {
    'scalar-values': ('scalarInteger', 'scalarFloat', 'scalarBoolean',
                      'scalarCharacter', 'scalarNothing'),
    'scalar-native': ('fence',),
    'ordinary-managed': (),
    'ordinary-native': (),
    'existing-parallel': ('square', 'next'),
}


class ParallelSignatures(CompilerTestCase):
    def setUp(self):
        super().setUp()
        self.ir_record = os.environ.get('MINYAR_PARALLEL_IR_RECORD')
        self.ir_control = os.environ.get('MINYAR_PARALLEL_IR_CONTROL')
        if self.ir_record and self.ir_control:
            raise ValueError('record and control modes are mutually exclusive')
        self.evidence.inputs[str(ROOT / 'build/compiler.min')] = hashlib.sha256(
            (ROOT / 'build/compiler.min').read_bytes()).hexdigest()

    def compile_fixture(self, name):
        if name == 'existing-parallel':
            source = ROOT / 'tests/parallel/main.min'
        elif name.startswith('legacy-'):
            source = ROOT / 'tests/parallel/errors' / (name[7:] + '.min')
        else:
            source = FIXTURES / (name + '.min')
        self.evidence.inputs[str(source)] = hashlib.sha256(source.read_bytes()).hexdigest()
        self.evidence.controls['fixture'] = name
        llvm = self.directory / (name + '.ll')
        result = self.evidence.run(
            [str(COMPILER), str(source), str(llvm), '--library', str(ROOT / 'library')],
            capture_output=True, text=True, timeout=COMPILE_TIMEOUT,
            phase='compile-parallel-signature')
        self.evidence.controls['compile_status'] = result.returncode
        observations = os.environ.get('MINYAR_PARALLEL_OBSERVATIONS')
        if observations:
            directory = Path(observations) / name
            directory.mkdir(parents=True, exist_ok=False)
            files = {'source.min': source.read_bytes(),
                     'stdout': result.stdout.encode('utf-8'),
                     'stderr': result.stderr.encode('utf-8')}
            if llvm.exists():
                files['output.ll'] = llvm.read_bytes()
            for filename, content in files.items():
                with (directory / filename).open('xb') as stream:
                    stream.write(content)
            manifest = {'inputs': self.evidence.inputs,
                        'controls': self.evidence.controls,
                        'commands': self.evidence.commands,
                        'files': {filename: hashlib.sha256(content).hexdigest()
                                  for filename, content in files.items()}}
            with (directory / 'observation.json').open('x') as stream:
                json.dump(manifest, stream, indent=2, sort_keys=True)
                stream.write('\n')
        return result, llvm

    def reject_fixture(self, name, function):
        self.reject_diagnostic(name, "parallel function '" + function + "' " + DIAGNOSTIC)

    def reject_diagnostic(self, name, diagnostic):
        result, llvm = self.compile_fixture(name)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(result.stdout, 'rejected signature wrote standard output')
        self.assertIn(diagnostic, result.stderr)
        self.assertFalse(llvm.exists(), 'rejected signature left LLVM output')
        self.assertNotIn('List position', result.stderr)

    def accept_fixture(self, name, parallel_functions):
        result, llvm = self.compile_fixture(name)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(result.stdout)
        self.assertFalse(result.stderr)
        emitted = llvm.read_bytes()
        self.evidence.controls['llvm_sha256'] = hashlib.sha256(emitted).hexdigest()
        text = emitted.decode('utf-8')
        for function in parallel_functions:
            match = re.search(
                r'define [^\n]*@\.minyar\.fn\.(?:minyar_module_[0-9]+_)?'
                + re.escape(function)
                + r'\([^\n]*\)[^\n]*\{\n(.*?)\n\}', text, re.S)
            self.assertIsNotNone(match, 'missing parallel function ' + function)
            self.assertNotIn('@minyar_rc_', match.group(1))
            self.assertNotIn('@minyar_stack_', match.group(1))
        if self.ir_record:
            directory = Path(self.ir_record)
            directory.mkdir(parents=True, exist_ok=True)
            recorded = directory / (name + '.ll')
            with recorded.open('xb') as stream:
                stream.write(emitted)
            self.evidence.controls['recorded_ir'] = str(recorded)
        if self.ir_control:
            control = Path(self.ir_control) / (name + '.ll')
            self.evidence.inputs[str(control)] = hashlib.sha256(control.read_bytes()).hexdigest()
            self.assertEqual(emitted, control.read_bytes(),
                             'accepted program LLVM changed: ' + name)


def rejection(name, function):
    def test(self):
        self.reject_fixture(name, function)
    return test


def legacy_rejection(name, diagnostic):
    def test(self):
        self.reject_diagnostic('legacy-' + name, diagnostic)
    return test


def acceptance(name, functions):
    def test(self):
        self.accept_fixture(name, functions)
    return test


for name, function in REJECTIONS.items():
    setattr(ParallelSignatures, 'test_reject_' + name.replace('-', '_'),
            rejection(name, function))
for name, diagnostic in LEGACY_REJECTIONS.items():
    setattr(ParallelSignatures, 'test_legacy_' + name,
            legacy_rejection(name, diagnostic))
for name, functions in ACCEPTANCES.items():
    setattr(ParallelSignatures, 'test_accept_' + name.replace('-', '_'),
            acceptance(name, functions))

if __name__ == '__main__':
    unittest.main()
