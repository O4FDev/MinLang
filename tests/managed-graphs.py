#!/usr/bin/env python3
"""Graph acceptance, exact reclamation and unchanged ordinary lowering.

Graph scenarios are independently written from Nim ORC and Astra's graph
oracles. No peer-language harness is copied. Compiler LLVM comparisons use
the same input file path, so diagnostics and literal names cannot hide a
different allocation/barrier path behind path normalization.
"""
import os
from pathlib import Path
import unittest

from regressions import CompilerTestCase, COMPILER, ROOT, CLANG, LINK_FLAGS
from clang_helpers import clang_command
from llvm_sanitizer import prepare_llvm_for_link, address_sanitizer_enabled
import sys
sys.path.insert(0, str(ROOT / 'tools'))
from cycle_runtime import engine_source


BASELINE = Path(os.environ.get('MINYAR_BASELINE_COMPILER',
                              ROOT / 'build/minyarc-baseline')).resolve()


class ManagedGraphs(CompilerTestCase):
    compiler_arguments = ('--library', str(ROOT / 'library'))

    def compile(self, source):
        result, llvm = super().compile(source)
        if result.returncode == 86:
            default = 'minyarc-callbacks-sanitize' if address_sanitizer_enabled(LINK_FLAGS) else 'minyarc-callbacks'
            frontend = Path(os.environ.get('MINYAR_CALLBACK_COMPILER', ROOT / 'build' / default))
            result = self.evidence.run([str(frontend), str(llvm.with_suffix('.min')), str(llvm),
                                       *self.compiler_arguments], capture_output=True, text=True,
                                       timeout=30, phase='compile-closure-extension')
        if result.returncode == 0: prepare_llvm_for_link(llvm, LINK_FLAGS)
        return result, llvm

    def executes(self, source, expected, optimizations=('-O0', '-O2'), status=0, stderr=''):
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue('; minyar-cycle-runtime: 1\n' in llvm.read_text() or
                        '; minyar-callback-runtime: 1\n' in llvm.read_text())
        harness = self.directory / 'runtime.c'
        contract = (ROOT / 'tests/memory-contracts-runtime.c').read_text()
        harness.write_text(contract.replace('#include "../runtime/minyar_runtime.c"',
                                            engine_source(ROOT)))
        # Match the established suites: generated user IR varies O0/O2,
        # while the runtime is the production O2 or sanitizer O1 artifact.
        runtime = harness.with_suffix('.o')
        compiled = self.evidence.run(clang_command([CLANG, '-O1' if LINK_FLAGS else '-O2',
            *LINK_FLAGS, '-DMINYAR_SYSTEM_HEAP=1', '-iquote', str(ROOT / 'runtime'),
            '-c', str(harness), '-o', str(runtime)]), capture_output=True, text=True,
            timeout=30, phase='compile-exact-ownership-runtime')
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        for optimization in optimizations:
            with self.subTest(optimization=optimization):
                executable = llvm.with_suffix('.' + optimization[1:])
                linked = self.evidence.run(clang_command([CLANG, optimization, *LINK_FLAGS,
                            '-Wno-override-module', str(llvm), str(runtime),
                            '-o', str(executable)]), capture_output=True, text=True,
                            timeout=30, phase='link-exact-ownership')
                self.assertEqual(linked.returncode, 0, linked.stderr)
                run = self.evidence.run([str(executable)], capture_output=True,
                                       timeout=30, phase='execute-exact-ownership')
                self.assertEqual(run.returncode, status, run.stderr)
                self.assertEqual(run.stdout, expected.encode())
                self.assertEqual(run.stderr, stderr.encode())

    def test_existing_recursive_programs_keep_exact_llvm(self):
        cases = (
            '''record Callback { value: Integer }
function value(record: Callback): Integer { return record.value }
let callback = Callback { value: 42 }
print(value(callback))
print("function(x: Integer) { Callback<Integer, Integer> }")
''',
            '''record Tree { value: Integer; children: List<Tree> }
function leaf(n: Integer): Tree { return Tree { value: n; children: [] } }
let child = leaf(42)
let branches: List<Tree> = []
let complete = branches.appended(child)
let root = Tree { value: 1; children: complete }
print(root.children[0].value)
''',
            '''record Box { value: Text }
let box = Box { value: "before" }
box.value = box.value + " after"
let values: List<Box> = []
values.add(box)
print(values[0].value)
''',
            '''use "json" as json
let value = json.parse("{\\"x\\":[1,2,{\\"y\\":true}]}")
print(json.pretty(value, ""))
''',
        )
        for source in cases:
            with self.subTest(source=source.splitlines()[0]):
                result, llvm = self.compile(source)
                self.assertEqual(result.returncode, 0, result.stderr)
                reference = llvm.with_suffix('.baseline.ll')
                baseline = self.evidence.run([str(BASELINE), str(llvm.with_suffix('.min')),
                                             str(reference), *self.compiler_arguments],
                                            capture_output=True, text=True, timeout=30,
                                            phase='baseline-compile')
                self.assertEqual(baseline.returncode, 0, baseline.stderr)
                prepare_llvm_for_link(reference, LINK_FLAGS)
                self.assertEqual(llvm.read_bytes(), reference.read_bytes())
                self.assertNotIn('minyar-cycle-runtime', llvm.read_text())
                self.assertNotIn('_traced(', llvm.read_text())

    def test_list_edge_can_close_a_self_cycle(self):
        self.executes('''record Node { value: Integer; children: List<Node> }
let n = Node { value: 7; children: [] }
n.children.add(n)
print(n.children[0].children[0].value)
''', '7\n')

    def test_enabling_cycles_preserves_index_contract_failure(self):
        # This peer-derived source used to fail the type-level cycle proof.
        # The mutation is now expressible, but its actual index is still a bug.
        self.executes('''record Node { children: List<Node> }
let empty: List<Node> = []
let node = Node { children: empty }
node.children[0] = node
''', '', status=1, stderr='Minyar stopped: List position 0 is outside its length of 0.\n')

    def test_record_edge_can_close_a_self_cycle(self):
        self.executes('''record Node { value: Integer; children: List<Node> }
let n = Node { value: 9; children: [] }
n.children = [n]
print(n.children[0].value)
''', '9\n')

    def test_mutually_recursive_aliases_and_replacement(self):
        self.executes('''record Parent { value: Integer; leaves: List<Leaf> }
record Leaf { parent: Parent }
let p = Parent { value: 11; leaves: [] }
let leaf = Leaf { parent: p }
p.leaves.add(leaf)
let alias = p.leaves
p.leaves[0] = Leaf { parent: p }
print(alias[0].parent.value)
let other = Parent { value: 13; leaves: [] }
alias[0].parent = other
print(p.leaves[0].parent.value)
''', '11\n13\n')

    def test_unrelated_recursive_types_keep_untraced_allocations(self):
        source = '''record Cyclic { edges: List<Cyclic> }
record Tree { children: List<Tree> }
function acyclic(): Tree { return Tree { children: [] } }
let cycle = Cyclic { edges: [] }
cycle.edges.add(cycle)
print(acyclic().children.length)
'''
        self.executes(source, '0\n')
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        definition = llvm.read_text().split('define ptr @.minyar.fn.acyclic(', 1)[1].split('\n}\n', 1)[0]
        self.assertIn('@minyar_record_new(', definition)
        self.assertIn('@minyar_list_new()', definition)
        self.assertNotIn('_traced', definition)

    def test_adapted_graph_churn_temporaries_and_shared_append(self):
        expected = {'graphs': '0\n1\n2\n1\n0\n', 'churn': '100000\n',
                    'dense': '5000\n', 'field': '', 'live-churn': '1\n100000\n',
                    'appended': '16800\n800\n'}
        for fixture, stdout in expected.items():
            with self.subTest(fixture=fixture):
                self.executes((ROOT / 'tests/managed-graphs' / (fixture + '.min')).read_text(), stdout)

    def test_closure_callback_retains_lexical_capture(self):
        # This red contract deliberately precedes syntax/type implementation.
        # Scalar captures snapshot; managed captures preserve aliases. Mutable
        # binding boxes and cross-thread callbacks are a separate feature.
        self.executes('''record Box { value: Integer }
let offset = 40
let box = Box { value: 1 }
let callback = function(value: Integer): Integer {
    return offset + box.value + value
}
box.value = 2
print(callback(0))
''', '42\n')


if __name__ == '__main__':
    unittest.main()
