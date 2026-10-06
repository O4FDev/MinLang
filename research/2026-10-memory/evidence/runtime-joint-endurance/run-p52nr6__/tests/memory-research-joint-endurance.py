#!/usr/bin/env python3
"""Explicit final-source endurance pilots/long cohort; no timing claim."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import selectors
import shutil
import signal
import subprocess
import tempfile
import time
from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot-only', action='store_true')
    parser.add_argument('--long-after-release', action='store_true')
    parser.add_argument('--pilot-evidence', type=Path)
    parser.add_argument('--gates-record', required=True, type=Path)
    args = parser.parse_args()
    if args.pilot_only == args.long_after_release:
        parser.error('Select exactly one explicitly authorized mode')
    gates = json.loads(args.gates_record.read_text())
    assert gates['status'] == 'passed', 'Focused joint gates are not complete'
    assert digest(ROOT / 'runtime/minyar_runtime.c') == 'd919f066a0e71c80cb079a22659928541e958b68b81a645d7631f52ec8531a51'
    assert digest(ROOT / 'runtime/minyar_collections.h') == '3b7ce602bc256dc8a42f49d87fd6cccd0eb28132d952e3eb34284614c4725810'
    parent = ROOT / 'research/2026-10-memory/evidence/runtime-joint-endurance'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent))
    report = {'status': 'running', 'runs': [], 'builds': [], 'scope':
              'Native C ABI with intentional testing accounting and nonallocating copy observer; correctness endurance, no speed claim'}
    source_hashes = {str(p): digest(p) for p in (ROOT / 'runtime').glob('minyar_*') if p.is_file()}
    report['source_hashes'] = source_hashes
    report['gates_record'] = {'path': str(args.gates_record), 'sha256': digest(args.gates_record)}
    prereg = ROOT / 'research/2026-10-memory/runtime-joint-endurance-preregister.json'
    shutil.copyfile(prereg, evidence / 'preregister.json')
    declared = json.loads(prereg.read_text())
    assert digest(ROOT / 'tests/memory-research-joint-endurance.c') == declared['fixture_sha256']
    assert digest(Path(__file__)) == declared['driver_sha256']
    shutil.copytree(ROOT / 'runtime', evidence / 'runtime', ignore=shutil.ignore_patterns('native'))
    (evidence / 'tests').mkdir()
    for name in ['memory-research-joint-endurance.c', Path(__file__).name, 'clang_helpers.py']:
        shutil.copyfile(ROOT / 'tests' / name, evidence / 'tests' / name)
    environment = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1',
                   'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}

    def save():
        temporary = evidence / 'results.json.tmp'
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(evidence / 'results.json')

    def limits():
        os.setsid()
        os.nice(15)
        resource.setrlimit(resource.RLIMIT_CPU, (180, 180))
        resource.setrlimit(resource.RLIMIT_FSIZE, (16777216, 16777216))

    def build(label, sanitize=False, omit=False):
        flags = ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if sanitize else ['-O2']
        defines = ['-DMINYAR_SYSTEM_HEAP=1', '-DMINYAR_RC_POLL_BUDGET=32']
        if omit:
            defines.append('-DMINYAR_RESEARCH_HIDE_PREFIX_COPY=1')
        command = clang_command(['clang', '-std=c11', *flags, *defines, '-Wall', '-Wextra', '-Werror',
                                 str(evidence / 'tests/memory-research-joint-endurance.c'), '-o', str(evidence / label)])
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, env=environment)
        row = {'label': label, 'command': command, 'returncode': result.returncode,
               'stdout': result.stdout, 'stderr': result.stderr}
        report['builds'].append(row)
        save()
        assert result.returncode == 0, row
        row['binary_sha256'] = digest(evidence / label)
        macros = subprocess.run(['clang', '-E', '-dM', *defines,
                                 str(evidence / 'tests/memory-research-joint-endurance.c')],
                                capture_output=True, text=True, timeout=30, check=True).stdout
        (evidence / (label + '-macros.txt')).write_text(macros)
        assert re.search(r'^#define MINYAR_RC_TESTING 1$', macros, re.M)
        save()
        return evidence / label

    def run(label, binary, duration, expected_fault=None):
        start = time.monotonic()
        command = ['/usr/bin/time', '-l', str(binary), str(duration), '4a01']
        if expected_fault == 'payload':
            command.append('--oracle-red')
        stderr_path = evidence / (label + '-stderr.log')
        summaries_path = evidence / (label + '-summaries.jsonl')
        monitor_path = evidence / (label + '-monitor.jsonl')
        binary_hash = digest(binary)
        row = {'label': label, 'command': command, 'binary_sha256': binary_hash,
               'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               'observer_monotonic_origin': start, 'duration_native_seconds': duration,
               'stderr': stderr_path.name, 'summaries': summaries_path.name, 'monitor': monitor_path.name}
        report['runs'].append(row)
        save()
        with stderr_path.open('w') as err, summaries_path.open('w') as summaries, monitor_path.open('w') as monitor:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=err, text=True,
                                       env=environment, preexec_fn=limits)
            row['time_wrapper_pid'] = process.pid
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ)
            last_progress = start
            next_monitor = start
            try:
                while process.poll() is None:
                    now = time.monotonic()
                    assert now - start <= 1850 and now - last_progress <= 120, 'External deadline/progress watchdog'
                    if now >= next_monitor:
                        children = subprocess.run(['pgrep', '-P', str(process.pid)], capture_output=True, text=True, timeout=5).stdout.split()
                        if children:
                            native_pid = children[0]
                            rss = subprocess.run(['ps', '-o', 'rss=', '-p', native_pid], capture_output=True, text=True, timeout=5).stdout.strip()
                            if rss:
                                rss_bytes = int(rss) * 1024
                                monitor.write(json.dumps({'observer_elapsed_seconds': now-start, 'native_pid': native_pid,
                                                          'sampled_rss_bytes': rss_bytes}) + '\n')
                                monitor.flush()
                                row['native_pid'] = int(native_pid)
                                assert rss_bytes <= 134217728, 'Sampled RSS threshold'
                        next_monitor = now + 30
                    for key, _ in selector.select(timeout=1):
                        line = key.fileobj.readline()
                        if line:
                            observation = json.loads(line)
                            summaries.write(line)
                            summaries.flush()
                            row['latest_summary'] = observation
                            last_progress = time.monotonic()
                            save()
                for line in process.stdout:
                    summaries.write(line)
                    row['latest_summary'] = json.loads(line)
                row['returncode'] = process.wait(timeout=5)
            except BaseException:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)
                raise
            finally:
                selector.close()
        row['observer_elapsed_seconds'] = time.monotonic() - start
        row['binary_hash_unchanged'] = digest(binary) == binary_hash
        logs = stderr_path.read_text()
        match = re.search(r'(\d+)\s+maximum resident set size', logs)
        row['completed_peak_RSS_bytes'] = int(match.group(1)) if match else None
        save()
        assert row['binary_hash_unchanged'] and match and row['completed_peak_RSS_bytes'] <= 134217728
        if expected_fault:
            assert row['returncode'] == 90 and 'FAILED line' in logs
            assert ('observed_prefix_copies ==' if expected_fault == 'observer' else 'bits == expected') in logs
            row['status'] = 'expected calibration rejection'
        else:
            summary = row['latest_summary']
            assert row['returncode'] == 0 and summary['final'] == 1
            assert summary['elapsed_native_seconds'] >= duration
            assert all(summary[key] > 0 for key in ['recoveries', 'eligible_scalar', 'eligible_empty',
                'observed_nonempty_prefix_copies', 'pending_debt_fallbacks', 'certified_ascii_joins',
                'unknown_ascii_joins', 'unicode_joins'])
            row['status'] = 'passed'
        save()

    try:
        report['toolchain'] = subprocess.run(['clang', '--version'], capture_output=True, text=True, check=True).stdout
        if args.pilot_only:
            native = build('native')
            sanitized = build('sanitize', sanitize=True)
            omission = build('observer-omission', omit=True)
            run('observer-calibration', omission, 2, 'observer')
            run('payload-calibration', sanitized, 10, 'payload')
            run('native-pilot', native, 2)
            run('sanitizer-pilot', sanitized, 1)
        else:
            assert args.pilot_evidence is not None
            prior = json.loads((args.pilot_evidence / 'results.json').read_text())
            assert prior['status'] == 'passed' and prior['source_hashes'] == source_hashes
            assert digest(args.pilot_evidence / 'tests/memory-research-joint-endurance.c') == declared['fixture_sha256']
            assert digest(args.pilot_evidence / 'tests' / Path(__file__).name) == declared['driver_sha256']
            native = args.pilot_evidence / 'native'
            identity = next(item['binary_sha256'] for item in prior['builds'] if item['label'] == 'native')
            assert digest(native) == identity
            report['pilot_evidence'] = {'path': str(args.pilot_evidence), 'results_sha256': digest(args.pilot_evidence / 'results.json')}
            run('joint-1800-seconds', native, 1800)
        assert all(digest(Path(path)) == sha for path, sha in source_hashes.items())
        report.update(status='passed', production_sources_unchanged=True)
    except BaseException as error:
        report.update(status='failed', failure=repr(error))
        raise
    finally:
        save()
        print('Results: ' + str(evidence / 'results.json'), flush=True)


if __name__ == '__main__':
    main()
