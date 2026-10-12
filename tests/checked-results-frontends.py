#!/usr/bin/env python3
"""Checked arithmetic through current module, callback and Result adapters."""
import os
import hashlib
from pathlib import Path
import unittest

import callbacks
from errors_evidence import retain
from regressions import CompilerTestCase, ROOT, LINK_FLAGS
from llvm_sanitizer import prepare_llvm_for_link, address_sanitizer_enabled


class CheckedFrontends(CompilerTestCase):
    compiler_arguments = ('--library', str(ROOT / 'library'))

    def select(self, name):
        suffix = '-sanitize' if address_sanitizer_enabled(LINK_FLAGS) else ''
        self.frontend = Path(os.environ.get('MINYAR_CHECKED_' + name.upper() + '_COMPILER',
                                          ROOT / 'build' / ('minyarc-' + name + suffix))).resolve()
        self.evidence.inputs[str(self.frontend)] = hashlib.sha256(self.frontend.read_bytes()).hexdigest()
        self.evidence.inputs[str(ROOT / 'library/errors.min')] = hashlib.sha256(
            (ROOT / 'library/errors.min').read_bytes()).hexdigest()

    def compile(self, source):
        self.serial += 1
        path = self.directory / f'case{self.serial}.min'
        path.write_text(source)
        llvm = path.with_suffix('.ll')
        result = self.evidence.run([str(self.frontend), str(path), str(llvm), *self.compiler_arguments],
                                  capture_output=True, text=True, timeout=30, phase='compile-checked-frontend')
        if result.returncode == 0:
            prepare_llvm_for_link(llvm, LINK_FLAGS)
        return result, llvm

    def close_evidence(self):
        result = self._outcome.result
        failed = any(test.id() == self.id() or test.id().startswith(self.id() + ' ')
                     for test, _ in result.failures + result.errors)
        retain(self.evidence, failed)

    def test_module_frontend_returns_existing_private_result(self):
        self.select('modules')
        self.executes('''use "errors" as errors
function add(a: Integer, b: Integer): errors.IntegerResult { return errors.checkedAdd(a, b) }
print(errors.integerOk(add(9223372036854775807, 1)))
print(errors.integerValue(add(19, 23)))
''', 'false\n42\n')

    def test_callback_recovers_and_retains_captured_result(self):
        self.select('callbacks')
        callbacks.Callbacks.executes(self, '''use "errors" as errors
function create(saved: errors.IntegerResult): Callback<Integer, Integer> {
    return function(value: Integer): Integer {
        let result = errors.checkedMultiply(value, 10)
        if !errors.integerOk(result) { return errors.integerValue(saved) }
        return errors.integerValue(result)
    }
}
let callback = create(errors.checkedSubtract(100, 58))
print(callback(9223372036854775807))
print(callback(2))
print("still alive")
''', '42\n20\nstill alive\n')

    def test_typed_result_match_and_try_propagate_overflow(self):
        self.select('errors')
        callbacks.Callbacks.executes(self, '''use "errors" as errors
function scale(digits: Integer): Result<Integer, errors.Error> {
    let value = 1
    for i in 0..digits {
        let next = errors.checkedMultiply(value, 10)
        if !errors.integerOk(next) { return Err<Integer, errors.Error>(errors.integerError(next)) }
        value = errors.integerValue(next)
    }
    return Ok<Integer, errors.Error>(value)
}
function propagated(digits: Integer): Result<Integer, errors.Error> {
    let value = try scale(digits)
    return Ok<Integer, errors.Error>(value)
}
match propagated(18) { Ok(value) { print(value) } Err(error) { print(errors.code(error)) } }
match propagated(19) { Ok(value) { print(value) } Err(error) { print(errors.code(error) == errors.overflowCode()) } }
match propagated(2) { Ok(value) { print(value) } Err(error) { print(errors.code(error)) } }
print("still alive")
''', '1000000000000000000\ntrue\n100\nstill alive\n')


if __name__ == '__main__':
    unittest.main()
