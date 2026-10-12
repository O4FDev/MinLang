#!/usr/bin/env python3
"""Public List sort contracts, independently generated Python model oracles."""
import importlib.util
import random
import os
import shlex
import unittest
from regressions import CompilerTestCase, ROOT, CLANG, LINK_FLAGS
from clang_helpers import clang_command

spec = importlib.util.spec_from_file_location('sort_callbacks', ROOT / 'tests/callbacks.py')
callbacks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(callbacks)

class NaturalSort(CompilerTestCase):
    def test_gap_image_and_content_hash_byte_order(self):
        self.executes('''let hashes = ["ff", "00", "é", "aa", "a", "00"]
let ordered = hashes.sorted()
print(hashes[0])
let alias = hashes
hashes.sort()
let i = 0
while i < ordered.length { print(ordered[i]); print(alias[i]); i = i + 1 }
''', 'ff\n00\n00\n00\n00\na\na\naa\naa\nff\nff\né\né\n')

    def test_independent_random_models_and_boundaries(self):
        rng = random.Random(813251)
        cases = [[], [5], list(range(64)), list(range(63,-1,-1)), [9]*65]
        cases += [[rng.randrange(-20,21) for _ in range(n)] for n in (2,3,7,16,31,65,129)]
        source, expected = [], []
        for case in cases:
            source.append('if true {\n' + '\n'.join(['let values: List<Integer> = [' + ','.join(map(str,case)) + ']',
                       'let copy = values.sorted()', 'values.sort()', 'let i = 0',
                       'while i < values.length { print(values[i]); print(copy[i]); i = i + 1 }']) + '\n}')
            expected += [str(v) for v in sorted(case) for _ in range(2)]
        self.executes('\n'.join(source)+'\n', '\n'.join(expected)+'\n')

    def test_other_natural_types_and_fresh_empty_copy(self):
        self.executes('''let flags = [true, false, true, false]
flags.sort()
print(flags[0]); print(flags[3])
let chars = ['😀', 'a', 'é']
let ordered = chars.sorted()
print(ordered[0]); print(ordered[1]); print(ordered[2])
let floats = [3.5, -0.0, 0.0, -8.5]
floats.sort()
print(floats[0]); print(floats[3])
let empty: List<Integer> = []
let copy = empty.sorted()
copy.add(1)
print(empty.length)
''', 'false\ntrue\na\né\n😀\n-8.5\n3.5\n0\n')

    def test_unordered_types_and_arguments_rejected(self):
        self.rejects('record Box { value: Integer }\nlet xs = [Box { value: 1 }]\nxs.sort()\n', 'no natural order')
        self.rejects('let xs = [1]\nxs.sorted(2)\n', "expected ')'")

class ComparatorSort(CompilerTestCase):
    compiler_arguments = ('--library', str(ROOT / 'library'))
    compile = callbacks.Callbacks.compile
    def executes(self, source, expected, status=0, stderr=''):
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        harness = self.directory / 'runtime.c'
        profile = shlex.split(os.environ.get('MINYAR_SORT_RUNTIME_FLAGS', '-DMINYAR_SYSTEM_HEAP=1'))
        engine = callbacks.engine_source(ROOT)
        harness.write_text(engine if any('MINYAR_COMPILER_ARENA' in flag for flag in profile) else
            (ROOT / 'tests/memory-contracts-runtime.c').read_text().replace('#include "../runtime/minyar_runtime.c"', engine))
        runtime = harness.with_suffix('.o')
        build = self.evidence.run(clang_command([CLANG, '-O1' if LINK_FLAGS else '-O2', *LINK_FLAGS, *profile, '-iquote', str(ROOT / 'runtime'), '-c', str(harness), '-o', str(runtime)]), timeout=60, phase='sort-ownership-runtime')
        self.assertEqual(build.returncode, 0, build.stderr)
        for optimization in ('-O0', '-O2'):
            exe = llvm.with_suffix('.' + optimization[1:])
            link = self.evidence.run(clang_command([CLANG, optimization, *LINK_FLAGS, '-Wno-override-module', str(llvm), str(runtime), '-o', str(exe)]), timeout=60, phase='sort-link')
            self.assertEqual(link.returncode, 0, link.stderr)
            run = self.evidence.run([str(exe)], timeout=30, phase='sort-execute')
            self.assertEqual((run.returncode, run.stdout, run.stderr), (status, expected.encode(), stderr.encode()))

    def test_empty_singleton_and_escaping_closure(self):
        self.executes('''record Box { offset: Integer }
function factory(): Callback<Integer, Integer, Integer> {
    let box = Box { offset: 0 }
    return function(a: Integer, b: Integer): Integer { return a - b + box.offset }
}
let compare = factory()
let empty: List<Integer> = []
empty.sortBy(compare)
let copy = empty.sortedBy(compare)
copy.add(9)
print(empty.length)
let one = [42]
one.sortBy(compare)
print(one.sortedBy(compare)[0])
''', '0\n42\n')

    def test_slot_mutation_and_growth_rejected_before_publication(self):
        for method in ('sortBy', 'sortedBy'):
            for mutation in ('values[0] = 99', 'values.add(99)'):
                self.executes('''let values = [3, 1, 2]
let compare = function(a: Integer, b: Integer): Integer {
    ''' + mutation + '''
    return a - b
}
values.''' + method + '''(compare)
''', '', 1, 'Minyar stopped: the List was mutated during its sort comparator.\n')

    def test_stable_records_shallow_copy_and_captured_side_effects(self):
        self.executes('''record Row { key: Integer; tag: Text }
record Counter { calls: Integer }
let counter = Counter { calls: 0 }
let rows = [Row { key: 2; tag: "a" }, Row { key: 1; tag: "b" }, Row { key: 2; tag: "c" }, Row { key: 1; tag: "d" }]
let compare: Callback<Row, Row, Integer> = function(a: Row, b: Row): Integer {
    counter.calls = counter.calls + 1
    if a.key < b.key { return -99 }
    if a.key > b.key { return 99 }
    return 0
}
let sorted = rows.sortedBy(compare)
print(rows[0].tag)
rows.sortBy(compare)
let i = 0
while i < rows.length { print(rows[i].tag); print(sorted[i].tag); i = i + 1 }
sorted[0].tag = "shared"
print(rows[0].tag)
print(counter.calls > 0)
''', 'a\nb\nb\nd\nd\na\na\nc\nc\nshared\ntrue\n')

    def test_independent_random_record_stability(self):
        rng = random.Random(98731)
        rows = [(rng.randrange(-4,5), i) for i in range(81)]
        literals = ','.join('Row { key: '+str(key)+'; id: '+str(i)+' }' for key,i in rows)
        source = '''record Row { key: Integer; id: Integer }
let rows = ['''+literals+''']
let compare = function(a: Row, b: Row): Integer { return a.key - b.key }
let ordered = rows.sortedBy(compare)
rows.sortBy(compare)
let i = 0
while i < rows.length { print(rows[i].id); print(ordered[i].id); i = i + 1 }
'''
        expected = ''.join(str(i)+'\n'+str(i)+'\n' for key,i in sorted(rows, key=lambda row:row[0]))
        self.executes(source, expected)

    def test_receiver_rebinding_and_unpermuted_callback_observation(self):
        self.executes('''record Holder { values: List<Integer> }
let holder = Holder { values: [3, 1, 2] }
let alias = holder.values
let compare = function(a: Integer, b: Integer): Integer {
    if alias[0] != 3 || alias[1] != 1 || alias[2] != 2 { fail("permuted during comparison") }
    holder.values = []
    return a - b
}
holder.values.sortBy(compare)
print(holder.values.length)
print(alias[0]); print(alias[1]); print(alias[2])
''', '0\n1\n2\n3\n')

    def test_comparator_kept_when_selected_field_is_rebound(self):
        self.executes('''record Holder { compare: Callback<Integer, Integer, Integer> }
let holder = Holder { compare: function(a: Integer, b: Integer): Integer { return a - b } }
holder.compare = function(a: Integer, b: Integer): Integer {
    holder.compare = function(x: Integer, y: Integer): Integer { return 0 }
    return a - b
}
let values = [3, 2, 1]
values.sortBy(holder.compare)
print(values[0]); print(values[1]); print(values[2])
''', '1\n2\n3\n')

    def test_float_boolean_character_and_text_thunks(self):
        self.executes('''let fs = [1.5, -2.5]
fs.sortBy(function(a: Float, b: Float): Integer { if a < b { return -1 }; if a > b { return 1 }; return 0 })
print(fs[0])
let bs = [true, false]
bs.sortBy(function(a: Boolean, b: Boolean): Integer { if a == b { return 0 }; if a { return 1 }; return -1 })
print(bs[0])
let cs = ['z', 'a']
cs.sortBy(function(a: Character, b: Character): Integer { return Integer(a) - Integer(b) })
print(cs[0])
let ts = ["long", "a"]
ts.sortBy(function(a: Text, b: Text): Integer { return a.length - b.length })
print(ts[0])
''', '-2.5\nfalse\na\na\n')

    def test_cyclic_record_list_publication(self):
        self.executes('''record Node { key: Integer; links: List<Node> }
let a = Node { key: 2; links: [] }
let b = Node { key: 1; links: [] }
let nodes = [a, b]
a.links = nodes
b.links = nodes
let compare = function(x: Node, y: Node): Integer { return x.key - y.key }
let copy = nodes.sortedBy(compare)
nodes.sortBy(compare)
print(nodes[0].key); print(nodes[1].key)
print(copy[0].links[0].key)
''', '1\n2\n1\n')

    def test_signature_rejected(self):
        for header in ('a: Integer, b: Integer): Boolean { return true', 'a: Text, b: Text): Integer { return 0', 'a: Integer): Integer { return a'):
            self.rejects('let values = [2,1]\nvalues.sortBy(function('+header+' })\n', 'Callback<T, T, Integer>')

if __name__ == '__main__': unittest.main()
