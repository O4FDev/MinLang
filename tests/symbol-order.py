#!/usr/bin/env python3
"""Compiler text/symbol comparators obey a total order and sort every input key."""
import json
import os
from pathlib import Path
import subprocess
import unittest

from clang_helpers import clang_command
from regressions import CLANG, LINK_FLAGS, ROOT, RUNTIME, CompilerTestCase

CORE = Path(os.environ.get('MINYAR_TEST_SOURCE', ROOT / 'compiler/compiler.min'))
TEXTS = ('', 'a', 'aa', 'ab', 'b', 'A', 'é', 'e\u0301', '界', '🙂', 'é🙂', 'same', 'same')
SYMBOL_NAMES = ('same', 'a', 'same', '', 'a', '🙂', 'é', 'same', 'A', 'aa', 'é', 'same', 'e\u0301', '界')
SYMBOL_KINDS = (2, 3, 1, 2, 1, 1, 3, 2, 1, 1, 1, 3, 1, 1)


def text_literal(value):
    return json.dumps(value, ensure_ascii=False)


class SymbolOrder(CompilerTestCase):
    def assert_total_order(self, matrix, keys, comparator):
        for left, key in enumerate(keys):
            self.assertEqual(matrix[left][left], 0,
                             f'{comparator} reflexivity failed at entry {left}: {key!r}')
            for right, other in enumerate(keys):
                actual = matrix[left][right]
                expected = (key > other) - (key < other)
                self.assertEqual(actual, expected,
                                 f'{comparator} independent order for {key!r} and {other!r}')
                self.assertEqual(actual, -matrix[right][left],
                                 f'{comparator} antisymmetry at entries {left}, {right}')
                if left != right and key == other:
                    self.assertEqual(actual, 0,
                                     f'{comparator} equal-content distinct entries {left}, {right}')
                for last in range(len(keys)):
                    following = matrix[right][last]
                    if actual <= 0 and following <= 0:
                        self.assertLessEqual(matrix[left][last], 0,
                                             f'{comparator} transitivity at {left}, {right}, {last}')
                        if actual < 0 or following < 0:
                            self.assertLess(matrix[left][last], 0,
                                            f'{comparator} strict transitivity at {left}, {right}, {last}')

    def test_text_and_symbol_total_orders_and_lookup_permutation(self):
        core = CORE.read_text()
        self.assertIn('\nfunction main(', core, 'compiler source entry point changed')
        # Exercise the actual selected compiler source, including a mutation
        # supplied by MINYAR_TEST_SOURCE, through its internal function API.
        core = core.split('\nfunction main(', 1)[0]
        texts = ', '.join(map(text_literal, TEXTS[:-1])) + ', "sa" + "me"'
        names = ', '.join(map(text_literal, SYMBOL_NAMES))
        kinds = ', '.join(map(str, SYMBOL_KINDS))
        probe = '''
function main() {
    let texts: List<Text> = [TEXT_VALUES]
    let left = 0
    while left < texts.length {
        let right = 0
        while right < texts.length {
            print(compareText(texts[left], texts[right]))
            right = right + 1
        }
        left = left + 1
    }
    let names: List<Text> = [SYMBOL_VALUES]
    let kinds: List<Integer> = [KIND_VALUES]
    left = 0
    while left < names.length {
        let right = 0
        while right < names.length {
            print(compareSymbol(names, kinds, left, right))
            right = right + 1
        }
        left = left + 1
    }
    let lookup = buildSymbolLookup(names, kinds)
    print(lookup.length)
    left = 0
    while left < lookup.length {
        print(lookup[left])
        left = left + 1
    }
}
'''.replace('TEXT_VALUES', texts).replace('SYMBOL_VALUES', names).replace('KIND_VALUES', kinds)
        compiled, llvm = self.compile(core + probe)
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        text_count = len(TEXTS)
        symbol_count = len(SYMBOL_NAMES)
        symbol_keys = list(zip(SYMBOL_NAMES, SYMBOL_KINDS))
        for optimization in ('-O0', '-O2'):
            with self.subTest(optimization=optimization):
                executable = self.directory / ('symbol-order-' + optimization[1:])
                linked = subprocess.run(clang_command([CLANG, optimization, *LINK_FLAGS,
                                        '-Wno-override-module', llvm, RUNTIME, '-o', executable]),
                                        capture_output=True, text=True, timeout=60)
                self.assertEqual(linked.returncode, 0, linked.stderr)
                result = subprocess.run([executable], capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, '')
                output = list(map(int, result.stdout.splitlines()))
                self.assertEqual(len(output), text_count ** 2 + symbol_count ** 2 + 1 + symbol_count)
                text_matrix = [output[row * text_count:(row + 1) * text_count]
                               for row in range(text_count)]
                start = text_count ** 2
                symbol_matrix = [output[start + row * symbol_count:start + (row + 1) * symbol_count]
                                 for row in range(symbol_count)]
                self.assert_total_order(text_matrix, TEXTS, 'compareText')
                self.assert_total_order(symbol_matrix, symbol_keys, 'compareSymbol')
                start += symbol_count ** 2
                self.assertEqual(output[start], symbol_count)
                lookup = output[start + 1:]
                self.assertEqual(sorted(lookup), list(range(symbol_count)),
                                 'lookup must contain each input entry exactly once')
                self.assertEqual([symbol_keys[index] for index in lookup], sorted(symbol_keys),
                                 'lookup must order names first, then kinds, without assuming stable ties')


if __name__ == '__main__':
    unittest.main()
