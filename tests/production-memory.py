#!/usr/bin/env python3
"""Check recursive data and reference lifetimes, including under ASan.

Cases combine module identity, constructor argument effects, and escaping borrows."""
import random
import unittest
from regressions import CompilerTestCase


CYCLE_DIAGNOSTIC = 'this List mutation could create a reference cycle'


class ProductionMemory(CompilerTestCase):
    def test_empty_literal_context_flows_through_nested_calls_and_add(self):
        self.executes('''record Node { children: List<Node> }
function nodes(values: List<Node>): List<Node> { return values }
function layers(values: List<List<Node>>): List<List<Node>> { return values }
function first(values: List<List<Node>>, fallback: List<Node>): List<Node> {
if values.length > 0 { return values[0] }
return fallback
}
let a = nodes([])
let b = layers([nodes([]), []])
print(a.length)
print(b.length)
print(first(layers([[]]), nodes([])).length)
let ordinary: List<List<Integer>> = []
ordinary.add([])
ordinary.add([1, 2])
print(ordinary[0].length)
print(ordinary[1][1])
print(joinText([]))
''', '0\n2\n0\n0\n2\n\n')

    def test_nested_literal_type_context_cannot_accept_void_or_wrong_scalars(self):
        self.rejects('''function count(values: List<List<Integer>>): Integer { return values.length }
print(count([[print(1)]]))
''', 'Nothing cannot be stored in a List')
        self.rejects('''function count(values: List<List<Integer>>): Integer { return values.length }
print(count([[true]]))
''', 'all values in a List literal must have the same type')

    def test_generated_shared_recursive_graphs_and_escaping_aliases(self):
        for seed in range(8):
            rng = random.Random(seed + 19061)
            source = ['record Node { value: Integer; children: List<Node> }',
                      'record Wrapper { node: Node }',
                      'function score(node: Node): Integer {',
                      'let result = node.value', 'let i = 0',
                      'while i < node.children.length {',
                      'result = result + score(node.children[i])', 'i = i + 1', '}',
                      'return result', '}',
                      'function make(): List<Wrapper> {']
            scores = []
            for node in range(24):
                children = [rng.randrange(node) for _ in range(rng.randrange(4))] if node else []
                value = rng.randrange(-50, 51)
                scores.append(value + sum(scores[child] for child in children))
                source += [f'let children{node}: List<Node> = [' + ', '.join(f'n{child}' for child in children) + ']',
                           f'let n{node} = Node {{ value: {value}; children: children{node} }}']
            selected = [rng.randrange(24) for _ in range(6)]
            source += ['return [' + ', '.join(f'Wrapper {{ node: n{node} }}' for node in selected) + ']', '}',
                       'let values = make()', 'let alias = values']
            expected = []
            saved = []
            for step in range(24):
                slot, other = rng.randrange(6), rng.randrange(6)
                if step % 3:
                    source.append(f'alias[{slot}] = values[{other}]')
                    selected[slot] = selected[other]
                else:
                    source.append(f'let saved{step} = values[{slot}].node')
                    saved.append((step, scores[selected[slot]]))
            source.append('values = []')
            for step, score in saved:
                source.append(f'print(score(saved{step}))')
                expected.append(str(score))
            # Dropping the mutable alias releases all unescaped constructor
            # graphs before the final reads of individually saved descendants.
            source.append('alias = []')
            for step, score in saved:
                source.append(f'print(score(saved{step}))')
                expected.append(str(score))
            with self.subTest(seed=seed):
                self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')

    def test_constructor_borrow_survives_later_argument_replacement(self):
        self.executes('''record Node { name: Text; children: List<Node> }
record Wrapper { node: Node }
record Pair { first: Node; second: Node }
function leaf(name: Text): Node { return Node { name: name; children: [] } }
function replace(values: List<Wrapper>): Node {
values[0] = Wrapper { node: leaf("new" + "!") }
return leaf("second" + "!")
}
let values: List<Wrapper> = [Wrapper { node: leaf("old" + "!") }]
let pair = Pair { first: values[0].node; second: replace(values) }
print(pair.first.name)
print(pair.second.name)
print(values[0].node.name)
let tree: List<Node> = [values[0].node, replace(values)]
print(tree[0].name)
print(tree[1].name)
''', 'old!\nsecond!\nnew!\nnew!\nsecond!\n')

    def test_recursive_borrow_escapes_after_ancestor_replacement(self):
        self.executes('''record Node { text: Text; children: List<Node> }
function leaf(text: Text): Node { return Node { text: text; children: [] } }
function pick(node: Node, depth: Integer): Node {
if depth == 0 { return node }
return pick(node.children[0], depth - 1)
}
function take(node: Node): Node {
let result = pick(node, 2)
node = leaf("replacement" + "!")
return result
}
function make(): Node {
let shared = leaf("survivor" + "!")
let middle = Node { text: "middle"; children: [shared, shared] }
return Node { text: "root"; children: [middle, middle] }
}
let root = make()
let survivor = take(root)
root = leaf("new root" + "!")
print(survivor.text)
print(root.text)
''', 'survivor!\nnew root!\n')

    def test_module_aliases_cannot_hide_cycle_write(self):
        (self.directory / 'node.min').write_text('''public record Node { children: List<Node> }
public function empty(): Node { return Node { children: [] } }
''')
        (self.directory / 'nested').mkdir()
        for write in ('children.add(node)', 'children[0] = node'):
            with self.subTest(write=write):
                self.rejects('''use "./node.min" as a
use "./nested/../node.min" as b
let children: List<a.Node> = [a.empty()]
let node = b.Node { children: children }
''' + write + '\n', CYCLE_DIAGNOSTIC)

    def test_module_identity_keeps_unrelated_outer_list_mutable(self):
        (self.directory / 'tree.min').write_text('''public record Node { children: List<Node>; text: Text }
public function leaf(text: Text): Node { return Node { children: []; text: text } }
''')
        (self.directory / 'wrapper.min').write_text('''use "./tree.min" as t
public record Node { tree: t.Node }
''')
        self.executes('''use "./tree.min" as tree
use "./wrapper.min" as wrapper
let values: List<wrapper.Node> = []
values.add(wrapper.Node { tree: tree.leaf("one") })
let saved = values[0].tree
values[0] = wrapper.Node { tree: tree.leaf("two") }
print(saved.text)
print(values[0].tree.text)
''', 'one\ntwo\n')

    def test_nested_list_write_inside_helper_cannot_hide_cycle(self):
        declarations = '''record Node { layers: List<List<Node>> }
function attach(target: List<Node>, node: Node) { target.add(node) }
'''
        self.rejects(declarations + '''let inner: List<Node> = []
let layers: List<List<Node>> = [inner]
let node = Node { layers: layers }
attach(inner, node)
''', CYCLE_DIAGNOSTIC)

    def test_empty_recursive_lists_are_not_mutable_through_return_alias(self):
        self.rejects('''record Node { children: List<Node> }
function identity(values: List<Node>): List<Node> { return values }
let values: List<Node> = []
let node = Node { children: values }
identity(values).add(node)
''', CYCLE_DIAGNOSTIC)


if __name__ == '__main__':
    unittest.main(verbosity=2)
