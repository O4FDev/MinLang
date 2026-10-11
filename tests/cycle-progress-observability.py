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

from clang_helpers import windows_host

ROOT = Path(__file__).resolve().parents[1]
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


def check_case(name, values, binaries, evidence, report):
    want = expected(values)
    failed = not want['idle_cpu'] <= 0.02
    results = {}
    for label, binary in binaries.items():
        argv = [str(binary), *map(str, values)]
        result = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        (evidence / f'{name}-{label}.stdout').write_text(result.stdout)
        (evidence / f'{name}-{label}.stderr').write_text(result.stderr)
        results[label] = result
        report['cases'].append({
            'case': name, 'fixture': label, 'argv': argv, 'status': result.returncode,
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, default=ROOT / 'build/cycle-progress-observability')
    args = parser.parse_args()
    baseline, current = BASELINE.read_text(), FIXTURE.read_text()
    helpers, window = contract(baseline, current)
    args.evidence.mkdir(parents=True, exist_ok=True)
    report = {
        'passed': False, 'scope': 'mocked observability only; no historical failure replay',
        'inputs': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in [BASELINE, FIXTURE, Path(__file__).resolve()]},
        'cases': [], 'compile': [],
    }
    try:
        binaries = {}
        for label, parts in [('before', sections(baseline)), ('after', (helpers, window))]:
            source = args.evidence / f'{label}-mock.c'
            source.write_text(MOCK + parts[0] + MAIN.replace('__WINDOW__', parts[1]))
            binary = args.evidence / (label + '-mock' + ('.exe' if windows_host() else ''))
            argv = [os.environ.get('MINYAR_TEST_CLANG', 'clang'), '-std=c11', '-O2',
                    '-Wall', '-Wextra', '-Werror', str(source), '-o', str(binary)]
            result = subprocess.run(argv, capture_output=True, text=True, timeout=30)
            (args.evidence / f'{label}-compile.stdout').write_text(result.stdout)
            (args.evidence / f'{label}-compile.stderr').write_text(result.stderr)
            report['compile'].append({'argv': argv, 'status': result.returncode,
                                      'stdout': result.stdout, 'stderr': result.stderr,
                                      'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
            assert result.returncode == 0, result.stderr
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
        # Guard against replacing the gate's existing double subtraction with
        # a newly computed integer-delta metric, even when both appear plausible.
        assert expected(cases[-2][1])['cpu_delta'] != 200000 / 1e7
        assert expected(cases[-1][1])['cpu_delta'] != 300000 / 1e7
        for name, values in cases:
            check_case(name, values, binaries, args.evidence, report)
        report['passed'] = True
        print(f'idle observability: {len(cases)} mocked controls passed; no performance claim')
    finally:
        (args.evidence / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
