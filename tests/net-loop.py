#!/usr/bin/env python3
"""Real selectors/timers plus compiled Minyar, with sanitizer ownership checks."""
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
    with tempfile.TemporaryDirectory(prefix='net-loop-', dir=ROOT / 'build') as temporary:
        for mode in (['native'] if WINDOWS else ['native', 'sanitize', 'app-native', 'app-sanitize']):
            executable = Path(temporary) / (mode + ('.exe' if WINDOWS else ''))
            flags = ['-O2'] if mode.endswith('native') else [
                '-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
            if mode.startswith('app-'):
                flags += ['-DMINYAR_APP_EVENT_LOOP=1']
            command = [CLANG, '-std=c11', '-D_GNU_SOURCE', '-DMINYAR_SYSTEM_HEAP=1',
                       '-Wall', '-Wextra', '-Werror', *flags,
                       str(ROOT / 'tests/net-loop.c'), str(ROOT / 'runtime/minyar_runtime.c'),
                       '-lm', '-o', str(executable)]
            if WINDOWS:
                command += ['-lws2_32']
            subprocess.run(command, check=True, cwd=ROOT)
            environment = os.environ.copy()
            environment['ASAN_OPTIONS'] = 'detect_leaks=1' if sys.platform.startswith('linux') else 'detect_leaks=0'
            environment['UBSAN_OPTIONS'] = 'halt_on_error=1'
            subprocess.run([executable], check=True, env=environment, timeout=30)
        for mode in ['--debug', '--release']:
            program = Path(temporary) / ('minyar-' + mode[2:] + ('.exe' if WINDOWS else ''))
            compiled = subprocess.run([ROOT / 'minyar', mode, ROOT / 'tests/net-loop.min', '-o', program],
                                      capture_output=True, text=True, cwd=ROOT, timeout=60)
            assert compiled.returncode == 0, compiled.stderr
            result = subprocess.run([program], check=True, capture_output=True, text=True, timeout=30)
            assert result.stdout == 'loop module verified\n', (result.stdout, result.stderr)
        print('Compiled Minyar event loop API verified at O0/release')


if __name__ == '__main__':
    main()
