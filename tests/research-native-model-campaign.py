#!/usr/bin/env python3
"""Isolated actual-runtime DAG/frame replay against an independent logical oracle."""
import importlib.util
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('research_native_oracle', Path(__file__).with_name('research-native-model-oracle.py'))
oracle = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = oracle
spec.loader.exec_module(oracle)


def instrument_sources(sources):
    result = dict(sources)
    for name, anchor, expected in [('minyar_bounded_rc.h', 'RC_DEALLOCATE(object);', 1),
                                   ('minyar_rc.h', 'free(object);', 2)]:
        source = sources[name]
        pattern = r'^( +)' + re.escape(anchor) + '$'
        if len(re.findall(pattern, source, re.MULTILINE)) != expected:
            raise ValueError('destructor observation anchor changed: ' + name)
        result[name] = re.sub(pattern, r'\1research_on_free(object + 1);\n\1' + anchor, source, flags=re.MULTILINE)
    return result


MUTANTS = {
    'borrow_without_retain': ('minyar_rc.h',
        'void minyar_rc_borrow(void *value) {\n    minyar_rc_retain(value);\n    minyar_rc_keep(value);',
        'void minyar_rc_borrow(void *value) {\n    minyar_rc_keep(value);'),
    'local_without_retain': ('minyar_rc.h',
        'void minyar_rc_local(long long index, void *value) {\n    minyar_rc_retain(value);',
        'void minyar_rc_local(long long index, void *value) {'),
    'frame_owner_visit_omitted': ('minyar_bounded_rc.h',
        'rc_drop(rc_bounded_pending_local_value(frame, --frame->local_count));',
        '(void)rc_bounded_pending_local_value(frame, --frame->local_count);'),
    'oversized_poll_k_plus_one': ('minyar_bounded_rc.h',
        'if (budget > MINYAR_RC_POLL_BUDGET) budget = MINYAR_RC_POLL_BUDGET;',
        'if (budget > MINYAR_RC_POLL_BUDGET + 1) budget = MINYAR_RC_POLL_BUDGET + 1;'),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    started = time.monotonic()
    starting_self_usage = resource.getrusage(resource.RUSAGE_SELF)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profiles', nargs='+', choices=['eager', 'system', 'fixed', 'lazy'], default=['eager', 'system', 'fixed', 'lazy'])
    parser.add_argument('--budgets', nargs='+', type=int, default=[1, 8, 32])
    parser.add_argument('--seeds', nargs='+', type=lambda value: int(value, 0), default=[1, 39752, 0xc0ffee, 0xbad5eed])
    parser.add_argument('--steps', type=int, default=3000)
    parser.add_argument('--sanitize', action='store_true', help='ASan+UBSan O1 instead of native O2')
    parser.add_argument('--mutations', action='store_true', help='Four calibrated mutants after correct-runtime replays')
    args = parser.parse_args()
    if args.steps < 0 or args.steps > 12000 or any(k < 1 for k in args.budgets):
        parser.error('steps must be 0..12000 and budgets positive')
    parent = ROOT / 'evidence/native-model'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent))
    binary_directory = ROOT / 'build/research-native-model-binaries' / evidence.name
    binary_directory.mkdir(parents=True)
    runtime = evidence / 'runtime'
    runtime.mkdir()
    sources = {}
    for path in (ROOT / 'runtime').glob('minyar_*'):
        if path.is_file():
            sources[path.name] = path.read_text()
            shutil.copy2(path, runtime / path.name)
    instrumented = instrument_sources(sources)
    for name in ('minyar_bounded_rc.h', 'minyar_rc.h'):
        (runtime / name).write_text(instrumented[name])
    fixture = evidence / 'replay.c'
    shutil.copy2(Path(__file__).with_name('research-native-model-replay.c'), fixture)
    tooling = evidence / 'tooling'
    tooling.mkdir()
    for path in Path(__file__).parent.glob('research-native-model-*.py'):
        shutil.copy2(path, tooling / path.name)
    shutil.copy2(Path(__file__).with_name('clang_helpers.py'), tooling / 'clang_helpers.py')
    report = {'status': 'running', 'scope': 'Actual runtime public ownership transitions versus independent immediate logical reachability; no compiler ownership inference or cycles claim.',
              'config': vars(args), 'source_hashes': {str(p.relative_to(ROOT)): sha(p) for p in (ROOT / 'runtime').glob('minyar_*') if p.is_file()},
              'tooling_hashes': {p.name: sha(p) for p in Path(__file__).parent.glob('research-native-model-*') if p.is_file()},
              'instrumentation': {name: {'before_sha256': hashlib.sha256(sources[name].encode()).hexdigest(), 'after_sha256': sha(runtime / name),
                                       'change': 'Read-only generation/destruction observer immediately before managed header deallocation; no queue/service/allocation calls.'}
                                  for name in ('minyar_bounded_rc.h', 'minyar_rc.h')},
              'traces': [], 'builds': [], 'replays': [], 'mutants': []}

    def save():
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    def command(command, timeout=60):
        environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=0:abort_on_error=1', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        command_started = time.monotonic()
        try:
            run = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=timeout)
            result = {'command': command, 'returncode': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr, 'timed_out': False}
        except subprocess.TimeoutExpired as error:
            result = {'command': command, 'returncode': None, 'stdout': str(error.stdout), 'stderr': str(error.stderr), 'timed_out': True}
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        result['resources'] = {'wall_seconds': time.monotonic() - command_started,
                               'user_cpu_seconds': after.ru_utime - before.ru_utime,
                               'system_cpu_seconds': after.ru_stime - before.ru_stime,
                               'campaign_children_peak_rss_bytes': after.ru_maxrss * (1 if sys.platform == 'darwin' else 1024),
                               'rss_scope': 'Cumulative maximum over all previously completed direct campaign children; not a per-command allocation estimate.'}
        return result

    for seed in args.seeds:
        operations = oracle.generate(seed, args.steps)
        trace = evidence / f'trace-{seed}.txt'
        census = {}
        trace.write_text(oracle.encode(operations, census))
        (evidence / f'operations-{seed}.json').write_text(json.dumps(operations) + '\n')
        report['traces'].append({'seed': seed, 'operations': len(operations), 'path': trace.name, 'sha256': sha(trace),
                                 'census': census,
                                 'premises': 'Validated before native replay: each referenced object is logically live, mutations cannot close a graph path into a cycle, root transfers consume an occupied source into a valid target; final logical roots/frames empty.'})
    save()
    flags = ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if args.sanitize else ['-O2']

    def build(directory, label, profile, budget):
        defines = []
        if profile == 'system':
            defines += ['-DMINYAR_SYSTEM_HEAP=1']
        elif profile in ('fixed', 'lazy'):
            defines += ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_BOUNDED_HEAP_BYTES=8388608']
            if profile == 'lazy':
                defines += ['-DMINYAR_LAZY_HEAP=1']
        binary = binary_directory / (label + '-probe')
        result = command(clang_command(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', *flags, *defines,
                                        f'-DMINYAR_RC_POLL_BUDGET={budget}', f'-DMINYAR_RESEARCH_RUNTIME="{directory / "minyar_runtime.c"}"',
                                        str(fixture), '-o', str(binary)]))
        result.update(label=label, profile=profile, budget=budget)
        report['builds'].append(result)
        save()
        return binary, result

    def replay(binary, trace, label):
        observations = evidence / (label + '-states.txt')
        result = command([str(binary), str(evidence / trace['path']), str(observations)])
        result.update(label=label, seed=trace['seed'], observations=observations.name)
        if result['returncode'] == 0:
            result['summary'] = json.loads(result['stdout'])
            result['observations_sha256'] = sha(observations)
            compressed = observations.with_suffix(observations.suffix + '.gz')
            with observations.open('rb') as source, gzip.open(compressed, 'wb', compresslevel=1) as output:
                shutil.copyfileobj(source, output)
            result['observations'] = compressed.name
            result['compressed_observations_sha256'] = sha(compressed)
            observations.unlink()
        return result

    for profile in args.profiles:
        for budget in ([1] if profile == 'eager' else args.budgets):
            label = f'{profile}-k{budget}'
            binary, built = build(runtime, label, profile, budget)
            if built['returncode'] != 0:
                report['status'] = 'build_timeout_inconclusive' if built['timed_out'] else 'fixture_build_failure'
                save()
                print(evidence / 'results.json')
                return 1
            for trace in report['traces']:
                result = replay(binary, trace, label + '-seed' + str(trace['seed']))
                report['replays'].append(result)
                if result['returncode'] != 0:
                    report['status'] = 'replay_timeout_inconclusive' if result['timed_out'] else 'replay_failure_requires_triage'
                    save()
                    print(evidence / 'results.json')
                    return 1
                save()
    if args.mutations:
        # Separate system/K1 correct calibration even when omitted by caller.
        binary, built = build(runtime, 'mutant-calibration-system-k1', 'system', 1)
        calibration = replay(binary, report['traces'][0], 'mutant-calibration') if built['returncode'] == 0 else built
        report['mutation_calibration'] = calibration
        if calibration['returncode'] != 0:
            report['status'] = 'invalid_mutation_calibration'
            save()
            print(evidence / 'results.json')
            return 1
        for name, (file, old, new) in MUTANTS.items():
            destination = evidence / name / 'runtime'
            shutil.copytree(runtime, destination)
            path = destination / file
            source = path.read_text()
            if source.count(old) != 1:
                raise ValueError('mutation anchor changed: ' + name)
            path.write_text(source.replace(old, new))
            binary, built = build(destination, name, 'system', 1)
            item = {'name': name, 'file': file, 'old': old, 'new': new, 'mutant_sha256': sha(path), 'build': built}
            if built['returncode'] != 0:
                item['status'] = 'build_timeout_inconclusive' if built['timed_out'] else 'build_failure_invalid_mutant'
            else:
                result = replay(binary, report['traces'][0], name + '-seed' + str(report['traces'][0]['seed']))
                item['run'] = result
                diagnostic = result['stderr']
                if result['timed_out']:
                    item['status'] = 'runtime_timeout_inconclusive'
                elif result['returncode'] == 0:
                    item['status'] = 'survived'
                elif any(marker in diagnostic for marker in ('LIVE FREE', 'LIVE PAYLOAD REFERENCES FREED OR UNKNOWN GENERATION',
                                                            'Assertion', 'assertion', 'AddressSanitizer', 'runtime error:')):
                    item['status'] = 'killed'
                else:
                    item['status'] = 'runtime_failure_unclassified'
            report['mutants'].append(item)
            save()
    report['source_unchanged'] = {name: sha(ROOT / name) == digest for name, digest in report['source_hashes'].items()}
    usage = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    report['resources'] = {'wall_seconds': time.monotonic() - started,
                           'runner_user_cpu_seconds': usage.ru_utime - starting_self_usage.ru_utime,
                           'runner_system_cpu_seconds': usage.ru_stime - starting_self_usage.ru_stime,
                           'runner_peak_rss_bytes': usage.ru_maxrss * (1 if sys.platform == 'darwin' else 1024),
                           'children_user_cpu_seconds': children.ru_utime,
                           'children_system_cpu_seconds': children.ru_stime,
                           'children_peak_rss_bytes': children.ru_maxrss * (1 if sys.platform == 'darwin' else 1024),
                           'limitations': 'RSS is OS getrusage maximum, not managed heap live bytes. Native observer changes elapsed time; these are campaign resource measurements, not latency benchmarks.'}
    report['status'] = 'passed' if all(report['source_unchanged'].values()) else 'source_changed_during_campaign'
    save()
    print(evidence / 'results.json')
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
