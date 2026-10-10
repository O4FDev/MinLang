#!/usr/bin/env python3
"""Exactly two deterministic reviewer-derived List/buddy correspondence cases."""
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parent = ROOT / 'build/memory-research-list-hand-cases'
    parent.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='run-', dir=parent))
    report = {'status': 'running', 'checks': [], 'sources': [],
              'scope': 'Two cases only; source-correspondence falsification, not universal proof.'}
    initial = {str(p): sha(p) for p in (ROOT / 'runtime').glob('minyar_*') if p.is_file()}
    fixture = ROOT / 'tests/memory-research-list-hand-cases.c'
    baseline = ROOT / 'research/2026-10-memory/evidence/runtime/core-production/baseline/minyar_collections.h'
    for variant in ('before', 'guarded'):
        target = out / variant / 'runtime'
        target.mkdir(parents=True)
        for path in (ROOT / 'runtime').glob('minyar_*'):
            if path.is_file():
                shutil.copyfile(path, target / path.name)
        if variant == 'before':
            shutil.copyfile(baseline, target / baseline.name)
        path = target / 'minyar_collections.h'
        text = path.read_text()
        marker = '    MinyarList *result = minyar_list_new();'
        assert text.count(marker) == 1
        observed = text.replace(marker, marker + '\n    hand_snapshot("post-header", list, result);')
        (out / (variant + '-observer.patch')).write_text(''.join(difflib.unified_diff(
            text.splitlines(True), observed.splitlines(True), fromfile='minyar_collections.h',
            tofile='observed/minyar_collections.h')))
        path.write_text(observed)
    for source in (fixture, Path(__file__).resolve(), ROOT / 'tests/clang_helpers.py'):
        shutil.copyfile(source, out / source.name)
    for path in out.rglob('*'):
        if path.is_file():
            report['sources'].append({'path': str(path.relative_to(out)), 'sha256': sha(path)})

    def save():
        (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    print('Evidence: ' + str(out), flush=True)
    save()
    try:
        runs = {}
        for profile, options in [('native', ['-O2']), ('sanitize', ['-O1', '-g',
                '-fsanitize=address,undefined', '-fno-omit-frame-pointer'])]:
            for variant in ('before', 'guarded'):
                binary = out / f'{profile}-{variant}'
                commands = [('compile', clang_command(['clang', *options, '-Wall', '-Wextra', '-Werror',
                    f'-DMINYAR_RESEARCH_RUNTIME="{out / variant / "runtime/minyar_runtime.c"}"',
                    str(out / fixture.name), '-o', str(binary)]))]
                commands += [(f'length{length}', [str(binary), str(length)]) for length in (3, 7)]
                for mode, command in commands:
                    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
                               UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
                    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=30)
                    name = f'{profile}-{variant}-{mode}'
                    (out / (name + '.stdout')).write_text(result.stdout)
                    (out / (name + '.stderr')).write_text(result.stderr)
                    report['checks'].append({'command': command, 'returncode': result.returncode,
                                             'stdout': name + '.stdout', 'stderr': name + '.stderr'})
                    save()
                    assert result.returncode == 0, (name, result.stderr)
                    if mode != 'compile':
                        runs[profile, variant, mode] = [json.loads(s) for s in result.stdout.splitlines()]
        comparisons = []
        for profile in ('native', 'sanitize'):
            for length in (3, 7):
                old, new = (runs[profile, variant, f'length{length}'] for variant in ('before', 'guarded'))
                assert len(old) == len(new)
                for a, b in zip(old, new):
                    assert {k: v for k, v in a.items() if k != 'telemetry'} == {
                        k: v for k, v in b.items() if k != 'telemetry'}, (profile, length, a, b)
                a, b = (next(r for r in rows if r.get('phase') == 'post-append') for rows in (old, new))
                assert a['telemetry']['high_water'] == (192 if length == 3 else 352)
                assert b['telemetry']['high_water'] == (160 if length == 3 else 288)
                assert a['telemetry']['allocations'] == (5 if length == 3 else 9)
                assert b['telemetry']['allocations'] == (4 if length == 3 else 7)
                comparisons.append({'profile': profile, 'length': length, 'observations': len(old),
                    'before_telemetry': a['telemetry'], 'guarded_telemetry': b['telemetry'],
                    'max_free_list_nodes': max(len(nodes) for r in old if 'decision' in r
                        for nodes in r['decision']['lists'])})
        report.update(status='passed', comparisons=comparisons,
                      production_hashes_unchanged=initial == {str(p): sha(p) for p in
                          (ROOT / 'runtime').glob('minyar_*') if p.is_file()})
        assert report['production_hashes_unchanged']
        print(json.dumps(comparisons), flush=True)
    except Exception as error:
        report.update(status='failed', failure=str(error))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
