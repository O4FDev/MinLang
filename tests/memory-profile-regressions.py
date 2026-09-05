#!/usr/bin/env python3
"""Snapshot and verify bounded-cleanup profiles without performance tests.

Focused: K32 with ASan/UBSan across system, fixed pool and lazy pool.
Full: K1/32/1024, native and ASan/UBSan across all three profiles.
Pool fragmentation, giant reservation, OOM and stale-pointer campaigns remain
in bounded/system/lazy-configurations.py and are not repeated here.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
STANDARD = ('recent-cursors', 'recent-fairness', 'immortal-reference-lists',
            'scalar-list-hotpath', 'idle-service')
INDEPENDENT = ('production-live-oracle', 'production-frame-oracle', 'production-idle-service')
VIRTUAL = 'production-virtual-stress'
PHASES = ('shared', 'frames', 'records', 'temporaries', 'graphs', 'bytes',
          'wrapped-bytes', 'frame-cache')
BACKEND_DEFINES = {'#define MINYAR_SYSTEM_HEAP 1', '#define MINYAR_BOUNDED_HEAP 1',
                   '#define MINYAR_LAZY_HEAP 1'}


class Failure(Exception):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def as_text(value):
    return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value or ''


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--runtime-source', type=Path, default=ROOT / 'runtime/minyar_runtime.c')
    parser.add_argument('--fixture-dir', type=Path,
                        help='Original runtime fixtures; defaults to the chosen runtime project/tests, then repository/tests.')
    parser.add_argument('--suite', choices=('focused', 'full'), default='focused')
    parser.add_argument('--profiles', nargs='+', choices=('system', 'fixed', 'lazy'),
                        default=['system', 'fixed', 'lazy'])
    parser.add_argument('--budgets', nargs='+', type=int, help='Override suite budgets (each 1..1024).')
    parser.add_argument('--mode', choices=('native', 'sanitize', 'both'), help='Override suite instrumentation.')
    parser.add_argument('--fixtures', nargs='+', choices=STANDARD + INDEPENDENT + (VIRTUAL,),
                        help='Run only selected fixtures; dependencies are still snapshotted.')
    parser.add_argument('--clang', default=os.environ.get('CLANG', 'clang'))
    parser.add_argument('--compile-timeout', type=float, default=60)
    parser.add_argument('--run-timeout', type=float, default=45)
    parser.add_argument('--output-dir', type=Path, help='Parent for a retained, uniquely named evidence directory.')
    args = parser.parse_args()
    if args.compile_timeout <= 0 or args.run_timeout <= 0:
        parser.error('timeouts must be positive')
    budgets = list(dict.fromkeys(args.budgets or ([32] if args.suite == 'focused' else [1, 32, 1024])))
    if any(budget < 1 or budget > 1024 for budget in budgets):
        parser.error('cleanup budgets must be between 1 and 1024')
    profiles = list(dict.fromkeys(args.profiles))
    mode = args.mode or ('sanitize' if args.suite == 'focused' else 'both')
    modes = ['native', 'sanitize'] if mode == 'both' else [mode]
    selected = list(dict.fromkeys(args.fixtures or (STANDARD + INDEPENDENT + (VIRTUAL,))))
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='minyar-memory-profiles-', dir=args.output_dir)).resolve()
    (evidence / 'logs').mkdir()
    report = {'status': 'running', 'suite': args.suite, 'profiles': profiles, 'budgets': budgets,
              'modes': modes, 'fixtures': selected, 'runtime_source': str(args.runtime_source.resolve()),
              'invocation': [sys.executable, *sys.argv],
              'sources': [], 'staged_sources': [], 'checks': [], 'skipped': [],
              'scope': 'Correctness only; no performance baselines, wall-time guarantees or heavyweight allocator campaigns.'}
    report_path = evidence / 'results.json'

    def save():
        report_path.write_text(json.dumps(report, indent=2) + '\n')

    def execute(label, command, timeout, environment, cwd=None):
        number = len(report['checks'])
        log = evidence / 'logs' / f'{number:04d}-{label}.log'
        result = {'label': label, 'command': command, 'timeout_seconds': timeout, 'log': str(log),
                  'cwd': str(cwd or ROOT)}
        try:
            checked = subprocess.run(command, capture_output=True, text=True, timeout=timeout,
                                     env=environment, cwd=cwd or ROOT)
            stdout, stderr = checked.stdout, checked.stderr
            result.update(returncode=checked.returncode, timed_out=False)
        except subprocess.TimeoutExpired as error:
            stdout, stderr = as_text(error.stdout), as_text(error.stderr)
            result.update(returncode=None, timed_out=True)
            stderr += f'\nTimed out after {timeout:g} seconds: {shlex.join(command)}\n'
        except OSError as error:
            stdout, stderr = '', str(error)
            result.update(returncode=None, timed_out=False)
        log.write_text('$ ' + shlex.join(command) + '\n\nSTDOUT\n' + stdout + '\nSTDERR\n' + stderr)
        report['checks'].append(result)
        save()
        if result['returncode'] != 0:
            raise Failure(f'{label}: {"timeout" if result["timed_out"] else "failed"}\n'
                          f'{(stdout + stderr)[-5000:]}\nFull log: {log}')
        return stdout

    def source(path, relative):
        try:
            data = path.read_bytes()
        except OSError as error:
            raise Failure(f'Cannot snapshot {path}: {error}') from error
        report['sources'].append({'path': str(path.resolve()), 'snapshot_path': str(relative), 'sha256': digest(data)})
        target = evidence / 'originals' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return data

    save()
    print(f'Evidence retained at {evidence}', flush=True)
    try:
        source(Path(__file__).resolve(), Path('tests/memory-profile-regressions.py'))
        report['snapshot_replay'] = [sys.executable, str(evidence / 'originals/tests/memory-profile-regressions.py'),
            '--runtime-source', str(evidence / 'originals/runtime/minyar_runtime.c'),
            '--fixture-dir', str(evidence / 'originals/tests'), '--suite', args.suite,
            '--profiles', *profiles, '--budgets', *map(str, budgets), '--mode', mode,
            '--fixtures', *selected, '--clang', args.clang,
            '--compile-timeout', str(args.compile_timeout), '--run-timeout', str(args.run_timeout)]
        runtime = args.runtime_source.resolve()
        runtime_files = {Path('runtime/minyar_runtime.c'): source(runtime, Path('runtime/minyar_runtime.c'))}
        for header in sorted(runtime.parent.glob('*.h')):
            relative = Path('runtime') / header.name
            runtime_files[relative] = source(header, relative)
        needed = set(selected)
        if 'production-frame-oracle' in needed:
            needed.add('production-live-oracle')
        fixture_files = {}
        for name in sorted(needed):
            if name in INDEPENDENT or name == VIRTUAL:
                relative = Path('experiments/memory') / (name + '.c')
                path = ROOT / relative
            else:
                relative = Path('tests') / (name + '.c')
                roots = [args.fixture_dir] if args.fixture_dir else [runtime.parent.parent / 'tests', ROOT / 'tests']
                path = next((directory / (name + '.c') for directory in roots
                             if (directory / (name + '.c')).is_file()), None)
                if path is None:
                    raise Failure(f'Missing fixture {name}.c; searched {roots}. Use --fixture-dir after preserving originals.')
            fixture_files[relative] = source(path, relative)
        environment = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1',
                       'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
        report['environment'] = {name: environment[name] for name in ('ASAN_OPTIONS', 'UBSAN_OPTIONS')}
        version = execute('compiler-version', [args.clang, '--version'], args.compile_timeout, environment)
        report['clang_version'] = version.splitlines()[0] if version.strip() else '(no version stdout)'
        for profile in profiles:
            stage = evidence / 'profiles' / profile
            for relative, data in {**runtime_files, **fixture_files}.items():
                transformations = []
                if relative in fixture_files:
                    text = data.decode('utf-8')
                    lines = text.splitlines(keepends=True)
                    text = ''.join(line for line in lines if line.strip() not in BACKEND_DEFINES)
                    transformations.append('Backend defines selected by compile flags; original assertions otherwise retained.')
                    if profile == 'system' and relative.stem in STANDARD:
                        text, replacements = re.subn(r'\bminyar_pool_used\b', 'rc_heap_allocation_count', text)
                        if replacements:
                            transformations.append(f'{replacements} pool-empty counter reference(s) use outstanding system allocations.')
                    elif profile != 'system' and relative.stem in STANDARD:
                        text, replacements = re.subn(r'\brc_heap_allocation_count\b', 'minyar_pool_used', text)
                        if replacements:
                            transformations.append(f'{replacements} system-empty counter reference(s) use outstanding pool bytes.')
                    data = text.encode('utf-8')
                target = stage / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                report['staged_sources'].append({'profile': profile, 'path': str(target),
                                                 'sha256': digest(data), 'transformations': transformations})
            backend = ['-DMINYAR_SYSTEM_HEAP=1'] if profile == 'system' else ['-DMINYAR_BOUNDED_HEAP=1']
            if profile == 'lazy':
                backend.append('-DMINYAR_LAZY_HEAP=1')
            if profile == 'system' and VIRTUAL in selected:
                report['skipped'].append({'profile': profile, 'fixture': VIRTUAL,
                    'reason': 'Pool byte/capacity and coalescing assertions require a pool; system uses exact object/byte ownership and allocation-count recovery checks.'})
            for budget in budgets:
                for instrumentation in modes:
                    for name in selected:
                        if name == VIRTUAL and profile == 'system':
                            continue
                        relative = (Path('tests') if name in STANDARD else Path('experiments/memory')) / (name + '.c')
                        label = f'{profile}-k{budget}-{instrumentation}-{name}'
                        binary = evidence / 'bin' / label
                        binary.parent.mkdir(exist_ok=True)
                        flags = ['-O2'] if instrumentation == 'native' else ['-O1', '-g', '-fsanitize=address,undefined']
                        command = [args.clang, '-std=c11', *flags, *backend,
                                   f'-DMINYAR_RC_POLL_BUDGET={budget}', str(stage / relative), '-o', str(binary)]
                        execute(label + '-compile', command, args.compile_timeout, environment)
                        phases = PHASES if name == VIRTUAL else (None,)
                        for phase in phases:
                            execute(label + ('-' + phase if phase else ''),
                                    [str(binary)] + ([phase] if phase else []), args.run_timeout, environment)
                        print(f'PASS {label}' + (' (8 retention phases)' if name == VIRTUAL else ''), flush=True)
        report['status'] = 'passed'
        report['compiled_fixtures'] = sum(check['label'].endswith('-compile') for check in report['checks'])
        report['runtime_checks'] = len(report['checks']) - report['compiled_fixtures'] - 1
        save()
        for skipped in report['skipped']:
            print(f'SKIP {skipped["profile"]}/{skipped["fixture"]}: {skipped["reason"]}', flush=True)
        print(f'PASS: {report["runtime_checks"]} runtime checks; reproducible commands, hashes and logs: {report_path}', flush=True)
        return 0
    except (Failure, KeyboardInterrupt) as error:
        report['status'] = 'interrupted' if isinstance(error, KeyboardInterrupt) else 'failed'
        report['failure'] = str(error) or 'Interrupted by user'
        save()
        print(f'FAIL: {report["failure"]}\nSnapshot and diagnostics retained: {evidence}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
