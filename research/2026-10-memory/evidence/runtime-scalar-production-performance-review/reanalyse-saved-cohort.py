"""Independently audit saved scalar CPU records, never execute owner code/binaries."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

MASK = (1 << 64) - 1
SLOT_SEED = 0x51F37
ORDER_SEED = 0x6b17
CASES = [(profile, n, mode) for profile in ['system', 'fixed']
         for n, mode in [(n, 0) for n in [0, 2, 31, 32, 1024, 8193]] + [(31, 1), (31, 2)]]


def expected(length, mode):
    checksum = 0xcbf29ce484222325
    for i in range(length + 1):
        word = 1 if mode == 2 else (
            (SLOT_SEED + i * 0x9e3779b97f4a7c15) & MASK if i < length else 0xfedcba9876543210)
        checksum = ((checksum ^ word) * 0x100000001b3) & MASK
    return checksum


def xor_prefix(n):
    if n < 0:
        return 0
    return (n, 1, n + 1, 0)[n % 4]


def accumulated(checksum, repetitions):
    end = checksum + repetitions - 1
    if end <= MASK:
        return xor_prefix(end) ^ xor_prefix(checksum - 1)
    return xor_prefix(MASK) ^ xor_prefix(checksum - 1) ^ xor_prefix(end & MASK)


def geometric(values):
    return math.exp(statistics.mean(math.log(v) for v in values))


def intervals(values):
    rng = random.Random(ORDER_SEED)
    geometric_draws = []
    median_draws = []
    for _ in range(10000):
        draw = [rng.choice(values) for _ in values]
        geometric_draws.append(geometric(draw))
        median_draws.append(statistics.median(draw))
    geometric_draws.sort()
    median_draws.sort()
    return [geometric_draws[249], geometric_draws[9749]], [median_draws[249], median_draws[9749]]


def audit(path):
    report = json.loads(path.read_text())
    checks = report['checks']
    pilots = report['pilots']
    pairs = report['pairs']
    journal = []
    for index, check in enumerate(checks):
        if 'observation' not in check:
            continue
        command = check['command']
        n, repetitions, mode, seed, expected_hash = command[-5:]
        n, repetitions, mode = int(n), int(repetitions), int(mode)
        assert 0 <= n <= 8193 and 0 < repetitions <= 8388608 and 0 <= mode <= 2
        assert int(seed, 16) == SLOT_SEED and int(expected_hash, 16) == expected(n, mode)
        observation = json.loads(check['stdout'])
        assert observation == check['observation']
        assert observation['kind'] == 'result' and observation['quiescent'] is True
        assert observation['repetitions'] == repetitions and observation['cpu_nanoseconds'] > 0
        assert observation['checksum'] == f'{accumulated(expected(n, mode), repetitions):016x}'
        assert check['returncode'] == 0 and not check['timed_out']
        assert check['peak_rss_bytes'] <= 128 * 1024 * 1024
        journal.append({'check': index, 'label': check['label'], 'input': [n, repetitions, mode],
                        'cpu_nanoseconds': observation['cpu_nanoseconds'],
                        'peak_rss_bytes': check['peak_rss_bytes'], 'checksum': observation['checksum']})
    accepted_repetitions = {}
    pilot_summary = []
    for case in CASES:
        attempts = [row for row in pilots if tuple(row['case']) == case]
        if not attempts:
            continue
        for i, row in enumerate(attempts):
            assert row['repetitions'] == 128 * (2 ** i)
            check = checks[row['check']]
            assert check['label'].startswith('pilot-')
            cpu = check['observation']['cpu_nanoseconds'] / 1e9
            assert cpu == row['measured_cpu_seconds']
            if i < len(attempts) - 1:
                assert cpu < 0.12 and row['repetitions'] < 8388608
        last = attempts[-1]
        if 0.12 <= last['measured_cpu_seconds'] <= 0.5:
            accepted_repetitions[case] = last['repetitions']
        pilot_summary.append({'case': list(case), 'all_attempts': attempts,
                              'accepted': case in accepted_repetitions})
    planned = []
    if len(accepted_repetitions) == 16:
        rng = random.Random(ORDER_SEED)
        for block in range(12):
            order = list(CASES)
            rng.shuffle(order)
            for case in order:
                variants = ['baseline', 'candidate']
                if rng.getrandbits(1):
                    variants.reverse()
                planned.append({'block': block, 'case': list(case), 'order': variants,
                                'repetitions': accepted_repetitions[case]})
        assert report['planned_pairs'] == planned
    else:
        assert not pairs
    independent_pairs = []
    used = set()
    for i, pair in enumerate(pairs):
        assert {key: pair[key] for key in ['block', 'case', 'order', 'repetitions']} == planned[i]
        first, second = [pair['checks'][v] for v in pair['order']]
        assert second == first + 1 and first not in used and second not in used
        used.update([first, second])
        profile, length, mode = pair['case']
        for variant in pair['order']:
            check = checks[pair['checks'][variant]]
            assert check['label'] == f'pair{pair["block"]}-{profile}-n{length}-mode{mode}-{variant}'
            assert check['command'][-5:] == [str(length), str(pair['repetitions']), str(mode),
                                           f'{SLOT_SEED:x}', f'{expected(length, mode):x}']
        baseline_ns = checks[pair['checks']['baseline']]['observation']['cpu_nanoseconds']
        candidate_ns = checks[pair['checks']['candidate']]['observation']['cpu_nanoseconds']
        ratio = baseline_ns / candidate_ns
        assert ratio == pair['baseline_over_candidate_ratio']
        independent_pairs.append({**pair, 'baseline_cpu_nanoseconds': baseline_ns,
                                  'candidate_cpu_nanoseconds': candidate_ns,
                                  'candidate_cpu_change': 1 / ratio - 1})
    summaries = []
    adverse = [row for row in independent_pairs if row['candidate_cpu_change'] > 0]
    complete = report['status'] == 'completed-observation'
    if complete:
        assert len(pairs) == 192 and len(used) == 384
        assert Counter(tuple(pair['case']) for pair in pairs) == Counter({case: 12 for case in CASES})
        for case in CASES:
            rows = [row for row in independent_pairs if tuple(row['case']) == case]
            values = [row['baseline_over_candidate_ratio'] for row in rows]
            geom_interval, median_interval = intervals(values)
            geom, median = geometric(values), statistics.median(values)
            worst = max(row['candidate_cpu_change'] for row in rows)
            large = case[2] == 0 and case[1] >= 1024
            point_gate = geom >= 1.05 and geom_interval[0] > 1 if large else geom >= 0.97 and median >= 0.97
            summary = {'case': list(case), 'ratios': values, 'geometric_ratio': geom,
                       'geometric_interval95': geom_interval, 'median_ratio': median,
                       'median_interval95': median_interval, 'worst_paired_slowdown': worst,
                       'declared_point_and_interval_gate_passed': point_gate,
                       'all_case_worst_pair_gate_passed': worst <= 0.10,
                       'all_declared_numeric_gates_passed': point_gate and worst <= 0.10,
                       'total_cpu_ratio': sum(r['baseline_cpu_nanoseconds'] for r in rows) / sum(r['candidate_cpu_nanoseconds'] for r in rows),
                       'first_six_geometric': geometric(values[:6]), 'last_six_geometric': geometric(values[6:]),
                       'candidate_point_cpu_change': 1 / geom - 1,
                       'candidate_CPU_change_interval95': [1 / geom_interval[1] - 1, 1 / geom_interval[0] - 1],
                       'adverse_pairs': sum(r['candidate_cpu_change'] > 0 for r in rows)}
            for variant in ['baseline', 'candidate']:
                group = [r['baseline_over_candidate_ratio'] for r in rows if r['order'][0] == variant]
                summary[variant + '_first'] = {'count': len(group), 'geometric_ratio': geometric(group) if group else None}
            published = next(s for s in report['summaries'] if tuple(s['case']) == case)
            for key in ['ratios', 'geometric_ratio', 'geometric_interval95', 'median_ratio', 'median_interval95', 'worst_paired_slowdown']:
                assert published[key] == summary[key], (case, key)
            summaries.append(summary)
    summed_cpu = sum(row.get('observed_child_cpu_seconds', 0) for row in checks)
    if complete:
        assert abs(summed_cpu - report['aggregate_child_cpu_seconds']) < 1e-9
        assert summed_cpu <= 180 and report['runner_wall_seconds'] <= 600
        assert all(c['returncode'] == 0 and not c['timed_out'] for c in checks)
    covered_native = used | {row['check'] for row in pilots}
    assert covered_native == {row['check'] for row in journal}, 'unindexed native attempt'
    return {'scope': 'Saved-data independent statistics/doc checks only; provenance and code review separate',
            'source': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'status': report['status'], 'failure': report.get('failure'), 'complete': complete,
            'pilot_attempts': len(pilots), 'paired_children': len(used), 'pairs': len(pairs),
            'native_journal': journal, 'pilots': pilot_summary, 'all_raw_pairs': independent_pairs,
            'all_adverse_pairs': adverse, 'summaries': summaries,
            'all_declared_numeric_gates_passed': all(s['all_declared_numeric_gates_passed'] for s in summaries) if complete else None,
            'summed_child_CPU_seconds': summed_cpu, 'runner_wall_seconds': report.get('runner_wall_seconds'),
            'pointwise_bootstrap_resamples': 10000, 'resampling_seed_per_case': ORDER_SEED,
            'interval_zero_based_endpoints': [249, 9749], 'population_noninferiority_claim': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.results)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['status', 'complete', 'pilot_attempts', 'pairs', 'paired_children', 'all_declared_numeric_gates_passed']}))


if __name__ == '__main__':
    main()
