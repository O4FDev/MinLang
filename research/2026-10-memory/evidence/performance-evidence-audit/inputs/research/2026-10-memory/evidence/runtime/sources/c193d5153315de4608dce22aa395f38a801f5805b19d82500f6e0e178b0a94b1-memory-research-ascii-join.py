#!/usr/bin/env python3
"""Red/green scan-work experiment with unchanged borrowed-join service hooks."""
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
    parser.add_argument('--language', action='store_true')
    parser.add_argument('--profile', choices=['system', 'fixed', 'lazy', 'eager'], default='system')
    parser.add_argument('--budget', choices=[1, 32], type=int, default=32)
    parser.add_argument('--sanitize', action='store_true')
    args = parser.parse_args()
    parent = ROOT / 'build/memory-research-ascii-join'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent)).resolve()
    report = {'status': 'running', 'checks': [], 'sources': [], 'observations': [],
              'profile': args.profile, 'budget': args.budget, 'sanitize': args.sanitize,
              'scope': 'Instrumented scan/allocation/service counts, not timing; candidate stays external.'}
    backends = {'system': ['-DMINYAR_SYSTEM_HEAP=1'], 'eager': ['-DMINYAR_EAGER_RC=1'],
                'fixed': ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_BOUNDED_HEAP_BYTES=8388608'],
                'lazy': ['-DMINYAR_LAZY_HEAP=1', '-DMINYAR_BOUNDED_HEAP_BYTES=8388608']}
    flags = [*backends[args.profile], f'-DMINYAR_RC_POLL_BUDGET={args.budget}']
    flags += (['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
              if args.sanitize else ['-O2'])
    environment = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1',
                   'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
    report['environment'] = {key: environment[key] for key in ('ASAN_OPTIONS', 'UBSAN_OPTIONS')}
    for name in ['memory-research-ascii-join.c', 'memory-research-ascii-join.min',
                 'memory-research-ascii-join-generated.c', Path(__file__).name, 'clang_helpers.py',
                 'llvm_sanitizer.py']:
        source = ROOT / 'tests' / name
        target = evidence / 'tests' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        report['sources'].append({'source': str(source), 'snapshot': str(target.relative_to(evidence))})
    for variant in ('before', 'candidate'):
        for source in (ROOT / 'runtime').glob('minyar_*'):
            if source.is_file():
                target = evidence / variant / 'runtime' / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                report['sources'].append({'source': str(source), 'snapshot': str(target.relative_to(evidence))})
        runtime = evidence / variant / 'runtime/minyar_runtime.c'
        text = runtime.read_text()
        old = 'static MINYAR_COLD void build_text_index(MinyarText *text) {\n'
        new = old + '    research_index_builds++;\n    research_index_input_bytes += (size_t)text->byte_length;\n'
        assert text.count(old) == 1
        runtime.write_text(text.replace(old, new))
        ownership = evidence / variant / 'runtime/minyar_rc.h'
        text = ownership.read_text()
        old = '    if (rc_pending_count) return minyar_rc_poll(budget);'
        new = '''    research_service_calls++;
    if (rc_pending_count) {
        size_t work = minyar_rc_poll(budget);
        research_service_work += work;
        return work;
    }'''
        assert text.count(old) == 1
        ownership.write_text(text.replace(old, new))

    def save():
        for source in report['sources']:
            source['sha256'] = hashlib.sha256((evidence / source['snapshot']).read_bytes()).hexdigest()
        target = evidence / 'results.json'
        temporary = target.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(target)

    def execute(label, command, outcome='success'):
        check = {'label': label, 'command': command, 'expected': outcome}
        try:
            result = subprocess.run(command, text=True, capture_output=True, env=environment, timeout=60)
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
        if outcome == 'missing-metadata':
            assert result.returncode != 0 and 'certified ASCII joins must avoid' in result.stderr
        elif outcome == 'invalid-utf8':
            assert result.returncode == 1 and 'Text contained invalid UTF-8' in result.stderr
        else:
            assert result.returncode == 0, (label, result.stdout, result.stderr)
        return result

    print(f'Evidence: {evidence}', flush=True)
    try:
        for variant in ('before', 'candidate'):
            if variant == 'candidate':
                # Mutation occurs only after the baseline target has failed.
                runtime = evidence / variant / 'runtime/minyar_runtime.c'
                text = runtime.read_text()
                begin = text.index('static MinyarText *join_by_copying(')
                end = text.index('\nMinyarText *minyar_join_text(', begin)
                fragment = text[begin:end]
                old = '    return new_text(bytes, length, -1);'
                new = '''    long long characters =
        left->character_length == left->byte_length && right->character_length == right->byte_length
            ? length : -1;
    return new_text(bytes, length, characters);'''
                assert fragment.count(old) == 1
                runtime.write_text(text[:begin] + fragment.replace(old, new) + text[end:])
                report['candidate'] = {'old': old, 'new': new, 'status': 'test-only'}
            binary = evidence / (variant + '-native')
            runtime = evidence / variant / 'runtime/minyar_runtime.c'
            execute(variant + '-compile', clang_command(['clang', '-std=c11', '-Wall', '-Wextra',
                    '-Werror', *flags, '-DMINYAR_RESEARCH_INSTRUMENTED=1',
                    f'-DMINYAR_RESEARCH_RUNTIME="{runtime}"',
                    str(evidence / 'tests/memory-research-ascii-join.c'), '-o', str(binary)]))
            ordinary = execute(variant, [str(binary)])
            report['observations'].extend({'variant': variant, **json.loads(line)}
                                          for line in ordinary.stdout.splitlines())
            execute(variant + '-target', [str(binary), '--require-known-ascii'],
                    'missing-metadata' if variant == 'before' else 'success')
            execute(variant + '-malformed', [str(binary), '--invalid-utf8'], 'invalid-utf8')
        if args.language:
            compiler = evidence / 'minyarc'
            shutil.copy2(ROOT / 'build/minyarc', compiler)
            report['compiler_artifact_sha256'] = hashlib.sha256(compiler.read_bytes()).hexdigest()
            llvm = evidence / 'generated.ll'
            execute('language-compile', [str(compiler), str(evidence / 'tests/memory-research-ascii-join.min'), str(llvm)])
            report['generated_borrowed_join_calls'] = llvm.read_text().count('call ptr @minyar_join_text(')
            assert report['generated_borrowed_join_calls'] >= 2
            prepare_llvm_for_link(llvm, flags)
            expected = {'known': '65536\n8388736\n65536\n', 'unknown': '0\n8388736\n65536\n',
                        'no-query': '65536\n8388736\n65536\n', 'short': '8\n1152\n8\n',
                        'unicode': '256\n32896\n768\n'}
            generated_observations = {}
            for variant in ('before', 'candidate'):
                observer = evidence / variant / 'tests/memory-research-ascii-join-generated.c'
                observer.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(evidence / 'tests/memory-research-ascii-join-generated.c', observer)
                binary = evidence / (variant + '-language')
                execute(variant + '-language-link', clang_command(['clang', *flags, '-Wno-override-module',
                        '-DMINYAR_RESEARCH_INSTRUMENTED=1',
                        str(llvm), str(observer), '-o', str(binary)]))
                for mode in expected:
                    result = execute(variant + '-language-' + mode, [str(binary), mode, ''])
                    assert result.stdout == expected[mode]
                    observed = json.loads(result.stderr)
                    generated_observations[variant, mode] = observed
                    report['observations'].append({'variant': variant, 'generated_case': mode, **observed})
            assert generated_observations['before', 'known']['index_builds'] == 129
            assert generated_observations['candidate', 'known']['index_builds'] == 1
            assert generated_observations['before', 'short']['index_builds'] == 128
            assert generated_observations['candidate', 'short']['index_builds'] == 0
            for mode in ('unknown', 'no-query', 'unicode'):
                assert generated_observations['before', mode] == generated_observations['candidate', mode]
            for mode in expected:
                for metric in ('service_hooks', 'service_units'):
                    assert generated_observations['before', mode][metric] == generated_observations['candidate', mode][metric]
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
