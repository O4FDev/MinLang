#!/usr/bin/env python3
"""Run actual loopback socket contracts against eager RC and ASan/UBSan."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from clang_helpers import windows_host

ROOT = Path(__file__).resolve().parents[1]
CLANG = os.environ.get('MINYAR_TEST_CLANG', 'clang')
WINDOWS = windows_host()


def main():
    (ROOT / 'build').mkdir(exist_ok=True)
    modes = ['native'] if WINDOWS else ['native', 'sanitize']
    with tempfile.TemporaryDirectory(prefix='net-native-', dir=ROOT / 'build') as directory:
        for mode in modes:
            flags = ['-O2'] if mode == 'native' else [
                '-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
            environment = os.environ.copy()
            environment['ASAN_OPTIONS'] = 'detect_leaks=1' if sys.platform.startswith('linux') else 'detect_leaks=0'
            for fixture in ('net-native', 'net-batch'):
                executable = Path(directory) / (f'{fixture}-{mode}' + ('.exe' if WINDOWS else ''))
                command = [CLANG, '-std=c11', '-D_GNU_SOURCE', '-DMINYAR_SYSTEM_HEAP=1',
                           '-Wall', '-Wextra', '-Werror', *flags,
                           str(ROOT / f'tests/{fixture}.c'), str(ROOT / 'runtime/native/net.c'),
                           str(ROOT / 'runtime/minyar_runtime.c'), '-lm', '-o', str(executable)]
                if WINDOWS:
                    command += ['-lws2_32']
                subprocess.run(command, check=True, cwd=ROOT)
                subprocess.run([executable], check=True, env=environment, timeout=30)
        program = Path(directory) / ('net-contract.exe' if WINDOWS else 'net-contract')
        subprocess.run([ROOT / 'minyar', ROOT / 'tests/net-contract.min', '-o', program],
                       check=True, cwd=ROOT, capture_output=True)
        result = subprocess.run([program], check=True, capture_output=True, text=True, timeout=30)
        assert result.stdout == 'true\n' * 11, (result.stdout, result.stderr)
        print('Minyar network result contracts verified')


if __name__ == '__main__':
    main()
