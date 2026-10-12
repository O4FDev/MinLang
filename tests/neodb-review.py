#!/usr/bin/env python3
"""Independent fault, lifetime and invalid-input controls for files/system."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

from clang_helpers import asan_leak_options, clang_command, windows_host

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    'files-review': [['names'], *[['listing', str(i)] for i in range(4)], ['diagnostic'], ['closed-fd'],
                     ['stale'], ['capacity'], *[['setup', 'fd', str(i)] for i in range(1, 10)],
                     ['setup', 'mutex', '1'], ['setup', 'condition', '1'], ['setup', 'condition', '2'],
                     ['setup', 'create', '1'], ['sticky'], ['sticky', 'rotation'], ['borrowed'],
                     ['saturated'], ['bounds'], ['append-position'], ['boundaries'], ['child-fds']],
    'system-review': [['aliases'], *[['setup', 'fd', str(i)] for i in range(1, 9)],
                      *[['setup', 'action', str(i)] for i in range(1, 4)],
                      ['setup', 'mask', '1'], ['setup', 'mask', '2'], ['rollback-in-flight'], ['stderr'], ['saturated'], ['child-fds']],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('native', 'sanitize'), default='native')
    options = parser.parse_args()
    if windows_host():
        parser.error('files/system are not implemented on Windows')
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    env = dict(os.environ, ASAN_OPTIONS=asan_leak_options()+':halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')
    configurations = [['-O0'], ['-O2']] if options.mode == 'native' else [
        ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']]
    checks = 0
    with tempfile.TemporaryDirectory(prefix='minyar-neodb-review-') as temporary:
        for fixture, cases in CASES.items():
            for index, flags in enumerate(configurations):
                exe = Path(temporary) / (fixture + str(index))
                command = clang_command([clang, '-std=c11', '-D_GNU_SOURCE', '-DMINYAR_SYSTEM_HEAP=1',
                    '-Wall', '-Wextra', '-Werror', *flags, ROOT/'tests'/(fixture+'.c'),
                    ROOT/'runtime/minyar_runtime.c', '-pthread', '-o', exe])
                print(shlex.join(map(str, command)), flush=True)
                built = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=60)
                assert built.returncode == 0, built.stderr
                for args in cases:
                    result = subprocess.run([exe, *args], cwd=ROOT, env=env, capture_output=True, timeout=10)
                    assert result.returncode == 0, (fixture, flags, args, result.returncode, result.stdout, result.stderr)
                    assert result.stderr == b'', (fixture, args, result.stderr)
                    checks += 1
                    print(f'{fixture} {flags[0]} {shlex.join(args)}: exit 0', flush=True)
    print(f'{checks} {options.mode} review controls passed')


if __name__ == '__main__':
    main()
