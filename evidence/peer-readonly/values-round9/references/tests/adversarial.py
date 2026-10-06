#!/usr/bin/env python3
"""Check ownership, mutation, control flow, and evaluation order.

Cases run at O0/O2 and use the same compiler/runtime environment variables as
regressions.py, including the sanitizer and exact-cleanup runtime."""
import random
import unittest
from regressions import CompilerTestCase


def literal(text):
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t') + '"'


class Adversarial(CompilerTestCase):
    def test_borrowed_parameters_can_be_reassigned_and_escape(self):
        self.executes('''record Box { words: List<Text> }
function alias(value: Text): Text { return value }
function mutate(value: Text, words: List<Text>): Text {
words[0] = "replacement" + "!"
let original = value
value = alias(value)
value = "local" + "!"
words.add(original)
return original
}
function recursive(value: Text, depth: Integer): Text {
if depth == 0 { return value }
return recursive(value, depth - 1)
}
function replace(box: Box, other: Box): Box {
box = other
return box
}
let words: List<Text> = []
words.add("original" + "!")
let box = Box { words: words }
print(mutate(box.words[0], words))
print(words[0])
print(words[1])
print(recursive("recursive" + "!", 80))
print(replace(box, Box { words: words }).words[1])
''', 'original!\nreplacement!\noriginal!\nrecursive!\noriginal!\n')

    def test_readonly_parameter_needs_no_ownership_frame(self):
        result, llvm = self.compile('''record Point { x: Integer }
function read(point: Point): Integer { return point.x }
print(read(Point { x: 7 }))
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        functions = llvm.read_text().split('define ')
        function = next(part.split('\n}', 1)[0] for part in functions
                        if part.startswith('i64 ') and '(ptr %argument.0)' in part)
        self.assertNotIn('call void @minyar_rc_', function)

    def test_source_truncations_produce_language_diagnostics(self):
        source = '''record Box { text: Text }
function make(value: Text): Box { return Box { text: value } }
let boxes: List<Box> = []
boxes.add(make("hello"))
if boxes.length > 0 { print(boxes[0].text) }
'''
        for end in range(len(source)):
            with self.subTest(prefix_length=end):
                result, _ = self.compile(source[:end])
                self.assertIn(result.returncode, (0, 1), result.stderr)
                if result.returncode == 1:
                    self.assertNotIn('List position', result.stderr)
                    self.assertIn('Minyar stopped:', result.stderr)

    def test_diagnostic_lines_after_multiline_literals(self):
        for source, expected_line in (
            ('let text = "first\nsecond"\nprint(missing)\n', 3),
            ("let character = '\n'\nprint(missing)\n", 3),
            ('let text = "first\\\nsecond"\nprint(missing)\n', 3),
            ('/* first\nsecond */\nprint(missing)\n', 3),
        ):
            with self.subTest(source=source):
                result, _ = self.compile(source)
                self.assertEqual(result.returncode, 1)
                self.assertRegex(result.stderr, rf'(?:line |:){expected_line}, column [0-9]+:.*missing')

    def test_receiver_survives_mutation_in_index_and_slice_arguments(self):
        self.executes('''record Box { words: List<Text> }
function box(word: Text): Box {
let words: List<Text> = []
words.add(word + "!")
return Box { words: words }
}
function replace(boxes: List<Box>): Integer {
boxes[0] = box("new")
return 0
}
function end(boxes: List<Box>): Integer {
boxes[0] = box("last")
return 3
}
let boxes: List<Box> = []
boxes.add(box("old"))
print(boxes[0].words[replace(boxes)])
print(boxes[0].words[0].slice(replace(boxes), end(boxes)))
print(boxes[0].words[0])
''', 'old!\nnew\nlast!\n')

    def test_list_grows_while_evaluating_its_own_add_argument(self):
        self.executes('''function grow(words: List<Text>): Text {
let first = words[0]
let i = 0
while i < 5000 {
words.add(Text(i) + "!")
i = i + 1
}
words[0] = "replaced" + "!"
return first
}
let words: List<Text> = []
words.add("original" + "!")
words.add(grow(words))
print(words[0])
print(words[words.length - 1])
print(words.length)
''', 'replaced!\noriginal!\n5002\n')

    def test_index_and_rhs_evaluation_order(self):
        self.executes('''function index(values: List<Text>, events: List<Integer>): Integer {
events.add(1)
values.add("extra")
return 0
}
function value(values: List<Text>, events: List<Integer>): Text {
events.add(2)
let before = values[0]
values[0] = "temporary" + "!"
return before + "!"
}
let values: List<Text> = []
values.add("original" + "!")
let events: List<Integer> = []
values[index(values, events)] = value(values, events)
print(events[0])
print(events[1])
print(values[0])
''', '1\n2\noriginal!!\n')

    def test_short_circuit_effects_and_temporary_lifetimes(self):
        self.executes('''function mark(events: List<Integer>, id: Integer, result: Boolean): Boolean {
let temporary = Text(id) + "!"
events.add(id)
return result && temporary.length > 0
}
let events: List<Integer> = []
print(false && mark(events, 1, true))
print(true || mark(events, 2, false))
print(mark(events, 3, false) || mark(events, 4, true) && mark(events, 5, false))
print((mark(events, 6, true) || mark(events, 7, true)) && mark(events, 8, true))
let i = 0
while i < events.length {
print(events[i])
i = i + 1
}
''', 'false\ntrue\nfalse\ntrue\n3\n4\n5\n6\n8\n')

    def test_shadowing_and_early_returns_through_nested_scopes(self):
        self.executes('''record Pair { left: Text; right: Text }
function make(n: Integer): Pair {
let text = "outer" + "!"
let index = 0
while index < 4 {
if index == n {
let text = Text(index) + "!"
if n % 2 == 0 {
return Pair { right: text; left: "even" + "!" }
} else {
let text = "odd" + text
return Pair { left: text; right: "right" + "!" }
}
}
let text = index
index = text + 1
}
return Pair { left: text; right: text }
}
let i = 0
while i < 5 {
let pair = make(i)
print(pair.left)
print(pair.right)
i = i + 1
}
''', 'even!\n0!\nodd1!\nright!\neven!\n2!\nodd3!\nright!\nouter!\nouter!\n')

    def test_nested_construction_returns_and_shared_diamond(self):
        self.executes('''record Leaf { text: Text }
record Pair { left: Leaf; right: Leaf }
record Root { first: Pair; second: Pair }
function leaf(): Leaf { return Leaf { text: "leaf" + "!" } }
function pair(value: Leaf): Pair { return Pair { left: value; right: value } }
function root(): Root {
let shared = leaf()
return Root { second: pair(shared); first: pair(shared) }
}
let roots: List<Root> = []
let i = 0
while i < 1000 {
roots.add(root())
i = i + 1
}
let saved = roots[0].first.left
roots[0] = root()
print(saved.text)
print(roots[999].second.right.text)
''', 'leaf!\nleaf!\n')

    def test_owned_expressions_cross_every_transfer_destination(self):
        self.executes('''record Box { text: Text }
function identity(text: Text): Text { return text }
function make(): Text { return identity("a" + "b") + "c" }
function box(): Box { return Box { text: (make()) } }
let text = (make())
text = Text(text)
let boxes: List<Box> = []
boxes.add((box()))
boxes.add(Box { text: make() + identity(text) })
boxes[0] = box()
let words: List<Text> = []
words.add(boxes[1].text.slice(0, 3) + Text('🙂'))
print(text)
print(boxes[0].text)
print(boxes[1].text)
print(words[0])
''', 'abc\nabc\nabcabc\nabc🙂\n')

    def test_unicode_metamorphic_properties(self):
        alphabet = ['a', '\0', 'é', '\u0301', '界', '🙂', '\U0010ffff', '"', '\\']
        for seed in range(8):
            rng = random.Random(seed)
            pieces = [''.join(rng.choice(alphabet) for _ in range(rng.randrange(1, 9))) for _ in range(5)]
            joined = ''.join(pieces)
            lines = ['let parts: List<Text> = []']
            lines += ['parts.add(' + literal(piece) + ' + "")' for piece in pieces]
            lines += ['let text = joinText(parts)', 'let copied = ' + ' + '.join(literal(piece) for piece in pieces),
                      'print(text == copied)', 'print(text.length)', 'print(text.byteLength)']
            expected = ['true', str(len(joined)), str(len(joined.encode('utf-8')))]
            for _ in range(8):
                start = rng.randrange(len(joined) + 1)
                end = rng.randrange(start, len(joined) + 1)
                lines.append(f'print(text.slice({start}, {end}) == {literal(joined[start:end])})')
                expected.append('true')
            for index, char in enumerate(joined):
                lines.append(f'print(Text(text[{index}]) == {literal(char)})')
                expected.append('true')
            with self.subTest(seed=seed):
                self.executes('\n'.join(lines) + '\n', '\n'.join(expected) + '\n')

    def test_arithmetic_against_integer_oracle(self):
        rng = random.Random(419)
        source, expected = [], []
        for _ in range(180):
            left, right = rng.randint(-1000000, 1000000), rng.choice([i for i in range(-19, 20) if i])
            quotient = (abs(left) // abs(right)) * (-1 if (left < 0) != (right < 0) else 1)
            remainder = left - quotient * right
            source += [f'print(({left}) / ({right}))', f'print(({left}) % ({right}))',
                       f'print((({left}) / ({right})) * ({right}) + ({left}) % ({right}) == ({left}))']
            expected += [str(quotient), str(remainder), 'true']
        self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')

    def test_large_acyclic_type_graph_and_hidden_back_edge(self):
        # Forward references with diamonds, not just a linked-list-shaped graph.
        records = []
        for index in range(400):
            fields = [f'next: List<R{index + 1}>'] if index < 399 else ['number: Integer']
            if index < 398:
                fields.append(f'skip: List<List<R{index + 2}>>')
            records.append(f'record R{index} {{ ' + '; '.join(fields) + ' }')
        result, _ = self.compile('\n'.join(records) + '\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        records[-1] = 'record R399 { back: List<List<R7>> }'
        mutation = 'function attach(values: List<R7>, value: R7) { values.add(value) }\n'
        self.rejects('\n'.join(records) + '\n' + mutation, 'this List mutation could create a reference cycle')

    def test_unreachable_code_still_has_type_checks(self):
        for body in ('return 1\nprint("text" - 1)', 'if true { return 1 } else { print("text" - 1) }\nreturn 2'):
            self.rejects('function f(): Integer {\n' + body + '\n}\n', 'different types')

    def test_transfer_operations_replace_temporary_owners(self):
        result, llvm = self.compile('''record Point { x: Integer }
function make(): Point { return Point { x: 3 } }
let points: List<Point> = []
points.add(make())
points.add(Point { x: 4 })
let text = "a" + "b"
print(text)
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        ir = llvm.read_text()
        self.assertIn('call void @minyar_list_add_take', ir)
        self.assertIn('call void @minyar_rc_local_take', ir)
        self.assertNotIn('call void @minyar_rc_keep', ir)
        self.assertNotIn('call void @minyar_rc_step', ir)


if __name__ == '__main__':
    unittest.main(verbosity=2)
