#!/usr/bin/env python3
"""Paired Linux common workloads; native Atacama GUI remains separately required.

Use only on an owned, otherwise idle Boat host. Run under xvfb-run for the
actual GLFW Minyarcraft application, not the headless research fixture.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import statistics
import subprocess
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--neodb', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--lock', type=Path, required=True)
    parser.add_argument('--candidate-receipt', type=Path, required=True,
                        help='Successful qualification receipt binding source and built artifact hashes')
    parser.add_argument('--clang', default='clang-22')
    parser.add_argument('--repeats', type=int, default=31)
    parser.add_argument('--compile-batch', type=int, default=16)
    parser.add_argument('--only', choices=('selfcompile', 'json', 'neodb', 'craft'))
    args = parser.parse_args()
    assert args.repeats >= 5 and args.compile_batch >= 1
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    roots = {name: path.resolve() for name, path in
             [('control', args.control), ('candidate', args.candidate)]}
    owner = args.neodb.resolve()
    qualification = json.loads(args.candidate_receipt.read_text())
    assert qualification['status'] == 'pass', 'candidate qualification did not pass'
    for name, expected in qualification['sha256'].items():
        assert digest(roots['candidate'] / name) == expected, 'candidate changed after qualification: ' + name
    required = {'compiler/compiler.min', 'bootstrap/stage0.c', 'runtime/minyar_runtime.c',
                'build/minyarc', 'build/minyar-runtime.o'}
    for pattern in ('runtime/minyar_*.h', 'compiler/*.min', 'compiler/*.patch',
                    'library/*.min', 'runtime/native/*.[cmh]'):
        required.update(str(p.relative_to(roots['candidate']))
                        for p in roots['candidate'].glob(pattern) if p.is_file())
    assert required <= qualification['sha256'].keys(), 'qualification lacks required source/artifact bindings'
    assert digest(roots['candidate'] / 'build/minyarc') != digest(roots['control'] / 'build/minyarc'), 'candidate is the copied control compiler'
    env = dict(os.environ, CC=args.clang, LLVM_CC=args.clang,
               MINYAR_CLANG=args.clang, MINYAR_TEST_CLANG=args.clang,
               COMPILER_LTO_FLAGS='-flto=thin -fuse-ld=lld-22 -Wl,--thinlto-jobs=1 -Wl,--threads=1',
               MINYAR_CLANG_FLAGS='-O2 -Wno-override-module -fuse-ld=lld-22 -Wl,--thinlto-jobs=1 -Wl,--threads=1',
               MINYAR_NATIVE_FLAGS='-O2 -Wno-override-module',
               LIBGL_ALWAYS_SOFTWARE='1', LP_NUM_THREADS='1')
    report = dict(status='running', maximum_ratio=1.01, commands=[], observations=[],
                  ratios={}, profile='system K32 release ThinLTO; compiler production flags',
                  scope='Actual Linux compiler, JSON, neo-db and GLFW craft. Atacama GUI unqualified.',
                  pending=['native Atacama GUI/AX', 'native macOS and Windows'], inputs={})
    report['candidate_qualification_sha256'] = digest(args.candidate_receipt)
    report['runner_sha256'] = digest(Path(__file__))
    report['requested_workload'] = args.only or 'all four Linux workloads'
    if args.only:
        report['pending'].extend(name for name in ('selfcompile', 'json', 'neodb', 'craft') if name != args.only)

    def save():
        (args.output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    def run(argv, cwd, label, batch=1):
        records = []
        for invocation in range(batch):
            before = resource.getrusage(resource.RUSAGE_CHILDREN)
            began = time.monotonic()
            result = subprocess.run(list(map(str, argv)), cwd=cwd, env=env,
                                    capture_output=True, text=True, timeout=240)
            wall = time.monotonic() - began
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            row = dict(label=label, argv=list(map(str, argv)), cwd=str(cwd),
                       invocation=invocation, returncode=result.returncode,
                       stdout=result.stdout, stderr=result.stderr, wall_seconds=wall,
                       cpu_seconds=after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime)
            report['commands'].append(row)
            records.append(row)
            save()
            if result.returncode or result.stderr:
                raise RuntimeError(f'{label} failed; retained results.json: {result.stderr}')
        return dict(cpu_seconds=sum(r['cpu_seconds'] for r in records) / batch,
                    wall_seconds=sum(r['wall_seconds'] for r in records) / batch,
                    stdout=records[-1]['stdout'])

    with args.lock.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        cpu = min(os.sched_getaffinity(0))
        os.sched_setaffinity(0, {cpu})
        report['cpu_affinity'] = [cpu]
        report['versions'] = dict(clang=subprocess.check_output([args.clang, '--version'], text=True),
                                  kernel=os.uname().release)
        inputs = roots['control']
        source = inputs / 'compiler/compiler.min'
        report['inputs']['fixed_selfcompile_source'] = digest(source)
        assert report['inputs']['fixed_selfcompile_source'] == '69be9f08cd580f8440876fb38788d0049daaab351e7a091914f3e638c0537db6'
        report['inputs']['neodb'] = {str(p.relative_to(owner)): digest(p)
                                     for p in sorted(owner.rglob('*')) if p.is_file()}
        report['inputs']['arms'] = {name: {str(p.relative_to(root)): digest(p)
                                      for p in [root / 'compiler/compiler.min', root / 'build/minyarc',
                                                root / 'runtime/minyar_runtime.c']}
                                   for name, root in roots.items()}
        cases = {}
        if args.only in (None, 'selfcompile'):
            cases['selfcompile'] = {name: ([root / 'build/minyarc', source,
                                            args.output / (name + '.ll')], inputs)
                                    for name, root in roots.items()}
        if args.only in (None, 'json'):
            for count in (500, 5000):
                fixture = args.output / f'history-{count}.json'
                fixture.write_text(subprocess.check_output(['python3', inputs / 'benchmarks/json/history.py', str(count)], text=True))
                values = json.loads(fixture.read_text())['runs']
                expected = f'{count * 20}\n{20 * sum(len(v["id"]) + len(v["prompt"]) + len(v["response"]["text"]) + len(v["response"]["sources"]) for v in values)}\n'
                report['inputs'][fixture.name] = digest(fixture)
                commands = {}
                for name, root in roots.items():
                    exe = args.output / (name + '-json')
                    run([root / 'minyar', '--release', '--memory-profile', 'system',
                         inputs / 'benchmarks/json/history-parse.min', '-o', exe], inputs, name + '-json-build')
                    report['inputs'][exe.name] = digest(exe)
                    commands[name] = ([exe, fixture, '20'], inputs)
                cases[f'json-{count}'] = commands
                report.setdefault('expected_stdout', {})[f'json-{count}'] = expected
        if args.only in (None, 'neodb'):
            commands = {}
            for name, root in roots.items():
                exe = args.output / (name + '-neodb')
                run([root / 'minyar', '--release', '--memory-profile', 'system',
                     owner / 'tests/sql/bench.min', '-o', exe], owner, name + '-neodb-build')
                report['inputs'][exe.name] = digest(exe)
                commands[name] = ([exe], owner)
            cases['neodb'] = commands
        if args.only in (None, 'craft'):
            if not env.get('DISPLAY'):
                raise RuntimeError('Actual craft needs a working DISPLAY; use xvfb-run on own Boat')
            report['graphics'] = subprocess.check_output(['glxinfo', '-B'], env=env, text=True)
            for name, root in roots.items():
                exe = args.output / (name + '-craft')
                run([root / 'minyar', '--release', '--memory-profile', 'system',
                     inputs / 'examples/craft/main.min', '-o', exe], inputs, name + '-craft-build')
                report['inputs'][exe.name] = digest(exe)
            for scenario in ('build', 'edit'):
                cases['craft-' + scenario] = {name: ([args.output / (name + '-craft'), '--benchmark', scenario], inputs)
                                               for name in roots}
        for case, commands in cases.items():
            for repeat in range(args.repeats + 1):
                order = ('control', 'candidate') if repeat % 2 == 0 else ('candidate', 'control')
                for arm in order:
                    argv, cwd = commands[arm]
                    sample = run(argv, cwd, case + '-' + arm,
                                 args.compile_batch if case == 'selfcompile' else 1)
                    if case.startswith('json'):
                        assert sample['stdout'] == report['expected_stdout'][case]
                    if case == 'selfcompile':
                        if arm == 'candidate':
                            assert (args.output / 'control.ll').read_bytes() == (args.output / 'candidate.ll').read_bytes()
                    if case == 'neodb':
                        parsed = re.findall(r'^(.+): (\d+) parses in (\d+) ms = \d+ ns/parse \(ok (\d+)\)$', sample['stdout'], re.M)
                        assert len(parsed) == 7 and all(n == ok and int(n) == (10000 if title == 'TPC-H Q1' else 100000) for title, n, ms, ok in parsed)
                        sample['statement_ms'] = {title: int(ms) for title, n, ms, ok in parsed}
                    report['observations'].append(dict(case=case, arm=arm, repeat=repeat,
                                                       warmup=repeat == 0, **sample))
                    save()
                print(case, repeat, flush=True)
            measured = [o for o in report['observations'] if o['case'] == case and not o['warmup']]
            medians = {arm: statistics.median(o['cpu_seconds'] for o in measured if o['arm'] == arm) for arm in roots}
            ratio = medians['candidate'] / medians['control']
            verdict = dict(cpu_medians=medians, candidate_control_ratio=ratio, passed=ratio <= 1.01)
            if case == 'neodb':
                verdict['statements'] = {}
                for title in measured[0]['statement_ms']:
                    times = {arm: statistics.median(o['statement_ms'][title] for o in measured if o['arm'] == arm) for arm in roots}
                    value = times['candidate'] / times['control'] if times['control'] else None
                    verdict['statements'][title] = dict(median_ms=times, ratio=value, passed=value is not None and value <= 1.01)
                verdict['passed'] &= all(v['passed'] for v in verdict['statements'].values())
            report['ratios'][case] = verdict
            save()
        passed = all(v['passed'] for v in report['ratios'].values())
        report['status'] = ('linux-subset-pass' if args.only else 'linux-pass') if passed else 'linux-fail'
        save()
        print(json.dumps(report['ratios'], indent=2), flush=True)
        if not passed:
            raise SystemExit('Unchanged 1% gate failed; raw evidence retained')


if __name__ == '__main__':
    main()
