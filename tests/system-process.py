#!/usr/bin/env python3
"""Safe launch, errno, signal inheritance and owned process lifetime regressions."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from clang_helpers import clang_command, windows_host, native_path
from system_test_build import build_language
ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--mode', choices=('native', 'sanitize'), default='native')
parser.add_argument('--language', action='store_true', help='compile language regression (run on Boat)')
parser.add_argument('--root', action='store_true', help='run ONLY bounded native credential fixture via authorized sudo -n')
parser.add_argument('--prebuilt', action='store_true', help='preserve admitted compiler/runtime bytes without bootstrap')
options = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='minyar-system-process-') as directory:
    directory = Path(directory).resolve(); directory.chmod(0o755)
    binary = directory/('process.exe' if windows_host() else 'process')
    flags = ['-O1', '-g', '-fsanitize=address,undefined'] if options.mode == 'sanitize' else ['-O2']
    command = clang_command([os.environ.get('MINYAR_TEST_CLANG', 'clang'), '-std=c11',
        '-Wall', '-Wextra', '-Werror', *flags, ROOT/'tests/system-process.c', '-o', binary,
        *(['-lpsapi', '-municode'] if windows_host() else ['-pthread'])])
    subprocess.run(command, check=True, timeout=40)
    unicode = directory/'Unicode λ'; unicode.mkdir(mode=0o755)
    target = unicode/binary.name; shutil.copy2(binary, target); target.chmod(0o755)
    env = dict(os.environ, MINYAR_PARENT_ONLY='must not inherit', ASAN_OPTIONS='detect_leaks=0', UBSAN_OPTIONS='halt_on_error=1')
    fixture = [native_path(target), 'contracts', native_path(unicode)]
    if options.root:
        if windows_host(): parser.error('--root requires POSIX')
        fixture[1] = 'root-contracts'
        fixture = ['sudo', '-n', 'timeout', '20', *fixture]
    run = subprocess.run(fixture, env=env, capture_output=True, timeout=25)
    assert run.returncode == 0, (run.returncode, run.stdout, run.stderr)
    assert run.stdout == b'child stdout\nsystem process: passed\n' and run.stderr == 'child stderr λ\n'.encode(), (run.stdout, run.stderr)
    print(f'system process {options.mode}: passed', flush=True)
    if options.language:
        language = directory/('language.exe' if windows_host() else 'language')
        build_language(ROOT, ROOT/'tests/system-process.min', language, prebuilt=options.prebuilt, sanitize=options.mode == 'sanitize')
        run = subprocess.run([language, native_path(target), native_path(unicode)], env=env, capture_output=True, timeout=20)
        assert run.returncode == 0, (run.returncode, run.stdout, run.stderr)
        assert run.stdout == b'system process language: passed\n' and run.stderr == b'', (run.stdout, run.stderr)
        print('system process language: passed', flush=True)
