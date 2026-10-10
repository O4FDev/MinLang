#!/usr/bin/env python3
"""Exercise the Text backing-root budget regression on all incremental heaps."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--clang', default='clang')
    args = p.parse_args()
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',
               UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    with tempfile.TemporaryDirectory(prefix='minyar-text-budget-') as directory:
        for profile, definitions in [('system', ['-DMINYAR_SYSTEM_HEAP=1']),
                                     ('fixed', ['-DMINYAR_BOUNDED_HEAP=1']),
                                     ('lazy', ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_LAZY_HEAP=1'])]:
            for budget in (1, 2, 32, 1024):
                for sanitize in (False, True):
                    binary = Path(directory) / f'{profile}-{budget}-{sanitize}'
                    command = [args.clang, '-std=c11', '-Wall', '-Wextra', '-Werror', '-O2',
                               *definitions, f'-DMINYAR_RC_POLL_BUDGET={budget}']
                    if sanitize:
                        command += ['-g', '-fsanitize=address,undefined']
                    subprocess.run(clang_command([*command, ROOT / 'tests/text-view-budget.c', '-o', binary]),
                                   check=True, env=env, timeout=90)
                    subprocess.run([binary], check=True, env=env, timeout=30, stdout=subprocess.PIPE)
                    print(f'{profile} K{budget} {"ASan/UBSan" if sanitize else "native"}: passed', flush=True)


if __name__ == '__main__':
    main()
