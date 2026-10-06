#!/usr/bin/env python3
"""Check frozen archive/source/binary identities; no fixture execution."""
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUT = HERE / 'inputs'
BASE = Path('research/2026-10-memory/evidence')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    return json.loads((INPUT / p).read_text())


def main():
    report = {'archives': [], 'timing_artifacts': [], 'comparisons': []}
    for run in ['runtime-aggregate-timing/run-rrkuiyad', 'runtime-aggregate/run-ltiaucr9', 'runtime-aggregate/run-z4ozpuwj']:
        root = BASE / run
        index = read(root / 'archive-index.json')
        for row in index['files']:
            assert sha(INPUT / root / row['path']) == row['sha256'], row
        report['archives'].append({'run': run, 'all_hashes_match': True, 'entries': len(index['files'])})
    runs = [('ascii', 'memory-research-ascii-join-bench/run-603xbkqt', 'runtime/results/ascii-paired-timing.json', 'candidate'),
            ('list', 'memory-research-list-reserve-bench/run-9t0lgm8s', 'runtime/results/final-list-timing.json', 'after'),
            ('aggregate', 'memory-research-aggregate-timing/run-rrkuiyad', 'runtime-aggregate-timing/run-rrkuiyad/results.json', 'candidate')]
    for name, original, raw, variant in runs:
        root = INPUT / 'build' / original
        d = read(BASE / raw)
        assert sha(root / 'results.json') == sha(INPUT / BASE / raw)
        for source in d['sources']:
            assert sha(root / source['snapshot']) == source['sha256'], source
        artifact = {'family': name, 'raw_build_and_durable_equal': True, 'source_hashes_verified': len(d['sources']),
                    'binaries': []}
        if name != 'list':
            expected_compiler = d.get('compiler_sha256') or next(s['sha256'] for s in d['sources'] if s['snapshot'] == 'minyarc')
            assert sha(root / 'minyarc') == expected_compiler
            llvm = root / ('program.ll' if name == 'aggregate' else 'generated.ll')
            assert sha(llvm) == d.get('generated_llvm_sha256', d.get('generated_sha256'))
            artifact.update(compiler_sha256=expected_compiler, generated_llvm_sha256=sha(llvm))
        binary_paths = ['before/program', 'candidate/program'] if name == 'aggregate' else ['before-language', 'candidate-language'] if name == 'ascii' else ['system-before','system-after','fixed-before','fixed-after']
        for path in binary_paths:
            h = sha(root / path)
            if name == 'aggregate':
                assert h == next(b['sha256'] for b in d['binaries'] if b['snapshot'] == path)
            artifact['binaries'].append({'snapshot': path, 'sha256': h,
                                        'hash_matches_acquisition_record': True if name == 'aggregate' else None})
        report['timing_artifacts'].append(artifact)
        changes = []
        for before in sorted((root/'before/runtime').glob('*')):
            after = root / variant / 'runtime' / before.name
            if not after.exists() or before.read_bytes() == after.read_bytes():
                continue
            diff = ''.join(difflib.unified_diff(before.read_text().splitlines(True), after.read_text().splitlines(True),
                                                fromfile='before/' + before.name, tofile=variant + '/' + before.name))
            target = HERE / 'source-diffs' / f'{name}-{before.name}.patch'
            target.parent.mkdir(exist_ok=True)
            target.write_text(diff)
            changes.append({'file': before.name, 'before_sha256': sha(before), 'candidate_sha256': sha(after),
                            'diff': str(target.relative_to(HERE)), 'diff_sha256': sha(target)})
        report['comparisons'].append({'family': name, 'changed_runtime_files': changes,
                                      'added_runtime_files': sorted(p.name for p in (root/variant/'runtime').glob('*') if not (root/'before/runtime'/p.name).exists())})
    aggregate = INPUT / BASE / 'runtime-aggregate-timing/run-rrkuiyad'
    before = aggregate/'before/runtime/minyar_runtime.c'
    candidate = aggregate/'candidate/runtime/minyar_runtime.c'
    diff = ''.join(difflib.unified_diff(before.read_text().splitlines(True), candidate.read_text().splitlines(True),
                                       fromfile='a/runtime/minyar_runtime.c', tofile='b/runtime/minyar_runtime.c'))
    assert diff == (aggregate/'candidate.patch').read_text()
    assert sha(before) == sha(INPUT / 'runtime/minyar_runtime.c') == 'c4e78f59096e0af8926c8d06febb9277e8c7cb7e5de8fc63b907d3afb613fcb4'
    assert sha(candidate) == 'd919f066a0e71c80cb079a22659928541e958b68b81a645d7631f52ec8531a51'
    report['aggregate_exact_diff_and_unapplied_at_checkpoint'] = True
    report['aggregate_patch_sha256'] = sha(aggregate/'candidate.patch')
    # Figure metadata's original build input paths match durable raw bytes.
    figure = read(Path('research/2026-10-memory/runtime-timing-figures.json'))
    report['figure_input_hashes_verified'] = all(sha(INPUT / row['path']) == row['sha256'] for row in figure['inputs'])
    assert report['figure_input_hashes_verified']
    figure_checks = []
    campaign = Path('research/2026-10-memory')
    assert sha(INPUT / campaign / 'runtime-timing-figures.py') == figure['generator_sha256']
    for row in figure['outputs']:
        assert sha(INPUT / row['path']) == row['sha256']
        figure_checks.append(row['path'])
    aggregate_figure = read(campaign / 'runtime-aggregate-figure.json')
    assert sha(INPUT / campaign / 'runtime-aggregate-figure.py') == aggregate_figure['generator_sha256']
    assert sha(INPUT / campaign / aggregate_figure['input']) == aggregate_figure['input_sha256']
    for row in aggregate_figure['outputs']:
        assert sha(INPUT / campaign / row['path']) == row['sha256']
        figure_checks.append(str(campaign / row['path']))
    report['figure_generators_and_exports_verified'] = figure_checks
    (HERE/'artifact-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Verified archives:', [(x['run'],x['entries']) for x in report['archives']])
    print('Timing source/LLVM/compiler hashes and aggregate recorded binaries match; original ASCII/List binaries newly pinned, without original binary hash records.')
    print('Exact aggregate patch verified and unapplied at checkpoint.')


if __name__ == '__main__':
    main()
