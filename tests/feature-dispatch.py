#!/usr/bin/env python3
"""Parsed feature dispatch has its own status and never emits unsafe LLVM."""
import unittest
from regressions import CompilerTestCase


class FeatureDispatch(CompilerTestCase):
    def test_valid_feature_headers_request_the_extended_frontend(self):
        sources = (
            'function make(): Callback<Nothing> { fail("unused") }\n',
            'function make(): Callback<Integer, Text, Integer> { fail("unused") }\n',
            'function make(): Callback<List<Integer>> { fail("unused") }\n',
            'function make(): Callback<List<Integer>, List<Text>, Nothing> { fail("unused") }\n',
            'function make(): Callback<List<List<Integer> >, Integer> { fail("unused") }\n',
            'let callback = function() {}\n',
            'let callback = function(value: Integer) { print(value) }\n',
            'let callback = function(first: Integer, second: Text): Integer { return first }\n',
            'record Node { children: List<Node> }\nlet node = Node { children: [] }\nnode.children.add(node)\n',
            'record Node { children: List<Node> }\nlet node = Node { children: [] }\nnode.children = [node]\n',
        )
        for source in sources:
            with self.subTest(source=source):
                result, llvm = self.compile(source)
                self.assertEqual(result.returncode, 86, result.stderr)
                self.assertFalse(result.stdout)
                self.assertFalse(result.stderr)
                self.assertFalse(llvm.exists())

    def test_feature_looking_text_and_ordinary_record_name_do_not_dispatch(self):
        result, llvm = self.compile('''record Callback { value: Integer }
function value(record: Callback): Integer { return record.value }
print(value(Callback { value: 42 }))
print("Callback<Integer> function(value: Integer) {}")
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(llvm.exists())
        self.assertNotIn('minyar-cycle-runtime', llvm.read_text())
        self.assertNotIn('minyar-callback-runtime', llvm.read_text())

    def test_incomplete_typed_headers_remain_source_errors(self):
        for source in ('let callback = function(value) {}\n',
                       'let callback = function(1: Integer) {}\n',
                       'let callback = function(): Integer\n',
                       'function make(): Callback<> {}\n',
                       'function make(): Callback<Integer {}\n'):
            with self.subTest(source=source):
                result, llvm = self.compile(source)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertTrue(result.stderr)
                self.assertFalse(llvm.exists())


if __name__ == '__main__':
    unittest.main()
