#!/usr/bin/env python3
"""Mocked Windows controls for idle evidence; never replay an actual idle failure.

The preserved fixture is the exact pre-observability input. Both fixtures' actual
CPU helpers and timed windows run against deterministic APIs, so the controls
check unchanged API ordering, gate arithmetic and passing output, plus retained
raw evidence before a forced assertion. This is an observability contract, not
a Windows performance test or an attribution of either historical failure.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import shutil
import sys
import time

from clang_helpers import native_path, windows_host
from test_evidence import terminate_process_tree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from host_paths import host_path
BASELINE = ROOT / 'tests/fixtures/cycle-progress-before-observability.c.txt'
FIXTURE = ROOT / 'tests/cycle-progress.c'
BASELINE_SHA256 = '1ab79ac428e106daf8d6f2aa8d1388571be3cc3d836ac6ccc9cd558bbf0e84b4'
START = '    double start = wall_seconds(), cpu_start = cpu_seconds();\n'
END = '    /* Unreachable cycles must disappear'
PREFIX = 'cycle progress idle failure:'
CALLS = 'WCPWRDVSWWCP'
LOOP = """    while (wall_seconds() - start < seconds) {
        minyar_rc_retain_traced(nodes[1]);
        minyar_rc_release(nodes[1]);
        long long wait = service_wait(20);
        assert(rc_object_count == N);
        assert(minyar_record_get(nodes[0], 0) == slot(nodes[0]));
        if (wait > 0) {
            waits++;
            sleep_ms(wait);
        }
    }
"""

MOCK = r"""
#define _WIN32 1
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
typedef uint64_t ULONGLONG;
typedef struct { uint32_t dwLowDateTime, dwHighDateTime; } FILETIME;
typedef union {
    struct { uint32_t LowPart, HighPart; };
    uint64_t QuadPart;
} ULARGE_INTEGER;
static char calls[64];
static unsigned call_count, cpu_calls;
static ULONGLONG kernels[2], users[2], wall_tick = 1000, wall_advance;
static void trace(char value) {
    if (call_count + 1 >= sizeof(calls)) exit(90);
    calls[call_count++] = value;
    calls[call_count] = 0;
}
static void mock_assert_failure(const char *expression) {
    fprintf(stderr, "MOCK_ASSERT %s\nMOCK_CALLS %s\n", expression, calls);
    exit(42);
}
#define assert(value) do { if (!(value)) mock_assert_failure(#value); } while (0)
static void *GetCurrentProcess(void) { trace('C'); return (void *)(uintptr_t)1; }
static int GetProcessTimes(void *process, FILETIME *created, FILETIME *exited,
                           FILETIME *kernel, FILETIME *user) {
    (void)created;
    (void)exited;
    trace('P');
    assert(process == (void *)(uintptr_t)1 && cpu_calls < 2);
    kernel->dwLowDateTime = (uint32_t)kernels[cpu_calls];
    kernel->dwHighDateTime = (uint32_t)(kernels[cpu_calls] >> 32);
    user->dwLowDateTime = (uint32_t)users[cpu_calls];
    user->dwHighDateTime = (uint32_t)(users[cpu_calls] >> 32);
    cpu_calls++;
    return 1;
}
static ULONGLONG GetTickCount64(void) { trace('W'); return wall_tick; }
typedef struct { long long self; } MinyarRecord;
static MinyarRecord records[2];
static MinyarRecord *nodes[2] = {&records[0], &records[1]};
static unsigned N = 2048;
static size_t rc_object_count = 2048, waits;
static long long slot(void *value) { return (long long)(uintptr_t)value; }
static void minyar_rc_retain_traced(void *value) {
    assert(value == nodes[1]); trace('R');
}
static void minyar_rc_release(void *value) {
    assert(value == nodes[1]); trace('D');
}
static long long service_wait(long long timeout) {
    assert(timeout == 20); trace('V'); return 20;
}
static long long minyar_record_get(MinyarRecord *record, long long index) {
    assert(record == nodes[0] && index == 0); return record->self;
}
static void sleep_ms(long long milliseconds) {
    assert(milliseconds == 20); trace('S'); wall_tick += wall_advance;
}
"""

MAIN = r"""
int main(int argc, char **argv) {
    assert(argc == 6);
    kernels[0] = strtoull(argv[1], NULL, 10);
    kernels[1] = strtoull(argv[2], NULL, 10);
    users[0] = strtoull(argv[3], NULL, 10);
    users[1] = strtoull(argv[4], NULL, 10);
    wall_advance = strtoull(argv[5], NULL, 10);
    records[0].self = slot(nodes[0]);
    double seconds = 1.0;
__WINDOW__
    assert(cpu_calls == 2);
    printf("MOCK_CALLS %s\n", calls);
    return 0;
}
"""


def sections(source):
    helpers = source[source.index('static double wall_seconds(void) {'):
                     source.index('static void sleep_ms(')]
    window = source[source.index(START):source.index(END)]
    return helpers, window


def contract(baseline, current):
    assert hashlib.sha256(BASELINE.read_bytes()).hexdigest() == BASELINE_SHA256
    old_helpers, old_window = sections(baseline)
    helpers, window = sections(current)
    assert PREFIX not in old_window
    assert PREFIX in window, 'idle failure must retain its timed evidence'
    assert old_window.count(LOOP) == window.count(LOOP) == 1
    for token, count in [('GetProcessTimes(', 1), ('GetCurrentProcess(', 1),
                         ('GetTickCount64(', 1)]:
        assert old_helpers.count(token) == helpers.count(token) == count
    assert old_window.count('cpu_seconds()') == window.count('cpu_seconds()') == 2
    assert old_window.count('wall_seconds()') == window.count('wall_seconds()') == 3
    assert window.count('assert(waits > 0);') == 1
    assert window.count('assert(idle_cpu <= 0.02);') == 1
    assert window.index(PREFIX) < window.index('assert(waits > 0);')
    assert window.index(PREFIX) < window.index('assert(idle_cpu <= 0.02);')
    assert window.index('cpu_end = cpu_seconds()') < window.index(PREFIX)
    # Prelude and cleanup/output remain the exact original implementation.
    helper_start = 'static double wall_seconds(void) {'
    sleep_start = 'static void sleep_ms('
    assert baseline[:baseline.index(helper_start)] == current[:current.index(helper_start)]
    assert baseline[baseline.index(sleep_start):baseline.index(START)] == \
           current[current.index(sleep_start):current.index(START)]
    assert baseline[baseline.index(END):] == current[current.index(END):]
    assert old_helpers[:old_helpers.index('static double cpu_seconds(void) {')] in helpers
    return helpers, window


def expected(values):
    kernel_begin, kernel_end, user_begin, user_end, milliseconds = values
    cpu_start = float(kernel_begin + user_begin) / 1e7
    cpu_end = float(kernel_end + user_end) / 1e7
    wall_start = 1.0
    wall_end = float(1000 + milliseconds) / 1000.0
    elapsed = wall_end - wall_start
    delta = cpu_end - cpu_start
    return {
        'calls': 2, 'kernel_begin': kernel_begin, 'kernel_end': kernel_end,
        'user_begin': user_begin, 'user_end': user_end,
        'cpu_start': cpu_start, 'cpu_end': cpu_end, 'cpu_delta': delta,
        'wall_start': wall_start, 'wall_end': wall_end, 'elapsed': elapsed,
        'idle_cpu': delta / elapsed,
    }


def require_assertions():
    if sys.flags.optimize:
        raise RuntimeError('Idle observability requires Python assertions; do not use -O')


def decoded(data):
    return data.decode('utf-8', errors='replace').replace('\r\n', '\n').replace('\r', '\n')


def secondary(report, primary, stage, error):
    row = {'stage': stage, 'exception': type(error).__name__, 'message': str(error)}
    report['passed'] = False
    report['finalization_errors'].append(row)
    if primary is not None and hasattr(primary, 'add_note'):
        primary.add_note('idle observation finalization: ' + json.dumps(row, sort_keys=True))


def finalize(evidence, report, primary):
    failure = None
    report.setdefault('files', {})
    report.setdefault('unhashed_files', [])
    try:
        paths = sorted(evidence.rglob('*'))
    except BaseException as error:
        paths = []
        secondary(report, primary, 'file-inventory', error)
        failure = failure or error
    for path in paths:
        name = path.relative_to(evidence).as_posix()
        try:
            if not path.is_file() or path.is_symlink() or path.name == 'manifest.json':
                continue
            report['files'][name] = {
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'bytes': path.stat().st_size,
            }
        except BaseException as error:
            report['unhashed_files'].append(name)
            secondary(report, primary, 'file-retention:' + name, error)
            failure = failure or error
    try:
        pending = evidence/'manifest.json.tmp'
        pending.write_text(json.dumps(report, indent=2) + '\n')
        os.replace(pending, evidence/'manifest.json')
    except BaseException as error:
        secondary(report, primary, 'manifest-retention', error)
        failure = failure or error
    if primary is None and failure is not None:
        raise failure


class CommandRecords:
    """Raw observations and the shared, owned tree timeout convention."""
    def __init__(self, evidence, report):
        self.evidence, self.report = evidence, report

    def run(self, command, *, timeout, label):
        command = list(map(str, command))
        row = {'argv': command, 'cwd': str(ROOT), 'label': label,
               'timeout_seconds': timeout, 'timed_out': False, 'status': None,
               'executable': None, 'executable_sha256': None,
               'cleanup': {'action': 'none', 'status': 'not-needed'}}
        self.report['commands'].append(row)
        began = time.monotonic()
        process = None
        out, err = b'', b''
        primary = None
        try:
            requested = command[0]
            executable = host_path(requested) if os.path.dirname(requested) else None
            if executable is None:
                found = shutil.which(requested)
                if found is None:
                    raise FileNotFoundError('Missing command executable: ' + requested)
                executable = host_path(found)
            executable = executable.resolve()
            row['executable'] = str(executable)
            row['executable_sha256'] = hashlib.sha256(executable.read_bytes()).hexdigest()
            process = subprocess.Popen(
                command, executable=native_path(executable), cwd=ROOT,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                start_new_session=not windows_host())
            row['pid'] = process.pid
            row['start_new_session'] = not windows_host()
            try:
                out, err = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired as error:
                row['timed_out'] = True
                row['cleanup'] = {'action': 'terminate_process_tree', 'status': 'started',
                                  'owned_pid': process.pid, 'backend': (
                                      'native-Windows-tree' if windows_host() else 'owned-POSIX-group')}
                try:
                    terminate_process_tree(process)
                    row['cleanup']['status'] = 'completed'
                except BaseException as cleanup_error:
                    row['cleanup']['status'] = 'failed'
                    row['cleanup']['exception'] = type(cleanup_error).__name__ + ': ' + str(cleanup_error)
                    error.add_note('idle mock tree cleanup failed: ' + row['cleanup']['exception'])
                    # Fail closed; direct-child cleanup is not a tree success.
                    process.kill()
                try:
                    out, err = process.communicate(timeout=10)
                except BaseException as drain_error:
                    row['cleanup']['status'] = 'failed'
                    row['cleanup']['drain_error'] = type(drain_error).__name__ + ': ' + str(drain_error)
                    error.add_note('idle mock post-cleanup drain failed: ' + str(drain_error))
                    process.kill()
                    for pipe in (process.stdout, process.stderr):
                        if pipe is not None:
                            pipe.close()
                    process.wait(timeout=5)
                row['status'] = process.returncode
                raise subprocess.TimeoutExpired(command, timeout, output=out, stderr=err) from error
            row['status'] = process.returncode
            return subprocess.CompletedProcess(command, process.returncode, out, err)
        except BaseException as error:
            primary = error
            if process is not None and process.poll() is None:
                row['cleanup'] = {'action': 'terminate_process_tree', 'status': 'started',
                                  'owned_pid': process.pid, 'reason': 'command-exception'}
                try:
                    terminate_process_tree(process)
                    row['cleanup']['status'] = 'completed'
                except BaseException as cleanup_error:
                    row['cleanup']['status'] = 'failed'
                    row['cleanup']['exception'] = type(cleanup_error).__name__ + ': ' + str(cleanup_error)
                    error.add_note('idle mock exception cleanup failed: ' + str(cleanup_error))
                    process.kill()
                try:
                    out, err = process.communicate(timeout=10)
                except BaseException as drain_error:
                    row['cleanup']['status'] = 'failed'
                    row['cleanup']['drain_error'] = str(drain_error)
                    error.add_note('idle mock exception drain failed: ' + str(drain_error))
                    process.kill()
                    for pipe in (process.stdout, process.stderr):
                        if pipe is not None and not pipe.closed:
                            pipe.close()
                    try:
                        process.wait(timeout=5)
                    except BaseException as wait_error:
                        row['cleanup']['wait_error'] = str(wait_error)
                        error.add_note('idle mock final child wait failed: ' + str(wait_error))
            if process is not None:
                row['status'] = process.returncode
            row['exception'] = type(error).__name__ + ': ' + str(error)
            raise
        finally:
            row['elapsed_seconds'] = time.monotonic() - began
            for name, data in (('stdout', out), ('stderr', err)):
                path = self.evidence/(label + '.' + name + '.bin')
                try:
                    path.write_bytes(data or b'')
                    row[name + '_path'] = path.relative_to(self.evidence).as_posix()
                    row[name + '_sha256'] = hashlib.sha256(data or b'').hexdigest()
                    row[name + '_bytes'] = len(data or b'')
                except BaseException as error:
                    secondary(self.report, primary, label + '-' + name + '-retention', error)
                    if primary is None:
                        raise
            if process is not None:
                for pipe in (process.stdout, process.stderr):
                    if pipe is not None and not pipe.closed:
                        pipe.close()


def check_case(name, values, binaries, owner, report):
    want = expected(values)
    failed = not want['idle_cpu'] <= 0.02
    results = {}
    for label, binary in binaries.items():
        argv = [native_path(binary), *map(str, values)]
        raw = owner.run(argv, timeout=10, label=f'{name}-{label}')
        result = subprocess.CompletedProcess(argv, raw.returncode,
                                             decoded(raw.stdout), decoded(raw.stderr))
        results[label] = result
        report['cases'].append({
            'case': name, 'fixture': label, 'argv': argv, 'status': result.returncode,
            'command_index': len(report['commands']) - 1,
            'stdout': result.stdout, 'stderr': result.stderr,
            'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
        })
        assert result.returncode == (42 if failed else 0), (name, label, result)
        if failed:
            assert result.stdout == ''
            assert result.stderr.endswith(f'MOCK_ASSERT idle_cpu <= 0.02\nMOCK_CALLS {CALLS}\n')
        else:
            assert result.stdout == f'MOCK_CALLS {CALLS}\n'
            assert result.stderr == ''
    before, after = results['before'], results['after']
    assert before.returncode == after.returncode
    if not failed:
        assert (before.stdout, before.stderr) == (after.stdout, after.stderr)
        return
    assert PREFIX not in before.stderr
    lines = after.stderr.splitlines()
    assert len(lines) == 3 and lines[0].startswith(PREFIX)
    actual = dict(re.findall(r'([a-z_]+)=([^\s]+)', lines[0]))
    assert set(actual) == set(want), (name, actual)
    for key, value in want.items():
        if isinstance(value, int):
            assert int(actual[key]) == value, (name, key, actual[key], value)
        else:
            assert float(actual[key]) == value, (name, key, actual[key], value)


def main(arguments=None):
    require_assertions()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, default=ROOT / 'build/cycle-progress-observability')
    args = parser.parse_args(arguments)
    evidence = args.evidence.resolve()
    if evidence.exists():
        raise ValueError('Idle observability evidence must be a fresh directory')
    evidence.mkdir(parents=True)
    report = {
        'passed': False, 'scope': 'mocked observability only; no historical failure replay',
        'inputs': {}, 'cases': [], 'compile': [], 'commands': [],
        'finalization_errors': [], 'unhashed_files': [],
    }
    primary = None
    try:
        inputs = [BASELINE, FIXTURE, Path(__file__).resolve(),
                  ROOT/'tests/clang_helpers.py', ROOT/'tests/test_evidence.py',
                  ROOT/'tools/host_paths.py']
        for path in inputs:
            name = path.relative_to(ROOT).as_posix()
            raw = path.read_bytes()
            before = hashlib.sha256(raw).hexdigest()
            copied = evidence/'inputs'/name
            copied.parent.mkdir(parents=True, exist_ok=True)
            copied.write_bytes(raw)
            copy_sha = hashlib.sha256(copied.read_bytes()).hexdigest()
            after = hashlib.sha256(path.read_bytes()).hexdigest()
            report['inputs'][name] = {
                'before_sha256': before, 'retained_path': copied.relative_to(evidence).as_posix(),
                'retained_sha256': copy_sha, 'after_sha256': after,
            }
            if before != copy_sha or before != after:
                raise ValueError('Idle observability input changed while copying: ' + name)
        baseline, current = BASELINE.read_text(), FIXTURE.read_text()
        helpers, window = contract(baseline, current)
        owner = CommandRecords(evidence, report)
        compiler = os.environ.get('MINYAR_TEST_CLANG', 'clang')
        version = owner.run([compiler, '--version'], timeout=10, label='compiler-version')
        if version.returncode:
            raise RuntimeError('Idle mock compiler version probe failed')
        compiler_row = report['commands'][-1]
        report['compiler'] = {
            'path': compiler_row['executable'], 'before_sha256': compiler_row['executable_sha256'],
            'version_stdout_path': compiler_row['stdout_path'],
            'version_stderr_path': compiler_row['stderr_path'],
        }
        binaries = {}
        for label, parts in [('before', sections(baseline)), ('after', (helpers, window))]:
            source = evidence / f'{label}-mock.c'
            source.write_text(MOCK + parts[0] + MAIN.replace('__WINDOW__', parts[1]))
            binary = evidence / (label + '-mock' + ('.exe' if windows_host() else ''))
            argv = [compiler, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                    native_path(source), '-o', native_path(binary)]
            result = owner.run(argv, timeout=30, label=label + '-compile')
            report['compile'].append({
                'argv': argv, 'status': result.returncode,
                'stdout': decoded(result.stdout), 'stderr': decoded(result.stderr),
                'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'command_index': len(report['commands']) - 1,
            })
            assert result.returncode == 0, decoded(result.stderr)
            binaries[label] = binary
        cases = [
            ('zero', (2000000, 2000000, 3000000, 3000000, 1000)),
            ('exact-boundary', (0, 200000, 0, 0, 1000)),
            ('kernel-failure', (2000000, 2300000, 3000000, 3000000, 1000)),
            ('user-failure', (2000000, 2000000, 3000000, 3400000, 1000)),
            ('high-word-carry', ((1 << 32) - 150000, (1 << 32) + 150000,
                                 (2 << 32) + 10001, (2 << 32) + 10001, 1000)),
            ('wall-overshoot', (2000000, 2300000, 3000000, 3000000, 1250)),
            ('double-boundary', (10**16, 10**16 + 200000, 0, 0, 1000)),
            ('double-failure', (10**16, 10**16 + 300000, 0, 0, 1000)),
        ]
        # Preserve the original double-subtraction oracle, not integer deltas.
        assert expected(cases[-2][1])['cpu_delta'] != 200000 / 1e7
        assert expected(cases[-1][1])['cpu_delta'] != 300000 / 1e7
        for name, values in cases:
            check_case(name, values, binaries, owner, report)
        for path in inputs:
            name = path.relative_to(ROOT).as_posix()
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            report['inputs'][name]['final_sha256'] = actual
            if actual != report['inputs'][name]['before_sha256']:
                raise ValueError('Idle observability input changed during execution: ' + name)
        report['compiler']['after_sha256'] = hashlib.sha256(
            Path(report['compiler']['path']).read_bytes()).hexdigest()
        if report['compiler']['after_sha256'] != report['compiler']['before_sha256']:
            raise ValueError('Idle mock compiler changed during execution')
        if report['finalization_errors']:
            raise RuntimeError('Idle observability raw evidence retention failed')
        report['passed'] = True
        print(f'idle observability: {len(cases)} mocked controls passed; no performance claim')
    except BaseException as error:
        primary = error
        report['exception'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        finalize(evidence, report, primary)


if __name__ == '__main__':
    main()
