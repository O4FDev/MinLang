#!/usr/bin/env python3
"""Application-inspired Integer formatting counts; no timing or policy change."""
import argparse
import difflib
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


def oracle(trajectory, count):
    values, statuses = [], []
    for frame in range(count):
        x = 16 + frame % 16 if trajectory == 'bounded' else frame if trajectory == 'positive' else -frame - 1
        minute = (frame + 360) % 1440
        hour, minute = divmod(minute, 60)
        values.extend([60, x, 64, -1, hour, minute])
        statuses.append(f'Minyarcraft  60 fps\nPosition {x} 64 -1  facing north\nTime {hour:02d}:{minute:02d}')
    output = ''.join(status + '\n' for status in statuses)
    return values, output + '1\n' + output + '2\n' + statuses[0] + '\n' + statuses[0] + '\n3\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot', action='store_true')
    args = parser.parse_args()
    count = 16 if args.pilot else 2048
    parent = ROOT / 'build/memory-research-hud-formatting'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent)).resolve()
    report = {'status': 'running', 'frames_per_pass': count, 'passes': 2, 'pilot': args.pilot,
              'checks': [], 'observations': [], 'sources': [], 'instrumentation': [],
              'scope': 'Generated Craft HUD formatting projection. Limit0 is a test-only cache policy control. No timing/RSS/optimization claim.'}
    for directory, paths in [('runtime', sorted((ROOT / 'runtime').glob('minyar_*'))),
                             ('tests', [ROOT / 'tests' / name for name in [Path(__file__).name,
                               'memory-research-hud-formatting.c', 'memory-research-hud-formatting.min',
                               'clang_helpers.py', 'llvm_sanitizer.py']])]:
        for path in paths:
            if path.is_file():
                target = evidence / directory / path.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
                report['sources'].append({'source': str(path), 'snapshot': str(target.relative_to(evidence)),
                                          'original_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    compiler = evidence / 'minyarc'
    shutil.copy2(ROOT / 'build/minyarc', compiler)
    report['compiler_sha256'] = hashlib.sha256(compiler.read_bytes()).hexdigest()
    changes = {
        'minyar_runtime.c': [('static MINYAR_COLD MinyarText *format_integer_text(long long integer) {\n',
                             '    if (research_active) research_formats++;\n')],
        'minyar_rc.h': [
            ('static inline size_t rc_service_pending(size_t budget) {\n',
             '    if (research_active) { research_hooks++; research_offered += budget; }\n'),
            ('static void *rc_allocate_object(size_t size, unsigned kind) {\n',
             '    if (research_active) { research_headers++; research_allocated_bytes += sizeof(RcObject) + size; }\n'),
            ('static void *rc_allocate_data(size_t size) {\n',
             '    if (research_active) { research_data++; research_allocated_bytes += sizeof(RcData) + size; }\n')],
        'minyar_bounded_rc.h': [
            ('static void *rc_bounded_finish_object(RcObject *object, unsigned kind) {\n',
             '    if (research_active) research_destroyed++;\n')]}
    for name, anchors in changes.items():
        path = evidence / 'runtime' / name
        before = path.read_text()
        after = before
        for anchor, addition in anchors:
            assert after.count(anchor) == 1, anchor
            after = after.replace(anchor, anchor + addition)
        if name == 'minyar_bounded_rc.h':
            anchor = '    rc_bounded_last_work = work;\n#endif\n    return work;'
            assert after.count(anchor) == 1
            after = after.replace(anchor, '    rc_bounded_last_work = work;\n#endif\n    if (research_active) research_work += work;\n    return work;')
        path.write_text(after)
        patch = evidence / (name + '.instrumentation.patch')
        patch.write_text(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                                    fromfile='original/' + name, tofile='instrumented/' + name)))
        report['instrumentation'].append({'file': name, 'patch': patch.name,
                                          'original_sha256': hashlib.sha256(before.encode()).hexdigest(),
                                          'instrumented_sha256': hashlib.sha256(after.encode()).hexdigest()})
    environment = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1',
                   'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
    report['environment'] = {key: environment[key] for key in ('ASAN_OPTIONS', 'UBSAN_OPTIONS')}

    def save():
        for record in report['sources']:
            record['sha256'] = hashlib.sha256((evidence / record['snapshot']).read_bytes()).hexdigest()
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    def execute(label, command):
        result = subprocess.run(command, capture_output=True, text=True, timeout=90, env=environment)
        report['checks'].append({'label': label, 'command': command, 'returncode': result.returncode,
                                 'stdout_bytes': len(result.stdout.encode()),
                                 'stdout_sha256': hashlib.sha256(result.stdout.encode()).hexdigest(),
                                 'stdout_excerpt': result.stdout[:600], 'stderr': result.stderr})
        save()
        assert result.returncode == 0, (label, result.stderr)
        return result

    print('Evidence: ' + str(evidence), flush=True)
    try:
        llvm = evidence / 'program.ll'
        execute('language-compile', [str(compiler), str(evidence / 'tests/memory-research-hud-formatting.min'), str(llvm)])
        sanitized = evidence / 'program-sanitize.ll'
        shutil.copyfile(llvm, sanitized)
        sanitize_flags = ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
        prepare_llvm_for_link(sanitized, sanitize_flags)
        definitions = re.findall(r'^define[^\n]*', sanitized.read_text(), re.M)
        assert definitions and all(' sanitize_address ' in header for header in definitions)
        report['generated_asan_definitions'] = len(definitions)
        for policy, limit in [('default', 32768), ('disabled-control', 0)]:
            for mode, flags, link_modes in ([('native', ['-O2'], ['-O2'])] if args.pilot else [
                    ('native', ['-O2'], ['-O0', '-O2']), ('sanitize', sanitize_flags, ['-O1'])]):
                runtime = evidence / (policy + '-' + mode + '.o')
                defines = ['-DMINYAR_SYSTEM_HEAP=1', '-DMINYAR_RC_POLL_BUDGET=32',
                           f'-DMINYAR_INTEGER_TEXT_CACHE_LIMIT={limit}', f'-DMINYAR_RESEARCH_HUD_FRAMES={count}']
                execute(policy + '-' + mode + '-runtime', clang_command(['clang', '-std=c11', '-Wall', '-Wextra',
                        '-Werror', *flags, *defines, '-c', str(evidence / 'tests/memory-research-hud-formatting.c'), '-o', str(runtime)]))
                for optimization in link_modes:
                    label = policy + '-' + mode + '-' + optimization[1:]
                    binary = evidence / label
                    link_flags = sanitize_flags if mode == 'sanitize' else [optimization]
                    execute(label + '-link', clang_command(['clang', *link_flags, '-Wno-override-module',
                            str(sanitized if mode == 'sanitize' else llvm), str(runtime), '-o', str(binary)]))
                    for trajectory in (['bounded'] if args.pilot else ['bounded', 'positive', 'negative']):
                        result = execute(label + '-' + trajectory, [str(binary), trajectory, 'pilot' if args.pilot else 'matrix'])
                        values, expected_output = oracle(trajectory, count)
                        assert result.stdout == expected_output, (label, trajectory, 'status oracle mismatch')
                        observations = [json.loads(line) for line in result.stderr.splitlines()]
                        assert len(observations) == 4
                        seen = set()
                        for phase_index in range(2):
                            observation = observations[phase_index]
                            formats = []
                            for value in values:
                                if not 0 <= value < limit or value not in seen:
                                    formats.append(value)
                                if 0 <= value < limit:
                                    seen.add(value)
                            metadata = observation['object_header_size'] + observation['text_size'] + observation['data_header_size']
                            assert observation['calls'] == count * 6
                            assert observation['formats'] == len(formats)
                            assert observation['allocated_requested_bytes'] == sum(metadata + len(str(value)) + 1 for value in formats)
                            assert observation['cached_objects'] == len(seen)
                            assert observation['cache_table_bytes'] == limit * 8
                        final = observations[-1]
                        metadata = observations[0]['object_header_size'] + observations[0]['text_size'] + observations[0]['data_header_size']
                        assert observations[2]['calls'] == observations[2]['formats'] == 0
                        assert final['cached_objects'] == len(seen)
                        assert final['requested_bytes'] == sum(metadata + len(str(value)) + 1 for value in seen)
                        report['observations'].append({'configuration': label, 'trajectory': trajectory,
                            'exact_output_sha256': hashlib.sha256(expected_output.encode()).hexdigest(), 'phases': observations})
                        print('PASS ' + label + '-' + trajectory, flush=True)
        expected_runs = 2 if args.pilot else 18
        assert len(report['observations']) == expected_runs
        report['summary'] = {'generated_executions': expected_runs, 'frames_per_pass': count,
                              'configuration_weighted_frames': expected_runs * count * 2,
                              'intentional_cache_is_not_a_leak': True}
        report['status'] = 'passed'
    except Exception as error:
        report.update(status='failed', failure=str(error))
        raise
    finally:
        save()
        print('Results: ' + str(evidence / 'results.json'), flush=True)


if __name__ == '__main__':
    main()
