#!/usr/bin/env python3
"""Check reference lifetimes, shared aliases, and cycle rejection."""
import os
import random
import unittest
from regressions import CompilerTestCase, ROOT


class Ownership(CompilerTestCase):
    def test_graph_example(self):
        self.executes((ROOT / 'examples/graph.min').read_text(), 'second\nfirst\n')

    def test_recursive_mutation_checker_against_independent_model(self):
        for seed in range(max(40, int(os.environ.get('MINYAR_OWNERSHIP_GRAPHS', '40')))):
            rng = random.Random(seed)
            edges = [[j for j in range(8) if rng.random() < .13] for _ in range(8)]
            # Independent Floyd-Warshall closure, unlike compiler graph walk.
            # Recursive declarations are safe; adding to List<Ri> is unsafe
            # exactly when Ri can reach that List type via a nonempty path.
            reaches = [[j in edges[i] for j in range(8)] for i in range(8)]
            for middle in range(8):
                for start in range(8):
                    for end in range(8):
                        reaches[start][end] |= reaches[start][middle] and reaches[middle][end]
            source = '\n'.join(f'record R{i} {{ ' + '; '.join(f'f{j}: List<R{j}>' for j in row) + ' }' for i, row in enumerate(edges)) + '\n'
            result, _ = self.compile(source)
            self.assertEqual(result.returncode, 0, result.stderr)
            for node in range(8):
                with self.subTest(seed=seed, mutation_type=node):
                    operation = f'function append(values: List<R{node}>, value: R{node}) {{ values.add(value) }}\n'
                    result, _ = self.compile(source + operation)
                    if reaches[node][node]:
                        self.assertEqual(result.returncode, 1, result.stderr)
                        self.assertIn('this List mutation could create a reference cycle', result.stderr)
                    else:
                        self.assertEqual(result.returncode, 0, result.stderr)

    def test_generated_alias_programs(self):
        for seed in range(max(8, int(os.environ.get('MINYAR_OWNERSHIP_SEEDS', '8')))):
            rng = random.Random(seed)
            source = ['record Box { text: Text; number: Integer }',
                      'function box(n: Integer): Box { return Box { text: Text(n) + "!"; number: n } }',
                      'function fetch(items: List<Box>, n: Integer): Box { return items[n] }',
                      'let items: List<Box> = []', 'let alias = items']
            model, snapshots, expected = list(range(6)), [], []
            source += [f'items.add(box({i}))' for i in model]
            for step in range(40):
                target, other = rng.randrange(6), rng.randrange(6)
                operation = rng.randrange(3)
                if operation == 0:
                    source.append(f'alias[{target}] = items[{other}]')
                    model[target] = model[other]
                elif operation == 1:
                    source.append(f'items[{target}] = box({step + 10})')
                    model[target] = step + 10
                else:
                    source.append(f'let saved{step} = fetch(alias, {target})')
                    snapshots.append((step, model[target]))
            for step, value in snapshots:
                source.append(f'print(saved{step}.text)')
                expected.append(f'{value}!')
            for index, value in enumerate(model):
                source.append(f'print(items[{index}].number)')
                expected.append(str(value))
            with self.subTest(seed=seed):
                self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')

    def test_recursive_shapes_without_mutations_are_supported(self):
        for declarations in (
            'record Node { children: List<Node> }',
            'record Node { next: Node }',
            'record A { b: List<B> }\nrecord B { a: A }',
            'record A { b: List<List<B>> }\nrecord B { a: List<A> }',
        ):
            with self.subTest(declarations=declarations):
                result, _ = self.compile(declarations + '\n')
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_unfinished_field_read_has_a_language_diagnostic(self):
        self.rejects('record Point { x: Integer }\nlet points: List<Point> = []\nprint(points[0].', "expected a field or method name after '.'")

    def test_native_output_uses_ownership_not_tracing(self):
        result, llvm = self.compile('let words: List<Text> = []\nwords.add("a" + "b")\nprint(words[0])\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('minyar_gc_', llvm.read_text())
        self.assertIn('minyar_rc_', llvm.read_text())

    def test_alias_and_self_assignment(self):
        self.executes('''let words: List<Text> = []
words.add("old" + "!")
let alias = words
let saved = words[0]
words[0] = words[0]
words = words
alias[0] = "new" + "!"
print(saved)
print(words[0])
''', 'old!\nnew!\n')

    def test_scalar_field_read_needs_no_extra_owner(self):
        result, llvm = self.compile('record Point { x: Integer }\nlet points: List<Point> = []\npoints.add(Point { x: 42 })\nprint(points[0].x)\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('call void @minyar_rc_retain', llvm.read_text())
        self.assertNotIn('call void @minyar_rc_borrow', llvm.read_text())
        self.assertIn('call ptr @minyar_record_new_scalar', llvm.read_text())

    def test_borrow_survives_mutating_argument(self):
        self.executes('''record Box { text: Text }
function replace(boxes: List<Box>): Text {
boxes[0] = Box { text: "new" + "!" }
return "tail" + "!"
}
function combine(first: Text, second: Text): Text { return first + second }
let boxes: List<Box> = []
boxes.add(Box { text: "old" + "!" })
print(combine(boxes[0].text, replace(boxes)))
print(boxes[0].text)
''', 'old!tail!\nnew!\n')

    def test_returns_reassignments_and_identity_conversion(self):
        self.executes('''function identity(text: Text): Text { return Text(text) }
function choose(left: Text, right: Text, flag: Boolean): Text {
if flag { return left } else { return right }
}
let text = "start" + "!"
let index = 0
while index < 1000 {
text = identity(choose(text, "other", true))
index = index + 1
}
print(text)
''', 'start!\n')

    def test_nested_shared_lists_and_records(self):
        self.executes('''record Leaf { text: Text; number: Integer }
record Pair { left: Leaf; right: Leaf }
function make(): List<List<Pair>> {
let leaf = Leaf { text: "shared" + "!"; number: 42 }
let pair = Pair { left: leaf; right: leaf }
let inner: List<Pair> = []
inner.add(pair)
let outer: List<List<Pair>> = []
outer.add(inner)
outer.add(inner)
return outer
}
let values = make()
print(values[1][0].left.text)
print(values[0][0].right.number)
''', 'shared!\n42\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
