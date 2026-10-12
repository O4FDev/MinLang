"""Native dictionary gap repros, typed nesting, ownership, and diagnostics."""
import unittest
import random
from regressions import CompilerTestCase

class Maps(CompilerTestCase):
    def test_python_dictionary_model(self):
        model = {}
        rng = random.Random(20261012)
        source = ['let m = Map<Integer, Integer>()']
        expected = []
        for step in range(240):
            key = rng.randrange(-32, 33)
            operation = rng.randrange(5)
            if operation < 2:
                model[key] = step
                source.append(f'm[{key}] = {step}')
            elif operation == 2:
                source.append(f'print(m.remove({key}))')
                expected.append(str(key in model).lower())
                model.pop(key, None)
            elif operation == 3:
                source.append(f'print(m.has({key}))')
                expected.append(str(key in model).lower())
            elif key in model:
                source.append(f'print(m[{key}])')
                expected.append(str(model[key]))
        source.append('print(m.length)')
        expected.append(str(len(model)))
        for key, value in sorted(model.items()):
            source.append(f'print(m[{key}])')
            expected.append(str(value))
        self.executes('\n'.join(source), '\n'.join(expected) + '\n')

    def test_key_and_value_survive_right_side_clear(self):
        self.executes('''function reset(m: Map<Text, Text>): Text { m.clear(); return "after" + "!" }
let m = Map<Text, Text>()
m["key"] = "borrowed" + "!"
m[m["key"]] = reset(m)
print(m["borrowed!"])
m["borrowed!"] = m["borrowed!"]
let saved = m["borrowed!"]
print(m.remove("borrowed!"))
print(saved)
''', 'after!\ntrue\nafter!\n')

    def test_managed_growth_and_all_removal_positions(self):
        self.executes('''let m = Map<Integer, List<Text>>()
let value = ["owned" + "!"]
let i = 0
while i < 300 { m[i] = value; i = i + 1 }
let saved = m[299]
i = 299
while i >= 0 { m.remove(i); i = i - 1 }
print(m.length)
print(saved[0])
m[0] = saved
m.clear()
m.clear()
print(value[0])
''', '0\nowned!\nowned!\n')

    def test_compound_assignment_and_contextual_arguments(self):
        self.executes('''function fresh(m: Map<Integer, Integer>): Map<Integer, Integer> { return m }
function make(): Map<Integer, Integer> { return Map() }
let m = fresh(Map())
m[1] = 40
m[1] += 2
print(m[1])
let others: List<Map<Text, List<Integer>>> = [Map()]
others[0]["a"] = [1, 2]
others[0]["a"][1] += 3
print(others[0]["a"][1])
print(make().length)
''', '42\n5\n0\n')

    def test_map_types_in_imported_records_and_constructors(self):
        (self.directory / 'map-values.min').write_text('''public record Value { text: Text }
public function make(): Map<Text, List<Value>> {
let result: Map<Text, List<Value>> = Map()
result["a"] = [Value { text: "module" + "!" }]
return result
}
''')
        self.executes('''use "./map-values.min" as values
let m = values.make()
print(m["a"][0].text)
let explicit = Map<Text, List<values.Value>>()
explicit["b"] = [values.Value { text: "explicit" + "!" }]
print(explicit["b"][0].text)
''', 'module!\nexplicit!\n')
    def test_image_path_dedup_contextual_constructor(self):
        self.executes('''let paths = ["usr/bin/a", "etc/passwd", "usr/bin/a"]
let seen: Map<Text, Integer> = Map()
let unique: List<Text> = []
for p in paths { if !seen.has(p) { seen[p] = unique.length; unique.add(p) } }
print(unique.length)
print(seen["etc/passwd"])
print(seen.remove("usr/bin/a"))
print(seen.remove("usr/bin/a"))
seen.clear()
print(seen.length)
''', '2\n1\ntrue\nfalse\n0\n')

    def test_explicit_constructor_growth_alias_and_replacement(self):
        self.executes('''let seen = Map<Integer, Integer>()
let alias = seen
let i = 0
while i < 1000 { seen[i] = i * 7; i = i + 1 }
i = 0
let sum = 0
while i < 1000 { sum = sum + alias[i]; i = i + 1 }
alias[0] = 42
print(seen.length)
print(sum)
print(seen[0])
''', '1000\n3496500\n42\n')

    def test_managed_values_and_nested_generics(self):
        self.executes('''record Box { text: Text }
function make(): Map<Text, List<Map<Integer, Box>>> {
let result: Map<Text, List<Map<Integer, Box>>> = Map()
let inner = Map<Integer, Box>()
inner[9] = Box { text: "old" + "!" }
result["key"] = [inner]
return result
}
let outer = make()
let inner = outer["key"][0]
let saved = inner[9]
inner[9] = Box { text: "new" + "!" }
outer.clear()
print(saved.text)
print(inner[9].text)
inner.clear()
print(saved.text)
''', 'old!\nnew!\nold!\n')

    def test_scalar_key_and_value_slots(self):
        self.executes('''let flags = Map<Boolean, Float>()
flags[true] = 1.5
print(flags[true])
let letters = Map<Character, Boolean>()
letters['λ'] = true
print(letters['λ'])
let floats = Map<Float, Integer>()
floats[-0.0] = 7
print(floats[0.0])
''', '1.5\ntrue\n7\n')

    def test_missing_key_is_fatal(self):
        self.executes('let m = Map<Integer, Integer>()\nprint(m[9])\n', '', status=1,
                      stderr='Minyar stopped: Map key is absent.\n')

    def test_nan_key_is_fatal_and_float_zeros_are_equal(self):
        self.executes('''let m = Map<Float, Integer>()
m[0.0] = 1
m[-0.0] = 2
print(m.length)
print(m[0.0])
print(m.remove(-0.0))
''', '1\n2\ntrue\n')
        self.executes('let m = Map<Float, Integer>()\nm[sqrt(-1.0)] = 1\n', '', status=1,
                      stderr='Minyar stopped: NaN cannot be used as a Map key.\n')

    def test_type_and_arity_diagnostics(self):
        for source, message in (
            ('let m = Map()', 'Map() needs a contextual Map<K, V> type'),
            ('let m = Map<Integer>()', "expected ','"),
            ('let m = Map<Bytes, Integer>()', 'Map keys must be Integer, Text, Character, Boolean, or Float'),
            ('let m = Map<Integer, Nothing>()', 'Nothing cannot be used as a value type'),
            ('let m = Map<Integer, Integer>()\nm["x"] = 1', 'Map key has the wrong type'),
            ('let m = Map<Integer, Integer>()\nm[1] = "x"', 'Map value has the wrong type'),
            ('let m = Map<Integer, Integer>()\nm.has()', 'expected an expression'),
            ('let m = Map<Integer, Integer>()\nm.clear(1)', "expected ')'"),
        ):
            with self.subTest(source=source): self.rejects(source, message)

    def test_map_cycles_are_rejected_in_every_frontend(self):
        self.rejects('''record Node { children: Map<Integer, Node> }
function insert(m: Map<Integer, Node>, n: Node) { m[1] = n }
''', 'Map mutation could create a reference cycle')

    def test_generic_encoding_limit(self):
        value = 'Integer'
        for _ in range(24): value = f'Map<Integer, {value}>'
        self.rejects(f'function f(m: {value}) {{ }}\n', 'generic type nesting exceeds the supported limit')

if __name__ == '__main__': unittest.main(verbosity=2)
