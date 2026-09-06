#!/usr/bin/env python3
"""Standard system/K32 runtime reuse through the actual public launcher."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
# Replays the same contract against the preserved pre-cache launcher/Makefile.
SNAPSHOT = Path(os.environ.get('MINYAR_RUNTIME_CACHE_SNAPSHOT', ROOT))


class RuntimeCache(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='minyar runtime cache ')
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.project = self.work / 'project with spaces'
        (self.project / 'build').mkdir(parents=True)
        for name in ('minyar', 'Makefile'):
            shutil.copy2(SNAPSHOT / name, self.project / name)
        shutil.copytree(ROOT / 'runtime', self.project / 'runtime')
        shutil.copy2(ROOT / 'build/minyarc', self.project / 'build/minyarc')
        tools = self.work / 'tools'
        tools.mkdir()
        # Real runtime rules run unchanged, but no cold compiler bootstrap occurs.
        make = tools / 'make'
        make.write_text('#!/bin/sh\nexec ' + shlex.quote(shutil.which('make')) +
                        ' -o build/minyarc "$@"\n')
        make.chmod(0o700)
        real_clang = shutil.which('clang')
        self.assertIsNotNone(real_clang)
        self.clang_log = self.work / 'clang.jsonl'
        clang = tools / 'clang'
        clang.write_text('#!' + sys.executable + '\n' +
                         'import json, os, sys\n' +
                         'with open(os.environ["CACHE_TEST_CLANG_LOG"], "a") as log:\n' +
                         '    log.write(json.dumps(sys.argv[1:]) + "\\n")\n' +
                         'os.execv(' + repr(real_clang) + ', ["clang", *sys.argv[1:]])\n')
        clang.chmod(0o700)
        self.env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ['PATH'],
                        CACHE_TEST_CLANG_LOG=str(self.clang_log), LIMITED='', SANITIZER_LIMITED='',
                        LLVM_CC='clang')
        for name in ('MINYAR_CLANG', 'MINYAR_CLANG_FLAGS', 'MINYAR_RUNTIME_FLAGS',
                     'MINYAR_MODULE_CACHE', 'MAKEFLAGS', 'MFLAGS'):
            self.env.pop(name, None)
        self.source = self.work / 'source with spaces.min'
        self.source.write_text('function value(n: Integer): Text {\n'
                               'let text = Text(n)\nreturn text\n}\nprint(value(42))\n')
        self.output = self.work / 'output program'

    def launch(self, options=(), extra_env=None):
        self.clang_log.write_text('')
        result = subprocess.run([str(self.project / 'minyar'), *options, str(self.source),
                                 '-o', str(self.output)], cwd=self.work,
                                env=dict(self.env, **(extra_env or {})),
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        ran = subprocess.run([str(self.output)], capture_output=True, text=True, timeout=10)
        self.assertEqual((ran.returncode, ran.stdout, ran.stderr), (0, '42\n', ''))
        return [json.loads(line) for line in self.clang_log.read_text().splitlines()]

    def signature(self, path):
        return path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest()

    def test_standard_runtime_is_reused(self):
        for release in (False, True):
            with self.subTest(release=release):
                options = ['--release'] if release else []
                target = self.project / 'build' / ('minyar-default-runtime-release.ll' if release
                                                  else 'minyar-default-runtime.o')
                self.launch(options)
                self.assertTrue(target.is_file(), 'standard system/K32 launch must create its shared runtime target')
                before = self.signature(target)
                calls = self.launch([*options, '--memory-profile', 'system', '--cleanup-budget', '00032'])
                self.assertEqual(self.signature(target), before)
                self.assertEqual(len(calls), 1, 'second build must link only, without recompiling a runtime')
                self.assertIn(str(target), calls[0])
                self.assertNotIn('-c', calls[0])
                self.assertNotIn('-emit-llvm', calls[0])

    def test_stack_header_change_rebuilds_runtime(self):
        target = self.project / 'build/minyar-default-runtime.o'
        self.launch()
        self.assertTrue(target.is_file())
        before = self.signature(target)
        header = self.project / 'runtime/minyar_stack_frames.h'
        with header.open('a') as stream:
            stream.write('\n/* isolated dependency invalidation */\n')
        # Ensure ordering even on coarse timestamp filesystems. Fixture is discarded.
        newer = time.time() + 2
        os.utime(header, (newer, newer))
        calls = self.launch()
        self.assertNotEqual(self.signature(target)[0], before[0])
        self.assertTrue(any('-c' in call for call in calls), 'header edit must compile a fresh runtime')
        self.assertIn(str(target), calls[-1])

    def test_custom_runtime_flags_use_invocation_storage(self):
        target = self.project / 'build/minyar-default-runtime.o'
        self.launch()
        self.assertTrue(target.is_file())
        before = self.signature(target)
        calls = self.launch(extra_env={'MINYAR_RUNTIME_FLAGS': '-O1 -Wno-override-module'})
        self.assertEqual(self.signature(target), before)
        runtime_call = next(call for call in calls if '-c' in call)
        self.assertIn('-O1', runtime_call)
        runtime_source = next(Path(arg) for arg in runtime_call if arg.endswith('.c'))
        self.assertTrue(runtime_source.parent.name.startswith('invocation.'))
        self.assertEqual(runtime_source.parent.parent, self.project / 'build/programs')
        self.assertNotIn(str(target), calls[-1])
        self.assertTrue(any(Path(arg).name == 'runtime.o' for arg in calls[-1]))
        self.assertFalse(list((self.project / 'build/programs').glob('invocation.*')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
