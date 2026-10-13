#!/usr/bin/env python3
"""Strict 1% fixed-input selfcompile comparison against the frozen compiler.

Execute under the exclusive Boat lock. Rotate paired process order, pin the
same CPU, retain all CPU/wall samples, and compare identical pinned input.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import statistics
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repeats', type=int, default=31)
    a = p.parse_args()
    if hasattr(os, 'sched_getaffinity'):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    source = ROOT / 'build/compiler-baseline-control.min'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == 'a5f30a7954381231fbe04a712b72bd9663d1bd7082c667fef851b739ec63c3cf'
    directory = ROOT / 'build/maps-baseline'
    directory.mkdir(parents=True, exist_ok=True)
    compilers = {'baseline': ROOT / 'build/minyarc-baseline', 'candidate': ROOT / 'build/minyarc'}
    samples = {key: [] for key in compilers}
    output_hashes = {}
    for repetition in range(-1, a.repeats):
        order = list(compilers) if repetition % 2 else list(reversed(compilers))
        for label in order:
            output = directory / (label + '.ll')
            before = resource.getrusage(resource.RUSAGE_CHILDREN)
            start = time.monotonic()
            subprocess.run([str(compilers[label]), str(source), str(output)], check=True, timeout=30)
            wall = time.monotonic() - start
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            cpu = after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime
            if repetition >= 0:
                samples[label].append({'cpu_seconds': cpu, 'wall_seconds': wall})
            output_hashes[label] = hashlib.sha256(output.read_bytes()).hexdigest()
    assert len(set(output_hashes.values())) == 1, output_hashes
    medians = {label: statistics.median(row['cpu_seconds'] for row in rows) for label, rows in samples.items()}
    ratio = medians['candidate'] / medians['baseline']
    results = {'samples': samples, 'median_cpu_seconds': medians, 'ratio': ratio, 'limit': 1.01,
               'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'output_sha256': output_hashes,
               'compiler_sha256': {label: hashlib.sha256(path.read_bytes()).hexdigest() for label, path in compilers.items()},
               'affinity': sorted(os.sched_getaffinity(0))}
    (directory / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps({'median_cpu_seconds': medians, 'ratio': ratio, 'limit': 1.01}), flush=True)
    if ratio > 1.01:
        raise SystemExit('fixed-input selfcompile exceeds the unchanged 1% gate')


if __name__ == '__main__':
    main()
