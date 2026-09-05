#!/usr/bin/env python3
"""Interleave measurements of two compiler/runtime versions.

Whole runs use the benchmark verbatim. Kernel runs select one top-level call
in a temporary copy. Runtime objects must use matching ABIs."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import resource
import statistics
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before-compiler', type=Path, required=True)
    parser.add_argument('--before-runtime', type=Path, required=True)
    parser.add_argument('--after-compiler', type=Path, default=ROOT / 'build/minyarc')
    parser.add_argument('--after-runtime', type=Path, default=ROOT / 'build/minyar-runtime.o')
    parser.add_argument('--clang', default='clang')
    parser.add_argument('--repeats', type=int, default=11)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    directory = Path(tempfile.mkdtemp(prefix='minyar-ownership-comparison-'))
    benchmark = ROOT / 'tests/performance/runtime.min'
    source = benchmark.read_text()
    versions = {'before': (args.before_compiler.resolve(), args.before_runtime.resolve()),
                'after': (args.after_compiler.resolve(), args.after_runtime.resolve())}
    samples, summaries = {}, {}

    def run(command):
        return subprocess.run(list(map(str, command)), check=True, capture_output=True,
                              timeout=60)

    for workload in ('whole', 'listWorkload', 'recordWorkload', 'textWorkload',
                     'arithmeticWorkload', 'callWorkload'):
        selected = source if workload == 'whole' else '\n'.join(
            line for line in source.splitlines()
            if not line.startswith('print(') or workload in line) + '\n'
        path = directory / (workload + '.min')
        path.write_text(selected)
        for optimization in ('-O0', '-O2'):
            binaries = {}
            for version, (compiler, runtime) in versions.items():
                stem = directory / (workload + optimization + version)
                ll = stem.with_suffix('.ll')
                run([compiler, path, ll])
                run([args.clang, optimization, '-Wno-override-module', ll, runtime, '-o', stem])
                binaries[version] = stem
            for scale in ((2, 8) if workload == 'whole' else (8,)):
                key = f'{workload}/{optimization}/scale{scale}'
                expected = None
                for binary in binaries.values():
                    result = run([binary, scale])
                    if expected is None:
                        expected = result.stdout
                    assert result.stdout == expected, key
                timings = {version: [] for version in versions}
                for repeat in range(args.repeats):
                    order = list(versions)
                    random.Random(repeat).shuffle(order)
                    for version in order:
                        start = resource.getrusage(resource.RUSAGE_CHILDREN)
                        result = run([binaries[version], scale])
                        end = resource.getrusage(resource.RUSAGE_CHILDREN)
                        assert result.stdout == expected, key
                        timings[version].append(1000 * (end.ru_utime + end.ru_stime
                                                       - start.ru_utime - start.ru_stime))
                samples[key] = timings
                medians = {version: statistics.median(values) for version, values in timings.items()}
                summaries[key] = dict(medians, after_over_before=medians['after'] / medians['before'])
                print(key, summaries[key], flush=True)
    result = {'method': 'Warm-up then seeded interleaved fresh processes; CPU milliseconds; '
              'stdout compared on every run. Whole benchmark unchanged; isolated kernels are temporary copies. '
              'Minyar code linked at O0/O2; runtime optimization supplied by caller.',
              'repeats': args.repeats, 'samples_ms': samples, 'summary': summaries,
              'hashes': {version: {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                                  for path in paths} for version, paths in versions.items()},
              'benchmark_sha256': hashlib.sha256(benchmark.read_bytes()).hexdigest(),
              'artifacts': str(directory)}
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
