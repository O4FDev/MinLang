#!/usr/bin/env python3
"""Snapshot and check known-length List construction across runtime profiles."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-dir', type=Path, default=ROOT / 'runtime')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'build/memory-research-list-reserve')
    parser.add_argument('--mode', choices=('native', 'all'), default='all')
    parser.add_argument('--measure-counts', action='store_true', help='Report original counts without enforcing the improved allocation bound.')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=args.output_dir)).resolve()
    report = {'invocation': [os.sys.executable, *os.sys.argv], 'sources': [], 'checks': [],
              'scope': 'Correctness, allocation counts and retained arena bytes; no latency claim.',
              'status': 'running'}
    for path in [*args.runtime_dir.glob('minyar_*'), ROOT / '.clang-format',
                 Path(__file__), ROOT / 'tests/clang_helpers.py',
                 ROOT / 'tests/memory-research-list-reserve.c',
                 ROOT / 'tests/memory-research-list-reserve-arena.c',
                 ROOT / 'tests/memory-research-list-reserve.min']:
        if not path.is_file():
            continue
        relative = Path('runtime') / path.name if path.parent == args.runtime_dir else path.relative_to(ROOT)
        target = evidence / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        report['sources'].append({'path': str(path.resolve()), 'snapshot': str(relative),
                                  'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    environment = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1',
                   'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
    if args.measure_counts:
        environment['MINYAR_RESEARCH_MEASURE_COUNTS'] = '1'
    report['environment'] = {key: environment[key] for key in ('ASAN_OPTIONS', 'UBSAN_OPTIONS', 'MINYAR_RESEARCH_MEASURE_COUNTS') if key in environment}

    def save():
        target = evidence / 'results.json'
        temporary = target.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(target)

    def execute(label, command, expect=None):
        result = subprocess.run(command, cwd=evidence, env=environment, text=True,
                                capture_output=True, timeout=60)
        check = {'label': label, 'command': list(map(str, command)), 'returncode': result.returncode,
                 'stdout': result.stdout, 'stderr': result.stderr, 'expected_diagnostic': expect}
        report['checks'].append(check)
        save()
        passed = result.returncode == 0 if expect is None else result.returncode == 1 and expect in result.stderr
        if not passed:
            raise RuntimeError(f'{label}: {result.returncode}\n{result.stdout}\n{result.stderr}')

    profiles = {'eager': [], 'system': ['-DMINYAR_SYSTEM_HEAP=1'],
                'fixed': ['-DMINYAR_BOUNDED_HEAP=1'],
                'lazy': ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_LAZY_HEAP=1'], 'arena': []}
    configurations = [('o0', ['-O0']), ('o2', ['-O2'])]
    if args.mode == 'all':
        configurations.append(('sanitize', ['-O1', '-g', '-fsanitize=address,undefined']))
    print(f'Evidence: {evidence}', flush=True)
    try:
        execute('compiler-version', ['clang', '--version'])
        compiler = ROOT / 'build/minyarc'
        copied_compiler = evidence / 'minyarc'
        shutil.copy2(compiler, copied_compiler)
        report['compiler_artifact_sha256'] = hashlib.sha256(copied_compiler.read_bytes()).hexdigest()
        report['compiler_artifact_snapshot'] = str(copied_compiler)
        llvm = evidence / 'generated.ll'
        execute('generated-language-compile', [str(copied_compiler), str(evidence / 'tests/memory-research-list-reserve.min'), str(llvm)])
        expected_generated = f'1024\n37851\n1152\n0\n127\n{sum(i * 37 for i in range(1024)) + sum(range(128))}\n257\n256\nMINYAR\n258\nMINYAR\nNEW!\n'
        for profile, defines in profiles.items():
            for mode, flags in configurations:
                budgets = (1, 32) if profile in ('system', 'fixed', 'lazy') else (32,)
                for budget in budgets:
                    label = f'{profile}-{mode}-k{budget}'
                    binary = evidence / label
                    fixture = 'memory-research-list-reserve-arena.c' if profile == 'arena' else 'memory-research-list-reserve.c'
                    execute(label + '-compile', clang_command(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            *flags, *defines, '-DMINYAR_BOUNDED_HEAP_BYTES=8388608',
                            f'-DMINYAR_RC_POLL_BUDGET={budget}', str(evidence / 'tests' / fixture), '-o', str(binary)]))
                    execute(label, [str(binary)])
                    if profile != 'arena':
                        generated = evidence / (label + '-generated')
                        execute(label + '-generated-link', clang_command(['clang', *flags, *defines,
                                '-Wno-override-module', '-DMINYAR_BOUNDED_HEAP_BYTES=8388608',
                                f'-DMINYAR_RC_POLL_BUDGET={budget}', str(llvm),
                                str(evidence / 'runtime/minyar_runtime.c'), '-o', str(generated)]))
                        execute(label + '-generated-run', [str(generated)])
                        if report['checks'][-1]['stdout'] != expected_generated:
                            raise RuntimeError(f'{label} generated output mismatch: {report["checks"][-1]["stdout"]!r}')
                    if mode == 'o2' and profile != 'arena':
                        execute(label + '-overflow', [str(binary), 'overflow'], 'this List became too large.')
                        if profile in ('eager', 'system'):
                            for failure in ('oom-object', 'oom-data'):
                                execute(label + '-' + failure, [str(binary), failure], 'the computer ran out of memory.')
                        else:
                            execute(label + '-oom', [str(binary), 'oom-pool'], 'the bounded heap is exhausted')
                    print('PASS ' + label, flush=True)
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
