#!/usr/bin/env python3
"""Tiny closed Text/frame cohort, including the automatic leave-poll work."""
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
    parent = ROOT / 'build/memory-research-text-owner-demand'
    parent.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='run-', dir=parent))
    report = {'status': 'running', 'checks': [], 'observations': {}, 'sources': [],
              'scope': 'Two owner orders, actual automatic leave and explicit polls; not a general certificate implementation.'}
    initial = {str(p): sha(p) for p in (ROOT / 'runtime').glob('minyar_*') if p.is_file()}
    runtime = out / 'runtime'
    runtime.mkdir()
    for source in (ROOT / 'runtime').glob('minyar_*'):
        if source.is_file():
            shutil.copyfile(source, runtime / source.name)
    header = runtime / 'minyar_bounded_rc.h'
    original = header.read_text()
    marker = 'static void *rc_bounded_finish_object(RcObject *object, unsigned kind) {'
    assert original.count(marker) == 1
    observed = original.replace(marker, marker + '\n    demand_destroy(object, kind);')
    (out / 'destruction-observer.patch').write_text(''.join(difflib.unified_diff(
        original.splitlines(True), observed.splitlines(True), fromfile='minyar_bounded_rc.h',
        tofile='observed/minyar_bounded_rc.h')))
    header.write_text(observed)
    fixture = ROOT / 'tests/memory-research-text-owner-demand.c'
    for source in (fixture, Path(__file__).resolve(), ROOT / 'tests/clang_helpers.py'):
        shutil.copyfile(source, out / source.name)
    for p in out.rglob('*'):
        if p.is_file():
            report['sources'].append({'path': str(p.relative_to(out)), 'sha256': sha(p)})

    def save():
        (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    def command(label, argv, expected=0):
        result = subprocess.run(argv, capture_output=True, text=True, timeout=30, env=dict(
            os.environ, ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
            UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1'))
        (out / (label + '.stdout')).write_text(result.stdout)
        (out / (label + '.stderr')).write_text(result.stderr)
        report['checks'].append({'label': label, 'command': argv, 'returncode': result.returncode,
                                'expected_returncode': expected, 'stdout': label + '.stdout',
                                'stderr': label + '.stderr'})
        save()
        assert result.returncode == expected, (label, result.stderr)
        return result

    print('Evidence: ' + str(out), flush=True)
    save()
    try:
        for profile, flags, mutant in [('observer-red', ['-O2'], True), ('native', ['-O2'], False),
                ('sanitize', ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer'], False)]:
            binary = out / profile
            definitions = ['-DMINYAR_RESEARCH_OMIT_LEAVE_WORK=1'] if mutant else []
            command(profile + '-compile', clang_command(['clang', *flags, '-Wall', '-Wextra', '-Werror',
                *definitions, f'-DMINYAR_RESEARCH_RUNTIME="{runtime / "minyar_runtime.c"}"',
                str(out / fixture.name), '-o', str(binary)]))
            for order in ((0,) if mutant else (0, 1)):
                label = profile + f'-order{order}'
                result = command(label, [str(binary), str(order)], 70 if mutant else 0)
                rows = [json.loads(line) for line in result.stdout.splitlines()]
                if mutant:
                    assert result.stderr.strip() == ('Demand observer assertion: '
                        'include automatic leave work in total3/4')
                    assert rows[-1]['summed_work'] == 2 and rows[-1]['heap_allocations'] == 0
                else:
                    assert rows[-1]['summed_work'] == (4 if order else 3)
                    assert [row['pending'] for row in rows[1:-1]] == ([1, 2, 1, 0] if order else [1, 1, 0])
                    assert [row['objects'] for row in rows[1:-1]] == ([2, 1, 0, 0] if order else [1, 0, 0])
                    assert [row['remaining_frame_slots'] for row in rows[1:-1]] == ([1, 0, 0, 0] if order else [1, 0, 0])
                    assert rows[-1]['requested'] == rows[-1]['objects'] == rows[-1]['heap_allocations'] == 0
                report['observations'][label] = rows
                save()
        for order in (0, 1):
            assert report['observations'][f'native-order{order}'] == report['observations'][f'sanitize-order{order}']
        report.update(status='passed', source_hashes_unchanged=initial == {str(p): sha(p) for p in
            (ROOT / 'runtime').glob('minyar_*') if p.is_file()},
            conclusion='Observed total3/4 with automatic leave counted; omit-leave observer rejected after exact recovery.')
        assert report['source_hashes_unchanged']
        print(report['conclusion'], flush=True)
    except Exception as error:
        report.update(status='failed', failure=str(error))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
