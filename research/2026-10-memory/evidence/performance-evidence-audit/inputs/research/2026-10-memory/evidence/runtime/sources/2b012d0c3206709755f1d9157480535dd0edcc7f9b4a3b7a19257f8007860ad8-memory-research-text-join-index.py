#!/usr/bin/env python3
"""Unicode join regression matrix; optional generated-source sanitizer coverage."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from clang_helpers import clang_command
from llvm_sanitizer import prepare_llvm_for_link

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-dir', type=Path, default=ROOT / 'runtime')
    parser.add_argument('--profiles', nargs='+', choices=['eager', 'system', 'fixed', 'lazy'],
                        default=['eager', 'system', 'fixed', 'lazy'])
    parser.add_argument('--budgets', nargs='+', type=int, default=[1, 32])
    parser.add_argument('--mode', choices=['native', 'sanitize', 'all'], default='all')
    parser.add_argument('--language', action='store_true')
    args = parser.parse_args()
    if any(budget < 1 or budget > 1024 for budget in args.budgets):
        parser.error('cleanup budgets must be 1 through 1024')
    parent = ROOT / 'build/memory-research-text-join-index'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent)).resolve()
    report = {'status': 'running', 'invocation': [os.sys.executable, *os.sys.argv],
              'sources': [], 'checks': [], 'scope': 'Semantic Unicode/index regression, no timing claim.',
              'coverage': {'language_requested': args.language, 'c_runs': [],
                           'generated_runs': [], 'expected_traps': []}}
    for source in args.runtime_dir.glob('minyar_*'):
        if source.is_file():
            target = evidence / 'runtime' / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            report['sources'].append({'source': str(source.resolve()),
                                     'snapshot': str(target.relative_to(evidence)),
                                     'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    for name in ['memory-research-text-join-index.c', 'memory-research-text-join-index.min',
                 'memory-research-text-join-index.stdout', Path(__file__).name,
                 'clang_helpers.py', 'llvm_sanitizer.py']:
        source = ROOT / 'tests' / name
        target = evidence / 'tests' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        report['sources'].append({'source': str(source), 'snapshot': str(target.relative_to(evidence)),
                                 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    environment = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1',
                   'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
    report['environment'] = {key: environment[key] for key in ('ASAN_OPTIONS', 'UBSAN_OPTIONS')}

    def save():
        target = evidence / 'results.json'
        temporary = target.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(target)

    def execute(label, command, expected=0):
        check = {'label': label, 'command': command, 'expected': expected}
        try:
            result = subprocess.run(command, text=True, capture_output=True,
                                    env=environment, timeout=60)
        except subprocess.TimeoutExpired as error:
            check.update(returncode=None, timed_out=True, timeout_seconds=60,
                         stdout=str(error.stdout), stderr=str(error.stderr))
            report['checks'].append(check)
            save()
            raise
        check.update(returncode=result.returncode, timed_out=False,
                     stdout=result.stdout, stderr=result.stderr)
        report['checks'].append(check)
        save()
        assert result.returncode == expected, (label, result.stdout, result.stderr)
        if expected:
            assert 'Text contained invalid UTF-8' in result.stderr
        return result

    print(f'Evidence: {evidence}', flush=True)
    try:
        execute('clang-version', ['clang', '--version'])
        llvm = None
        if args.language:
            compiler = evidence / 'minyarc'
            shutil.copy2(ROOT / 'build/minyarc', compiler)
            report['compiler_artifact_sha256'] = hashlib.sha256(compiler.read_bytes()).hexdigest()
            llvm = evidence / 'generated.ll'
            execute('language-compile', [str(compiler),
                    str(evidence / 'tests/memory-research-text-join-index.min'), str(llvm)])
            report['generated_consuming_join_calls'] = llvm.read_text().count(
                'call ptr @minyar_join_text_take_left(')
            assert report['generated_consuming_join_calls'] >= 6
        configurations = [('o0', ['-O0']), ('o2', ['-O2'])] if args.mode != 'sanitize' else []
        if args.mode != 'native':
            configurations.append(('sanitize', ['-O1', '-g', '-fsanitize=address,undefined',
                                                '-fno-omit-frame-pointer']))
        profiles = {'eager': [], 'system': ['-DMINYAR_SYSTEM_HEAP=1'],
                    'fixed': ['-DMINYAR_BOUNDED_HEAP=1'],
                    'lazy': ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_LAZY_HEAP=1']}
        expected_configurations = [f'{profile}-k{budget}-{mode}'
                                   for profile in args.profiles
                                   for budget in ([32] if profile == 'eager' else args.budgets)
                                   for mode, _ in configurations]
        report['coverage']['expected_configurations'] = expected_configurations
        for profile in args.profiles:
            for budget in ([32] if profile == 'eager' else args.budgets):
                defines = [*profiles[profile], '-DMINYAR_BOUNDED_HEAP_BYTES=8388608',
                           f'-DMINYAR_RC_POLL_BUDGET={budget}']
                for mode, flags in configurations:
                    label = f'{profile}-k{budget}-{mode}'
                    binary = evidence / label
                    execute(label + '-compile', clang_command(['clang', '-std=c11', '-Wall',
                            '-Wextra', '-Werror', *flags, *defines,
                            str(evidence / 'tests/memory-research-text-join-index.c'), '-o', str(binary)]))
                    result = execute(label, [str(binary)])
                    assert len(result.stdout.splitlines()) == 18
                    report['coverage']['c_runs'].append({'configuration': label,
                                                        'semantic_cases': len(result.stdout.splitlines())})
                    execute(label + '-invalid-utf8', [str(binary), '--invalid-utf8'], 1)
                    report['coverage']['expected_traps'].append(label)
                    if llvm:
                        generated_llvm = llvm
                        if mode == 'sanitize':
                            generated_llvm = evidence / 'generated-sanitize.ll'
                            shutil.copyfile(llvm, generated_llvm)
                            prepare_llvm_for_link(generated_llvm, flags)
                        generated = evidence / (label + '-language')
                        execute(label + '-language-link', clang_command(['clang', *flags, *defines,
                                '-Wno-override-module', str(generated_llvm),
                                str(evidence / 'runtime/minyar_runtime.c'), '-o', str(generated)]))
                        actual = execute(label + '-language', [str(generated)])
                        expected = (evidence / 'tests/memory-research-text-join-index.stdout').read_text()
                        assert actual.stdout == expected, (label, actual.stdout, expected)
                        report['coverage']['generated_runs'].append(label)
                    print('PASS ' + label, flush=True)
        assert [run['configuration'] for run in report['coverage']['c_runs']] == expected_configurations
        assert report['coverage']['expected_traps'] == expected_configurations
        assert report['coverage']['generated_runs'] == (expected_configurations if args.language else [])
        assert len(report['checks']) == (5 if args.language else 3) * len(expected_configurations) + (2 if args.language else 1)
        report['summary'] = {'recorded_checks': len(report['checks']),
                             'c_configuration_runs': len(report['coverage']['c_runs']),
                             'generated_executions': len(report['coverage']['generated_runs']),
                             'expected_utf8_traps': len(report['coverage']['expected_traps'])}
        print('Coverage: ' + json.dumps(report['summary']), flush=True)
        report['status'] = 'passed'
    except KeyboardInterrupt:
        report['status'] = 'interrupted'
        raise
    except Exception as error:
        report['status'] = 'failed'
        report['failure'] = str(error)
        raise
    finally:
        save()
        print(f'Results: {evidence / "results.json"}', flush=True)


if __name__ == '__main__':
    main()
