#!/usr/bin/env python3
"""Paired original/changed append timings, including ordinary growth control."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import shutil
import subprocess
import sys
import tempfile
from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments/memory'))
from measurement_stats import paired_cpu_ratio_summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before-runtime', type=Path, required=True)
    parser.add_argument('--after-runtime', type=Path, default=ROOT / 'runtime')
    parser.add_argument('--pairs', type=int, default=12)
    args = parser.parse_args()
    parent = ROOT / 'build/memory-research-list-reserve-bench'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent)).resolve()
    report = {'status': 'running', 'invocation': [sys.executable, *sys.argv],
              'host': platform.platform(), 'sources': [], 'checks': [], 'measurements': [],
              'limitations': 'Same-host C microbenchmarks. Includes copying. No latency or HFT guarantee. No samples discarded.'}

    def save():
        target = evidence / 'results.json'
        temporary = target.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(target)

    def execute(command):
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        report['checks'].append({'command': list(map(str, command)), 'returncode': result.returncode,
                                 'stdout': result.stdout, 'stderr': result.stderr})
        save()
        if result.returncode:
            raise RuntimeError(result.stderr)
        return result.stdout

    for variant, directory in [('before', args.before_runtime), ('after', args.after_runtime)]:
        target = evidence / variant / 'runtime'
        target.mkdir(parents=True)
        for source in directory.glob('minyar_*'):
            if source.is_file():
                data = source.read_bytes()
                (target / source.name).write_bytes(data)
                report['sources'].append({'source': str(source.resolve()), 'snapshot': str((target / source.name).relative_to(evidence)),
                                         'sha256': hashlib.sha256(data).hexdigest()})
    fixture = ROOT / 'tests/memory-research-list-reserve-bench.c'
    shutil.copyfile(fixture, evidence / fixture.name)
    report['sources'].append({'source': str(fixture), 'snapshot': fixture.name,
                             'sha256': hashlib.sha256(fixture.read_bytes()).hexdigest()})
    for source in [Path(__file__), ROOT / 'experiments/memory/measurement_stats.py']:
        shutil.copyfile(source, evidence / source.name)
    print(f'Evidence: {evidence}', flush=True)
    try:
        execute(['clang', '--version'])
        for profile, backend in [('system', ['-DMINYAR_SYSTEM_HEAP=1']), ('fixed', ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_BOUNDED_HEAP_BYTES=8388608'])]:
            binaries = {}
            for variant in ('before', 'after'):
                binary = evidence / f'{profile}-{variant}'
                runtime = evidence / variant / 'runtime/minyar_runtime.c'
                execute(clang_command(['clang', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', *backend,
                        f'-DMINYAR_RESEARCH_RUNTIME="{runtime}"', str(evidence / fixture.name), '-o', str(binary)]))
                binaries[variant] = binary
            for mode, length, iterations in [('append', 31, 200000), ('append', 1024, 10000),
                                              ('append', 8193, 1500), ('grow', 31, 200000)]:
                case = {'profile': profile, 'mode': mode, 'length': length, 'iterations': iterations, 'pairs': [], 'warmups': []}
                report['measurements'].append(case)
                arguments = [str(length), str(iterations), mode]
                for variant in ('before', 'after'):
                    case['warmups'].append({'variant': variant, 'observation': json.loads(execute([str(binaries[variant]), *arguments]))})
                generator = random.Random(20261004)
                for number in range(args.pairs):
                    order = ['before', 'after']
                    if generator.randrange(2):
                        order.reverse()
                    pair = {'order': order}
                    for variant in order:
                        pair[variant] = json.loads(execute([str(binaries[variant]), *arguments]))
                    expected = iterations * (iterations - 1) // 2 if mode == 'append' else iterations * (length - 1) * 37
                    assert pair['before']['checksum'] == pair['after']['checksum'] == expected
                    case['pairs'].append(pair)
                    save()
                case['cpu_before_over_after'] = paired_cpu_ratio_summary(
                    [p['before']['cpu_ns'] for p in case['pairs']], [p['after']['cpu_ns'] for p in case['pairs']])
                case['wall_before_over_after'] = paired_cpu_ratio_summary(
                    [p['before']['wall_ns'] for p in case['pairs']], [p['after']['wall_ns'] for p in case['pairs']])
                summary = case['cpu_before_over_after']
                print(f'{profile} {mode} length={length}: CPU before/after={summary["median"]:.3f}, CI={summary["confidence_interval"]["lower"]:.3f}..{summary["confidence_interval"]["upper"]:.3f}', flush=True)
        report['status'] = 'passed'
    except KeyboardInterrupt:
        report['status'] = 'interrupted'
        raise
    except Exception as error:
        report['status'] = 'failed'
        report['failure'] = str(error)
        raise
    finally:
        save()
        print(f'Results: {evidence / "results.json"}', flush=True)


if __name__ == '__main__':
    main()
