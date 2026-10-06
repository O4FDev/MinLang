#!/usr/bin/env python3
"""Focused semantic runtime mutations in isolated snapshots; no production edits."""
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
U = 'memory-research-text-join-index.c'
A = 'memory-research-accounting-edges.c'
F = 'bounded-frame-retirement.c'
V = 'text-view-budget.c'
D = 'memory-research-list-debt-pressure.c'
GUARD = 'left->character_length == left_length && right->character_length == right_length'
MUTANTS = [
 ('unicode_known_counts_without_index', 'minyar_runtime.c', GUARD,
  'left->character_length >= 0 && right->character_length >= 0', U, 'o2', 'Restores the demonstrated invalid known-count/no-index state.'),
 ('unicode_check_left_only', 'minyar_runtime.c', GUARD,
  'left->character_length == left_length', U, 'o2', 'Ignores indexed or unknown Unicode RHS.'),
 ('unicode_check_right_only', 'minyar_runtime.c', GUARD,
  'right->character_length == right_length', U, 'o2', 'Ignores indexed or unknown Unicode LHS.'),
 ('unicode_always_invalidate', 'minyar_runtime.c', GUARD,
  '0', U, 'o2', 'Correct Unicode semantics, but loses known ASCII fast-state; semantic survivor expected.'),
 ('join_shared_left_reused', 'minyar_runtime.c',
  'object->ownership == (8 | RC_TEXT) && !left->backing',
  '(object->ownership & 7) == RC_TEXT && !left->backing', U, 'o2', 'Mutates a shared Text header and invalidates aliases.'),
 ('join_view_reused', 'minyar_runtime.c',
  'object->ownership == (8 | RC_TEXT) && !left->backing',
  'object->ownership == (8 | RC_TEXT)', U, 'sanitize', 'Interprets view interior bytes as owning RcData.'),
 ('join_self_uses_stale_storage', 'minyar_runtime.c',
  'right == left ? bytes : right->bytes', 'right->bytes', U, 'sanitize', 'Self-join reads old storage after moving reallocation.'),
 ('poll_cap_k_plus_one', 'minyar_bounded_rc.h',
  'if (budget > MINYAR_RC_POLL_BUDGET) budget = MINYAR_RC_POLL_BUDGET;',
  'if (budget > MINYAR_RC_POLL_BUDGET + 1) budget = MINYAR_RC_POLL_BUDGET + 1;', F, 'o2', 'Oversized requests can perform K+1 units.'),
 ('poll_forgets_round_robin', 'minyar_bounded_rc.h',
  'unsigned queue = rc_bounded_next_queue;', 'unsigned queue = 0;', F, 'o2', 'Continuously ready frame/chunk queues can starve behind objects.'),
 ('temporary_partial_chunk_omitted', 'minyar_bounded_rc.h',
  '+ (frame->temporary_count % RC_TEMPORARY_CHUNK_SLOTS != 0);', '+ 0;', A, 'o2', 'Floor chunk accounting omits the final partial owner task.'),
 ('release_ignores_immediate_work', 'minyar_bounded_rc.h',
  'rc_service_pending(immediate < MINYAR_RC_POLL_BUDGET\n                       ? MINYAR_RC_POLL_BUDGET - immediate : 0);',
  'rc_service_pending(MINYAR_RC_POLL_BUDGET);', V, 'o2', 'Public release can perform an immediate free plus K queued units.'),
 ('reserve_ignores_retirement_debt', 'minyar_collections.h',
  'if (rc_pending_count) {', 'if (0) {', D, 'o2', 'Reserves final buffer before geometric growth can release its buddy.'),
 ('reserve_ignores_active_object_debt', 'minyar_collections.h',
  'if (rc_pending_count) {', 'if (rc_bounded_head || rc_bounded_recent_head) {', D, 'o2', 'Pending active cursor is excluded from the guard.'),
 ('reserve_ignores_frame_chunk_debt', 'minyar_collections.h',
  'if (rc_pending_count) {',
  'if (rc_bounded_head || rc_bounded_recent_head || rc_bounded_active) {', D, 'o2', 'Object-debt-only fixture may survive a guard that ignores retired owners.'),
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--names', nargs='*')
    args = parser.parse_args()
    selected = [m for m in MUTANTS if not args.names or m[0] in args.names]
    if args.names and set(args.names) - {m[0] for m in selected}:
        parser.error('unknown mutation name')
    parent = ROOT / 'build/peer-memory-native-mutants'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent))
    report = {'status': 'running', 'scope': 'Compiled semantic snapshot mutants; neither production defects nor exhaustive mutation coverage.',
              'sources': {}, 'calibrations': [], 'mutants': [], 'runner_sha256': digest(Path(__file__))}
    runtime = evidence / 'original/runtime'
    runtime.mkdir(parents=True)
    for source in (ROOT / 'runtime').glob('minyar_*'):
        if source.is_file():
            shutil.copy2(source, runtime / source.name)
            report['sources'][str(source.relative_to(ROOT))] = digest(source)
    fixtures = evidence / 'original/tests'
    fixtures.mkdir()
    for name in {m[4] for m in selected}:
        shutil.copy2(ROOT / 'tests' / name, fixtures / name)
        report['sources']['tests/' + name] = digest(fixtures / name)
    environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',
                       UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')

    def save():
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    def command(command, timeout=45):
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=environment)
            return {'command': command, 'returncode': result.returncode,
                    'stdout': result.stdout, 'stderr': result.stderr, 'timed_out': False}
        except subprocess.TimeoutExpired as error:
            return {'command': command, 'returncode': None, 'timed_out': True,
                    'stdout': str(error.stdout), 'stderr': str(error.stderr)}

    def probe(directory, fixture, mode):
        flags = ['-O2'] if mode == 'o2' else ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
        defines = ['-DMINYAR_RC_POLL_BUDGET=1']
        if fixture in (U, A, V):
            defines += ['-DMINYAR_SYSTEM_HEAP=1']
        binary = directory / 'probe'
        build = command(clang_command(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', *flags,
                                       *defines, str(directory / 'tests' / fixture), '-o', str(binary)]))
        record = {'fixture': fixture, 'mode': mode, 'budget': 1, 'build': build}
        if build['returncode'] != 0:
            record['status'] = 'build_timeout_inconclusive' if build['timed_out'] else 'build_failure_invalid_mutant'
            return record
        run = command([str(binary)], 15)
        record['run'] = run
        if run['timed_out']:
            record['status'] = 'runtime_timeout_inconclusive'
        elif run['returncode'] == 0:
            record['status'] = 'survived'
        elif ('Assertion' in run['stderr'] or 'assertion' in run['stderr'] or
              'ERROR: AddressSanitizer' in run['stderr'] or 'runtime error:' in run['stderr'] or
              'the Minyar heap is full' in run['stderr'] or 'out of memory' in run['stderr'].lower() or
              'the bounded heap is exhausted' in run['stderr']):
            record['status'] = 'killed'
        else:
            record['status'] = 'runtime_failure_unclassified'
        return record

    print('Evidence: ' + str(evidence), flush=True)
    save()
    for fixture, mode in sorted({(m[4], m[5]) for m in selected}):
        directory = evidence / ('calibration-' + fixture.removesuffix('.c') + '-' + mode)
        shutil.copytree(evidence / 'original', directory)
        result = probe(directory, fixture, mode)
        report['calibrations'].append(result)
        save()
        if result['status'] != 'survived':
            report['status'] = 'invalid_calibration'
            save()
            raise RuntimeError('unmodified calibration failed: ' + str(result))
    for name, file, before, after, fixture, mode, meaning in selected:
        directory = evidence / name
        shutil.copytree(evidence / 'original', directory)
        target = directory / 'runtime' / file
        source = target.read_text()
        if source.count(before) != 1:
            raise RuntimeError(name + ': anchor must occur exactly once')
        target.write_text(source.replace(before, after))
        record = probe(directory, fixture, mode)
        record.update(name=name, meaning=meaning, mutation_file=file,
                      before=before, after=after, mutated_sha256=digest(target))
        report['mutants'].append(record)
        save()
        print(name + ': ' + record['status'], flush=True)
    report['status'] = 'completed'
    save()
    print(json.dumps({'evidence': str(evidence / 'results.json'), 'statuses': {status: sum(m['status'] == status for m in report['mutants']) for status in {m['status'] for m in report['mutants']}}}), flush=True)


if __name__ == '__main__':
    main()
