#!/usr/bin/env python3
"""Small native system contracts; Windows runs only in parent-assigned Boat slots."""
import os
import argparse
from pathlib import Path
import subprocess
import tempfile
from clang_helpers import clang_command, windows_host
from system_test_build import build_language

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--language', action='store_true', help='compile language regression (run on Boat)')
parser.add_argument('--mode', choices=('native', 'sanitize'), default='native')
parser.add_argument('--prebuilt', action='store_true', help='preserve admitted compiler/runtime bytes without bootstrap')
options = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='minyar-system-services-') as directory:
    binary = Path(directory) / ('services.exe' if windows_host() else 'services')
    command = clang_command([os.environ.get('MINYAR_TEST_CLANG', 'clang'), '-std=c11',
        '-Wall', '-Wextra', '-Werror', '-O1',
        *(['-g', '-fsanitize=address,undefined'] if options.mode == 'sanitize' else []),
        ROOT/'tests/system-services.c', '-o', binary])
    if windows_host(): command += ['-lpsapi']
    subprocess.run(command, check=True, timeout=30)
    environment = dict(os.environ, MINYAR_SYSTEM_TEST='snowman-☃', MINYAR_SYSTEM_EMPTY='')
    environment.update(ASAN_OPTIONS='detect_leaks=0', UBSAN_OPTIONS='halt_on_error=1')
    environment.pop('MINYAR_SYSTEM_MISSING', None)
    for case in ('environment', 'limits', 'signals', 'stderr'):
        result = subprocess.run([binary, case], env=environment, capture_output=True, timeout=10)
        assert result.returncode == 0, (case, result.stderr)
        assert result.stdout == b'', (case, result.stdout)
        assert result.stderr == ('diagnostic\0λ\n'.encode() if case == 'stderr' else b''), (case, result.stderr)
        print(f'system {case}: passed', flush=True)
    if options.language:
        source = ROOT/'tests/system-services.min'
        build_language(ROOT, source, binary, prebuilt=options.prebuilt, sanitize=options.mode == 'sanitize')
        result = subprocess.run([binary], env=environment, capture_output=True, timeout=10)
        assert result.returncode == 0, result.stderr
        assert result.stdout == b'system services: passed\n', result.stdout
        assert result.stderr == 'system services: stderr λ\n'.encode(), result.stderr
        print('system language services: passed', flush=True)
