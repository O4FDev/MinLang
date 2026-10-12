#!/usr/bin/env python3
"""VMM-5: publish the actual function-name reservation contract."""
import importlib.util
from pathlib import Path
import unittest
from regressions import CompilerTestCase, ROOT

spec = importlib.util.spec_from_file_location('reserved_names', ROOT / 'tools/reserved-names.py')


class ReservedNames(CompilerTestCase):
    def test_builtin_collision_suggests_a_rename_and_published_list(self):
        self.rejects('function joinText(parts: List<Text>, separator: Text): Text { return "" }\n',
                     "function 'joinText' uses a reserved built-in name; rename this function (for example, 'joinTextLocal'); see docs/reserved-names.md")

    def test_all_published_names_are_reserved_and_document_is_current(self):
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual((ROOT / 'docs/reserved-names.md').read_text(), module.render())
        for name in module.names():
            with self.subTest(name=name):
                self.rejects(f'function {name}() {{}}\n', f"function '{name}' uses a reserved built-in name")

    def test_methods_fields_and_longer_names_keep_their_namespace(self):
        self.executes('''record Helpers { joinText: Integer; Map: Integer }
function joinTextLocal(): Integer { return 7 }
let helpers = Helpers { joinText: 3; Map: 4 }
print(helpers.joinText)
print(joinTextLocal())
print(helpers.Map)
''', '3\n7\n4\n')


if __name__ == '__main__': unittest.main(verbosity=2)
