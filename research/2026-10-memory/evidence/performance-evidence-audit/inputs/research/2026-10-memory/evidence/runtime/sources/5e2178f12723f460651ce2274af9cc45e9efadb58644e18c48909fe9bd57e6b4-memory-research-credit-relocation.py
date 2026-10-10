#!/usr/bin/env python3
"""Causal count-only baseline/relocated service experiment; no production edits."""
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
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--admission', action='store_true', help='Finite-pool admission counterexample')
    args = parser.parse_args()
    parent = ROOT / 'build/memory-research-credit-relocation'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent)).resolve()
    report = {'status': 'running', 'checks': [], 'sources': [], 'observations': [],
              'scope': 'Two separate K allocation hooks relocated only from an initially shared copy path. '
                       'No global suppression flag. Explicit no-service helpers remain test-only.',
              'sanitize': args.sanitize, 'admission': args.admission}
    for source in [*ROOT.joinpath('runtime').glob('minyar_*'), Path(__file__),
                   ROOT / 'tests/memory-research-credit-relocation.c',
                   ROOT / 'tests/memory-research-credit-relocation.h',
                   ROOT / 'tests/memory-research-credit-admission.c', ROOT / 'tests/clang_helpers.py']:
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
                                        else 'tests/memory-research-credit-relocation.c')),
                        '-o', str(binary)]))
                observations = {}
                for policy in ('baseline', 'relocated'):
                    result = execute(label + '-' + policy, [str(binary), policy],
                                     expected=int(args.admission and policy == 'relocated'))
                    if args.admission:
                        row = json.loads(result.stdout.splitlines()[0])
                        observations[policy] = row
                        report['observations'].append({'profile': profile, **row})
                        if policy == 'relocated':
                            assert result.stderr == 'Minyar stopped: the computer ran out of memory.\n'
                        else:
                            assert result.stdout.endswith('Recovered complete pool after next allocation.\n')
                        continue
                    rows = [json.loads(line) for line in result.stdout.splitlines()]
                    assert len(rows) == 9
                    observations[policy] = {row['case']: row for row in rows}
                    report['observations'].extend({'profile': profile, **row} for row in rows)
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
