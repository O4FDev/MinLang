#!/usr/bin/env python3
"""Recursive construction with type-proven acyclic mutable edges.

Run natively and with MINYAR_TEST_RUNTIME pointing at the exact-accounting
sanitizer runtime. Every executable case runs at both O0 and O2.
"""
import random
import unittest
from regressions import CompilerTestCase

DIAGNOSTIC = 'this List mutation could create a reference cycle'


class RecursiveData(CompilerTestCase):
    def test_tree_construction_recursion_and_shared_subtrees(self):
        self.executes('''record Node { value: Integer; children: List<Node> }
function tree(depth: Integer): Node {
    if depth == 0 { return Node { value: 1; children: [] } }
    let child = tree(depth - 1)
    return Node { value: 1; children: [child, child] }
}
function size(node: Node): Integer {
    let total = node.value
    let i = 0
    while i < node.children.length {
        total = total + size(node.children[i])
        i = i + 1
    }
    return total
}
let root = tree(12)
print(size(root))
print(root.children[0].children.length)
''', '8191\n2\n')

    def test_persistent_chain_loop_and_returned_borrow(self):
        self.executes('''record Link { value: Integer; next: List<Link> }
function first(links: List<Link>): Link { return links[0] }
let chain = Link { value: 0; next: [] }
let i = 1
while i < 4000 {
    chain = Link { value: i; next: [chain] }
    i = i + 1
}
let saved = first(chain.next)
let total = 0
while chain.next.length > 0 {
    total = total + chain.value
    chain = chain.next[0]
}
print(total)
print(saved.value)
''', '7998000\n3998\n')

    def test_mutually_recursive_records_with_terminating_list(self):
        self.executes('''record Branch { leaves: List<Leaf> }
record Leaf { parentShape: Branch; value: Integer }
function grow(n: Integer): Branch {
    if n == 0 { return Branch { leaves: [] } }
    return Branch { leaves: [Leaf { parentShape: grow(n - 1); value: n }] }
}
let branch = grow(20)
print(branch.leaves[0].parentShape.leaves[0].value)
''', '19\n')

    def test_mutable_payloads_and_external_worklists_keep_alias_semantics(self):
        self.executes('''record Node { children: List<Node>; payload: List<Integer> }
record Job { node: Node }
let payload: List<Integer> = [1]
let leaf = Node { children: []; payload: payload }
let root = Node { children: [leaf]; payload: payload }
let jobs: List<Job> = []
let alias = jobs
alias.add(Job { node: root })
jobs[0] = Job { node: leaf }
payload[0] = 42
payload.add(7)
print(alias[0].node.payload[0])
print(root.payload.length)
''', '42\n2\n')

    def test_outer_list_is_mutable_when_its_exact_type_is_not_on_a_cycle(self):
        self.executes('''record Node { children: List<Node> }
let leaf = Node { children: [] }
let childLists: List<List<Node>> = []
let alias = childLists
alias.add([leaf])
childLists[0] = [leaf, leaf]
print(alias[0].length)
''', '2\n')

    def test_recursive_children_can_be_built_with_fresh_appended_lists(self):
        self.executes('''record Node { value: Integer; children: List<Node> }
let children: List<Node> = []
let i = 1
while i <= 20 {
    children = children.appended(Node { value: i; children: [] })
    i = i + 1
}
let root = Node { value: 0; children: children }
print(root.children.length)
print(root.children[0].value)
print(root.children[19].value)
''', '20\n1\n20\n')

    def test_direct_self_cycle_add_and_overwrite_rejected(self):
        declarations = 'record Node { children: List<Node> }\n'
        for body in (
            'let children: List<Node> = []\nlet node = Node { children: children }\nchildren.add(node)',
            'let leaf = Node { children: [] }\nlet children: List<Node> = [leaf]\nlet node = Node { children: children }\nchildren[0] = node',
            'function attach(children: List<Node>, node: Node) { children.add(node) }',
            'function replace(children: List<Node>, node: Node) { children[0] = node }',
        ):
            with self.subTest(body=body):
                self.rejects(declarations + body + '\n', DIAGNOSTIC)

    def test_alias_return_and_record_projection_cannot_bypass_rejection(self):
        declarations = '''record Node { children: List<Node> }
function children(node: Node): List<Node> { return node.children }
'''
        for expression in ('alias.add(node)', 'children(node).add(node)', 'node.children.add(node)'):
            self.rejects(declarations + '''let items: List<Node> = []
let node = Node { children: items }
let alias = items
''' + expression + '\n', DIAGNOSTIC)

    def test_nested_list_edges_both_rejected(self):
        declarations = 'record Node { groups: List<List<Node>> }\n'
        for body in (
            'function inner(items: List<Node>, node: Node) { items.add(node) }',
            'function outer(groups: List<List<Node>>, items: List<Node>) { groups.add(items) }',
            'function overwrite(groups: List<List<Node>>, items: List<Node>) { groups[0] = items }',
        ):
            self.rejects(declarations + body + '\n', DIAGNOSTIC)

    def test_mutual_cycle_through_different_mutable_type_is_rejected(self):
        self.rejects('''record A { links: List<B> }
record B { back: A }
function attach(links: List<B>, owner: A) {
    links.add(B { back: owner })
}
''', DIAGNOSTIC)

    def test_recursive_declarations_without_values_are_legal(self):
        result, _ = self.compile('record Loop { next: Loop }\nrecord Tree { children: List<Tree> }\n')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_list_literals_infer_types_and_evaluate_left_to_right(self):
        self.executes('''function bump(state: List<Integer>): Integer {
    state[0] = state[0] + 1
    return state[0]
}
function mixed(numbers: List<Integer>, words: List<Text>) {
    print(numbers[0])
    print(words[0])
}
let state = [0]
let values = [bump(state), bump(state), bump(state)]
print(values[0])
print(values[1])
print(values[2])
mixed([7], ["seven"])
let flags = [true, false]
let characters = ['a', 'b']
print(flags[1])
print(characters[1])
let nested: List<List<Text>> = [[], ["é" + "🙂"], []]
print(nested[0].length)
print(nested[1][0])
print(nested[2].length)
''', '1\n2\n3\n7\nseven\nfalse\nb\n0\né🙂\n0\n')

    def test_literal_retains_earlier_projection_before_later_mutation(self):
        self.executes('''record Box { text: Text }
function replace(boxes: List<Box>): Box {
    boxes[0] = Box { text: "new" + "!" }
    return boxes[0]
}
let boxes = [Box { text: "old" + "!" }]
let captured = [boxes[0], replace(boxes)]
print(captured[0].text)
print(captured[1].text)
print(boxes[0].text)
''', 'old!\nnew!\nnew!\n')

    def test_list_literals_reject_invalid_types_and_separators(self):
        for source, diagnostic in (
            ('let bad = [1, true]', 'all values in a List literal must have the same type'),
            ('let bad = [[], []]', 'an empty List needs a type'),
            ('let bad = [print(1)]', 'Nothing cannot be stored in a List'),
            ('let bad = [1 2]', "expected ','"),
            ('let bad = [1,', 'expected an expression'),
            ('let bad: List<Integer> = [true]', 'all values in a List literal must have the same type'),
            ('function bad(): List<Integer> { return }', 'a returned value has the wrong type'),
        ):
            with self.subTest(source=source):
                self.rejects(source + '\n', diagnostic)

    def test_contextual_empty_list_returns_and_reassignment(self):
        self.executes('''record Node { children: List<Node> }
function empty(): List<Node> { return [] }
let items: List<Node> = [Node { children: empty() }]
items = []
print(items.length)
let multiline: List<List<Integer>> = [
    [],
    [1, 2,],
]
print(multiline[1][1])
''', '0\n2\n')

    def test_type_edge_mutations_against_independent_reachability_model(self):
        # Independent transitive closure over explicit record AND List types;
        # compiler uses an iterative worklist and strips nested List layers.
        for seed in range(32):
            rng = random.Random(seed)
            count = 5
            edges = [[(j, rng.randint(0, 2)) for j in range(count)
                      if rng.random() < .23] for _ in range(count)]
            def type_name(node, depth):
                result = f'R{node}'
                for _ in range(depth):
                    result = f'List<{result}>'
                return result
            declarations = '\n'.join(
                f'record R{i} {{ ' + '; '.join(f'f{k}: {type_name(j, depth)}'
                for k, (j, depth) in enumerate(row)) + ' }'
                for i, row in enumerate(edges)) + '\n'
            names = [(i, depth) for i in range(count) for depth in range(3)]
            reach = {(a, b) for a in names for b in names if a == b}
            for i, row in enumerate(edges):
                for j, depth in row:
                    reach.add(((i, 0), (j, depth)))
                for depth in (1, 2):
                    reach.add(((i, depth), (i, depth - 1)))
            for middle in names:
                for start in names:
                    for end in names:
                        if (start, middle) in reach and (middle, end) in reach:
                            reach.add((start, end))
            for node, depth in [(seed % count, 1), ((seed + 1) % count, 2)]:
                cyclic = ((node, depth - 1), (node, depth)) in reach
                for mutation in ('items.add(value)', 'items[0] = value'):
                    source = declarations + (f'function mutate(items: {type_name(node, depth)}, '
                        f'value: {type_name(node, depth - 1)}) {{ {mutation} }}\n')
                    with self.subTest(seed=seed, node=node, depth=depth, mutation=mutation):
                        result, _ = self.compile(source)
                        if cyclic:
                            self.assertEqual(result.returncode, 1, result.stderr)
                            self.assertIn(DIAGNOSTIC, result.stderr)
                        else:
                            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
