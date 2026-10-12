#!/usr/bin/env python3
"""Check thread-selector storage and effective allocator admission."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from cycle_runtime import engine_source
from clang_helpers import native_path


class ThreadConfig(unittest.TestCase):
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
