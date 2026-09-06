#!/usr/bin/env python3
"""Launcher intermediate isolation with prebuilt compiler/runtime artifacts.

A barrier makes both source compilations finish before either linker reads IR.
This deliberately does not test concurrent cold bootstrap or shared outputs.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LauncherIsolation(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='minyar launcher isolation ')
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.project = self.work / 'project with spaces'
        build = self.project / 'build'
        build.mkdir(parents=True)
        shutil.copy2(ROOT / 'minyar', self.project / 'minyar')
        for name in ('minyarc', 'minyar-runtime.o', 'minyar-runtime-release.ll'):
            shutil.copy2(ROOT / 'build' / name, build / name)
        (self.project / 'Makefile').write_text(
            '.PHONY: build/minyarc build/minyar-runtime.o build/minyar-runtime-release.ll\n'
            'build/minyarc build/minyar-runtime.o build/minyar-runtime-release.ll:\n\t@:\n')
        shutil.copytree(ROOT / 'runtime', self.project / 'runtime')
        # Keep this path space-free for the race-only regression on the old launcher.
        wrapper = tempfile.NamedTemporaryFile(prefix='minyar-clang-barrier-', delete=False)
        wrapper.close()
        self.wrapper = Path(wrapper.name)
        self.addCleanup(self.wrapper.unlink, missing_ok=True)
        self.wrapper.write_text('''#!/usr/bin/env python3
import json, os, signal, sys, time
from pathlib import Path
work = Path(os.environ['LAUNCHER_TEST_WORK'])
identity = os.environ['LAUNCHER_TEST_ID']
mode = os.environ.get('LAUNCHER_TEST_MODE', '')
# The configured runtime is compiled before linking. Keep the race barrier
# at the linker, so both generated programs and runtimes exist first.
if '-c' in sys.argv or '-emit-llvm' in sys.argv:
    (work / (identity + '-runtime.json')).write_text(json.dumps(sys.argv[1:]))
    source = next(arg for arg in sys.argv[1:] if arg.endswith('.c'))
    (work / (identity + '-runtime.c')).write_text(Path(source).read_text())
    os.execv(os.environ['LAUNCHER_TEST_REAL_CLANG'], ['clang', *sys.argv[1:]])
(work / (identity + '.json')).write_text(json.dumps(sys.argv[1:]))
if mode == 'barrier':
    deadline = time.monotonic() + 30
    while not all((work / (name + '.json')).exists() for name in ('first', 'second')):
        if time.monotonic() > deadline:
            sys.exit('link barrier timed out: both compilers must complete')
        time.sleep(0.005)
if mode == 'failure':
    sys.exit(37)
if mode == 'signal':
    os.kill(os.getppid(), signal.SIGTERM)
    sys.exit(0)
os.execv(os.environ['LAUNCHER_TEST_REAL_CLANG'], ['clang', *sys.argv[1:]])
''')
        self.wrapper.chmod(0o755)
        self.env = dict(os.environ, MINYAR_CLANG=str(self.wrapper),
                        MINYAR_CLANG_FLAGS='-O1 -Wno-override-module',
                        LAUNCHER_TEST_WORK=str(self.work),
                        LAUNCHER_TEST_REAL_CLANG=shutil.which('clang'))

    def command(self, identity, text, release=False):
        directory = self.work / identity
        directory.mkdir(exist_ok=True)
        source = directory / 'same source name.min'
        source.write_text(text)
        output = directory / 'output with spaces'
        return [str(self.project / 'minyar'), *(['--release'] if release else []),
                str(source), '-o', str(output)], output

    def assert_clean(self):
        self.assertEqual(list((self.project / 'build/programs').iterdir()), [],
                         'invocation intermediate files/directories must be removed')

    def concurrent(self, release):
        jobs = []
        try:
            for identity, value in [('first', 111), ('second', 222)]:
                command, output = self.command(identity, f'print({value})\n', release)
                process = subprocess.Popen(command, cwd=self.work,
                    env=dict(self.env, LAUNCHER_TEST_ID=identity, LAUNCHER_TEST_MODE='barrier'),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                jobs.append((process, identity, value, output))
            for process, identity, value, output in jobs:
                stdout, stderr = process.communicate(timeout=45)
                self.assertEqual(process.returncode, 0, stdout + stderr)
                self.assertEqual(subprocess.check_output([str(output)], text=True), f'{value}\n')
                args = json.loads((self.work / (identity + '.json')).read_text())
                self.assertIn('-O1', args)
                self.assertEqual('-flto' in args, release)
                runtime = 'runtime.ll' if release else 'runtime.o'
                runtime_path = next(Path(arg) for arg in args if Path(arg).name == runtime)
                self.assertTrue(runtime_path.parent.name.startswith('invocation.'))
                self.assertEqual(runtime_path.parent.parent, self.project / 'build/programs')
                config = (self.work / (identity + '-runtime.c')).read_text()
                self.assertIn('#define MINYAR_SYSTEM_HEAP 1', config)
                self.assertIn('#define MINYAR_RC_POLL_BUDGET 32', config)
            program_ir = lambda name: next(a for a in json.loads((self.work / name).read_text())
                                         if '/build/programs/' in a and a.endswith('.ll'))
            self.assertNotEqual(program_ir('first.json'), program_ir('second.json'))
            self.assert_clean()
        finally:
            for process, _, _, _ in jobs:
                if process.poll() is None:
                    process.kill()
                process.communicate()

    def test_same_basename_concurrent_development_builds(self):
        self.concurrent(False)

    def test_same_basename_concurrent_release_builds(self):
        self.concurrent(True)

    def test_clang_path_with_spaces_and_custom_flags(self):
        spaced_wrapper = self.work / 'custom clang with spaces'
        shutil.copy2(self.wrapper, spaced_wrapper)
        command, output = self.command('custom', 'print(42)\n')
        result = subprocess.run(command, cwd=self.work,
            env=dict(self.env, MINYAR_CLANG=str(spaced_wrapper), LAUNCHER_TEST_ID='custom'),
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(subprocess.check_output([str(output)], text=True), '42\n')
        self.assertIn('-O1', json.loads((self.work / 'custom.json').read_text()))
        self.assert_clean()

    def test_compiler_failure_cleans_intermediates(self):
        command, output = self.command('invalid', 'print(missingName)\n')
        result = subprocess.run(command, cwd=self.work,
            env=dict(self.env, LAUNCHER_TEST_ID='invalid'), capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 1)
        self.assertIn("can't find a value", result.stderr)
        self.assertFalse(output.exists())
        self.assertFalse((self.work / 'invalid.json').exists(), 'linker must not run')
        self.assert_clean()

    def test_linker_failure_and_signal_clean_intermediates(self):
        for mode, status in [('failure', 37), ('signal', 143)]:
            with self.subTest(mode=mode):
                command, output = self.command(mode, 'print(42)\n')
                result = subprocess.run(command, cwd=self.work,
                    env=dict(self.env, LAUNCHER_TEST_ID=mode, LAUNCHER_TEST_MODE=mode),
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertFalse(output.exists())
                self.assert_clean()


if __name__ == '__main__':
    unittest.main()
