#!/usr/bin/env python3
"""Observe physical/logical uniqueness and retention without changing runtime policy."""
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
    parent = ROOT / 'build/memory-research-deferred-reuse'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent)).resolve()
    report = {'status': 'running', 'sources': [], 'checks': [], 'observations': [],
              'scope': 'Test-only explicit poll; no production reuse mechanism or timing/novelty claim.'}
    paths = [* (ROOT / 'runtime').glob('minyar_*'), Path(__file__),
             ROOT / 'tests/memory-research-deferred-reuse.c', ROOT / 'tests/clang_helpers.py']
    for source in paths:
        if source.is_file():
            relative = source.relative_to(ROOT)
            target = evidence / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            report['sources'].append({'source': str(source), 'snapshot': str(relative),
                                     'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
    environment = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1', 'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
    report['environment'] = {key: environment[key] for key in ('ASAN_OPTIONS', 'UBSAN_OPTIONS')}

    def save():
        target = evidence / 'results.json'
        temporary = target.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(target)

    def execute(label, command):
        result = subprocess.run(command, text=True, capture_output=True, env=environment, timeout=60)
        report['checks'].append({'label': label, 'command': command, 'returncode': result.returncode,
                                 'stdout': result.stdout, 'stderr': result.stderr})
        save()
        assert result.returncode == 0, (label, result.stdout, result.stderr)
        return result.stdout

    print(f'Evidence: {evidence}', flush=True)
    try:
        execute('compiler-version', ['clang', '--version'])
        for profile, backend in [('eager', []), ('system', ['-DMINYAR_SYSTEM_HEAP=1']),
                                  ('fixed', ['-DMINYAR_BOUNDED_HEAP=1']),
                                  ('lazy', ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_LAZY_HEAP=1'])]:
            for budget in ((32,) if profile == 'eager' else (1, 8, 32)):
                for mode, flags in [('native', ['-O2']), ('sanitize', ['-O1', '-g', '-fsanitize=address,undefined'])]:
                    label = f'{profile}-k{budget}-{mode}'
                    binary = evidence / label
                    execute(label + '-compile', clang_command(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', *flags,
                            *backend, '-DMINYAR_BOUNDED_HEAP_BYTES=8388608', f'-DMINYAR_RC_POLL_BUDGET={budget}',
                            str(evidence / 'tests/memory-research-deferred-reuse.c'), '-o', str(binary)]))
                    for action in ('standard', 'pre-service'):
                        observations = [json.loads(line) for line in execute(label + '-' + action, [str(binary), action, '33']).splitlines()]
                        assert len(observations) == 5
                        for observed in observations:
                            eligible = observed['case'] in ('retired-alias', 'self-borrow')
                            if profile == 'eager':
                                expected = observed['case'] not in ('live-alias', 'live-view')
                            else:
                                expected = eligible and budget == 32 and action == 'pre-service'
                            assert observed['reused'] == int(expected), (label, action, observed)
                            if profile != 'eager':
                                assert observed['extra_service_work'] <= budget
                                assert observed['physical_before'] == observed['logical_owners'] + 1
                            report['observations'].append({'profile': profile, 'budget': budget, 'mode': mode, **observed})
                        save()
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
