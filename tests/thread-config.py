#!/usr/bin/env python3
"""Check thread-selector storage and effective allocator admission."""
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from cycle_runtime import engine_source
from clang_helpers import native_path, windows_host


class ThreadConfig(unittest.TestCase):
    @unittest.skipIf(windows_host(), 'POSIX depth fixture; Windows runtime qualification is separate')
    def test_depth_thread_isolation(self):
        with tempfile.TemporaryDirectory(prefix='minyar-depth-tls-') as temporary:
            for optimization in ('-O0', '-O2'):
                with self.subTest(optimization=optimization):
                    program = Path(temporary) / 'depth'
                    compiled = subprocess.run([os.environ.get('MINYAR_TEST_CLANG', 'clang'),
                        optimization, '-DMINYAR_THREADED=1', '-DMINYAR_SYSTEM_HEAP=1',
                        str(ROOT / 'tests/depth-thread-local.c'), '-pthread', '-lm', '-o', str(program)],
                        capture_output=True, text=True, timeout=30)
                    self.assertEqual(compiled.returncode, 0, compiled.stderr)
                    executed = subprocess.run([str(program)], capture_output=True, text=True, timeout=10)
                    self.assertEqual(executed.returncode, 0, executed.stderr)
                    self.assertEqual(executed.stdout, '')
                    self.assertEqual(executed.stderr, '')

    def test_depth_fixture_platform_selection(self):
        # Evaluate the actual decorator again, including POSIX Python on MSYS.
        for host in ('Linux', 'Darwin', 'Windows', 'MSYS_NT-10.0',
                     'MINGW64_NT-10.0', 'CYGWIN_NT-10.0'):
            with self.subTest(host=host), patch('clang_helpers.platform.system', return_value=host):
                module = runpy.run_path(__file__, run_name='thread_config_platform_probe')
                fixture = module['ThreadConfig'].test_depth_thread_isolation
                self.assertEqual(getattr(fixture, '__unittest_skip__', False),
                                 host not in ('Linux', 'Darwin'))

    def compile(self, definitions, source=None):
        header_root = Path(os.environ.get('MINYAR_THREAD_CONFIG_ROOT', ROOT / 'runtime'))
        command = [os.environ.get('MINYAR_TEST_CLANG', 'clang'), '-std=c11',
                   '-I', native_path(header_root), '-I', native_path(ROOT / 'runtime')]
        command += ['-D' + item for item in definitions]
        command += ['-x', 'c', '-E', '-P', '-'] if source is None else ['-x', 'c', '-fsyntax-only', '-']
        if source is None:
            source = '#include "minyar_thread_config.h"\nMINYAR_THREAD_LOCAL long probe;\n'
        return subprocess.run(command, input=source, capture_output=True, text=True, timeout=10)

    def test_storage_and_profiles(self):
        profiles = [[], ['MINYAR_SYSTEM_HEAP=1'], ['MINYAR_COMPILER_ARENA=1'],
                    ['MINYAR_BOUNDED_HEAP=1'], ['MINYAR_LAZY_HEAP=1'],
                    ['MINYAR_BOUNDED_RC=1'],
                    ['MINYAR_BOUNDED_RC=1', 'MINYAR_SYSTEM_HEAP=1']]
        for selector in ([], ['MINYAR_THREADED=0'], ['MINYAR_THREADED=1']):
            enabled = selector == ['MINYAR_THREADED=1']
            for profile in profiles:
                with self.subTest(selector=selector, profile=profile):
                    bad = enabled and (any(flag.startswith(('MINYAR_COMPILER_ARENA=',
                                      'MINYAR_BOUNDED_HEAP=', 'MINYAR_LAZY_HEAP=')) for flag in profile)
                                      or (profile == ['MINYAR_BOUNDED_RC=1']))
                    result = self.compile(selector + profile)
                    if bad:
                        self.assertNotEqual(result.returncode, 0, result.stdout)
                        self.assertIn('managed threads', result.stderr.lower())
                    else:
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual('_Thread_local' in result.stdout, enabled, result.stdout)

    def test_invalid_selector(self):
        for value in ('2', '-1'):
            with self.subTest(value=value):
                result = self.compile(['MINYAR_THREADED=' + value])
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('MINYAR_THREADED must be 0 or 1', result.stderr)
        self.assertNotEqual(self.compile(['MINYAR_THREADED=bogus'],
                            '#include "minyar_thread_config.h"\n').returncode, 0)

    @unittest.skipIf(windows_host(), 'Threaded runtime is not yet qualified on native Windows')
    def test_runtime_effective_allocators(self):
        engines = [(ROOT / 'runtime/minyar_runtime.c').read_text(), engine_source(ROOT)]
        for number, source in enumerate(engines):
            for flags, accepted in [(['MINYAR_THREADED=1'], True),
                     (['MINYAR_THREADED=1', 'MINYAR_SYSTEM_HEAP=1'], True),
                     (['MINYAR_THREADED=1', 'MINYAR_BOUNDED_RC=1'], False),
                     (['MINYAR_THREADED=1', 'MINYAR_BOUNDED_RC=1', 'MINYAR_SYSTEM_HEAP=1'], True),
                     (['MINYAR_THREADED=0', 'MINYAR_COMPILER_ARENA=1'], True)]:
                with self.subTest(engine=number, flags=flags):
                    result = self.compile(flags, source)
                    self.assertEqual(result.returncode == 0, accepted, result.stderr)
                    if not accepted:
                        self.assertIn('managed threads', result.stderr.lower())


if __name__ == '__main__':
    unittest.main()
