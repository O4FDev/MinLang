#!/usr/bin/env python3
"""Causal count-only baseline/relocated service experiment; no production edits."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
from clang_helpers import clang_command
from llvm_sanitizer import prepare_llvm_for_link

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--admission', action='store_true', help='Finite-pool admission counterexample')
    parser.add_argument('--api-probes', action='store_true', help='Baseline-only slice/Boolean counts')
    parser.add_argument('--language', action='store_true', help='Generated view workload for API probes')
    parser.add_argument('--guard-probes', action='store_true', help='Baseline size guard order under detached debt')
    args = parser.parse_args()
    if sum((args.admission, args.api_probes, args.guard_probes)) > 1:
        parser.error('--admission, --api-probes and --guard-probes are mutually exclusive')
    if args.language and not args.api_probes:
        parser.error('--language requires --api-probes')
    parent = ROOT / 'build/memory-research-credit-relocation'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent)).resolve()
    report = {'status': 'running', 'checks': [], 'sources': [], 'observations': [],
              'scope': 'Two separate K allocation hooks relocated only from an initially shared copy path. '
                       'No global suppression flag. Explicit no-service helpers remain test-only.',
              'sanitize': args.sanitize, 'admission': args.admission, 'api_probes': args.api_probes, 'language_requested': args.language, 'guard_probes': args.guard_probes}
    if args.api_probes:
        report['scope'] = 'Baseline-only C slice retention/Boolean-format counts; generated view workload when --language is explicit. No production policy changes or timing.'
    if args.guard_probes:
        report['scope'] = 'Native/internal size guards with pending debt: managed allocation/service failure order only, synthetic huge ABI sizes, no production changes.'
    for source in [*ROOT.joinpath('runtime').glob('minyar_*'), Path(__file__),
                   ROOT / 'tests/memory-research-credit-relocation.c',
                   ROOT / 'tests/memory-research-credit-relocation.h',
                   ROOT / 'tests/memory-research-credit-admission.c',
                   ROOT / 'tests/memory-research-api-counts.c',
                   ROOT / 'tests/memory-research-guard-order.c',
                   ROOT / 'tests/memory-research-view-counts-generated.c',
                   ROOT / 'tests/memory-research-view-counts.min',
                   ROOT / 'tests/llvm_sanitizer.py', ROOT / 'tests/clang_helpers.py']:
        if source.is_file():
            relative = Path('runtime' if source.parent == ROOT / 'runtime' else 'tests') / source.name
            target = evidence / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            report['sources'].append({'source': str(source), 'snapshot': str(relative),
                                     'original_sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    ownership = evidence / 'runtime/minyar_rc.h'
    source = ownership.read_text()
    changes = [
        ('static inline size_t rc_service_pending(size_t budget) {\n',
         '''static inline size_t rc_service_pending(size_t budget) {
    if (research_active) {
        assert(budget <= MINYAR_RC_POLL_BUDGET);
        research_service_calls++;
        research_offered += budget;
    }
'''),
        ('static void *rc_allocate_object(size_t size, unsigned kind) {\n',
         'static void *rc_allocate_object(size_t size, unsigned kind) {\n    if (research_active) research_object_allocations++;\n'),
        ('static void *rc_allocate_data(size_t size) {\n',
         'static void *rc_allocate_data(size_t size) {\n    if (research_active) research_data_allocations++;\n'),
        ('static void *rc_reallocate_data(void *pointer, size_t size) {\n',
         'static void *rc_reallocate_data(void *pointer, size_t size) {\n    if (research_active) research_data_resizes++;\n'),
        ('    RC_ACCOUNT(rc_bytes += sizeof(*object) + size);',
         '    RC_ACCOUNT(rc_bytes += sizeof(*object) + size);\n    research_note_storage();'),
        ('    RC_ACCOUNT(rc_bytes += sizeof(*data) + size);',
         '    RC_ACCOUNT(rc_bytes += sizeof(*data) + size);\n    research_note_storage();'),
        ('    RC_ACCOUNT(rc_bytes += size);',
         '    RC_ACCOUNT(rc_bytes += size);\n    research_note_storage();'),
    ]
    for old, new in changes:
        assert source.count(old) == 1, old
        source = source.replace(old, new)
    ownership.write_text(source)
    bounded = evidence / 'runtime/minyar_bounded_rc.h'
    source = bounded.read_text()
    changes = [
        ('static void *rc_bounded_finish_object(RcObject *object, unsigned kind) {\n',
         'static void *rc_bounded_finish_object(RcObject *object, unsigned kind) {\n    if (research_active) research_destroyed++;\n'),
        ('    rc_bounded_last_work = work;\n#endif\n    return work;',
         '    rc_bounded_last_work = work;\n#endif\n    if (research_active) research_queued += work;\n    return work;'),
        ('    unsigned immediate = rc_drop(value);\n',
         '    unsigned immediate = rc_drop(value);\n    if (research_active) research_immediate += immediate;\n'),
    ]
    for old, new in changes:
        assert source.count(old) == 1, old
        source = source.replace(old, new)
    bounded.write_text(source)
    if args.api_probes:
        runtime = evidence / 'runtime/minyar_runtime.c'
        source = runtime.read_text()
        anchor = 'static MINYAR_COLD void build_text_index(MinyarText *text) {\n'
        assert source.count(anchor) == 1
        runtime.write_text(source.replace(anchor, anchor +
            '    if (research_active) { research_index_calls++; research_index_input_bytes += (size_t)text->byte_length; }\n'))
    environment = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1',
                   'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
    report['environment'] = {key: environment[key] for key in ('ASAN_OPTIONS', 'UBSAN_OPTIONS')}

    def save():
        for record in report['sources']:
            record['sha256'] = hashlib.sha256((evidence / record['snapshot']).read_bytes()).hexdigest()
        temporary = evidence / 'results.json.tmp'
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(evidence / 'results.json')

    def execute(label, command, expected=0):
        check = {'label': label, 'command': command}
        try:
            result = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=60)
        except subprocess.TimeoutExpired as error:
            check.update(returncode=None, timed_out=True, timeout_seconds=60,
                         stdout=str(error.stdout), stderr=str(error.stderr))
            report['checks'].append(check)
            save()
            raise
        check.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
        report['checks'].append(check)
        save()
        assert result.returncode == expected, (label, result.stdout, result.stderr)
        return result

    print(f'Evidence: {evidence}', flush=True)
    try:
        flags = (['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
                 if args.sanitize else ['-O2'])
        profiles = ([('fixed', ['-DMINYAR_BOUNDED_HEAP=1']),
                     ('lazy', ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_LAZY_HEAP=1'])]
                    if args.admission else [('system', ['-DMINYAR_SYSTEM_HEAP=1']),
                                            ('fixed', ['-DMINYAR_BOUNDED_HEAP=1'])])
        for profile, definitions in profiles:
            for budget in (1, 32):
                label = f'{profile}-k{budget}'
                binary = evidence / label
                execute(label + '-compile', clang_command(['clang', '-std=c11', '-Wall', '-Wextra',
                        '-Werror', *flags, *definitions, f'-DMINYAR_RC_POLL_BUDGET={budget}',
                        '-DMINYAR_RESEARCH_INSTRUMENTED=1',
                        f'-DMINYAR_BOUNDED_HEAP_BYTES={524288 if args.admission else 8388608}',
                        str(evidence / ('tests/memory-research-credit-admission.c' if args.admission
                                        else 'tests/memory-research-guard-order.c' if args.guard_probes
                                        else 'tests/memory-research-api-counts.c' if args.api_probes
                                        else 'tests/memory-research-credit-relocation.c')),
                        '-o', str(binary)]))
                if args.guard_probes:
                    cases = {'bytes-negative': 'Bytes cannot have a negative length.',
                        'bytes-max': 'these Bytes are too large.', 'bytes-resize-max': 'these Bytes are too large.',
                        'bytes-extend-negative': 'Bytes cannot shrink by a negative amount.',
                        'bytes-extend-max': 'these Bytes are too large.',
                        'bytes-int64-max-position': 'a 8-byte value at position 9223372036854775807 does not fit in Bytes of length 16.',
                        'record-negative': 'this record has too many fields.',
                        'record-max': 'this record has too many fields.',
                        'record-allocation-overflow': 'the computer ran out of memory.',
                        'text-copy-overflow': 'the joined Text would be too large.',
                        'text-consume-overflow': 'the joined Text would be too large.'}
                    for case, diagnostic in cases.items():
                        result = execute(label + '-' + case, [str(binary), case], expected=1)
                        assert result.stderr == 'Minyar stopped: ' + diagnostic + '\n'
                        observation = json.loads(result.stdout)
                        assert observation == {'managed_allocations': 0, 'managed_service_hooks': 0,
                            'queued_units': 0, 'immediate_units': 0, 'pending_before': 1, 'full_recovery': True}
                        report['observations'].append({'profile': profile, 'budget': budget, 'case': case, **observation})
                    if profile == 'system' and budget == 1:
                        environment['MINYAR_RESEARCH_GUARD_INJECT_SERVICE'] = '1'
                        try:
                            result = execute(label + '-oracle-injected-service', [str(binary), 'bytes-negative'], expected=-6)
                            assert 'research_service_calls' in result.stderr
                            report['oracle_calibration'] = 'Injected pre-guard service detected by the post-trap assertion; fixture mutation only.'
                        finally:
                            environment.pop('MINYAR_RESEARCH_GUARD_INJECT_SERVICE', None)
                    print('PASS guard order ' + label, flush=True)
                    continue
                observations = {}
                for policy in (('probe',) if args.api_probes else ('baseline', 'relocated')):
                    result = execute(label + '-' + policy, [str(binary), policy],
                                     expected=int(args.admission and policy == 'relocated'))
                    if args.admission:
                        row = json.loads(result.stdout.splitlines()[0])
                        observations[policy] = row
                        report['observations'].append({'profile': profile, **row})
                        if policy == 'relocated':
                            assert result.stderr == 'Minyar stopped: the bounded heap is exhausted (including pending cleanup and fragmentation).\n'
                        else:
                            assert result.stdout.endswith('Recovered complete pool after next allocation.\n')
                        continue
                    rows = [json.loads(line) for line in result.stdout.splitlines()]
                    if args.api_probes:
                        assert len(rows) == 48
                        report['observations'].extend({'profile': profile, **row} for row in rows)
                        continue
                    assert len(rows) == 9
                    observations[policy] = {row['case']: row for row in rows}
                    report['observations'].extend({'profile': profile, **row} for row in rows)
                if args.api_probes:
                    print('PASS baseline API counts ' + label, flush=True)
                    continue
                if args.admission:
                    before, after = observations['baseline'], observations['relocated']
                    assert after['offered_units'] + after['immediate_units'] <= before['offered_units'] + before['immediate_units']
                    print('PASS admission counterexample ' + label, flush=True)
                    continue
                for case in observations['baseline']:
                    before, after = observations['baseline'][case], observations['relocated'][case]
                    assert after['offered_units'] + after['immediate_units'] <= before['offered_units'] + before['immediate_units']
                    for row in (before, after):
                        assert row['destructions'] <= row['queued_units'] + row['immediate_units']
                print('PASS ' + label, flush=True)
        if args.language:
            compiler = evidence / 'minyarc'
            shutil.copy2(ROOT / 'build/minyarc', compiler)
            report['compiler_artifact_sha256'] = hashlib.sha256(compiler.read_bytes()).hexdigest()
            llvm = evidence / 'view-generated.ll'
            execute('view-language-compile', [str(compiler), str(evidence / 'tests/memory-research-view-counts.min'), str(llvm)])
            prepare_llvm_for_link(llvm, flags)
            report['generated_llvm_sha256'] = hashlib.sha256(llvm.read_bytes()).hexdigest()
            if args.sanitize:
                definitions = re.findall(r'^define [^\n]*', llvm.read_text(), flags=re.M)
                attributed = [row for row in definitions if re.search(r'\bsanitize_address\b', row[row.rfind(')') + 1:])]
                assert definitions and len(definitions) == len(attributed)
                report['sanitizer_coverage'] = {'native_c': 'ASan+UBSan',
                    'generated_definitions': len(definitions), 'generated_asan_definitions': len(attributed),
                    'limitations': 'Generated UBSan not asserted; leak detection disabled.'}
            language_flags = ['-DMINYAR_SYSTEM_HEAP=1', '-DMINYAR_RC_POLL_BUDGET=32',
                              '-DMINYAR_RESEARCH_INSTRUMENTED=1']
            binary = evidence / 'view-generated'
            execute('view-language-link', clang_command(['clang', *flags, *language_flags,
                    '-Wno-override-module', str(llvm),
                    str(evidence / 'tests/memory-research-view-counts-generated.c'), '-o', str(binary)]))
            cases = [('4096-small', 4096, 511, 1), ('4096-many', 4096, 512, 32),
                     ('4097-small', 4097, 511, 1), ('default', 4097, 512, 32),
                     ('4097-view', 4097, 513, 1), ('4097-many-views', 4097, 513, 32),
                     ('8192-small', 8192, 1023, 1), ('8192-many-copies', 8192, 1023, 32),
                     ('8192-view', 8192, 1024, 1), ('8192-many-views', 8192, 1024, 32)]
            for mode, root, token, survivors in cases:
                result = execute('view-language-' + mode, [str(binary), mode])
                assert result.stdout == f'{survivors}\n{token * survivors}\n'
                rows = [json.loads(line) for line in result.stderr.splitlines()]
                assert len(rows) == 2 and rows[1] == {'phase': 'final-recovery', 'objects': 0, 'requested_bytes': 0}
                observation = rows[0]
                copied = root > 4096 and token * 8 < root
                assert observation['slices'] == survivors
                assert observation['root_length'] == root
                assert observation['copies'] == (survivors if copied else 0)
                assert observation['views'] == (0 if copied else survivors)
                assert observation['slice_object_allocations'] == survivors
                assert observation['slice_data_allocations'] == (survivors if copied else 0)
                report['observations'].append({'generated_mode': mode, 'profile': 'system', 'budget': 32, **observation})
            report['language_executions'] = len(cases)
            assert report['language_executions'] == 10
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
