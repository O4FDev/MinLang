#!/usr/bin/env python3
"""Check owner-domain entry before RC access on POSIX and native Windows."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from cycle_runtime import engine_source
sys.path.insert(0, str(ROOT / 'tests'))
from clang_helpers import windows_host


def main():
    output = ROOT / 'build/callback-domains'
    output.mkdir(parents=True, exist_ok=True)
    (ROOT / 'build/managed-graphs-engine.c').write_text(engine_source(ROOT))
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    # MinGW lacks the ASan/UBSan runtime; Linux/macOS retain both checks.
    for sanitize in ((False,) if windows_host() else (False, True)):
        binary = output / (('sanitize' if sanitize else 'native') + ('.exe' if windows_host() else ''))
        flags = ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if sanitize else ['-O2']
        command = [clang, *flags, '-std=c11', '-Wall', '-Wextra', '-Werror', '-DMINYAR_SYSTEM_HEAP=1',
            '-iquote', str(ROOT / 'runtime'), str(ROOT / 'tests/callback-domains.c'), '-o', str(binary)]
        if not windows_host(): command += ['-pthread', '-lm']
        compiled = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
        if compiled.returncode: raise AssertionError(compiled.stdout + compiled.stderr)
        for mode in ('', 'callback', 'environment'):
            run = subprocess.run([str(binary), *([mode] if mode else [])], capture_output=True, text=True,
                timeout=10, env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1'))
            expected = 1 if mode else 0
            if run.returncode != expected: raise AssertionError(str((sanitize, mode, run.returncode, run.stdout, run.stderr)))
            if mode:
                if 'different execution domain' not in run.stderr: raise AssertionError(run.stderr)
            elif run.stdout != 'callback domains passed\n' or run.stderr: raise AssertionError(run.stdout + run.stderr)
            print(('sanitize' if sanitize else 'native') + ' ' + (mode or 'owned') + ' passed', flush=True)


if __name__ == '__main__':
    main()
