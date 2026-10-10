#!/usr/bin/env python3
"""Baseline-only generated escaped-literal assembly counts; no policy mutation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from clang_helpers import clang_command
from llvm_sanitizer import prepare_llvm_for_link

ROOT = Path(__file__).resolve().parents[1]
INPUTS = {'ascii': r'left\ncenter\tend', 'unicode': 'é\\n🙂\\éend',
          'unknown': r'left\ncenter\tend', 'no-query': r'left\ncenter\tend',
          'empty': '', 'single': 'one'}


def decode(source):
    output, count, position, first = [], 0, 0, 0
    while position < len(source):
        if source[position] == '\\' and position + 1 < len(source):
            if first < position:
                output.append(source[first:position])
                count += 1
            escaped = source[position + 1]
            output.append({'n': '\n', 'r': '\r', 't': '\t'}.get(escaped, escaped))
            count += 1
            position += 2
            first = position
        else:
            position += 1
    if first < position:
        output.append(source[first:])
        count += 1
    return ''.join(output), count


def expected(mode):
    raw = INPUTS[mode]
    value, parts = decode(raw)
    if mode == 'unknown':
        value += 'tail'
        parts += 1
    query = '' if mode == 'no-query' else f'{len(value)}\n{sum(map(ord, value))}\n'
    output = ('-10001\n-10002\n-10003\n' + query + '-10004\n' + query +
              '-10005\n' + value + '\n' + str(len(value.encode())) + '\n' + raw +
              '\n' + raw + '!\n-10006\n')
    return value, parts, output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot', action='store_true')
    args = parser.parse_args()
    parent = ROOT / 'build/memory-research-aggregate-join'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent))
    opaque = evidence / 'opaque-ascii.txt'
    opaque.write_text('tail')
    report = {'status': 'running', 'checks': [], 'sources': [], 'observations': [],
              'scope': 'Original compiler call-pattern projection, not full compiler execution. '
                       'Compiler-arena and ordinary system runtime are separate. Baseline only; no timing.'}
    for directory, paths in [('runtime', list((ROOT / 'runtime').glob('minyar_*'))),
                             ('tests', [Path(__file__), ROOT / 'tests/memory-research-aggregate-join.c',
                                        ROOT / 'tests/memory-research-aggregate-join.min',
                                        ROOT / 'tests/clang_helpers.py', ROOT / 'tests/llvm_sanitizer.py'])]:
        for source in paths:
            if source.is_file():
                target = evidence / directory / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                original = target
                if directory == 'runtime':
                    original = evidence / 'original/runtime' / source.name
                    original.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, original)
                report['sources'].append({'snapshot': str(original.relative_to(evidence)),
                                          'sha256': hashlib.sha256(original.read_bytes()).hexdigest()})
    compiler = evidence / 'minyarc'
    shutil.copy2(ROOT / 'build/minyarc', compiler)
    report['compiler_sha256'] = hashlib.sha256(compiler.read_bytes()).hexdigest()
    environment = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1',
                   'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
    report['environment'] = {key: environment[key] for key in ('ASAN_OPTIONS', 'UBSAN_OPTIONS')}

    def save():
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    def execute(label, argv):
        result = subprocess.run(argv, capture_output=True, text=True, env=environment, timeout=60)
        report['checks'].append({'label': label, 'command': argv, 'returncode': result.returncode,
                                 'stdout': result.stdout, 'stderr': result.stderr})
        save()
        assert result.returncode == 0, (label, result.stderr)
        return result

    runtime = evidence / 'runtime/minyar_runtime.c'
    text = runtime.read_text()
    before = text
    injections = {
        'MINYAR_HOT void *object_allocate(size_t size, unsigned kind) {':
            '    if (research_phase) research_objects++;',
        'MINYAR_HOT void *data_allocate(size_t size, size_t alignment) {':
            '    if (research_phase) { research_data++; research_data_bytes += size; }',
        'MINYAR_HOT void copy_bytes(unsigned char *target, const unsigned char *source, size_t length) {':
            '    if (research_phase) { research_copy_calls++; research_copy_bytes += length; }',
        'MinyarText *minyar_join_texts(const MinyarList *parts) {':
            '    if (research_phase) research_joins++;',
        'static MINYAR_COLD void build_text_index(MinyarText *text) {':
            '    if (research_phase) { research_indexes++; research_index_bytes += (size_t)text->byte_length; }',
        'MinyarText *minyar_character_text(int character) {':
            '    if (research_phase) { research_characters++; if ((unsigned int)character < 128) research_ascii++; else research_nonascii++; }'}
    for needle, addition in injections.items():
        assert text.count(needle) == (2 if 'object_allocate(' in needle or 'data_allocate(' in needle else 1), needle
        text = text.replace(needle, needle + '\n' + addition)
    start = text.index('MinyarText *minyar_join_texts(')
    end = text.index('\nstatic MINYAR_COLD MINYAR_NORETURN void invalid_utf8', start)
    fragment = text[start:end]
    needle = '    for (index = 0; index < parts->length; index++) {'
    assert fragment.count(needle) == 2
    fragment = fragment.replace(needle, needle + '\n        if (research_phase) research_sizing_parts++;', 1)
    part = '        const MinyarText *part = (const MinyarText *)(intptr_t)parts->values[index];'
    assert fragment.count(part) == 2
    fragment = fragment.replace(part, part + '''
        if (research_phase) {
            if (part->character_length == part->byte_length) research_certified_parts++;
            else research_uncertified_parts++;
        }''', 1)
    offset = fragment.index(needle, fragment.index(needle) + len(needle))
    fragment = fragment[:offset] + fragment[offset:].replace(needle, needle + '\n        if (research_phase) research_copy_parts++;', 1)
    runtime.write_text(text[:start] + fragment + text[end:])
    import difflib
    (evidence / 'runtime-instrumentation.patch').write_text(''.join(difflib.unified_diff(
        before.splitlines(True), runtime.read_text().splitlines(True), fromfile='a/runtime/minyar_runtime.c',
        tofile='b/runtime/minyar_runtime.c')))
    ownership = evidence / 'runtime/minyar_rc.h'
    text = ownership.read_text()
    before = text
    needle = '    if (rc_pending_count) return minyar_rc_poll(budget);'
    assert text.count(needle) == 1
    text = text.replace(needle, '''    if (research_phase) { research_hooks++; research_offered += budget; }
    if (rc_pending_count) {
        size_t work = minyar_rc_poll(budget);
        if (research_phase) research_queued_work += work;
        return work;
    }''')
    ownership.write_text(text)
    (evidence / 'ownership-instrumentation.patch').write_text(''.join(difflib.unified_diff(
        before.splitlines(True), text.splitlines(True), fromfile='a/runtime/minyar_rc.h',
        tofile='b/runtime/minyar_rc.h')))
    report['instrumented_sources'] = [{'snapshot': str(p.relative_to(evidence)),
                                      'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                                     for p in [runtime, ownership]]
    print('Evidence: ' + str(evidence), flush=True)
    try:
        execute('toolchain', ['clang', '--version'])
        llvm = evidence / 'program.ll'
        execute('compile-language', [str(compiler), str(evidence / 'tests/memory-research-aggregate-join.min'), str(llvm)])
        report['generated_aggregate_join_calls'] = llvm.read_text().count('call ptr @minyar_join_texts(')
        assert report['generated_aggregate_join_calls'] >= 2
        sanitize_flags = ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
        sanitized = evidence / 'program-sanitize.ll'
        shutil.copyfile(llvm, sanitized)
        prepare_llvm_for_link(sanitized, sanitize_flags)
        definitions = re.findall(r'^define[^\n]*', sanitized.read_text(), re.M)
        assert definitions and all(' sanitize_address ' in line for line in definitions)
        report['generated_asan_definitions'] = len(definitions)
        for label, defines, flags in [('system-k32', ['-DMINYAR_SYSTEM_HEAP=1'], ['-O2']),
                                     ('compiler-arena', ['-DMINYAR_COMPILER_ARENA=1'], ['-O2']),
                                     ('system-k32-sanitize', ['-DMINYAR_SYSTEM_HEAP=1'], sanitize_flags)]:
            binary = evidence / label
            execute(label + '-link', clang_command(['clang', '-std=c11', *flags, *defines,
                    '-DMINYAR_RC_POLL_BUDGET=32', '-DMINYAR_RESEARCH_INSTRUMENTED=1',
                    '-Wall', '-Wextra', '-Werror', '-Wno-override-module',
                    str(sanitized if 'sanitize' in label else llvm),
                    str(evidence / 'tests/memory-research-aggregate-join.c'), '-o', str(binary)]))
            for mode in ['ascii'] if args.pilot else list(INPUTS):
                value, parts, oracle = expected(mode)
                result = execute(label + '-' + mode, [str(binary), mode, str(opaque)])
                assert result.stdout == oracle, (label, mode, result.stdout, oracle)
                observations = [json.loads(line) for line in result.stderr.splitlines()]
                assert len(observations) == 6
                join, cold, warm = observations[1:4]
                assert join['phase'] == 2 and join['aggregate_joins'] == 1
                assert join['sizing_parts'] == join['copy_parts'] == parts
                assert join['certified_ascii_parts'] + join['uncertified_parts'] == parts
                assert join['uncertified_parts'] == (1 if mode == 'unknown' else 3 if mode == 'unicode' else 0)
                assert join['copy_bytes'] == len(value.encode())
                assert join['object_payload_requests'] == join['data_requests'] == 1
                assert join['data_payload_request_bytes'] == len(value.encode()) + 1
                assert cold['index_builds'] == (0 if mode == 'no-query' else 1)
                assert cold['index_input_bytes'] == (0 if mode == 'no-query' else len(value.encode()))
                assert warm['index_builds'] == warm['index_input_bytes'] == 0
                report['observations'].append({'configuration': label, 'mode': mode,
                                               'parts': parts, 'output_bytes': len(value.encode()),
                                               'phases': observations})
                print('PASS ' + label + '-' + mode, flush=True)
        assert len(report['observations']) == (3 if args.pilot else 18)
        report['summary'] = {'generated_executions': len(report['observations']),
                             'native_generated_link_optimization': 'O2',
                             'sanitized_generated_link_optimization': 'O1',
                             'modes': ['ascii'] if args.pilot else list(INPUTS)}
        report['status'] = 'passed'
    except BaseException as error:
        report.update(status='failed', failure=repr(error))
        raise
    finally:
        save()
        print('Results: ' + str(evidence / 'results.json'), flush=True)


if __name__ == '__main__':
    main()
