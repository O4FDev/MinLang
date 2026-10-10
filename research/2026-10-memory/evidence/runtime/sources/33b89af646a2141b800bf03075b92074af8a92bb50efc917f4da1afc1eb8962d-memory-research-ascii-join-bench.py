#!/usr/bin/env python3
"""Randomized blocked CPU pairs for ASCII propagation and workload controls."""
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
    parser.add_argument('--pairs', type=int, default=12)
    args = parser.parse_args()
    assert args.pairs >= 4
    parent = ROOT / 'build/memory-research-ascii-join-bench'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent)).resolve()
    report = {'status': 'running', 'invocation': [sys.executable, *sys.argv],
              'host': platform.platform(), 'cpu_count': os.cpu_count(),
              'load_average_start': os.getloadavg(), 'sources': [], 'checks': [],
              'measurements': [], 'seed': 20261004,
              'scope': 'Uninstrumented system/K32 generated program, including construction, cleanup and three prints. '
                       'Process CPU is primary; wall measurements retain host noise. No samples discarded.',
              'decision_rule': 'A material negative-control regression is >3% median slowdown with a 95% paired '
                               'bootstrap interval excluding parity; broad intervals require more evidence.'}

    def copy(source, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        report['sources'].append({'source': str(source), 'snapshot': str(target.relative_to(evidence))})

    def save():
        for source in report['sources']:
            source['sha256'] = hashlib.sha256((evidence / source['snapshot']).read_bytes()).hexdigest()
        report['load_average_latest'] = os.getloadavg()
        temporary = evidence / 'results.json.tmp'
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(evidence / 'results.json')

    def execute(label, command):
        check = {'label': label, 'command': list(map(str, command))}
        try:
            result = subprocess.run(command, text=True, capture_output=True, timeout=60)
        except subprocess.TimeoutExpired as error:
            check.update(returncode=None, timed_out=True, timeout_seconds=60,
                         stdout=str(error.stdout), stderr=str(error.stderr))
            report['checks'].append(check)
            save()
            raise
        check.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
        report['checks'].append(check)
        save()
        assert result.returncode == 0, (label, result.stdout, result.stderr)
        return result

    copy(ROOT / 'build/minyarc', evidence / 'minyarc')
    for source in (Path(__file__), ROOT / 'tests/memory-research-ascii-join.min',
                   ROOT / 'tests/memory-research-ascii-join-bench.c', ROOT / 'tests/clang_helpers.py',
                   ROOT / 'experiments/memory/measurement_stats.py'):
        copy(source, evidence / 'tests' / source.name)
    for variant in ('before', 'candidate'):
        for source in (ROOT / 'runtime').glob('minyar_*'):
            if source.is_file():
                copy(source, evidence / variant / 'runtime' / source.name)
        copy(ROOT / 'tests/memory-research-ascii-join-bench.c',
             evidence / variant / 'tests/memory-research-ascii-join-bench.c')
    candidate = evidence / 'candidate/runtime/minyar_runtime.c'
    text = candidate.read_text()
    begin = text.index('static MinyarText *join_by_copying(')
    end = text.index('\nMinyarText *minyar_join_text(', begin)
    fragment = text[begin:end]
    old = '    return new_text(bytes, length, -1);'
    new = '''    long long characters =
        left->character_length == left->byte_length && right->character_length == right->byte_length
            ? length : -1;
    return new_text(bytes, length, characters);'''
    assert fragment.count(old) == 1
    candidate.write_text(text[:begin] + fragment.replace(old, new) + text[end:])
    report['candidate'] = {'old': old, 'new': new}
    source = evidence / 'tests/memory-research-ascii-join.min'
    text = source.read_text()
    old = 'while iteration < 128 {'
    new = '''let repetitions = 4096
if mode == "short" { repetitions = 262144 }
if mode == "unicode" { repetitions = 16384 }
while iteration < repetitions {'''
    assert text.count(old) == 1
    source.write_text(text.replace(old, new))
    cases = {'known': (65536, 4096, 65537), 'unknown': (0, 4096, 65537),
             'no-query': (65536, 4096, 65537), 'short': (8, 262144, 9),
             'unicode': (256, 16384, 257)}
    case_records = {mode: {'mode': mode, 'repetitions': counts[1], 'pairs': [], 'warmups': []}
                    for mode, counts in cases.items()}
    report['measurements'] = list(case_records.values())

    def observe(variant, mode, label):
        result = execute(label, [str(evidence / (variant + '-language')), mode, ''])
        initial, repetitions, length = cases[mode]
        byte_length = 768 if mode == 'unicode' else 8 if mode == 'short' else 65536
        assert result.stdout == f'{initial}\n{repetitions * length}\n{byte_length}\n'
        return json.loads(result.stderr)

    print(f'Evidence: {evidence}', flush=True)
    try:
        execute('clang-version', ['clang', '--version'])
        llvm = evidence / 'generated.ll'
        execute('language-compile', [str(evidence / 'minyarc'), str(source), str(llvm)])
        assert llvm.read_text().count('call ptr @minyar_join_text(') >= 2
        report['generated_sha256'] = hashlib.sha256(llvm.read_bytes()).hexdigest()
        for variant in ('before', 'candidate'):
            execute(variant + '-link', clang_command(['clang', '-O2', '-Wno-override-module',
                    '-DMINYAR_SYSTEM_HEAP=1', '-DMINYAR_RC_POLL_BUDGET=32', str(llvm),
                    str(evidence / variant / 'tests/memory-research-ascii-join-bench.c'),
                    '-o', str(evidence / (variant + '-language'))]))
        generator = random.Random(report['seed'])
        for mode, case in case_records.items():
            for variant in ('before', 'candidate'):
                case['warmups'].append({'variant': variant, 'observation': observe(variant, mode, 'warmup-' + variant + '-' + mode)})
        for block in range(args.pairs):
            modes = list(cases)
            generator.shuffle(modes)
            for mode in modes:
                order = ['before', 'candidate']
                generator.shuffle(order)
                pair = {'block': block, 'mode_order': modes, 'order': order}
                for variant in order:
                    pair[variant] = observe(variant, mode, f'block{block}-{mode}-{variant}')
                case_records[mode]['pairs'].append(pair)
                save()
        for mode, case in case_records.items():
            for clock in ('cpu', 'wall'):
                case[clock + '_before_over_candidate'] = paired_cpu_ratio_summary(
                    [pair['before'][clock + '_ns'] for pair in case['pairs']],
                    [pair['candidate'][clock + '_ns'] for pair in case['pairs']])
            summary = case['cpu_before_over_candidate']
            print(f'{mode}: CPU before/candidate={summary["median"]:.3f}, '
                  f'CI={summary["confidence_interval"]["lower"]:.3f}..{summary["confidence_interval"]["upper"]:.3f}', flush=True)
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
