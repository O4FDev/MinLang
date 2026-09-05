#!/usr/bin/env python3
"""Measure cleanup distributions independently of whole-process throughput."""
import argparse
import json
from pathlib import Path
import random
import statistics
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=31)
    args = parser.parse_args()
    directory = Path(tempfile.mkdtemp(prefix='minyar-release-latency-'))
    versions = {'before': args.before.resolve() / 'runtime/minyar_runtime.c',
                'after': ROOT / 'runtime/minyar_runtime.c'}
    for version, source in versions.items():
        subprocess.run(['clang', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-DMINYAR_RUNTIME_SOURCE="' + str(source) + '"',
                        str(ROOT / 'scripts/ownership-latency.c'), '-o', str(directory / version)],
                       check=True, capture_output=True, timeout=60)
    results = {}
    for mode in ('wide', 'chain', 'shared'):
        for size in (50000, 200000, 800000):
            key = f'{mode}/{size}'
            samples = {version: [] for version in versions}
            for repeat in range(args.repeats + 1):
                order = list(versions)
                random.Random(repeat).shuffle(order)
                for version in order:
                    result = subprocess.run([str(directory / version), mode, str(size)],
                                            check=True, capture_output=True, timeout=30)
                    if repeat:
                        samples[version].append(json.loads(result.stdout))
            summary = {}
            for version, rows in samples.items():
                releases = sorted(row['release_ms'] for row in rows)
                summary[version] = {'median_release_ms': statistics.median(releases),
                                    'p95_release_ms': releases[int(.95 * (len(releases) - 1))],
                                    'max_release_ms': max(releases),
                                    'median_build_ms': statistics.median(row['build_ms'] for row in rows),
                                    'live_bytes': rows[0]['live_bytes'],
                                    'live_objects': rows[0]['live_objects'],
                                    'max_queue_capacity': max(row['queue_capacity'] for row in rows)}
            results[key] = {'samples': samples, 'summary': summary}
            print(key, json.dumps(summary), flush=True)
    args.output.write_text(json.dumps({'method': __doc__, 'repeats': args.repeats,
                                      'artifacts': str(directory), 'results': results}, indent=2) + '\n')


if __name__ == '__main__':
    main()
