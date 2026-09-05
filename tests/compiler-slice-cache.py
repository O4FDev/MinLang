#!/usr/bin/env python3
"""Compiler-only slice interning, including a deliberately broken collision check."""
import os
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
from regressions import CLANG, ROOT


def main():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    runtime = Path(os.environ.get('MINYAR_COMPILER_RUNTIME_SOURCE', ROOT / 'runtime/minyar_runtime.c'))
    env = os.environ.copy()
    env['ASAN_OPTIONS'] = 'detect_leaks=0:halt_on_error=1'
    env['UBSAN_OPTIONS'] = 'halt_on_error=1'
    with tempfile.TemporaryDirectory(prefix='minyar-slice-cache-') as temporary:
        directory = Path(temporary)
        (directory / 'runtime').mkdir()
        (directory / 'tests').mkdir()
        for header in runtime.parent.glob('*.h'):
            shutil.copy2(header, directory / 'runtime' / header.name)
        shutil.copy2(ROOT / 'tests/compiler-slice-cache.c', directory / 'tests/compiler-slice-cache.c')
        source = runtime.read_text()
        before = '!memcmp(cached->bytes, bytes, (size_t)length)'
        assert source.count(before) == 1, 'slice-cache collision check changed'
        for mode in ('control', 'collision-mutant'):
            (directory / 'runtime/minyar_runtime.c').write_text(source if mode == 'control'
                else source.replace(before, '1', 1))
            for opt in ('-O0', '-O2'):
                for sanitized in (False, True):
                    exe = directory / 'case'
                    command = [CLANG, opt, '-Wall', '-Wextra', '-Werror']
                    if sanitized:
                        command += ['-fsanitize=address,undefined']
                    command += [str(directory / 'tests/compiler-slice-cache.c'), '-o', str(exe)]
                    build = subprocess.run(command, text=True, capture_output=True, timeout=30)
                    assert build.returncode == 0, build.stderr
                    result = subprocess.run([str(exe)], env=env, text=True, capture_output=True, timeout=10)
                    if mode == 'control':
                        assert result.returncode == 0 and 'contracts pass' in result.stdout, result.stderr
                    else:
                        assert result.returncode != 0 and ('value->byte_length == n && !memcmp' in result.stderr
                            or 'collision1 != collision2' in result.stderr), result.stderr
            print(f'{mode}: O0/O2 native and sanitizer checks pass', flush=True)
    print('Compiler slice cache semantics and collision mutant verified')


if __name__ == '__main__':
    main()
