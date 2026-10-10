#!/usr/bin/env python3
"""Exact graph/root/debt oracles across heaps, budgets, seeds and sanitizers.

The C fixture is adapted from this repository's audited Astra branch. It
computes reachability independently of collector metadata and reads/mutates
only modeled live nodes. Small poll budgets drive interleavings at every
phase; exact reclaimed-object/byte accounting is checked after each graph.
"""
import argparse
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from cycle_runtime import engine_source
sys.path.insert(0, str(ROOT / 'tests'))
from clang_helpers import windows_host


def run(command, **kwargs):
    result = subprocess.run([str(x) for x in command], cwd=ROOT, capture_output=True,
                            text=True, timeout=120, **kwargs)
    if result.returncode:
        raise AssertionError(str(command) + '\n' + result.stdout + result.stderr)
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--quick', action='store_true')
    args = parser.parse_args()
    output = ROOT / 'build/managed-graphs-profiles'
    output.mkdir(parents=True, exist_ok=True)
    (ROOT / 'build/managed-graphs-engine.c').write_text(engine_source(ROOT))
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    profiles = {'system': ['-DMINYAR_SYSTEM_HEAP=1'],
                'fixed': ['-DMINYAR_BOUNDED_HEAP=1'],
                'lazy': ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_LAZY_HEAP=1'],
                'eager': []}
    if windows_host():
        profiles.pop('lazy')
    for profile, flags in profiles.items():
        budgets = (32,) if profile == 'eager' else ((1, 32) if args.quick else (1, 2, 7, 32, 1024))
        for budget in budgets:
            # MinGW has no sanitizer runtime; native Windows still exercises
            # every supported heap/budget/seed and exact independent oracle.
            for sanitize in ((False,) if windows_host() else (False, True)):
                label = profile + '-k' + str(budget) + ('-sanitize' if sanitize else '-native')
                binary = output / (label + ('.exe' if windows_host() else ''))
                options = (['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
                           if sanitize else ['-O2'])
                options += ['-std=c11', '-Wall', '-Wextra', '-Werror', '-iquote', str(ROOT / 'runtime'),
                            *flags, '-DMINYAR_BOUNDED_HEAP_BYTES=1048576',
                            '-DMINYAR_RC_POLL_BUDGET=' + str(budget)]
                run([clang, *options, ROOT / 'tests/managed-graphs-runtime.c', '-lm', '-o', binary])
                for seed in ((314159, 0xffffffff) if args.quick else (0, 1, 7, 314159, 0xffffffff)):
                    environment = dict(os.environ, MINYAR_GRAPH_SEED=str(seed),
                        ASAN_OPTIONS='detect_leaks=' + ('1' if platform.system() == 'Linux' else '0') + ':halt_on_error=1',
                        UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
                    print(label + ' seed=' + str(seed) + ': ' + run([binary], env=environment), flush=True)


if __name__ == '__main__':
    main()
