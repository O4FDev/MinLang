#!/usr/bin/env python3
"""Strict observational performance gates. Never use as a deterministic CI timer test.

Replays every event oracle and verifies source/binary/trace hashes before using
metrics. Missing comparisons fail. Passing is evidence for this workload and
declared competitors only, not statistical significance or language superiority.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys

if not __debug__:
    raise RuntimeError('acceptance checks require Python assertions; do not use -O or PYTHONOPTIMIZE')

from event_report import load
from event_study import analyze, oracle, read_csv, sha
from run_study import percentile


def identity(run):
    s = run['summary']
    return tuple(s[k] for k in ('events', 'width', 'seed', 'spacing_ns', 'burst'))


def validate_phases(phases, summary, rows, recovery):
    """Account for setup, idle cleanup, event service and final teardown.

    Origin agrees with the event trace; setup can start at negative time.
    Every gap must be explicitly labelled wait or overhead. This checks trace
    consistency, not the honesty of an instrumented external executable.
    """
    assert phases, 'empty phase ledger'
    events, windows, setup, teardown = {}, {}, [], []
    previous = phases[0]['start_ns']; active = 0
    allowed = {'setup', 'event', 'idle', 'recovery', 'teardown', 'wait', 'overhead'}
    for phase in phases:
        kind, start, end = (phase[k] for k in ('kind', 'start_ns', 'end_ns'))
        assert kind in allowed, 'unknown lifecycle phase'
        assert type(start) is int and type(end) is int and start == previous and end >= start, 'phase gap, overlap or invalid time'
        previous = end
        if kind != 'wait': active += end - start
        if kind == 'event':
            index = phase['event']; assert type(index) is int and index not in events, 'duplicate/invalid event phase'
            events[index] = (start, end)
        elif kind == 'recovery':
            index = phase['cycle']; assert type(index) is int and index not in windows, 'duplicate/invalid recovery phase'
            windows[index] = (start, end)
        elif kind == 'setup': setup.append((start, end))
        elif kind == 'teardown': teardown.append((start, end))
    assert len(setup) == len(teardown) == 1 and setup[0][0] <= setup[0][1] <= 0, 'missing or invalid setup/teardown'
    assert phases[0]['kind'] == 'setup' and phases[-1]['kind'] == 'teardown', 'incomplete lifecycle endpoints'
    assert previous == summary['lifecycle_ns'], 'phase ledger excludes final teardown time'
    assert events == {r['event']: (r['start_ns'], r['start_ns'] + r['service_ns']) for r in rows}, 'event phases do not match raw event trace'
    assert windows == {r['cycle']: (r['start_ns'], r['start_ns'] + r['duration_ns']) for r in recovery}, 'recovery phases do not match raw trace'
    return active


def measurements(run, rows, recovery, diagnostic=False, phases=None):
    if diagnostic:
        result = {
            'dead_managed_peak': max(r['managed_bytes'] - r['live_bytes'] for r in rows),
            'managed_and_owner_peak': max(r['managed_bytes'] + r['owner_bytes'] for r in rows),
        }
        resources = run.get('resources')
        if resources is not None:
            assert resources.get('scope') == 'setup-through-teardown', 'resource counters exclude lifecycle work'
            for field in ('peak_rss_bytes', 'peak_managed_bytes', 'peak_owner_bytes', 'allocation_count', 'allocated_bytes'):
                value = resources[field]
                assert type(value) is int and value >= 0, 'invalid resource counter'
                result[field] = value
            assert resources['peak_rss_bytes'] > 0, 'RSS measurement is missing'
            assert resources['peak_managed_bytes'] >= max(r['managed_bytes'] for r in rows), 'reported heap peak below observed boundary'
            assert resources['peak_owner_bytes'] >= max(r['owner_bytes'] for r in rows), 'reported owner peak below observed boundary'
        return result
    ordinary = [r for r in rows if r['kind'] == 'ordinary']
    post_rebuild = [r['service_ns'] for r in ordinary if r['event'] % 256 in (1, 2)]
    assert len(ordinary) >= 1000 and post_rebuild, 'too few events for the declared tail gate'
    result = {
        'response_p99': percentile([r['response_ns'] for r in ordinary], .99),
        'response_p999': percentile([r['response_ns'] for r in ordinary], .999),
        'response_max': max(r['response_ns'] for r in rows),
        'post_rebuild_service_mean': sum(post_rebuild) / len(post_rebuild),
        # Include explicit recovery work so moving work to quiet windows alone
        # cannot improve this measure. Between-arrival idle work is not present
        # in the v1 driver; a new driver must extend this accounting.
        'event_and_recovery_service': run['summary']['total_service_ns'] + sum(r['duration_ns'] for r in recovery),
        'lifecycle': run['summary']['lifecycle_ns'],
    }
    if phases is not None:
        result['full_active_service'] = validate_phases(phases, run['summary'], rows, recovery)
    return result


def compare(candidate, baseline, maximum_ratio=1.0):
    """No subtraction of percentiles, pooling, missing metrics, or zero division."""
    assert candidate.keys() == baseline.keys() and candidate, 'comparison metrics differ or are empty'
    outcomes = []
    for metric, value in candidate.items():
        reference = baseline[metric]
        assert type(value) in (int, float) and type(reference) in (int, float) and math.isfinite(value) and math.isfinite(reference) and value >= 0 and reference >= 0, 'nonfinite, negative or invalid comparison metric'
        passed = value <= reference * maximum_ratio
        outcomes.append({'metric': metric, 'candidate': value, 'baseline': reference,
                         'ratio': value / reference if reference else None, 'passed': passed})
    return outcomes


def checked_artifact(base, record):
    path = (base / record['path']).resolve()
    if sha(path) != record['sha256']:
        raise ValueError(f'external artifact hash mismatch: {path}')
    return path


def load_external(path, native):
    """External adapters produce the SAME event/recovery trace semantics.

    No external program or supplied shell command is executed by this checker.
    The JSON format is specified in acceptance.md.
    """
    data = json.loads(path.read_text())
    if data.get('schema') != 1 or data.get('workload') != 'event_workload_v1':
        raise ValueError('unsupported external evidence schema/workload')
    for field in ('host', 'hardware'):
        if data.get(field) != native.get(field) or not data.get(field):
            raise ValueError(f'external comparison changed or omitted {field}')
    if data.get('allocator') != 'system' or data.get('lto') is not False:
        raise ValueError('external comparison must match system allocator and no-LTO campaign')
    entries = {}
    for run in data['runs']:
        if not run.get('toolchain') or not run.get('build_command') or not run.get('run_command') or not run.get('sources'):
            raise ValueError('external evidence lacks build/source provenance')
        for field in ('build_command', 'run_command'):
            if not isinstance(run[field], list) or not all(isinstance(x, str) for x in run[field]):
                raise ValueError('commands must be argument arrays')
        checked_artifact(path.parent, run['binary'])
        for source in run['sources']: checked_artifact(path.parent, source)
        rows = read_csv(checked_artifact(path.parent, run['events']))
        recovery = read_csv(checked_artifact(path.parent, run['recovery']))
        if run.get('mode') not in ('timing', 'diagnostic'):
            raise ValueError('external mode must be timing or diagnostic')
        diagnostic = run['mode'] == 'diagnostic'; s = run['summary']
        # The existing oracle independently reconstructs every expected result.
        analyze(s, rows, recovery, oracle(s['events'], s['width'], s['seed']),
                s['spacing_ns'], s['burst'], diagnostic, 'heap', s['width'], s['seed'])
        if any(r['pending_after'] or r['overrun_ns'] for r in recovery):
            raise ValueError('external baseline failed its recovery envelope')
        key = run['implementation'], run['mode'], identity(run)
        if key in entries: raise ValueError('duplicate external comparison run')
        phases = json.loads(checked_artifact(path.parent, run['phases']).read_text()) if 'phases' in run else None
        entries[key] = measurements(run, rows, recovery, diagnostic, phases)
    return entries


def local_entries(directory, data):
    entries = {}
    for run in data['runs']:
        key = run['configuration'], identity(run)
        if key in entries: raise ValueError('duplicate native comparison run')
        phases = json.loads(checked_artifact(directory, run['phases']).read_text()) if 'phases' in run else None
        entries[key] = (run, measurements(run,
            read_csv(directory / (run['label'] + '.events.csv')),
            read_csv(directory / (run['label'] + '.recovery.csv')), data['mode'] == 'diagnostic', phases))
    return entries


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--timing', type=Path, required=True)
    p.add_argument('--diagnostic', type=Path, required=True)
    p.add_argument('--candidate', default='current-k32-heap')
    p.add_argument('--baselines', nargs='+', default=['fifo-k32-heap', 'eager-k0-heap'])
    p.add_argument('--external', type=Path)
    p.add_argument('--competitors', nargs='+', default=['c', 'rust', 'zig'])
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    if args.output is None:
        args.output = Path(__file__).resolve().parents[2] / 'build' / ('reclamation-acceptance-evidence-' +
                      datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    if args.candidate in args.baselines or len(set(args.baselines)) != len(args.baselines):
        p.error('candidate cannot be its own baseline; duplicate baselines are forbidden')
    if len(set(args.competitors)) != len(args.competitors): p.error('duplicate external competitors')
    tests = []

    def record(name, passed, **details):
        tests.append({'name': name, 'status': 'passed' if passed else 'failed', **details})

    try:
        timing, diagnostic = [load(d.resolve()) for d in (args.timing, args.diagnostic)]
        if timing['mode'] != 'timing' or timing['sanitize'] or diagnostic['mode'] != 'diagnostic' or diagnostic['sanitize']:
            raise ValueError('wrong campaign modes')
        relevant = [k for k in timing['source_sha256'] if k.startswith('runtime/') or k in
                    ('compiler/compiler.min', 'research/reclamation/event_driver.c',
                     'research/reclamation/event_workload.min', 'research/reclamation/variants.py')]
        if timing['compiler_sha256'] != diagnostic['compiler_sha256'] or any(
                timing['source_sha256'][k] != diagnostic['source_sha256'].get(k) for k in relevant):
            raise ValueError('timing and memory campaigns measured different implementations')
        record('evidence/integrity_and_semantics', True)
        timing_sizes = {(r['summary']['events'], r['summary']['width'], r['summary']['seed'])
                        for r in timing['runs'] if r['configuration'] == args.candidate}
        memory_sizes = {(r['summary']['events'], r['summary']['width'], r['summary']['seed'])
                        for r in diagnostic['runs'] if r['configuration'] == args.candidate}
        record('evidence/memory_covers_timing_sizes', bool(timing_sizes) and timing_sizes <= memory_sizes,
               reason='smaller diagnostic graphs cannot establish memory costs at timing sizes')
        external = load_external(args.external.resolve(), timing) if args.external else {}
        any_strict_win = {baseline: False for baseline in [*args.baselines, *args.competitors]}
        for mode, directory, data in [('timing', args.timing, timing), ('diagnostic', args.diagnostic, diagnostic)]:
            entries = local_entries(directory, data)
            selected = [(key, value) for key, value in entries.items() if key[0] == args.candidate]
            expected_arrivals = {(10000, 1), (10000, 16), (50000, 1), (50000, 16)} if mode == 'timing' else {(0, 1)}
            arrivals = {(k[1][3], k[1][4]) for k, _ in selected}
            record(f'{mode}/arrival_coverage', arrivals == expected_arrivals, actual=sorted(arrivals))
            for spacing, burst in expected_arrivals:
                seeds = {k[1][2] for k, _ in selected if k[1][3:] == (spacing, burst)}
                record(f'{mode}/{spacing}/{burst}/seed_coverage', len(seeds) >= 3, seeds=sorted(seeds))
            for (configuration, key), (run, values) in selected:
                prefix = f'{mode}/n{key[0]}/w{key[1]}/seed{key[2]}/spacing{key[3]}/burst{key[4]}'
                record(prefix + '/recovery', run['metrics']['recovery_failed_cycles'] == 0)
                if mode == 'timing':
                    record(prefix + '/full_active_service_coverage', 'full_active_service' in values,
                           reason='requires hashed, complete setup/event/idle/recovery/teardown phase ledger')
                else:
                    record(prefix + '/whole_lifecycle_resource_coverage', 'peak_rss_bytes' in values,
                           reason='requires RSS, transient heap/owner peaks and allocation traffic')
                for baseline in [*args.baselines, *args.competitors]:
                    other = entries.get((baseline, key)) if baseline in args.baselines else None
                    reference = other[1] if other else external.get((baseline, mode, key))
                    if reference is None:
                        record(prefix + f'/{baseline}/coverage', False, reason='matched comparison evidence is missing')
                        continue
                    compared, compared_reference = dict(values), dict(reference)
                    if mode == 'timing':
                        complete = 'full_active_service' in values and 'full_active_service' in reference
                        record(prefix + f'/{baseline}/full_active_service_coverage', complete)
                        if not complete:
                            compared.pop('full_active_service', None); compared_reference.pop('full_active_service', None)
                    else:
                        complete = 'peak_rss_bytes' in values and 'peak_rss_bytes' in reference
                        record(prefix + f'/{baseline}/whole_lifecycle_resource_coverage', complete)
                        if not complete:
                            for field in ('peak_rss_bytes', 'peak_managed_bytes', 'peak_owner_bytes', 'allocation_count', 'allocated_bytes'):
                                compared.pop(field, None); compared_reference.pop(field, None)
                    for outcome in compare(compared, compared_reference):
                        record(prefix + f'/{baseline}/' + outcome['metric'], **outcome)
                        if outcome['metric'] == 'response_p99' and outcome['candidate'] < outcome['baseline']:
                            any_strict_win[baseline] = True
        for baseline, won in any_strict_win.items():
            record(f'{baseline}/at_least_one_strict_response_p99_win', won)
    except (OSError, ValueError, KeyError, AssertionError, TypeError) as error:
        record('evidence/admission', False, reason=str(error))
    result = {'schema': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
              'claim_scope': 'Observed event_workload_v1 results only; no significance or universal dominance claim.',
              'candidate': args.candidate, 'baselines': args.baselines, 'competitors': args.competitors,
              'tests': tests, 'status': 'passed' if tests and all(t['status'] == 'passed' for t in tests) else 'failed'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as output: json.dump(result, output, indent=2); output.write('\n')
    failed = sum(t['status'] == 'failed' for t in tests)
    print(f'{len(tests)} evidence checks: {len(tests) - failed} passed, {failed} failed')
    print(f'Evidence: {args.output.resolve()}')
    return int(result['status'] != 'passed')


if __name__ == '__main__':
    sys.exit(main())
