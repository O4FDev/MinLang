#!/usr/bin/env python3
"""Measure release-call distributions and verify complete reclamation.

Uses production-release.c with accounting assertions."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import shutil
import statistics
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FLAGS = {'eager': [], 'system': ['-DMINYAR_SYSTEM_HEAP=1'],
         'fixed': ['-DMINYAR_BOUNDED_HEAP=1'],
         'lazy': ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_LAZY_HEAP=1']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runtime-source', type=Path, default=ROOT / 'runtime/minyar_runtime.c')
    parser.add_argument('--profiles', nargs='+', choices=FLAGS, default=list(FLAGS))
    parser.add_argument('--sizes', nargs='+', type=int, default=[50000, 800000])
    parser.add_argument('--repeats', type=int, default=7)
    parser.add_argument('--clang', default='clang')
    args = parser.parse_args()
    if args.repeats < 1 or any(n < 1 or n > 800000 for n in args.sizes):
        parser.error('positive repeats and sizes in 1..800000 are required')
    directory = Path(tempfile.mkdtemp(prefix='minyar-incremental-release-'))
    runtime = directory / 'runtime'
    runtime.mkdir()
    original = args.runtime_source.resolve()
    for source in [original, *original.parent.glob('*.h')]:
        shutil.copy2(source, runtime / source.name)
    fixture = directory / 'production-release.c'
    shutil.copy2(ROOT / 'experiments/memory/production-release.c', fixture)
    report = {'platform': platform.platform(), 'machine': platform.machine(),
              'method': 'One warm-up then seeded interleaved fresh processes per shape/size. '
                        'Accounting assertions verify every object reclaimed and every poll within K=32. '
                        'Monotonic wall clocks include interruptions and clock-call overhead. '
                        'sum_timed_ns sums timed release/poll calls; it excludes between-call harness work. '
                        'Observed distributions do not establish a hard deadline. No samples discarded.',
              'artifacts': str(directory), 'repeats': args.repeats, 'commands': [], 'results': {},
              'source_sha256': {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in [fixture, *sorted(runtime.iterdir())]}}

    def run(command):
        result = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise RuntimeError(result.stderr or result.stdout)
        return result

    report['toolchain'] = run([args.clang, '--version']).stdout
    for name in args.profiles:
        command = [args.clang, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                   '-D_DEFAULT_SOURCE=1', *FLAGS[name],
                   '-DMINYAR_RUNTIME_SOURCE="' + str(runtime / original.name) + '"',
                   str(fixture), '-o', str(directory / name)]
        report['commands'].append(command)
        run(command)
    for shape in ['wide', 'chain', 'shared']:
        for size in args.sizes:
            samples = {name: [] for name in args.profiles}
            for repeat in range(args.repeats + 1):
                order = list(args.profiles)
                random.Random(repeat).shuffle(order)
                for name in order:
                    row = json.loads(run([directory / name, shape, str(size)]).stdout)
                    if repeat:
                        samples[name].append(row)
            summary = {name: {'median_first_ns': statistics.median(r['first_ns'] for r in rows),
                              'worst_first_ns': max(r['first_ns'] for r in rows),
                              'worst_slice_ns': max(r['max_slice_ns'] for r in rows),
                              'median_sum_timed_ns': statistics.median(r['sum_timed_ns'] for r in rows),
                              'calls': sorted(set(r['calls'] for r in rows))}
                       for name, rows in samples.items()}
            key = f'{shape}/{size}'
            report['results'][key] = {'samples': samples, 'summary': summary}
            args.output.write_text(json.dumps(report, indent=2) + '\n')
            print(key, json.dumps(summary), flush=True)
    print(args.output, flush=True)


if __name__ == '__main__':
    main()
