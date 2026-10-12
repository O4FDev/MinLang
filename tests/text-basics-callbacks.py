#!/usr/bin/env python3
"""Text/List contracts through the independently assembled graph frontends."""
import unittest
import callbacks
from regressions import CompilerTestCase, ROOT

class TextGraphBasics(CompilerTestCase):
    compiler_arguments = ('--library', str(ROOT / 'library'))
    compile = callbacks.Callbacks.compile
    executes = callbacks.Callbacks.executes

    def test_clear_cyclic_lists_and_captured_aliases(self):
        self.executes('''record Node { children: List<Node>; label: Text }
let children: List<Node> = []
let node = Node { children: children; label: "alive" }
children.add(node)
let captured = function(): Text {
    children.clear()
    return node.label.trim()
}
print(captured())
print(children.length)
children.add(node)
children.clear()
print(node.label)
''', 'alive\n0\nalive\n')

    def test_text_results_escape_closure_and_lists(self):
        self.executes('''function make(): Callback<List<Text>> {
    let source = "  é:🍊:零　"
    return function(): List<Text> { return source.trim().split(":") }
}
let callback = make()
let parts = callback()
let middle = parts[1]
parts.clear()
print(middle)
print(middle.find("🍊"))
print(middle.startsWith(""))
print(middle.endsWith("🍊"))
''', '🍊\n0\ntrue\ntrue\n')

if __name__ == '__main__': unittest.main()
