import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from clang_helpers import clang_command
from regressions import COMPILER, CLANG, ROOT


class CompilerContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='minyar-compiler-contracts-')
        cls.addClassCleanup(cls.temporary.cleanup)
        directory = Path(cls.temporary.name)
        original = Path(os.environ.get('MINYAR_TEST_SOURCE', ROOT / 'build/compiler.min')).read_text()
        source = original.split('\nfunction main(')[0] + '''
function main() {
    let mode = argument(0)
    if mode == "nested-reference" {
        let cases: List<Text> = ["(\\n value\\n)", "[\\n value\\n]", "{\\n value\\n}", "other\\nvalue", "(\\n other\\n)\\nvalue", "[\\n other\\n]\\nvalue", "[other] + value", "{other} + value", "{other\\nvalue}"]
        let index = 0
        while index < cases.length {
            let kinds: List<Integer> = []
            let texts: List<Text> = []
            let locations = newSourceMap()
            tokenize(cases[index], kinds, texts, locations)
            print(nameInStatement(kinds, texts, 0, "value"))
            index = index + 1
        }
    } else if mode == "module-type" {
        let fields: List<Text> = ["9223372036854775807"]
        let cursor: List<Integer> = [0]
        print(takeModuleType(fields, cursor))
        print(cursor[0])
    } else if mode == "module-overflow" {
        let fields: List<Text> = ["9223372036854775808"]
        let cursor: List<Integer> = [0]
        print(takeModuleType(fields, cursor))
    } else if mode == "result-limit" {
        let successes: List<Text> = []
        let errors: List<Text> = []
        let index = 0
        while index < 4095 {
            successes.add("shape" + Text(index))
            errors.add("Integer")
            index = index + 1
        }
        print(internResultType("last", "Integer", successes, errors))
        print(internResultType("shape0", "Integer", successes, errors))
        print(successes.length)
        print(internResultType("overflow", "Integer", successes, errors))
    }
}
'''
        path = directory / 'contracts.min'
        llvm = path.with_suffix('.ll')
        path.write_text(source)
        compiled = subprocess.run([COMPILER, path, llvm], capture_output=True, text=True, timeout=30)
        assert compiled.returncode == 0, compiled.stderr
        cls.binary = directory / 'contracts'
        linked = subprocess.run(clang_command([CLANG, '-O1', '-Wno-override-module', llvm,
                                ROOT / 'build/minyar-compiler-runtime.ll', '-o', cls.binary]),
                                capture_output=True, text=True, timeout=30)
        assert linked.returncode == 0, linked.stderr

    def check_mode(self, mode, status, output, error=''):
        result = subprocess.run([self.binary, mode], capture_output=True, text=True, timeout=10)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (status, output, error))

    def test_nested_reference_scan_crosses_only_nested_line_breaks(self):
        self.check_mode('nested-reference', 0, 'true\ntrue\ntrue\nfalse\nfalse\nfalse\ntrue\ntrue\ntrue\n')

    def test_module_integer_codec_accepts_maximum_and_rejects_overflow(self):
        self.check_mode('module-type', 0, '9223372036854775807\n1\n')
        self.check_mode('module-overflow', 1, '', 'Minyar stopped: invalid compiled module type table\n')

    def test_result_interning_reuses_existing_types_at_limit(self):
        self.check_mode('result-limit', 1, 'minyar_result_type_4095\nminyar_result_type_0\n4096\n',
                        'Minyar stopped: too many Result instantiations\n')


if __name__ == '__main__':
    unittest.main()
