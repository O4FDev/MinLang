#!/usr/bin/env python3
"""Stack ownership safety, bounded work and fallback profiles.

Shares the maintained physical ownership graph oracle. All native and sanitizer
builds use the candidate runtime implementation directly; no experiment archive
or pre-generated LLVM is required. This measures correctness, not performance.
"""
import argparse
import os
from pathlib import Path
import shlex
import tempfile
import unittest

from bounded_process import run

ROOT = Path(__file__).resolve().parents[1]
CLANG = 'clang'
MODES = ('native', 'sanitize')


class StackOwnership(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='minyar-stack-ownership-')
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.wrapper = self.work / 'runtime.c'
        self.wrapper.write_text('#include "minyar_runtime.c"\n'
                                '#include "minyar_stack_frames.h"\n')
        self.env = dict(os.environ,
                        ASAN_OPTIONS='detect_leaks=0:detect_stack_use_after_return=1',
                        UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')

    def command(self, command):
        command = list(map(str, command))
        result = run(command, self.env, 120)
        self.assertFalse(result.timed_out, shlex.join(command) + '\n' + result.stdout)
        self.assertEqual(result.returncode, 0, shlex.join(command) + '\n' + result.stdout)
        return result.stdout

    def check_profile(self, profile, budget, mode):
        name = f'{profile}-k{budget}-{mode}'
        binary = self.work / name
        bounded = profile in ('system', 'fixed', 'lazy')
        fixture = 'stack-ownership-runtime.c' if bounded else 'stack-ownership-fallback.c'
        command = [CLANG, '-std=c11', '-O1' if mode == 'sanitize' else '-O2', '-g',
                   '-iquote', ROOT / 'runtime',
                   f'-DMINYAR_RUNTIME_SOURCE="{self.wrapper}"',
                   f'-DMINYAR_RC_POLL_BUDGET={budget}']
        if profile == 'system':
            command += ['-DMINYAR_SYSTEM_HEAP=1']
        elif profile in ('fixed', 'lazy'):
            command += ['-DMINYAR_BOUNDED_HEAP=1']
            if profile == 'lazy':
                command += ['-DMINYAR_LAZY_HEAP=1']
        elif profile == 'arena':
            command += ['-DMINYAR_COMPILER_ARENA=1']
        if mode == 'sanitize':
            command += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
        self.command([*command, ROOT / 'tests' / fixture, '-o', binary])
        # Structural mode also runs all semantic checks and asserts stack
        # admission where eligible, including zero allocation on idle entry.
        output = self.command([binary, *(['require-stack'] if bounded else [])])
        self.assertIn('PASS stack-contract' if bounded else 'PASS private API', output)
        print(name + ': ' + output.strip(), flush=True)

    def test_bounded_profiles(self):
        for profile in ('system', 'fixed', 'lazy'):
            for budget in (1, 2, 8, 9, 32, 1024):
                for mode in MODES:
                    with self.subTest(profile=profile, budget=budget, mode=mode):
                        self.check_profile(profile, budget, mode)

    def test_eager_and_compiler_arena_fallback(self):
        for profile in ('eager', 'arena'):
            for mode in MODES:
                with self.subTest(profile=profile, mode=mode):
                    self.check_profile(profile, 32, mode)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clang', default='clang')
    parser.add_argument('--mode', choices=('both', 'native', 'sanitize'), default='both')
    args, rest = parser.parse_known_args()
    CLANG = args.clang
    MODES = ('native', 'sanitize') if args.mode == 'both' else (args.mode,)
    unittest.main(argv=[__file__, *rest], verbosity=2)
