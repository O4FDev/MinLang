#!/usr/bin/env python3
"""Retain exact PNG file-open failures and source/format checks without new builds."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--matrix', required=True, type=Path)
    parser.add_argument('--label', required=True)
    args = parser.parse_args()
    matrix_path = args.matrix.resolve()
    matrix = json.loads(matrix_path.read_text())
    assert matrix['status'] == 'passed'
    evidence = ROOT / 'research/2026-10-memory/evidence/native-application-round2' / args.label
    evidence.mkdir(parents=True, exist_ok=False)
    report = {'status': 'running', 'matrix_sha256': digest(matrix_path), 'commands': [], 'contracts': [],
              'source_hashes': [], 'source_unchanged_from_final_matrix': [],
              'scope': 'Additional native file-open contracts and routine source verification; no matrix recount.',
              'sanitizers': matrix['sanitizers']}
    environment = {**os.environ, **{key: value for key, value in matrix['sanitizers'].items() if key.endswith('_OPTIONS')}}
    (evidence / Path(__file__).name).write_bytes(Path(__file__).read_bytes())

    def save():
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    def run(label, command):
        row = {'label': label, 'command': [str(item) for item in command], 'cwd': str(ROOT)}
        report['commands'].append(row)
        result = subprocess.run(row['command'], cwd=ROOT, env=environment, text=True, capture_output=True, timeout=30)
        row.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
        save()
        return result

    for name, binary in matrix['binaries'].items():
        missing = Path(matrix['work']) / (name + '-no-parent') / 'screenshot.png'
        assert not missing.parent.exists()
        result = run(name + '-png-open-failure', [binary, 'png-retry', missing, 0])
        row = {'label': name + '-png-open-failure', 'passed': False}
        report['contracts'].append(row)
        try:
            assert result.returncode == 1 and result.stderr == 'Minyar stopped: the screenshot file could not be created.\n'
            stats = json.loads(result.stdout)
            assert stats['malloc_calls'] == 3 and stats['allocated_bytes'] == stats['peak_bytes'] == stats['live_bytes_at_exit'] == 667
            assert stats['pending'] == 1 and stats['read_calls'] == stats['open_calls'] == 1
            assert stats['write_calls'] == stats['close_calls'] == 0 and not missing.exists()
            row.update(passed=True, evidence=stats)
        except (AssertionError, ValueError) as error:
            row['error'] = repr(error)
        save()
    formatter = Path('/Users/luke/.cache/uv/archive-v0/qir4EsQDYRgTcgFN/clang_format/data/bin/clang-format')
    report['formatter_sha256'] = digest(formatter)
    assert run('formatter-version', [formatter, '--version']).returncode == 0
    assert run('formatter-owned-c', [formatter, '--dry-run', '--Werror', ROOT / 'tests/native-research-round2.c']).returncode == 0
    owned = sorted((ROOT / 'tests').glob('native-research-round2*'))
    owned = [path for path in owned if path.is_file()]
    assert run('python-syntax', ['python3', '-m', 'py_compile', *[path for path in owned if path.suffix == '.py']]).returncode == 0
    assert run('git-diff-whitespace', ['git', 'diff', '--check']).returncode == 0
    for path in owned:
        report['source_hashes'].append({'path': str(path.relative_to(ROOT)), 'sha256': digest(path)})
    for row in matrix['sources']:
        current = digest(ROOT / row['path'])
        report['source_unchanged_from_final_matrix'].append({'path': row['path'], 'sha256': current,
                                                            'unchanged': current == row['sha256']})
    assert all(row['unchanged'] for row in report['source_unchanged_from_final_matrix'])
    report.update(status='passed' if all(row['passed'] for row in report['contracts']) else 'failed',
                  contracts_passed=sum(row['passed'] for row in report['contracts']))
    save()
    print(json.dumps({'status': report['status'], 'contracts': len(report['contracts']), 'results': str(evidence / 'results.json')}, indent=2))
    return int(report['status'] != 'passed')


if __name__ == '__main__':
    raise SystemExit(main())
