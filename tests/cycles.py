#!/usr/bin/env python3
"""Source acceptance, ownership and profile coverage for cyclic graphs."""
import unittest
from regressions import CompilerTestCase, ROOT

class Cycles(CompilerTestCase):
    def test_list_only_cycle(self):
        self.executes('record Node { children: List<Node> }\nlet n = Node { children: [] }\nn.children.add(n)\n', '')

    def test_graphs_and_temporaries(self):
        self.executes((ROOT / 'tests/cycles/graphs.min').read_text(), '0\n1\n2\n1\n0\n')

if __name__ == '__main__':
    unittest.main()
