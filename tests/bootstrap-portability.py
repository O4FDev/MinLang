#!/usr/bin/env python3
"""Check bootstrap C semantics with the selected compiler and UBSan."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


@unittest.skipIf(os.name == 'nt', 'UBSan bootstrap probe requires a Unix toolchain')
class BootstrapPortability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='minyar-bootstrap-')
        cls.directory = Path(cls.temporary.name)
        cls.compiler = cls.directory / 'stage0'
        cc = os.environ.get('MINYAR_TEST_BOOTSTRAP_CC', os.environ.get('CC', 'clang'))
        subprocess.run([cc, '-std=c11', '-O2', '-g', '-fsanitize=undefined',
                        '-fno-sanitize-recover=all', '-isystem', str(ROOT / 'vendor'),
                        str(ROOT / 'bootstrap/stage0.c'), '-o', str(cls.compiler)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_largest_integer_has_no_intermediate_overflow(self):
        source = self.directory / 'boundary.min'
        source.write_text('function main() {\nprint(9223372036854775807)\nreturn 0\n}\n')
        result = subprocess.run([str(self.compiler), str(source), '-o',
                                 str(self.directory / 'boundary.ll')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_real_compiler_source_has_no_c_undefined_behavior(self):
        result = subprocess.run([str(self.compiler), str(ROOT / 'compiler/compiler.min'), '-o',
                                 str(self.directory / 'compiler.ll')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
