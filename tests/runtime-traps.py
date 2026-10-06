#!/usr/bin/env python3
"""Check exact traps and capacity boundaries without enormous allocations."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

from clang_helpers import clang_command, windows_host

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clang', default=os.environ.get('MINYAR_TEST_CLANG', 'clang'))
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--legacy-only', action='store_true', help='Replay old ABI and capacity regressions.')
    args = parser.parse_args()
    profiles = {'eager': [], 'arena': ['-DMINYAR_COMPILER_ARENA'],
                'system': ['-DMINYAR_SYSTEM_HEAP=1'], 'fixed': ['-DMINYAR_BOUNDED_HEAP=1']}
    if not windows_host():
        profiles['lazy'] = ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_LAZY_HEAP=1']
    errors = {'overflow': 'this Integer calculation is outside the supported range.',
              'zero': 'an Integer cannot be divided by zero.',
              'division': 'this Integer division is outside the supported range.'}
    cases = [([name], message) for name, message in errors.items()]
    if not args.legacy_only:
        cases += [(['fail-' + name], message) for name, message in errors.items()]
    # Independent arbitrary-precision integers describe the boundary values.
    cases += [(['growth', str(capacity)], 'this List became too large.')
              for capacity in (-(1 << 63), -1, 1 << 61, 1 << 62, (1 << 63) - 1)]
    environment = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:halt_on_error=1',
                   'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
    with tempfile.TemporaryDirectory(prefix='minyar-runtime-traps-') as temporary:
        for profile, definitions in profiles.items():
            executable = Path(temporary) / (profile + ('.exe' if os.name == 'nt' else ''))
            flags = ['-O1', '-g', '-fsanitize=address,undefined'] if args.sanitize else ['-O2']
            if not args.legacy_only:
                flags += ['-DMINYAR_TEST_EXPLICIT_TRAPS']
            command = [args.clang, '-std=c11', '-Wall', '-Wextra', '-Werror', *flags,
                       *definitions, ROOT / 'tests/runtime-traps.c', '-o', executable]
            subprocess.run(clang_command(list(map(str, command))), check=True, timeout=60)
            valid = subprocess.run([str(executable), 'valid'], env=environment,
                                   capture_output=True, text=True, timeout=10)
            assert (valid.returncode, valid.stdout, valid.stderr) == (0, 'valid checks return\n', ''), valid
            for arguments, message in cases:
                result = subprocess.run([str(executable), *arguments], env=environment,
                                        capture_output=True, text=True, timeout=10)
                assert (result.returncode, result.stdout, result.stderr) == (
                    1, '', 'Minyar stopped: ' + message + '\n'), (profile, arguments, result)
            print(f'{profile}: valid arithmetic and {len(cases)} exact failure paths passed', flush=True)


if __name__ == '__main__':
    main()
