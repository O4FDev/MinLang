#!/usr/bin/env python3
"""Cycle collector/profile matrix, including sanitizers and small pools."""
import argparse
import os
from pathlib import Path
import subprocess
from regressions import CLANG, ROOT
from llvm_sanitizer import instrument_address_sanitizer


def run(command, **kwargs):
    result = subprocess.run([str(x) for x in command], cwd=ROOT, text=True,
                            capture_output=True, timeout=180, **kwargs)
    if result.returncode:
        raise AssertionError(f'{command}\n{result.stdout}\n{result.stderr}')
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--quick', action='store_true')
    parser.add_argument('--runtime-only', action='store_true',
                        help='run the native API oracle matrix without recompiling source fixtures')
    args = parser.parse_args()
    directory = ROOT / 'build/cycles-profiles'
    directory.mkdir(parents=True, exist_ok=True)
    runtime = ROOT / 'tests/cycles-runtime.c'
    compiler = ROOT / 'build/minyarc'
    sources = ('graphs', 'churn', 'dense', 'field', 'live-churn')
    for name in (() if args.runtime_only else sources):
        run([compiler, ROOT / f'tests/cycles/{name}.min', directory / f'{name}.ll'])
        (directory / f'{name}-sanitize.ll').write_text(instrument_address_sanitizer((directory / f'{name}.ll').read_text()))
    profiles = {
        'system': ['-DMINYAR_SYSTEM_HEAP=1'],
        'fixed': ['-DMINYAR_BOUNDED_HEAP=1'],
        'lazy': ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_LAZY_HEAP=1'],
        'eager': [],
    }
    environment = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:halt_on_error=1',
                   'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
    for profile, flags in profiles.items():
        budgets = (32,) if profile == 'eager' else ((1, 32) if args.quick else (1, 2, 7, 32, 1024))
        for budget in budgets:
            for sanitize in ((True,) if args.quick else (False, True)):
                label = f'{profile}-k{budget}-' + ('sanitize' if sanitize else 'native')
                options = ['-O1', '-g', '-fsanitize=address,undefined'] if sanitize else ['-O2']
                options += ['-Wno-override-module', *flags, f'-DMINYAR_RC_POLL_BUDGET={budget}',
                            '-DMINYAR_BOUNDED_HEAP_BYTES=1048576']
                binary = directory / label
                run([CLANG, *options, '-Wall', '-Wextra', '-Werror', runtime, '-o', binary])
                print(label + ': ' + run([binary], env=environment), flush=True)
                if args.runtime_only:
                    continue
                # The exact accounting harness drains debt only after program
                # return. Churn must fit the pool BEFORE reaching that drain.
                obj = directory / (label + '.o')
                run([CLANG, *options, '-c', ROOT / 'tests/memory-contracts-runtime.c', '-o', obj])
                for name in sources:
                    executable = directory / (label + '-' + name)
                    ir = directory / (name + ('-sanitize' if sanitize else '') + '.ll')
                    run([CLANG, *options, ir, obj, '-o', executable])
                    expected = {'field': '', 'churn': '100000', 'dense': '5000',
                                'live-churn': '1\n100000', 'graphs': '0\n1\n2\n1\n0'}[name]
                    assert run([executable], env=environment) == expected
    if args.runtime_only:
        print('cycle runtime profiles: native/sanitizer roots, oracle, exact recovery and bounded work')
    else:
        print('cycle profiles: native/sanitizer graph semantics, exact recovery and 100,000-cycle pool reuse')


if __name__ == '__main__':
    main()
