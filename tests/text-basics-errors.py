#!/usr/bin/env python3
"""Result frontend preserves Text result ownership and List edge removal."""
from pathlib import Path
import importlib.util
import sys
import unittest
from regressions import CompilerTestCase, ROOT

_spec = importlib.util.spec_from_file_location('text_errors_frontend_contract', Path(__file__).with_name('errors-language.py'))
_errors = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _errors
_spec.loader.exec_module(_errors)

class TextResultBasics(CompilerTestCase):
    compiler_arguments = ('--library', str(ROOT / 'library'))
    compile = _errors.ErrorsLanguage.compile
    executes = _errors.ErrorsLanguage.executes

    def test_text_list_return_and_clear_under_result_match(self):
        self.executes('''function pieces(source: Text): Result<List<Text>, Text> {
    return Ok<List<Text>, Text>(source.trim().split(":"))
}
match pieces(" é:42:🍊　") {
    Ok(values) {
        let last = values[2]
        print(Integer(values[1]))
        values.clear()
        print(last)
        print(last.find("🍊"))
    }
    Err(error) { print(error) }
}
''', '42\n🍊\n0\n')

if __name__ == '__main__': unittest.main()
