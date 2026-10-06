#!/usr/bin/env python3
"""Check List capacity arithmetic before allocation or payload access."""
import argparse
import json
import os
import sys
from pathlib import Path

from test_evidence import Evidence

ROOT = Path(__file__).resolve().parents[1]
PROFILES = {
    'system': ['-DMINYAR_SYSTEM_HEAP=1'],
    'eager': [],
    'arena': ['-DMINYAR_COMPILER_ARENA'],
    'bounded': ['-DMINYAR_BOUNDED_HEAP=1'],
    'lazy': ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_LAZY_HEAP=1'],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['native', 'sanitize', 'both'], default='both')
    parser.add_argument('--profile', choices=[*PROFILES, 'all'], default='all')
    args = parser.parse_args()
    if sys.flags.optimize:
        raise RuntimeError('Size guard checks require assertions')
    modes = ['native', 'sanitize'] if args.mode == 'both' else [args.mode]
    profiles = list(PROFILES) if args.profile == 'all' else [args.profile]
    if os.name == 'nt' and 'lazy' in profiles:
        profiles.remove('lazy')  # No Windows mmap-backed lazy allocator exists.
    inputs = [Path(__file__), ROOT / 'tests/runtime-size-guards.c', ROOT / 'tests/test_evidence.py',
              ROOT / 'runtime/minyar_runtime.c', *sorted((ROOT / 'runtime').glob('*.h'))]
    rows = []
    finite_prefixes = {}
    with Evidence('runtime-size-guards', inputs=inputs, controls={'modes': modes, 'profiles': profiles}) as evidence:
        for mode in modes:
            flags = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if mode == 'sanitize' else []
            env = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0',
                   'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
            for profile in profiles:
                executable = evidence.path / f'{mode}-{profile}'
                evidence.run([os.environ.get('CLANG', 'clang'), '-std=c11', '-O1', '-g',
                              '-Wall', '-Wextra', '-Werror', *flags, *PROFILES[profile],
                              ROOT / 'tests/runtime-size-guards.c', '-o', executable],
                             timeout=60, check=True, phase='compile-size-guards')
                normal = evidence.run([executable], env=env, timeout=15, phase='execute-normal-growth')
                assert (normal.returncode, normal.stdout, normal.stderr) == (0, b'', b''), normal
                cases = [(operation, index) for operation in ('add', 'take') for index in range(6)]
                cases.append(('appended', 0))
                for operation, index in cases:
                    result = evidence.run([executable, operation, str(index)], env=env,
                                          timeout=15, phase='execute-size-rejection')
                    assert (result.returncode, result.stdout, result.stderr) == (
                        1, b'', b'Minyar stopped: this List became too large.\n'), (profile, operation, index, result)
                row = {'mode': mode, 'profile': profile, 'rejections': len(cases), 'normal_growth': 4097,
                       'aliased_integer_and_text_growth': 257, 'all_prior_elements_checked_after_each_append': True}
                if profile in ('bounded', 'lazy'):
                    finite = evidence.path / f'{mode}-{profile}-finite'
                    evidence.run([os.environ.get('CLANG', 'clang'), '-std=c11', '-O1', '-g',
                                  '-Wall', '-Wextra', '-Werror', *flags, *PROFILES[profile],
                                  '-DMINYAR_BOUNDED_HEAP_BYTES=16384', ROOT / 'tests/runtime-size-guards.c',
                                  '-o', finite], timeout=60, check=True, phase='compile-finite-growth')
                    result = evidence.run([finite, 'exhaust'], env=env, timeout=15, phase='execute-finite-growth')
                    assert result.returncode == 1 and result.stderr == (
                        b'Minyar stopped: the bounded heap is exhausted (including pending cleanup and fragmentation).\n'), result
                    prefix = result.stdout.splitlines()
                    assert 5 < len(prefix) < 4097, prefix
                    assert result.stdout == b''.join(str(i).encode() + b'\n' for i in range(len(prefix))), result
                    if profile in finite_prefixes:
                        assert result.stdout == finite_prefixes[profile], 'Sanitizer changed finite growth prefix'
                    finite_prefixes[profile] = result.stdout
                    row['finite_heap_bytes'] = 16384
                    row['finite_successful_prefix'] = len(prefix)
                rows.append(row)
    output = ROOT / 'build/runtime-size-guards.json'
    output.write_text(json.dumps({'status': 'passed', 'cases': rows}, indent=2) + '\n')
    print(f'{sum(row["rejections"] for row in rows)} size rejections and {len(rows)} normal-growth controls passed')


if __name__ == '__main__':
    main()
