#!/usr/bin/env python3
"""Collector/reactor progress under unchanged borrowed graphs and real root loss."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from cycle_runtime import publish_engine
sys.path.insert(0, str(ROOT / 'tests'))
from clang_helpers import windows_host

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--legacy-service', action='store_true')
    parser.add_argument('--quick', action='store_true')
    parser.add_argument('--nodes', type=int, nargs='+', choices=[32, 2048, 4096],
                        default=[32, 2048, 4096])
    parser.add_argument('--evidence', type=Path)
    args = parser.parse_args()
    output = args.evidence or ROOT / 'build/cycle-progress'
    output.mkdir(parents=True, exist_ok=True)
    (ROOT / 'build').mkdir(exist_ok=True)
    publish_engine(ROOT)
    inputs = [ROOT / 'tests/cycle-progress.c', Path(__file__).resolve(),
              ROOT / 'tools/cycle_runtime.py', ROOT / 'runtime/minyar_runtime.c',
              *sorted((ROOT / 'runtime').glob('*.h'))]
    report = {'passed': False, 'sanitize': args.sanitize,
              'legacy_service': args.legacy_service, 'nodes': args.nodes,
              'inputs': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in inputs}, 'cases': []}
    flags = (['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
             if args.sanitize else ['-O2'])
    environment = dict(os.environ,
        ASAN_OPTIONS='detect_leaks=' + ('1' if platform.system() == 'Linux' else '0') + ':halt_on_error=1',
        UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    try:
        profiles = {'system': ['-DMINYAR_SYSTEM_HEAP=1'],
                    'fixed': ['-DMINYAR_BOUNDED_HEAP=1'], 'eager': []}
        for profile, options in profiles.items():
            budgets = [32] if profile == 'eager' else ([1, 32] if args.quick else [1, 32, 1024])
            for budget in budgets:
                label = f'{profile}-k{budget}'
                binary = output / (label + ('.exe' if windows_host() else ''))
                command = [os.environ.get('MINYAR_TEST_CLANG', 'clang'), *flags,
                    '-std=c11', '-Wall', '-Wextra', '-Werror', '-iquote', str(ROOT / 'runtime'),
                    *options, '-DMINYAR_BOUNDED_HEAP_BYTES=1048576',
                    f'-DMINYAR_RC_POLL_BUDGET={budget}']
                if args.legacy_service: command += ['-DMINYAR_CYCLE_LEGACY_SERVICE=1']
                command += [str(ROOT / 'tests/cycle-progress.c'), '-lm', '-o', str(binary)]
                for phase, argv in [('compile', command), *[
                    (f'run-n{nodes}', [str(binary), '1', str(nodes)]) for nodes in args.nodes]]:
                    result = subprocess.run(argv, cwd=ROOT, env=environment, capture_output=True,
                                            text=True, timeout=120)
                    (output / f'{label}-{phase}.stdout').write_text(result.stdout)
                    (output / f'{label}-{phase}.stderr').write_text(result.stderr)
                    case = {'profile': label, 'phase': phase, 'argv': argv,
                            'status': result.returncode, 'stdout': result.stdout,
                            'stderr': result.stderr}
                    if binary.is_file(): case['binary_sha256'] = hashlib.sha256(binary.read_bytes()).hexdigest()
                    report['cases'].append(case)
                    if result.returncode:
                        raise AssertionError(f'{label} {phase}: {result.returncode}\n{result.stdout}{result.stderr}')
                    if phase.startswith('run'):
                        print(label + ' ' + phase + ': ' + result.stdout.strip(), flush=True)
        report['passed'] = True
    finally:
        (output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')

if __name__ == '__main__':
    main()
