#!/usr/bin/env python3
"""Isolated scalar prefix-copy counts; no timing or production edits."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import resource
import shutil
import signal
import subprocess
import tempfile
from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text, needle, replacement):
    assert text.count(needle) == 1, needle
    return text.replace(needle, replacement)


def instrument(runtime):
    path = runtime / 'minyar_rc.h'
    text = before = path.read_text()
    for needle, injection in {
        'static void *rc_allocate_object(size_t size, unsigned kind) {':
            '    research_event(1, size, kind, 0, 0);',
        'static void *rc_allocate_data(size_t size) {':
            '    research_event(2, size, 0, 0, 0);',
        'static void *rc_reallocate_data(void *pointer, size_t size) {':
            '    research_event(3, size, 0, 0, 0);',
        'void minyar_rc_retain(void *value) {\n':
            '    if (research_phase) research_retains++;',
    }.items():
        text = replace_once(text, needle, needle + '\n' + injection)
    needle = '    if (rc_pending_count) return minyar_rc_poll(budget);'
    text = replace_once(text, needle, '''    size_t before_pending = rc_pending_count;
    if (rc_pending_count) {
        size_t work = minyar_rc_poll(budget);
        research_event(4, budget, before_pending, work, rc_pending_count);
        return work;
    }
    research_event(4, budget, before_pending, 0, rc_pending_count);''')
    path.write_text(text)
    (runtime.parent / 'rc-observer.patch').write_text(''.join(difflib.unified_diff(
        before.splitlines(True), text.splitlines(True), fromfile='a/minyar_rc.h', tofile='b/minyar_rc.h')))
    path = runtime / 'minyar_bounded_rc.h'
    text = before = path.read_text()
    needle = '    if (budget > MINYAR_RC_POLL_BUDGET) budget = MINYAR_RC_POLL_BUDGET;'
    text = replace_once(text, needle, needle + '\n    size_t before_pending = rc_pending_count;')
    start = text.index('size_t minyar_rc_poll(size_t budget) {')
    end = text.index('\nvoid minyar_rc_release(', start)
    fragment = text[start:end]
    fragment = replace_once(fragment, '    return work;',
                            '    research_event(5, budget, before_pending, work, rc_pending_count);\n    return work;')
    text = text[:start] + fragment + text[end:]
    path.write_text(text)
    (runtime.parent / 'poll-observer.patch').write_text(''.join(difflib.unified_diff(
        before.splitlines(True), text.splitlines(True), fromfile='a/minyar_bounded_rc.h', tofile='b/minyar_bounded_rc.h')))
    path = runtime / 'minyar_collections.h'
    text = before = path.read_text()
    for name, counter in [('minyar_list_add', 'research_adds'), ('minyar_list_add_take', 'research_takes')]:
        needle = f'void {name}(MinyarList *list, long long value) {{'
        text = replace_once(text, needle, needle + f'\n    if (research_phase) {counter}++;')
    needle = '#ifdef MINYAR_BOUNDED_RC\n    /* Intermediate growth services pending retirement.'
    text = replace_once(text, needle, '#ifdef MINYAR_BOUNDED_RC\n    research_guard_pending = rc_pending_count;\n    /* Intermediate growth services pending retirement.')
    path.write_text(text)
    (runtime.parent / 'list-observer.patch').write_text(''.join(difflib.unified_diff(
        before.splitlines(True), text.splitlines(True), fromfile='a/minyar_collections.h', tofile='b/minyar_collections.h')))


def candidate(runtime):
    path = runtime / 'minyar_collections.h'
    text = original = path.read_text()
    start = text.index('MinyarList *minyar_list_appended(')
    end = text.index('\n#ifdef MINYAR_BOUNDED_RC\nMINYAR_HOT', start)
    fragment = text[start:end]
    marker = '#ifdef MINYAR_BOUNDED_RC\n    /* Intermediate growth services pending retirement.'
    fragment = replace_once(fragment, marker, '    _Bool bulk_scalar = !references;\n#ifdef MINYAR_BOUNDED_RC\n    bulk_scalar = bulk_scalar && !rc_pending_count;\n#endif\n' + marker)
    needle = '    for (long long position = 0; position < list->length; position++)\n        minyar_list_add(result, list->values[position]);'
    replacement = '    if (bulk_scalar) {\n        if (list->length)\n            memcpy(result->values, list->values, (size_t)list->length * sizeof(*list->values));\n        result->length = list->length;\n    } else {\n        for (long long position = 0; position < list->length; position++)\n            minyar_list_add(result, list->values[position]);\n    }'
    fragment = replace_once(fragment, needle, replacement)
    text = text[:start] + fragment + text[end:]
    path.write_text(text)
    (runtime.parent / 'candidate.patch').write_text(''.join(difflib.unified_diff(
        original.splitlines(True), text.splitlines(True), fromfile='a/runtime/minyar_collections.h',
        tofile='b/runtime/minyar_collections.h')))


def verify_candidate(runtime):
    """Allow only the reviewed function tokens, including after local formatting."""
    reference = ROOT / 'research/2026-10-memory/evidence/runtime-list-bulk-cpu/run-ws0ma9zu/candidate/runtime/minyar_collections.h'
    assert digest(reference) == '3b7ce602bc256dc8a42f49d87fd6cccd0eb28132d952e3eb34284614c4725810'
    def body(path):
        text = path.read_text()
        start = text.index('MinyarList *minyar_list_appended(')
        end = text.index('\n#ifdef MINYAR_BOUNDED_RC\nMINYAR_HOT', start)
        return re.findall(r'[A-Za-z_]\w*|\d+|"(?:\\.|[^"\\])*"|[^\s]', text[start:end])
    assert body(runtime / 'minyar_collections.h') == body(reference), 'Not the reviewed scalar body'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=['system', 'fixed'], default='system')
    parser.add_argument('--budget', type=int, choices=[1, 32], default=32)
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--candidate', action='store_true')
    parser.add_argument('--already-applied', action='store_true')
    parser.add_argument('--compare-baseline', type=Path)
    args = parser.parse_args()
    if args.compare_baseline and not args.candidate:
        parser.error('--compare-baseline requires --candidate')
    if args.already_applied and not args.candidate:
        parser.error('--already-applied requires --candidate')
    parent = ROOT / 'build/memory-research-list-bulk'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent))
    report = {'status': 'running', 'variant': 'candidate' if args.candidate else 'baseline',
              'configuration': {'profile': args.profile, 'budget': args.budget, 'sanitize': args.sanitize},
              'checks': [], 'sources': [], 'scope': 'Source-level entries/copy bytes and complete managed request/poll traces; no CPU claim.'}
    for source in (ROOT / 'runtime').glob('minyar_*'):
        if source.is_file():
            target = evidence / 'runtime' / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            original = evidence / 'original/runtime' / source.name
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, original)
            report['sources'].append({'path': str(source), 'snapshot': str(original.relative_to(evidence)), 'sha256': digest(original)})
    for name in ['memory-research-list-bulk.c', Path(__file__).name, 'clang_helpers.py']:
        target = evidence / 'tests' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / 'tests' / name, target)
        report['sources'].append({'snapshot': str(target.relative_to(evidence)), 'sha256': digest(target)})
    shutil.copyfile(ROOT / 'research/2026-10-memory/runtime-list-bulk-preregister.json', evidence / 'preregister.json')
    environment = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1', 'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}

    def save():
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    def limits():
        os.setsid()
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
        resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))

    def execute(label, command, expected=0, native=False):
        wrapped = command
        if native and platform.system() == 'Darwin':
            wrapped = ['/usr/bin/time', '-l', '/usr/sbin/taskpolicy', '-m', '128', *command]
        process = subprocess.Popen(wrapped, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   env=environment, preexec_fn=limits)
        try:
            stdout, stderr = process.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
            report['checks'].append({'label': label, 'command': wrapped, 'returncode': process.returncode,
                                     'stdout': stdout, 'stderr': stderr, 'timed_out': True})
            save()
            raise
        row = {'label': label, 'command': wrapped, 'returncode': process.returncode, 'stdout': stdout, 'stderr': stderr}
        if native and platform.system() == 'Darwin':
            peak = re.search(r'(\d+)\s+maximum resident set size', stderr)
            assert peak, stderr
            row['peak_rss_bytes'] = int(peak.group(1))
        report['checks'].append(row)
        save()
        assert process.returncode == expected, (label, row)
        if native and platform.system() == 'Darwin':
            assert row['peak_rss_bytes'] <= 128 * 1024 * 1024, row
        return row

    try:
        if args.candidate:
            if args.already_applied:
                verify_candidate(evidence / 'runtime')
            else:
                candidate(evidence / 'runtime')
        instrument(evidence / 'runtime')
        execute('toolchain', ['clang', '--version'])
        flags = ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if args.sanitize else ['-O2']
        defines = ['-DMINYAR_SYSTEM_HEAP=1'] if args.profile == 'system' else ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_BOUNDED_HEAP_BYTES=2097152']
        binary = evidence / 'fixture'
        execute('compile', clang_command(['clang', '-std=c11', *flags, *defines,
                f'-DMINYAR_RC_POLL_BUDGET={args.budget}', '-Wall', '-Wextra', '-Werror',
                str(evidence / 'tests/memory-research-list-bulk.c'), '-o', str(binary)]))
        report['binary_sha256'] = digest(binary)
        red = execute('count-target', [str(binary), '--require-bulk'], 0 if args.candidate else 70, True)
        if not args.candidate:
            assert 'Expected n2 scalar prefix' in red['stderr']
        successful = execute('semantic-counts', [str(binary)], native=True)
        report['observations'] = [json.loads(line) for line in successful['stdout'].splitlines()]
        assert len(report['observations']) == 34
        for row in report['observations']:
            capacity = 0
            while capacity < row['length'] + 1:
                if args.profile == 'fixed':
                    capacity = 3 if not capacity else 2 * capacity + 1
                else:
                    capacity = 2 if not capacity else capacity * (4 if capacity >= 4096 else 2)
            assert row['capacity'] == capacity, row
            bulk = args.candidate and row['mode'] == 'idle'
            assert row['add_entries'] == (0 if bulk else row['length']) + (not row['take']), row
            assert row['take_entries'] == row['take'], row
            if bulk:
                assert row['copy_entries'] == bool(row['length']), row
                assert row['copy_bytes'] == row['length'] * 8, row
            if row['mode'] == 'references':
                assert row['retain_entries'] == 4 + (not row['take']), row
            else:
                assert row['retain_entries'] == 0, row
        if args.compare_baseline:
            baseline = json.loads(args.compare_baseline.read_text())
            assert baseline['status'].startswith('passed') and baseline['variant'] == 'baseline'
            assert baseline['configuration'] == report['configuration']
            assert len(baseline['observations']) == len(report['observations'])
            changed = []
            for old, new in zip(baseline['observations'], report['observations']):
                if new['mode'] != 'idle':
                    assert old == new, (old, new)
                else:
                    work = {'add_entries', 'copy_entries', 'copy_bytes'}
                    assert {k:v for k,v in old.items() if k not in work} == {k:v for k,v in new.items() if k not in work}, (old,new)
                    if old != new:
                        changed.append({'length':new['length'],'take':new['take'],
                                        'before_append_entries':old['add_entries']+old['take_entries'],
                                        'after_append_entries':new['add_entries']+new['take_entries'],
                                        'after_bulk_copy_bytes':new['copy_bytes']})
            report['baseline_comparison'] = {'path':str(args.compare_baseline),'sha256':digest(args.compare_baseline),
                'result':'Complete ordered requests/helper/all-public-poll arrays, capacity, retain/take and post/recovery fields match; debt/reference rows match fully.',
                'changed_source_work_rows':changed}
        report['status'] = 'passed-candidate' if args.candidate else 'passed-baseline-with-expected-count-red' 
    except BaseException as error:
        report.update(status='failed', failure=repr(error))
        raise
    finally:
        save()
        print('Results: ' + str(evidence / 'results.json'), flush=True)


if __name__ == '__main__':
    main()
