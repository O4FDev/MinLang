#!/usr/bin/env python3
"""Compile unchanged Minyar syntax and observe deferred-owner join decisions."""
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
EXPECTED = '65\n32769\na\n!\n65\n32768\nh\n32769\n65\n16384\nh\n32769\n65\n65536\na\n'


def main():
    parent = ROOT / 'build/memory-research-deferred-generated'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent)).resolve()
    report = {'status': 'running', 'sources': [], 'checks': [], 'observations': [],
              'scope': 'Generated Minyar semantics and observer data; explicit extra poll is test-only, not accepted runtime policy.'}
    for source in [*(ROOT / 'runtime').glob('minyar_*'), Path(__file__), ROOT / 'tests/clang_helpers.py',
                   ROOT / 'tests/llvm_sanitizer.py',
                   ROOT / 'tests/memory-research-deferred-generated.min', ROOT / 'tests/memory-research-deferred-generated.c']:
        if source.is_file():
            target = evidence / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            report['sources'].append({'source': str(source), 'snapshot': str(target.relative_to(evidence)),
                                     'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    compiler = evidence / 'minyarc'
    shutil.copy2(ROOT / 'build/minyarc', compiler)
    report['compiler_artifact_sha256'] = hashlib.sha256(compiler.read_bytes()).hexdigest()
    environment = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1', 'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
    report['environment'] = {key: environment[key] for key in ('ASAN_OPTIONS', 'UBSAN_OPTIONS')}

    def save():
        target = evidence / 'results.json'
        temporary = target.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(target)

    def execute(label, command, action='standard'):
        selected_environment = environment.copy()
        if action == 'pre-service':
            selected_environment['MINYAR_RESEARCH_PRE_SERVICE'] = '1'
        else:
            selected_environment.pop('MINYAR_RESEARCH_PRE_SERVICE', None)
        check = {'label': label, 'command': command, 'action': action}
        try:
            result = subprocess.run(command, text=True, capture_output=True, env=selected_environment, timeout=60)
        except subprocess.TimeoutExpired as error:
            check.update(returncode=None, timed_out=True, timeout_seconds=60,
                         stdout=str(error.stdout), stderr=str(error.stderr))
            report['checks'].append(check)
            save()
            raise
        check.update(returncode=result.returncode, timed_out=False, stdout=result.stdout, stderr=result.stderr)
        report['checks'].append(check)
        save()
        assert result.returncode == 0, (label, result.stdout, result.stderr)
        return result

    print(f'Evidence: {evidence}', flush=True)
    try:
        execute('compiler-version', ['clang', '--version'])
        llvm = evidence / 'generated.ll'
        execute('generated-compile', [str(compiler), str(evidence / 'tests/memory-research-deferred-generated.min'), str(llvm)])
        generated = llvm.read_text()
        report['generated_consuming_join_calls'] = generated.count('call ptr @minyar_join_text_take_left(')
        assert report['generated_consuming_join_calls'] >= 4
        for profile, backend in [('eager', []), ('system', ['-DMINYAR_SYSTEM_HEAP=1']),
                                  ('fixed', ['-DMINYAR_BOUNDED_HEAP=1']),
                                  ('lazy', ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_LAZY_HEAP=1'])]:
            for budget in ((32,) if profile == 'eager' else (1, 8, 32)):
                for mode, flags in [('native', ['-O2']), ('sanitize', ['-O1', '-g', '-fsanitize=address,undefined'])]:
                    label = f'{profile}-k{budget}-{mode}'
                    binary = evidence / label
                    generated_llvm = llvm
                    if mode == 'sanitize':
                        generated_llvm = evidence / 'generated-sanitize.ll'
                        shutil.copyfile(llvm, generated_llvm)
                        prepare_llvm_for_link(generated_llvm, flags)
                    execute(label + '-link', clang_command(['clang', *flags, '-Wno-override-module', *backend,
                            '-DMINYAR_BOUNDED_HEAP_BYTES=8388608', f'-DMINYAR_RC_POLL_BUDGET={budget}',
                            str(generated_llvm), str(evidence / 'tests/memory-research-deferred-generated.c'), '-o', str(binary)]))
                    for action in ('standard', 'pre-service'):
                        result = execute(label + '-' + action, [str(binary)], action)
                        assert result.stdout == EXPECTED, (label, action, result.stdout)
                        observations = [json.loads(line) for line in result.stderr.splitlines()]
                        assert len(observations) == 4, (label, action, observations)
                        assert not observations[1]['header_reused'] and not observations[2]['header_reused']
                        for position, observed in enumerate(observations):
                            assert observed['physical_after_service'] >= 1
                            assert observed['extra_work'] <= budget
                            report['observations'].append({'profile': profile, 'budget': budget, 'mode': mode,
                                    'action': action, 'case': ('retired-alias', 'live-alias', 'live-view', 'self-borrow')[position], **observed})
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
