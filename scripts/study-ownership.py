#!/usr/bin/env python3
"""Separate compiler, layout, and reclamation costs.

Temporary runtime variants retain allocations to measure reclamation overhead."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import resource
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def without_body(source, signature, replacement):
    start = source.index(signature) + len(signature)
    assert source[start] == '{'
    depth, end = 1, start + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[:start] + '{ ' + replacement + ' }' + source[end:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True,
                        help='Snapshot containing minyarc, minyar-runtime.o, runtime/')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=21)
    parser.add_argument('--candidate-runtime', type=Path,
                        help='Compare only the current runtime and this disposable candidate')
    args = parser.parse_args()
    directory = Path(tempfile.mkdtemp(prefix='minyar-ownership-study-'))
    before = args.before.resolve()

    def run(command):
        return subprocess.run(list(map(str, command)), check=True, capture_output=True, timeout=60)

    spec = importlib.util.spec_from_file_location('workloads', ROOT / 'scripts/ownership-workloads.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    native = ROOT / 'build/minyar-runtime.o'
    variants = {
        'before': (before / 'minyarc', before / 'minyar-runtime.o'),
        'borrow_only': (ROOT / 'build/minyarc', before / 'minyar-runtime.o'),
        'layout_only': (before / 'minyarc', native),
        'combined': (ROOT / 'build/minyarc', native),
    }
    if args.candidate_runtime:
        variants = {'combined': (ROOT / 'build/minyarc', native),
                    'candidate': (ROOT / 'build/minyarc', args.candidate_runtime.resolve())}
    runtime_source = (ROOT / 'runtime/minyar_runtime.c').read_text()
    ownership_source = (ROOT / 'runtime/minyar_rc.h').read_text()
    ablations = [] if args.candidate_runtime else [('retain_allocations', False), ('no_counts_or_free', True)]
    for name, remove_retain in ablations:
        path = directory / name
        path.mkdir()
        modified = without_body(ownership_source, 'void minyar_rc_release(void *value) ', '(void)value;')
        if remove_retain:
            modified = without_body(modified, 'void minyar_rc_retain(void *value) ', '(void)value;')
        # The first declarations are arena stubs; replace the native definitions.
        native_start = modified.index('\n#else\n')
        prefix, body = modified[:native_start], modified[native_start:]
        body = without_body(body, 'void minyar_rc_release(void *value) ', '(void)value;')
        if remove_retain:
            body = without_body(body, 'void minyar_rc_retain(void *value) ', '(void)value;')
        (path / 'minyar_rc.h').write_text(prefix + body)
        (path / 'minyar_runtime.c').write_text(runtime_source)
        run(['clang', '-O2', '-c', path / 'minyar_runtime.c', '-o', path / 'runtime.o'])
        variants[name] = (ROOT / 'build/minyarc', path / 'runtime.o')

    results = {}
    for scale in (1, 4):
        for workload, (source, expected) in module.workloads(scale).items():
            path = directory / f'{workload}-{scale}.min'
            path.write_text(source)
            for optimization in ('-O0', '-O2'):
                key = f'{workload}/{optimization}/scale{scale}'
                binaries = {}
                for version, (compiler, runtime) in variants.items():
                    executable = directory / f'{workload}-{scale}-{optimization}-{version}'
                    ll = executable.with_suffix('.ll')
                    run([compiler, path, ll])
                    run(['clang', optimization, '-Wno-override-module', ll, runtime, '-o', executable])
                    assert run([executable]).stdout.decode() == expected, (key, version)
                    binaries[version] = executable
                cpu = {v: [] for v in variants}
                wall = {v: [] for v in variants}
                for repeat in range(args.repeats):
                    order = list(variants)
                    random.Random(repeat).shuffle(order)
                    for version in order:
                        start_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
                        start = time.perf_counter()
                        result = run([binaries[version]])
                        elapsed = time.perf_counter() - start
                        end_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
                        assert result.stdout.decode() == expected, (key, version)
                        cpu[version].append(1000 * (end_cpu.ru_utime + end_cpu.ru_stime
                                                  - start_cpu.ru_utime - start_cpu.ru_stime))
                        wall[version].append(1000 * elapsed)
                rss = {}
                for version, executable in binaries.items():
                    measurement = run([sys.executable, '-c',
                        'import resource,subprocess,sys; '
                        'subprocess.run([sys.argv[1]],check=True,stdout=subprocess.DEVNULL); '
                        'print(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)', executable])
                    rss[version] = int(measurement.stdout) / (1024 * 1024 if sys.platform == 'darwin' else 1024)
                medians = {v: statistics.median(values) for v, values in cpu.items()}
                results[key] = {'cpu_ms': cpu, 'wall_ms': wall, 'median_cpu_ms': medians,
                                'rss_mib': rss, 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                print(key, json.dumps(medians), flush=True)
                args.output.write_text(json.dumps({'method': __doc__, 'repeats': args.repeats,
                    'artifacts': str(directory), 'results': results, 'complete': False}, indent=2) + '\n')
    result = json.loads(args.output.read_text())
    result['complete'] = True
    result['versions'] = {v: {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
                          for v, paths in variants.items()}
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
