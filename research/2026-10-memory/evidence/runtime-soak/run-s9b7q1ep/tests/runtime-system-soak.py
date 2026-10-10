#!/usr/bin/env python3
"""Approved default-system cohort; run only after fixed cohort succeeds."""
import argparse
import difflib
import sys
import hashlib
import json
import os
from pathlib import Path
import resource
import selectors
import shutil
import subprocess
import tempfile
import time
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
from clang_helpers import clang_command

SEED = 0x51f37


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=float, default=7200)
    parser.add_argument('--pilot-only', action='store_true')
    args = parser.parse_args()
    if args.duration <= 0 or args.duration > 7200:
        parser.error('Duration must stay within the approved 7200-second cohort.')
    prior_path = ROOT / 'research/2026-10-memory/evidence/runtime-soak/run-h2hs4wqq/results.json'
    prior = json.loads(prior_path.read_text())
    assert prior['status'] == 'passed' and prior['source_hashes_unchanged'], 'Fixed cohort is not complete.'
    fixed = next(run for run in prior['runs'] if run['label'] == 'fixed-two-hour')
    assert fixed['status'] == 'passed' and fixed['latest_summary']['final'] == 1
    assert fixed['latest_summary']['elapsed_monotonic_seconds'] >= 7200
    parent = ROOT / 'research/2026-10-memory/evidence/runtime-soak'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent)).resolve()
    report = {'status': 'running', 'seed': SEED, 'invocation': [__file__, *os.sys.argv[1:]],
              'sources': [], 'builds': [], 'runs': [],
              'prior_cohort': {'path': str(prior_path.relative_to(ROOT)), 'sha256': digest(prior_path)},
              'preregistered': {'long_profile': 'default-system/K32', 'long_seconds': args.duration,
                               'live_slots': 32, 'payload_cap': 4096, 'rss_native_bytes': 256 * 1024**2,
                               'rss_sanitizer_bytes': 1024**3, 'requested_bytes_cap': 4 * 1024**2,
                               'charged_bytes_cap': None, 'quiescent_epoch_interval': 1024,
                               'progress_watchdog_seconds': 120, 'absolute_watchdog_seconds': 7800,
                               'cpu_seconds_limit': 9000, 'target_cpu_fraction': .08,
                               'failure_trace_events': 64},
              'scope': 'Native C ABI payload/alias churn, not generated code. Counted API calls include '
                       'oracle queries; internal calls are excluded. Explicit poll bounds are checked; '
                       'all hidden hook aggregate work is not instrumented. Wall samples are loaded-host '
                       'observations, not throughput or latency guarantees. Stable logical slots and '
                       'potentially growing queued debt are distinct.'}
    for source in [*ROOT.joinpath('runtime').glob('minyar_*'), Path(__file__),
                   ROOT / 'tests/memory-research-soak.c', ROOT / 'tests/clang_helpers.py']:
        if source.is_file():
            relative = Path('runtime' if source.parent == ROOT / 'runtime' else 'tests') / source.name
            source_path = str(source.relative_to(ROOT))
            if source.name == 'memory-research-soak.c':
                relative = Path('original') / relative
            target = evidence / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            report['sources'].append({'path': str(relative), 'source_path': source_path, 'sha256': digest(target)})
    original_fixture = evidence / 'original/tests/memory-research-soak.c'
    fixture = evidence / 'tests/memory-research-soak.c'
    original = original_fixture.read_text()
    old = r'\"elapsed_monotonic_seconds\":%.6f,'
    new = r'\"monotonic_origin_seconds\":%.9f,' + old
    assert original.count(old) == 1
    changed = original.replace(old, new)
    assert changed.count('final, original_seed, monotonic() - started,') == 1
    changed = changed.replace('final, original_seed, monotonic() - started,',
                              'final, original_seed, started, monotonic() - started,')
    assert changed.count('    initialize();\n    while (') == 1
    changed = changed.replace('    initialize();\n    while (',
                              '    initialize();\n    summary(started, 0);\n    while (')
    fixture.write_text(changed)
    (evidence / 'summary-metadata.patch').write_text(''.join(difflib.unified_diff(
        original.splitlines(True), changed.splitlines(True),
        fromfile='a/tests/memory-research-soak.c', tofile='b/tests/memory-research-soak.c')))
    report['compiled_fixture'] = {'path': str(fixture.relative_to(evidence)), 'sha256': digest(fixture),
        'original_sha256': digest(original_fixture),
        'change': 'Only summary native-origin field/argument and one initial summary; epoch operations, limits and pacing unchanged.'}
    report['toolchain'] = subprocess.run(['clang', '--version'], capture_output=True, text=True, timeout=10).stdout
    report['metric_scope'] = {'requested_and_charged': 'End-of-epoch samples, not continuous transient peaks',
        'rss': 'Periodic 30s ps samples, not continuous peak', 'recovery': 'Exact objects/requested/tracked-system-allocation zero after quiescent drain and frame-cache disposal',
        'duration': 'Native monotonic origin and elapsed seconds in each summary; observer origin separately recorded',
        'cpu_pacing': '8% responsiveness policy, not throughput evidence'}
    environment = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1',
                   'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
    report['sanitizer_environment'] = {key: environment[key] for key in ('ASAN_OPTIONS', 'UBSAN_OPTIONS')}

    def save():
        temporary = evidence / 'results.json.tmp'
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(evidence / 'results.json')

    def limits():
        resource.setrlimit(resource.RLIMIT_CPU, (9000, 9000))
        resource.setrlimit(resource.RLIMIT_FSIZE, (256 * 1024**2, 256 * 1024**2))
        os.nice(15)

    def build(label, definitions, sanitize=False):
        flags = ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if sanitize else ['-O2']
        binary = evidence / label
        command = clang_command(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', *flags,
                                  *definitions, '-DMINYAR_BOUNDED_HEAP_BYTES=16777216',
                                  str(evidence / 'tests/memory-research-soak.c'), '-o', str(binary)])
        result = subprocess.run(command, capture_output=True, text=True, timeout=120, env=environment,
                                preexec_fn=limits)
        report['builds'].append({'label': label, 'command': command, 'returncode': result.returncode,
                                 'stdout': result.stdout, 'stderr': result.stderr,
                                 'binary_sha256': digest(binary) if result.returncode == 0 else None})
        save()
        assert result.returncode == 0, (label, result.stderr)
        return binary

    def run(binary, label, duration, sanitize=False, mutant=False):
        command = [str(binary), str(duration), str(SEED), str(int(mutant))]
        record = {'label': label, 'command': command, 'sanitizer': sanitize, 'mutant': mutant,
                  'summaries': label + '-summaries.jsonl', 'monitor': label + '-monitor.jsonl',
                  'stderr': label + '-stderr.log', 'rss_peak_bytes': 0, 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
        report['runs'].append(record)
        save()
        started = last_progress = last_monitor = time.monotonic()
        record['observer_monotonic_origin_seconds'] = started
        record['observer_target_seconds'] = started + duration
        record['binary_sha256'] = digest(binary)
        maximum = min(duration + 120, 7800)
        threshold = 1024**3 if sanitize else 256 * 1024**2
        with (evidence / record['stderr']).open('w') as errors, (evidence / record['summaries']).open('w') as summaries, (evidence / record['monitor']).open('w') as monitor:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors, text=True,
                                       env=environment, preexec_fn=limits)
            record['pid'] = process.pid
            save()
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ)
            try:
                while process.poll() is None:
                    for key, _ in selector.select(timeout=1):
                        line = key.fileobj.readline()
                        if line:
                            row = json.loads(line)
                            row['provenance'] = {'generator_sha256': digest(Path(__file__)),
                                'compiled_fixture_sha256': report['compiled_fixture']['sha256'],
                                'runtime_sha256': digest(evidence / 'runtime/minyar_runtime.c'),
                                'binary_sha256': record['binary_sha256'], 'profile': label,
                                'memory_scope': 'Completed-epoch samples; exact recovery separate'}
                            record['native_monotonic_origin_seconds'] = row['monotonic_origin_seconds']
                            record['native_target_seconds'] = row['monotonic_origin_seconds'] + duration
                            summaries.write(json.dumps(row) + '\n')
                            summaries.flush()
                            record['latest_summary'] = row
                            last_progress = time.monotonic()
                            save()
                            print(label + ': ' + json.dumps(row), flush=True)
                    now = time.monotonic()
                    if now - last_monitor >= 30 or last_monitor == started:
                        observation = subprocess.run(['ps', '-o', 'rss=', '-p', str(process.pid)],
                                                     capture_output=True, text=True, timeout=5)
                        if observation.stdout.strip():
                            rss = int(observation.stdout.strip()) * 1024
                            record['rss_peak_bytes'] = max(record['rss_peak_bytes'], rss)
                            monitor.write(json.dumps({'elapsed_monotonic_seconds': now - started, 'rss_bytes': rss}) + '\n')
                            monitor.flush()
                            if rss > threshold:
                                raise RuntimeError('Preregistered RSS threshold exceeded')
                        last_monitor = now
                    if now - started > maximum:
                        raise TimeoutError('Preregistered absolute watchdog exceeded')
                    if now - last_progress > 120:
                        raise TimeoutError('Preregistered progress watchdog exceeded')
                # The final line can arrive between poll completion and selector dispatch.
                for line in process.stdout:
                    row = json.loads(line)
                    row['provenance'] = {'generator_sha256': digest(Path(__file__)),
                        'compiled_fixture_sha256': report['compiled_fixture']['sha256'],
                        'runtime_sha256': digest(evidence / 'runtime/minyar_runtime.c'),
                        'binary_sha256': record['binary_sha256'], 'profile': label,
                        'memory_scope': 'Completed-epoch samples; exact recovery separate'}
                    summaries.write(json.dumps(row) + '\n')
                    record['latest_summary'] = row
            except BaseException as error:
                record['monitor_failure'] = repr(error)
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                raise
            finally:
                selector.close()
                record['returncode'] = process.wait()
                record['elapsed_monotonic_seconds'] = time.monotonic() - started
                save()
        if mutant:
            assert record['returncode'] == 70 and 'Soak assertion failed' in (evidence / record['stderr']).read_text()
            record['status'] = 'oracle-mutation-detected'
        else:
            assert record['returncode'] == 0, (label, record['returncode'], record['stderr'])
            assert record['latest_summary']['final'] == 1 and record['latest_summary']['full_recoveries'] > 0
            record['status'] = 'passed'
        save()

    print('Evidence: ' + str(evidence), flush=True)
    try:
        system = build('system-k32-sanitize', ['-DMINYAR_SYSTEM_HEAP=1', '-DMINYAR_RC_POLL_BUDGET=32'], True)
        run(system, 'oracle-red', 60, sanitize=True, mutant=True)
        run(system, 'system-sanitizer-pilot', 10, sanitize=True)
        native = build('system-k32-native', ['-DMINYAR_SYSTEM_HEAP=1', '-DMINYAR_RC_POLL_BUDGET=32'])
        run(native, 'system-native-pilot', 10)
        if not args.pilot_only:
            run(native, 'system-two-hour', args.duration)
        report['status'] = 'passed'
    except BaseException as error:
        report.update(status='failed', failure=repr(error))
        raise
    finally:
        report['source_hashes_unchanged'] = all(digest(ROOT / row['source_path']) == row['sha256'] for row in report['sources'])
        save()
        print('Results: ' + str(evidence / 'results.json'), flush=True)


if __name__ == '__main__':
    main()
