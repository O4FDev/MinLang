import importlib.util
import unittest
from regressions import CompilerTestCase, ROOT

spec = importlib.util.spec_from_file_location('list_basics', ROOT / 'tests/list-basics.py')
list_basics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(list_basics)


class MapBasics(CompilerTestCase):
    link_program = list_basics.ListBasics.link_program

    def test_inferred_typed_contextual_nested_and_duplicate_literals(self):
        self.executes('''print('{'); print("{")
let braces = {"{": '}', "}": '{'}
print(braces["}"])
let inferred = {"é": 1, "🙂": 2, "é": 3,}
print(inferred.length); print(inferred["é"])
let typed = Map<Integer, Text> {1: Text(11), 2: Text(22)}
let contextual: Map<Integer, List<Integer>> = Map {1: [3, 4], 2: []}
print(typed[1]); print(contextual[1].pop()); print(contextual[2].length)
let empty: Map<Text, Integer> = {}
print(empty.length)
function consume(value: Map<Text, Integer>): Integer { return value.length }
print(consume({})); print(consume(Map {}))
let nested = {1: {"key": Text(42)}}
print(nested[1]["key"])
''', '{\n{\n{\n2\n3\n11\n4\n0\n0\n0\n0\n42\n')

    def test_literal_evaluation_order_and_key_lifetime(self):
        self.executes('''record Holder { key: Text; calls: Integer }
function key(holder: Holder): Text { holder.calls += 1; print(holder.calls); return holder.key }
function value(holder: Holder): Text { holder.calls += 1; print(holder.calls); holder.key = Text(holder.calls); return Text(holder.calls) }
let holder = Holder { key: Text(100); calls: 0 }
let map = {key(holder): value(holder), key(holder): value(holder)}
print(map["100"]); print(map["2"]); print(holder.calls)
let duplicates = {true: 1, true: 2}
print(duplicates.length); print(duplicates[true])
''', '1\n2\n3\n4\n2\n4\n4\n1\n2\n')

    def test_equality_matches_dictionary_model_and_float_rules(self):
        self.executes('''let left = {1: Text(11), 2: Text(22)}
let right = {2: Text(22), 1: Text(11)}
print(left == right); print(left != right)
right[2] = Text(33)
print(left == right); print(left != right)
right.remove(2); right[3] = Text(22)
print(left == right)
let empty = Map<Integer, Text>()
print(empty == Map<Integer, Text> {})
print({true: '🙂'} == {true: '🙂'})
print({1.0: -0.0} == {1.0: 0.0})
let nan = sqrt(-1.0)
print({1: nan} == {1: nan})
print({1: {"a": 2}} == {1: {"a": 2}})
print({1: {"a": 2}} != {1: {"a": 3}})
''', 'true\nfalse\nfalse\ntrue\nfalse\ntrue\ntrue\ntrue\nfalse\ntrue\ntrue\n')

    def test_equality_captures_receiver_before_rhs_rebind(self):
        self.executes('''record Holder { value: Map<Text, Integer> }
function replace(holder: Holder): Map<Text, Integer> { holder.value = {}; return {"key": 7} }
let holder = Holder { value: {"key": 7} }
print(holder.value == replace(holder))
print(holder.value.length)
''', 'true\n0\n')

    def test_for_in_snapshot_survives_clear_growth_and_break(self):
        self.executes('''let map = {Text(1): 1, Text(2): 2, Text(3): 3}
let visited = Map<Text, Boolean>()
for key in map {
    map.clear()
    for n in 0..64 { map[Text(n + 100)] = n }
    visited[key] = true
}
print(visited.length)
print(visited.has("1") && visited.has("2") && visited.has("3"))
let total = 0
for key in {1: 9, 2: 8, 3: 7} { if key == 2 { continue }; total += key }
print(total)
for key in {Text(4): Text(5)} { print(key); break }
for key in Map<Integer, Integer> {} { fail("empty map iterated") }
''', '3\ntrue\n4\n4\n')

    def test_owned_values_cycles_and_imported_literals(self):
        (self.directory / 'table.min').write_text('''public record Node { values: List<Node>; text: Text }
public function make(): Map<Text, Node> {
    let node = Node { values: []; text: Text(9) }
    node.values.add(node)
    return {"node": node}
}
''')
        self.executes('''use "./table.min" as table
let map = table.make()
for key in map { print(map[key].text) }
let saved = map["node"]
map.clear()
print(saved.text)
''', '9\n9\n')

    def test_literal_and_equality_diagnostics(self):
        self.rejects('let map = {}\n', 'an empty Map literal needs a type')
        self.rejects('let map = {1: 2, "x": 3}\n', 'Map literal key has the wrong type')
        self.rejects('let map = {1: 2, 3: true}\n', 'Map literal value has the wrong type')
        self.rejects('let map = {[1]: 2}\n', 'Map keys must be Integer, Text, Character, Boolean, or Float')
        self.rejects('record Node { children: Map<Integer, Node> }\nlet node = Node { children: Map<Integer, Node>() }\nnode.children = {1: node}\n', 'Map mutation could create a reference cycle')
        self.rejects('print({1: [2]} == {1: [2]})\n', 'Map equality needs comparable values')
        self.rejects('print({1: 2} == {1: true})\n', "the two sides of '==' have different types")
        self.rejects('print({1: 2} < {1: 3})\n', 'ordered comparison needs Integer, Float, or Character operands')


if __name__ == '__main__':
    unittest.main()
