#!/usr/bin/env python3
"""G11 retained module roots participate in the existing traced graph contract."""
from pathlib import Path
import runpy
import unittest
from regressions import CLANG, LINK_FLAGS, ROOT
from clang_helpers import clang_command, windows_host

ManagedGraphs = runpy.run_path(str(Path(__file__).with_name('managed-graphs.py')))['ManagedGraphs']


class ModuleConstantGraphs(ManagedGraphs):
    def executes_in_profiles(self, source, expected):
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('; minyar-cycle-runtime: 1\n', llvm.read_text())
        contract = (ROOT / 'tests/memory-contracts-runtime.c').read_text()
        engine = runpy.run_path(str(ROOT / 'tools/cycle_runtime.py'))['engine_source'](ROOT)
        profiles = {
            'eager': '',
            'system-k1': '#define MINYAR_SYSTEM_HEAP 1\n#define MINYAR_RC_POLL_BUDGET 1\n',
            'system-k32': '#define MINYAR_SYSTEM_HEAP 1\n',
            'fixed': '#define MINYAR_BOUNDED_HEAP 1\n',
            'lazy': '#define MINYAR_BOUNDED_HEAP 1\n#define MINYAR_LAZY_HEAP 1\n',
        }
        for profile, defines in profiles.items():
            with self.subTest(profile=profile):
                harness = self.directory / (profile + '-runtime.c')
                runtime = harness.with_suffix('.o')
                if not runtime.exists():
                    harness.write_text(defines + contract.replace('#include "../runtime/minyar_runtime.c"', engine))
                    compiled = self.evidence.run(clang_command([CLANG, '-O1' if LINK_FLAGS else '-O2',
                        *LINK_FLAGS, '-iquote', str(ROOT / 'runtime'), '-c', str(harness), '-o', str(runtime)]),
                        capture_output=True, text=True, timeout=30, phase='compile-exact-ownership-' + profile)
                    self.assertEqual(compiled.returncode, 0, compiled.stderr)
                for optimization in ('-O0', '-O2'):
                    with self.subTest(optimization=optimization):
                        executable = llvm.with_suffix('.' + profile + '.' + optimization[1:] +
                                                      ('.exe' if windows_host() else ''))
                        linked = self.evidence.run(clang_command([CLANG, optimization, *LINK_FLAGS,
                            '-Wno-override-module', str(llvm), str(runtime), '-o', str(executable)]),
                            capture_output=True, text=True, timeout=30, phase='link-exact-ownership-' + profile)
                        self.assertEqual(linked.returncode, 0, linked.stderr)
                        run = self.evidence.run([str(executable)], capture_output=True, timeout=30,
                                               phase='execute-exact-ownership-' + profile)
                        self.assertEqual(run.returncode, 0, run.stderr)
                        self.assertEqual(run.stdout, expected.encode())
                        self.assertEqual(run.stderr, b'')

    def test_unused_dense_cycle_released_after_scalar_main(self):
        for body in ('return 0', 'if argumentCount() == 0 { return 0 }; return 1'):
            with self.subTest(body=body):
                self.executes_in_profiles('''record Node { children: List<Node> }
constant ROOT: Node = make()
function make(): Node {
    let node = Node { children: [] }
    for i in 0..256 { node.children.add(node) }
    return node
}
function main(): Integer { ''' + body + ''' }
''', '')

    def test_constant_receivers_survive_calls_that_replace_nested_owners(self):
        self.executes_in_profiles('''record Node { children: List<Node>; label: Text }
constant ROOT: Node = make()
function make(): Node {
    let node = Node { children: []; label: "root" + "!" }
    node.children.add(Node { children: []; label: "child" + "!" })
    node.children.add(node)
    return node
}
function replace(): Text {
    ROOT.children = []
    return "changed" + "!"
}
ROOT.children[0].label = replace()
print(ROOT.label)
ROOT.children = [ROOT]
ROOT.children[0] = ROOT
print(ROOT.children[0].label)
''', 'root!\nroot!\n')

    def test_cyclic_module_root_released_on_normal_return(self):
        self.executes('''record Node { children: List<Node>; label: Text }
constant ROOT: Node = make()
function make(): Node {
    print("graph init")
    let node = Node { children: []; label: "root" + "!" }
    node.children.add(node)
    return node
}
function read(): Text { return ROOT.children[0].label }
print(read())
print(read())
''', 'graph init\nroot!\nroot!\n')


if __name__ == '__main__':
    unittest.main(defaultTest=[f'ModuleConstantGraphs.{name}' for name in ModuleConstantGraphs.__dict__
                              if name.startswith('test_')], verbosity=2)
