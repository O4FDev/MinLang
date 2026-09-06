#!/usr/bin/env python3
"""Check release-mode CLI behavior."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReleaseBuild(unittest.TestCase):
    def test_release_and_custom_flags(self):
        with tempfile.TemporaryDirectory(prefix='minyar-release-cli-') as name:
            work = Path(name)
            source, output = work / 'source with spaces.min', work / 'program with spaces'
            source.write_text('let values: List<Integer> = [19, 23]\nprint(values[0] + values[1])\n')
            log, shim = work / 'clang-args.json', work / 'clang-capture'
            shim.write_text('#!/usr/bin/env python3\nimport json,os,sys\n'
                            'open(os.environ["MINYAR_RELEASE_ARGUMENT_LOG"],"w").write(json.dumps(sys.argv[1:]))\n'
                            'os.execvp("clang",["clang",*sys.argv[1:]])\n')
            shim.chmod(0o755)
            env = dict(os.environ, LIMITED='', SANITIZER_LIMITED='', MINYAR_CLANG=str(shim),
                       MINYAR_RELEASE_ARGUMENT_LOG=str(log))
            env.pop('MINYAR_CLANG_FLAGS', None)
            for flags, expected, lto in [([], '-O0', False), (['--release'], '-O2', True),
                                         (['--release'], '-O1', True)]:
                if expected == '-O1':
                    env['MINYAR_CLANG_FLAGS'] = '-O1 -Wno-override-module'
                built = subprocess.run([str(ROOT / 'minyar'), *flags, str(source), '-o', str(output)],
                                       cwd=work, env=env, capture_output=True, text=True, timeout=120)
                self.assertEqual(built.returncode, 0, built.stderr)
                args = json.loads(log.read_text())
                self.assertIn(expected, args)
                self.assertEqual('-flto' in args, lto)
                runtime_name = 'runtime.ll' if lto else 'runtime.o'
                runtime_path = next(Path(arg) for arg in args if Path(arg).name == runtime_name)
                self.assertTrue(runtime_path.parent.name.startswith('invocation.'))
                self.assertEqual(runtime_path.parent.parent, ROOT / 'build/programs')
                self.assertEqual(subprocess.check_output([str(output)], text=True), '42\n')

    def test_release_usage_errors(self):
        for args in (['--release'], ['--release', '--release'],
                     ['--release', 'examples/hello.min', '--unknown']):
            p = subprocess.run([str(ROOT / 'minyar'), *args], cwd=ROOT, capture_output=True,
                               text=True, timeout=10)
            self.assertEqual(p.returncode, 2)
            self.assertIn('usage:', p.stderr)

    def test_release_preserves_runtime_checks(self):
        with tempfile.TemporaryDirectory(prefix='minyar-release-errors-') as name:
            work = Path(name)
            source, output = work / 'checked.min', work / 'checked'
            env = dict(os.environ, LIMITED='', SANITIZER_LIMITED='')
            env.pop('MINYAR_CLANG_FLAGS', None)
            for text, diagnostic in [
                ('let value = 9223372036854775807\nprint(value + 1)\n', 'Integer calculation is outside'),
                ('let values: List<Integer> = [42]\nprint(values[1])\n', 'outside its length'),
                ('let divisor = 0\nprint(42 / divisor)\n', 'Integer cannot be divided by zero'),
            ]:
                source.write_text(text)
                built = subprocess.run([str(ROOT / 'minyar'), '--release', str(source), '-o', str(output)],
                                       env=env, cwd=work, capture_output=True, text=True, timeout=120)
                self.assertEqual(built.returncode, 0, built.stderr)
                p = subprocess.run([str(output)], capture_output=True, text=True, timeout=10)
                self.assertNotEqual(p.returncode, 0)
                self.assertIn(diagnostic, p.stderr)


if __name__ == '__main__':
    unittest.main()
