"""Independent bounded stdlib analysis of frozen JSON, never runs native code."""
from collections import Counter, defaultdict
import difflib
import hashlib
import json
import math
from pathlib import Path
import random
import re
import statistics

OUT = Path(__file__).resolve().parent
INPUT = OUT / 'inputs'
R = INPUT / 'research/2026-10-memory'
FINAL = R / 'evidence/runtime-list-bulk-cpu/run-ws0ma9zu'
MASK = (1 << 64) - 1
SEED = 0x51f37

def read(p):
    return json.loads(p.read_text())

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + '\n')

def expected(n, mode):
    answer = 0xcbf29ce484222325
    for i in range(n + 1):
        word = 1 if mode == 2 else ((SEED + i * 0x9e3779b97f4a7c15) & MASK
                                  if i < n else 0xfedcba9876543210)
        answer = ((answer ^ word) * 0x100000001b3) & MASK
    return answer

def prefix_xor(v):
    if v < 0:
        return 0
    return (v, 1, v + 1, 0)[v & 3]

def accumulation(value, repeats):
    end = value + repeats - 1
    if end <= MASK:
        return prefix_xor(end) ^ prefix_xor(value - 1)
    return prefix_xor(MASK) ^ prefix_xor(value - 1) ^ prefix_xor(end & MASK)

def geom(values):
    return math.exp(statistics.mean(math.log(x) for x in values))

def endpoints(values):
    ordered = sorted(values)
    return [ordered[249], ordered[9749]]

data = read(FINAL / 'results.json')
checks = data['checks']
cases = [(p, n, m) for p in ['system', 'fixed']
         for n, m in [(0, 0), (2, 0), (31, 0), (32, 0), (1024, 0), (8193, 0), (31, 1), (31, 2)]]
used = set()
rows = []
for pair in data['pairs']:
    a, b = (pair['checks'][v] for v in ['baseline', 'candidate'])
    assert [pair['checks'][v] for v in pair['order']] == [min(a, b), max(a, b)]
    assert abs(a - b) == 1
    assert not ({a, b} & used)
    used.update([a, b])
    times = {}
    for variant, index in [('baseline', a), ('candidate', b)]:
        c = checks[index]
        assert c['returncode'] == 0 and not c['timed_out']
        o = json.loads(c['stdout'])
        assert o == c['observation'] and o['kind'] == 'result' and o['recovered']
        n, mode = pair['case'][1:]
        repetitions = pair['repetitions']
        checksum = expected(n, mode)
        assert c['command'][-5:] == [str(n), str(repetitions), str(mode), f'{SEED:x}', f'{checksum:x}']
        assert c['command'][:5] == ['/usr/bin/time', '-l', '/usr/sbin/taskpolicy', '-m', '128']
        assert c['command'][5].endswith('/' + variant + '/' + pair['case'][0])
        assert o['repetitions'] == repetitions and o['cpu_nanoseconds'] > 0
        assert o['checksum'] == f'{accumulation(checksum, repetitions):016x}'
        times[variant] = o['cpu_nanoseconds']
    ratio = times['baseline'] / times['candidate']
    assert ratio == pair['baseline_over_candidate_ratio']
    rows.append({**pair, 'cpu_nanoseconds': times, 'ratio': ratio,
                 'candidate_cpu_change': 1 / ratio - 1})
assert len(rows) == 192 and len(used) == 384
assert set(Counter(tuple(p['case']) for p in rows).values()) == {12}
assert all(Counter(tuple(p['case']) for p in rows if p['block'] == b) == Counter(cases) for b in range(12))

counts = {}
pilot_rows = []
for case in cases:
    pilots = [p for p in data['pilots'] if tuple(p['case']) == case]
    assert pilots and len(pilots) <= 17
    for i, p in enumerate(pilots):
        assert p['repetitions'] == 128 * 2 ** i
        c = checks[p['check']]
        assert p['check'] not in used
        used.add(p['check'])
        assert c['returncode'] == 0 and not c['timed_out']
        o = json.loads(c['stdout'])
        assert o == c['observation'] and o['recovered']
        value = expected(case[1], case[2])
        assert c['command'][-5:] == [str(case[1]), str(p['repetitions']), str(case[2]), f'{SEED:x}', f'{value:x}']
        assert o['checksum'] == f'{accumulation(value, p["repetitions"]):016x}'
        assert o['repetitions'] == p['repetitions']
        assert o['cpu_nanoseconds'] / 1e9 == p['measured_cpu_seconds']
        assert p['measured_cpu_seconds'] < 0.12 if i < len(pilots) - 1 else 0.12 <= p['measured_cpu_seconds'] <= 0.5
        assert p['repetitions'] <= 8388608
    counts[case] = pilots[-1]['repetitions']
    pilot_rows.append({'case': list(case), 'attempts': len(pilots), 'accepted_repetitions': counts[case],
                       'accepted_cpu_seconds': pilots[-1]['measured_cpu_seconds']})
assert sum(r['attempts'] for r in pilot_rows) == 203
rng = random.Random(0x6b17)
plan = []
for block in range(12):
    shuffled = list(cases)
    rng.shuffle(shuffled)
    for case in shuffled:
        order = ['baseline', 'candidate']
        if rng.getrandbits(1):
            order.reverse()
        plan.append({'block': block, 'case': list(case), 'order': order, 'repetitions': counts[case]})
assert plan == data['planned_pairs'] == read(FINAL / 'inputs-and-order.json')
assert plan == [{k: p[k] for k in ['block', 'case', 'order', 'repetitions']} for p in rows]
assert sorted(used) == list(range(19, 606))
assert len(checks) == 606
assert all(c['returncode'] == 0 and not c['timed_out'] for c in checks)

summaries = []
for case in cases:
    selected = [p for p in rows if tuple(p['case']) == case]
    values = [p['ratio'] for p in selected]
    logs = [math.log(v) for v in values]
    rng = random.Random(0x6b17)
    geoms, medians = [], []
    for _ in range(10000):
        indices = [rng.randrange(12) for _ in range(12)]
        geoms.append(math.exp(statistics.mean(logs[i] for i in indices)))
        medians.append(statistics.median(values[i] for i in indices))
    row = {'case': list(case), 'ratios': values, 'geometric_ratio': geom(values),
           'geometric_interval95': endpoints(geoms), 'median_ratio': statistics.median(values),
           'median_interval95': endpoints(medians),
           'worst_paired_slowdown': max(1 / x - 1 for x in values)}
    large = case[2] == 0 and case[1] >= 1024
    row['criterion_passed'] = (row['geometric_ratio'] >= 1.05 and row['geometric_interval95'][0] > 1
                               if large else row['geometric_ratio'] >= 0.97 and row['median_ratio'] >= 0.97
                               and row['worst_paired_slowdown'] <= 0.10)
    published = next(s for s in data['summaries'] if tuple(s['case']) == case)
    for key in row:
        assert row[key] == published[key], (case, key, row[key], published[key])
    row.update(total_cpu_ratio=sum(p['cpu_nanoseconds']['baseline'] for p in selected) /
                              sum(p['cpu_nanoseconds']['candidate'] for p in selected),
               first_six_geometric=geom(values[:6]), last_six_geometric=geom(values[6:]),
               baseline_mean_batch_seconds=statistics.mean(p['cpu_nanoseconds']['baseline'] for p in selected) / 1e9,
               candidate_mean_batch_seconds=statistics.mean(p['cpu_nanoseconds']['candidate'] for p in selected) / 1e9,
               adverse_pairs=sum(v < 1 for v in values),
               baseline_first={'count': sum(p['order'][0] == 'baseline' for p in selected),
                               'geometric_ratio': geom([p['ratio'] for p in selected if p['order'][0] == 'baseline'])},
               candidate_first={'count': sum(p['order'][0] == 'candidate' for p in selected),
                                'geometric_ratio': geom([p['ratio'] for p in selected if p['order'][0] == 'candidate'])},
               candidate_point_cpu_change=1 / row['geometric_ratio'] - 1,
               inverted_interval_candidate_cpu_change=[1 / row['geometric_interval95'][1] - 1,
                                                       1 / row['geometric_interval95'][0] - 1])
    summaries.append(row)
assert all(s['criterion_passed'] for s in summaries) == data['criteria_passed']
assert data['summaries'] == read(R / 'runtime-list-bulk-cpu-results.json')['pointwise_summary']
native = [checks[i] for i in sorted(used)]
assert all(c['peak_rss_bytes'] <= 128 * 1024 * 1024 for c in native)
assert all(c['observer_wall_seconds'] <= 10 for c in checks)
assert all(c['aggregate_child_cpu_seconds'] <= 180 and c['runner_elapsed_seconds'] <= 600 for c in checks)
assert all(c['observed_child_cpu_seconds'] <= 5 for c in checks)
for a, b in zip(checks, checks[1:]):
    assert a['aggregate_child_cpu_seconds'] <= b['aggregate_child_cpu_seconds']
    assert a['runner_elapsed_seconds'] <= b['runner_elapsed_seconds']
resources = {'acquisition_check_count': len(checks), 'native_count': len(native),
             'max_observed_child_cpu_seconds': max(c['observed_child_cpu_seconds'] for c in checks),
             'max_check_wall_seconds': max(c['observer_wall_seconds'] for c in checks),
             'max_native_rss_bytes': max(c['peak_rss_bytes'] for c in native),
             'max_native_clock_seconds': max(c['observation']['cpu_nanoseconds'] / 1e9 for c in native),
             'sum_check_child_cpu_seconds': sum(c['observed_child_cpu_seconds'] for c in checks),
             'aggregate_child_cpu_seconds': data['aggregate_child_cpu_seconds'],
             'runner_wall_seconds': data['runner_wall_seconds']}
save('reanalysis.json', {'scope': 'No native execution; every retained raw final observation checked',
                        'checks_passed': True, 'seed': 0x6b17, 'resamples': 10000,
                        'quantile_zero_based_indices': [249, 9749], 'rows': rows,
                        'adverse_rows': [p for p in rows if p['ratio'] < 1],
                        'summaries': summaries, 'pilot_summary': pilot_rows, 'resources': resources})

# Hash correspondence, source-pair identity and saved disassembly are independent
# of the numerical analysis above. Executable/object hashes cannot be rechecked
# after owner cleanup; retain the limitation explicitly.
indices = []
for run in ['run-ws0ma9zu', 'run-63_142as', 'run-pt288kkw']:
    directory = R / 'evidence/runtime-list-bulk-cpu' / run
    index = read(directory / 'archive-index.json')
    for f in index['files']:
        assert sha(directory / f['path']) == f['sha256']
        assert (directory / f['path']).stat().st_size == f['bytes']
    indices.append({'run': run, 'files_verified': len(index['files'])})
surviving, removed = [], []
for path, value in data['frozen_artifacts'].items():
    relative = path.split('/run-ws0ma9zu/', 1)[1]
    saved = FINAL / relative
    if saved.exists():
        assert sha(saved) == value
        surviving.append(relative)
    else:
        removed.append({'path': relative, 'sha256': value})
assert len(removed) == 6 and len(surviving) == 47
cleanup = read(FINAL / 'selective-disposable-cleanup.json')['removed_own_completed_objects_binaries']
assert sorted(cleanup, key=lambda x: x['path']) == sorted(removed, key=lambda x: x['path'])
for path, value in data['production_entry_hashes'].items():
    assert sha(INPUT / 'runtime' / Path(path).name) == value
    assert sha(FINAL / 'baseline/runtime' / Path(path).name) == value
pair_diff = []
for p in sorted((FINAL / 'baseline/runtime').glob('*')):
    other = FINAL / 'candidate/runtime' / p.name
    if p.read_bytes() != other.read_bytes():
        pair_diff.append(p.name)
assert pair_diff == ['minyar_collections.h']
patch = ''.join(difflib.unified_diff((FINAL / 'baseline/runtime/minyar_collections.h').read_text().splitlines(True),
                                   (FINAL / 'candidate/runtime/minyar_collections.h').read_text().splitlines(True),
                                   fromfile='a/runtime/minyar_collections.h', tofile='b/runtime/minyar_collections.h'))
assert patch == (FINAL / 'candidate/candidate.patch').read_text()
(OUT / 'verified-source-pair.patch').write_text(patch)
for p in (FINAL / 'baseline/tests').glob('*'):
    assert p.read_bytes() == (FINAL / 'candidate/tests' / p.name).read_bytes()
proposal = read(FINAL / 'proposal.json')
for f in proposal['prepared_artifacts']:
    assert sha(FINAL / 'baseline' / f['path']) == f['sha256']
    assert sha(INPUT / f['path']) == f['sha256']

amendments = []
for run, revision, pilot_count, cap in [('run-63_142as', 2, 14, 1048576),
                                       ('run-pt288kkw', 3, 113, 4194304),
                                       ('run-ws0ma9zu', 4, 203, 8388608)]:
    directory = R / 'evidence/runtime-list-bulk-cpu' / run
    d = read(directory / 'results.json')
    prop = read(directory / 'proposal.json')
    assert prop['revision'] == revision
    assert len(d['pilots']) == pilot_count
    for f in prop['prepared_artifacts']:
        assert sha(directory / 'baseline' / f['path']) == f['sha256']
    amendments.append({'run': run, 'revision': revision, 'pilots': pilot_count,
                       'pairs': len(d['pairs']), 'status': d['status'], 'failure': d.get('failure'),
                       'last_pilot': d['pilots'][-1], 'cap': cap})
for previous, following in zip(['run-63_142as', 'run-pt288kkw'], ['run-pt288kkw', 'run-ws0ma9zu']):
    for name in ['memory-research-list-bulk-cpu.c', 'memory-research-list-bulk-cpu.py']:
        old = R / 'evidence/runtime-list-bulk-cpu' / previous / 'baseline/tests' / name
        new = R / 'evidence/runtime-list-bulk-cpu' / following / 'baseline/tests' / name
        diff = ''.join(difflib.unified_diff(old.read_text().splitlines(True), new.read_text().splitlines(True),
                                           fromfile=previous + '/' + name, tofile=following + '/' + name))
        (OUT / f'{previous}-to-{following}-{name}.diff').write_text(diff)

cal = R / 'evidence/runtime-list-bulk-cpu-calibration/run-fe4pyup4'
caldata = read(cal / 'results.json')
calrows = []
for c in caldata['checks']:
    assert c['returncode'] == 0 and not c['timed_out']
    if not c['label'].startswith(('baseline-', 'candidate-')):
        continue
    match = re.fullmatch(r'(baseline|candidate)-(system|fixed)-n(\d+)-mode(\d+)', c['label'])
    assert match, c['label']
    variant, profile, n, mode = match.groups()
    n, mode = int(n), int(mode)
    observations = [json.loads(line) for line in c['stdout'].splitlines() if line.startswith('{')]
    assert observations == c['observations'] and len(observations) == 2
    count, result = observations
    assert bool(count['guard_pending']) == (mode == 1)
    assert count['adds'] == (1 if variant == 'candidate' and mode == 0 else n + 1)
    # Fixed-pool debt preparation also moves backing twice in both variants.
    # Those 192 bytes are not a scalar fast-prefix copy.
    debt_copies = 2 if profile == 'fixed' and mode == 1 else 0
    debt_bytes = 192 if debt_copies else 0
    assert count['copies'] == debt_copies + (1 if variant == 'candidate' and mode == 0 and n else 0)
    assert count['copy_bytes'] == debt_bytes + (8 * n if variant == 'candidate' and mode == 0 else 0)
    assert count['retains'] == (n + 1 if mode == 2 else 0)
    assert result['recovered'] and result['checksum'] == f'{expected(n, mode):016x}'
    calrows.append({'label': c['label'], 'counts': count, 'result': result})
assert len(calrows) == 32
for c in calrows:
    if '-mode1' in c['label'] or '-mode2' in c['label']:
        counterpart = next(x for x in calrows if x['label'] == c['label'].replace('baseline-', 'candidate-'))
        assert c['counts'] == counterpart['counts']
calfixture = cal / 'baseline/tests/memory-research-list-bulk-cpu.c'
timingfixture = FINAL / 'baseline/tests/memory-research-list-bulk-cpu.c'
(OUT / 'calibration-to-timing-fixture.diff').write_text(''.join(difflib.unified_diff(
    calfixture.read_text().splitlines(True), timingfixture.read_text().splitlines(True),
    fromfile='calibration', tofile='timing')))

machine = []
for variant in ['baseline', 'candidate']:
    for profile in ['system', 'fixed']:
        p = FINAL / f'linked-machine-code-{variant}-{profile}.s'
        text = p.read_text()
        functions = {}
        for name in ['minyar_list_appended', 'main', 'research_checksum']:
            match = re.search(r'^_' + name + r':\n(.*?)(?=^_[^\s:]+:|\Z)', text, re.M | re.S)
            assert match, (p, name)
            functions[name] = match.group(0)
        assert '_research_checksum' in functions['main']
        assert '_minyar_list_appended' in functions['main']
        assert functions['main'].count('_clock_gettime') == 2
        assert 'ldr\tx10, [x8], #0x8' in functions['research_checksum']
        assert 'mul\tx0, x10, x9' in functions['research_checksum']
        assert '_minyar_list_add' in functions['minyar_list_appended']
        if variant == 'candidate':
            assert '_memcpy' in functions['minyar_list_appended']
        else:
            assert '_memcpy' not in functions['minyar_list_appended']
        excerpt = OUT / f'machine-code-{variant}-{profile}-selected.s'
        excerpt.write_text('\n'.join(functions.values()))
        clocks = [line for line in functions['main'].splitlines() if '_clock_gettime' in line]
        calls = [line for line in functions['main'].splitlines() if '_research_checksum' in line or '_minyar_list_appended' in line]
        copy = [line for line in functions['minyar_list_appended'].splitlines() if '_memcpy' in line]
        machine.append({'variant': variant, 'profile': profile, 'source': str(p.relative_to(INPUT)),
                        'sha256': sha(p), 'clock_calls': clocks, 'main_calls': calls,
                        'bulk_copy_calls': copy, 'selected_excerpt': excerpt.name})
save('provenance-verification.json', {'archive_indices': indices, 'final_freeze_surviving_verified': surviving,
                                    'final_freeze_removed_owner_hashes_only': removed,
                                    'source_pair_different_files': pair_diff,
                                    'candidate_patch_sha256': sha(FINAL / 'candidate/candidate.patch'),
                                    'baseline_collections_sha256': sha(FINAL / 'baseline/runtime/minyar_collections.h'),
                                    'candidate_collections_sha256': sha(FINAL / 'candidate/runtime/minyar_collections.h'),
                                    'runtime_c_sha256': sha(FINAL / 'baseline/runtime/minyar_runtime.c'),
                                    'proposal_revision': proposal['revision'],
                                    'amendments': amendments, 'calibration_rows': calrows, 'machine_code': machine,
                                    'testing_define_present': '#define MINYAR_RC_TESTING 1' in timingfixture.read_text(),
                                    'binary_execution_by_reviewer': False})
print(json.dumps({'pairs': len(rows), 'all_summary_fields_exact': True, 'criteria_passed': data['criteria_passed'],
                  'adverse_pairs': sum(p['ratio'] < 1 for p in rows), 'resources': resources,
                  'indices': indices, 'frozen_files': len(surviving), 'deleted_objects_binaries': len(removed)}))
