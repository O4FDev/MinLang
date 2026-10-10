#!/usr/bin/env python3
"""Bounded mixed-value soak with red oracle calibration and short profile pilots."""
import argparse
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
from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]
SEED = 0x20261004


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=float, default=7200)
    parser.add_argument('--pilot-only', action='store_true')
    args = parser.parse_args()
    parent = ROOT / 'research/2026-10-memory/evidence/runtime-soak'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent)).resolve()
    report = {'status': 'running', 'seed': SEED, 'invocation': [__file__, *os.sys.argv[1:]],
              'sources': [], 'builds': [], 'runs': [],
              'preregistered': {'long_profile': 'fixed16MiB/K1', 'long_seconds': args.duration,
                               'live_slots': 32, 'payload_cap': 4096, 'rss_native_bytes': 256 * 1024**2,
                               'rss_sanitizer_bytes': 1024**3, 'requested_bytes_cap': 4 * 1024**2,
                               'charged_bytes_cap': 8 * 1024**2, 'quiescent_epoch_interval': 1024,
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
            target = evidence / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            report['sources'].append({'path': str(relative), 'sha256': digest(target)})
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
                                 'stdout': result.stdout, 'stderr': result.stderr})
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
        fixed = build('fixed-k1', ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_RC_POLL_BUDGET=1'])
        run(fixed, 'fixed-pilot', 10)
        lazy = build('lazy-k32', ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_LAZY_HEAP=1', '-DMINYAR_RC_POLL_BUDGET=32'])
        run(lazy, 'lazy-pilot', 10)
        if not args.pilot_only:
            run(fixed, 'fixed-two-hour', args.duration)
        report['status'] = 'passed'
    except BaseException as error:
        report.update(status='failed', failure=repr(error))
        raise
    finally:
        report['source_hashes_unchanged'] = all(digest(ROOT / row['path']) == row['sha256'] for row in report['sources'])
        save()
        print('Results: ' + str(evidence / 'results.json'), flush=True)


if __name__ == '__main__':
    main()
