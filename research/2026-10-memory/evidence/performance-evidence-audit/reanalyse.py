#!/usr/bin/env python3
"""Bounded, stdlib-only reanalysis of frozen observations. Never runs a fixture."""
import hashlib
import json
import math
from pathlib import Path
import random
import statistics as st

HERE = Path(__file__).resolve().parent
INPUT = HERE / 'inputs'
BASE = 'research/2026-10-memory/evidence/'
RUNS = {
    'ascii': ('runtime/results/ascii-paired-timing.json', 'candidate'),
    'list': ('runtime/results/final-list-timing.json', 'after'),
    'aggregate': ('runtime-aggregate-timing/run-rrkuiyad/results.json', 'candidate'),
}


def read(path):
    return json.loads((INPUT / path).read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def geo(values):
    return math.exp(st.fmean(math.log(x) for x in values))


def quantile(values, p):
    values = sorted(values)
    pos = (len(values) - 1) * p
    lo = int(pos)
    return values[lo] + (values[min(lo + 1, len(values) - 1)] - values[lo]) * (pos - lo)


def bootstrap(ratios, seed, estimator, aggregate_endpoints=False, cluster=1):
    rng = random.Random(seed)
    groups = [ratios[i:i + cluster] for i in range(0, len(ratios), cluster)]
    samples = sorted(estimator([v for group in rng.choices(groups, k=len(groups)) for v in group])
                     for _ in range(10000))
    if aggregate_endpoints:
        interval = [samples[249], samples[9749]]
    else:
        interval = [quantile(samples, .025), quantile(samples, .975)]
    return {'interval95': interval,
            'interval99_pointwise_sensitivity': [quantile(samples, .005), quantile(samples, .995)],
            'resamples': 10000, 'seed': seed, 'cluster_adjacent_pairs': cluster}


def identity(case):
    return case['mode'] if 'profile' not in case else f"{case['profile']}/{case['mode']}/{case['length']}"


def examine_case(case, variant, aggregate=False):
    pairs = case['pairs']
    ratios = [p['before']['cpu_ns'] / p[variant]['cpu_ns'] for p in pairs]
    assert len(pairs) == 12
    for pair in pairs:
        assert sorted(pair['order']) == sorted(['before', variant])
        for name in ['before', variant]:
            assert pair[name]['cpu_ns'] > 0 and pair[name]['wall_ns'] > 0
    estimator = geo if aggregate else st.median
    reproduced = bootstrap(ratios, 681492 if aggregate else 20261002, estimator, aggregate)
    key = 'cpu_ns_before_over_candidate' if aggregate else 'cpu_before_over_' + variant
    recorded = case[key]
    expected_ci = ([recorded['lower'], recorded['upper']] if aggregate else
                   [recorded['confidence_interval']['lower'], recorded['confidence_interval']['upper']])
    assert all(abs(a - b) < 1e-12 for a, b in zip(reproduced['interval95'], expected_ci))
    assert abs(estimator(ratios) - recorded['geometric_mean' if aggregate else 'median']) < 1e-12
    log_ratios = [math.log(x) for x in ratios]
    mean_log = st.fmean(log_ratios)
    slope = sum((i - 5.5) * (x - mean_log) for i, x in enumerate(log_ratios)) / sum((i - 5.5)**2 for i in range(12))
    orders = {}
    for first in ['before', variant]:
        selected = [x for x, p in zip(ratios, pairs) if p['order'][0] == first]
        orders[first + '_first'] = {'count': len(selected), 'geomean': geo(selected), 'median': st.median(selected)}
    residual = [x - mean_log for x in log_ratios]
    denom = sum(x*x for x in residual)
    lag = sum(a*b for a, b in zip(residual[:-1], residual[1:])) / denom if denom else 0
    before = [p['before']['cpu_ns'] for p in pairs]
    after = [p[variant]['cpu_ns'] for p in pairs]
    wall_ratios = [p['before']['wall_ns'] / p[variant]['wall_ns'] for p in pairs]
    return {
        'case': identity(case), 'pairs': 12, 'ratios': ratios,
        'recorded_estimator': 'geometric mean' if aggregate else 'median of ratios',
        'recorded_estimator_reproduced': estimator(ratios), 'bootstrap_reproduced': reproduced,
        'all_rows_summaries': {'median': st.median(ratios), 'geomean': geo(ratios),
                              'arithmetic_mean': st.fmean(ratios),
                              'ratio_of_total_cpu': sum(before) / sum(after),
                              'minimum': min(ratios), 'maximum': max(ratios),
                              'candidate_faster_count': sum(x > 1 for x in ratios)},
        'robust_sensitivity': {'median_bootstrap': bootstrap(ratios, 914721, st.median),
                               'geomean_bootstrap': bootstrap(ratios, 914721, geo),
                               'adjacent_two_pair_cluster_geomean': bootstrap(ratios, 914721, geo, cluster=2)},
        'chronology_sensitivity': {'first_six_geomean': geo(ratios[:6]),
                                   'last_six_geomean': geo(ratios[6:]),
                                   'multiplicative_log_fit_change_first_to_last': math.exp(11*slope),
                                   'lag1_log_autocorrelation_descriptive': lag,
                                   'orders': orders},
        'batch_cpu_ms': {'before_mean': st.fmean(before)/1e6, 'candidate_mean': st.fmean(after)/1e6,
                         'before_range': [min(before)/1e6, max(before)/1e6],
                         'candidate_range': [min(after)/1e6, max(after)/1e6]},
        'wall': {'median_ratio': st.median(wall_ratios), 'geomean_ratio': geo(wall_ratios),
                 'ratio_range': [min(wall_ratios), max(wall_ratios)],
                 'max_wall_over_cpu': max(p[v]['wall_ns']/p[v]['cpu_ns'] for p in pairs for v in ['before', variant])},
    }


def check_randomization(d, family, variant):
    cases = d['measurements']
    if family == 'list':
        rng = random.Random(20261004)
        orders = []
        for _ in range(12):
            order = ['before', variant]
            if rng.randrange(2):
                order.reverse()
            orders.append(order)
        assert all([p['order'] for p in c['pairs']] == orders for c in cases)
        return {'verified': True, 'design': 'Fixed case/profile order; seed reset each case, same 12 AB/BA orders; no randomized cross-case blocks.', 'orders': orders}
    rng = random.Random(d['seed'])
    lookup = {c['mode']: c for c in cases}
    for block in range(12):
        modes = list(lookup)
        rng.shuffle(modes)
        for mode in modes:
            order = ['before', variant]
            rng.shuffle(order)
            row = lookup[mode]['pairs'][block]
            assert row['block'] == block and row['mode_order'] == modes and row['order'] == order
    return {'verified': True, 'design': '12 randomized mode blocks, adjacent randomized variant pairs; seed exactly replayed.'}


def check_rows(d, family, variant):
    """Independently connect journal stdout/clocks to pair records and expected values."""
    if family in ['ascii', 'aggregate']:
        observations = [c for c in d['checks'] if c.get('label', '').startswith(('block', 'warmup-', 'pilot-'))]
        labels = [c['label'] for c in observations]
        assert len(labels) == len(set(labels))
        expected = set()
        byte_totals = {'known': 65536, 'unknown': 65536, 'no-query': 65536, 'short': 8, 'unicode': 768}
        def expected_stdout(mode, loops):
            if family == 'ascii':
                initial = {'known': 65536, 'unknown': 0, 'no-query': 65536, 'short': 8, 'unicode': 256}[mode]
                units = 257 if mode == 'unicode' else 9 if mode == 'short' else 65537
                return f'{initial}\n{loops * units}\n{byte_totals[mode]}\n'
            raw = (INPUT / BASE / 'runtime-aggregate-timing/run-rrkuiyad' / (mode + '.txt')).read_text()
            value = raw.replace('\\n', '\n').replace('\\t', '\t') + ('tail' if mode == 'unknown' else '')
            units = len(value.encode()) if mode == 'no-query' else len(value)
            return f'{loops*units}\n{len(value.encode())}\n{value}\ntrue\n'

        for case in d['measurements']:
            mode = case['mode']
            for i, pair in enumerate(case['pairs']):
                for name in ['before', variant]:
                    label = f'block{i}-{mode}-{name}'
                    expected.add(label)
                    row = next(c for c in observations if c['label'] == label)
                    assert row['returncode'] == 0 and json.loads(row['stderr']) == pair[name]
                    assert row['stdout'] == expected_stdout(mode, case['repetitions'])
            for warm in case['warmups']:
                label = f"warmup-{warm['variant']}-{mode}"
                expected.add(label)
                row = next(c for c in observations if c['label'] == label)
                assert row['returncode'] == 0 and json.loads(row['stderr']) == warm['observation']
                assert row['stdout'] == expected_stdout(mode, case['repetitions'])
            if family == 'aggregate':
                label = 'pilot-' + mode
                expected.add(label)
                row = next(c for c in observations if c['label'] == label)
                pilot = case['pilot']
                assert row['returncode'] == 0 and json.loads(row['stderr']) == pilot['observation']
                assert row['stdout'] == expected_stdout(mode, pilot['loops'])
                assert case['repetitions'] == max(1, min(1000000, round(pilot['loops'] * 200000000 / pilot['observation']['cpu_ns'])))
        assert set(labels) == expected
        assert len(d['checks']) == len(observations) + 4
        return {'paired_executions': 120, 'warmup_executions': 10, 'pilot_executions': 5 if family == 'aggregate' else 0,
                'no_missing_duplicate_or_unreported_timing_rows': True, 'all_paired_warmup_pilot_stdout_and_clock_records_rechecked': True}
    executions = [c for c in d['checks'] if len(c['command']) == 4 and not c['command'][0] == 'clang']
    offset = 0
    for case in d['measurements']:
        group = executions[offset:offset + 26]
        offset += 26
        expected = case['iterations']*(case['iterations']-1)//2 if case['mode'] == 'append' else case['iterations']*(case['length']-1)*37
        ordered = [(w['variant'], w['observation']) for w in case['warmups']]
        ordered += [(v, p[v]) for p in case['pairs'] for v in p['order']]
        for row, (v, observation) in zip(group, ordered):
            assert row['command'][0].endswith(f"{case['profile']}-{v}")
            assert row['command'][1:] == [str(case['length']), str(case['iterations']), case['mode']]
            assert row['returncode'] == 0 and json.loads(row['stdout']) == observation
            assert observation['checksum'] == expected
        assert len(group) == 26 and len(ordered) == 26
    assert offset == len(executions) == 208
    return {'paired_executions': 192, 'warmup_executions': 16,
            'no_missing_duplicate_or_unreported_timing_rows': True, 'all_stdout_and_clock_records_rechecked': True}


def main():
    manifest = json.loads((HERE / 'inputs.json').read_text())
    assert all(digest(INPUT / row['path']) == row['sha256'] for row in manifest['files'])
    output = {'method': 'All rows retained. Independent stdlib estimator, seeded randomization/journal/oracle rechecks. Sensitivity intervals are descriptive resampling, not population guarantees.',
              'inputs_manifest_sha256': digest(HERE / 'inputs.json'), 'families': {}}
    for family, (path, variant) in RUNS.items():
        d = read(BASE + path)
        assert d['status'] == 'passed'
        output['families'][family] = {'input_sha256': digest(INPUT / BASE / path),
                                     'randomization': check_randomization(d, family, variant),
                                     'row_integrity': check_rows(d, family, variant),
                                     'cases': [examine_case(c, variant, family == 'aggregate') for c in d['measurements']]}
    # Independent refined count observer comparison, including every direct poll.
    before = read(BASE + 'runtime-aggregate/run-ltiaucr9/results.json')
    after = read(BASE + 'runtime-aggregate/run-z4ozpuwj/results.json')
    ignored = {'index_builds', 'index_input_bytes'}
    compared = 0
    for key in ['observations', 'native_observations']:
        assert len(before[key]) == len(after[key])
        for a, b in zip(before[key], after[key]):
            assert (a['configuration'], a['mode']) == (b['configuration'], b['mode'])
            aa = a.get('phases', [a.get('phase')]); bb = b.get('phases', [b.get('phase')])
            assert len(aa) == len(bb)
            for x, y in zip(aa, bb):
                if x is None:
                    continue
                assert {k:v for k,v in x.items() if k not in ignored} == {k:v for k,v in y.items() if k not in ignored}
                if 'events' not in x:
                    # Final recovery rows are observations, not event phases.
                    assert x['phase'] == 'final'
                    continue
                polls = [event for event in x['events'] if event[0] == 5]
                assert x['all_poll_calls'] == len(polls)
                assert x['all_poll_work'] == sum(event[3] for event in polls)
                assert x['all_poll_offered_units'] == sum(event[1] for event in polls)
                compared += 1
    output['all_poll_observer'] = {'matched_phase_arrays': compared,
                                   'all_events_requests_copy_service_poll_fields_equal_except_index_counts': True,
                                   'poll_counts_offerings_work_independently_summed': True}
    (HERE / 'reanalysis.json').write_text(json.dumps(output, indent=2) + '\n')
    for family, data in output['families'].items():
        for c in data['cases']:
            s = c['all_rows_summaries']; t = c['chronology_sensitivity']
            print(f"{family:9} {c['case']:19} recorded={c['recorded_estimator_reproduced']:.6f} CI={c['bootstrap_reproduced']['interval95']} median={s['median']:.6f} geo={s['geomean']:.6f} totals={s['ratio_of_total_cpu']:.6f} halves={t['first_six_geomean']:.6f}/{t['last_six_geomean']:.6f} range={s['minimum']:.6f}/{s['maximum']:.6f}")
    print('All journal/randomization/interval/count assertions passed.')


if __name__ == '__main__':
    main()
