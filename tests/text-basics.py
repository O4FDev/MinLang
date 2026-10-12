#!/usr/bin/env python3
"""Frontend contracts for Text methods, Integer(Text), and List.clear."""
import unittest
import random
import re
from regressions import CompilerTestCase, ROOT

class TextBasics(CompilerTestCase):
    compiler_arguments = ("--library", str(ROOT / "library"))
    def test_declarations_are_emitted_only_once_and_only_when_used(self):
        result, llvm = self.compile('print("value".slice(0, 1))\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ('find', 'split', 'starts_with', 'ends_with', 'trim', 'integer'):
            self.assertNotIn('@minyar_text_' + name + '(', llvm.read_text())
        self.assertNotIn('@minyar_list_clear(', llvm.read_text())
        result, llvm = self.compile('print("x".find("x"))\nprint("y".find("y"))\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(llvm.read_text().count('declare i64 @minyar_text_find('), 1)

    def test_text_split_original_gap_and_scalar_positions(self):
        self.executes('''let fields = "postgres:x:70:70:PostgreSQL:/var/lib/postgresql:/bin/sh".split(":")
print(Integer(fields[2]))
let pieces = ":a::".split(":")
print(pieces.length)
print(pieces[0] == "")
print(pieces[2] == "")
print(pieces[3] == "")
print("".split("").length)
print("".split(":").length)
print("é🍊é零".split("").length)
print("é🍊é零".find("零"))
print("é🍊é零".find("é"))
print("é🍊é零".find("missing"))
print("é🍊".find(""))
print("é🍊".startsWith("é"))
print("é🍊".endsWith("🍊"))
print("".startsWith(""))
print("".endsWith(""))
print(" \t 🍊　".trim())
print("​﻿".trim().length)
''', '70\n4\ntrue\ntrue\ntrue\n0\n1\n5\n4\n2\n-1\n0\ntrue\ntrue\ntrue\ntrue\n🍊\n2\n')

    def test_list_clear_original_gap_alias_and_reuse(self):
        self.executes('''function main() {
let values: List<Integer> = [1, 2, 3]
let alias = values
values.clear()
print(alias.length)
values.clear()
values.add(42)
print(alias[0])
let words = "a:b".split(":")
let first = words[0]
words.clear()
print(first)
words.add("again")
print(words[0])
let lists: List<List<Text>> = [["owned"]]
lists.clear()
print(lists.length)
}
''', '0\n42\na\nagain\n0\n')

    def test_clear_all_scalar_slot_types(self):
        self.executes('''let floats = [1.5, -0.0]
let flags = [true, false]
let scalars = ['é', '🍊']
floats.clear()
flags.clear()
scalars.clear()
floats.add(2.5)
flags.add(false)
scalars.add('零')
print(floats[0])
print(flags[0])
print(scalars[0])
''', '2.5\nfalse\n零\n')

    def test_integer_text_boundaries(self):
        self.executes('''print(Integer("0"))
print(Integer("-0"))
print(Integer(" \t+00042\r\n"))
print(Integer("-9223372036854775808"))
print(Integer("9223372036854775807"))
''', '0\n0\n42\n-9223372036854775808\n9223372036854775807\n')

    def test_method_arguments_are_checked(self):
        for member in ('find', 'startsWith', 'endsWith', 'split'):
            self.rejects(f'print("value".{member}(42))\n', f'Text.{member} expects one Text argument')
        self.rejects('print("value".trim(1))\n', "expected ')'")
        self.rejects('let values: List<Integer> = []\nvalues.clear(1)\n', "expected ')'")

    def test_integer_invalid_and_overflow_are_fatal(self):
        for value, diagnostic in (('', 'signed decimal ASCII integer'), ('1x', 'signed decimal ASCII integer'),
                                  ('9223372036854775808', 'signed 64-bit range'),
                                  ('-9223372036854775809', 'signed 64-bit range')):
            result, llvm = self.compile(f'print(Integer("{value}"))\n')
            self.assertEqual(result.returncode, 0, result.stderr)
            exe = llvm.with_suffix('.exe')
            self.assertEqual(self.link_program(llvm, '-O2', exe).returncode, 0)
            run = self.evidence.run([str(exe)], capture_output=True, text=True, timeout=10, phase='execute')
            self.assertEqual(run.returncode, 1)
            self.assertIn(diagnostic, run.stderr)

    def test_nonfatal_library_parser(self):
        self.executes('''use "text" as text
use "errors" as errors
let zero = text.parseInteger("0")
print(errors.integerOk(zero))
print(errors.integerValue(zero))
print(errors.integerValue(text.parseInteger("-9223372036854775808")))
print(errors.integerValue(text.parseInteger(" +9223372036854775807 ")))
print(errors.integerOk(text.parseInteger("9223372036854775808")))
print(errors.integerOk(text.parseInteger("-9223372036854775809")))
print(errors.integerOk(text.parseInteger("1x")))
print(errors.code(errors.integerError(text.parseInteger(" 1"))))
let bad = Bytes()
bad.add(255)
print(text.validUTF8(bad))
print(errors.code(errors.integerError(text.parseIntegerBytes(bad))))
print(errors.integerOk(text.parseInteger(Text(bad))))
print(errors.integerOk(text.parseIntegerBytes(Bytes("0"))))
''', 'true\n0\n-9223372036854775808\n9223372036854775807\nfalse\nfalse\nfalse\n6\nfalse\n6\nfalse\ntrue\n')

    def test_nonfatal_parser_matches_unbounded_integer_model(self):
        rng = random.Random(0x1A64)
        values = [str(value).encode() for value in
                  (-(2**63) - 1, -(2**63), 2**63 - 1, 2**63, 0)]
        values += [f' \t{rng.randrange(-(2**65), 2**65)}\r\n'.encode() for _ in range(40)]
        values += [b'', b'+', b'-', b'+-1', b'0x2a', b'1_000', b'1\0', b'1 2',
                   b'0000', b'-0000', b'+00042', b'\v\f42\v\f', b'0' * 100,
                   '１２'.encode(), '\u00a01'.encode()]
        values += [bytes.fromhex(value) for value in
                   ('80', 'c080', 'eda080', 'f4908080', 'e282', 'f0808080', '30ff')]
        program = ['use "text" as text', 'use "errors" as errors',
                   'function show(raw: Bytes) {', 'let result = text.parseIntegerBytes(raw)',
                   'if errors.integerOk(result) { print(errors.integerValue(result)) }',
                   'else { print("invalid") }', '}']
        expected = []
        for index, raw in enumerate(values):
            try:
                source = raw.decode('utf-8')
            except UnicodeDecodeError:
                source = None
            if source is not None and re.fullmatch(r'[ \t\n\r\v\f]*[+-]?[0-9]+[ \t\n\r\v\f]*', source):
                value = int(source)
                expected.append(str(value) if -(2**63) <= value < 2**63 else 'invalid')
            else:
                expected.append('invalid')
            program.append(f'let raw{index} = Bytes()')
            program.extend(f'raw{index}.add({byte})' for byte in raw)
            program.append(f'show(raw{index})')
        self.executes('\n'.join(program) + '\n', '\n'.join(expected) + '\n')

if __name__ == '__main__': unittest.main()
