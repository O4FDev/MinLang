#!/usr/bin/env python3
"""RESP2 streaming adversaries derived from Redis protocol and parser tests.

Every prefix is incomplete or a recoverable invalid-data error; coalesced
replies consume exactly one frame. Binary data and nulls retain their meaning.
"""
import random
import struct
import unittest

from regressions import CompilerTestCase, ROOT


class RedisProtocol(CompilerTestCase):
    compiler_arguments = ('--library', str(ROOT / 'library'))

    def test_independent_models_all_short_inputs_and_seeded_mutations(self):
        # Generate semantic values first, then independently encode their wire
        # form. The Minyar oracle compares every byte of the decoded value's
        # canonical encoding, including binary bulk strings and nested nulls.
        rng = random.Random(0x5245535032)

        def model(depth=0):
            kind = rng.choice(('simple', 'error', 'integer', 'bulk', 'null-bulk', 'null-array', 'array') if depth < 4
                              else ('integer', 'bulk', 'null-bulk'))
            if kind in ('simple', 'error'):
                return kind, bytes(rng.choice([n for n in range(256) if n not in (10, 13)]) for _ in range(rng.randrange(24)))
            if kind == 'integer':
                return kind, rng.choice((-(1 << 63), (1 << 63) - 1, 0, rng.randrange(-(1 << 63), 1 << 63)))
            if kind == 'bulk':
                return kind, rng.randbytes(rng.randrange(65))
            if kind == 'array':
                return kind, [model(depth + 1) for _ in range(rng.randrange(6))]
            return kind, None

        def encode(value):
            kind, data = value
            if kind in ('simple', 'error'):
                return (b'+' if kind == 'simple' else b'-') + data + b'\r\n'
            if kind == 'integer':
                return b':' + str(data).encode() + b'\r\n'
            if kind == 'bulk':
                return b'$' + str(len(data)).encode() + b'\r\n' + data + b'\r\n'
            if kind == 'array':
                return b'*' + str(len(data)).encode() + b'\r\n' + b''.join(encode(child) for child in data)
            return b'$-1\r\n' if kind == 'null-bulk' else b'*-1\r\n'

        cases = [(0, bytes([first]), b'') for first in range(256)]
        cases.extend((0, bytes([first, second]), b'') for first in range(256) for second in range(256))
        for _ in range(200):
            packet = encode(model())
            cases.append((1, packet, packet))
            cases.extend((3, packet[:cut], b'') for cut in range(len(packet)))
            for _ in range(8):
                changed = bytearray(packet); changed[rng.randrange(len(changed))] ^= 1 << rng.randrange(8)
                cases.append((2, bytes(changed), b''))
        cases.extend((2, rng.randbytes(rng.randrange(65)), b'') for _ in range(5000))
        corpus = self.directory / 'resp-corpus.bin'
        corpus.write_bytes(b''.join(struct.pack('>BII', mode, len(packet), len(expected)) + packet + expected
                                    for mode, packet, expected in cases))
        self.executes((ROOT / 'tests/redis-protocol-corpus.min').read_text(), f'{len(cases)}\n', arguments=(str(corpus),))

    def test_binary_bulk_null_and_error_replies_are_distinct(self):
        self.executes('''use "resp2" as resp
use "errors" as errors
let data = Bytes("$4\\r\\n")
data.add(0); data.add(255); data.add(13); data.add(10)
data.addBytes(Bytes("\\r\\n+tail\\r\\n"))
let result = resp.parse(data)
print(resp.ok(result)); print(resp.consumed(result))
let value = resp.value(result)
print(resp.kind(value) == resp.BULK)
print(resp.data(value).length); print(resp.data(value)[1])
print(resp.kind(resp.value(resp.parse(Bytes("$-1\\r\\n")))) == resp.NULL_BULK)
print(resp.kind(resp.value(resp.parse(Bytes("*-1\\r\\n")))) == resp.NULL_ARRAY)
print(resp.kind(resp.value(resp.parse(Bytes("$0\\r\\n\\r\\n")))) == resp.BULK)
print(resp.kind(resp.value(resp.parse(Bytes("*0\\r\\n")))) == resp.ARRAY)
let error = resp.parse(Bytes("-ERR rejected\\r\\n"))
print(resp.ok(error)); print(resp.kind(resp.value(error)) == resp.ERROR)
print(Text(resp.data(resp.value(error))))
''', 'true\n10\ntrue\n4\n255\ntrue\ntrue\ntrue\ntrue\ntrue\ntrue\nERR rejected\n')

    def test_every_prefix_and_coalesced_reply_boundary(self):
        self.executes('''use "resp2" as resp
use "errors" as errors
let packet = Bytes("*3\\r\\n+OK\\r\\n$4\\r\\nhé!\\r\\n:9223372036854775807\\r\\n")
for length in 0..packet.length {
    let result = resp.parse(packet.slice(0, length))
    if resp.ok(result) || !resp.incomplete(result) || resp.consumed(result) != 0 { fail("prefix accepted") }
}
let result = resp.parse(packet)
print(resp.ok(result)); print(resp.consumed(result) == packet.length)
let values = resp.items(resp.value(result))
print(values.length); print(Text(resp.data(values[1]))); print(resp.integer(values[2]))
packet.addBytes(Bytes("+NEXT\\r\\n"))
let first = resp.parse(packet)
let second = resp.parse(packet.slice(resp.consumed(first), packet.length))
print(Text(resp.data(resp.value(second))))
''', 'true\ntrue\n3\nhé!\n9223372036854775807\nNEXT\n')

    def test_malformed_numbers_and_delimiters_are_recoverable(self):
        self.executes('''use "resp2" as resp
use "errors" as errors
for packet in [":9223372036854775808\\r\\n", ":-9223372036854775809\\r\\n", ":\\r\\n", ":+\\r\\n", ": 1\\r\\n", ":1x\\r\\n",
               "$-2\\r\\n", "*+1\\r\\n", "*-2\\r\\n", "$1048577\\r\\n", "*1025\\r\\n", "$3\\r\\nabcXX", "+bad\\n", "+bad\\rX", "?unknown\\r\\n"] {
    let result = resp.parse(Bytes(packet))
    if resp.ok(result) || resp.incomplete(result) || resp.consumed(result) != 0 { fail("malformed RESP accepted") }
    if errors.code(resp.error(result)) != errors.invalidDataCode() { fail("wrong RESP error") }
}
let minimum = resp.parse(Bytes(":-9223372036854775808\\r\\n"))
print(resp.integer(resp.value(minimum)))
print(resp.integer(resp.value(resp.parse(Bytes(":+1\\r\\n")))))
print("still alive")
''', '-9223372036854775808\n1\nstill alive\n')

    def test_encoded_commands_use_byte_lengths_and_preserve_empty_data(self):
        self.executes('''use "resp2" as resp
use "errors" as errors
let binary = Bytes(3); binary[0] = 0; binary[1] = 255; binary[2] = 10
let encoded = resp.command([Bytes("SET"), Bytes("é🙂"), Bytes(), binary])
let result = resp.parse(errors.bytesValue(encoded))
let items = resp.items(resp.value(result))
print(items.length); print(resp.data(items[1]).length); print(Text(resp.data(items[1])))
print(resp.data(items[2]).length); print(resp.data(items[3])[1])
print(errors.bytesOk(resp.command([])))
''', '4\n6\né🙂\n0\n255\nfalse\n')

    def test_parser_bounds_and_repeated_recovery(self):
        self.executes('''use "resp2" as resp
let nested = Bytes()
for i in 0..18 { nested.addBytes(Bytes("*1\\r\\n")) }
nested.addBytes(Bytes("+x\\r\\n"))
print(resp.ok(resp.parse(nested)))
let longLine = Bytes("+")
for i in 0..4097 { longLine.add(120) }
print(resp.incomplete(resp.parse(longLine)))
let complete = 0
for i in 0..10000 {
    let invalid = resp.parse(Bytes("$999999999999999999999999999999\\r\\n"))
    if resp.ok(invalid) || resp.incomplete(invalid) { fail("overflow accepted") }
    let valid = resp.parse(Bytes("*2\\r\\n:1\\r\\n$0\\r\\n\\r\\n"))
    if resp.items(resp.value(valid)).length != 2 { fail("recovery changed reply") }
    complete += 1
}
print(complete)
''', 'false\nfalse\n10000\n')


if __name__ == '__main__':
    unittest.main()
