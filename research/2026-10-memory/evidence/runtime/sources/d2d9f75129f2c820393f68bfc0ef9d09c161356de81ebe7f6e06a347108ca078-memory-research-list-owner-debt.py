#!/usr/bin/env python3
"""Pressure controls kill an append guard that ignores frame/chunk tasks."""
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
    parser.add_argument('--mode', choices=['native', 'all'], default='all')
    args = parser.parse_args()
    parent = ROOT / 'build/memory-research-list-owner-debt'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent)).resolve()
    report = {'status': 'running', 'sources': [], 'checks': [],
              'scope': 'Owner queue pressure; object-only append guard mutant must fail.'}
    for source in [ROOT / 'tests/memory-research-list-owner-debt.c', Path(__file__),
                   ROOT / 'tests/clang_helpers.py']:
        target = evidence / source.name
        shutil.copyfile(source, target)
        report['sources'].append({'source': str(source), 'snapshot': target.name,
                                 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    for variant in ('correct', 'object-only'):
        for source in (ROOT / 'runtime').glob('minyar_*'):
            if source.is_file():
                target = evidence / variant / 'runtime' / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                report['sources'].append({'source': str(source),
                                         'snapshot': str(target.relative_to(evidence)),
                                         'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    fragment = evidence / 'object-only/runtime/minyar_collections.h'
    original = fragment.read_text()
    old = '    if (rc_pending_count) {\n'
    new = '    if (rc_bounded_head || rc_bounded_recent_head || rc_bounded_active) {\n'
    assert original.count(old) == 1
    fragment.write_text(original.replace(old, new))
    report['mutant'] = {'original_sha256': hashlib.sha256(original.encode()).hexdigest(),
                        'mutant_sha256': hashlib.sha256(fragment.read_bytes()).hexdigest(),
                        'old': old, 'new': new}
    for source in report['sources']:
        source['sha256'] = hashlib.sha256((evidence / source['snapshot']).read_bytes()).hexdigest()
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
            check.update(returncode=None, timed_out=True, stdout=str(error.stdout),
                         stderr=str(error.stderr), timeout_seconds=60)
            report['checks'].append(check)
            save()
            raise
        check.update(returncode=result.returncode, timed_out=False,
                     stdout=result.stdout, stderr=result.stderr)
        report['checks'].append(check)
        save()
        assert result.returncode == expected, (label, result.stdout, result.stderr)
        if expected:
            assert 'bounded heap is exhausted' in result.stderr
        elif not label.endswith('-compile'):
            assert 'owner queue debt: contents and complete pool recovery verified' in result.stdout

    print(f'Evidence: {evidence}', flush=True)
    try:
        configurations = [('native', ['-O2'])]
        if args.mode == 'all':
            configurations.append(('sanitize', ['-O1', '-g', '-fsanitize=address,undefined',
                                                '-fno-omit-frame-pointer']))
        for budget in (1, 32):
            for mode, flags in configurations:
                for variant in ('correct', 'object-only'):
                    label = f'k{budget}-{mode}-{variant}'
                    binary = evidence / label
                    runtime = evidence / variant / 'runtime/minyar_runtime.c'
                    execute(label + '-compile', clang_command(['clang', '-std=c11', '-Wall',
                            '-Wextra', '-Werror', *flags, f'-DMINYAR_RC_POLL_BUDGET={budget}',
                            f'-DMINYAR_RESEARCH_RUNTIME="{runtime}"',
                            str(evidence / 'memory-research-list-owner-debt.c'), '-o', str(binary)]))
                    for queue in ('frame', 'chunk'):
                        execute(label + '-' + queue, [str(binary), queue],
                                1 if variant == 'object-only' else 0)
                        print('PASS ' + label + ' ' + queue, flush=True)
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
