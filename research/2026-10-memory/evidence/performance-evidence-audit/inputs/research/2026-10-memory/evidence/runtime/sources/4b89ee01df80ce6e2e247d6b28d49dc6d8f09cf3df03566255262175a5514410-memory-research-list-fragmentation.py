#!/usr/bin/env python3
"""Bounded original/guarded queue-empty buddy-placement differential."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before-runtime', type=Path, required=True)
    parser.add_argument('--seeds', type=int, default=16384)
    args = parser.parse_args()
    if not 1 <= args.seeds <= 16384:
        parser.error('--seeds must be 1 through 16384')
    parent = ROOT / 'build/memory-research-list-fragmentation'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent)).resolve()
    report = {'status': 'running', 'checks': [], 'sources': [],
              'scope': 'Queue-empty finite-pool search; no universal admission theorem or timing claim.'}
    for variant, source in [('before', args.before_runtime), ('guarded', ROOT / 'runtime'),
                             ('tests', ROOT / 'tests')]:
        names = list(source.glob('minyar_*')) if variant != 'tests' else [
            source / Path(__file__).name, source / 'memory-research-list-fragmentation.c',
            source / 'clang_helpers.py']
        for path in names:
            if path.is_file():
                target = evidence / variant / ('runtime' if variant != 'tests' else '') / path.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
                report['sources'].append({'source': str(path.resolve()), 'snapshot': str(target.relative_to(evidence)),
                                          'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})

    def save():
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    print('Evidence: ' + str(evidence), flush=True)
    try:
        rows = {}
        for variant in ('before', 'guarded'):
            binary = evidence / variant / 'search'
            commands = [clang_command(['clang', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-DMINYAR_RC_POLL_BUDGET=32',
                        f'-DMINYAR_RESEARCH_RUNTIME="{evidence / variant / "runtime/minyar_runtime.c"}"',
                        str(evidence / 'tests/memory-research-list-fragmentation.c'), '-o', str(binary)]),
                        [str(binary), '1', str(args.seeds)]]
            for index, command in enumerate(commands):
                result = subprocess.run(command, capture_output=True, text=True, timeout=90)
                output = variant + ('-compile.log' if index == 0 else '.jsonl')
                (evidence / output).write_text(result.stdout)
                report['checks'].append({'command': command, 'returncode': result.returncode,
                                         'stdout': output, 'stderr': result.stderr})
                save()
                assert result.returncode == 0, (variant, result.stderr)
            rows[variant] = [json.loads(line) for line in (evidence / (variant + '.jsonl')).read_text().splitlines()]
        assert len(rows['before']) == len(rows['guarded']) == args.seeds
        differences = []
        for old, new in zip(rows['before'], rows['guarded']):
            for key in ('seed', 'length', 'initial_hash', 'admitted'):
                assert old[key] == new[key], (key, old, new)
            if old['accepted'] != new['accepted'] or old['result_offset'] != new['result_offset']:
                differences.append({'before': old, 'guarded': new})
        report.update(status='passed', differences=differences, summary={
            'seeds': args.seeds, 'admitted': sum(row['admitted'] for row in rows['before']),
            'append_lengths': sorted({row['length'] for row in rows['before']}),
            'placement_differences': sum(d['before']['result_offset'] != d['guarded']['result_offset'] for d in differences),
            'admission_differences': sum(d['before']['accepted'] != d['guarded']['accepted'] for d in differences)})
        print(json.dumps(report['summary']), flush=True)
    except Exception as error:
        report.update(status='failed', failure=str(error))
        raise
    finally:
        save()
        print('Results: ' + str(evidence / 'results.json'), flush=True)


if __name__ == '__main__':
    main()
