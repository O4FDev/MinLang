#!/usr/bin/env python3
"""Recoverable value results; original semantic adaptations of peer tests.

Peer sources/provenance: docs/research/runtime-concurrency-errors.md.
These tests use real module compilation and execute at O0/O2. They exercise
independent outcome combinations, binary data, retained aliases and caller
recovery, rather than only comparing factories with their implementations.
"""
import unittest

from regressions import CompilerTestCase, ROOT


class ErrorValues(CompilerTestCase):
    compiler_arguments = ('--library', str(ROOT / 'library'))

    def test_recoverable_failure_does_not_stop_program(self):
        self.executes('''use "errors" as errors
function parse(packet: Bytes): errors.IntegerResult {
    if packet.length < 2 {
        return errors.integerFailure(errors.make(errors.invalidDataCode(), 0, "short packet"))
    }
    return errors.integer(packet[0] * 256 + packet[1])
}
let failed = parse(Bytes(1))
print(errors.integerOk(failed))
print(errors.code(errors.integerError(failed)))
print(errors.message(errors.integerError(failed)))
let valid = Bytes(2)
valid[0] = 1; valid[1] = 2
print(errors.integerValue(parse(valid)))
print("still alive")
''', 'false\n6\nshort packet\n258\nstill alive\n')

    def test_error_classes_and_native_codes_are_independent(self):
        cases = [(code, native) for code in (1, 2, 6, 7, 11, 12, 999)
                 for native in (-1, 0, 13, 10035, 9223372036854775807)]
        statements = ['use "errors" as errors']
        expected = []
        for index, (code, native) in enumerate(cases):
            statements += [f'let e{index} = errors.make({code}, {native}, "é🙂-{index}")',
                           f'print(errors.code(e{index}))',
                           f'print(errors.nativeCode(e{index}))',
                           f'print(errors.message(e{index}))',
                           f'print(errors.isError(e{index}))']
            expected += [str(code), str(native), f'é🙂-{index}', 'true']
        self.executes('\n'.join(statements) + '\n', '\n'.join(expected) + '\n')

    def test_data_eof_wouldblock_failure_and_truncation_are_distinct(self):
        self.executes('''use "errors" as errors
let data = errors.bytes(Bytes())
let eof = errors.endOfStream()
let blocked = errors.wouldBlock(10035)
let failed = errors.bytesFailure(errors.make(errors.systemCode(), 9, "bad socket"))
let cut = errors.truncated(Bytes("abc"), 90)
print(errors.bytesStatus(data)); print(errors.bytesValue(data).length)
print(errors.bytesStatus(eof)); print(errors.bytesValue(eof).length)
print(errors.bytesStatus(blocked)); print(errors.nativeCode(errors.bytesError(blocked)))
print(errors.bytesStatus(failed)); print(errors.nativeCode(errors.bytesError(failed)))
print(errors.bytesStatus(cut)); print(Text(errors.bytesValue(cut)))
print(errors.bytesOk(data)); print(errors.bytesOk(eof)); print(errors.bytesOk(blocked))
print(errors.bytesOk(failed)); print(errors.bytesOk(cut))
print(errors.isWouldBlock(errors.bytesError(blocked)))
''', '0\n0\n2\n0\n1\n10035\n3\n9\n4\nabc\ntrue\ntrue\nfalse\nfalse\nfalse\ntrue\n')

    def test_binary_payload_and_error_survive_other_operations(self):
        self.executes('''use "errors" as errors
function create(): errors.BytesResult {
    let data = Bytes(3)
    data[0] = 0; data[1] = 255; data[2] = 128
    return errors.bytes(data)
}
let first = errors.bytesFailure(errors.make(errors.systemCode(), 13, "first"))
let second = errors.bytesFailure(errors.make(errors.systemCode(), 10054, "second"))
let payload = create()
let alias = payload
let data = errors.bytesValue(payload)
print(data[0]); print(data[1]); print(data[2])
print(errors.bytesValue(alias).length)
print(errors.nativeCode(errors.bytesError(first)))
print(errors.message(errors.bytesError(first)))
print(errors.nativeCode(errors.bytesError(second)))
print(errors.message(errors.bytesError(second)))
''', '0\n255\n128\n3\n13\nfirst\n10054\nsecond\n')

    def test_boolean_false_and_integer_zero_are_success_values(self):
        self.executes('''use "errors" as errors
let b = errors.boolean(false)
let n = errors.integer(0)
print(errors.booleanOk(b)); print(errors.booleanValue(b))
print(errors.integerOk(n)); print(errors.integerValue(n))
print(errors.code(errors.booleanError(b)))
print(errors.code(errors.integerError(n)))
let bad = errors.booleanFailure(errors.make(errors.cancelledCode(), 0, "cancelled"))
print(errors.booleanOk(bad)); print(errors.message(errors.booleanError(bad)))
''', 'true\nfalse\ntrue\n0\n0\n0\nfalse\ncancelled\n')

    def test_repeated_recovery_and_alias_lifetimes(self):
        self.executes('''use "errors" as errors
let survivor = errors.bytesFailure(errors.make(errors.systemCode(), 17, "survivor"))
let successes = 0
for i in 0..10000 {
    let result = errors.bytesFailure(errors.make(errors.invalidDataCode(), i, Text(i)))
    if errors.code(errors.bytesError(result)) == errors.invalidDataCode() {
        successes = successes + 1
    }
    let recovered = errors.bytes(Bytes("ok"))
    if errors.bytesValue(recovered).length != 2 { fail("payload changed") }
}
print(successes)
print(errors.nativeCode(errors.bytesError(survivor)))
print(errors.message(errors.bytesError(survivor)))
''', '10000\n17\nsurvivor\n')

    def test_invalid_programmer_contracts_remain_fatal(self):
        cases = [
            ('errors.make(0, 0, "bad")', 'an error code must be positive'),
            ('errors.make(-1, 0, "bad")', 'an error code must be positive'),
            ('errors.integerFailure(errors.none())', 'a failure result requires an error'),
            ('errors.bytesFailure(errors.none())', 'a failure result requires an error'),
            ('errors.booleanFailure(errors.none())', 'a failure result requires an error'),
            ('errors.integerValue(errors.integerFailure(errors.make(7, 9, "bad")))',
             'cannot read the value of a failed IntegerResult'),
            ('errors.booleanValue(errors.booleanFailure(errors.make(7, 9, "bad")))',
             'cannot read the value of a failed BooleanResult'),
            ('errors.bytesValue(errors.wouldBlock(11))', 'this BytesResult has no readable data'),
        ]
        for expression, message in cases:
            with self.subTest(expression=expression):
                self.executes('use "errors" as errors\n' + expression + '\nprint("after")\n',
                              '', status=1, stderr='Minyar stopped: ' + message + '\n')

    def test_private_fields_prevent_forged_or_mutated_result_tags(self):
        self.rejects('''use "errors" as errors
let result = errors.bytes(Bytes())
result.status = 2
''', 'private')
        self.rejects('''use "errors" as errors
let bad = errors.Error { code: 0; nativeCode: 9; message: "forged" }
''', 'private')


if __name__ == '__main__':
    unittest.main()
