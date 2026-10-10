#!/usr/bin/env python3
"""Source acceptance, ownership and profile coverage for cyclic graphs."""
import unittest
from regressions import CompilerTestCase, ROOT

class Cycles(CompilerTestCase):
    def test_list_only_cycle(self):
        self.executes('record Node { children: List<Node> }\nlet n = Node { children: [] }\nn.children.add(n)\n', '')

    def test_field_only_cycle(self):
        self.executes((ROOT / 'tests/cycles/field.min').read_text(), '')

    def test_graphs_and_temporaries(self):
        self.executes((ROOT / 'tests/cycles/graphs.min').read_text(), '0\n1\n2\n1\n0\n')

    def test_text_field_append_and_indexed_store_on_cycles(self):
        # In-place Text field appends and borrow-free indexed stores on
        # cycle-capable records and Lists.
        source = (
            'record Node { name: Text; kids: List<Node> }\n'
            'let total = 0\n'
            'let i = 0\n'
            'while i < 20000 {\n'
            '    let a = Node { name: "a"; kids: [] }\n'
            '    let b = Node { name: "b"; kids: [a] }\n'
            '    a.kids.add(b)\n'
            '    a.name = a.name + "x"\n'
            '    a.name += "y"\n'
            '    a.kids[0] = a\n'
            '    b.kids[0] = b\n'
            '    total = total + a.name.length + a.kids.length\n'
            '    i = i + 1\n'
            '}\n'
            'print(total)\n')
        self.executes(source, '80000\n')

if __name__ == '__main__':
    unittest.main()
