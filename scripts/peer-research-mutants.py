#!/usr/bin/env python3
"""Calibrated, isolated semantic mutations of literal-true reachability.

Mutation anchors are source checked; compiler-build errors, setup failures and
process timeouts are excluded from semantic-kill and viable denominators.
Each viable mutant runs the full unchanged calibrated O0/O2 regression suite.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import traceback
import unittest

ROOT = Path(__file__).resolve().parents[1]


def apply_mutation(source, mutant):
    occurrences = source.count(mutant['before'])
    if not mutant['before'] or occurrences != mutant['anchor_occurrences'] or occurrences != 1:
        raise ValueError(f"mutation anchor must occur once; found {occurrences}")
    return source.replace(mutant['before'], mutant['after'], 1)


def classify_suite(report, calibrated_count):
    if report['tests_run'] != calibrated_count:
        return 'incomplete_suite'
    errors = {row['kind'] for row in report['errors']}
    for kind in ('timeout', 'infrastructure_error', 'unexpected_error'):
        if kind in errors:
            return kind
    return 'semantic_kill' if report['failures'] else 'survived'


def mutation_score(outcomes):
    killed, survived = outcomes.count('semantic_kill'), outcomes.count('survived')
    viable = killed + survived
    return {'viable': viable, 'killed': killed, 'survived': survived,
            'excluded': len(outcomes) - viable,
            'percent': round(100 * killed / viable, 2) if viable else None}


def suite_worker(destination):
    sys.path.insert(0, str(ROOT / 'tests'))
    spec = importlib.util.spec_from_file_location('reachability_suite', ROOT / 'tests/peer-research-reachability.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    report = {'tests_run': 0, 'failures': [], 'errors': []}

    class RecordingResult(unittest.TextTestResult):
        def addFailure(self, test, error):
            report['failures'].append({'test': test.id(), 'exception': self._exc_info_to_string(error, test)})
            super().addFailure(test, error)

        def addError(self, test, error):
            kind = ('timeout' if issubclass(error[0], (subprocess.TimeoutExpired, TimeoutError)) else
                    'infrastructure_error' if issubclass(error[0], OSError) else 'unexpected_error')
            report['errors'].append({'test': test.id(), 'kind': kind,
                                     'exception': self._exc_info_to_string(error, test)})
            super().addError(test, error)

        def addSubTest(self, test, subtest, error):
            if error is not None:
                if issubclass(error[0], test.failureException):
                    report['failures'].append({'test': subtest.id(), 'exception': self._exc_info_to_string(error, subtest)})
                else:
                    kind = ('timeout' if issubclass(error[0], (subprocess.TimeoutExpired, TimeoutError)) else
                            'infrastructure_error' if issubclass(error[0], OSError) else 'unexpected_error')
                    report['errors'].append({'test': subtest.id(), 'kind': kind,
                                             'exception': self._exc_info_to_string(error, subtest)})
            super().addSubTest(test, subtest, error)

    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(suite)
    report['tests_run'] = result.testsRun
    destination.write_text(json.dumps(report, indent=2) + '\n')
    return 0 if result.wasSuccessful() else 1


def execute(command, directory, env, *, timeout=90):
    started = time.monotonic()
    record = {'command': command, 'timeout_seconds': timeout}
    try:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=os.name != 'nt')
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == 'nt':
                process.kill()
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            stdout, stderr = process.communicate(timeout=10)
            record['timed_out'] = True
        record.update(exit_code=process.returncode, stdout=stdout.decode('utf-8', errors='backslashreplace'),
                      stderr=stderr.decode('utf-8', errors='backslashreplace'))
    except OSError as error:
        record.update(infrastructure_error=str(error), exit_code=None)
    record['wall_seconds'] = time.monotonic() - started
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'command.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


def hashes(paths):
    return {str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path):
            hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite-worker', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--plan', type=Path, default=ROOT / 'research/2026-10-memory/profiling-reachability-mutations-plan.json')
    parser.add_argument('--compiler', type=Path, default=ROOT / 'build/minyarc')
    parser.add_argument('--stage0', type=Path, default=ROOT / 'build/stage0')
    parser.add_argument('--runtime', type=Path, default=ROOT / 'build/minyar-runtime.o')
    parser.add_argument('--compiler-runtime', type=Path, default=ROOT / 'build/minyar-compiler-runtime.ll')
    parser.add_argument('--clang', default=os.environ.get('MINYAR_TEST_CLANG', 'clang'))
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    if args.suite_worker:
        return suite_worker(args.suite_worker.resolve())
    for name in ('compiler', 'stage0', 'runtime', 'compiler_runtime', 'plan'):
        setattr(args, name, getattr(args, name).resolve())
    parent = ROOT / 'build/peer-research/mutants'
    parent.mkdir(parents=True, exist_ok=True)
    directory = args.output_dir.resolve() if args.output_dir else Path(tempfile.mkdtemp(prefix='run-', dir=parent)).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    plan = json.loads(args.plan.read_text())
    source_path = ROOT / plan['source']
    source = source_path.read_text()
    paths = [source_path, ROOT / 'bootstrap/stage0.c', args.compiler, args.stage0, args.runtime,
             args.compiler_runtime, ROOT / 'tests/peer-research-reachability.py', Path(__file__).resolve(), args.plan,
             *sorted((ROOT / 'runtime').glob('*.h')), *sorted((ROOT / 'runtime').glob('*.c'))]
    env = dict(os.environ, MINYAR_TEST_CLANG=args.clang, MINYAR_TEST_COMPILER=str(args.compiler),
               MINYAR_TEST_RUNTIME=str(args.runtime))
    report = {'start_utc': datetime.now(timezone.utc).isoformat(), 'source_sha256_start': hashes(paths),
              'scope': 'Six source-anchored CFG mutants, full calibrated literal-true suite at O0/O2; infrastructure exclusions explicit.',
              'status': 'running', 'mutants': [], 'clang': args.clang}
    path = directory / 'results.json'
    path.write_text(json.dumps(report, indent=2) + '\n')

    def run_suite(compiler, target):
        target.mkdir(parents=True, exist_ok=True)
        output = target / 'suite.json'
        record = execute([sys.executable, str(Path(__file__).resolve()), '--suite-worker', str(output)],
                         target, dict(env, MINYAR_TEST_COMPILER=str(compiler)), timeout=180)
        if record.get('timed_out'):
            return 'timeout', record, None
        if record.get('infrastructure_error') or not output.exists():
            return 'infrastructure_error', record, None
        return None, record, json.loads(output.read_text())

    try:
        error, calibration, calibrated = run_suite(args.compiler, directory / 'calibration')
        report['calibration'] = calibration
        if error or not calibrated or calibrated['tests_run'] < 17 or calibrated['failures'] or calibrated['errors'] or calibration['exit_code'] != 0:
            report['status'] = 'calibration_failed'
            return 2
        expected_count = calibrated['tests_run']
        report['calibrated_tests'] = expected_count
        for mutant in plan['mutants']:
            target = directory / mutant['id']
            target.mkdir()
            record = {'id': mutant['id'], 'detecting_test': mutant['detecting_test'], 'status': 'incomplete'}
            report['mutants'].append(record)
            candidate = apply_mutation(source, mutant)
            candidate_path, llvm, binary = target / 'compiler.min', target / 'compiler.ll', target / 'compiler'
            candidate_path.write_text(candidate)
            record['candidate_sha256'] = hashlib.sha256(candidate.encode()).hexdigest()
            command = execute([str(args.stage0), str(candidate_path), '-o', str(llvm)], target / 'frontend', env)
            record['frontend'] = command
            if command.get('timed_out') or command.get('infrastructure_error') or command['exit_code'] != 0:
                record['status'] = ('timeout' if command.get('timed_out') else 'infrastructure_error' if command.get('infrastructure_error') else 'build_failed')
            else:
                command = execute([args.clang, '-O0', '-Wno-override-module', str(llvm),
                                   str(args.compiler_runtime), *([] if os.name == 'nt' else ['-lm']),
                                   '-o', str(binary)], target / 'backend', env)
                record['backend'] = command
                if command.get('timed_out') or command.get('infrastructure_error') or command['exit_code'] != 0:
                    record['status'] = ('timeout' if command.get('timed_out') else 'infrastructure_error' if command.get('infrastructure_error') else 'build_failed')
                else:
                    error, command, suite = run_suite(binary, target / 'tests')
                    record.update(suite_command=command, suite=suite,
                                  status=error or classify_suite(suite, expected_count))
            path.write_text(json.dumps(report, indent=2) + '\n')
            print(f"{mutant['id']}: {record['status']}", flush=True)
        report['score'] = mutation_score([row['status'] for row in report['mutants']])
        report['status'] = 'completed' if report['score']['excluded'] == 0 else 'incomplete'
        return 0 if report['status'] == 'completed' else 2
    except (OSError, ValueError, KeyError) as error:
        report.update(status='infrastructure_error', error=str(error), traceback=traceback.format_exc())
        return 2
    finally:
        report.update(end_utc=datetime.now(timezone.utc).isoformat(), source_sha256_end=hashes(paths))
        report['changed_sources_during_run'] = [name for name, value in report['source_sha256_start'].items()
                                              if value != report['source_sha256_end'].get(name)]
        if report['changed_sources_during_run']:
            report['status'] = 'source_changed'
        path.write_text(json.dumps(report, indent=2) + '\n')
        print(path)


if __name__ == '__main__':
    raise SystemExit(main())
