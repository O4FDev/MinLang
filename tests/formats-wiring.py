#!/usr/bin/env python3
"""Exercise actual Make recipe environment at each format-test launch boundary."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Dispatch(unittest.TestCase):
    def run_recipe(self, target, sanitizer=True):
        with tempfile.TemporaryDirectory(prefix='minyar-formats-routing-') as name:
            root = Path(name).resolve()
            (root / 'tests').mkdir(); (root / 'tools').mkdir(); (root / 'build').mkdir()
            (root / 'build/minyarc').touch()
            selected = root / "selected provider's bin" / 'clang'
            selected.parent.mkdir(); selected.touch()
            shutil.copyfile(ROOT / 'tools/host_paths.py', root / 'tools/host_paths.py')
            shutil.copyfile(ROOT / 'build-support/formats.mk', root / 'formats.mk')
            (root / 'Makefile').write_text('LLVM_CC := native-clang\nLIMITED :=\nSANITIZER_LIMITED :=\ninclude formats.mk\n')
            spy = '''import json,os,sys
print(json.dumps({'clang':os.environ.get('MINYAR_TEST_CLANG'),'path':os.environ['PATH'],
                  'ubsan':os.environ.get('UBSAN_OPTIONS'),'argv':sys.argv[1:]}))
'''
            for script in ('compression-codecs.py', 'sha256.py', 'tar.py', 'formats.py'):
                (root / 'tests' / script).write_text(spy)
            environment = dict(os.environ)
            # This isolated Makefile sets its own native compiler. An outer
            # make's command-line overrides otherwise replace the fixture value.
            for name in ('MAKEFLAGS', 'MFLAGS', 'MAKEOVERRIDES'):
                environment.pop(name, None)
            environment.pop('UBSAN_OPTIONS', None)
            environment.pop('MINYAR_SANITIZER_CLANG', None)
            if sanitizer:
                environment['MINYAR_SANITIZER_CLANG'] = str(selected)
            result = subprocess.run(['make', '-s', target], cwd=root, env=environment,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads(result.stdout)
            if target.endswith('-sanitize'):
                self.assertEqual(receipt['clang'], str(selected) if sanitizer else 'native-clang')
                self.assertEqual(receipt['ubsan'], 'halt_on_error=1')
                if sanitizer:
                    self.assertEqual(receipt['path'].split(os.pathsep)[0], str(selected.parent))
                self.assertIn('sanitize' if target == 'check-compression-sanitize' else '--sanitize', receipt['argv'])
            else:
                self.assertEqual(receipt['clang'], 'native-clang')
                self.assertEqual(receipt['path'], environment['PATH'])
                self.assertIsNone(receipt['ubsan'])

    def test_explicit_sanitizer_compiler_space_apostrophe_and_path(self):
        for target in ('check-compression-sanitize', 'check-sha256-sanitize',
                       'check-tar-sanitize', 'check-formats-pipeline-sanitize'):
            with self.subTest(target=target): self.run_recipe(target)

    def test_sanitizer_default_uses_native_compiler(self):
        self.run_recipe('check-sha256-sanitize', sanitizer=False)

    def test_native_recipe_keeps_native_toolchain(self):
        self.run_recipe('check-sha256')


if __name__ == '__main__':
    unittest.main()
