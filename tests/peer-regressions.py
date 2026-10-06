#!/usr/bin/env python3
"""Original Minyar regressions derived from the pinned peer-testing audit.

Sources and semantic differences: docs/research/peer-tests-{cpp,javascript-java,
rust-go-zig,python-swift,ruby-lua}.md. No upstream fixture code is copied.
"""
import os
import json
import random
import stat
import sys
import shlex
import unittest

from regressions import CompilerTestCase, CLANG, COMPILER, ROOT
from test_evidence import digest

OVERFLOW = 'Minyar stopped: this Integer calculation is outside the supported range.\n'
ZERO = 'Minyar stopped: an Integer cannot be divided by zero.\n'


def literal(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t') + '"'


class PeerRegressions(CompilerTestCase):
    def test_index_assignment_ignores_brackets_inside_literals(self):
        for kind, quote in (('Text', '"'), ('Character', "'")):
            with self.subTest(kind=kind):
                source = f'''record Holder {{ values: List<Integer> }}
function position(value: {kind}, calls: List<Integer>): Integer {{
print(value)
calls[0] = calls[0] + 1
return 0
}}
let calls = [0]
let values = [0]
let holder = Holder {{ values: values }}
'''
                for index, (receiver, bracket) in enumerate(
                        [('values', '['), ('values', ']'), ('holder.values', '['), ('holder.values', ']')], 1):
                    source += f'{receiver}[position({quote}{bracket}{quote}, calls)] = {index}\n'
                    source += 'print(values[0])\n'
                source += 'print(calls[0])\nprint(holder.values[0])\n'
                self.executes(source, '[\n1\n]\n2\n[\n3\n]\n4\n4\n4\n')

    def executes(self, source, expected, status=0, stderr='', arguments=()):
        variants = ('-O0', '-O2', '-O3', '-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1' else ('-O0', '-O2')
        return super().executes(source, expected, status, stderr, optimizations=variants, arguments=arguments)

    def test_final_statement_without_newline_and_incomplete_input(self):
        for ending in ('', ';', ' // comment at EOF', ' /* comment at EOF */', '\n ',
                       '\n//' + 'x' * 10000, '\n//' + 'x' * 10002):
            with self.subTest(ending=ending):
                self.executes('print(42)' + ending, '42\n')
        self.executes('let value = 42\r\nprint(value)', '42\n')
        self.rejects('let a = 42\rlet b = -13\rprint(a)\rprint(b)',
                     "unexpected 'let'; start the next statement on a new line")
        self.executes('let value = 1 // comment ending in ' + chr(92) + '\nvalue = 2\nprint(value)\n', '2\n')
        for incomplete in ('print(42', 'let value =', 'if true { print(42)', 'function f(): Integer { return 42'):
            with self.subTest(incomplete=incomplete):
                self.rejects(incomplete, 'Minyar stopped:')

    def test_wide_argument_positions_survive_register_stack_boundary(self):
        parameters = ', '.join(f'value{index}: Integer' for index in range(41))
        expression = ' + '.join(f'value{index} * {index + 1}' for index in range(41))
        arguments = ', '.join('input' if index == 39 else str(index) for index in range(41))
        self.executes(f'''function wide({parameters}): Integer {{ return {expression} }}
function caller(input: Integer): Integer {{
let result = wide({arguments})
print(input)
return result
}}
print(caller(39))
''', f'39\n{sum(index * (index + 1) for index in range(41))}\n')

    def test_associative_products_preserve_checked_intermediates(self):
        fixture = ROOT / 'tests/peer-associative-vectors.json'
        self.evidence.inputs[str(fixture.resolve())] = digest(fixture)
        data = json.loads(fixture.read_text())
        self.assertEqual(data['schema_version'], 1)
        self.assertEqual(len(data['cases']), 96)
        source = []
        expected = []
        failures = []
        minimum, maximum = -(1 << 63), (1 << 63) - 1
        for index, case in enumerate(data['cases']):
            expression = case['expression']
            self.assertRegex(expression, r'^[abc]\*[abc][+-][abc]\*[abc]$')
            left = case[expression[0]] * case[expression[2]]
            right = case[expression[4]] * case[expression[6]]
            result = left + right if expression[3] == '+' else left - right
            overflow = next((name for name, value in [('left product', left), ('right product', right),
                                                       ('final result', result)]
                             if not minimum <= value <= maximum), None)
            self.assertEqual(result, case['result'])
            self.assertEqual(overflow, case['overflow_stage'])
            source.append(f'function calculate{index}(a: Integer, b: Integer, c: Integer): Integer {{ return {expression} }}')
            constant = ''.join(f'({case[char]})' if char in 'abc' else char for char in expression)
            call = f'calculate{index}({case["a"]}, {case["b"]}, {case["c"]})'
            if overflow:
                failures += [(f'{index}-literal', constant), (f'{index}-parameter', call)]
            else:
                source += [f'print({constant})', f'print({call})']
                expected += [str(result)] * 2
        self.assertEqual(len(failures), 80)
        source.append('let choice = argument(0)')
        for choice, expression in failures:
            source.append(f'if choice == "{choice}" {{ print("before"); print({expression}) }}')
        source.append('print("ready")')
        prefix = '\n'.join(expected) + '\n'
        llvm = self.executes('\n'.join(source) + '\n', prefix + 'ready\n', arguments=['probe'])
        variants = ('-O0', '-O2', '-O3', '-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1' else ('-O0', '-O2')
        for optimization in variants:
            for choice, _ in failures:
                with self.subTest(optimization=optimization, choice=choice):
                    result = self.evidence.run([llvm.with_suffix('.' + optimization[1:]), choice],
                                               timeout=10, phase='execute-associative-overflow')
                    self.assertEqual((result.returncode, result.stdout, result.stderr),
                                     (1, (prefix + 'before\n').encode(), OVERFLOW.encode()))

    def test_intermediate_overflow_cannot_be_reassociated_away(self):
        # C02/C03: a mathematical final result may fit after an earlier trap.
        for expression, value in [('(x + 13) - 7', 9223372036854775797),
                                  ('(x - 13) + 7', -9223372036854775798)]:
            with self.subTest(expression=expression):
                self.executes(f'function calculate(x: Integer): Integer {{ return {expression} }}\nprint("before")\nprint(calculate({value}))\n',
                              'before\n', 1, OVERFLOW)
        self.executes('''function calculate(x: Integer): Integer { return (x + 13) - 7 }
print(calculate(9223372036854775794))
''', '9223372036854775800\n')

    def test_unused_dynamic_arithmetic_must_still_trap(self):
        # Zig Z5: dead value elimination must preserve required error effects.
        for expression, value, error in [('x + 1', 9223372036854775807, OVERFLOW),
                                         ('x - 1', -9223372036854775808, OVERFLOW),
                                         ('x * 2', 4611686018427387904, OVERFLOW),
                                         ('-x', -9223372036854775808, OVERFLOW),
                                         ('7 / x', 0, ZERO), ('7 % x', 0, ZERO)]:
            with self.subTest(expression=expression):
                self.executes(f'''function calculate(x: Integer) {{
let unused = {expression}
print("incorrectly survived")
}}
calculate({value})
''', '', 1, error)

    def test_unreachable_traps_and_safe_neighbors(self):
        self.executes('''function calculate(x: Integer, execute: Boolean): Integer {
if execute { return x + 1 } else { return 42 }
}
print(calculate(9223372036854775807, false))
print(calculate(9223372036854775806, true))
function division(x: Integer, execute: Boolean): Integer {
if execute { return 7 / x } else { return 9 }
}
print(division(0, false))
print(division(1, true))
''', '42\n9223372036854775807\n9\n7\n')

    def test_huge_indices_fail_before_scaled_address_or_reference_update(self):
        for index in (-9223372036854775808, -1, 2305843009213693952, 4611686018427387904, 9223372036854775807):
            for operation in ('print(values[index])', 'values[index] = "replacement"'):
                with self.subTest(index=index, operation=operation):
                    self.executes(f'''function access(values: List<Text>, index: Integer) {{
{operation}
}}
let values = ["retained"]
access(values, {index})
''', '', 1, f'Minyar stopped: List position {index} is outside its length of 1.\n')

    def test_module_alias_reload_after_calls_and_loops(self):
        # C04: same versus distinct reference values through a module boundary.
        (self.directory / 'mutation.min').write_text('''public function mutate(write: List<Integer>, read: List<Integer>): Integer {
let index = 0
while index < 7 {
write[0] = write[0] + 1
index = index + 1
}
return read[0]
}
''')
        self.executes('''use "./mutation.min" as mutation
let values = [10]
let other = [20]
print(mutation.mutate(values, values))
print(mutation.mutate(values, other))
print(values[0])
print(other[0])
''', '17\n20\n24\n20\n')

    def test_terminal_operand_stops_later_effects(self):
        # JS1: borrow trace technique, not JavaScript coercion/exception rules.
        self.executes('''function left(): Integer { print("left"); fail("stopped") }
function right(): Integer { print("right"); return 2 }
print(left() + right())
''', 'left\n', 1, 'Minyar stopped: stopped\n')

    def test_dead_boolean_operands_still_require_valid_names(self):
        for expression in ('false && missing', 'true || missing'):
            with self.subTest(expression=expression):
                self.rejects(f'print({expression})\n', 'missing')

    def test_integer_equality_keeps_all_64_bits(self):
        self.executes('''function same(left: Integer, right: Integer): Boolean { return left == right }
print(same(2305843009213693697, 2305843009213693698))
print(same(-2305843009213693697, -2305843009213693698))
print(same(2305843009213693697, 2305843009213693697))
''', 'false\nfalse\ntrue\n')

    def test_unused_bounds_check_and_reversed_slice_still_fail(self):
        self.executes('''function discard(value: Text) {}
function get(values: List<Text>, index: Integer): Text { return values[index] }
discard(get(["safe"], 1))
''', '', 1, 'Minyar stopped: List position 1 is outside its length of 1.\n')
        self.executes('''function slice(text: Text, start: Integer, end: Integer): Text { return text.slice(start, end) }
print(slice("abcd", 3, 1))
''', '', 1, 'Minyar stopped: a Text slice must stay within the Text and end after it starts.\n')

    def test_selected_record_survives_reassignment_of_both_sources(self):
        self.executes('''record Box { text: Text }
function choose(left: Box, right: Box, first: Boolean): Box {
if first { return left } else { return right }
}
let left = Box { text: "left" + "!" }
let right = Box { text: "right" + "!" }
let chosen = choose(left, right, false)
left = Box { text: "replacement left" }
right = Box { text: "replacement right" }
print(chosen.text)
''', 'right!\n')

    def test_trailing_boolean_constant_preserves_prior_effects(self):
        self.executes('''function mark(value: Boolean, events: List<Integer>): Boolean {
events.add(events.length)
return value
}
let andEvents: List<Integer> = []
print(mark(true, andEvents) && mark(true, andEvents) && false && mark(true, andEvents))
print(andEvents.length)
let orEvents: List<Integer> = []
print(mark(false, orEvents) || mark(false, orEvents) || true || mark(false, orEvents))
print(orEvents.length)
''', 'false\n2\ntrue\n2\n')

    def test_division_record_result_and_multiply_boundary(self):
        self.executes('''record Division { quotient: Integer; remainder: Integer }
function divide(left: Integer, right: Integer): Division {
return Division { quotient: left / right; remainder: left % right }
}
let result = divide(1152921504606846976, 34359738365)
print(result.quotient)
print(result.remainder)
function multiply(left: Integer, right: Integer): Integer { return left * right }
print(multiply(3, -3074457345618258602))
''', '33554432\n100663296\n-9223372036854775806\n')
        self.executes('''function multiply(left: Integer, right: Integer): Integer { return left * right }
print(multiply(3, -3074457345618258603))
''', '', 1, OVERFLOW)

    def test_scalar_record_fields_feed_required_division_check(self):
        self.executes('''record Number { value: Integer }
record Outer { inner: Number }
let value = Outer { inner: Number { value: 42 } }
print(7 / (value.inner.value - 42))
''', '', 1, ZERO)

    def test_malformed_radix_like_literals_do_not_accept_valid_prefix(self):
        for value in ('0x', '0X', '0xG', '0b2', '00b0', '0b', '0o8', '00o0', '0o', '123name'):
            with self.subTest(value=value):
                self.rejects(f'print({value})\n', 'Minyar stopped:')
        self.executes('\n'.join(f'print(0{value})' for value in range(70, 78)),
                      ''.join(f'{value}\n' for value in range(70, 78)))

    def test_invalid_source_bytes_are_not_hidden_by_comments_or_eof(self):
        invalid = (b'\xef', b'\xef\xbb', b'\x80', b'\xc0\xaf', b'\xed\xa0\x80', b'\xf4\x90\x80\x80')
        programs = [prefix + value + suffix for value in invalid
                    for prefix, suffix in ((b'', b''), (b'// ', b'\nprint(42)\n'),
                                           (b'/* ', b' */\nprint(42)\n'))]
        programs += [b'print(42)\x00print(99)\n', b'print(42)\x1aprint(99)\n']
        for index, program in enumerate(programs):
            with self.subTest(index=index):
                source, llvm = self.directory / f'bytes{index}.min', self.directory / f'bytes{index}.ll'
                source.write_bytes(program)
                result = self.evidence.run([COMPILER, source, llvm], timeout=10, phase='compile-reject')
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(b'Minyar stopped:', result.stderr)
                self.assertFalse(result.stdout)
                self.assertFalse(llvm.exists())

    def test_algebraic_simplification_preserves_inner_overflow(self):
        cases = [('0 * (x + 1)', 9223372036854775807),
                 ('(x + 1) * 0', 9223372036854775807),
                 ('x * 2 * 0', 9223372036854775807),
                 ('(x * 2) * 0', 9223372036854775807),
                 ('(x + 1) - x', 9223372036854775807),
                 ('(x * 100) / 10', 92233720368547759)]
        for expression, value in cases:
            with self.subTest(expression=expression):
                self.executes(f'function calculate(x: Integer): Integer {{ return {expression} }}\nprint("before")\nprint(calculate({value}))\n',
                              'before\n', 1, OVERFLOW)
        for expression in ('9223372036854775807 * 2 * 0', '(9223372036854775807 * 2) * 0'):
            self.executes('print(' + expression + ')\n', '', 1, OVERFLOW)
        self.executes('function safe(x: Integer): Integer { return x * (2 * 0) }\n'
                      'print(safe(9223372036854775807))\nprint(9223372036854775807 * (2 * 0))\n', '0\n0\n')
        self.executes('function greater(x: Integer): Boolean { return x + 1 > x }\nprint(greater(9223372036854775807))\n', '', 1, OVERFLOW)
        self.executes('function greater(x: Integer): Boolean { return x + 1 > x }\nprint(greater(9223372036854775806))\n', 'true\n')
        self.executes("""function count(start: Integer): Integer {
let index = start
let count = 0
while index <= start + 4 { count = count + 1; index = index + 2 }
return count
}
print(count(9223372036854775804))
""", '', 1, OVERFLOW)

    def test_signed_division_remainder_and_operand_placement_grid(self):
        pairs = {(a, b) for a in range(-6, 7) for b in range(-6, 7) if b}
        boundaries = (-9223372036854775808, -9223372036854775807, -2, -1, 0, 1, 2, 9223372036854775806, 9223372036854775807)
        lua_values = (-16, -15, -3, -2, -1, 0, 1, 2, 3, 15)
        pairs.update((a, b) for a in lua_values for b in lua_values if b)
        pairs.update((a, b) for a in boundaries for b in boundaries if b and (a, b) != (-9223372036854775808, -1))
        source = ['function divide(a: Integer, b: Integer): Integer { return a / b }',
                  'function remainder(a: Integer, b: Integer): Integer { return a % b }']
        expected = []
        for index, (a, b) in enumerate(sorted(pairs)):
            quotient = abs(a) // abs(b)
            if (a < 0) != (b < 0): quotient = -quotient
            remainder = a - quotient * b
            source += [f'let a{index} = {a}', f'let b{index} = {b}']
            for left, right in ((str(a), str(b)), (f'a{index}', str(b)),
                                (str(a), f'b{index}'), (f'a{index}', f'b{index}')):
                source += [f'print({left} / {right})', f'print({left} % {right})']
                expected += [str(quotient), str(remainder)]
            source += [f'print(divide(a{index}, b{index}))', f'print(remainder(a{index}, b{index}))']
            expected += [str(quotient), str(remainder)]
        self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')

    def test_negation_literal_and_parameter_paths(self):
        self.executes('print(-2 == 0 - 2)\n', 'true\n')
        self.executes('function negate(value: Integer): Integer { return -value }\n'
                      'print(negate(2305843009213693697))\nprint(-(2305843009213693697))\n'
                      'print(negate(2305843009213693697) != -2305843009213693696)\n',
                      '-2305843009213693697\n-2305843009213693697\ntrue\n')
        for operator in ('/', '%'):
            for expression in (f'-9223372036854775808 {operator} -1', f'calculate(-9223372036854775808, -1)'):
                self.executes(f'function calculate(a: Integer, b: Integer): Integer {{ return a {operator} b }}\nprint({expression})\n', '', 1, 'Minyar stopped: this Integer division is outside the supported range.\n')
        self.executes('function negate(value: Integer): Integer { return -value }\nprint(-0)\nprint(--2)\nprint(negate(0))\nprint(negate(negate(2)))\nprint(negate(-9223372036854775807))\n',
                      '0\n2\n0\n2\n9223372036854775807\n')
        self.executes('print(-(-9223372036854775808))\n', '', 1, OVERFLOW)
        for expression in ('0 * (1 / 0)', '0 * (1 % 0)'):
            self.executes('print(' + expression + ')\n', '', 1, ZERO)

    def test_thirty_distinct_program_arguments(self):
        arguments = ['', 'é🙂', 'two words', '--option', '-1', 'quote"slash\\']
        arguments += [f'argument-{index}' for index in range(24)]
        self.executes('print(argumentCount())\nlet index = 0\nwhile index < argumentCount() { print(argument(index)); index = index + 1 }\n',
                      '30\n' + '\n'.join(arguments) + '\n', arguments=arguments)

    def test_large_unicode_nul_file_roundtrip(self):
        value = ('abé🙂\0\n' * 11000) + 'last🙂'
        original, output = self.directory / 'large-input.txt', self.directory / 'large-output.txt'
        original.write_bytes(value.encode('utf-8'))
        CompilerTestCase.executes(self, 'let text = readTextFile(argument(0))\nprint(text.length)\n'
                      'writeTextFile(argument(1), text)\nprint(readTextFile(argument(1)) == text)\n',
                      f'{len(value)}\ntrue\n', arguments=[str(original), str(output)],
                      optimizations=('-O0','-O2','-O3','-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT')=='1' else ('-O0','-O2'),
                      file_outputs=((output, value.encode('utf-8')),))

    def test_unicode_composition_vectors_indices_slices_and_files(self):
        vectors = [
            [27721, 23383, 47, 28450, 23383],
            [0, 97, 98, 99, 1],
            [0, 127, 128, 2047, 2048, 65535, 65536, 1114111],
            [26085, 26412, 35486, 97, 45, 52, 0, 233, 243],
            [0x23CB7, 0x2070E, 0x20C53, 0x2107B, 0x20D7C, 97, 98, 0x20EA2],
            [0x28CCA, 0x29D98, 0x269FA, 0x28CD2, 0x2512B, 0x244D3, 0x10FFFF],
            [0xC7, 0x2202, 0xE9, 0x192, 0x67],
            [0x8987],
            [0x24B62],
        ]
        for number, vector in enumerate(vectors):
            value = ''.join(map(chr, vector))
            original = self.directory / f'composition{number}-input.txt'
            output = self.directory / f'composition{number}-output.txt'
            original.write_bytes(value.encode('utf-8'))
            source = ['let text = readTextFile(argument(0))',
                      'print(text.length)', 'print(text.byteLength)',
                      'print(text == ' + literal(value) + ')',
                      'let parts: List<Text> = []']
            expected = [str(len(value)), str(len(value.encode('utf-8'))), 'true']
            for index, scalar in enumerate(value):
                source += [f'print(text[{index}])', f'parts.add(Text(text[{index}]))']
                expected.append(scalar)
            for begin in range(len(value) + 1):
                for end in range(begin, len(value) + 1):
                    source.append(f'print(text.slice({begin}, {end}))')
                    expected.append(value[begin:end])
            source += ['let joined = joinText(parts)', 'text = "released"',
                       'print(joined)', 'writeTextFile(argument(1), joined)',
                       'print(readTextFile(argument(1)))']
            expected += [value, value]
            CompilerTestCase.executes(self, '\n'.join(source) + '\n', '\n'.join(expected) + '\n',
                          arguments=[str(original), str(output)],
                      optimizations=('-O0','-O2','-O3','-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT')=='1' else ('-O0','-O2'),
                      file_outputs=((output, value.encode('utf-8')),))

    def test_text_equality_compares_bytes_after_nul(self):
        left, right = 'abc\0def', 'abc\0xyz'
        paths = [self.directory / 'nul-left.txt', self.directory / 'nul-right.txt']
        for path, value in zip(paths, (left, right)):
            path.write_bytes(value.encode('utf-8'))
        source = ['function compare(left: Text, right: Text) {',
                  'print(left == right)', 'print(left != right)', '}',
                  'compare(' + literal(left) + ', ' + literal(right) + ')',
                  'let left = readTextFile(argument(0))', 'let right = readTextFile(argument(1))',
                  'compare(left, right)', 'compare(right, left)',
                  'compare(left, ' + literal(left) + ')',
                  'compare(right, ' + literal(right) + ')',
                  'compare(left.slice(3, 7), right.slice(3, 7))',
                  'compare(joinText([left.slice(0, 4), "def"]), left)',
                  'compare(joinText([left.slice(0, 4), "xyz"]), left)',
                  'compare("a", ' + literal('a\0') + ')',
                  'compare(' + literal('a\0') + ', "a")',
                  'compare(left.slice(0, 1), left.slice(0, 1) + ' + literal('\0') + ')',
                  'compare(joinText(["a", ' + literal('\0') + ']), "a")']
        self.executes('\n'.join(source) + '\n',
                      'false\ntrue\n' * 3 + 'true\nfalse\n' * 2 + 'false\ntrue\ntrue\nfalse\nfalse\ntrue\n' + 'false\ntrue\n' * 4,
                      arguments=list(map(str, paths)))

    def test_identical_mutable_constructor_calls_remain_independent(self):
        self.executes('''function make(): List<Integer> { return [0] }
function makeEmpty(): List<Integer> { return [] }
let first = make()
let second = make()
first[0] = 10
print(second[0])
second[0] = 20
print(first[0])
let third = make()
print(third[0])
third[0] = 30
let fourth = make()
print(fourth[0])
print(first[0])
print(second[0])
print(third[0])
let emptyFirst = makeEmpty()
let emptySecond = makeEmpty()
emptyFirst.add(10)
print(emptySecond.length)
emptySecond.add(20)
print(emptyFirst.length)
print(emptySecond.length)
print(emptyFirst[0])
print(emptySecond[0])
emptyFirst.add(30)
print(emptySecond.length)
''', '0\n10\n0\n0\n10\n20\n30\n0\n1\n1\n10\n20\n1\n')

    def test_long_record_fields_and_late_diagnostic_line(self):
        prefix = 'field' + 'x' * 300
        self.executes(f'record Wide {{ {prefix}0: Integer; {prefix}1: Integer }}\n'
                      f'function read(value: Wide): Integer {{ return value.{prefix}0 * 100 + value.{prefix}1 }}\n'
                      f'print(read(Wide {{ {prefix}0: 12; {prefix}1: 34 }}))\n', '1234\n')
        self.rejects('\n' * 300 + 'print(missingName)\n', 'line 301, column 7:')

    def test_boolean_tree_values_and_short_circuit_trace(self):
        # Enumerate two binary-tree shapes, all leaf truth values, both operators,
        # and independent negation at the two internal nodes. The host oracle
        # traverses tuples and records only actually evaluated leaf IDs.
        def evaluate(node, trace):
            if len(node) == 2:
                identity, value = node
                trace.append(identity)
                return value
            operator, negate, left, right = node
            first = evaluate(left, trace)
            result = (first and evaluate(right, trace)) if operator == '&&' else (first or evaluate(right, trace))
            return not result if negate else result

        def expression(node):
            if len(node) == 2:
                identity, value = node
                return f'mark({str(value).lower()}, {identity}, trace)'
            operator, negate, left, right = node
            body = f'({expression(left)} {operator} {expression(right)})'
            return '!' + body if negate else body

        source = ['function mark(value: Boolean, identity: Integer, trace: List<Integer>): Boolean { trace.add(identity); return value }',
                  'let trace: List<Integer> = []']
        expected = []
        for bits in range(8):
            leaves = [(index + 1, bool(bits & (1 << index))) for index in range(3)]
            for outer in ('&&', '||'):
                for inner in ('&&', '||'):
                    for negations in range(4):
                        for shape in (0, 1):
                            nested = (inner, bool(negations & 1), *leaves[shape:shape + 2])
                            node = (outer, bool(negations & 2), nested, leaves[2]) if shape == 0 else (outer, bool(negations & 2), leaves[0], nested)
                            trace = []
                            result = evaluate(node, trace)
                            source += ['trace = []', 'print(' + expression(node) + ')', 'print(trace.length)']
                            source += [f'print(trace[{index}])' for index in range(len(trace))]
                            expected += [str(result).lower(), str(len(trace)), *map(str, trace)]
        self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')
        for invalid in ('true * false', '1 && 2'):
            self.rejects('print(' + invalid + ')\n', 'Minyar stopped:')

    def test_character_integer_arithmetic_never_coerces(self):
        for parameter, argument in (('Integer', '"x"[0]'), ('Character', '120')):
            self.rejects(f'function accept(value: {parameter}) {{ print(value) }}\naccept({argument})\n',
                         'an argument passed to accept has the wrong type')
        for operator in ('+', '-', '*', '/'):
            for left, right in (('"x"[0]', '1'), ('1', '"x"[0]')):
                with self.subTest(operator=operator, left=left):
                    self.rejects(f'print({left} {operator} {right})\n', 'Minyar stopped:')
            for left, right in (('character', 'integer'), ('integer', 'character')):
                self.rejects(f'function mixed(character: Character, integer: Integer) {{ print({left} {operator} {right}) }}\n', 'Minyar stopped:')

    def test_record_operators_initializers_and_boolean_indexing_reject(self):
        declaration = 'record Box { field: Integer }\nlet left = Box { field: 1 }\nlet right = Box { field: 2 }\n'
        for operator in ('+', '-', '*', '/', '%', '==', '!=', '<', '<=', '>', '>='):
            if operator in ('==', '!='):
                diagnostic = 'records and Lists do not yet support equality'
            elif operator in ('<', '<=', '>', '>='):
                diagnostic = 'ordered comparison needs Integer or Character operands'
            else:
                diagnostic = 'needs Integer operands'
            self.rejects(declaration + f'print(left {operator} right)\n', diagnostic)
        self.rejects('record Box { field: Integer }\nlet value = Box { field: 10; field: 20 }\n',
                     "record field 'field' was provided twice")
        self.rejects('let bad = true\nprint(bad[0])\n', 'indexing needs Text or a List')
        self.rejects('let bad = true\nbad[0] = bad[0]\n', 'indexed assignment needs a List')

    def test_file_paths_reject_embedded_nul_without_touching_prefix(self):
        path = self.directory / 'existing-prefix.txt'
        contents = b'original contents\n'
        path.write_bytes(contents)
        for operation in ('print(readTextFile(path))', 'writeTextFile(path, "overwritten")'):
            with self.subTest(operation=operation):
                source = 'let path = argument(0) + ' + literal('\0suffix') + '\n' + operation + '\n'
                self.executes(source, '', 1, 'Minyar stopped: a file path cannot contain a zero byte.\n',
                              arguments=[str(path)])
                self.assertEqual(path.read_bytes(), contents)

    def test_malformed_utf8_file_corpus(self):
        corpus = [b'\xe3', b'abc\xe3def', b'\xf4\x9f\xbf', b'\xf4\x9f\xbf\xbf',
                  b'ab\xff', b'\xf4\x90\x80\x80', b'in\x80valid', b'\xbfinvalid',
                  'αλφ'.encode() + b'\xbf' + 'α'.encode(),
                  b'\xed\xa0\x80', b'\xed\xbf\xbf', b'\xc0\x80', b'\xc1\xbf',
                  b'\xe0\x9f\xbf', b'\xf0\x8f\xbf\xbf', b'\x80', b'\xbf', b'\xfe', b'\xff',
                  b'\xff' + b'\x80' * 7]
        for invalid in (b'\x80', b'\xbf'):
            corpus += ['汉字'.encode() + invalid, invalid + b'hello', b'hel' + invalid + b'lo']
        paths = []
        for index, content in enumerate(corpus):
            path = self.directory / f'invalid-{index}.txt'
            path.write_bytes(content)
            paths.append(path)
        error = 'Minyar stopped: Text contained invalid UTF-8.\n'
        # Observe successful raw ingress before the strict character operation.
        source = 'let text = readTextFile(argument(0))\nprint(text.byteLength)\nprint(text.length)\n'
        llvm = self.executes(source, f'{len(corpus[0])}\n', 1, error,
                             arguments=[str(paths[0])])
        variants = ('-O0', '-O2', '-O3', '-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1' else ('-O0', '-O2')
        for optimization in variants:
            for path, content in zip(paths[1:], corpus[1:]):
                with self.subTest(optimization=optimization, input=path.name):
                    result = self.evidence.run([llvm.with_suffix('.' + optimization[1:]), path], timeout=10, phase='execute-invalid-utf8')
                    self.assertEqual((result.returncode, result.stdout, result.stderr),
                                     (1, f'{len(content)}\n'.encode(), error.encode()))

    def test_utf8_lead_continuation_and_endpoint_vectors(self):
        fixture = ROOT / 'tests/peer-utf8-vectors.json'
        self.evidence.inputs[str(fixture.resolve())] = digest(fixture)
        data = json.loads(fixture.read_text())
        self.assertEqual(data['schema_version'], 1)
        vectors = data['vectors']
        self.assertEqual(len(vectors), 83)
        cases = []
        for index, vector in enumerate(vectors):
            raw = bytes.fromhex(vector['hex'])
            path = self.directory / f'utf8-vector-{index}.txt'
            path.write_bytes(raw)
            if vector['valid']:
                scalars = vector['codepoints']
                self.assertEqual(''.join(map(chr, scalars)).encode('utf-8'), raw)
                expected = f'{len(raw)}\n{len(scalars)}\n{len(raw)}\n'.encode() + raw + b'\n'
                expected += b''.join(chr(value).encode('utf-8') + b'\n' for value in scalars)
                cases.append((path, 0, expected, b''))
            else:
                with self.assertRaises(UnicodeDecodeError):
                    raw.decode('utf-8')
                cases.append((path, 1, f'{len(raw)}\n'.encode(), b'Minyar stopped: Text contained invalid UTF-8.\n'))
        source = '''let text = readTextFile(argument(0))
print(text.byteLength)
print(text.length)
print(text.byteLength)
print(text)
let index = 0
while index < text.length { print(text[index]); index = index + 1 }
'''
        first, status, stdout, stderr = cases[0]
        llvm = self.executes(source, stdout.decode('utf-8'), status, stderr.decode('utf-8'), arguments=[str(first)])
        variants = ('-O0', '-O2', '-O3', '-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1' else ('-O0', '-O2')
        for optimization in variants:
            for path, status, stdout, stderr in cases[1:]:
                with self.subTest(optimization=optimization, vector=path.name):
                    result = self.evidence.run([llvm.with_suffix('.' + optimization[1:]), path],
                                               timeout=10, phase='execute-utf8-vector')
                    self.assertEqual((result.returncode, result.stdout, result.stderr), (status, stdout, stderr))

    def test_unicode_width_compositions_and_cached_append_queries(self):
        fixture = ROOT / 'tests/peer-unicode-compositions.json'
        self.evidence.inputs[str(fixture.resolve())] = digest(fixture)
        data = json.loads(fixture.read_text())
        self.assertEqual(data['schema_version'], 1)
        self.assertEqual(len(data['cases']), 167)
        source = ['function compareCompositions(left: Text, right: Text) {',
                  'print(left == right)', 'print(right == left)',
                  'print(left != right)', 'print(right != left)', '}']
        expected = []
        incremental = {}
        for index, case in enumerate(data['cases']):
            kind = case['kind']
            if kind == 'incremental_append':
                incremental.setdefault(case['scalar'], []).append(case)
                continue
            source.append(f'function case{index}() {{')
            if kind == 'concat':
                self.assertEqual(case['expected'], case['left'] + case['right'])
                source += [f'let left = {literal(case["left"])}',
                           f'let right = {literal(case["right"])}', 'let alias = left',
                           'left = left + right', 'right = "released"',
                           'print(left)', 'print(left.length)', 'print(left.byteLength)', 'print(alias)']
                expected += [case['expected'], str(len(case['expected'])),
                             str(len(case['expected'].encode())), case['left']]
            elif kind == 'slice':
                self.assertEqual(case['expected'], case['text'][case['start']:case['end']])
                source += [f'let root = {literal(case["text"])}',
                           f'let view = root.slice({case["start"]}, {case["end"]})',
                           'root = "released"', 'print(view)', 'print(view.length)', 'print(view.byteLength)']
                expected += [case['expected'], str(len(case['expected'])), str(len(case['expected'].encode()))]
            else:
                self.assertEqual(kind, 'equality')
                self.assertEqual(case['expected'], case['left'] == case['right'])
                left_path = self.directory / f'composition-left-{index}.txt'
                right_path = self.directory / f'composition-right-{index}.txt'
                left_path.write_text(case['left'], encoding='utf-8')
                right_path.write_text(case['right'], encoding='utf-8')
                source += [f'let left = {literal(case["left"])}', f'let right = {literal(case["right"])}',
                           'print(left == right)', 'print(right == left)',
                           'print(left != right)', 'print(right != left)',
                           'compareCompositions(left, right)',
                           f'compareCompositions(readTextFile({literal(str(left_path))}), '
                           f'readTextFile({literal(str(right_path))}))']
                expected += ([str(case['expected']).lower()] * 2 +
                             [str(not case['expected']).lower()] * 2) * 3
            source += ['}', f'case{index}()']
        for scalar, cases in incremental.items():
            self.assertEqual([case['count'] for case in cases], list(range(1, 6)))
            source += [f'function append{scalar}() {{', 'let text = ""']
            for case in cases:
                self.assertEqual(case['expected'], chr(scalar) * case['count'])
                source.append(f'text = text + {literal(chr(scalar))}')
                for _ in range(2):
                    source += ['print(text)', 'print(text.length)', 'print(text.byteLength)']
                    expected += [case['expected'], str(case['count']), str(len(case['expected'].encode()))]
                    source += [f'print(text[{index}])' for index in range(case['count'])]
                    expected += list(case['expected'])
            source += ['}', f'append{scalar}()']
        self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')

    def test_signed_comparisons_preserve_boolean_values(self):
        values = (-9223372036854775808, -9223372036854775807, -4611686018427387904, -123, -1, 0, 1, 123, 4294967295, 4611686018427387903, 9223372036854775806, 9223372036854775807)
        operations = [('==', lambda a, b: a == b), ('!=', lambda a, b: a != b),
                      ('<', lambda a, b: a < b), ('<=', lambda a, b: a <= b),
                      ('>', lambda a, b: a > b), ('>=', lambda a, b: a >= b)]
        source = ['function identity(value: Boolean): Boolean { return value }']
        expected = []
        for index, (symbol, oracle) in enumerate(operations):
            source.append(f'function compare{index}(a: Integer, b: Integer): Boolean {{ return a {symbol} b }}')
            for a in values:
                for b in values:
                    source += [f'print(identity({a} {symbol} {b}))',
                               f'print(identity(compare{index}({a}, {b})))']
                    expected += [str(oracle(a, b)).lower()] * 2
        source += ['function atMost(a: Integer, b: Integer): Boolean { return a < b || a == b }',
                   'function greater(a: Integer, b: Integer): Boolean { return a > b && a != b }',
                   'function negatedRange(a: Integer, b: Integer): Boolean { return !(a < b || a == b) }']
        for a in values:
            for b in values:
                source += [f'print(atMost({a}, {b}))', f'print(greater({a}, {b}))', f'print(negatedRange({a}, {b}))']
                expected += [str(a <= b).lower(), str(a > b).lower(), str(a > b).lower()]
        self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')

    def test_signed64_arithmetic_runtime_matrix(self):
        minimum, maximum = -(1 << 63), (1 << 63) - 1
        values = (0, 1, 2, -1, -2, maximum, maximum - 1, minimum, minimum + 1)
        source = ['function operand(value: Text): Integer {']
        source += [f'if value == "{value}" {{ return {value} }}' for value in values]
        source += ['fail("unknown matrix operand")', '}', 'let operation = argument(0)',
                   'let a = operand(argument(1))', 'let b = operand(argument(2))']
        for index, symbol in enumerate(('+', '-', '*', '/', '%')):
            source.append(f'if operation == "{symbol}" {{ print(a {symbol} b) }}')
        source += ['if operation == "negate" { print(-a) }']
        llvm = self.executes('\n'.join(source) + '\n', '0\n', arguments=['+', '0', '0'])
        cases = []
        for symbol in ('+', '-', '*', '/', '%'):
            for a in values:
                for b in values:
                    error = None
                    if symbol in ('/', '%') and b == 0:
                        error = ZERO
                    elif symbol in ('/', '%') and a == minimum and b == -1:
                        error = 'Minyar stopped: this Integer division is outside the supported range.\n'
                    elif symbol == '+': result = a + b
                    elif symbol == '-': result = a - b
                    elif symbol == '*': result = a * b
                    else:
                        quotient = abs(a) // abs(b)
                        if (a < 0) != (b < 0): quotient = -quotient
                        result = quotient if symbol == '/' else a - quotient * b
                    if error is None and not minimum <= result <= maximum:
                        error = OVERFLOW
                    cases.append(([symbol, str(a), str(b)], '' if error else str(result) + '\n', error or ''))
        for a in values:
            error = OVERFLOW if a == minimum else ''
            cases.append((['negate', str(a), '0'], '' if error else str(-a) + '\n', error))
        self.evidence.controls['integer_matrix_oracles'] = [
            {'arguments': arguments, 'stdout': stdout, 'stderr': stderr, 'status': int(bool(stderr))}
            for arguments, stdout, stderr in cases]
        variants = ('-O0', '-O2', '-O3', '-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1' else ('-O0', '-O2')
        for optimization in variants:
            for arguments, stdout, stderr in cases:
                with self.subTest(optimization=optimization, arguments=arguments):
                    result = self.evidence.run([llvm.with_suffix('.' + optimization[1:]), *arguments], timeout=10, phase='execute-integer-matrix')
                    self.assertEqual((result.returncode, result.stdout, result.stderr),
                                     (int(bool(stderr)), stdout.encode(), stderr.encode()))

    def test_ascii_identifier_policy_rejects_confusables(self):
        fragments = [
            'let $ = 1',
            'let $$ = 1',
            'let Σ$ = 1',
            'let $Σ = 1',
            'let\xa0x = 1',
            'let\u3000x = 1',
            'let ༀ = 1',
            'let 𑩐 = 1',
            'let 𐠈 = 1',
            'let ꙮ = 1',
            'let 𝛛 = 1',
            'let ₉ = 1',
            'let a¹b₍₄₂₎∇ = 1',
            'let 🌹 = 1',
            'let 🫎 = 1',
            'let 👷 = 1',
            'let 👷\u200d♀ = 1',
            'let 🌵 = 1',
            'let 🌻 = 1',
            'let 🌷 = 1',
            'let n; = 1',
            'let n꞉꞉v = 1',
            'let v＝［＝］（auto）｛return～x；｝（） = 1',
            'let \u2060x\ufeffx\u200d = 1',
            'let ∣foo = 1',
            'let foo\u200bbar = 1',
            'let a\xa0b = 1',
            'let a¹b = 1',
            'let a;b = 1',
            'let aΣb = 1',
            'let aༀb = 1',
            'let a\u200bb = 1',
            'let a\u200db = 1',
            'let a\u2060b = 1',
            'let a₂b = 1',
            'let a₄b = 1',
            'let a₉b = 1',
            'let a₍b = 1',
            'let a₎b = 1',
            'let a∇b = 1',
            'let a∣b = 1',
            'let a♀b = 1',
            'let a\u3000b = 1',
            'let aꙮb = 1',
            'let a꞉b = 1',
            'let a\ufeffb = 1',
            'let a（b = 1',
            'let a）b = 1',
            'let a；b = 1',
            'let a＝b = 1',
            'let a［b = 1',
            'let a］b = 1',
            'let a｛b = 1',
            'let a｝b = 1',
            'let a～b = 1',
            'let a𐠈b = 1',
            'let a𑩐b = 1',
            'let a𝛛b = 1',
            'let a🌵b = 1',
            'let a🌷b = 1',
            'let a🌹b = 1',
            'let a🌻b = 1',
            'let a👷b = 1',
            'let a🫎b = 1',
        ]
        for fragment in fragments:
            with self.subTest(fragment=fragment):
                self.rejects(fragment + "\n", "Minyar stopped:")
        self.rejects("let foobar = 1\nprint(foo\u200bbar)\n", "names must use ASCII")

    def test_character_literal_requires_one_scalar(self):
        values = 'က⌘Ø👿👽'
        self.executes(''.join("print('" + value + "')\n" for value in values), '\n'.join(values) + '\n')
        for value in ('ab', 'aက', 'APPS'):
            self.rejects("print('" + value + "')\n", 'Character literal must contain exactly one character')

    def test_logical_not_types_values_and_whitespace(self):
        self.executes('''record Box { prop: Boolean }
let value = Box { prop: true }
let x = true
print(!true)
print(!(!true))
print(!x)
print(!(!x))
print(!value.prop)
print(!false)
''', 'false\ntrue\nfalse\ntrue\nfalse\ntrue\n')
        for whitespace in ('\t', ' ', '\n', '\r'):
            self.executes('print(!' + whitespace + 'true)\n', 'false\n')
        for whitespace in ('\v', '\f', '\u00a0', '\u2028', '\u2029', '\t\v\f \u00a0\n\r\u2028\u2029'):
            self.rejects('print(!' + whitespace + 'true)\n', 'Minyar stopped:')
        for operand in ('missing', '0', '(-0)', '13', '(-13)', '1', '-1',
                        '"1"', '"x"', '""', '" "', '"Nonempty String"'):
            self.rejects('print(!' + operand + ')\n', 'Minyar stopped:')

    def test_power_of_two_neighbor_cancellation(self):
        for start in range(2, 63, 8):
            source = ['function localPair(left: Integer, right: Integer) {',
                      'print(left + right)', 'print(-left - right)', '}']
            expected = []
            for exponent in range(start, min(start + 8, 63)):
                power = 1 << exponent
                for small in range(-3, 4):
                    other = power - small
                    # Literal/literal, local/local and both mixed placements.
                    source += [f'print({small} + {other})', f'print(-({small}) - {other})',
                               f'localPair({small}, {other})',
                               f'let left{exponent}_{small + 3} = {small}',
                               f'let right{exponent}_{small + 3} = {other}',
                               f'print(left{exponent}_{small + 3} + {other})',
                               f'print(-left{exponent}_{small + 3} - {other})',
                               f'print({small} + right{exponent}_{small + 3})',
                               f'print(-({small}) - right{exponent}_{small + 3})']
                    expected += [str(power), str(-power)] * 4
            self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')

    def test_full_int32_constant_divisor_domain(self):
        # Exact finite input domain recorded from V8 division-by-constant.js.
        # Minyar uses signed64; exclude the upstream int32 wraparound pair.
        values = [-2147483648, 715827883, 1431655766, -1431655765, -1431655764,
                  123, -1234, 12345, -123456, 1234567, -12345678, 123456789]
        positive = [1 << shift for shift in range(6, 31)] + list(range(1, 33))
        positive += [10 ** magnitude + offset for magnitude in range(2, 10) for offset in range(10)]
        values += [signed for value in positive for signed in (value, -value)]
        self.assertEqual((len(values), len(set(values))), (286, 286))
        self.evidence.controls['division_domain'] = {
            'values': values, 'excluded_pair': [-2147483648, -1],
            'pairs': 81795, 'operations': ['division', 'remainder'],
            'placements': ['constant-divisor', 'parameter-divisor'],
        }
        checked = 0
        # Bound compiler input size while preserving every Cartesian pair.
        for start in range(0, len(values), 16):
            source = ['function divide(a: Integer, b: Integer): Integer { return a / b }',
                      'function remainder(a: Integer, b: Integer): Integer { return a % b }']
            for offset, divisor in enumerate(values[start:start + 16]):
                source += [f'function constant{offset}(a: Integer) {{',
                           f'print(a / ({divisor}))', f'print(a % ({divisor}))', '}']
            source += ['let values = [' + ', '.join(map(str, values)) + ']']
            expected = []
            for offset, divisor in enumerate(values[start:start + 16]):
                source += ['let index = 0', 'while index < values.length {',
                           'let value = values[index]']
                if divisor == -1:
                    source.append('if value != -2147483648 {')
                source += [f'constant{offset}(value)', f'print(divide(value, {divisor}))',
                           f'print(remainder(value, {divisor}))']
                if divisor == -1:
                    source.append('}')
                source += ['index = index + 1', '}']
                for value in values:
                    if (value, divisor) == (-2147483648, -1):
                        continue
                    quotient = abs(value) // abs(divisor)
                    if (value < 0) != (divisor < 0):
                        quotient = -quotient
                    remainder = value - quotient * divisor
                    expected += [str(quotient), str(remainder)] * 2
                    checked += 1
            self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')
        self.assertEqual(checked, 81795)

    def test_long_near_identical_identifiers(self):
        first, second = 'a' * 15000 + '1', 'a' * 15000 + '2'
        self.executes(f'let {first} = 5\nlet {second} = 6\nprint({first})\nprint({second})\nprint({first} - {second})\n',
                      '5\n6\n-1\n')

    def test_ignored_call_result_preserves_live_argument(self):
        self.executes('''function ignored(trace: List<Integer>): Integer {
trace.add(23)
return 23
}
function consume(value: Integer, trace: List<Integer>) {
print(value)
print(trace.length)
print(trace[0])
}
function caller(value: Integer, trace: List<Integer>) {
ignored(trace)
consume(value, trace)
}
let trace: List<Integer> = []
caller(42, trace)
''', '42\n1\n23\n')

    def test_repeated_and_shifted_call_arguments(self):
        self.executes('''function weighted(a: Integer, b: Integer, c: Integer): Integer {
return 100 * a + 10 * b + c
}
function caller(a: Integer, b: Integer) {
print(weighted(1, a, b))
print(weighted(b, b, b))
print(a)
print(b)
}
caller(42, 7)
caller(7, 42)
''', '527\n777\n42\n7\n212\n4662\n7\n42\n')

    def test_loop_sentinels_nested_state_and_dead_inner_loop(self):
        self.executes('''let line = ""
let index = 0
while line != "exit" {
if index == 9 { line = "exit" } else { line = "notexit" }
index = index + 1
}
print(index)
print(line)
let ones: List<Integer> = []
let twos: List<Integer> = []
index = 0
while index < 100 { ones.add(1); twos.add(2); index = index + 1 }
let p = 0
let q = 0
index = 0
while index < ones.length {
let inner = 0
while inner < twos.length { p = p + twos[inner]; inner = inner + 1 }
q = q + ones[index] + p
index = index + 1
}
print(p)
print(q)
let y = 42
let z = 42
let iterations = 0
while z < 50 {
z = z + 1
iterations = iterations + 1
while false { y = 0 }
}
print(y)
print(z)
print(iterations)
''', '10\nexit\n20000\n1010100\n42\n50\n8\n')

    def test_owned_condition_temporaries_include_final_false_check(self):
        self.executes('''function condition(counter: List<Integer>): Text {
let value = counter[0]
counter[0] = value + 1
return Text(value) + "!"
}
function leave(counter: List<Integer>) {
let text = Text(counter[0]) + "hej"
while text != condition(counter) { return }
fail("unexpected equal condition")
}
let counter = [0]
let iterations = 0
while condition(counter) != "9!" { iterations = iterations + 1 }
print(iterations)
print(counter[0])
if condition(counter) == "10!" { print("matched") }
if condition(counter) == "12!" { print("unexpected") }
print(counter[0])
leave(counter)
print(counter[0])
print("returned")
''', '9\n10\nmatched\n12\n13\nreturned\n')

    def test_euclidean_gcd_and_lcm_integer_workloads(self):
        gcd_cases = [(0, 5, 5), (5, 0, 5), (8, 12, 4), (12, 8, 4),
                     (33, 77, 11), (77, 33, 11), (49865, 69811, 9973),
                     (300000, 2300000, 100000)]
        lcm_cases = [(0, 0, 0), (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0),
                     (7, 1, 7), (7, -1, 7), (8, 12, 24), (-23, 15, 345),
                     (120, 84, 840), (84, -120, 840)]
        source = ['''function gcd(first: Integer, second: Integer): Integer {
let a = first
let b = second
while b != 0 { let remainder = a % b; a = b; b = remainder }
return a
}
function lcm(first: Integer, second: Integer): Integer {
if first == 0 || second == 0 { return 0 }
let a = first
let b = second
if a < 0 { a = -a }
if b < 0 { b = -b }
return (a / gcd(a, b)) * b
}
''']
        expected = []
        for name, cases in (('gcd', gcd_cases), ('lcm', lcm_cases)):
            for a, b, result in cases:
                source.append(f'print({name}({a}, {b}))')
                expected.append(str(result))
        self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')

    def test_discarded_owned_results_and_temporary_record_arguments(self):
        self.executes('''record Wrapper { text: Text }
function makeText(index: Integer): Text { return Text(index) + "!" }
function makeRecord(index: Integer): Wrapper { return Wrapper { text: makeText(index) } }
function discard() {
let named = makeRecord(1)
makeRecord(3)
let text = makeText(2)
makeText(4)
}
function say(value: Wrapper) { print(value.text) }
function paths(index: Integer) {
let text = Text(index) + "!"
if index == 1 { print("early"); return }
print(text)
}
discard()
let named = Wrapper { text: "B" + "ob" }
say(named)
say(Wrapper { text: "B" + "ob" })
let index = 0
while index < 2 { paths(index); index = index + 1 }
print("done")
''', 'Bob\nBob\n0!\nearly\ndone\n')

    def test_changing_index_short_circuit_loop_and_blank_output(self):
        self.executes('''let values = [0, 1, 2]
let index = 1
while index > 0 && values[index] != 2 { index = index + 1 }
print(index)
index = -1
while index > 0 && values[index] != 2 { fail("unexpected") }
print(index)
print("A")
print("")
print("B")
''', '2\n-1\nA\n\nB\n')

    def test_induction_indexed_division_and_remainder_cancellation(self):
        maximum = (1 << 63) - 1
        expected = ['1', '1']
        expected += [str(value) for n in range(1, 20) for value in (n, maximum % n)]
        self.executes('''let index = 1
let count = 0
while index <= 11 {
if index - 6 > 4 { count = count + 1 }
index = index + 1
}
print(count)
let values = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
index = 0
let numerator = 10
let denominator = 7
values[index] = numerator / denominator
print(values[0])
function rounded(n: Integer): Integer { return 9223372036854775807 - 9223372036854775807 % n }
index = 1
while index < 20 {
print(index)
print(9223372036854775807 - rounded(index))
index = index + 1
}
''', '\n'.join(expected) + '\n')

    def test_descending_list_shift_pretested_and_posttested_loops(self):
        source = ['''function shift(bound: Integer, posttested: Boolean) {
let values = [5, 6, 7, 8]
let index = 3
if posttested { values[index] = values[index - 1]; index = index - 1 }
while index > bound { values[index] = values[index - 1]; index = index - 1 }
print(bound)
index = 0
while index < values.length { print(values[index]); index = index + 1 }
}
''']
        expected = []
        initial = [5, 6, 7, 8]
        for posttested in (False, True):
            for bound in (0, 1, 2, 3, 4, 4294967295):
                source.append(f'shift({bound}, {str(posttested).lower()})')
                result = [initial[index - 1] if index > bound or (posttested and index == 3)
                          else initial[index] for index in range(4)]
                expected += [str(bound), *map(str, result)]
        source += ['''function observe(value: Integer): Integer { print(value); return value }
let values = [0, 0, 0, 0]
let index = 3
while index >= 0 { values[index] = observe(5 + index); index = index - 1 }
index = 0
while index < values.length { observe(values[index]); index = index + 1 }
''']
        expected += list(map(str, (8, 7, 6, 5, 5, 6, 7, 8)))
        self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')

    def test_parameterized_nested_list_dimensions_and_cells(self):
        self.executes('''function fill2(values: List<List<Integer>>, width: Integer) {
let number = 1
let i = 0
while i < values.length {
let row = values[i]
let j = 0
while j < width { row[j] = number; number = number + 1; j = j + 1 }
i = i + 1
}
}
function fill3(values: List<List<List<Integer>>>, width: Integer, depth: Integer) {
let number = 1
let i = 0
while i < values.length {
let j = 0
while j < width {
let row = values[i][j]
let k = 0
while k < depth { row[k] = number; number = number + 1; k = k + 1 }
j = j + 1
}
i = i + 1
}
}
let matrix: List<List<Integer>> = []
let i = 0
while i < 4 { matrix.add([0, 0, 0]); i = i + 1 }
let cube: List<List<List<Integer>>> = []
i = 0
while i < 2 {
let plane: List<List<Integer>> = []
let j = 0
while j < 3 { plane.add([0, 0, 0, 0]); j = j + 1 }
cube.add(plane)
i = i + 1
}
fill2(matrix, 3)
fill3(cube, 3, 4)
i = 0
while i < matrix.length {
let j = 0
while j < matrix[i].length { print(matrix[i][j]); j = j + 1 }
i = i + 1
}
i = 0
while i < cube.length {
let j = 0
while j < cube[i].length {
let k = 0
while k < cube[i][j].length { print(cube[i][j][k]); k = k + 1 }
j = j + 1
}
i = i + 1
}
''', ''.join(str(value) + '\n' for value in [*range(1, 13), *range(1, 25)]))

    def test_nested_branch_keeps_text_live_across_join(self):
        self.executes('''function branch(enabled: Boolean, kind: Integer, nested: Boolean, text: Text, trace: List<Text>) {
if kind == 1 {
if enabled {
let output = text
if nested { print("unexpected") }
trace.add(output)
}
}
}
let trace: List<Text> = []
let text = "ao" + "eu"
branch(true, 2, false, text, trace)
print(trace.length)
branch(false, 1, false, text, trace)
print(trace.length)
branch(true, 1, false, text, trace)
text = "replaced"
print(trace.length)
print(trace[0])
''', '0\n0\n1\naoeu\n')

    def test_fresh_allocation_is_consumed_and_dropped_each_iteration(self):
        expected = sum(len(str(index) + '!') for index in range(100000))
        self.executes('''function consume(index: Integer): Integer {
let text = Text(index) + "!"
return text.length
}
let index = 0
let checksum = 0
while index < 100000 {
checksum = checksum + consume(index)
index = index + 1
}
print(index)
print(checksum)
''', f'100000\n{expected}\n')

    def test_alternating_retained_and_discarded_large_allocations(self):
        # Preserve the upstream ten rounds / hundred alternating objects. Minyar
        # frame cleanup replaces Go's GC; secret erasure is not claimed here.
        padding = 'x' * 1024
        self.executes(f'''record Payload {{ id: Integer, text: Text }}
function populate(round: Integer, retained: List<Payload>) {{
let index = 0
while index < 100 {{
let id = round * 100 + index
let payload = Payload {{ id: id, text: Text(id) + {literal(padding)} }}
if index % 2 == 0 {{ retained.add(payload) }}
index = index + 1
}}
}}
function churn(round: Integer) {{
let index = 0
while index < 100 {{
let transient = Text(round * 100 + index) + {literal('y' * 1024)}
if transient.length < 1025 {{ print("bad transient") }}
index = index + 1
}}
}}
let round = 0
while round < 10 {{
let retained: List<Payload> = []
populate(round, retained)
churn(round)
churn(round)
print(retained.length)
let index = 0
while index < retained.length {{
let expected = round * 100 + index * 2
let payload = retained[index]
print(payload.id)
print(payload.text == Text(expected) + {literal(padding)})
index = index + 1
}}
round = round + 1
}}
''', ''.join('50\n' + ''.join(f'{round * 100 + index * 2}\ntrue\n'
                                    for index in range(50)) for round in range(10)))

    def test_record_returns_recursive_results_and_argument_permutations(self):
        parameters = ', '.join(f'v{index}: Integer' for index in range(26))
        reverse = ', '.join(f'v{index}' for index in reversed(range(26)))
        prints = '\n'.join(f'print(v{index})' for index in range(26))
        source = f"function output({parameters}) {{ {prints} }}\n"
        source += f"function reverse({parameters}) {{ output({reverse}) }}\n"
        source += 'reverse(' + ', '.join(str(index) for index in range(1, 27)) + ')\n'
        source += '''record Four { a: Integer, b: Integer, c: Integer, d: Integer }
function arithmetic(x: Four): Four {
let ab = x.a + x.b
let bc = x.b + x.c
let cd = x.c + x.d
let ad = x.a + x.d
let ba = x.a - x.b
let cb = x.b - x.c
let dc = x.c - x.d
let da = x.a - x.d
return Four { a: ab * bc + da, b: cd * ad + cb, c: ba * cb + ad, d: dc * da + bc }
}
let result = arithmetic(Four { a: 1, b: 2, c: 3, d: 4 })
print(result.a)
print(result.b)
print(result.c)
print(result.d)
record Five { a: Integer, b: Integer, c: Integer, d: Integer, e: Integer }
function make(): Five { return Five { a: 1, b: 2, c: 3, d: 4, e: 5 } }
function compare(s: Five, t: Five) {
print(s.a == t.a && s.b == t.b && s.c == t.c && s.d == t.d && s.e == t.e)
}
let a = make()
let b = make()
compare(b, b)
compare(a, make())
if a.a == 1 { a = make() }
compare(a, a)
function store(x: Integer, y: Integer, values: List<Integer>) {
if x < 0 { print("unexpected") }
values.add(x)
values.add(y)
values.add(x)
values.add(y)
}
let values: List<Integer> = []
store(1, 2, values)
print(values[0])
print(values[1])
print(values[2])
print(values[3])
record Words { a: Text, b: Text, c: Text }
function join(words: Words): Text { return words.a + " " + words.b + " " + words.c }
print(join(Words { a: "Hel" + "lo", b: "the" + "re,", c: "Wor" + "ld" }))
record Pair { a: Integer, b: Integer }
function recursive(x: Integer): Pair {
if x < 3 { return Pair { a: 0, b: x } }
let first = recursive(x - 2)
let second = recursive(x - 1)
return Pair { a: first.a + second.b, b: first.b + second.a }
}
let small = recursive(12)
print(small.a)
print(small.b)
let larger = recursive(20)
print(larger.a)
print(larger.b)
'''
        # Iterative independent oracle avoids mirroring the recursive lowering.
        pairs = [(0, index) for index in range(3)]
        for index in range(3, 21):
            pairs.append((pairs[index - 2][0] + pairs[index - 1][1],
                          pairs[index - 2][1] + pairs[index - 1][0]))
        expected = [*range(26, 0, -1), 12, 34, 6, 8, 'true', 'true', 'true',
                    1, 2, 1, 2, 'Hello there, World', *pairs[12], *pairs[20]]
        self.executes(source, ''.join(str(value) + '\n' for value in expected))

    def test_integer_power_algorithms(self):
        self.executes('''function powerOfTwo(value: Integer): Boolean {
if value <= 0 { return false }
let remaining = value
while remaining > 1 {
if remaining % 2 != 0 { return false }
remaining = remaining / 2
}
return true
}
function power(base: Integer, exponent: Integer): Integer {
let result = 1
let index = 0
while index < exponent { result = result * base; index = index + 1 }
return result
}
function nextPowerOfTwo(value: Integer): Integer {
let result = 1
while result < value { result = result * 2 }
return result
}
print(powerOfTwo(0))
print(powerOfTwo(32))
print(powerOfTwo(33))
print(power(3, 5))
print(nextPowerOfTwo(3))
''', 'false\ntrue\nfalse\n243\n4\n')

    def test_recursive_hanoi_argument_permutation_trace(self):
        # Fixed source oracle, independent of the recursive implementation.
        moves = [(1, 3), (1, 2), (3, 2), (1, 3), (2, 1), (2, 3), (1, 3),
                 (1, 2), (3, 2), (3, 1), (2, 1), (3, 2), (1, 3), (1, 2), (3, 2)]
        self.executes('''function hanoi(disks: Integer, start: Integer, end: Integer, via: Integer) {
if disks == 1 {
print("Move disk from pole " + Text(start) + " to pole " + Text(end))
} else {
hanoi(disks - 1, start, via, end)
hanoi(1, start, end, via)
hanoi(disks - 1, via, end, start)
}
}
print("Towers of Hanoi, 4 disks")
hanoi(4, 1, 2, 3)
''', 'Towers of Hanoi, 4 disks\n' + ''.join(f'Move disk from pole {a} to pole {b}\n' for a, b in moves))

    def test_decimal_and_boolean_text_conversion_widths(self):
        values = [-9223372036854775808, -9223372036854775807, -4294967297, -4294967296, -4294967295, -2147483649, -2147483648, -2147483647, -987654321, -1, 0, 1, 12, 123, 1234, 12345, 123456, 1234567, 12345678, 123456789, 1234567890, 2147483647, 2147483648, 2147483649, 4294967295, 4294967296, 4294967297, 12345678901, 123456789012, 1234567890123, 12345678901234, 123456789012345, 1125899906842624, 1234567890123456, 12345678901234567, 123456789012345678, 1234567890123456789, 9223372036854775807]
        source = ['''function integerText(value: Integer) {
let converted = Text(value)
let prefixed = "abc" + converted
print(converted)
print(converted.length)
print(converted.byteLength)
print(prefixed)
print(prefixed.length)
}
function booleanText(value: Boolean) {
let converted = Text(value)
let prefixed = "foo " + converted
print(converted)
print(converted.length)
print(prefixed)
print(prefixed.length)
}
''']
        expected = []
        for value in values:
            source.append(f'integerText({value})')
            text = str(value)
            expected += [text, str(len(text)), str(len(text)), 'abc' + text, str(len(text) + 3)]
        for value in (False, True):
            text = str(value).lower()
            source.append(f'booleanText({text})')
            expected += [text, str(len(text)), 'foo ' + text, str(len(text) + 4)]
        self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')

    def test_nested_text_record_returns_and_field_permutations(self):
        self.executes('''record Pair { a: Text, b: Text }
record Nested { x: Pair, y: Pair }
function make(a: Text, b: Text, c: Text, d: Text): Nested {
return Nested { x: Pair { a: a, b: b }, y: Pair { a: c, b: d } }
}
function makeReverse(d: Text, c: Text, b: Text, a: Text): Nested { return make(a, b, c, d) }
function reverse(value: Nested): Nested {
return make(value.y.b, value.y.a, value.x.b, value.x.a)
}
function join(value: Nested): Text { return value.x.a + " " + value.x.b + " " + value.y.a + " " + value.y.b }
print(join(make("th" + "is", "i" + "s", "" + "a", "te" + "st")))
let original = makeReverse("th" + "is", "i" + "s", "" + "a", "te" + "st")
let reordered = reverse(original)
print(join(reordered))
print(join(original))
original = make("gone", "gone", "gone", "gone")
print(join(reordered))
record Words { a: Text, b: Text, c: Text }
function words(a: Text, b: Text, c: Text): Words { return Words { a: a, b: b, c: c } }
function sentence(value: Words): Text { return value.a + " " + value.b + " " + value.c }
print(sentence(words("Ah" + "oy", "the" + "re,", "Ma" + "tey")))
''', 'this is a test\nthis is a test\ntest a is this\nthis is a test\nAhoy there, Matey\n')

    def test_prime_filter_pipeline_with_owned_lists(self):
        primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47,
                  53, 59, 61, 67, 71, 73, 79, 83, 89, 97]
        self.executes('''function filter(values: List<Integer>, divisor: Integer): List<Integer> {
let result: List<Integer> = []
let index = 0
while index < values.length {
if values[index] % divisor != 0 { result.add(values[index]) }
index = index + 1
}
return result
}
let candidates: List<Integer> = []
let value = 2
while value < 100 { candidates.add(value); value = value + 1 }
let primes: List<Integer> = []
while candidates.length > 0 {
let prime = candidates[0]
primes.add(prime)
candidates = filter(candidates, prime)
}
print(primes.length)
let index = 0
while index < primes.length { print(primes[index]); index = index + 1 }
''', '25\n' + ''.join(f'{prime}\n' for prime in primes))

    def test_smooth_number_merge_suppresses_duplicate_candidates(self):
        expected = [2, 3, 4, 5, 6, 8, 9, 10, 12, 15, 16, 18, 20, 24, 25, 27, 30, 32, 36, 40, 45, 48, 50, 54, 60, 64, 72, 75, 80, 81, 90, 96, 100, 108, 120, 125, 128, 135, 144, 150, 160, 162, 180, 192, 200, 216, 225, 240, 243, 250, 256, 270, 288, 300, 320, 324, 360, 375, 384, 400, 405, 432, 450, 480, 486, 500, 512, 540, 576, 600, 625, 640, 648, 675, 720, 729, 750, 768, 800, 810, 864, 900, 960, 972, 1000, 1024, 1080, 1125, 1152, 1200, 1215, 1250, 1280, 1296, 1350, 1440, 1458, 1500, 1536, 1600]
        self.executes('''let values: List<Integer> = [1]
let two = 0
let three = 0
let five = 0
let count = 0
while count < 100 {
let a = values[two] * 2
let b = values[three] * 3
let c = values[five] * 5
let next = a
if b < next { next = b }
if c < next { next = c }
values.add(next)
print(next)
if a == next { two = two + 1 }
if b == next { three = three + 1 }
if c == next { five = five + 1 }
count = count + 1
}
''', ''.join(f'{value}\n' for value in expected))

    def test_returned_text_observes_alias_mutation_without_clobbering_local(self):
        texts = ['OKAY! Aloha! Hello World! !!!!!!!!!!!!!!!', 'Aloha! Hello Pal!',
                 'OKAY! Aloha! Hello World!', 'Aloha! Hello Pal!']
        expected = ['1', '6', '27', '21']
        for text in texts:
            expected += [str(len(text)), text]
        self.executes('''function observe(value: Integer, state: List<Integer>) {
state[0] = state[0] + value
print(state[0])
}
function total(a: Integer, b: Integer, c: Integer, state: List<Integer>): Integer {
let result = a
observe(result, state)
result = result + b
observe(result, state)
result = result + c
observe(result, state)
return result
}
function mutate(cell: List<Text>) { cell[0] = cell[0] + " !!!!!!!!!!!!!!!" }
function shared(s: Text, t: Text, cell: List<Text>): Text {
cell[0] = "Aloha! " + s + " " + t
let prefix = ""
if s.length <= t.length { prefix = "OKAY! "; mutate(cell) }
return prefix + cell[0]
}
function separate(s: Text, t: Text, cell: List<Text>): Text {
let result = "Aloha! " + s + " " + t
let prefix = ""
if s.length <= t.length { prefix = "OKAY! "; mutate(cell) }
return prefix + result
}
function show(text: Text) { print(text.length); print(text) }
let state: List<Integer> = [0]
print(total(1, 4, 16, state))
let cell: List<Text> = [""]
show(shared("Hello", "World!", cell))
show(shared("Hello", "Pal!", cell))
show(separate("Hello", "World!", cell))
show(separate("Hello", "Pal!", cell))
''', '\n'.join(expected) + '\n')

    def test_oversized_decimal_literals_reject_cleanly(self):
        for length in (512, 513, 9998, 9999):
            with self.subTest(length=length):
                self.rejects('let value = ' + '9' * length + '\n',
                             'Integer literal is outside the supported range')

    def test_record_initializers_evaluate_in_source_order(self):
        self.executes('''record Fields { first: Integer, second: Integer, third: Integer }
function next(expected: Integer, counter: List<Integer>): Integer {
if counter[0] != expected { fail("initializer order changed") }
counter[0] = counter[0] + 1
return counter[0]
}
function make(counter: List<Integer>): Fields {
return Fields { first: next(0, counter), third: next(1, counter), second: next(2, counter) }
}
let counter: List<Integer> = [0]
let fields = make(counter)
print(fields.first)
print(fields.second)
print(fields.third)
print(counter[0])
''', '1\n3\n2\n3\n')

    def test_text_call_arguments_and_concatenations_keep_evaluation_order(self):
        self.executes('''function next(index: Integer, counter: List<Integer>): Text {
let lower = "abcdefghi"
let upper = "ABCDEFGHI"
let text = Text(lower[counter[0]]) + Text(upper[index - 1])
counter[0] = counter[0] + 1
return text
}
function join(left: Text, right: Text): Text { return left + right }
let counter: List<Integer> = [0]
let first = next(1, counter) + next(2, counter)
let second = join(next(3, counter), next(4, counter))
let third = next(5, counter) + next(6, counter) + next(7, counter) + next(8, counter) + next(9, counter)
print(first)
print(second)
print(third)
print(counter[0])
''', 'aAbB\ncCdD\neEfFgGhHiI\n9\n')

    def test_earlier_text_argument_survives_later_slot_replacement(self):
        self.executes('''function dynamic(value: Integer): Text {
let text = "x" + Text(value)
return text.slice(1, text.length)
}
function rewrite(holder: List<Text>): Text {
holder[0] = dynamic(22)
return holder[0]
}
function churn() {
let i = 0
while i < 100 {
let text = "allocation-" + Text(i)
if text.length < 12 { fail("short allocation") }
i = i + 1
}
}
function consume(first: Text, second: Text) {
churn()
print(first)
print(second)
}
function replaceInside(first: Text, holder: List<Text>) {
holder[0] = dynamic(22)
churn()
print(first)
print(holder[0])
}
let holder: List<Text> = [dynamic(1)]
consume(holder[0], rewrite(holder))
print(holder[0])
holder[0] = dynamic(1)
replaceInside(holder[0], holder)
print(holder[0])
''', '1\n22\n22\n1\n22\n22\n')

    def test_incomplete_list_call_index_slice_and_grouping_prefixes(self):
        numbers = 'let a = 1\nlet b = 2\nlet c = 3\n'
        call = 'function a(b: Integer, c: Integer, d: Integer): Integer { return b + c + d }\nlet b = 1\nlet c = 2\n'
        indexing = 'let a: List<Integer> = [1, 2, 3]\nlet b = 0\n'
        slicing = 'let a = "abc"\nlet b = 0\nlet c = 1\n'
        cases = [(numbers, prefix) for prefix in ('(', '(a', '[', '[a', '[a,', '[a,b', '[a,b,')]
        cases += [(call, prefix) for prefix in ('a(', 'a(b', 'a(b,', 'a(b,c', 'a(b,c,')]
        cases += [(indexing, prefix) for prefix in ('a[', 'a[b')]
        # Python's slice colon becomes Minyar's explicit slice method argument.
        cases += [(slicing, prefix) for prefix in ('a.slice(b,', 'a.slice(b,c')]
        for declarations, prefix in cases:
            with self.subTest(prefix=prefix):
                self.rejects(declarations + 'let value = ' + prefix, 'Minyar stopped: line ')

    def test_argument_bounds_failure_precedes_callee_entry(self):
        declarations = '''function first(value: Integer): Integer {
print("entered")
return value + 1
}
function second(prefix: Integer, value: Integer): Integer {
print("entered")
return prefix + value
}
let values: List<Integer> = []
'''
        for call in ('first(values[0])', 'second(1, values[0])'):
            with self.subTest(call=call):
                self.executes(declarations + 'print(' + call + ')\n', '', status=1,
                              stderr='Minyar stopped: List position 0 is outside its length of 0.\n')

    def test_loop_carried_swaps_preserve_both_previous_values(self):
        source = []
        expected = []
        for name, bound, count in [('literal', '3', 3), ('parameter', 'a', 8)]:
            source.append(f'''function {name}(a: Integer, b: Integer): Integer {{
let i = a
let j = b
let sum = 0
let c = 0
while c < {bound} {{
print(i)
sum = sum + i + j
c = c + 1
let previous = i
i = j
j = previous
}}
print(i)
print(j)
return sum
}}
print({name}(8, 3))
''')
            expected += [str(8 if index % 2 == 0 else 3) for index in range(count)]
            expected += ['3', '8'] if count % 2 else ['8', '3']
            expected += [str(count * 11)]
        self.executes(''.join(source), '\n'.join(expected) + '\n')

    def test_doubled_integer_guards_keep_exact_large_results(self):
        self.executes('''function multiply(a: Integer, b: Integer): Integer {
a = a * 2
b = b * 2
if a < 1 && b < 1 { return a * b }
return 0
}
function add(a: Integer, b: Integer): Integer {
a = a * 2
b = b * 2
if a < 1 && b < 1 { return a + b }
return 0
}
function subtract(a: Integer, b: Integer): Integer {
a = a * 2
b = b * 2
if b == 2 { print(a); print(b) }
if a < 1 && b < 3 { return a - b }
return 0
}
let count = 0
while count < 5 { print(multiply(0, 0)); count = count + 1 }
print(multiply(-1073741824, -1073741824))
count = 0
while count < 5 { print(add(0, 0)); count = count + 1 }
print(add(-1073741824, -1073741824))
count = 0
while count < 5 { print(subtract(0, 0)); count = count + 1 }
print(subtract(-1073741824, 1))
''', '0\n' * 5 + '4611686018427387904\n' + '0\n' * 5 + '-4294967296\n' +
             '0\n' * 5 + '-2147483648\n2\n-2147483650\n')

    def test_loop_counter_boundaries_and_condition_side_effects(self):
        self.executes('''function first(): Integer { let x = 1073741823; x = x + 1; return x }
function second(): Integer { let x = -1073741824; x = x - 1; return x }
function fourth(): Integer {
let i = 1073741822
while i <= 1073741823 { i = i + 1 }
return i
}
function fifth(): Integer {
let i = -1073741823
while i >= -1073741824 { i = i - 1 }
return i
}
function sixth(): Integer { let x = 1073741823; x = x + 1; return x + 1 }
function seventh(): Integer {
let i = 1073741821
while i <= 1073741822 { i = i + 1 }
i = i + 1
i = i + 1
return i
}
function eighth(): Integer {
let i = 1073741821
while i <= 1073741823 { i = i + 1 }
i = i + 1
i = i + 1
return i
}
function ninth(): Integer {
let i = 0
while i < 42 { return 42 }
return 0
}
function tenth(x: Integer): Integer {
x = 0
while x < 4 { print(x); x = x + 1 }
return x
}
print(first())
print(second())
print(fourth())
print(fifth())
print(sixth())
print(seventh())
print(eighth())
print(ninth())
print(tenth(42))
let n = 1
let i = 1
while (6 - i) != 0 { n = n * i; i = i + 1 }
print(n)
function decrement(cell: List<Integer>): Boolean { cell[0] = cell[0] - 1; return cell[0] >= 0 }
let cell: List<Integer> = [42]
i = 0
while decrement(cell) { i = cell[0] + 1 }
print(i)
print(cell[0])
function posttest(bound: Integer): Integer {
let x = 1
let count = 0
if x >= 5 { count = count + 1 }
print(x)
while x < bound {
x = x + 1
if x >= 5 { count = count + 1 }
print(x)
}
return count
}
print(posttest(10))
''', ''.join(f'{value}\n' for value in [1073741824, -1073741825, 1073741824, -1073741825,
             1073741825, 1073741825, 1073741826, 42, 0, 1, 2, 3, 4, 120, 1, -1, *range(1, 11), 6]))

    def test_previous_space_scanner_all_positions(self):
        phrase = 'I am the very model of a modern major general\n'
        text = phrase * 100
        # Precompute run starts, rather than mirror the backwards scanning loop.
        def oracle(value):
            starts = [index for index, char in enumerate(value)
                      if char == ' ' and (index == 0 or value[index - 1] != ' ')]
            return [max([0] + [start for start in starts if start < seek]) for seek in range(len(value))]
        extra = 'ab   cd'
        source = '''function previousSpace(text: Text, seek: Integer): Integer {
seek = seek - 1
while seek > 0 {
if text[seek] == ' ' {
while seek > 0 && text[seek - 1] == ' ' { seek = seek - 1 }
return seek
}
seek = seek - 1
}
return 0
}
function scan(text: Text) {
let seek = 0
while seek < text.length { print(previousSpace(text, seek)); seek = seek + 1 }
}
let text = ""
let repeat = 0
'''
        source += f'while repeat < 100 {{ text = text + {literal(phrase)}; repeat = repeat + 1 }}\n'
        source += 'scan(text)\nscan(' + literal(extra) + ')\n'
        self.executes(source, ''.join(f'{value}\n' for value in oracle(text) + oracle(extra)))

    def test_repeated_sequential_list_shifts_preserve_alias_reads(self):
        # One rotation after the first shift acts on the three surviving values.
        expected = []
        state = [1, 2, 3, 4]
        for _ in range(4):
            for _ in range(10000 * 8):
                state = [state[1], state[2], state[3], state[1]]
            expected += state + [10000]
        expected += [0]
        shifts = '\n'.join(['values[0] = values[1]', 'values[1] = values[2]',
                             'values[2] = values[3]', 'values[3] = values[0]'] * 8)
        source = '''function done(counter: List<Integer>): Boolean {
counter[0] = counter[0] - 1
return counter[0] > 0
}
let values: List<Integer> = [1, 2, 3, 4]
let counter: List<Integer> = [5]
while done(counter) {
let i = 0
while i < 10000 {
''' + shifts + '''
i = i + 1
}
print(values[0])
print(values[1])
print(values[2])
print(values[3])
print(i)
}
print(counter[0])
'''
        self.executes(source, ''.join(f'{value}\n' for value in expected))

    @unittest.skipUnless(sys.platform.startswith('linux'), '/dev/full transport check requires Linux')
    def test_buffered_and_large_file_writes_report_device_failure(self):
        device = os.stat('/dev/full')
        self.assertTrue(stat.S_ISCHR(device.st_mode))
        self.assertEqual((os.major(device.st_rdev), os.minor(device.st_rdev)), (1, 7))
        for length in (1, 65536):
            with self.subTest(length=length):
                source = f'''let text = "x"
while text.byteLength < {length} {{ text = text + text }}
print("before")
writeTextFile("/dev/full", text)
print("unexpected success")
'''
                self.executes(source, 'before\n', 1, 'Minyar stopped: a requested text file could not be written.\n')

    def test_iteration_rechecks_list_length_after_append(self):
        self.executes('''let values: List<Integer> = [1, 2, 3, 4, 5]
let index = 0
while index < values.length {
let value = values[index]
print(value)
if value % 2 == 0 { values.add(value + 5) }
index = index + 1
}
print(values.length)
let zeros: List<Integer> = [2]
index = 0
while index < zeros.length {
let value = zeros[index]
print(value)
let count = 0
while count < value { zeros.add(0); count = count + 1 }
index = index + 1
}
print(zeros.length)
''', '1\n2\n3\n4\n5\n7\n9\n7\n2\n0\n0\n3\n')

    def test_wide_record_construction_preserves_every_field(self):
        fields = ', '.join(f'foo{index}: Integer' for index in range(1, 258))
        values = ', '.join(f'foo{index}: {index}' for index in range(1, 258))
        source = [f'record Wide {{ {fields} }}',
                  f'function construct(): Wide {{ return Wide {{ {values} }} }}',
                  'function forward(): Wide { return construct() }',
                  'let first = forward()', 'let second = forward()',
                  'let third = forward()', 'let direct = construct()']
        for name in ('first', 'second', 'third', 'direct'):
            source += [f'print({name}.foo{index})' for index in range(1, 258)]
        self.executes('\n'.join(source) + '\n', ''.join(f'{index}\n' for index in range(1, 258)) * 4)

    def test_every_contiguous_source_substring(self):
        program = 'let x = 1\nprint(x)\n'
        self.evidence.controls['substring_domain'] = {
            'source': program, 'rule': 'all 0 <= begin <= end <= length, including empty spans',
            'count': (len(program) + 1) * (len(program) + 2) // 2,
        }
        for begin in range(len(program) + 1):
            for end in range(begin, len(program) + 1):
                with self.subTest(begin=begin, end=end):
                    result, llvm = self.compile(program[begin:end])
                    self.assertIn(result.returncode, (0, 1), result.stderr)
                    self.assertEqual(result.stdout, '')
                    if result.returncode == 0:
                        self.assertEqual(result.stderr, '')
                        self.assertTrue(llvm.is_file())
                    else:
                        self.assertTrue(result.stderr.startswith('Minyar stopped:'), result.stderr)
                        self.assertNotIn('List position', result.stderr)
                        self.assertNotIn('outside the supported range', result.stderr)
                        self.assertFalse(llvm.exists())

    def test_arithmetic_grouping_and_invalid_assignment_targets(self):
        self.executes("""function grouping(a: Integer, b: Integer, c: Integer) {
print(a / (b / c))
print((a / b) / c)
print(a / b / c)
}
grouping(16, 4, 2)
print(16 / (4 / 2))
print((16 / 4) / 2)
print(16 / 4 / 2)
print(-1*1/1 + 1*1 - ---1*1)
""", '8\n2\n2\n8\n2\n2\n1\n')
        for assignment in ('x + 1 = 1', 'x + 1 = y + 2'):
            self.rejects('let x = 1\nlet y = 2\n' + assignment + '\n', 'Minyar stopped:')

    def test_wide_products_and_square_overflow_boundary(self):
        self.executes("""function product(a: Integer, b: Integer): Integer { return a * b }
print(product(4608, 1024) * 1024)
print(product(3037000499, 3037000499))
print(product(-3037000499, 3037000499))
""", '4831838208\n9223372030926249001\n-9223372030926249001\n')
        for left, right in ((3037000500, 3037000500), (-3037000500, 3037000500),
                            (4831838208, 4831838208), (-9223372036854775808, 7)):
            with self.subTest(left=left, right=right):
                self.executes(f'function product(a: Integer, b: Integer): Integer {{ return a * b }}\nprint(product({left}, {right}))\n', '', 1, OVERFLOW)

    def test_subtraction_table_and_mutation_order(self):
        values = (-4275878552, -4275878551, -4660, -3, -2, -1, 0, 1, 2, 3, 4660, 4275878551, 4275878552)
        source = ['function subtract(a: Integer, b: Integer): Integer { return a - b }',
                  'function add(a: Integer, b: Integer): Integer { return a + b }',
                  'function divide(a: Integer, b: Integer): Integer { return a / b }',
                  'function remainder(a: Integer, b: Integer): Integer { return a % b }',
                  'function multiply(a: Integer, b: Integer): Integer { return a * b }']
        expected = []
        overflow_pairs = []
        for a in values:
            for b in values:
                source += [f'print(subtract({a}, {b}))', f'print({a} - {b})', f'print(add({a}, {b}))', f'print({a} + {b})']
                expected += [str(a - b), str(a - b), str(a + b), str(a + b)]
                if b != 0:
                    quotient = abs(a) // abs(b)
                    if (a < 0) != (b < 0):
                        quotient = -quotient
                    source += [f'print(divide({a}, {b}))', f'print({a} / {b})']
                    expected += [str(quotient), str(quotient)]
                    source += [f'print(remainder({a}, {b}))', f'print({a} % {b})']
                    expected += [str(a - quotient * b)] * 2
                if -(1 << 63) <= a * b < (1 << 63):
                    source += [f'print(multiply({a}, {b}))', f'print({a} * {b})']
                    expected += [str(a * b)] * 2
                else:
                    overflow_pairs.append((a, b))
        for index, (a, b) in enumerate(((4923, 2), (1342177, 800), (65536, 65536))):
            source += [f'let a{index} = {a}', f'let b{index} = {b}',
                       f'print({a} * {b})', f'print(a{index} * b{index})', f'print(multiply({a}, {b}))']
            expected += [str(a * b)] * 3
        source += ['function change(values: List<Integer>): Integer { values[0] = 1; return 1 }',
                   'function changeTwo(values: List<Integer>): Integer { values[0] = 2; return 2 }',
                   'let values = [0]', 'print(change(values) - values[0])',
                   'values[0] = 0', 'print(values[0] - change(values))',
                   'values[0] = 0', 'print(change(values) + values[0])',
                   'values[0] = 0', 'print(values[0] + change(values))',
                   'values[0] = 0', 'print(change(values) % values[0])',
                   'values[0] = 1', 'print(values[0] % changeTwo(values))',
                   'values[0] = 0', 'print(change(values) * values[0])',
                   'values[0] = 0', 'print(values[0] * change(values))',
                   'values[0] = 0', 'print(change(values) / values[0])',
                   'values[0] = 1', 'print(values[0] / changeTwo(values))',
                   'values[0] = 0', 'print(values[0] / change(values))']
        expected += ['0', '-1', '2', '1', '0', '1', '1', '0', '1', '0', '0']
        for a, b in ((101, 51), (101, -51), (-101, 51), (-101, -51)):
            source += [f'print(remainder({a}, {b}))', f'print({a} % {b})']
            expected += [str(50 if a > 0 else -50)] * 2
        self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')
        source = ['function multiply(a: Integer, b: Integer): Integer { return a * b }',
                  'let choice = argument(0)']
        choices = []
        for index, (a, b) in enumerate(overflow_pairs):
            for kind, expression in (('literal', f'{a} * {b}'), ('parameter', f'multiply({a}, {b})')):
                choice = f'{index}-{kind}'
                choices.append(choice)
                source.append(f'if choice == "{choice}" {{ print({expression}) }}')
        source.append('print("ready")')
        llvm = self.executes('\n'.join(source) + '\n', 'ready\n', arguments=['probe'])
        self.evidence.controls['multiplication_overflow_pairs'] = overflow_pairs
        variants = ('-O0', '-O2', '-O3', '-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1' else ('-O0', '-O2')
        for optimization in variants:
            for choice in choices:
                with self.subTest(optimization=optimization, choice=choice):
                    result = self.evidence.run([llvm.with_suffix('.' + optimization[1:]), choice],
                                               timeout=10, phase='execute-multiplication-overflow')
                    self.assertEqual((result.returncode, result.stdout, result.stderr), (1, b'', OVERFLOW.encode()))

    def test_loop_exit_zero_is_not_used_as_divisor(self):
        source = """function calculate(start: Integer): Integer {
let divisor = start
let total = 0
while divisor > 0 {
total = total + 20 / divisor + 20 % divisor
divisor = divisor - 2
}
return total
}
print(calculate(50))
print(calculate(0))
"""
        total = sum(20 // divisor + 20 % divisor for divisor in range(50, 0, -2))
        self.executes(source, f'{total}\n0\n')

    def test_negative_remainder_remains_invalid_list_index(self):
        for divisor in (999, 1000, 1001):
            with self.subTest(divisor=divisor):
                self.executes(f'function access(value: Integer) {{ let values: List<Integer> = []; let index = 0; while index < 1000 {{ values.add(index); index = index + 1 }}; print(values[value % {divisor}]) }}\naccess(-1)\n',
                              '', 1, 'Minyar stopped: List position -1 is outside its length of 1000.\n')

    def test_repeated_old_value_concatenation_and_unaligned_views(self):
        value = ''
        for _ in range(3):
            value = 'a' + value + 'b' + value + 'c'
        payload = '0123456789é🙂' * 100
        self.executes('let text = ""\nlet index = 0\nwhile index < 3 { text = "a" + text + "b" + text + "c"; index = index + 1 }\nprint(text)\n'
                      + 'let root = "12345" + ' + literal(payload) + '\n'
                      + 'let view = root.slice(5, root.length)\nroot = "gone"\n'
                      + 'print(view == ' + literal(payload) + ')\n', value + '\ntrue\n')

    @unittest.skipUnless(os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1', 'extended LTO lane')
    def test_lto_preserves_checked_arithmetic_and_list_aliases(self):
        flags = shlex.split(os.environ.get('MINYAR_TEST_LTO_FLAGS', '-flto'))
        cases = [
            ('function calculate(x: Integer): Integer { return (x + 13) - 7 }\nprint(calculate(9223372036854775797))\n', b'', 1, OVERFLOW.encode()),
            ('''function change(write: List<Integer>, read: List<Integer>): Integer {
write[0] = 42
return read[0]
}
let values = [1]
print(change(values, values))
''', b'42\n', 0, b''),
        ]
        for source, stdout, status, stderr in cases:
            compiled, llvm = self.compile(source)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            executable = llvm.with_suffix('.lto')
            linked = self.evidence.run([CLANG, '-O2', *flags, '-DMINYAR_SYSTEM_HEAP=1',
                                       '-Wno-override-module', llvm, ROOT / 'runtime/minyar_runtime.c', '-o', executable],
                                      phase='link-lto', timeout=60)
            self.assertEqual(linked.returncode, 0, linked.stderr)
            result = self.evidence.run([executable], phase='execute-lto', timeout=10)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (status, stdout, stderr))

    def test_mixed_width_boundary_views_survive_nonsequential_access(self):
        # Existing scalar/forward-index checks are extended by composition/order.
        scalars = '\0\x7f\u0080\u07ff\u0800\ud7ff\ue000\uffff\U00010000\U0010ffff'
        value = (scalars * 14) + 'e\u0301🙂'
        lines = ['let text = ' + literal(value) + ' + ""', 'let parts: List<Text> = []']
        expected = []
        indices = list(range(len(value)))
        random.Random(0x50454552).shuffle(indices)
        for index in indices:
            lines.append(f'print(text[{index}] == {literal(value[index])}[0])')
            expected.append('true')
        lines += ['let index = 0', 'while index < text.length {',
                  'parts.add(text.slice(index, index + 1))', 'index = index + 1', '}',
                  'print(joinText(parts) == text)',
                  'let view = text.slice(61, 132).slice(2, 68)',
                  'text = "released root binding"',
                  'print(view == ' + literal(value[63:129]) + ')',
                  'print(view.length)']
        expected += ['true', 'true', '66']
        self.executes('\n'.join(lines) + '\n', '\n'.join(expected) + '\n')

    def test_self_join_keeps_old_alias_across_growth(self):
        value = 'A\0é🙂'
        source = ['let text = ' + literal(value) + ' + ""']
        expected = []
        for index in range(8):
            source += [f'let old{index} = text', 'text = text + text',
                       f'print(old{index} == {literal(value)})',
                       'print(text == ' + literal(value + value) + ')']
            expected += ['true', 'true']
            value += value
        self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')


if __name__ == '__main__':
    from peer_runner import main
    main()
