#!/usr/bin/env python3
"""Compile/check the standard Text workload and retain repeatable raw timings.

Run only under the WS3 Boat lock, with an otherwise idle sandbox. This runner
reports timings; the existing common <=1% regression gates remain unchanged.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import statistics
import subprocess
import time
from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=ROOT / 'build/minyarc')
    parser.add_argument('--runtime', type=Path, default=ROOT / 'build/minyar-runtime.o')
    parser.add_argument('--clang', default=os.environ.get('MINYAR_TEST_CLANG', 'clang'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=9)
    parser.add_argument('--fixture', choices=('text-basics', 'text-find-prefixes'), default='text-basics')
    parser.add_argument('--baseline-compiler', type=Path)
    parser.add_argument('--batch-size', type=int, default=16)
    args = parser.parse_args()
    assert args.repeats >= 1 and args.batch_size >= 1
    source = ROOT / ('benchmarks/' + args.fixture + '.min')
    checksum = 11200000 if args.fixture == 'text-basics' else -64
    llvm = args.output.with_suffix('.ll')
    executable = args.output.with_suffix('.exe')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(args.compiler), str(source), str(llvm)], check=True, timeout=30)
    subprocess.run(clang_command([args.clang, '-O2', '-Wno-override-module',
                                 *shlex.split(os.environ.get('MINYAR_TEST_LINK_FLAGS', '')),
                                 str(llvm), str(args.runtime), '-o', str(executable)]), check=True, timeout=60)
    samples = []
    for _ in range(args.repeats + 1):
        start = time.perf_counter()
        result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=30)
        elapsed = time.perf_counter() - start
        assert result.returncode == 0 and result.stdout == f'{checksum}\n' and not result.stderr, result
        samples.append(elapsed)
    record = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'compiler_sha256': hashlib.sha256(args.compiler.read_bytes()).hexdigest(),
              'runtime_sha256': hashlib.sha256(args.runtime.read_bytes()).hexdigest(),
              'cpu_affinity': sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None,
              'warmup_seconds': samples[0], 'samples_seconds': samples[1:],
              'median_seconds': statistics.median(samples[1:]), 'checksum': checksum}
    if args.baseline_compiler:
        reference = ROOT / 'build/compiler.min'
        samples = {'control': [], 'candidate': []}
        compilers = {'control': args.baseline_compiler, 'candidate': args.compiler}
        outputs = {name: args.output.with_suffix('.' + name + '.ll') for name in compilers}
        expected = None
        for repeat in range(32):
            order = ('control', 'candidate') if repeat % 2 == 0 else ('candidate', 'control')
            for name in order:
                elapsed = 0
                for _ in range(args.batch_size):
                    started = time.perf_counter()
                    built = subprocess.run([str(compilers[name]), str(reference), str(outputs[name])],
                                           capture_output=True, text=True, timeout=30)
                    elapsed += time.perf_counter() - started
                    assert built.returncode == 0 and not built.stderr, built
                    if expected is None: expected = outputs[name].read_bytes()
                    assert outputs[name].read_bytes() == expected, 'same-source LLVM changed'
                if repeat: samples[name].append(elapsed / args.batch_size)
        medians = {name: statistics.median(times) for name, times in samples.items()}
        ratio = medians['candidate'] / medians['control']
        record['self_compile'] = {'source_sha256': hashlib.sha256(reference.read_bytes()).hexdigest(),
                                  'baseline_compiler_sha256': hashlib.sha256(args.baseline_compiler.read_bytes()).hexdigest(),
                                  'batch_size': args.batch_size, 'samples_seconds': samples, 'medians_seconds': medians,
                                  'candidate_control_ratio': ratio, 'maximum_ratio': 1.01, 'passed': ratio <= 1.01}
    args.output.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))
    if args.baseline_compiler: assert record['self_compile']['passed'], 'self-compile exceeded the unchanged 1% gate'

if __name__ == '__main__': main()
