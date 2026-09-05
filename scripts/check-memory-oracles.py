#!/usr/bin/env python3
"""Validate bounded cleanup with sanitizer and architecture checks.

Snapshots sources and optionally an earlier runtime, then runs object and frame
ownership oracles at budgets 1, 32 and 1024. Results and commands are retained
in a temporary directory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-runtime', type=Path, help='Earlier runtime directory containing its C file and headers')
    parser.add_argument('--llvm', default='/opt/homebrew/opt/llvm/bin/clang')
    args = parser.parse_args()
    destination = Path(tempfile.mkdtemp(prefix='minyar-oracle-platforms-'))
    results = {'directory': str(destination), 'runtimes': {}, 'commands': [], 'complete': False,
               'limitations': ['Rosetta is translated x86_64 on Apple Silicon; Linux and native Intel are not covered.']}
    sources = destination / 'experiments/memory'
    sources.mkdir(parents=True)
    results['oracle_sha256'] = {}
    for name in ('production-live-oracle.c', 'production-frame-oracle.c'):
        shutil.copyfile(ROOT / 'experiments/memory' / name, sources / name)
        results['oracle_sha256'][name] = hashlib.sha256((sources / name).read_bytes()).hexdigest()
    runtimes = [('final', ROOT / 'runtime')]
    if args.baseline_runtime:
        runtimes.insert(0, ('baseline', args.baseline_runtime.resolve()))
    for label, origin in runtimes:
        target = destination / label / 'runtime'
        target.mkdir(parents=True)
        record = {'origin': str(origin), 'sha256': {}}
        for name in ('minyar_runtime.c', 'minyar_rc.h', 'minyar_pool.h', 'minyar_bounded_rc.h'):
            shutil.copyfile(origin / name, target / name)
            record['sha256'][name] = hashlib.sha256((target / name).read_bytes()).hexdigest()
        results['runtimes'][label] = record

    def save():
        (destination / 'results.json').write_text(json.dumps(results, indent=2) + '\n')

    def run(label, command):
        result = subprocess.run(command, env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0'),
                                text=True, capture_output=True, timeout=60)
        (destination / (label + '.log')).write_text(result.stdout + result.stderr)
        results['commands'].append({'label': label, 'argv': command, 'returncode': result.returncode})
        save()
        if result.returncode:
            raise RuntimeError(f'{label} failed; see {destination / (label + ".log")}')
        print(label + ' passed', flush=True)

    print(destination, flush=True)
    platforms = [('native', 'clang', []), ('rosetta', 'clang', ['-arch', 'x86_64']),
                 ('llvm22', args.llvm, [])]
    for runtime, _ in runtimes:
        for platform, compiler, architecture in platforms:
            if runtime == 'baseline' and platform != 'native':
                continue
            for budget in (1, 32, 1024):
                for oracle in ('live', 'frame'):
                    label = f'{runtime}-{platform}-{oracle}-k{budget}'
                    executable = destination / label
                    command = [compiler, *architecture, '-O1', '-g', '-fsanitize=address,undefined',
                               '-fno-omit-frame-pointer', f'-DMINYAR_RC_POLL_BUDGET={budget}',
                               '-DMINYAR_RUNTIME_SOURCE="' + str(destination / runtime / 'runtime/minyar_runtime.c') + '"',
                               str(sources / f'production-{oracle}-oracle.c'), '-o', str(executable)]
                    run(label + '-build', command)
                    run(label, [str(executable)])
    results['complete'] = True
    save()
    print('All narrow sanitizer/oracle checks passed: ' + str(destination / 'results.json'), flush=True)


if __name__ == '__main__':
    main()
