#!/usr/bin/env python3
"""Exercise the module shell harness with actual metadata-dependent crypto IR."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from clang_helpers import native_path
from regressions import CompilerTestCase, COMPILER, ROOT, CLANG, RUNTIME


class ModuleTestDriver(CompilerTestCase):
    def test_shell_harness_links_native_metadata_and_preserves_optimizations(self):
        project = self.directory / 'project with spaces'
        (project / 'tests').mkdir(parents=True)
        (project / 'build').mkdir()
        (project / 'tools').mkdir()
        for name in ('modules', 'packages', 'parallel'):
            shutil.copytree(ROOT / 'tests' / name, project / 'tests' / name)
        shutil.copytree(ROOT / 'library', project / 'library')
        shutil.copy2(ROOT / 'tests/run-module-tests.sh', project / 'tests/run-module-tests.sh')
        shutil.copy2(RUNTIME, project / 'build/minyar-runtime.o')
        log = project / 'driver.jsonl'
        # Observe the actual harness boundary, then delegate to the real driver
        # and native sources. No compiler, linker or executable is simulated.
        (project / 'tools/clang-driver.py').write_text(
            'import json,os,subprocess,sys\n'
            'with open(os.environ["MODULE_DRIVER_LOG"], "a") as stream:\n'
            '    stream.write(json.dumps({"argv":sys.argv[1:],"flags":os.environ.get("MINYAR_CLANG_FLAGS"),"clang":os.environ.get("MINYAR_CLANG")})+"\\n")\n'
            'arguments=sys.argv[1:]\n'
            'arguments[1]=os.environ["MODULE_DRIVER_PROJECT"]\n'
            'sys.exit(subprocess.call([sys.executable,os.environ["MODULE_DRIVER_REAL"],*arguments]))\n')
        environment = dict(os.environ, MINYAR_TEST_COMPILER=native_path(COMPILER),
                           MINYAR_TEST_CLANG=CLANG, MODULE_DRIVER_LOG=native_path(log),
                           MODULE_DRIVER_PROJECT=native_path(ROOT),
                           MODULE_DRIVER_REAL=native_path(ROOT / 'tools/clang-driver.py'))
        result = self.evidence.run(['sh', native_path(project / 'tests/run-module-tests.sh')],
                                   env=environment, text=True, timeout=240, phase='module-shell-harness')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        expected = {name: '-O0 -Wno-override-module' for name in
                    ('basic', 'diamond', 'explicit-main', 'windows-path', 'character-literals',
                     'private-fields', 'search-path')}
        expected.update({name: '-O1 -Wno-override-module' for name in ('json', 'crypto', 'parallel')})
        self.assertEqual({Path(row['argv'][2]).stem: row['flags'] for row in calls}, expected)
        self.assertEqual(len(calls), len(expected))
        for row in calls:
            self.assertEqual(row['argv'][0], 'link')
            self.assertEqual(row['argv'][-1], '0', 'module tests must not silently enable release LTO')
            self.assertEqual(row['clang'], CLANG)
        llvm = project / 'build/module-tests/crypto.ll'
        self.assertIn('; minyar-native-library: securecrypto', llvm.read_text())
        # A direct IR/runtime link is an independent negative control: this
        # fixture really needs native package objects rather than metadata alone.
        result = self.evidence.run([CLANG, '-O1', '-Wno-override-module', native_path(llvm),
                                   native_path(RUNTIME), '-lm', '-o', native_path(project / 'control')],
                                  text=True, timeout=60, phase='native-link-negative-control')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('minyar_securecrypto_', result.stderr)


if __name__ == '__main__':
    unittest.main()
