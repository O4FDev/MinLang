#!/usr/bin/env python3
"""Exercise finite-heap configuration extremes and failure paths.

Temporary binaries run with runtime assertions and sanitizers."""
from pathlib import Path
import argparse
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clang', default=os.environ.get('CLANG', 'clang'))
    args = parser.parse_args()
    environment = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1'}
    with tempfile.TemporaryDirectory(prefix='minyar-bounded-configurations-') as directory:
        directory = Path(directory)
        for budget in (1, 32, 1024):
            for sanitized in (False, True):
                executable = directory / f'bounded-{budget}-{int(sanitized)}'
                command = [args.clang, '-std=c11', '-Wall', '-Wextra', '-Werror',
                           f'-DMINYAR_RC_POLL_BUDGET={budget}',
                           '-O1' if sanitized else '-O2']
                if sanitized:
                    command.extend(['-g', '-fsanitize=address,undefined'])
                command.extend([str(ROOT / 'tests/bounded-runtime.c'), '-o', str(executable)])
                subprocess.run(command, check=True, timeout=60, env=environment)
                checked = subprocess.run([str(executable)], capture_output=True, text=True,
                                         timeout=120, env=environment)
                assert checked.returncode == 0, checked.stdout + checked.stderr
                frame_executable = directory / f'frames-{budget}-{int(sanitized)}'
                frame_command = command[:-3] + [str(ROOT / 'tests/bounded-frame-retirement.c'),
                                                '-o', str(frame_executable)]
                subprocess.run(frame_command, check=True, timeout=60, env=environment)
                frames = subprocess.run([str(frame_executable)], capture_output=True, text=True,
                                        timeout=120, env=environment)
                assert frames.returncode == 0, frames.stdout + frames.stderr
                exhausted = subprocess.run([str(executable), 'oom'], capture_output=True,
                                           text=True, timeout=30, env=environment)
                assert exhausted.returncode != 0, 'oversized allocation unexpectedly succeeded'
                assert 'bounded heap is exhausted' in exhausted.stderr, exhausted.stderr
                if sanitized:
                    stale = subprocess.run([str(executable), 'stale'], capture_output=True,
                                           text=True, timeout=30, env=environment)
                    assert stale.returncode != 0, 'stale pool read unexpectedly survived ASan'
                    assert 'AddressSanitizer' in stale.stderr and 'use-after-poison' in stale.stderr, stale.stderr
                print(f'poll budget {budget}, {"ASan/UBSan" if sanitized else "native"}: '
                      'models, capacity recovery and failure diagnostics passed', flush=True)
        # Invalid compile-time values must fail with the intentional assertion.
        for definition, expected in (
            ('MINYAR_BOUNDED_HEAP_BYTES=1000', 'bounded heap'),
            ('MINYAR_BOUNDED_HEAP_BYTES=6000', 'power of two'),
            ('MINYAR_RC_POLL_BUDGET=0', 'cleanup budget'),
            ('MINYAR_RC_POLL_BUDGET=1025', 'cleanup budget'),
        ):
            checked = subprocess.run(
                [args.clang, '-std=c11', '-DMINYAR_BOUNDED_HEAP=1', '-D' + definition,
                 '-fsyntax-only', str(ROOT / 'runtime/minyar_runtime.c')],
                capture_output=True, text=True, timeout=30, env=environment)
            assert checked.returncode != 0 and expected in checked.stderr, checked.stderr
        print('invalid heap capacities and cleanup budgets rejected at compilation', flush=True)


if __name__ == '__main__':
    main()
