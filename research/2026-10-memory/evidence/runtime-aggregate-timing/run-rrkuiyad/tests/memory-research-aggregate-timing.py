#!/usr/bin/env python3
"""Preregistered isolated aggregate-join CPU pairs; production stays frozen."""
import difflib
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import shutil
import subprocess
import tempfile

from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]
SEED = 681492


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def interval(pairs, clock):
    logs = [math.log(pair['before'][clock] / pair['candidate'][clock]) for pair in pairs]
    generator = random.Random(SEED)
    samples = sorted(math.exp(sum(generator.choices(logs, k=len(logs))) / len(logs))
                     for _ in range(10000))
    return {'geometric_mean': math.exp(sum(logs) / len(logs)),
            'lower': samples[249], 'upper': samples[9749],
            'individual_ratios': [math.exp(value) for value in logs],
            'method': 'Paired-block bootstrap of mean log ratio,10000 seeded resamples,95% interval.'}


def main():
    parent = ROOT / 'build/memory-research-aggregate-timing'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent)).resolve()
    report = {'status': 'running', 'seed': SEED, 'sources': [], 'checks': [], 'measurements': [],
              'host': platform.platform(), 'cpu_count': os.cpu_count(), 'load_start': os.getloadavg(),
              'preregistered': json.loads((ROOT / 'research/2026-10-memory/runtime-aggregate-timing-preregister.json').read_text()),
              'scope': 'Uninstrumented generated system/K32/O2 construction, repeated joins, cleanup and output. '
                       'Core paced soak and external host jobs can contaminate CPU/wall observations. '
                       'No quiet-window, whole-compiler speedup or per-operation latency claim. No discarded rows.'}

    def copy(source, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        report['sources'].append({'snapshot': str(target.relative_to(evidence)), 'sha256': sha(target)})

    def save():
        report['load_latest'] = os.getloadavg()
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    def execute(label, argv):
        row = {'label': label, 'argv': list(map(str, argv))}
        try:
            result = subprocess.run(argv, text=True, capture_output=True, timeout=30)
        except subprocess.TimeoutExpired as error:
            row.update(returncode=None, timeout=30, stdout=str(error.stdout), stderr=str(error.stderr))
            report['checks'].append(row)
            save()
            raise
        row.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
        report['checks'].append(row)
        save()
        assert result.returncode == 0, (label, result.stderr)
        return result

    compiler = evidence / 'minyarc'
    shutil.copy2(ROOT / 'build/minyarc', compiler)
    report['compiler_sha256'] = sha(compiler)
    for source in [Path(__file__), ROOT / 'tests/memory-research-aggregate-timing.min',
                   ROOT / 'tests/memory-research-aggregate-timing.c', ROOT / 'tests/clang_helpers.py',
                   ROOT / 'research/2026-10-memory/runtime-aggregate-timing-preregister.json']:
        copy(source, evidence / 'tests' / source.name)
    for variant in ['before', 'candidate']:
        for source in (ROOT / 'runtime').glob('minyar_*'):
            if source.is_file():
                copy(source, evidence / variant / 'runtime' / source.name)
        copy(ROOT / 'tests/memory-research-aggregate-timing.c',
             evidence / variant / 'tests/memory-research-aggregate-timing.c')
    candidate = evidence / 'candidate/runtime/minyar_runtime.c'
    assert sha(candidate) == report['preregistered']['runtime_sha256']
    patch = ROOT / 'research/2026-10-memory' / report['preregistered']['candidate_source']
    copy(patch, evidence / 'candidate.patch')
    applied = subprocess.run(['patch', '-s', '-p2', '-d', str(candidate.parent)],
                             input=patch.read_text(), text=True, capture_output=True, timeout=10)
    assert applied.returncode == 0, applied.stderr
    before = (evidence / 'before/runtime/minyar_runtime.c').read_text()
    after = candidate.read_text()
    assert ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                fromfile='a/runtime/minyar_runtime.c', tofile='b/runtime/minyar_runtime.c')) == patch.read_text()
    for source in report['sources']:
        if source['snapshot'] == 'candidate/runtime/minyar_runtime.c':
            source['pre_candidate_sha256'] = source['sha256']
            source['sha256'] = sha(candidate)
    raw_inputs = {
        'known': 'x' * 2040 + r'\n' + 'y' * 2048 + r'\t' + 'z' * 6,
        'short': r'left\ncenter\tend',
        'unknown': 'x' * 2040 + r'\n' + 'y' * 2048 + r'\t' + 'z' * 2,
        'unicode': 'é' * 1020 + r'\n' + '🙂' * 510 + r'\t' + 'é' * 7}
    raw_inputs['no-query'] = raw_inputs['known']
    cases = {}
    for mode, raw in raw_inputs.items():
        path = evidence / (mode + '.txt')
        path.write_text(raw)
        value = raw.replace(r'\n', '\n').replace(r'\t', '\t')
        if mode == 'unknown':
            value += 'tail'
        assert len(value.encode()) == (15 if mode == 'short' else 4096)
        cases[mode] = {'mode': mode, 'input': path, 'value': value, 'pairs': [], 'warmups': []}
    opaque = evidence / 'opaque.txt'
    opaque.write_text('tail')
    print('Evidence: ' + str(evidence), flush=True)
    try:
        execute('toolchain', ['clang', '--version'])
        llvm = evidence / 'program.ll'
        execute('compile-language', [str(compiler), str(evidence / 'tests/memory-research-aggregate-timing.min'), str(llvm)])
        assert llvm.read_text().count('call ptr @minyar_join_texts(') == 1
        report['generated_llvm_sha256'] = sha(llvm)
        report['binaries'] = []
        for variant in ['before', 'candidate']:
            binary = evidence / variant / 'program'
            execute(variant + '-link', clang_command(['clang', '-O2', '-DMINYAR_SYSTEM_HEAP=1',
                    '-DMINYAR_RC_POLL_BUDGET=32', '-Wno-override-module', str(llvm),
                    str(evidence / variant / 'tests/memory-research-aggregate-timing.c'), '-o', str(binary)]))
            report['binaries'].append({'variant': variant, 'snapshot': str(binary.relative_to(evidence)), 'sha256': sha(binary)})

        def observe(variant, case, loops, label):
            result = execute(label, [str(evidence / variant / 'program'), case['mode'], str(loops),
                                    str(case['input']), str(opaque)])
            value = case['value']
            unit = len(value.encode()) if case['mode'] == 'no-query' else len(value)
            assert result.stdout == f'{unit * loops}\n{len(value.encode())}\n{value}\ntrue\n'
            row = json.loads(result.stderr)
            assert row['cpu_ns'] > 0 and row['wall_ns'] > 0
            return row

        for mode, case in cases.items():
            loops = 4096
            pilot = observe('before', case, loops, 'pilot-' + mode)
            repetitions = max(1, min(1000000, round(loops * 200000000 / pilot['cpu_ns'])))
            case['repetitions'] = repetitions
            case['pilot'] = {'loops': loops, 'observation': pilot,
                             'target_ns': 200000000, 'capped': repetitions == 1000000}
            print('Calibrated ' + mode + ': ' + str(repetitions) + ' loops', flush=True)
        report['measurements'] = [{key: value for key, value in case.items() if key not in ('input', 'value')}
                                  for case in cases.values()]
        # Freeze every source/compiler/binary hash before observations.
        frozen = {str(evidence / row['snapshot']): row['sha256']
                  for row in [*report['sources'], *report['binaries']]}
        frozen[str(compiler)] = report['compiler_sha256']
        assert all(sha(Path(path)) == digest for path, digest in frozen.items())
        for case in cases.values():
            for variant in ['before', 'candidate']:
                case['warmups'].append({'variant': variant,
                    'observation': observe(variant, case, case['repetitions'], 'warmup-' + variant + '-' + case['mode'])})
        generator = random.Random(SEED)
        for block in range(12):
            modes = list(cases)
            generator.shuffle(modes)
            for mode in modes:
                case = cases[mode]
                order = ['before', 'candidate']
                generator.shuffle(order)
                pair = {'block': block, 'mode_order': modes, 'order': order}
                for variant in order:
                    pair[variant] = observe(variant, case, case['repetitions'],
                                            f'block{block}-{mode}-{variant}')
                case['pairs'].append(pair)
                report['measurements'] = [{key: value for key, value in item.items()
                                           if key not in ('input', 'value')} for item in cases.values()]
                save()
            print('Finished block ' + str(block + 1) + '/12', flush=True)
        for measurement in report['measurements']:
            for clock in ['cpu_ns', 'wall_ns']:
                measurement[clock + '_before_over_candidate'] = interval(measurement['pairs'], clock)
            ratio = measurement['cpu_ns_before_over_candidate']
            threshold = 1.03 if measurement['mode'] == 'no-query' else 1.05
            measurement['supported_negative_over_threshold'] = (measurement['mode'] != 'known'
                                                                 and ratio['upper'] < 1 / threshold)
            print(measurement['mode'] + ': ' + json.dumps(ratio), flush=True)
        known = report['measurements'][0]['cpu_ns_before_over_candidate']
        report['decision'] = {
            'known_positive_criterion_met': known['geometric_mean'] > 1.03 and known['lower'] > 1,
            'rejected_by_control': [case['mode'] for case in report['measurements']
                                    if case['supported_negative_over_threshold']],
            'production_adoption': False,
            'scope': 'Timing criteria only; independent review and sustained source freezes remain prerequisites.'}
        report['immutable_hashes_match_after'] = all(sha(Path(path)) == digest for path, digest in frozen.items())
        assert report['immutable_hashes_match_after']
        assert all(len(case['pairs']) == 12 for case in report['measurements'])
        report['status'] = 'passed'
    except BaseException as error:
        report.update(status='failed', failure=repr(error))
        raise
    finally:
        save()
        print('Results: ' + str(evidence / 'results.json'), flush=True)


if __name__ == '__main__':
    main()
