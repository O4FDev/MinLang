#!/usr/bin/env python3
"""Original Minyar adaptations of pinned peer cases; no upstream test code copied.

Scope and source identities: peer-pyswru-vectors.json and the exhaustive ledger.
Python/Ruby runtime reflection, Swift graphemes and Zig JSON parsing are excluded.
"""
from clang_helpers import clang_command
import json
import math
import os
import sys
import unittest

from regressions import CompilerTestCase, ROOT, RUN_TIMEOUT, CLANG, LINK_FLAGS, RUNTIME
from test_evidence import digest
from peer_runner import peer_configurations


def literal(text):
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t') + '"'


# Exact finite lexical expectations, derived independently of compiler output.
import itertools
import re

DECIMAL_PREFIXES = ('', '0x', '0o', '0b', '0d', '-', '+')
DECIMAL_ALPHABET = '01_9f'
DECIMAL_EXPLICIT_DECIMAL = ('0_0_0', '4_2', '1_0000_0000', '0_', '42_',
                    '0_b0', '0_xf', '0_o5', '0_7', '09_99', '4_______2')
DECIMAL_RADIX_TAIL = tuple(sign + radix + '_' for sign in ('', '-', '+')
                   for radix in ('0x', '0o', '0b', '0d'))

def decimal_literal_diagnostic(token):
    """Decimal and hexadecimal grammar in the exact print(token) context.

    '+' has no unary production. A bare '-' lacks its expression. Identifiers
    following an optional numeric prefix remain whole unknown names. These
    finite tokens cannot contain a second sign or other punctuation.
    """
    assert not re.fullmatch(r'-?(?:0[xX][0-9a-fA-F]+|[0-9]+)', token)
    if not token:
        return 'print expects 1 arguments, but received 0'
    if token.startswith('+'):
        return "line 1, column 7: expected an expression, found '+'"
    if token == '-':
        return "line 1, column 8: expected an expression, found ')'"
    offset = 1 if token.startswith('-') else 0
    number = re.match(r'-?(?:0[xX][0-9a-fA-F]+|[0-9]+)', token)
    if number:
        offset = number.end()
    name = token[offset:]
    assert re.fullmatch(r'[a-zA-Z_][a-zA-Z_0-9]*', name)
    return f"line 1, column {7+offset}: I can't find a value named '{name}'"

def decimal_literal_cells():
    for prefix in DECIMAL_PREFIXES:
        for size in range(4):
            for digits in itertools.product(DECIMAL_ALPHABET, repeat=size):
                token = prefix + ''.join(digits)
                accept = re.fullmatch(r'-?(?:0[xX][0-9a-fA-F]+|[0-9]+)', token) is not None
                yield {'cohort': 'ruby-product', 'prefix': prefix, 'size': size,
                       'digits': list(digits), 'token': token,
                       'source_skips': token == '',
                       'expected_value': int(token, 16 if 'x' in token.lower() else 10) if accept else None,
                       'diagnostic': None if accept else decimal_literal_diagnostic(token)}
    for token in DECIMAL_EXPLICIT_DECIMAL:
        yield {'cohort': 'python-explicit-decimal', 'token': token,
               'expected_value': None, 'diagnostic': decimal_literal_diagnostic(token)}
    for token in DECIMAL_RADIX_TAIL:
        yield {'cohort': 'ruby-bug2407-tail', 'token': token,
               'expected_value': None, 'diagnostic': decimal_literal_diagnostic(token)}
    # Missing integer separator inputs from Python's shared literal table.
    for token in ('0o5_', '0b1001__0100', '0xffff__ffff', '0o5__77'):
        yield {'cohort': 'python-additional-integer-underscores', 'token': token,
               'expected_value': None, 'diagnostic': decimal_literal_diagnostic(token)}


class PeerPythonSwiftRubyLua(CompilerTestCase):
    def variants(self):
        return ('-O0', '-O2', '-O3', '-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1' else ('-O0', '-O2')

    def executes(self, source, expected, status=0, stderr='', arguments=()):
        return super().executes(source, expected, status, stderr, optimizations=self.variants(), arguments=arguments)

    def vectors(self):
        path = ROOT / 'tests/peer-pyswru-vectors.json'
        self.evidence.inputs[str(path.resolve())] = digest(path)
        data = json.loads(path.read_text())
        self.assertEqual(data['schema_version'], 1)
        return data

    def test_three_hundred_positional_parameters_and_values(self):
        parameters = ', '.join(f'p{i}: Integer' for i in range(300))
        body = ['let checksum = 0']
        body += [f'checksum = checksum + p{i} * {i + 1}' for i in range(300)]
        body += ['print(p0)', 'print(p149)', 'print(p299)', 'return checksum']
        source = f'function wide({parameters}): Integer {{\n' + '\n'.join(body) + '\n}\n'
        source += 'print(wide(' + ', '.join(map(str, range(300))) + '))\n'
        self.executes(source, f'0\n149\n299\n{sum(i * (i + 1) for i in range(300))}\n')

    def test_ten_five_hundred_and_thousand_positional_arguments(self):
        # CPython test_call.py checks the middle argument for exactly these
        # arities. Printing every slot additionally detects dropped/reordered
        # arguments that happen not to affect that middle slot.
        for count in (10, 500, 1000):
            with self.subTest(arguments=count):
                parameters = ', '.join(f'p{i}: Integer' for i in range(count))
                arguments = ', '.join(map(str, range(count)))
                source = f'function middle({parameters}): Integer {{ return p{count // 2} }}\n'
                source += f'function every({parameters}): Nothing {{\n'
                source += ''.join(f'print(p{i})\n' for i in range(count)) + '}\n'
                source += f'print(middle({arguments}))\nevery({arguments})\n'
                self.executes(source, '\n'.join(map(str, [count // 2, *range(count)])) + '\n')

    def test_filtered_iteration_preserves_present_payload_order(self):
        # Swift's Optional/pattern syntax is represented explicitly. Poison
        # payloads in absent records expose accidental inclusion of nil slots.
        source = '''record Item { present: Boolean; value: Integer }
let items: List<Item> = [
Item { present: true, value: 1 }, Item { present: false, value: 91 },
Item { present: true, value: 2 }, Item { present: false, value: 92 },
Item { present: true, value: 3 }, Item { present: false, value: 93 },
Item { present: false, value: 94 }, Item { present: false, value: 95 },
Item { present: true, value: 4 }, Item { present: true, value: 5 },
]
let i = 0
while i <= 6 {
    if i % 2 == 0 { print(i) }
    i = i + 1
}
print("present")
i = 0
while i < items.length {
    if items[i].present { print(items[i].value) }
    i = i + 1
}
print("filtered")
i = 0
while i < items.length {
    if items[i].present && items[i].value != 3 { print(items[i].value) }
    i = i + 1
}
'''
        self.executes(source, '0\n2\n4\n6\npresent\n1\n2\n3\n4\n5\nfiltered\n1\n2\n4\n5\n')

    def test_text_suffix_candidates_use_scalar_boundaries(self):
        # Ruby's variadic Text suffix predicate becomes an explicit List<Text>
        # helper built from Minyar's scalar length/slice/equality operations.
        cases = [
            ('hello', ['o'], True), ('hello', ['llo'], True),
            ('hello', ['ll'], False), ('hello', [''], True), ('', [''], True),
            ('hello', ['x', 'y', 'llo', 'z'], True), ('hello', [], False),
            ('céréale', ['réale'], True),
            # Local controls supplement the exact upstream examples.
            ('hello', ['hello!'], False), ('', ['o'], False),
            ('hello', ['x', 'y'], False), ('céréale', ['réal'], False),
            ('a🙂é', ['🙂é'], True), ('a🙂é', ['a🙂'], False),
            ('a\0🙂', ['\0🙂'], True), ('a\0🙂', ['\0'], False),
        ]
        source = '''function endsWithAny(value: Text, suffixes: List<Text>): Boolean {
    let i = 0
    while i < suffixes.length {
        let suffix = suffixes[i]
        if suffix.length <= value.length {
            if value.slice(value.length - suffix.length, value.length) == suffix {
                return true
            }
        }
        i = i + 1
    }
    return false
}
'''
        for value, suffixes, expected in cases:
            self.assertEqual(any(value.endswith(suffix) for suffix in suffixes), expected)
            source += f'print(endsWithAny({literal(value)}, [' + ', '.join(map(literal, suffixes)) + ']))\n'
        self.executes(source, ''.join(str(expected).lower() + '\n' for _, _, expected in cases))

    def test_five_module_cycle_shapes_and_acyclic_controls(self):
        graphs = [{1: [1]}, {1: [2], 2: [3], 3: [1]},
                  {1: [2], 2: [3], 3: [1], 5: [4], 4: [6]},
                  {1: [2], 2: [1], 3: [4], 4: [5], 6: [7], 7: [6]},
                  {1: [2], 2: [3], 3: [2, 4], 4: [5]}]
        for index, graph in enumerate(graphs):
            nodes = sorted(set(graph) | {dep for deps in graph.values() for dep in deps})
            folder = self.directory / f'graph{index}'
            folder.mkdir()
            def write_graph(acyclic):
                for node in nodes:
                    edges = graph.get(node, [])
                    if acyclic:
                        edges = [dep for dep in edges if dep > node]
                    source = ''.join(f'use "./node{dep}.min" as n{dep}\n' for dep in edges)
                    source += f'public function value(): Integer {{ return {node} }}\n'
                    (folder / f'node{node}.min').write_text(source)
            main = ''.join(f'use "./graph{index}/node{node}.min" as n{node}\n' for node in nodes)
            main += 'print(' + ' + '.join(f'n{node}.value()' for node in nodes) + ')\n'
            with self.subTest(graph=index):
                write_graph(False)
                self.rejects(main, 'module import cycle:')
                write_graph(True)
                self.executes(main, f'{sum(nodes)}\n')

    def test_unicode_filename_read_write_and_missing_path_guards(self):
        rows = self.vectors()['filenames']
        self.assertEqual(len(rows), 19)
        for prefix, scalar in [(16, 0x2000), (17, 0x2001), (18, 0x2003)]:
            self.assertEqual(rows[prefix - 1]['filename'], f'{prefix}_' + chr(scalar) * 3 + 'A')
        for row in rows:
            self.assertNotIn(chr(92) + 'u', row['filename'], 'filename contains an unevaluated Unicode escape')
        source, expected, outputs, arguments = [], [], [], []
        inputs = self.directory / 'inputs'
        output_directory = self.directory / 'outputs'
        inputs.mkdir()
        output_directory.mkdir()
        for index, row in enumerate(rows):
            with self.subTest(filename=row['filename']):
                if row['non_apple_only'] and sys.platform == 'darwin':
                    self.evidence.controls.setdefault('platform_exclusions', []).append(row['filename'])
                    continue  # Preserve upstream normalization-sensitive platform scope.
                path = inputs / row['filename']
                output = output_directory / row['filename']
                payload = f'file{index}:é\0🙂'
                path.write_bytes(payload.encode('utf-8'))
                argument_index = len(arguments)
                arguments += [str(path), str(output)]
                source += [f'let path{index} = argument({argument_index})',
                           f'let output{index} = argument({argument_index + 1})',
                           f'let text{index} = readTextFile(path{index})', f'print(text{index})',
                           f'writeTextFile(output{index}, text{index} + "!")',
                           f'print(readTextFile(output{index}))']
                expected += [payload, payload + '!']
                outputs.append((output, (payload + '!').encode()))
        # Each optimization must create its own output; stale successful writes
        # from an earlier executable cannot satisfy the next variant's oracle.
        for optimization in self.variants():
            for path, _ in outputs:
                path.unlink(missing_ok=True)
            CompilerTestCase.executes(self, '\n'.join(source) + '\n', '\n'.join(expected) + '\n',
                                      optimizations=(optimization,), arguments=arguments)
            for path, content in outputs:
                self.assertEqual(path.read_bytes(), content)
        missing = self.directory / 'absent-Γειά-🙂'
        self.executes('print(readTextFile(argument(0)))\n', '', 1,
                      f"Minyar stopped: the file '{missing}' could not be opened.\n", arguments=[str(missing)])

    def check_literal_payloads(self, texts):
        source, expected = [], []
        for index, text in enumerate(texts):
            path = self.directory / f'payload{index}.txt'
            path.write_bytes(text.encode('utf-8'))
            source += [f'let text{index} = {literal(text)}', f'let disk{index} = readTextFile({literal(str(path))})',
                       f'print(text{index} == disk{index})', f'print(text{index}.length)', f'print(text{index}.byteLength)',
                       f'print(text{index})']
            expected += ['true', str(len(text)), str(len(text.encode('utf-8'))), text]
            for position, scalar in enumerate(text):
                source += [f'print(Text(text{index}[{position}]))', f'print(text{index}[{position}] == disk{index}[{position}])']
                expected += [scalar, 'true']
            for begin in range(len(text) + 1):
                for end in range(begin, len(text) + 1):
                    source.append(f'print(text{index}.slice({begin}, {end}))')
                    expected.append(text[begin:end])
        self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')

    def test_python_literal_payloads_match_independent_utf8_files(self):
        rows = self.vectors()['python_literals']
        self.assertEqual(len(rows), 7)
        self.check_literal_payloads([r['text'] for r in rows])

    def test_swift_flag_and_mathematical_scalar_literals(self):
        rows = self.vectors()['swift_literals']
        self.assertEqual(len(rows), 6)
        texts = list(dict.fromkeys(r['payload'] for r in rows))
        self.assertEqual(texts, ['🇦🇺', '𝔹'])
        self.check_literal_payloads(texts)

    def test_zig_and_ruby_malformed_utf8_ingress_vectors(self):
        rows = self.vectors()['invalid_utf8']
        self.assertEqual(len(rows), 35)
        self.assertEqual(len({r['hex'] for r in rows}), 35)
        paths = []
        for index, row in enumerate(rows):
            raw = bytes.fromhex(row['hex'])
            with self.assertRaises(UnicodeDecodeError):
                raw.decode('utf-8')
            path = self.directory / f'invalid{index}.txt'
            path.write_bytes(raw)
            paths.append(path)
        error = 'Minyar stopped: Text contained invalid UTF-8.\n'
        source = 'let text = readTextFile(argument(0))\nprint(text.byteLength)\nprint(text.length)\n'
        llvm = self.executes(source, f'{len(bytes.fromhex(rows[0]["hex"]))}\n', 1, error, arguments=[str(paths[0])])
        for optimization in self.variants():
            for row, path in zip(rows[1:], paths[1:]):
                with self.subTest(optimization=optimization, raw=row['hex']):
                    result = self.evidence.run([llvm.with_suffix('.' + optimization[1:]), path], timeout=RUN_TIMEOUT,
                                               phase='execute-peer-malformed-utf8')
                    self.assertEqual((result.returncode, result.stdout, result.stderr),
                                     (1, f'{len(bytes.fromhex(row["hex"]))}\n'.encode(), error.encode()))

    def test_ruby_quotient_remainder_operand_placements(self):
        cases = [(13, 4, 3, 1), (4, 13, 0, 4), (-200, -256, 0, -200), (-1000, -512, 1, -488)]
        source = ['function quotient(a: Integer, b: Integer): Integer { return a / b }',
                  'function remainder(a: Integer, b: Integer): Integer { return a % b }']
        expected = []
        for index, (a, b, q, r) in enumerate(cases):
            self.assertEqual(a, q * b + r)
            source += [f'let a{index} = {a}', f'let b{index} = {b}']
            for left, right in [(str(a), str(b)), (f'a{index}', str(b)), (str(a), f'b{index}'), (f'a{index}', f'b{index}')]:
                source += [f'print({left} / {right})', f'print({left} % {right})']
                expected += [str(q), str(r)]
            source += [f'print(quotient(a{index}, b{index}))', f'print(remainder(a{index}, b{index}))']
            expected += [str(q), str(r)]
        self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')

    def test_ruby_negation_at_signed32_transition(self):
        source = ['function negate(n: Integer): Integer { return -n }']
        expected = []
        for index, value in enumerate([100, -100, 2147483648, -2147483648]):
            source += [f'let n{index} = {value}', f'print(-({value}))', f'print(-n{index})', f'print(negate(n{index}))']
            expected += [str(-value)] * 3
        self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')

    def test_iterative_fibonacci_uses_previous_pair(self):
        self.executes('''function fib() {
let a = 0
let b = 1
while b < 10 {
print(b)
let previous = a
a = b
b = previous + b
}
}
fib()
''', '1\n1\n2\n3\n5\n8\n')

    def test_parenthesized_division_and_mixed_unary_precedence(self):
        self.executes('''function grouped(a: Integer, b: Integer, c: Integer) {
print(a / (b / c))
print((a / b) / c)
print(a / b / c)
}
function mixed(one: Integer): Integer { return -one * one / one + one * one - ---one * one }
print(16 / (4 / 2))
print((16 / 4) / 2)
print(16 / 4 / 2)
grouped(16, 4, 2)
print(-1 * 1 / 1 + 1 * 1 - ---1 * 1)
print(mixed(1))
''', '8\n2\n2\n8\n2\n2\n1\n1\n')

    def test_utf8_program_arguments_in_c_and_posix_locales(self):
        source = 'let value = argument(0)\nprint(value)\nprint(value.length)\nprint(value.byteLength)\nprint(value[0])\nprint(value[1])\nprint(value[2])\n'
        llvm = self.executes(source, 'hé€\n3\n6\nh\né\n€\n', arguments=['hé€'])
        for optimization in self.variants():
            for locale in ['C', 'POSIX']:
                with self.subTest(optimization=optimization, locale=locale):
                    environment = dict(os.environ, LC_ALL=locale, LANG=locale)
                    result = self.evidence.run([llvm.with_suffix('.' + optimization[1:]), 'hé€'], env=environment,
                                               timeout=RUN_TIMEOUT, phase='execute-peer-locale')
                    self.assertEqual((result.returncode, result.stdout, result.stderr), (0, 'hé€\n3\n6\nh\né\n€\n'.encode(), b''))

    def test_integer_conditions_never_coerce_to_boolean(self):
        for value in ('0', '(0)', '1', '(1)', '12', '(12)'):
            with self.subTest(value=value):
                self.rejects(f'if {value} {{ print(1) }}\n', 'an if condition must be Boolean')

    def test_numeric_values_and_minus_are_not_types(self):
        for spelling in ('123', '-123', '-Integer'):
            for template in ('let value: TYPE = 1\n', 'let value: List<TYPE> = []\n'):
                with self.subTest(spelling=spelling, template=template):
                    self.rejects(template.replace('TYPE', spelling), 'unknown type')

    def test_declaration_names_reject_numeric_tokens(self):
        for keyword, names, tail in [('function', ('1',), '() {}'),
                                      ('record', ('13',), ' {}')]:
            for name in names:
                with self.subTest(keyword=keyword, name=name):
                    self.rejects(f'{keyword} {name}{tail}\n', 'Minyar stopped: line 1,')

    def test_declaration_names_reject_float_and_digit_prefix_tokens(self):
        for keyword,names,tail in [('function',('2.0','3func'),'() {}'),
                                   ('record',('14.0','15struct'),' {}')]:
            for name in names:
                with self.subTest(keyword=keyword,name=name):
                    self.rejects(f'{keyword} {name}{tail}\n','Minyar stopped: line 1,')

    def test_unresolved_git_and_perforce_conflicts(self):
        variants = [
            '<<<<<<< HEAD\nlet a = "A"\n=======\nlet a = "B"\n>>>>>>> branch\n',
            '<<<<<<< HEAD\n=======\nlet d = "D"\n>>>>>>> branch\n',
            '>>>> ORIGINAL\nlet a = "A"\n==== THEIRS\nlet a = "B"\n==== YOURS\nlet a = "C"\n<<<<\n',
            '>>>> ORIGINAL\n==== THEIRS\n==== YOURS\nlet d = "D"\n<<<<\n',
        ]
        for index, source in enumerate(variants):
            with self.subTest(conflict=index):
                self.rejects(source, 'Minyar stopped: line 1,')

    def test_consecutive_statements_require_a_separator(self):
        for source in ('let a = 1 let b = 2\n', 'let a = 1\nlet b = 2\na = 3 b = 4\n'):
            for wrapped in (False, True):
                text = 'function probe() {\n' + source + '}\nprobe()\n' if wrapped else source
                with self.subTest(source=source, wrapped=wrapped):
                    self.rejects(text, 'start the next statement on a new line')
        self.executes('function probe() { let a = 1; let b = 2; a = 3; b = 4; print(a + b) }\nprobe()\n', '7\n')

    def test_comments_preserve_fixed_operator_boundaries(self):
        expressions = [('/* */!true', 'false'), ('1/**/+ 2', '3'), ('1 /**/+ 2', '3'),
                       ('1 +/*hi*/2', '3'), ('1 +/**/ 2', '3'), ('1 +/* hi */2', '3'),
                       ('1/**/+2', '3'), ('1+/**/2', '3'), ('!/* */true', 'false'), ('1+/* */2', '3')]
        source = '\n'.join('print(' + expression + ')' for expression, _ in expressions)
        source += '\nlet after =/**/2\nlet before/**/= 2\nprint(after)\nprint(before)\n'
        self.executes(source, '\n'.join(value for _, value in expressions) + '\n2\n2\n')

    def test_boolean_list_toggle_keeps_other_elements(self):
        self.executes('let flags = [false, true, true]\nflags[0] = !flags[0]\nflags[1] = !flags[1]\nprint(flags.length)\nprint(flags[0])\nprint(flags[1])\nprint(flags[2])\n', '3\ntrue\nfalse\ntrue\n')

    def test_computed_assignment_and_unescaped_quote_reject(self):
        for assignment in ('x + 1 = 1', 'x + 1 = y + 2'):
            self.rejects('let x = 1\nlet y = 2\n' + assignment + '\n', "unexpected '='")
        self.rejects('let x = "doesn\'t "shrink", does it"\n', "unexpected 'shrink'")

    def test_million_digit_decimal_tokens_are_bounded_rejections(self):
        for count in (133700, 1200000):
            with self.subTest(digits=count):
                self.rejects('print(' + '9' * count + ')\n', 'outside the supported range')

    def test_supplementary_scalar_23456_has_exact_utf8(self):
        scalar = chr(0x23456)
        self.assertEqual(scalar.encode('utf-8'), bytes.fromhex('f0a39196'))
        self.check_literal_payloads([scalar])

    def test_f1_followed_by_ascii_is_invalid_utf8(self):
        path = self.directory / 'f1-ascii.txt'
        path.write_bytes(bytes.fromhex('f161626364'))
        # Text indexing is lazy. The transferred converter assertion concerns
        # scalar decoding, rather than byte-preserving file I/O or printing.
        for operation in ('.length', '[0]', '.slice(0, 1)'):
            self.executes('let text = readTextFile(argument(0))\nprint(text.byteLength)\nprint(text' + operation + ')\n', '5\n', 1,
                          'Minyar stopped: Text contained invalid UTF-8.\n', arguments=[str(path)])

    def test_nul_prefix_slices_and_control_fragment_join(self):
        self.executes('let value = "\0' + '123456789"\nprint(value.slice(2,5))\nprint(value.slice(7,10))\n', '234\n789\n')
        fragments = ['\0.\0.', '\0\x01.\0.', '\0\x01\x02']
        text = ''.join(fragments)
        source = 'let parts = [' + ', '.join(literal(part) for part in fragments) + ']\nlet text = joinText(parts)\n'
        source += 'print(text)\nprint(text.length)\n'
        expected = text + '\n' + str(len(text)) + '\n'
        for i, c in enumerate(text):
            source += f'print(Text(text[{i}]))\n'
            expected += c + '\n'
        self.executes(source, expected)

    def test_nested_triangular_loops_preserve_outer_binding(self):
        self.executes('''let i = 3
let count = 0
let marks: List<Integer> = []
let init = 0
while init < 100 { marks.add(0); init = init + 1 }
let row = 1
while row <= 100 {
let i = row
while i > 0 { count = count + 1; marks[i - 1] = 1; i = i - 1 }
row = row + 1
}
print(i)
print(count)
let index = 0
while index < marks.length { print(marks[index]); index = index + 1 }
''', '3\n5050\n' + '1\n' * 100)

    def test_truncated_bom_source_inputs_reject(self):
        from regressions import COMPILER, COMPILE_TIMEOUT
        for index, prefix in enumerate((b'\xef', b'\xef\xbb')):
            for following in (b'', b'print(42)\n'):
                with self.subTest(prefix=prefix.hex(), following=bool(following)):
                    path = self.directory / f'bom-{index}-{len(following)}.min'
                    path.write_bytes(prefix + following)
                    llvm = path.with_suffix('.ll')
                    result = self.evidence.run([COMPILER, path, llvm], timeout=COMPILE_TIMEOUT, phase='compile-invalid-bom')
                    self.assertEqual((result.returncode, result.stdout, result.stderr),
                                     (1, b'', b'Minyar stopped: Text contained invalid UTF-8.\n'))
                    self.assertFalse(llvm.exists())



    def integer_values(self):
        path = ROOT / 'tests/peer-pyswru-integer-values.json'
        self.evidence.inputs[str(path.resolve())] = digest(path)
        values = json.loads(path.read_text())['values']
        self.assertEqual(len(values), 79)
        self.assertEqual(values, sorted(set(values)))
        return values

    def test_signed_integer_peer_corpus_safe_arithmetic_and_boolean_storage(self):
        values = self.integer_values()
        minimum, maximum = -(1 << 63), (1 << 63) - 1
        source = ['let values = [' + ','.join(map(str, values)) + ']']
        expected = []
        # Safe b values form one contiguous interval for each fixed a and operation.
        # Host arbitrary precision chooses that interval before Minyar executes it.
        for label, symbol, operation in [('add', '+', lambda a,b:a+b),
                                          ('sub', '-', lambda a,b:a-b),
                                          ('mul', '*', lambda a,b:a*b)]:
            lower, upper = [], []
            for a in values:
                positions = [j for j,b in enumerate(values) if minimum <= operation(a,b) <= maximum]
                self.assertEqual(positions, list(range(positions[0], positions[-1]+1)))
                lower.append(positions[0]); upper.append(positions[-1]+1)
            source += [f'let {label}Low = [' + ','.join(map(str,lower)) + ']',
                       f'let {label}High = [' + ','.join(map(str,upper)) + ']']
            source += ['let i = 0', 'while i < values.length {', 'let a = values[i]',
                       f'let j = {label}Low[i]', f'while j < {label}High[i] {{',
                       'let b = values[j]', f'let c = a {symbol} b', 'print(c)']
            if symbol == '+':
                source += ['print(b + a)', 'print(c - b)']
            elif symbol == '-':
                source += ['print(c + b)', 'print(c - a)', 'print(-b)']
            else:
                source += ['print(b * a)', 'if a != 0 { print(c / a) }']
            source += ['j = j + 1', '}', 'i = i + 1', '}']
            for i,a in enumerate(values):
                for b in values[lower[i]:upper[i]]:
                    c = operation(a,b)
                    expected.append(str(c))
                    if symbol == '+': expected += [str(c),str(a)]
                    elif symbol == '-': expected += [str(a),str(-b),str(-b)]
                    else:
                        expected.append(str(c))
                        if a: expected.append(str(b))
        source += ['function carry(value: Boolean): Boolean { return value }',
                   'let i = 0', 'while i < values.length {', 'let a = values[i]',
                   'print(a)', 'print(-a)', 'print(0 - a)', 'print(a + -a)',
                   'let j = 0', 'while j < values.length {', 'let b = values[j]',
                   'let comparisons = [carry(a < b), carry(a <= b), carry(a > b), carry(a >= b), carry(a == b), carry(a != b)]',
                   'let k = 0', 'while k < comparisons.length { print(comparisons[k]); k = k + 1 }',
                   'print(b == a)', 'if b != 0 {', 'let q = a / b', 'let r = a % b',
                   'print(q)', 'print(r)', 'print(b * q + r)', '}',
                   'j = j + 1', '}', 'i = i + 1', '}']
        for i,a in enumerate(values):
            expected += [str(a),str(-a),str(-a),'0']
            for j,b in enumerate(values):
                expected += [str(v).lower() for v in (i<j,i<=j,i>j,i>=j,i==j,i!=j,j==i)]
                if b:
                    q=abs(a)//abs(b)
                    if (a<0)!=(b<0): q=-q
                    r=a-q*b
                    self.assertLess(abs(r),abs(b))
                    self.assertTrue(r==0 or (r<0)==(a<0))
                    expected += [str(q),str(r),str(a)]
        self.executes('\n'.join(source)+'\n', '\n'.join(expected)+'\n')

    def test_signed_integer_peer_corpus_overflow_and_zero_divisors(self):
        values = self.integer_values()
        source = ['function operand(text: Text): Integer {']
        source += [f'if text == "{value}" {{ return {value} }}' for value in values]
        source += ['return 0', '}', 'let op = argument(0)',
                   'let a = operand(argument(1))', 'let b = operand(argument(2))']
        for op in ('+','-','*','/','%'):
            source += [f'if op == "{op}" {{ print(a {op} b) }}']
        llvm = self.executes('\n'.join(source)+'\n', '0\n', arguments=['+','0','0'])
        cases = []
        for op, fn in [('+',lambda a,b:a+b),('-',lambda a,b:a-b),('*',lambda a,b:a*b)]:
            for a in values:
                for b in values:
                    if not -(1<<63) <= fn(a,b) < (1<<63):
                        cases.append(([op,str(a),str(b)], b'Minyar stopped: this Integer calculation is outside the supported range.\n'))
        for a in values:
            for op in ('/','%'):
                cases.append(([op,str(a),'0'], b'Minyar stopped: an Integer cannot be divided by zero.\n'))
        self.assertEqual(len(cases), 1486)
        self.evidence.controls['peer_integer_failure_cases'] = [args for args,_ in cases]
        for optimization in self.variants():
            for args, error in cases:
                with self.subTest(optimization=optimization, arguments=args):
                    run = self.evidence.run([llvm.with_suffix('.'+optimization[1:]), *args],
                                            timeout=RUN_TIMEOUT, phase='peer-integer-failure')
                    self.assertEqual((run.returncode,run.stdout,run.stderr), (1,b'',error))


    def test_decimal_prefix_and_separator_finite_lexical_product(self):
        accepted = []
        rejected = 0
        for cell in decimal_literal_cells():
            token = cell['token']
            if cell['diagnostic'] is None:
                accepted.append((token, cell['expected_value']))
            else:
                with self.subTest(cohort=cell['cohort'], token=token):
                    self.rejects_exact_diagnostic(f'print({token})\n', cell['diagnostic'])
                rejected += 1
        self.assertEqual((len(accepted), rejected), (162, 957))
        self.executes(''.join(f'print({token})\n' for token, _ in accepted),
                      ''.join(f'{value}\n' for _, value in accepted))

    def test_long_ascii_literal_and_supported_escapes(self):
        path = ROOT / 'tests/peer-pyswru-long-literal.json'
        self.evidence.inputs[str(path.resolve())] = digest(path)
        value = json.loads(path.read_text())['value']
        self.assertEqual(len(value),960)
        payloads = [value, '\n\r\t"\\', '\\n\\r\\t', 'quote"middle\\end']
        for value in payloads:
            source = f'let value = {literal(value)}\nprint(value)\nprint(value.length)\nprint(value.byteLength)\n'
            source += ''.join(f'print(value[{i}])\n' for i in range(len(value)))
            self.executes(source, value+'\n'+str(len(value))+'\n'+str(len(value.encode()))+'\n'+''.join(c+'\n' for c in value))

    def test_list_literal_capacity_boundaries_and_computed_elements(self):
        sizes = (0,1,2,3,4,5,7,8,9,15,16,17,30,31,32,33,34,254,255,256,257,500,1001)
        source, expected = [], []
        for size in sizes:
            name = f'values{size}'
            source += [f'let {name}: List<Integer> = [' + ','.join(map(str,range(size))) + ']',
                       f'print({name}.length)', 'let i = 0', f'while i < {name}.length {{ print({name}[i]); i = i + 1 }}']
            expected += [str(size), *map(str,range(size))]
            if size:
                source += [f'{name}[{size-1}] = -1',f'print({name}[{size-1}])']
                expected += ['-1']
        source += ['record Box { value: Text }']
        for size in (0,1,2,5,33,257):
            name=f'boxes{size}'
            source += [f'let {name}: List<Box> = [' + ','.join(f'Box {{ value: Text({i}) + "é" }}' for i in range(size))+']',
                       f'print({name}.length)', 'let i = 0', f'while i < {name}.length {{ print({name}[i].value); i = i + 1 }}']
            expected += [str(size), *(f'{i}é' for i in range(size))]
        source += ['let computed = [1 + 2, 3 + 4, 5 + 6]', 'print(computed.length)',
                   'print(computed[0])', 'print(computed[1])', 'print(computed[2])',
                   'computed[1] = computed[0] + computed[2]', 'print(computed[1])']
        expected += ['3','3','7','11','14']
        self.executes('\n'.join(source)+'\n','\n'.join(expected)+'\n')

    def test_three_hundred_owned_fragments_join_after_reassignment(self):
        self.executes('''let pieces: List<Text> = []
let i = 0
while i < 300 { pieces.add("xuxu" + Text(123)); i = i + 1 }
let alias = pieces
let joined = joinText(pieces)
pieces = []
alias[0] = "changed"
print(joined)
print(joined.length)
print(joined.byteLength)
print(joined.slice(0, 7))
print(joined.slice(2093, 2100))
print(alias[299])
''', 'xuxu123'*300+'\n2100\n2100\nxuxu123\nxuxu123\nxuxu123\n')

    def test_dead_zero_division_and_power_neighbor_cancellation(self):
        source = ['if false { print(3 / 0) }', 'if false { print(3 % 0) }',
                  'function cancel(a: Integer, b: Integer): Integer { return a + b }']
        expected=[]
        for value in (8388607,8388608,8388609):
            for a,b in ((value,-value),(-value,value)):
                source += [f'let a = {a}',f'let b = {b}',f'print({a} + ({b}))',
                           f'print(a + ({b}))',f'print(({a}) + b)','print(a + b)', 'print(cancel(a,b))']
                expected += ['0']*5
        source += ['print(42)']; expected += ['42']
        self.executes('\n'.join(source)+'\n','\n'.join(expected)+'\n')

    def test_control_byte_and_adjacent_identifier_have_source_locations(self):
        self.rejects('let value = 1name\n', 'line 1, column 14:')
        self.rejects('let a = 1\nlet b = a\x01a\n', 'line 2, column 10:')


    def test_every_byte_in_identifier_start_and_continuation(self):
        from regressions import COMPILER, COMPILE_TIMEOUT
        accepted = []
        for position in ('start','continuation'):
            for byte in range(256):
                name = bytes([byte]) if position == 'start' else b'a'+bytes([byte])+b'1'
                valid = 65<=byte<=90 or 97<=byte<=122 or byte==95 or (position=='continuation' and 48<=byte<=57)
                source = b'let '+name+b' = 1\n'
                path = self.directory / f'identifier-{position}-{byte}.min'
                path.write_bytes(source)
                llvm=path.with_suffix('.ll')
                with self.subTest(position=position,byte=byte):
                    run=self.evidence.run([COMPILER,path,llvm],timeout=COMPILE_TIMEOUT,phase='compile-identifier-byte')
                    self.assertEqual(run.returncode,0 if valid else 1,run.stderr)
                    self.assertEqual(run.stdout,b'')
                    self.assertEqual(llvm.exists(),valid)
                    if valid:
                        self.assertEqual(run.stderr,b'')
                        accepted.append(source.decode('ascii')+'print('+name.decode('ascii')+')\n')
                    else:
                        run.stderr.decode('utf-8',errors='strict')
                        self.assertTrue(run.stderr.startswith(b'Minyar stopped:'))
                        if byte>=128: self.assertIn(b'Text contained invalid UTF-8',run.stderr)
        self.assertEqual(len(accepted),116)
        self.executes(''.join(accepted),'1\n'*len(accepted))

    def test_seven_operands_all_supported_operator_placements(self):
        import operator
        values=(3,100,5,-10,-5,10000,-10000)
        operators=[('+',operator.add),('-',operator.sub),('*',operator.mul),
                   ('/',None),('%',None),('==',operator.eq),('!=',operator.ne),
                   ('<',operator.lt),('>',operator.gt),('<=',operator.le),('>=',operator.ge)]
        for symbol, operation in operators:
            with self.subTest(operator=symbol):
                result_type='Boolean' if symbol in ('==','!=','<','>','<=','>=') else 'Integer'
                source=[f'function apply(a: Integer,b: Integer): {result_type} {{ return a {symbol} b }}']
                expected=[]
                for a in values:
                    for b in values:
                        if operation: value=operation(a,b)
                        else:
                            q=abs(a)//abs(b)
                            if (a<0)!=(b<0): q=-q
                            value=q if symbol=='/' else a-q*b
                        source += [f'let a = {a}',f'let b = {b}']
                        for left,right in ((str(a),str(b)),('a',str(b)),(str(a),'b'),('a','b')):
                            source.append(f'print(({left}) {symbol} ({right}))')
                        source += ['print(apply(a,b))']
                        expected += [str(value).lower()]*5
                self.executes('\n'.join(source)+'\n','\n'.join(expected)+'\n')

    def test_demorgan_truth_and_short_circuit_effect_traces(self):
        for a in (False,True):
            for b in (False,True):
                source=['function left(value: Boolean): Boolean { print("left"); return value }',
                        'function right(value: Boolean): Boolean { print("right"); return value }',
                        f'let a = {str(a).lower()}',f'let b = {str(b).lower()}']
                expected=[]
                expressions=[('!(left(a) && right(b))',not(a and b),a),
                             ('!left(a) || !right(b)',not(a and b),a),
                             ('!(left(a) || right(b))',not(a or b),not a),
                             ('!left(a) && !right(b)',not(a or b),not a)]
                for expr,value,visits_right in expressions:
                    source.append('print('+expr+')')
                    expected += ['left']+(['right'] if visits_right else [])+[str(value).lower()]
                self.executes('\n'.join(source)+'\n','\n'.join(expected)+'\n')

    def test_checked_negation_square_and_cube_never_wrap(self):
        error='Minyar stopped: this Integer calculation is outside the supported range.\n'
        cases=[('0 - (-9223372036854775808)','function calculate(a: Integer): Integer { return 0 - a }','-9223372036854775808'),
               ('(-9223372036854775808) * (-9223372036854775808)','function calculate(a: Integer): Integer { return a * a }','-9223372036854775808'),
               ('9223372036854775807 * 9223372036854775807 * 9223372036854775807','function calculate(a: Integer): Integer { return a * a * a }','9223372036854775807')]
        for expr,helper,arg in cases:
            self.executes('print('+expr+')\n','',status=1,stderr=error)
            self.executes(helper+'\nprint(calculate('+arg+'))\n','',status=1,stderr=error)


    def test_all_boolean_trees_through_four_leaves(self):
        # Boolean-compatible restriction of Lua constructs.lua's finite generator.
        # Every syntax tree is compiled: there is no randomized or sampled domain.
        cases={1:['false','true','global']}
        for size in range(2,5):
            cases[size]=[(op,neg,left,right)
                         for split in range(1,size)
                         for left in cases[split] for right in cases[size-split]
                         for op in ('&&','||') for neg in (False,True)]
        trees=[tree for size in range(1,5) for tree in cases[size]]
        self.assertEqual([len(cases[n]) for n in range(1,5)],[3,36,864,25920])
        self.evidence.controls['boolean_tree_domain']={
            'trees':len(trees),'global_values':[0,1],
            'false_bindings':{'0':'local F=false','1':'literal false'},
            'leaves':['false','true','0==glob'],'chunk_size':192}
        def render(tree,glob,probe=False,position=None):
            if position is None: position=[0]
            if isinstance(tree,str):
                index=position[0];position[0]+=1
                expr={'false':'F' if glob==0 else 'false','true':'true','global':'(0 == glob)'}[tree]
                return f'visit({expr},{index})' if probe else expr
            op,neg,left,right=tree
            expr='('+render(left,glob,probe,position)+' '+op+' '+render(right,glob,probe,position)+')'
            return '!'+expr if neg else expr
        def oracle(tree,glob,position=None):
            if position is None: position=[0]
            if isinstance(tree,str):
                index=position[0];position[0]+=1
                return {'false':False,'true':True,'global':glob==0}[tree],[index]
            op,neg,left,right=tree
            lv,lt=oracle(left,glob,position)
            rv,rt=oracle(right,glob,position)
            use_right=lv if op=='&&' else not lv
            value=(lv and rv) if op=='&&' else (lv or rv)
            return (not value if neg else value),lt+(rt if use_right else [])
        for offset in range(0,len(trees),192):
            with self.subTest(first_tree=offset):
                source=['function visit(value: Boolean, position: Integer): Boolean { print(position); return value }']
                expected=[]
                for glob in (0,1):
                    source += [f'function run{glob}(glob: Integer) {{','let F = false']
                    for tree in trees[offset:offset+192]:
                        expr=render(tree,glob)
                        source += ['let branch = false',f'if {expr} {{ branch = true }}',
                                   'print(branch)',f'print({expr})',f'print({render(tree,glob,True)})']
                        value,trace=oracle(tree,glob)
                        word=str(value).lower()
                        expected += [word,word,*map(str,trace),word]
                    source += ['}']
                source += ['run0(0)','run1(1)']
                self.executes('\n'.join(source)+'\n','\n'.join(expected)+'\n')


    def test_runner_cwd_environment_and_output_isolation(self):
        before_cwd=os.getcwd()
        before_environment=dict(os.environ)
        original=self.directory/'original.txt'
        llvm=self.executes('writeTextFile(argument(0),argument(1))\nprint(readTextFile(argument(0)))\n',
                           'baseline\n',arguments=[str(original),'baseline'])
        for optimization in self.variants():
            directories=[self.directory/(optimization[1:]+'-left'),self.directory/(optimization[1:]+'-right')]
            for directory in directories: directory.mkdir()
            for index,directory in enumerate(directories):
                payload=f'{optimization}-{index}-é'
                sibling=directories[1-index]/'result.txt'
                sibling_before=sibling.read_bytes() if sibling.exists() else None
                run=self.evidence.run([llvm.with_suffix('.'+optimization[1:]),'result.txt',payload],
                                      cwd=directory,env=dict(os.environ,MINYAR_PEER_ISOLATION=payload),
                                      timeout=RUN_TIMEOUT,phase='isolated-execute')
                self.assertEqual((run.returncode,run.stdout,run.stderr),(0,(payload+'\n').encode(),b''))
                self.assertEqual((directory/'result.txt').read_bytes(),payload.encode())
                self.assertEqual(sibling.read_bytes() if sibling.exists() else None,sibling_before)
                self.assertEqual(original.read_bytes(),b'baseline')
                self.assertEqual(os.getcwd(),before_cwd)
                self.assertEqual(dict(os.environ),before_environment)
        probe=self.evidence.run([sys.executable,'-c',
                                 'import json,os; print(json.dumps(dict(marker=os.environ.get("MINYAR_PEER_ISOLATION"),cwd=os.getcwd())))'],
                                cwd=self.directory,env={'MINYAR_PEER_ISOLATION':'fresh'},
                                timeout=RUN_TIMEOUT,phase='isolated-environment-probe')
        self.assertEqual(probe.returncode,0,probe.stderr)
        self.assertEqual(json.loads(probe.stdout),dict(marker='fresh',cwd=str(self.directory)))
        self.assertEqual(dict(os.environ),before_environment)


    def test_ascii_and_empty_scalar_sequence_assembly(self):
        # Every strict check(s,t) invocation in pinned Lua utf8.lua, plus the
        # explicit NUL/control sequence. Lax non-Unicode sequences are excluded.
        sequences = [tuple(map(ord, 'hello World')), (), (27721,23383,47,28450,23383),
                     (0,127,128,2047,2048,65535,65536,1114111),
                     (26085,26412,35486,97,45,52,0,233,243),
                     (0x23cb7,0x2070e,0x20c53,0x2107b,0x20d7c,97,98,0x20ea2),
                     (0x28cca,0x29d98,0x269fa,0x28cd2,0x2512b,0x244d3,0x10ffff),
                     (0,97,98,99,1)]
        for scalars in sequences:
            value = ''.join(map(chr, scalars))
            source = ['let value = '+literal(value),'let parts: List<Text> = []',
                      'print(value.length)','print(value.byteLength)','let i = 0',
                      'while i < value.length { print(value[i]); parts.add(Text(value[i])); i = i + 1 }',
                      'print(i)','print(joinText(parts) == value)','print(joinText(parts))']
            expected=[str(len(scalars)),str(len(value.encode('utf-8'))),*map(chr,scalars),str(len(scalars)),'true',value]
            self.executes('\n'.join(source)+'\n','\n'.join(expected)+'\n')

    def test_signed_integer_corpus_decimal_text_conversion(self):
        source = ['function render(value: Integer): Text { return Text(value) }']
        expected = []
        for value in self.integer_values():
            text = str(value)
            source += [f'let text = render({value})', 'let held = [text]',
                       'text = "replaced"', 'print(held[0])',
                       'print(held[0].length)', 'print(held[0].byteLength)',
                       'print("prefix:" + held[0])']
            expected += [text,str(len(text)),str(len(text)),'prefix:'+text]
        self.executes('\n'.join(source)+'\n','\n'.join(expected)+'\n')

    def test_integer_product_expansions_only_when_every_intermediate_fits(self):
        values = self.integer_values()
        minimum,maximum = -(1<<63),(1<<63)-1
        for offset,count in ((-100,4843),(100,4829)):
            lower,upper,expected = [],[],[]
            for a in values:
                positions = []
                for j,b in enumerate(values):
                    x,y = a+offset,b+offset
                    product,left,right = x*y,x*100,y*100
                    first = product+left if offset<0 else product-left
                    second = first+right if offset<0 else first-right
                    result = second+10000
                    intermediates = (a*b,x,y,product,left,right,first,second,result)
                    if all(minimum<=value<=maximum for value in intermediates):
                        self.assertEqual(result,a*b)
                        positions.append(j)
                        expected += [str(a*b)]*2
                # The accepted b domain is independently computed using Python
                # arbitrary precision before creating the executable bounds.
                if positions:
                    self.assertEqual(positions,list(range(positions[0],positions[-1]+1)))
                    lower.append(positions[0]); upper.append(positions[-1]+1)
                else:
                    lower.append(0); upper.append(0)
            self.assertEqual(len(expected)//2,count)
            sign = '+' if offset<0 else '-'
            source = ['let values = ['+','.join(map(str,values))+']',
                      'let low = ['+','.join(map(str,lower))+']',
                      'let high = ['+','.join(map(str,upper))+']',
                      'let i = 0','while i < values.length {','let a = values[i]',
                      'let j = low[i]','while j < high[i] {','let b = values[j]',
                      f'let x = a + ({offset})',f'let y = b + ({offset})',
                      f'print(x*y {sign} x*100 {sign} y*100 + 10000)',
                      'print(a*b)','j = j + 1','}','i = i + 1','}']
            self.executes('\n'.join(source)+'\n','\n'.join(expected)+'\n')

    def test_extreme_integer_relations_all_operand_placements(self):
        import operator
        values = (-(1<<63),-(1<<63)+1,(1<<63)-2,(1<<63)-1)
        for symbol, oracle in (('<',operator.lt),('<=',operator.le),('>',operator.gt),('>=',operator.ge)):
            source = [f'function compare(a: Integer,b: Integer): Boolean {{ return a {symbol} b }}']
            expected = []
            for a in values:
                for b in values:
                    source += [f'let a = {a}',f'let b = {b}']
                    for left,right in ((str(a),str(b)),('a',str(b)),(str(a),'b'),('a','b')):
                        source += [f'print(({left}) {symbol} ({right}))']
                    source += ['print(compare(a,b))']
                    expected += [str(oracle(a,b)).lower()]*5
            self.executes('\n'.join(source)+'\n','\n'.join(expected)+'\n')

    def test_file_write_and_buffered_close_failures(self):
        from regressions import CLANG, LINK_FLAGS
        probe = ROOT/'tests/peer-pyswru-write-failures.c'
        for path in [probe,ROOT/'runtime/minyar_runtime.c',*sorted((ROOT/'runtime').glob('*.h'))]:
            self.evidence.inputs[str(path.resolve())] = digest(path)
        runtime = self.directory/'write-failure-runtime.o'
        build = self.evidence.run(clang_command([CLANG,'-std=c11','-O2',*LINK_FLAGS,
                                   '-DMINYAR_SYSTEM_HEAP=1','-c',probe,'-o',runtime]),
                                  timeout=60,phase='compile-write-failure-runtime')
        self.assertEqual(build.returncode,0,build.stderr)
        result,llvm = self.compile('let text = readTextFile(argument(0))\n'
                                   'writeTextFile(argument(1),text)\nprint("complete")\n')
        self.assertEqual(result.returncode,0,result.stderr)
        payload_file = self.directory/'payload.txt'
        output = self.directory/'written.txt'
        error = b'Minyar stopped: a requested text file could not be written.\n'
        for optimization in self.variants():
            exe = llvm.with_suffix('.'+optimization[1:])
            link = self.evidence.run(clang_command([CLANG,optimization,*LINK_FLAGS,'-Wno-override-module',
                                      llvm,runtime,'-o',exe]),timeout=30,phase='link-write-failure')
            self.assertEqual(link.returncode,0,link.stderr)
            # Four bytes reach stdio's close/flush path; the long payload exceeds
            # buffering. Both branches use real files and independently checked bytes.
            for payload in (b'abcd',b'abcd'*50000):
                payload_file.write_bytes(payload)
                for failure in ('','write','write-zero','close'):
                    with self.subTest(optimization=optimization,size=len(payload),failure=failure):
                        output.unlink(missing_ok=True)
                        run = self.evidence.run([exe,payload_file,output],timeout=RUN_TIMEOUT,
                                                env=dict(os.environ,MINYAR_PEER_WRITE_FAILURE=failure),
                                                phase='execute-write-failure')
                        expected = (1,b'',error) if failure else (0,b'complete\n',b'')
                        self.assertEqual((run.returncode,run.stdout,run.stderr),expected)
                        written = b'' if failure == 'write-zero' else payload[:len(payload)//2] if failure == 'write' else payload
                        self.assertEqual(output.read_bytes(), written)
                        self.assertEqual(payload_file.read_bytes(),payload)


    @peer_configurations("O2")
    def test_reviewed_allocator_workloads(self):
        import argparse
        import importlib.util
        from regressions import COMPILER, CLANG, LINK_FLAGS
        fixture=ROOT/'tests/peer-pyswru-allocation-cases.json'
        self.evidence.inputs[str(fixture.resolve())]=digest(fixture)
        data=json.loads(fixture.read_text())
        input_path=self.directory/'allocation-input.txt'
        input_bytes=data['input'].encode('utf-8')
        input_path.write_bytes(input_bytes)
        runner=ROOT/'tests/allocation-faults.py'
        self.evidence.inputs[str(runner.resolve())]=digest(runner)
        spec=importlib.util.spec_from_file_location('peer_allocation_campaign',runner)
        campaign=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(campaign)
        campaign.CASES={name:(row['source'].replace('__INPUT_PATH__',literal(str(input_path))),row['stdout'].encode('utf-8'))
                        for name,row in data['cases'].items()}
        output=self.directory/'allocation-results.json'
        mode='sanitize' if LINK_FLAGS else 'native'
        campaign.campaign(argparse.Namespace(mode=mode,compiler=COMPILER,clang=CLANG,
                                            scope='runtime',output=output))
        self.assertEqual(input_path.read_bytes(),input_bytes)
        report=json.loads(output.read_text())
        self.assertEqual(report['status'],'passed')
        self.assertIn('O2',report['configurations'])
        self.evidence.controls['campaign_configurations'] = report['configurations']
        self.assertEqual(len(report['cases']),12)
        for row in report['cases']:
            self.assertEqual(row['mode'],mode)
            self.assertGreater(row['allocation_failures'],0)
            self.assertGreater(row['byte_budget_failures'],0)
            self.assertEqual(row['byte_budget_successes'],2)
            if row['case'] in ('peer-record-growth','peer-join100','peer-join300'):
                self.assertGreater(row['forced_moves'],0)
        self.evidence.controls['peer_allocation_results']=report


    @peer_configurations("O2")
    def test_small_runtime_capacity_pairwise_configurations(self):
        from regressions import CLANG, LINK_FLAGS
        probe=ROOT/'tests/integer-text-cache.c'
        for path in [probe,ROOT/'runtime/minyar_runtime.c',*sorted((ROOT/'runtime').glob('*.h'))]:
            self.evidence.inputs[str(path.resolve())]=digest(path)
        # Complete pairwise combinations of small cache, heap, and cleanup budget.
        # Default cache/budget plus the ordinary system profile are separate controls.
        configurations=[(heap,cache,budget) for heap in (4096,8*1024*1024)
                        for cache in (0,1) for budget in (1,32)]
        configurations += [(8*1024*1024,32768,32)]
        for profile in ('fixed','lazy'):
            for heap,cache,budget in configurations:
                with self.subTest(profile=profile,heap=heap,cache=cache,budget=budget):
                    exe=self.directory/f'{profile}-{heap}-{cache}-{budget}'
                    flags=['-DMINYAR_BOUNDED_HEAP=1',f'-DMINYAR_BOUNDED_HEAP_BYTES={heap}',
                           f'-DMINYAR_INTEGER_TEXT_CACHE_LIMIT={cache}',f'-DEXPECTED_CACHE_LIMIT={cache}',
                           f'-DMINYAR_RC_POLL_BUDGET={budget}']
                    if profile=='lazy':flags+=['-DMINYAR_LAZY_HEAP=1']
                    build=self.evidence.run(clang_command([CLANG,'-std=c11','-O2',*LINK_FLAGS,*flags,probe,'-o',exe]),timeout=60,phase='compile-capacity-probe')
                    self.assertEqual(build.returncode,0,build.stderr)
                    run=self.evidence.run([exe],timeout=30,phase='execute-capacity-probe')
                    self.assertEqual((run.returncode,run.stdout,run.stderr),
                                     (0,f'cache limit {cache}: values, aliases and retained storage passed\n'.encode(),b''))
        exe=self.directory/'system-defaults'
        build=self.evidence.run(clang_command([CLANG,'-std=c11','-O2',*LINK_FLAGS,'-DMINYAR_SYSTEM_HEAP=1',
                                 '-DEXPECTED_CACHE_LIMIT=32768',probe,'-o',exe]),timeout=60,phase='compile-default-probe')
        self.assertEqual(build.returncode,0,build.stderr)
        run=self.evidence.run([exe],timeout=30,phase='execute-default-probe')
        self.assertEqual((run.returncode,run.stdout,run.stderr),
                         (0,b'cache limit 32768: values, aliases and retained storage passed\n',b''))


    def test_zero_divisors_literal_and_parameter_pairs(self):
        error='Minyar stopped: an Integer cannot be divided by zero.\n'
        for numerator,operator in ((3,'/'),(0,'%'),(-4,'/'),(1,'%'),(3,'%')):
            helper=f'function calculate(a: Integer,b: Integer): Integer {{ return a {operator} b }}\n'
            for expression in (f'({numerator}) {operator} 0',f'calculate({numerator},0)'):
                self.executes(helper+'print('+expression+')\n','',status=1,stderr=error)


    @peer_configurations("harness")
    def test_incompatible_compiler_and_runtime_fail_required_suite(self):
        from regressions import COMPILER, RUNTIME, CLANG, LINK_FLAGS
        # Negative controls exercise the real unittest runner. A compiler that
        # silently emits a different program is not allowed to make the suite green.
        built,wrong_ir=self.compile('print(0)\n')
        self.assertEqual(built.returncode,0,built.stderr)
        fake_source=self.directory/'wrong-compiler.c'
        fake=self.directory/('wrong-compiler.exe' if os.name=='nt' else 'wrong-compiler')
        fake_source.write_text('#include <stdio.h>\nint main(int argc,char **argv) {\n'
                               'if (argc != 3) return 2;\n'
                               'FILE *in=fopen('+json.dumps(str(wrong_ir))+',"rb");\n'
                               'FILE *out=fopen(argv[2],"wb");\n'
                               'if (!in || !out) return 3;\n'
                               'int c; while ((c=fgetc(in)) != EOF) { if (fputc(c,out)==EOF) return 4; }\n'
                               'if (ferror(in) || fclose(in) || fclose(out)) return 5;\n'
                               'return 0; }\n')
        fake_build=self.evidence.run(clang_command([CLANG,'-std=c11',fake_source,'-o',fake]),timeout=30,phase='build-incompatible-compiler')
        self.assertEqual(fake_build.returncode,0,fake_build.stderr)
        copied=self.directory/'wrong-copy.ll'
        control=self.evidence.run([fake,'ignored.min',copied],timeout=RUN_TIMEOUT,phase='verify-incompatible-compiler')
        self.assertEqual((control.returncode,control.stdout,control.stderr),(0,b'',b''))
        self.assertEqual(copied.read_bytes(),wrong_ir.read_bytes())
        empty=self.directory/'wrong-runtime.c'
        empty.write_text('int peer_wrong_runtime_abi_marker;\n')
        wrong_runtime=empty.with_suffix('.o')
        build=self.evidence.run(clang_command([CLANG,'-c',*LINK_FLAGS,empty,'-o',wrong_runtime]),timeout=30,phase='build-incompatible-runtime')
        self.assertEqual(build.returncode,0,build.stderr)
        target='PeerPythonSwiftRubyLua.test_iterative_fibonacci_uses_previous_pair'
        for kind,compiler,runtime in (('compiler',fake,RUNTIME),('runtime',COMPILER,wrong_runtime)):
            with self.subTest(incompatible=kind):
                env=dict(os.environ,MINYAR_TEST_COMPILER=str(compiler),MINYAR_TEST_RUNTIME=str(runtime))
                run=self.evidence.run([sys.executable,str(ROOT/'tests/peer-python-swift-ruby-lua.py'),target,'-v'],
                                      env=env,timeout=60,phase='incompatible-required-suite')
                self.assertEqual(run.returncode,1,run.stderr)
                self.assertIn(b'FAILED (',run.stderr)
                self.assertNotIn(b'skipped',run.stderr)
                if kind=='compiler': self.assertIn(b'AssertionError',run.stderr)
                else: self.assertTrue(b'undefined' in run.stderr.lower() or b'unresolved' in run.stderr.lower(),run.stderr)


    def test_demorgan_signed_range_equivalence(self):
        values=(-(1<<63),-(1<<63)+1,-1,0,1,(1<<63)-2,(1<<63)-1)
        source=['function direct(a: Integer, limit: Integer): Boolean { return 0 <= a && a <= limit }',
                'function negated(a: Integer, limit: Integer): Boolean { return !(!(a >= 0) || !(a <= limit)) }']
        expected=[]
        for a in values:
            for limit in values:
                source += [f'print(0 <= ({a}) && ({a}) <= ({limit}))',
                           f'print(!(!(({a}) >= 0) || !(({a}) <= ({limit}))))',
                           f'print(direct({a},{limit}))',f'print(negated({a},{limit}))']
                expected += [str(0<=a<=limit).lower()]*4
        self.executes('\n'.join(source)+'\n','\n'.join(expected)+'\n')


    def test_multiline_operator_and_call_diagnostics_have_locations(self):
        path=ROOT/'tests/peer-pyswru-multiline-diagnostics.json'
        self.evidence.inputs[str(path.resolve())]=digest(path)
        for case in json.loads(path.read_text())['cases']:
            with self.subTest(case=case['id']):
                result,llvm = self.compile(case['source'])
                expected = f"Minyar stopped: line {case['line']}, column {case['column']}: {case['message']}\n"
                self.assertEqual((result.returncode,result.stdout,result.stderr),(1,'',expected))
                self.assertFalse(llvm.exists())

    def test_lua_comparison_results_and_ordinary_recursion_depths(self):
        source = '''let a = 10; let b = 1
print(a < b == false && a > b == true)
function deep(n: Integer, visits: List<Integer>) {
    visits[0] = visits[0] + 1
    if n > 0 { deep(n - 1, visits) }
    print(n)
}
let visits = [0]; deep(10, visits); print(visits[0])
visits[0] = 0; deep(180, visits); print(visits[0])
'''
        expected = 'true\n' + ''.join(f'{n}\n' for n in range(11)) + '11\n'
        expected += ''.join(f'{n}\n' for n in range(181)) + '181\n'
        self.executes(source, expected)

    def test_empty_semicolons_sibling_scopes_and_typed_shadowing(self):
        source = ''';;print("start");;
if true { ;;; }; if true { ; let a = 3; print(a) };
let i = 10
if true { let i = 100; print(i) }
if true { let i = 1000; print(i) }
print(i)
if i != 10 { let i = 20; print(i) } else { let i = 30; print(i) }
print(i)
let x = 1
function shadow(a: Integer) {
    let d0 = 0; let d1 = 1; let d2 = 2; let d3 = 3; let d4 = 4
    let d5 = 5; let d6 = 6; let d7 = 7; let d8 = 8; let d9 = 9
    let x = 3; let b = a; let c = a; let d = b
    if d == b {
        let x = "q"; print(x)
        if true { let x = b; print(x) }
        print(x)
    } else { fail("wrong branch") }
    print(x); print(a); print(b); print(c); print(d)
    print(d0); print(d1); print(d2); print(d3); print(d4)
    print(d5); print(d6); print(d7); print(d8); print(d9)
    let shadow = 10; print(shadow)
}
shadow(2); print(x);;
'''
        self.executes(source, 'start\n3\n100\n1000\n10\n30\n10\nq\n2\nq\n3\n'
                      + '2\n' * 4 + ''.join(f'{n}\n' for n in range(10)) + '10\n1\n')

    def test_boolean_false_values_and_dense_lengths_zero_through_forty(self):
        source = '''let booleans = [true, false, true, false]
let expected = false; let index = 0
while index < booleans.length { expected = !expected; print(booleans[index]); print(booleans[index] == expected); index = index + 1 }
print(index)
let size = 0
while size <= 40 {
    let values: List<Integer> = []; let value = 1
    while value <= size { values.add(value); value = value + 1 }
    print(values.length); index = 0
    while index < values.length { print(values[index]); index = index + 1 }
    size = size + 1
}
'''
        expected = 'true\ntrue\nfalse\ntrue\ntrue\ntrue\nfalse\ntrue\n4\n'
        expected += ''.join(str(size) + '\n' + ''.join(f'{n}\n' for n in range(1, size + 1))
                            for size in range(41))
        self.executes(source, expected)

    def test_three_hundred_eighty_character_concatenations(self):
        fragment = '0123456789' * 8
        source = f'let fragment = {literal(fragment)}\nlet result = ""\nlet n = 1\n'
        source += '''while n <= 300 { result = result + fragment; let temporary = Text(n); n = n + 1 }
print(result.length); print(result.byteLength); print(result)
let prefix = result.slice(0, 10000); result = "replaced"
print(prefix.length); print(prefix); print(fragment)
'''
        joined = fragment * 300
        self.executes(source, f'24000\n24000\n{joined}\n10000\n{joined[:10000]}\n{fragment}\n')

    def test_five_thousand_transient_empty_lists(self):
        self.executes('''function temporary() { let values: List<Integer> = []; if values.length != 0 { fail("nonempty fresh List") } }
let count = 0; while count < 5000 { temporary(); count = count + 1 }; print(count)
''', '5000\n')

    def test_flat_list_literal_preserves_all_263145_positions(self):
        from regressions import CLANG, LINK_FLAGS, RUNTIME
        # Lua's generator emits an initial0 followed by1..2**18+1000 inclusive.
        last = 2**18 + 1000
        source = 'let values = [' + ','.join(map(str, range(last + 1))) + ']\n'
        source += '''print(values.length)
print(values[263142]); print(values[263143]); print(values[263144])
let i = 0; while i < values.length { if values[i] != i { fail("literal position") }; i = i + 1 }; print(i)
'''
        expected = b'263145\n263142\n263143\n263144\n263145\n'
        result, llvm = self.compile(source)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))
        self.evidence.controls['large_literal'] = {'elements': last + 1, 'stdout': expected.decode(),
                                                   'link_timeout_seconds': 180, 'all_positions_checked': True}
        for optimization in self.variants():
            with self.subTest(optimization=optimization):
                executable = llvm.with_suffix('.' + optimization[1:])
                # Retain a bounded stress-case allowance for this exact large
                # upstream literal; its count must not shrink to fit a backend.
                link = self.evidence.run(clang_command([CLANG, optimization, *LINK_FLAGS, '-Wno-override-module', llvm,
                                          RUNTIME, '-o', executable]), timeout=180, phase='link-large-literal')
                self.assertEqual(link.returncode, 0, link.stderr)
                result = self.evidence.run([executable], timeout=30, phase='execute-large-literal')
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected, b''))

    def test_documented_whitespace_and_raw_nul_literal(self):
        # VT/FF are not Minyar whitespace; raw NUL inside Text remains data.
        for character in ('\v', '\f'):
            with self.subTest(character=repr(character)):
                result, llvm = self.compile('let x ' + character + ' = "a\0a"\n')
                self.assertEqual((result.returncode, result.stdout, result.stderr),
                                 (1, '', f"Minyar stopped: line 1, column 7: expected '=', found '{character}'\n"))
                self.assertFalse(llvm.exists())
        self.executes('let x \t\r = "a\0a" \t\r\nprint(x)\nprint(x.length)\nprint(x.byteLength)\nprint(x[1] == "\0"[0])\n',
                      'a\0a\n3\n3\ntrue\n')

    def test_four_line_endings_keep_documented_diagnostic_positions(self):
        for ending in ('\n', '\r', '\n\r', '\r\n'):
            with self.subTest(ending=repr(ending)):
                prefix = 'let a = 1;' + ending + 'let b = 2;' + ending
                self.executes(prefix + 'print(a + b)\n', '3\n')
                comment_source = 'let value = 1;\n// value = 2;' + ending + 'value = 3;\nprint(value)\n'
                self.executes(comment_source, '3\n' if '\n' in ending else '1\n')
                # Raw quoted multiline Text preserves source bytes; Lua's
                # long-bracket normalization and escaped newlines do not apply.
                value = 'hi' + ending + 'there'
                raw_source = 'let text = "' + value + '"\nprint(text)\nprint(text.length)\nprint(text.byteLength)\n'
                self.executes(raw_source, value + f'\n{len(value)}\n{len(value.encode())}\n')
                source = prefix + 'print(missing)\n'
                offset = source.index('missing')
                before = source[:offset]
                # LF advances lines; CR contributes one scalar column.
                line = before.count('\n') + 1
                column = len(before.rsplit('\n', 1)[-1]) + 1
                result, llvm = self.compile(source)
                self.assertEqual((result.returncode, result.stdout, result.stderr),
                                 (1, '', f"Minyar stopped: line {line}, column {column}: I can't find a value named 'missing'\n"))
                self.assertFalse(llvm.exists())

    def test_missing_list_delimiter_after_blank_lines_has_eof_location(self):
        result, llvm = self.compile('let a = [4\n\n')
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (1, '', "Minyar stopped: line 3, column 1: expected ',', found ''\n"))
        self.assertFalse(llvm.exists())

    def test_nested_branch_errors_keep_exact_compile_time_locations(self):
        for depth in (1, 3):
            with self.subTest(depth=depth):
                source = 'let b = false\n' + 'if !b {\n' * depth + 'print(missing)\n' + '}\n' * depth
                result, llvm = self.compile(source)
                self.assertEqual((result.returncode, result.stdout, result.stderr),
                                 (1, '', f"Minyar stopped: line {depth + 2}, column 7: I can't find a value named 'missing'\n"))
                self.assertFalse(llvm.exists())

    def test_ff_at_source_start_is_rejected_as_invalid_utf8(self):
        from regressions import COMPILER, COMPILE_TIMEOUT
        source = self.directory / 'ff.min'; llvm = source.with_suffix('.ll')
        source.write_bytes(b'\xfflet a = 1\n')
        result = self.evidence.run([COMPILER, source, llvm], timeout=COMPILE_TIMEOUT, phase='compile-invalid-encoding')
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (1, b'', b'Minyar stopped: Text contained invalid UTF-8.\n'))
        self.assertFalse(llvm.exists())

    def test_two_source_gap_axes_keep_all_256_diagnostic_locations(self):
        gaps = (1, 2, 3, 10, 124, 125, 126, 127, 128, 129, 130, 255, 256, 257, 500, 1000)
        for first in gaps:
            for second in gaps:
                for operand in ('missing', '"wrong"'):
                    with self.subTest(first=first, second=second, operand=operand):
                        source = 'let b = 10\nprint(b +' + '\n' * first + ' b +' + '\n' * second + ' ' + operand + ')\n'
                        if operand == 'missing':
                            line, column = 2 + first + second, 2
                            message = "I can't find a value named 'missing'"
                        else:
                            line, column = 2 + first, 4
                            message = "the two sides of '+' have different types (Integer and Text)"
                        result, llvm = self.compile(source)
                        self.assertEqual((result.returncode, result.stdout, result.stderr),
                                         (1, '', f'Minyar stopped: line {line}, column {column}: {message}\n'))
                        self.assertFalse(llvm.exists())

    def test_integer_exit_zero_and_one_suppress_following_statements(self):
        for status in (0, 1):
            with self.subTest(status=status):
                self.executes(f'print("before")\nexit({status})\nprint("after")\n', 'before\n', status)

    def test_supported_syntax_depth_shapes_and_controlled_limits(self):
        def program(shape, depth):
            if shape == 'constructor':
                return 'let value = ' + '[' * depth + '0' + ']' * depth + '\nprint(value' + '[0]' * depth + ')\n', '0\n'
            if shape == 'parentheses':
                return 'print(' + '(' * depth + '2' + ')' * depth + ')\n', '2\n'
            if shape == 'call':
                # The source identity preserves nonintegral 2.2. Text retains
                # that exact observable value without claiming Float support.
                return 'function identity(x: Text): Text { return x }\nprint(' + 'identity(' * depth + '"2.2"' + ')' * depth + ')\n', '2.2\n'
            if shape == 'block':
                return 'if true { ' * depth + 'print("done")' + ' }' * depth + '\n', 'done\n'
            if shape == 'while':
                return 'while false { ' * depth + 'fail("inner ran")' + ' }' * depth + '\nprint("done")\n', 'done\n'
            if shape == 'if-else':
                return 'if false { fail("wrong branch") } else { ' * depth + 'print("done")' + ' }' * depth + '\n', 'done\n'
            return 'let a = ""\nprint(' + 'a + ' * depth + '"a")\n', 'a\n'
        for shape in ('constructor', 'parentheses', 'call', 'block', 'while', 'if-else', 'concat'):
            for depth in (100, 500):
                with self.subTest(shape=shape, depth=depth):
                    source, expected = program(shape, depth)
                    self.executes(source, expected)
            if shape == 'concat':
                continue  # Left-associated Text addition is an iterative parser path.
            with self.subTest(shape=shape, depth=100000):
                source, expected = program(shape, 100000)
                result, llvm = self.compile(source)
                self.assertIn(result.returncode, (0, 1))
                self.assertEqual(result.stdout, '')
                if result.returncode:
                    self.assertEqual(result.stderr, 'Minyar stopped: the program exceeded the maximum call depth.\n')
                    self.assertFalse(llvm.exists())
                else:
                    self.assertEqual(result.stderr, '')
                    self.executes(source, expected)

    def test_runtime_cleanup_without_allocations_and_poisoned_format_buffers(self):
        from regressions import CLANG, LINK_FLAGS
        probe = ROOT / 'tests/peer-pyswru-runtime-probes.c'
        for path in (probe, ROOT / 'runtime/minyar_runtime.c', *sorted((ROOT / 'runtime').glob('*.h'))):
            self.evidence.inputs[str(path.resolve())] = digest(path)
        expected = {
            'chain': b'200001 objects released; zero allocation attempts, live objects, bytes and blocks\n',
            'format': b'16 integer formatting boundary strings and terminators passed\n',
        }
        for initialization in ('zero', 'pattern'):
            for optimization in self.variants():
                with self.subTest(initialization=initialization, optimization=optimization):
                    executable = self.directory / f'runtime-{initialization}-{optimization[1:]}'
                    compiled = self.evidence.run(clang_command([CLANG, '-std=c11', optimization, '-UNDEBUG', *LINK_FLAGS,
                                                  '-ftrivial-auto-var-init=' + initialization,
                                                  probe, '-o', executable]), timeout=60, phase='compile-runtime-probe')
                    self.assertEqual(compiled.returncode, 0, compiled.stderr)
                    for case, stdout in expected.items():
                        result = self.evidence.run([executable, case], timeout=30, phase='execute-runtime-probe')
                        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, stdout, b''))

    @peer_configurations('O2')
    def test_runtime_applicable_strict_warning_profiles(self):
        from regressions import CLANG, LINK_FLAGS
        source = ROOT / 'runtime/minyar_runtime.c'
        for path in (source, *sorted((ROOT / 'runtime').glob('*.h'))):
            self.evidence.inputs[str(path.resolve())] = digest(path)
        warnings = ['-Wall', '-Wextra', '-Werror', '-Wshadow', '-Wundef', '-Wwrite-strings',
                    '-Wredundant-decls', '-Wdouble-promotion', '-Wstrict-prototypes', '-Wold-style-definition']
        configurations = set()
        for profile, flags in [('default', []), ('system', ['-DMINYAR_SYSTEM_HEAP=1']),
                               ('bounded', ['-DMINYAR_BOUNDED_HEAP=1']), ('compiler', ['-DMINYAR_COMPILER_ARENA=1'])]:
            with self.subTest(profile=profile):
                command = clang_command([CLANG, '-std=c11', '-O2', *warnings, *LINK_FLAGS, *flags,
                           '-c', source, '-o', self.directory / f'{profile}.o'])
                result = self.evidence.run(command, timeout=60, phase='compile-strict-warnings')
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'', b''))
                configurations.update(flag[1:] for flag in command if flag in ('-O0', '-O1', '-O2', '-O3', '-Os'))
        self.evidence.controls['campaign_configurations'] = sorted(configurations)

    @peer_configurations('O2')
    def test_owned_recursion_allocator_growth_campaign(self):
        import argparse
        import importlib.util
        from regressions import COMPILER, CLANG, LINK_FLAGS
        runner = ROOT / 'tests/allocation-faults.py'
        self.evidence.inputs[str(runner.resolve())] = digest(runner)
        spec = importlib.util.spec_from_file_location('peer_recursive_allocation_campaign', runner)
        campaign = importlib.util.module_from_spec(spec); spec.loader.exec_module(campaign)
        # Keeping an owned Text across each call activates Minyar owner-frame
        # allocation. Scalar-only native calls have no Lua VM-stack allocator.
        source = '''function grow(n: Integer): Integer {
    let label = "frame" + Text(40000 + n)
    if n == 0 { print(label); return 1 }
    let result = 1 + grow(n - 1)
    if label.length != 10 { fail("lost caller Text") }
    return result
}
print(grow(100))
'''
        input_path = self.directory / 'large-pair.txt'
        input_path.write_bytes(b'a' * 10000)
        pair_source = 'let text = readTextFile(' + literal(str(input_path)) + ')\n'
        pair_source += '''let parts = [text, text]
let joined = joinText(parts)
parts = []; text = "replaced"
print(joined.length); print(joined)
'''
        campaign.CASES = {
            'peer-owned-recursion': (source, b'frame40000\n101\n'),
            'peer-large-pair': (pair_source, b'20000\n' + b'a' * 20000 + b'\n'),
        }
        output = self.directory / 'recursive-allocation-results.json'
        mode = 'sanitize' if LINK_FLAGS else 'native'
        campaign.campaign(argparse.Namespace(mode=mode, compiler=COMPILER, clang=CLANG, scope='runtime', output=output))
        report = json.loads(output.read_text())
        self.assertEqual(report['status'], 'passed')
        self.assertIn('O2', report['configurations'])
        self.assertEqual(input_path.read_bytes(), b'a' * 10000)
        self.assertEqual(len(report['cases']), 4)
        self.assertEqual({row['case'] for row in report['cases']}, set(campaign.CASES))
        for row in report['cases']:
            self.assertGreaterEqual(row['allocation_failures'], 101 if row['case'] == 'peer-owned-recursion' else 1)
            self.assertGreater(row['byte_budget_failures'], 0)
            self.assertEqual(row['byte_budget_successes'], 2)
        self.evidence.controls['campaign_configurations'] = report['configurations']
        self.evidence.controls['peer_allocation_results'] = report


    def rejects_exact_diagnostic(self, source, diagnostic):
        expected = 'Minyar stopped: ' + diagnostic + '\n'
        self.evidence.controls.setdefault('rejection_oracles', []).append({
            'source': f'case{self.serial + 1}.min', 'status': 1,
            'stdout': '', 'stderr': expected, 'llvm_created': False,
        })
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr, expected)
        self.assertFalse(llvm.exists(), 'invalid source left LLVM output behind')


    def test_integer_total_order_1001_and_1002(self):
        # assert_total_order's six helpers check the original and mirrored
        # operation for each pair. The literal truth table is independent of
        # Minyar and includes every one of the 24 source observations.
        source = '''function observe(a: Integer, b: Integer): Nothing {
print(a == b); print(b == a)
print(a != b); print(b != a)
print(a < b); print(b > a)
print(a <= b); print(b >= a)
print(a > b); print(b < a)
print(a >= b); print(b <= a)
}
observe(1001, 1001)
observe(1001, 1002)
'''
        expected = (True, True, False, False, False, False, True, True,
                    False, False, True, True,
                    False, False, True, True, True, True, True, True,
                    False, False, False, False)
        self.executes(source, ''.join(str(value).lower() + '\n' for value in expected))


    def test_euclidean_gcd_full_signed_one_through_nineteen_domain(self):
        # The source helper uses floor remainder. Convert truncating Minyar %
        # explicitly; this is an algorithm adaptation, not a language-policy
        # assertion. All inputs are nonzero and far inside signed Integer.
        source = '''function floorRemainder(left: Integer, right: Integer): Integer {
let remainder = left % right
if remainder != 0 && ((remainder < 0) != (right < 0)) {
return remainder + right
}
return remainder
}
function gcd(first: Integer, second: Integer): Integer {
let a = first
let b = second
while a != 0 {
let next = floorRemainder(b, a)
b = a
a = next
}
return b
}
function observe(index: Integer, a: Integer, b: Integer): Nothing {
print(index); print(a); print(b); print(gcd(a, b))
}
'''
        examples = [(10, 12, 2), (10, 15, 5), (10, 11, 1), (100, 15, 5),
                    (-10, 2, -2), (10, -2, 2), (-10, -2, -2)]
        cases = list(examples)
        for i in range(1, 20):
            for j in range(1, 20):
                for a, b in ((i, j), (-i, j), (i, -j), (-i, -j)):
                    # Original grid checks only sign. Exact mathematical
                    # magnitude is a stronger independently derived oracle.
                    cases.append((a, b, math.gcd(abs(a), abs(b)) * (1 if a > 0 else -1)))
        self.assertEqual(len(cases), 1451)
        expected = []
        for index, (a, b, answer) in enumerate(cases):
            source += f'observe({index}, {a}, {b})\n'
            expected.extend((index, a, b, answer))
        self.evidence.controls['domain_coverage'] = {'calls': 1451, 'explicit_examples': 7, 'signed_grid': 1444}
        self.executes(source, ''.join(str(value) + '\n' for value in expected))


    def test_uppercase_true_is_an_identifier(self):
        self.executes('let TRUE: Integer = 42\nprint(TRUE)\n', '42\n')


    def test_five_ordinary_quote_payloads(self):
        payloads = ('', "'", '"', 'doesn\'t "shrink" does it', 'does "shrink" doesn\'t it')
        lengths = (0, 1, 1, 24, 24)
        source, expected = [], []
        for index, (value, length) in enumerate(zip(payloads, lengths)):
            self.assertEqual(len(value), length)
            # Both source spellings denote Text; Minyar single quotes denote
            # Character, so normalize both representations to double quotes.
            source += [f'let x{index}: Text = {literal(value)}',
                       f'let y{index}: Text = {literal(value)}',
                       f'print(x{index})', f'print(x{index}.length)',
                       f'print(x{index} == y{index})']
            expected += [value, str(length), 'true']
            if length == 1:
                source += [f'print(x{index}[0])']
                expected += [value]  # Exact byte oracle also fixes U+0027/U+0022.
        self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')


    def test_four_if_chain_shapes(self):
        # Numeric truthiness becomes Boolean guards; elif becomes nested if.
        self.executes('''if true { print(1) }
if true { print(2) } else { print(20) }
if false { print(30) } else { if false { print(31) } }
if false { print(40) } else {
if false { print(41) } else {
if false { print(42) } else {
if false { print(43) } else { print(4) }
}
}
}
print("done")
''', '1\n2\n4\ndone\n')


    def test_six_unparenthesized_boolean_expressions(self):
        cases = [('!true', False), ('true && true', True), ('true || true', True),
                 ('!!!true', False), ('!true && true && true', False),
                 ('true && true || true && true && true || !true && true', True)]
        source, expected = [], []
        for index, (expression, answer) in enumerate(cases):
            source += [f'print({expression})', f'if {expression} {{ print({index}) }}']
            expected += [str(answer).lower()]
            if answer:
                expected += [str(index)]
        source += ['print("done")']
        expected += ['done']
        self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')


    def test_comparison_result_and_all_six_branch_forms(self):
        self.executes('''if true { print("atom") }
let x = (1 == 1)
print(x)
if 1 == 1 { print("equal") }
if 1 != 1 { print("unequal") }
if 1 < 1 { print("less") }
if 1 > 1 { print("greater") }
if 1 <= 1 { print("lessEqual") }
if 1 >= 1 { print("greaterEqual") }
print("done")
''', 'atom\ntrue\nequal\nlessEqual\ngreaterEqual\ndone\n')


    def test_all_additive_and_multiplicative_expression_shapes(self):
        # These source statements require successful evaluation, without value
        # assertions. Exact values strengthen that contract. Python / produces
        # Float here; both explicit divisions are exactly integral (1 / 1).
        expressions = ('1', '1 + 1', '1 - 1 - 1', '1 - 1 + 1 - 1 + 1',
                       '1 * 1', '1 / 1', '1 % 1', '1 / 1 * 1 % 1')
        answers = (1, 2, -1, 1, 1, 1, 0, 0)
        self.executes(''.join(f'print({expression})\n' for expression in expressions),
                      ''.join(f'{answer}\n' for answer in answers))


    def test_negating_text_rejects_before_llvm(self):
        self.rejects('print(-"a")\n', 'line 1, column 11: negation needs an Integer or Float')


    def test_incomplete_function_three_newline_placements(self):
        # Source asserts a diagnostic message, not an exact position. Minyar
        # diagnoses the absent body before argument-list parsing at EOF.
        for source in ('function foo(', '\nfunction foo(', 'function foo(\n'):
            with self.subTest(source=source):
                self.rejects(source, "a declaration is missing its '{ ... }' body")


    def test_all_twelve_bad_radix_tokens_reject(self):
        tokens = ('0b12', '0b1_2', '0b2', '0b1_', '0b', '0o18', '0o1_8',
                  '0o8', '0o1_', '0o', '0x1_', '0x')
        for token in tokens:
            with self.subTest(token=token):
                # Binary/octal prefixes and digit separators remain unsupported.
                # The hexadecimal prefix consumes 0x1 before the invalid '_'.
                column, name = (10, '_') if token == '0x1_' else (8, token[1:])
                self.rejects_exact_diagnostic(f'print({token})\n',
                             f"line 1, column {column}: I can't find a value named '{name}'")


    def test_exact_prefix_removal_values(self):
        # Only example-7: two value equalities. Neighboring object identity,
        # mutation, encoding and partial-byte contracts are not claimed.
        self.executes('''function deletePrefix(value: Text, prefix: Text): Text {
if prefix.length <= value.length {
if value.slice(0, prefix.length) == prefix {
return value.slice(prefix.length, value.length)
}
}
return value
}
let first = deletePrefix("hello", "hell")
let second = deletePrefix("hello", "hello")
print(first); print(first.length)
print(second); print(second.length)
''', 'o\n1\n\n0\n')


    def test_exact_suffix_removal_values(self):
        self.executes('''function deleteSuffix(value: Text, suffix: Text): Text {
if suffix.length <= value.length {
if value.slice(value.length - suffix.length, value.length) == suffix {
return value.slice(0, value.length - suffix.length)
}
}
return value
}
let first = deleteSuffix("hello", "ello")
let second = deleteSuffix("hello", "hello")
print(first); print(first.length)
print(second); print(second.length)
''', 'h\n1\n\n0\n')


    def test_binary_enumerator_size_uses_bytes_for_all_three_inputs(self):
        # The upstream file declares encoding: binary. Its third literal is
        # ten BINARY codepoints/bytes, even though those bytes also form five
        # valid UTF8 scalars. Explicit size metadata models only that mode;
        # it does not claim a general codepoint Enumerator source API.
        source = '''record BinaryEnumerator { value: Text }
function binaryEnumerator(value: Text): BinaryEnumerator {
return BinaryEnumerator { value: value }
}
function size(iterator: BinaryEnumerator): Integer { return iterator.value.byteLength }
function observe(value: Text) {
let iterator = binaryEnumerator(value)
print(size(iterator)); print(value.byteLength)
print(size(iterator) == value.byteLength)
print(iterator.value)
print(iterator.value.length)
}
observe("hello")
observe("ola")
observe("Ç∂éƒg")
'''
        self.executes(source, '5\n5\ntrue\nhello\n5\n3\n3\ntrue\nola\n3\n10\n10\ntrue\nÇ∂éƒg\n5\n')


    def test_ascii_codepoints_form_complete_numeric_scalar_list(self):
        fixture = ROOT / 'tests/peer-pyswru-codepoints-runtime.c'
        self.evidence.inputs[str(fixture.resolve())] = digest(fixture)
        self.evidence.controls['domain_coverage'] = {'input_hex':'616263', 'numeric_scalars':[97,98,99], 'array_length':3}
        for optimization in self.variants():
            with self.subTest(optimization=optimization):
                executable = self.directory / ('codepoints.' + optimization[1:])
                command = clang_command([CLANG, '-std=c11', optimization, *LINK_FLAGS, '-Wall', '-Wextra', '-Werror',
                           fixture, RUNTIME, '-o', executable])
                result = self.evidence.run(command, timeout=30, phase='link-c-runtime-probe')
                self.assertEqual(result.returncode, 0, result.stderr)
                result = self.evidence.run([executable, 'abc'], timeout=RUN_TIMEOUT, phase='execute')
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'3\n97\n98\n99\n', b''))



    def executes_with_clean_compilation(self, source, expected):
        # These positive source controls require no compiler warning/output.
        # Reuse the shared execution/configuration oracle and check the real
        # compile result before the normal link/execute phases.
        from unittest.mock import patch
        compile_source = self.compile

        def checked_compile(source):
            result, llvm = compile_source(source)
            if result.returncode == 0:
                self.assertEqual(result.stdout, '')
                self.assertEqual(result.stderr, '')
            return result, llvm

        with patch.object(self, 'compile', checked_compile):
            return self.executes(source, expected)


    def test_ordinary_positional_calls_keep_repetitions_and_trailing_commas(self):
        # f1's declaration is the immediately preceding source helper. Keep
        # both direct zero-argument calls, both calls of f2(1), and both of
        # f3(1,2), including the original trailing commas. Output is added to
        # make complete parameter binding observable; the source bodies pass.
        # a1/a2 are declaration-only source observations and remain uncalled.
        self.executes('''function f1(): Nothing { print("f1") }
f1()
function f2(one_argument: Integer): Nothing { print(one_argument) }
function f3(two: Integer, arguments: Integer): Nothing {
print(two); print(arguments)
}
function a1(one_arg: Integer,): Nothing { }
function a2(two: Integer, args: Integer,): Nothing { }
f1()
f2(1)
f2(1,)
f3(1, 2)
f3(1, 2,)
''', 'f1\nf1\n1\n1\n1\n2\n1\n2\n')


    def test_one_positional_parameter_declaration_accepts_trailing_comma(self):
        # Exact supported declaration f(a,) among fifteen source signatures.
        # The other fourteen require variadic or keyword-only parameters.
        # Calling with1 and observing it is explicit local instrumentation.
        self.executes('''function f(a: Integer,): Nothing { print(a) }
f(1)
''', '1\n')


    def test_bare_and_integer_returns_keep_actual_callers(self):
        # Preserve both helper bodies and their actual source callers at
        # lines875/876. Output strengthens the original compile/run-only
        # assertions. The neighboring starred return is outside this subset.
        self.executes('''function g1(): Nothing { return }
function g2(): Integer { return 1 }
g1()
print("g1 returned")
let x = g2()
print(x)
''', 'g1 returned\n1\n')


    def test_parenthesized_integer_and_all_three_plain_list_atoms(self):
        # Four supported atom cells, in their source order. Use one Integer
        # binding and one List binding because Minyar bindings have fixed
        # types. The two distinct [] assignments must both stay observable.
        # Numeric operand-valued `or` and tuple atoms remain excluded.
        self.executes('''let scalar = (1)
print(scalar)
let values: List<Integer> = []
print(values.length)
values = [1]
print(values.length); print(values[0])
values = []
print(values.length)
''', '1\n0\n1\n1\n0\n')


    def test_all_nine_text_selectors_keep_relative_indices_and_omitted_bounds(self):
        # Explicit relative-index/default-bound helpers adapt the exact
        # source payload01234 and nine selectors. Minyar's native operations
        # do not wrap negative positions. These inputs need no clipping or
        # step handling; neither is claimed, nor the earlier module selectors.
        self.executes('''function relativeIndex(value: Text, index: Integer): Character {
let position = index
if position < 0 { position = value.length + position }
return value[position]
}
function relativeSlice(value: Text, hasStart: Boolean, start: Integer, hasEnd: Boolean, end: Integer): Text {
let first = 0
if hasStart {
first = start
if first < 0 { first = value.length + first }
}
let last = value.length
if hasEnd {
last = end
if last < 0 { last = value.length + last }
}
return value.slice(first, last)
}
let a = "01234"
print(relativeIndex(a, 0))
print(relativeIndex(a, -1))
print(relativeSlice(a, true, 0, true, 5))
print(relativeSlice(a, false, 0, true, 5))
print(relativeSlice(a, true, 0, false, 0))
print(relativeSlice(a, false, 0, false, 0))
print(relativeSlice(a, true, -5, false, 0))
print(relativeSlice(a, false, 0, true, -1))
print(relativeSlice(a, true, -4, true, -3))
''', '0\n4\n01234\n01234\n01234\n01234\n01234\n0123\n1\n')


    def test_seven_integer_literal_adjacencies_reject(self):
        # These source cells require SyntaxError and no warning, rather than
        # the neighboring successful compile plus warning/filter protocol.
        # Keep the complete original expression, including0or x's final x.
        for expression, column, name in (
            ('0xfand x', 11, 'nd'), ('0xfspam', 10, 'spam'),
            ('0o7spam', 8, 'o7spam'), ('0b1spam', 8, 'b1spam'),
            ('9spam', 8, 'spam'), ('0or x', 8, 'or'), ('0spam', 8, 'spam'),
        ):
            with self.subTest(expression=expression):
                # Hexadecimal literals consume valid hex digits before the
                # unknown name; binary and octal prefixes remain unsupported.
                self.rejects_exact_diagnostic(f'print({expression})\n',
                                   f"line 1, column {column}: I can't find a value named '{name}'")


    def test_fraction_slash_is_rejected_after_all_eight_numeric_spellings(self):
        # Full source scanner runs before parsing and must reject U+2044 for
        # every original prefix, even prefixes unavailable as Minyar values.
        # All source prefixes are ASCII; column counts Unicode characters.
        for number in ('0xf', '0o7', '0b1', '9', '0', '1.', '1e3', '1j'):
            with self.subTest(number=number):
                self.rejects_exact_diagnostic(f'print({number}⁄7)\n',
                                   f"line 1, column {7 + len(number)}: names must use ASCII letters, digits, and '_'; found non-ASCII character '⁄'")


    def test_indexed_list_literal_keeps_the_outer_list(self):
        # Positive source control [[1,2][0]], compiled with warnings escalated.
        # The exact one-element outer List and its computed1 are observable.
        self.executes_with_clean_compilation('''let result = [[1, 2][0]]
print(result.length)
print(result[0])
''', '1\n1\n')


    def test_sliced_list_literal_keeps_both_collection_levels(self):
        # Positive source control [[1,2][1:2]]. An explicit copying helper
        # replaces unsupported slice syntax and retains start1/end2, the
        # returned inner List[2], and the one-element outer List[[2]].
        self.executes_with_clean_compilation('''function listSlice(value: List<Integer>, start: Integer, end: Integer): List<Integer> {
let result: List<Integer> = []
let position = start
while position < end {
result.add(value[position])
position = position + 1
}
return result
}
let result = [listSlice([1, 2], 1, 2)]
print(result.length)
print(result[0].length)
print(result[0][0])
''', '1\n1\n2\n')


    def test_reference_self_assignment_preserves_all_specialized_set_values(self):
        # Source x=x starts with Set{2,3,4}. Represent its three values as
        # List[2,3,4] solely for this reference/name-load observation; no Set
        # ordering, uniqueness or heterogeneous rebinding contract is claimed.
        # First check the sole-owner case; then add an explicit alias variant
        # whose appended5 is local identity instrumentation, not upstream input.
        for with_alias in (False, True):
            with self.subTest(with_alias=with_alias):
                source = 'let x = [2, 3, 4]\n'
                if with_alias:
                    source += 'let alias = x\n'
                source += 'x = x\nprint(x.length)\nprint(x[0]); print(x[1]); print(x[2])\n'
                expected = '3\n2\n3\n4\n'
                if with_alias:
                    source += 'alias.add(5)\nprint(x.length); print(x[3])\n'
                    expected += '4\n5\n'
                self.executes(source, expected)


    def test_missing_nonnegative_clipped_substring_matrix(self):
        # CPython clips endpoints; Minyar native slice requires a valid range.
        # This explicit adapter preserves each of the 84 missing input pairs.
        # The other 94 source pairs already have direct native slice coverage.
        source = ['''function clippedSlice(value: Text, start: Integer, end: Integer): Text {
let first = start
let last = end
if first > value.length { first = value.length }
if last > value.length { last = value.length }
if last < first { return "" }
return value.slice(first, last)
}''']
        expected = []
        cells = []
        total = 0
        for text in ('ab', 'ab¡¢', 'ab¡¢你好', 'ab¡¢你好😀😁'):
            for start in [*range(len(text) + 2), 9223372036854775807]:
                for end in [*range(max(start - 1, 0), len(text) + 2), 9223372036854775807]:
                    total += 1
                    if 0 <= start <= end <= len(text):
                        continue
                    result = text[start:end]  # independent host slicing oracle
                    cell = len(cells)
                    cells.append({'text': text, 'start': start, 'end': end, 'expected': result})
                    source += [f'function case{cell}() {{', f'let root = {literal(text)}',
                               f'let view = clippedSlice(root, {start}, {end})',
                               'root = "released"', 'print(view)', 'print(view.length)',
                               'print(view.byteLength)', '}', f'case{cell}()']
                    expected += [result, str(len(result)), str(len(result.encode('utf-8')))]
        self.assertEqual(total, 178)
        self.assertEqual(len(cells), 84)
        self.evidence.controls['source_domain'] = {'total': total, 'new_cells': cells,
            'existing_strict_spans': 94, 'adaptation': 'explicit nonnegative clipping adapter; native slice is strict'}
        self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')


    def test_utf8_constructor_value_projections_keep_complete_bytes(self):
        # File reads preserve bytes and scalar operations validate lazily.
        # This transfers decoded values, not CPython allocation/pointer APIs.
        # Only ASCII abc,count2 is sliced; byte counts are not scalar counts
        # for the other inputs. Embedded NUL remains part of the full value.
        cells = [(b'abc', None), (b'abc', 2), (b'abc\0def', None),
                 (bytes.fromhex('c2a1c2a2'), None), (bytes.fromhex('e4bda0'), None),
                 (bytes.fromhex('f09f9880'), None), (b'', None)]
        source = []
        expected = []
        for index, (raw, count) in enumerate(cells):
            path = self.directory / f'constructor-{index}.bin'
            path.write_bytes(raw)
            value = (raw if count is None else raw[:count]).decode('utf-8')
            source += [f'function case{index}() {{', f'let original = readTextFile({literal(str(path))})',
                       'print(original.byteLength)', 'let value = original' if count is None else 'let value = original.slice(0, 2)',
                       'print(value.length)', 'print(value.byteLength)', 'print(value)']
            source += [f'print(value[{position}])' for position in range(len(value))]
            source += ['}', f'case{index}()']
            expected += [str(len(raw)), str(len(value)), str(len(value.encode('utf-8'))), value, *value]
        self.evidence.controls['source_domain'] = [{'hex': raw.hex(), 'count': count,
            'expected': (raw if count is None else raw[:count]).decode('utf-8')} for raw, count in cells]
        self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')


    def test_lone_a1_decoder_view_rejects_at_scalar_operation(self):
        # The missing exact continuation byte; C2 is already in the shared
        # 83-vector corpus. No eager file-ingress rejection is asserted.
        path = self.directory / 'lone-a1.bin'
        path.write_bytes(bytes.fromhex('a1'))
        self.executes(f'let value = readTextFile({literal(str(path))})\nprint(value.length)\n',
                      '', 1, 'Minyar stopped: Text contained invalid UTF-8.\n')


    def test_invalid_a1_and_c2_preserve_raw_ingress_and_complete_byte_roundtrip(self):
        # These successful byte-only observations distinguish lazy validation
        # from an eager reader that would produce the same later fatal error.
        source = []
        outputs = []
        for index, raw in enumerate((bytes.fromhex('a1'), bytes.fromhex('c2'))):
            incoming = self.directory / f'raw-invalid-{index}.bin'
            outgoing = self.directory / f'raw-preserved-{index}.bin'
            incoming.write_bytes(raw)
            source += [f'let value{index} = readTextFile({literal(str(incoming))})',
                       f'print(value{index}.byteLength)',
                       f'writeTextFile({literal(str(outgoing))}, value{index})']
            outputs.append((outgoing, raw))
        CompilerTestCase.executes(self, '\n'.join(source) + '\n', '1\n1\n', optimizations=self.variants(), file_outputs=outputs)


    def unicode_capi_runtime_probe(self, optimization):
        fixture = ROOT / 'tests/peer-pyswru-unicode-runtime.c'
        self.evidence.inputs[str(fixture.resolve())] = digest(fixture)
        executable = self.directory / ('unicode-probe.' + optimization[1:])
        result = self.evidence.run(clang_command([CLANG, '-std=c11', optimization, *LINK_FLAGS,
            '-Wall', '-Wextra', '-Werror', fixture, RUNTIME, '-o', executable]),
            timeout=30, phase='link-c-runtime-probe')
        self.assertEqual(result.returncode, 0, result.stderr)
        return executable


    def test_valid_scalar_lengths_and_numeric_character_reads(self):
        # ord observations use the real int-returning runtime API. Checked and
        # macro CPython paths share these values, not Minyar's implementation.
        # Two source strings containing surrogate code units are excluded.
        lengths = [('', 0), ('abc', 3), ('¡¢', 2), ('你好', 2), ('a😀', 2)]
        positions = [(text, index, ord(character)) for text in ('abc', '¡¢', '你好', 'a😀') for index, character in enumerate(text)]
        self.assertEqual(len(positions), 9)
        self.evidence.controls['source_domain'] = {'lengths': lengths, 'numeric_character_reads': positions,
            'excluded_surrogate_strings': [{'source_codepoints': [97, 55296, 98, 57343, 99], 'source_length': 5}, {'source_codepoints': [55348, 56606], 'source_length': 2}]}
        for optimization in self.variants():
            executable = self.unicode_capi_runtime_probe(optimization)
            for text, expected in lengths:
                with self.subTest(optimization=optimization, text=text, operation='length'):
                    result = self.evidence.run([executable, text, 'length'], timeout=RUN_TIMEOUT, phase='execute')
                    self.assertEqual((result.returncode, result.stdout, result.stderr), (0, f'{expected}\n'.encode(), b''))
            for text, index, expected in positions:
                with self.subTest(optimization=optimization, text=text, index=index):
                    result = self.evidence.run([executable, text, str(index)], timeout=RUN_TIMEOUT, phase='execute')
                    self.assertEqual((result.returncode, result.stdout, result.stderr), (0, f'{expected}\n'.encode(), b''))


    def test_checked_numeric_scalar_reads_reject_all_four_invalid_positions(self):
        # Python raises IndexError; Minyar terminates with a bounds diagnostic.
        # Preserve len/9223372036854775807/-1/(-9223372036854775808) for each of the four scalar-valid strings.
        # NUL-terminator reads from the unchecked macros are not this contract.
        cells = [(text, position) for text in ('abc', '¡¢', '你好', 'a😀') for position in (len(text), 9223372036854775807, -1, (-9223372036854775808))]
        self.assertEqual(len(cells), 16)
        self.evidence.controls['source_domain'] = cells
        for optimization in self.variants():
            executable = self.unicode_capi_runtime_probe(optimization)
            for text, position in cells:
                with self.subTest(optimization=optimization, text=text, position=position):
                    message = 'a Text position cannot be negative.' if position < 0 else 'a Text position was outside the Text.'
                    result = self.evidence.run([executable, text, str(position)], timeout=RUN_TIMEOUT, phase='execute')
                    self.assertEqual((result.returncode, result.stdout, result.stderr),
                        (1, b'', ('Minyar stopped: ' + message + '\n').encode()))


if __name__ == '__main__':
    from peer_runner import main
    main()
