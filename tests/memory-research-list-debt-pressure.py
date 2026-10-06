#!/usr/bin/env python3
"""Compare allocation success under retirement pressure against saved variants."""
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
    parser.add_argument('--before-runtime', type=Path, required=True)
    parser.add_argument('--unconditional-runtime', type=Path, required=True)
    args = parser.parse_args()
    parent = ROOT / 'build/memory-research-list-debt-pressure'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent)).resolve()
    report = {'invocation': [os.sys.executable, *os.sys.argv], 'sources': [], 'checks': [],
              'status': 'running', 'scope': 'Finite-pool success/failure boundary; no timing measurement.'}
    fixture = ROOT / 'tests/memory-research-list-debt-pressure.c'
    shutil.copyfile(fixture, evidence / fixture.name)
    shutil.copyfile(Path(__file__), evidence / Path(__file__).name)
    for name, directory in [('before', args.before_runtime), ('unconditional', args.unconditional_runtime), ('guarded', ROOT / 'runtime')]:
        target = evidence / name / 'runtime'
        target.mkdir(parents=True)
        for path in directory.glob('minyar_*'):
            if path.is_file():
                data = path.read_bytes()
                (target / path.name).write_bytes(data)
                report['sources'].append({'source': str(path.resolve()), 'snapshot': str((target / path.name).relative_to(evidence)),
                                         'sha256': hashlib.sha256(data).hexdigest()})
    environment = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1', 'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
    report['environment'] = {key: environment[key] for key in ('ASAN_OPTIONS', 'UBSAN_OPTIONS')}

    def save():
        target = evidence / 'results.json'
        temporary = target.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(target)

    def execute(label, command, expected=0):
        result = subprocess.run(command, env=environment, text=True, capture_output=True, timeout=60)
        report['checks'].append({'label': label, 'command': command, 'returncode': result.returncode, 'expected': expected,
                                 'stdout': result.stdout, 'stderr': result.stderr})
        save()
        assert result.returncode == expected, (label, result.stdout, result.stderr)
        if expected == 1:
            assert 'the bounded heap is exhausted' in result.stderr
        elif not label.endswith('-compile') and label != 'clang-version':
            assert 'complete pool recovery verified' in result.stdout

    print(f'Evidence: {evidence}', flush=True)
    try:
        execute('clang-version', ['clang', '--version'])
        for profile, backend in [('fixed', []), ('lazy', ['-DMINYAR_LAZY_HEAP=1'])]:
            for budget in (1, 32):
                for mode, flags in [('native', ['-O2']), ('sanitize', ['-O1', '-g', '-fsanitize=address,undefined'])]:
                    for variant in ('before', 'unconditional', 'guarded'):
                        label = f'{profile}-k{budget}-{mode}-{variant}'
                        binary = evidence / label
                        runtime = evidence / variant / 'runtime/minyar_runtime.c'
                        execute(label + '-compile', clang_command(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', *flags,
                                *backend, f'-DMINYAR_RC_POLL_BUDGET={budget}', f'-DMINYAR_RESEARCH_RUNTIME="{runtime}"',
                                str(evidence / fixture.name), '-o', str(binary)]))
                        execute(label, [str(binary)], 1 if variant == 'unconditional' else 0)
                        print('PASS ' + label + (' (expected OOM)' if variant == 'unconditional' else ''), flush=True)
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
