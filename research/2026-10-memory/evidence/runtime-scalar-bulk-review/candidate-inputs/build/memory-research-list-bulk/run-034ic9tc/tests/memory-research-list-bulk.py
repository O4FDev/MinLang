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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=['system', 'fixed'], default='system')
    parser.add_argument('--budget', type=int, choices=[1, 32], default=32)
    parser.add_argument('--sanitize', action='store_true')
    args = parser.parse_args()
    parent = ROOT / 'build/memory-research-list-bulk'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent))
    report = {'status': 'running', 'variant': 'baseline', 'configuration': vars(args),
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
        instrument(evidence / 'runtime')
        execute('toolchain', ['clang', '--version'])
        flags = ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if args.sanitize else ['-O2']
        defines = ['-DMINYAR_SYSTEM_HEAP=1'] if args.profile == 'system' else ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_BOUNDED_HEAP_BYTES=2097152']
        binary = evidence / 'fixture'
        execute('compile', clang_command(['clang', '-std=c11', *flags, *defines,
                f'-DMINYAR_RC_POLL_BUDGET={args.budget}', '-Wall', '-Wextra', '-Werror',
                str(evidence / 'tests/memory-research-list-bulk.c'), '-o', str(binary)]))
        report['binary_sha256'] = digest(binary)
        red = execute('count-red', [str(binary), '--require-bulk'], 70, True)
        assert 'Expected n2 scalar prefix' in red['stderr']
        successful = execute('semantic-counts', [str(binary)], native=True)
        report['observations'] = [json.loads(line) for line in successful['stdout'].splitlines()]
        assert len(report['observations']) == 34
        report['status'] = 'passed-baseline-with-expected-count-red'
    except BaseException as error:
        report.update(status='failed', failure=repr(error))
        raise
    finally:
        save()
        print('Results: ' + str(evidence / 'results.json'), flush=True)


if __name__ == '__main__':
    main()
