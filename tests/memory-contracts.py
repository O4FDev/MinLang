#!/usr/bin/env python3
"""Run shared memory contracts against a frozen compiler/runtime pair.

smoke: existing CLI, language, modules, files and exit-status smoke cases.
standard: smoke plus C ownership model, alias/recursive/graph language tests.
extended: standard plus general/adversarial regressions and independent bounded
runtime models. Language executions cover O0/O2; sanitizers instrument both
generated LLVM and C. No performance suite or baseline update is invoked.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROFILES = {
    'eager': [],
    'system': ['-DMINYAR_SYSTEM_HEAP=1'],
    'fixed': ['-DMINYAR_BOUNDED_HEAP=1'],
    'lazy': ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_LAZY_HEAP=1'],
}
LANGUAGE = ('ownership.py', 'recursive-data.py', 'production-memory.py')


class Failure(Exception):
    pass


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def protected_inputs():
    paths = {ROOT / 'build/performance-baseline.json'}
    for path in (ROOT / 'tests').rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and (
            any(word in path.name for word in ('performance', 'scaling', 'budget', 'baseline'))
            or 'performance' in path.relative_to(ROOT / 'tests').parts
        ):
            paths.add(path)
    paths.update((ROOT / 'build').glob('*baseline*.json'))
    return {str(path.relative_to(ROOT)): digest(path) for path in sorted(paths)}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--compiler', type=Path, default=ROOT / 'build/minyarc')
    parser.add_argument('--runtime-source', type=Path, default=ROOT / 'runtime/minyar_runtime.c',
                        help='Path to minyar_runtime.c; sibling headers are snapshotted with it.')
    parser.add_argument('--level', choices=('smoke', 'standard', 'extended'), default='standard')
    parser.add_argument('--profiles', nargs='+', choices=PROFILES, default=['eager', 'system', 'fixed', 'lazy'])
    parser.add_argument('--mode', choices=('native', 'sanitize', 'both'), default='both')
    parser.add_argument('--budgets', type=int, nargs='+', default=[32])
    parser.add_argument('--clang', default=os.environ.get('CLANG', 'clang'))
    parser.add_argument('--timeout', type=float, default=600,
                        help='Maximum seconds per suite/build, including its children (default: 600).')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0 or any(k < 1 or k > 1024 for k in args.budgets):
        parser.error('timeout must be positive and cleanup budgets must be 1..1024')
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='minyar-memory-contracts-', dir=args.output_dir)).resolve()
    stage = evidence / 'snapshot'
    (evidence / 'logs').mkdir()
    profiles = list(dict.fromkeys(args.profiles))
    modes = ['native', 'sanitize'] if args.mode == 'both' else [args.mode]
    protected = protected_inputs()
    report = {
        'status': 'running', 'level': args.level, 'profiles': profiles,
        'modes': modes, 'budgets': list(dict.fromkeys(args.budgets)),
        'invocation': [sys.executable, *sys.argv], 'sources': [], 'checks': [],
        'protected_before': protected,
        'scope': 'Correctness only. No timing guarantee, compiler-arena leak claim, '
                 'launcher-wrapper coverage, or implicit unwinding on explicit exit. '
                 'Smoke uses the selected compiler directly; normal return is checked '
                 'by a test-only cleanup oracle. Runtime sanitizers do not instrument '
                 'the supplied compiler executable.',
    }
    report_path = evidence / 'results.json'

    def save():
        report_path.write_text(json.dumps(report, indent=2) + '\n')

    def snapshot(source, relative):
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        report['sources'].append({'source': str(source.resolve()), 'path': str(relative), 'sha256': digest(target)})
        return target

    def execute(label, command, environment, cwd=stage):
        log = evidence / 'logs' / f'{len(report["checks"]):03d}-{label}.log'
        row = {'label': label, 'command': list(map(str, command)), 'log': str(log),
               'cwd': str(cwd), 'timeout_seconds': args.timeout, 'timed_out': False,
               'environment': {key: value for key, value in environment.items()
                               if key.startswith(('MINYAR_', 'ASAN_', 'UBSAN_'))}}
        stdout = stderr = ''
        process = None
        try:
            process = subprocess.Popen(row['command'], cwd=cwd, env=environment,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, errors='replace', start_new_session=True)
            try:
                stdout, stderr = process.communicate(timeout=args.timeout)
                row['returncode'] = process.returncode
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
                row.update(returncode=None, timed_out=True)
        except OSError as error:
            row['returncode'] = None
            stderr = str(error)
        except KeyboardInterrupt:
            if process is not None:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
            row['returncode'] = None
            raise
        finally:
            log.write_text('$ ' + shlex.join(row['command']) + '\n\nSTDOUT\n' + stdout + '\nSTDERR\n' + stderr)
            report['checks'].append(row)
            save()
        if row['returncode'] != 0:
            raise Failure(f'{label}: {"timed out" if row["timed_out"] else "failed"}; see {log}')
        print(f'PASS {label}', flush=True)
        return stdout

    save()
    try:
        compiler = snapshot(args.compiler.resolve(), Path('build/minyarc'))
        snapshot(args.runtime_source.resolve(), Path('runtime/minyar_runtime.c'))
        for header in sorted(args.runtime_source.resolve().parent.glob('*.h')):
            snapshot(header, Path('runtime') / header.name)
        for directory in ('tests', 'examples'):
            for path in sorted((ROOT / directory).rglob('*')):
                if path.is_file() and '__pycache__' not in path.parts:
                    snapshot(path, path.relative_to(ROOT))
        if args.level == 'extended':
            for name in ('production-live-oracle', 'production-frame-oracle',
                         'production-idle-service', 'production-virtual-stress'):
                path = Path('experiments/memory') / (name + '.c')
                snapshot(ROOT / path, path)
        clang = shutil.which(args.clang)
        if clang is None:
            raise Failure(f'C compiler not found: {args.clang}')
        # Ignore inherited test artifact selectors so they cannot silently test
        # an unrelated compiler/runtime. Record generation controls explicitly.
        environment = {key: value for key, value in os.environ.items() if not key.startswith('MINYAR_TEST_')}
        environment.update(ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',
                           UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        environment.update(MINYAR_TEST_COMPILER=str(compiler), MINYAR_TEST_CLANG=clang)
        report['environment'] = {key: value for key, value in environment.items()
                                 if key.startswith(('MINYAR_', 'ASAN_', 'UBSAN_'))}
        report['clang_version'] = execute('clang-version', [clang, '--version'], environment)
        report['compiler_banner'] = execute('compiler-version', [compiler], environment)
        for profile in profiles:
            budgets = [32] if profile == 'eager' else report['budgets']
            for budget in budgets:
                for mode in modes:
                    label = f'{profile}-k{budget}-{mode}'
                    flags = ['-O2'] if mode == 'native' else ['-O1', '-g', '-fsanitize=address,undefined']
                    backend = [*PROFILES[profile], f'-DMINYAR_RC_POLL_BUDGET={budget}']
                    runtime = stage / 'build/minyar-runtime.o'
                    execute(label + '-runtime', [clang, '-std=c11', *flags, *backend, '-c',
                            stage / 'tests/memory-contracts-runtime.c', '-o', runtime], environment)
                    link_flags = [] if mode == 'native' else ['-fsanitize=address,undefined']
                    selected_env = {**environment, 'MINYAR_TEST_RUNTIME': str(runtime),
                                    'MINYAR_TEST_LINK_FLAGS': shlex.join(link_flags)}
                    # smoke.sh supports a clang override but predates link flags.
                    # This test-only adapter adds sanitizer attributes to a copy
                    # of its IR, preserving its compiler-determinism assertion.
                    adapter = stage / 'build' / ('smoke-clang-' + label)
                    adapter.write_text('#!' + sys.executable + '\n'
                        'import subprocess, sys\nfrom pathlib import Path\n'
                        f'sys.path.insert(0, {str(stage / "tests")!r})\n'
                        'from llvm_sanitizer import prepare_llvm_for_link\n'
                        f'flags = {link_flags!r}\nargs = sys.argv[1:]\n'
                        'for i, arg in enumerate(args):\n'
                        '    if flags and arg.endswith(".ll"):\n'
                        '        original = Path(arg); copy = original.with_suffix(".sanitized.ll")\n'
                        '        copy.write_bytes(original.read_bytes())\n'
                        '        prepare_llvm_for_link(copy, flags); args[i] = str(copy)\n'
                        f'raise SystemExit(subprocess.call([{clang!r}, *flags, *args]))\n')
                    adapter.chmod(0o755)
                    execute(label + '-smoke', ['sh', stage / 'tests/smoke.sh'],
                            {**selected_env, 'MINYAR_TEST_CLANG': str(adapter)})
                    # Keep artifacts before another profile reuses smoke paths.
                    shutil.copytree(stage / 'build/smoke', evidence / 'artifacts' / label / 'smoke')
                    shutil.copy2(runtime, evidence / 'artifacts' / label / 'runtime.o')
                    if args.level != 'smoke':
                        if profile == 'eager':
                            unit = evidence / 'artifacts' / label / 'runtime-unit'
                            execute(label + '-unit-build', [clang, '-std=c11', *flags,
                                    stage / 'tests/runtime-unit.c', '-o', unit], environment)
                            execute(label + '-unit-model', [unit], environment)
                        scripts = LANGUAGE + (('regressions.py', 'adversarial.py') if args.level == 'extended' else ())
                        for script in scripts:
                            execute(label + '-' + Path(script).stem,
                                    [sys.executable, stage / 'tests' / script], selected_env)
        bounded = [profile for profile in profiles if profile != 'eager']
        if args.level == 'extended' and bounded:
            execute('independent-runtime-models', [sys.executable, stage / 'tests/memory-profile-regressions.py',
                    '--runtime-source', stage / 'runtime/minyar_runtime.c', '--profiles', *bounded,
                    '--budgets', *map(str, report['budgets']), '--mode', args.mode, '--clang', clang,
                    '--output-dir', evidence / 'runtime-models'], environment)
        report['status'] = 'passed'
    except (Failure, OSError, KeyboardInterrupt) as error:
        report['status'] = 'interrupted' if isinstance(error, KeyboardInterrupt) else 'failed'
        report['failure'] = str(error) or 'Interrupted'
    finally:
        report['protected_after'] = protected_inputs()
        report['protected_unchanged'] = protected == report['protected_after']
        if not report['protected_unchanged']:
            report['status'] = 'failed'
            report['protected_failure'] = 'A protected performance input changed during this run; inspect concurrent work.'
        save()
    print(f'{report["status"].upper()}: {report_path}', flush=True)
    if report.get('failure'):
        print(report['failure'], file=sys.stderr)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
