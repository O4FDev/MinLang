#!/usr/bin/env python3
"""Bounded isolated bulk-copy pressure/admission/error comparisons; no timing."""
import argparse
import difflib
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import subprocess
import tempfile
from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bulk', ROOT / 'tests/memory-research-list-bulk.py')
bulk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bulk)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-dir', type=Path, default=ROOT / 'runtime')
    parser.add_argument('--candidate-dir', type=Path)
    args = parser.parse_args()
    parent = ROOT / 'build/memory-research-list-bulk-pressure'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent))
    report = {'status': 'running', 'checks': [], 'comparisons': [], 'sources': [],
              'scope': 'Complete observed finite-pool continuation and managed event equality; no timing.'}
    frozen = {str(p): bulk.digest(p) for p in (ROOT / 'runtime').glob('minyar_*') if p.is_file()}
    prelude = (ROOT / 'tests/memory-research-list-bulk.c').read_text().split('#undef memcpy')[0]
    names = ['memory-research-list-debt-pressure.c', 'memory-research-list-owner-debt.c',
             'memory-research-list-reserve.c', 'memory-research-list-bulk-pressure.h',
             'memory-research-list-bulk.py', 'memory-research-list-bulk.c',
             Path(__file__).name, 'clang_helpers.py']
    original = evidence / 'original'
    shutil.copytree(args.baseline_dir, original / 'runtime', ignore=shutil.ignore_patterns('native'))
    (original / 'tests').mkdir()
    for name in names:
        shutil.copyfile(ROOT / 'tests' / name, original / 'tests' / name)
    shutil.copyfile(ROOT / 'research/2026-10-memory/runtime-list-bulk-pressure-preregister.json',
                    evidence / 'preregister.json')
    environment = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1',
                   'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}

    def save():
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    def limits():
        os.setsid()
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
        resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))

    def execute(label, command, expected=0, native=False, idle=False):
        env = dict(environment)
        env.pop('MINYAR_RESEARCH_CLEAR_DEBT', None)
        if idle:
            env['MINYAR_RESEARCH_CLEAR_DEBT'] = '1'
        wrapped = ['/usr/bin/time', '-l', '/usr/sbin/taskpolicy', '-m', '128', *command] if native else command
        process = subprocess.Popen(wrapped, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, env=env, preexec_fn=limits)
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
        row = {'label': label, 'command': wrapped, 'returncode': process.returncode,
               'stdout': stdout, 'stderr': stderr, 'timed_out': timed_out, 'clear_debt': idle}
        if native:
            peak = re.search(r'(\d+)\s+maximum resident set size', stderr)
            row['peak_rss_bytes'] = int(peak.group(1)) if peak else None
        report['checks'].append(row)
        save()
        assert not timed_out and process.returncode == expected, row
        if native:
            assert row['peak_rss_bytes'] is not None and row['peak_rss_bytes'] <= 128 * 1024 * 1024, row
        row['observations'] = [json.loads(line) for line in stdout.splitlines() if line.startswith('{')]
        save()
        return row

    try:
        execute('toolchain', ['clang', '--version'])
        for variant in ['baseline', 'candidate']:
            directory = evidence / variant
            shutil.copytree(original, directory)
            if variant == 'candidate':
                if args.candidate_dir:
                    shutil.rmtree(directory / 'runtime')
                    shutil.copytree(args.candidate_dir, directory / 'runtime', ignore=shutil.ignore_patterns('native'))
                    bulk.verify_candidate(directory / 'runtime')
                else:
                    bulk.candidate(directory / 'runtime')
            bulk.instrument(directory / 'runtime')
            for name in names[:3]:
                path = directory / 'tests' / name
                before = path.read_text()
                text = before
                include = '#include MINYAR_RESEARCH_RUNTIME' if name != names[2] else '#include "../runtime/minyar_runtime.c"'
                text = bulk.replace_once(text, include, '#undef memcpy\n#define memcpy research_copy\n' + include +
                                         '\n#undef memcpy\n#include "memory-research-list-bulk-pressure.h"')
                if name != names[2]:
                    needle = '    MinyarList *result = minyar_list_appended(source, 313, 0, 0);'
                    text = bulk.replace_once(text, needle, '''    if (getenv("MINYAR_RESEARCH_CLEAR_DEBT"))
        while (rc_pending_count) assert(minyar_rc_poll(1) == 1);
    research_begin();
''' + needle + '''
    research_phase = 0;
    research_pressure(source, result, fillers, count);''')
                else:
                    text = bulk.replace_once(text, '    setvbuf(stdout, NULL, _IONBF, 0);',
                                             '    setvbuf(stdout, NULL, _IONBF, 0);\n    atexit(research_emit);')
                    text = bulk.replace_once(text, '            MinyarList empty = {NULL, 0, LLONG_MAX};\n            list_grow(&empty);',
                                             '            MinyarList empty = {NULL, LLONG_MAX, 0};\n            research_begin();\n            minyar_list_appended(&empty, 1, 0, 0);')
                    text = bulk.replace_once(text, '            minyar_list_appended(source, 1, 0, 0);',
                                             '            research_begin();\n            minyar_list_appended(source, 1, 0, 0);')
                text = prelude + text
                path.write_text(text)
                (directory / (name + '.adapter.patch')).write_text(''.join(difflib.unified_diff(
                    before.splitlines(True), text.splitlines(True), fromfile='original/' + name, tofile='adapted/' + name)))
        paired = {}
        for budget, sanitize in [(1, False), (32, False), (1, True)]:
            for fixture in names[:2]:
                for variant in ['baseline', 'candidate']:
                    directory = evidence / variant
                    label = f'{variant}-K{budget}-san{int(sanitize)}-{fixture}'
                    binary = directory / label
                    flags = ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if sanitize else ['-O2']
                    execute('compile-' + label, clang_command(['clang', '-std=c11', *flags,
                            f'-DMINYAR_RC_POLL_BUDGET={budget}', '-Wall', '-Wextra', '-Werror',
                            str(directory / 'tests' / fixture), '-o', str(binary)]))
                    report.setdefault('binaries', []).append({'path': str(binary.relative_to(evidence)), 'sha256': bulk.digest(binary)})
                    for mode in (['object'] if fixture == names[0] else ['frame', 'chunk']):
                        for idle in [False, True]:
                            row = execute(label + '-' + mode + ('-idle' if idle else '-debt'),
                                          [str(binary), *([] if mode == 'object' else [mode])], native=True, idle=idle)
                            key = (budget, sanitize, fixture, mode, idle)
                            events = row['observations'][0]
                            assert events['kind'] == 'events' and bool(events['guard_pending']) != idle, events
                            assert len([r for r in row['observations'] if r['kind'] == 'request']) == 9
                            if variant == 'baseline':
                                paired[key] = row
                            else:
                                old = paired[key]['observations']
                                new = row['observations']
                                assert old[1:] == new[1:], (key, 'state/admission difference')
                                if idle:
                                    work = {'add_entries', 'copy_entries', 'copy_bytes'}
                                    assert {k:v for k,v in old[0].items() if k not in work} == {k:v for k,v in new[0].items() if k not in work}
                                    assert new[0]['add_entries'] == 1 and old[0]['add_entries'] == (128 if budget == 1 else 512)
                                else:
                                    assert old == new, (key, 'debt path difference')
                                report['comparisons'].append({'configuration': list(key), 'status': 'equal-states-admissions-events'})
                                save()
        for sanitize in [False, True]:
            for variant in ['baseline', 'candidate']:
                directory = evidence / variant
                label = f'{variant}-errors-san{int(sanitize)}'
                binary = directory / label
                flags = ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if sanitize else ['-O2']
                execute('compile-' + label, clang_command(['clang', '-std=c11', *flags,
                        '-DMINYAR_SYSTEM_HEAP=1', '-DMINYAR_RC_POLL_BUDGET=32', '-Wall', '-Wextra', '-Werror',
                        str(directory / 'tests' / names[2]), '-o', str(binary)]))
                report['binaries'].append({'path': str(binary.relative_to(evidence)), 'sha256': bulk.digest(binary)})
                for mode in ['oom-object', 'oom-data', 'overflow']:
                    row = execute(label + '-' + mode, [str(binary), mode], expected=1, native=True)
                    diagnostic = ('Minyar stopped: this List became too large.' if mode == 'overflow'
                                  else 'Minyar stopped: the computer ran out of memory.')
                    actual = [line for line in row['stderr'].splitlines() if line.startswith('Minyar stopped:')]
                    assert actual == [diagnostic], row
                    key = (sanitize, mode)
                    if variant == 'baseline':
                        paired[key] = row
                    else:
                        assert row['observations'] == paired[key]['observations']
                        report['comparisons'].append({'configuration': list(key), 'status': 'equal-fatal-diagnostic-entry-order'})
        assert len(report['comparisons']) == 24
        assert all(bulk.digest(Path(path)) == value for path, value in frozen.items())
        report['status'] = 'passed'
        report['production_frozen_hashes'] = frozen
    except BaseException as error:
        report.update(status='failed', failure=repr(error))
        raise
    finally:
        save()
        print('Results: ' + str(evidence / 'results.json'), flush=True)


if __name__ == '__main__':
    main()
