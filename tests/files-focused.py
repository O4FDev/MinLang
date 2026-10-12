#!/usr/bin/env python3
"""Small files-only native controls; each case has a bounded process lifetime."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
from clang_helpers import clang_command, windows_host
ROOT = Path(__file__).resolve().parents[1]
CASES = {'files-ranges': ['huge', 'invalid', 'pseudo', 'large', 'eof']}
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sanitize', action='store_true')
    options = parser.parse_args()
    if windows_host():
        parser.error('use files-windows.c for the Windows backend')
    flags = ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if options.sanitize else ['-O2']
    with tempfile.TemporaryDirectory(prefix='minyar-files-focused-') as directory:
        for fixture, cases in CASES.items():
            exe = Path(directory)/fixture
            command = clang_command([os.environ.get('MINYAR_TEST_CLANG', 'clang'), '-std=c11', '-D_GNU_SOURCE',
                '-DMINYAR_SYSTEM_HEAP=1', '-Wall', '-Wextra', '-Werror', *flags,
                ROOT/'tests'/(fixture+'.c'), ROOT/'runtime/minyar_runtime.c', '-pthread', '-o', exe])
            subprocess.run(command, check=True, cwd=ROOT, timeout=60)
            for case in cases:
                subprocess.run([exe, case], check=True, cwd=ROOT, timeout=10)
                print(f'{fixture} {case}: passed', flush=True)
if __name__ == '__main__':
    main()
