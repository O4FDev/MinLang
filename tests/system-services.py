#!/usr/bin/env python3
"""Small native system contracts; Windows runs only in parent-assigned Boat slots."""
import os
import argparse
from pathlib import Path
import subprocess
import tempfile
from clang_helpers import clang_command, windows_host, launcher_command

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--language', action='store_true', help='compile language regression (run on Boat)')
options = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='minyar-system-services-') as directory:
    binary = Path(directory) / ('services.exe' if windows_host() else 'services')
    command = clang_command([os.environ.get('MINYAR_TEST_CLANG', 'clang'), '-std=c11',
        '-Wall', '-Wextra', '-Werror', '-O1', ROOT/'tests/system-services.c', '-o', binary])
    if windows_host(): command += ['-lpsapi']
    subprocess.run(command, check=True, timeout=30)
    environment = dict(os.environ, MINYAR_SYSTEM_TEST='snowman-☃', MINYAR_SYSTEM_EMPTY='')
    environment.pop('MINYAR_SYSTEM_MISSING', None)
    for case in ('environment', 'limits', 'signals', 'stderr'):
        result = subprocess.run([binary, case], env=environment, capture_output=True, timeout=10)
        assert result.returncode == 0, (case, result.stderr)
        assert result.stdout == b'', (case, result.stdout)
        assert result.stderr == ('diagnostic\0λ\n'.encode() if case == 'stderr' else b''), (case, result.stderr)
        print(f'system {case}: passed', flush=True)
    if options.language:
        source = ROOT/'tests/system-services.min'
        subprocess.run([*launcher_command(ROOT), source, '-o', binary], check=True, timeout=120)
        result = subprocess.run([binary], env=environment, capture_output=True, timeout=10)
        assert result.returncode == 0, result.stderr
        assert result.stdout == b'system services: passed\n', result.stdout
        assert result.stderr == 'system services: stderr λ\n'.encode(), result.stderr
        print('system language services: passed', flush=True)
