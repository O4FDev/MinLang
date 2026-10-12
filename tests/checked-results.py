#!/usr/bin/env python3
"""G15 recovery and signed arithmetic against Python's unbounded integers."""
import hashlib
import math
import random
import re
import unittest

from errors_evidence import retain
from regressions import CompilerTestCase, ROOT


class CheckedResults(CompilerTestCase):
    compiler_arguments = ('--library', str(ROOT / 'library'))

    def setUp(self):
        super().setUp()
        for path in (ROOT / 'library/errors.min',
                     ROOT / 'tests/fixtures/g15-overflow-recovery.min',
                     ROOT / 'tests/fixtures/g15-overflow-trap.min'):
            self.evidence.inputs[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()

    def close_evidence(self):
        result = self._outcome.result
        failed = any(test.id() == self.id() or test.id().startswith(self.id() + ' ')
                     for test, _ in result.failures + result.errors)
        retain(self.evidence, failed)

    def test_g15_scale_failure_recovers(self):
        self.executes((ROOT / 'tests/fixtures/g15-overflow-recovery.min').read_text(),
                      '1000000000000000000\nfalse\ntrue\n100\nstill alive\n')

    def test_original_g15_trap_is_unchanged(self):
        self.executes((ROOT / 'tests/fixtures/g15-overflow-trap.min').read_text(),
                      '1000000000000000000\n', status=1,
                      stderr='Minyar stopped: this Integer calculation is outside the supported range.\n')

    def test_signed_boundaries_and_random_pairs_against_python(self):
        low, high = -(1 << 63), (1 << 63) - 1
        root = math.isqrt(high)
        boundaries = (low, low + 1, -root - 1, -root, -2, -1, 0, 1, 2,
                      root, root + 1, high - 1, high)
        pairs = [(a, b) for a in boundaries for b in boundaries]
        rng = random.Random(15102026)
        pairs += [(rng.randrange(low, high + 1), rng.randrange(low, high + 1))
                  for _ in range(128)]
        self.evidence.controls['python_oracle'] = {
            'seed': 15102026, 'signed_bits': 64, 'pairs': pairs,
        }
        source = ['use "errors" as errors',
                  'function report(result: errors.IntegerResult) {',
                  'print(errors.integerOk(result))',
                  'if errors.integerOk(result) { print(errors.integerValue(result)) }',
                  'else { print(errors.code(errors.integerError(result)) == errors.overflowCode());',
                  'print(errors.nativeCode(errors.integerError(result))) }', '}',
                  'let lefts: List<Integer> = [' + ','.join(str(a) for a, _ in pairs) + ']',
                  'let rights: List<Integer> = [' + ','.join(str(b) for _, b in pairs) + ']']
        expected = []
        for operation, model in (('Add', lambda a, b: a + b),
                                 ('Subtract', lambda a, b: a - b),
                                 ('Multiply', lambda a, b: a * b)):
            source += ['for i in 0..lefts.length {',
                       f'report(errors.checked{operation}(lefts[i], rights[i]))', '}']
            for a, b in pairs:
                value = model(a, b)
                expected += ['true', str(value)] if low <= value <= high else ['false', 'true', '0']
        llvm = self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')
        ir = llvm.read_text()
        for operation in ('sadd', 'ssub', 'smul'):
            self.assertIn(f'call {{ i64, i1 }} @llvm.{operation}.with.overflow.i64', ir)
        helpers = [body for body in re.findall(r'define [^\n]+\{\n.*?\n\}', ir, re.S)
                   if '%integer.overflow.pair =' in body]
        self.assertEqual(len(helpers), 3)
        for body in helpers:
            self.assertIn('extractvalue { i64, i1 } %integer.overflow.pair, 1', body)
            self.assertNotIn('@.minyar.integer.overflow.checked', body)
            self.assertNotIn('nsw', body)
        self.assertNotIn('minyar-native-library: integer_overflow', ir)

    def test_overflow_messages_and_error_codes_are_stable(self):
        self.executes('''use "errors" as errors
let a = errors.checkedAdd(9223372036854775807, 1)
let s = errors.checkedSubtract(-9223372036854775808, 1)
let m = errors.checkedMultiply(-9223372036854775808, -1)
print(errors.overflowCode())
print(errors.message(errors.integerError(a)))
print(errors.message(errors.integerError(s)))
print(errors.message(errors.integerError(m)))
print(errors.isWouldBlock(errors.integerError(a)))
print(errors.code(errors.integerError(errors.checkedAdd(-1, 1))))
''', '13\nInteger addition overflow\nInteger subtraction overflow\nInteger multiplication overflow\nfalse\n0\n')

    def test_operands_evaluate_once_in_order(self):
        self.executes('''use "errors" as errors
function left(): Integer { print(11); return 9223372036854775807 }
function right(): Integer { print(22); return 1 }
print(errors.integerOk(errors.checkedAdd(left(), right())))
print(errors.integerOk(errors.checkedSubtract(left(), right())))
print(errors.integerOk(errors.checkedMultiply(left(), right())))
print(33)
''', '11\n22\nfalse\n11\n22\ntrue\n11\n22\ntrue\n33\n')

    def test_failed_value_extraction_remains_fatal(self):
        for expression in ('errors.checkedAdd(9223372036854775807, 1)',
                           'errors.checkedSubtract(-9223372036854775808, 1)',
                           'errors.checkedMultiply(-9223372036854775808, -1)'):
            with self.subTest(expression=expression):
                self.executes('use "errors" as errors\nerrors.integerValue(' + expression +
                              ')\nprint("after")\n', '', status=1,
                              stderr='Minyar stopped: cannot read the value of a failed IntegerResult\n')

    def test_wrapping_operations_remain_compatible(self):
        self.executes('''print(wrappingAdd(9223372036854775807, 1))
print(wrappingSubtract(-9223372036854775808, 1))
print(wrappingMultiply(-9223372036854775808, -1))
''', '-9223372036854775808\n9223372036854775807\n-9223372036854775808\n')

    def test_public_arguments_and_private_fields_are_checked(self):
        for operation in ('Add', 'Subtract', 'Multiply'):
            with self.subTest(operation=operation):
                self.rejects('use "errors" as errors\nerrors.checked' + operation + '(1.0, 2)\n',
                             'an argument passed to checked' + operation + ' has the wrong type')
                self.rejects('use "errors" as errors\nlet result = errors.checked' + operation +
                             '(1, 2)\nresult.value = 9\n', 'private')

    def test_scalar_intrinsic_signatures_are_checked(self):
        for name in ('addOverflows', 'subtractOverflows', 'multiplyOverflows'):
            for signature in ('(a: Integer): Boolean', '(a: Float, b: Integer): Boolean',
                              '(a: Integer, b: Integer): Integer',
                              '(a: Integer, b: Integer, c: Integer): Boolean'):
                with self.subTest(name=name, signature=signature):
                    self.rejects(f'function {name}{signature} {{ native "integer_overflow" }}\n',
                                 'expects two Integer parameters and a Boolean return')
        self.rejects('function unknown(a: Integer, b: Integer): Boolean { native "integer_overflow" }\n',
                     'no intrinsic named')


if __name__ == '__main__':
    unittest.main()
