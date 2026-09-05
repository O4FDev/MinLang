#!/usr/bin/env python3
"""Temporary-owner admission, alias lifetime and aggregate cleanup ceilings."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-source', type=Path,
                        default=ROOT / 'runtime/minyar_runtime.c')
    parser.add_argument('--clang', default=os.environ.get('MINYAR_TEST_CLANG', 'clang'))
    args = parser.parse_args()
    environment = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:halt_on_error=1',
                   'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=0'}
    with tempfile.TemporaryDirectory(prefix='minyar-temporary-admission-') as temporary:
        directory = Path(temporary)
        runtime = directory / 'runtime'
        runtime.mkdir()
        shutil.copy2(args.runtime_source, runtime / 'minyar_runtime.c')
        for header in args.runtime_source.parent.glob('*.h'):
            shutil.copy2(header, runtime / header.name)
        # Interpose only the poll definition. Every production call still
        # reaches the test wrapper, which sums actual work across the operation.
        header = runtime / 'minyar_bounded_rc.h'
        source = header.read_text()
        signature = 'size_t minyar_rc_poll(size_t budget) {'
        assert source.count(signature) == 1, 'poll definition changed'
        header.write_text(source.replace(signature, 'size_t probe_poll_impl(size_t budget) {'))
        fixture = Path(__file__).with_suffix('.c')
        checks = 0
        for budget in (1, 2, 7, 32, 1024):
            for profile in ('fixed', 'lazy'):
                for mode in ('native', 'sanitize'):
                    executable = directory / f'{budget}-{profile}-{mode}'
                    flags = ['-std=c11', '-O2', f'-DMINYAR_RC_POLL_BUDGET={budget}',
                             f'-DMINYAR_RUNTIME_SOURCE="{runtime / "minyar_runtime.c"}"']
                    if profile == 'lazy':
                        flags += ['-DMINYAR_LAZY_HEAP=1']
                    if mode == 'sanitize':
                        flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-g']
                    result = subprocess.run([args.clang, *flags, str(fixture), '-o', str(executable)],
                                            capture_output=True, timeout=90)
                    assert result.returncode == 0, result.stderr.decode(errors='replace')
                    for chunk in ('first', 'rollover', 'existing'):
                        for owner in ('owned', 'borrow'):
                            result = subprocess.run([str(executable), chunk, owner],
                                                    capture_output=True, timeout=60, env=environment)
                            assert result.returncode == 0, (
                                budget, profile, mode, chunk, owner, result.stderr.decode(errors='replace'))
                            checks += 1
        idle_fixture = Path(__file__).with_name('temporary-owner-idle.c')
        for budget in (1, 32, 1024):
            for profile in ('system', 'fixed', 'lazy'):
                for mode in ('native', 'sanitize'):
                    executable = directory / f'idle-{budget}-{profile}-{mode}'
                    flags = ['-std=c11', '-O2', f'-DMINYAR_RC_POLL_BUDGET={budget}',
                             f'-DMINYAR_RUNTIME_SOURCE="{runtime / "minyar_runtime.c"}"']
                    if profile == 'system':
                        flags += ['-DMINYAR_SYSTEM_HEAP=1']
                    else:
                        flags += ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_BOUNDED_HEAP_BYTES=4096']
                    if profile == 'lazy':
                        flags += ['-DMINYAR_LAZY_HEAP=1']
                    if mode == 'sanitize':
                        flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-g']
                    result = subprocess.run([args.clang, *flags, str(idle_fixture), '-o', str(executable)],
                                            capture_output=True, timeout=90)
                    assert result.returncode == 0, result.stderr.decode(errors='replace')
                    result = subprocess.run([str(executable)], capture_output=True,
                                            timeout=60, env=environment)
                    assert result.returncode == 0, (
                        budget, profile, mode, result.stderr.decode(errors='replace'))
                    checks += 1
        print(f'Temporary-owner admission passed: {checks} pressure, alias, idle and work-ceiling checks.')


if __name__ == '__main__':
    main()
