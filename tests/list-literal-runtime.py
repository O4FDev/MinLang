#!/usr/bin/env python3
"""Bulk scalar List runtime semantics, size guards and allocation-failure checks."""
import argparse
import json
import os
from pathlib import Path
import time

from test_evidence import Evidence

ROOT = Path(__file__).resolve().parents[1]
OVERFLOW = b'Minyar stopped: this List became too large.\n'
OOM = b'Minyar stopped: the computer ran out of memory.\n'
INVALID = ('negative-count', 'negative-length', 'count-overflow', 'byte-overflow',
           'negative-capacity', 'negative-reserve', 'growth-overflow',
           'reserve-byte-overflow', 'grow-maximum')
PROFILES = {
    'arena': ['-DMINYAR_COMPILER_ARENA=1'],
    'eager': [],
    'system': ['-DMINYAR_SYSTEM_HEAP=1'],
    'bounded': ['-DMINYAR_BOUNDED_HEAP=1'],
    'lazy': ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_LAZY_HEAP=1'],
    'fault-system': ['-DLIST_LITERAL_FAULTS=1'],
}


def run_campaign(args):
    modes = ('native', 'sanitize') if args.mode == 'both' else (args.mode,)
    source = ROOT / 'tests/list-literal-runtime.c'
    inputs = [source, Path(__file__), ROOT / 'tests/test_evidence.py',
              ROOT / 'tests/allocation-fault-runtime.c', ROOT / 'runtime/minyar_runtime.c',
              *sorted((ROOT / 'runtime').glob('*.h'))]
    started = time.monotonic()
    observations = []
    with Evidence('list-literal-runtime', inputs=inputs,
                  controls={'modes': modes, 'profiles': list(PROFILES),
                            'invalid_headers': INVALID, 'fault_scope': 'system allocator malloc/realloc refusal'}) as evidence:
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(('MINYAR_FAIL_', 'MINYAR_ALLOCATION_', 'MINYAR_FORCE_MOVE'))}
        environment.update(ASAN_OPTIONS='detect_leaks=0:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')

        def checked(executable, mode, expected_status=0, expected_stdout=b'', expected_stderr=b'', **extra):
            result = evidence.run([executable, mode], timeout=30, env=environment,
                                  phase='execute-' + mode, **extra)
            assert (result.returncode, result.stdout, result.stderr) == (expected_status, expected_stdout, expected_stderr), (
                mode, result.returncode, result.stdout, result.stderr)

        for mode in modes:
            flags = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-g'] if mode == 'sanitize' else []
            optimizations = ('-O0', '-O2') if mode == 'sanitize' else ('-O0', '-O2', '-O3', '-Os')
            for optimization in optimizations:
                for profile, defines in PROFILES.items():
                    executable = evidence.path / (mode + '-' + optimization[1:] + '-' + profile)
                    built = evidence.run([args.clang, '-std=c11', optimization, *flags, *defines,
                                          '-DMINYAR_BOUNDED_HEAP_BYTES=33554432', source, '-o', executable],
                                         timeout=30, phase='compile-link-' + profile)
                    assert built.returncode == 0, built.stderr
                    checked(executable, 'normal', expected_stdout=b'copies-prefixes-capacities-ok\n')
                    checked(executable, 'one-reserve', expected_stdout=b'one-reserve-ok\n')
                    for invalid in INVALID:
                        checked(executable, invalid, 1, b'', OVERFLOW)
                    failures = []
                    if profile == 'fault-system':
                        for failure in ('fail-fresh', 'fail-resize'):
                            checked(executable, failure, 1, b'old-list-preserved\n', OOM)
                            failures.append(failure)
                    observations.append(dict(mode=mode, optimization=optimization, profile=profile,
                                             normal_checks=['mutable-independent-copies', 'null-zero-noop', 'full-prefix-and-tail',
                                                            '21-capacity-boundaries-plus-appends', 'single-backing-reserve'],
                                             rejected_headers=list(INVALID), failures_preserved=failures))
                    print(mode, optimization, profile, 'passed', flush=True)
        receipt = dict(schema_version=1, successful=True, elapsed_seconds=time.monotonic()-started,
                       observations=observations, inputs=evidence.inputs, commands=evidence.commands,
                       scope='Complete helper/runtime campaign for declared profiles/configurations. No compiler-lowering or ABI-overlap/null-receiver guarantee is inferred.')
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(receipt, indent=2)+'\n')
    print(f'{len(observations)} profile/configuration campaigns passed; receipt {args.report}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('native', 'sanitize', 'both'), default='both')
    parser.add_argument('--clang', default=os.environ.get('MINYAR_TEST_CLANG', 'clang'))
    parser.add_argument('--report', type=Path, default=ROOT / 'build/list-literal-runtime-results.json')
    run_campaign(parser.parse_args())
