#!/usr/bin/env python3
"""G11 retained module roots participate in the existing traced graph contract."""
from pathlib import Path
import runpy
import unittest

ManagedGraphs = runpy.run_path(str(Path(__file__).with_name('managed-graphs.py')))['ManagedGraphs']


class ModuleConstantGraphs(ManagedGraphs):
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
    unittest.main(defaultTest='ModuleConstantGraphs.test_cyclic_module_root_released_on_normal_return', verbosity=2)
