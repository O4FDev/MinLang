#!/usr/bin/env python3
"""Configured integer Text caches preserve ownership and exact retained storage."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clang', default='clang')
    args = parser.parse_args()
    env = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:halt_on_error=1',
           'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=0'}
    profiles = {
        'eager': [],
        'system': ['-DMINYAR_SYSTEM_HEAP=1'],
        'fixed': ['-DMINYAR_BOUNDED_HEAP=1'],
        'lazy': ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_LAZY_HEAP=1'],
    }
    with tempfile.TemporaryDirectory(prefix='minyar-integer-cache-') as temporary:
        directory = Path(temporary)
        for limit in (0, 1, 42, 43, 256, 32768):
            for profile, flags in profiles.items():
                for sanitize in (False, True):
                    executable = directory / f'{profile}-{limit}-{sanitize}'
                    command = [args.clang, '-std=c11', '-O2', *flags,
                               f'-DMINYAR_INTEGER_TEXT_CACHE_LIMIT={limit}',
                               f'-DEXPECTED_CACHE_LIMIT={limit}']
                    if sanitize:
                        command += ['-fsanitize=address,undefined']
                    command += [str(ROOT / 'tests/integer-text-cache.c'), '-o', str(executable)]
                    built = subprocess.run(command, capture_output=True, text=True, timeout=60)
                    assert built.returncode == 0, (command, built.stderr)
                    result = subprocess.run([str(executable)], capture_output=True,
                                            text=True, env=env, timeout=30)
                    assert result.returncode == 0, (command, result.stdout, result.stderr)
            print(f'cache limit {limit}: all four profiles passed natively and with sanitizers', flush=True)
        # Disabling the permanent cache permits repeated conversion in the
        # smallest supported pool without progressively consuming its space.
        for profile in ('fixed', 'lazy'):
            for sanitize in (False, True):
                executable = directory / f'{profile}-minimum-{sanitize}'
                command = [args.clang, '-std=c11', '-O2', *profiles[profile],
                           '-DMINYAR_BOUNDED_HEAP_BYTES=4096',
                           '-DMINYAR_INTEGER_TEXT_CACHE_LIMIT=0', '-DEXPECTED_CACHE_LIMIT=0']
                if sanitize:
                    command += ['-fsanitize=address,undefined']
                command += [str(ROOT / 'tests/integer-text-cache.c'), '-o', str(executable)]
                built = subprocess.run(command, capture_output=True, text=True, timeout=60)
                assert built.returncode == 0, built.stderr
                result = subprocess.run([str(executable)], capture_output=True,
                                        text=True, env=env, timeout=30)
                assert result.returncode == 0, (command, result.stderr)
        print('Zero-cache conversion also passed with 4 KiB fixed and lazy pools.')
        for limit in (-1, 32769):
            result = subprocess.run([args.clang, '-std=c11',
                                     f'-DMINYAR_INTEGER_TEXT_CACHE_LIMIT={limit}', '-c',
                                     str(ROOT / 'runtime/minyar_runtime.c'),
                                     '-o', str(directory / f'invalid-{limit}.o')],
                                    capture_output=True, text=True, timeout=60)
            assert result.returncode != 0 and 'static assertion failed' in result.stderr
            assert 'Integer Text cache limit must be between' in result.stderr
        zero = directory / 'zero.o'
        subprocess.run([args.clang, '-O2', '-DMINYAR_INTEGER_TEXT_CACHE_LIMIT=0', '-c',
                        str(ROOT / 'runtime/minyar_runtime.c'), '-o', str(zero)],
                       check=True, capture_output=True, timeout=60)
        symbols = subprocess.run(['nm', str(zero)], check=True, capture_output=True,
                                 text=True, timeout=30).stdout
        assert 'integer_cache' not in symbols, 'zero limit retained the cache table'
    print('Invalid limits rejected; zero limit has no cache table.')


if __name__ == '__main__':
    main()
