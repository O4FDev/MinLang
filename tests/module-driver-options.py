#!/usr/bin/env python3
"""Driver option forwarding and validation using a protocol-aware compiler."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ModuleDriverOptions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='minyar driver options ')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.work = Path(cls.temporary.name)
        cls.driver = os.environ.get('MINYAR_TEST_MODULE_DRIVER', str(cls.work / 'module-build'))
        if 'MINYAR_TEST_MODULE_DRIVER' not in os.environ:
            subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                            str(ROOT / 'tools/module-build.c'), '-o', cls.driver], check=True)
        cls.compiler = cls.work / 'compiler with spaces'
        cls.compiler.write_text('#!' + sys.executable + '\n' + '''import json, os, sys
from pathlib import Path
Path(os.environ['MODULE_OPTIONS_LOG']).write_text(json.dumps(sys.argv[1:]))
Path(sys.argv[2]).write_text('; module IR\\n')
start = sys.argv.index('--module-state')
schema = os.environ.get('MODULE_TEST_SCHEMA', '')
Path(sys.argv[start + 2]).write_text(str(len(schema)) + '\\n' + schema if schema else '')
Path(sys.argv[start + 3]).write_text('0 0 0 0 0 0 false\\n')
''')
        cls.compiler.chmod(0o700)
        cls.source = cls.work / 'source with spaces.min'
        cls.source.write_text('print(42)\n')
        cls.library = cls.work / 'library with spaces'
        cls.library.mkdir()

    def invoke(self, options, schema=''):
        log = self.work / 'options.json'
        log.unlink(missing_ok=True)
        result = subprocess.run([self.driver, str(self.compiler), str(self.source),
                                 str(self.work / 'program.ll'), str(self.work / 'cache'), *options],
                                cwd=self.work, env=dict(os.environ, MODULE_OPTIONS_LOG=str(log), MODULE_TEST_SCHEMA=schema),
                                capture_output=True, text=True, timeout=10)
        return result, json.loads(log.read_text()) if log.exists() else None

    def test_library_and_budget_forwarded_in_either_order(self):
        pairs = ['--library', str(self.library), '--bounded-owners', '32']
        for options in (pairs, pairs[2:] + pairs[:2]):
            result, args = self.invoke(options)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(args[args.index('--library') + 1], str(self.library))
            self.assertEqual(args[args.index('--bounded-owners') + 1], '32')

    def test_duplicate_or_missing_options_do_not_run_compiler(self):
        for options in (['--library'], ['--library', str(self.library)] * 2,
                        ['--bounded-owners', '32'] * 2, ['--unknown', 'value']):
            result, args = self.invoke(options)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIsNone(args)

    def test_language_linkage_cache_schemas_are_published(self):
        for schema in ('minyar-module-interface-v5', 'minyar-module-delta-v3'):
            with self.subTest(schema=schema):
                result, args = self.invoke([], schema=schema)
                self.assertIsNotNone(args)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_older_linkage_cache_schemas_are_not_published(self):
        for schema in ('minyar-module-interface-v4', 'minyar-module-delta-v2'):
            with self.subTest(schema=schema):
                result, args = self.invoke([], schema=schema)
                self.assertIsNotNone(args)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('unsupported compiler state', result.stderr)


if __name__ == '__main__':
    unittest.main()
