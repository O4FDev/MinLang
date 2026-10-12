"""Map captures, typed callable signatures, Results and unrelated cycles."""
import os
from pathlib import Path
import unittest
import callbacks
from regressions import CompilerTestCase, ROOT


class MapCallbacks(CompilerTestCase):
    compiler_arguments = ('--library', str(ROOT / 'library'))
    compile = callbacks.Callbacks.compile
    executes = callbacks.Callbacks.executes

    def test_imported_callback_map_argument_preserves_following_record_type(self):
        (self.directory / 'factory.min').write_text('''public record Box { value: Integer }
public function make(): Callback<Map<Integer, Integer>, Box> {
    return function(row: Map<Integer, Integer>): Box { return Box { value: row[1] } }
}
''')
        self.executes('''use "./factory.min" as factory
let row = Map<Integer, Integer>()
row[1] = 42
let call = factory.make()
print(call(row).value)
''', '42\n')

    def test_owned_callback_survives_map_clear(self):
        self.executes('''let m = Map<Integer, Callback<Integer, Integer>>()
let offset = 40
m[1] = function(value: Integer): Integer { return offset + value }
let saved = m[1]
m.clear()
print(saved(2))
''', '42\n')

    def test_capture_and_negative_map_signature_roundtrip(self):
        self.executes('''function make(m: Map<Integer, Text>): Callback<Integer, Map<Integer, Text>> {
return function(key: Integer): Map<Integer, Text> { m[key] = "capture" + "!"; return m }
}
let m = Map<Integer, Text>()
let call = make(m)
let result = call(9)
m.clear()
result[9] = "retained" + "!"
print(call(3)[9])
print(m[3])
''', 'retained!\ncapture!\n')

    def test_map_owns_and_releases_unrelated_traced_graph(self):
        self.executes('''record Node { label: Text; children: List<Node> }
let n = Node { label: "cyclic" + "!"; children: [] }
n.children.add(n)
let m = Map<Integer, Node>()
let i = 0
while i < 80 { m[i] = n; i = i + 1 }
let saved = m[79]
m.remove(0)
m.clear()
print(saved.children[0].label)
''', 'cyclic!\n')

    def test_callback_cycle_through_map_rejected_after_all_bodies(self):
        self.rejects('''function insert(m: Map<Integer, Callback<Integer>>, call: Callback<Integer>) { m[1] = call }
let m = Map<Integer, Callback<Integer>>()
let call = function(): Integer { return m.length }
insert(m, call)
''', 'Map mutation could create a reference cycle')


class MapResults(MapCallbacks):
    def compile(self, source):
        # Reuse the evidence/ownership machinery with the Result frontend.
        old = callbacks.COMPILER
        suffix = '-sanitize' if callbacks.address_sanitizer_enabled(callbacks.LINK_FLAGS) else ''
        callbacks.COMPILER = Path(os.environ.get('MINYAR_ERRORS_COMPILER', ROOT / 'build' / ('minyarc-errors' + suffix)))
        try:
            return callbacks.Callbacks.compile(self, source)
        finally:
            callbacks.COMPILER = old

    def test_result_payload_contains_map_and_map_contains_result(self):
        self.executes('''let m = Map<Text, Result<List<Integer>, Text>>()
m["answer"] = Ok<List<Integer>, Text>([42])
let saved = m["answer"]
m.clear()
match saved { Ok(v) { print(v[0]) } Err(e) { print(e) } }
let r = Ok<Map<Integer, Text>, Text>(Map())
match r { Ok(v) { v[9] = "result" + "!"; print(v[9]) } Err(e) { print(e) } }
''', '42\nresult!\n')

    def test_imported_result_map_argument_preserves_following_record_type(self):
        (self.directory / 'factory.min').write_text('''public record Box { value: Integer }
public function make(): Result<Map<Integer, Integer>, Box> {
    return Err<Map<Integer, Integer>, Box>(Box { value: 42 })
}
''')
        self.executes('''use "./factory.min" as factory
match factory.make() { Ok(row) { print(row.length) } Err(box) { print(box.value) } }
''', '42\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
