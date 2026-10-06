"""Independent saved correctness/count/oracle audit, without native execution."""
from pathlib import Path
import datetime
import hashlib
import json
import re
from audit_source import apply, ROOT, OUT

FINAL = {'minyar_runtime.c': 'd919f066a0e71c80cb079a22659928541e958b68b81a645d7631f52ec8531a51',
         'minyar_collections.h': '3b7ce602bc256dc8a42f49d87fd6cccd0eb28132d952e3eb34284614c4725810'}
BEFORE = {'minyar_runtime.c': 'c4e78f59096e0af8926c8d06febb9277e8c7cb7e5de8fc63b907d3afb613fcb4',
          'minyar_collections.h': '01ae1e88dbcd98a9f8815a7a8e0508247a19f7f0b912d938544db129191eb4c0'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(kind, run):
    base = ROOT / 'build' / kind / run
    return base, json.loads((base / 'results.json').read_text())


def pin_runtime(base, sub, expected):
    for name, digest in expected.items():
        assert sha(base / sub / name) == digest


def optimization(command):
    flags = [x for x in command if re.fullmatch(r'-O(?:[0123szg]|fast)', x)]
    return flags[-1] if flags else None


def main():
    report = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'gates': []}
    base, data = read('memory-research-list-reserve', 'run-l_bci80g')
    assert data['status'] == 'passed' and len(data['checks']) == 109
    pin_runtime(base, 'runtime', FINAL)
    profiles = {'eager': [32], 'system': [1, 32], 'fixed': [1, 32], 'lazy': [1, 32], 'arena': [32]}
    labels = [f'{p}-{m}-k{k}' for p, budgets in profiles.items() for m in ['o0', 'o2', 'sanitize'] for k in budgets]
    checks = {x['label']: x for x in data['checks']}
    assert len(checks) == 109 and len(labels) == 24
    for label in labels:
        assert checks[label]['returncode'] == 0
        expected = '-O1' if 'sanitize' in label else '-O0' if '-o0-' in label else '-O2'
        assert optimization(checks[label + '-compile']['command']) == expected
        if not label.startswith('arena'):
            assert checks[label + '-generated-run']['returncode'] == 0
            assert optimization(checks[label + '-generated-link']['command']) == expected
    traps = [x for x in data['checks'] if x.get('expected_diagnostic')]
    assert len(traps) == 17 and all(x['returncode'] == 1 and x['expected_diagnostic'] in x['stderr'] for x in traps)
    generated_stdout = f'1024\n37851\n1152\n0\n127\n{sum(i * 37 for i in range(1024)) + sum(range(128))}\n257\n256\nMINYAR\n258\nMINYAR\nNEW!\n'
    assert all(x['stdout'] == generated_stdout for x in data['checks'] if x['label'].endswith('-generated-run'))
    report['gates'].append({'gate': 'List reservation', 'run': base.name, 'result_sha256': sha(base/'results.json'),
                            'native_configurations': 24, 'generated_executions': 21, 'expected_traps': 17,
                            'journal_records': 109, 'generated_asan_definitions': 13, 'status': 'accepted scoped saved results'})
    for run, config in [('run-rkjr1y18', {'profile':'system','budget':32,'sanitize':False}),
                        ('run-f493st0w', {'profile':'fixed','budget':1,'sanitize':False}),
                        ('run-xq_rxk4i', {'profile':'system','budget':32,'sanitize':True})]:
        base, data = read('memory-research-list-bulk', run)
        assert data['status'] == 'passed-candidate' and data['configuration'] == config and len(data['checks']) == 4
        pin_runtime(base, 'original/runtime', FINAL)
        for name, patch in [('minyar_collections.h','list-observer.patch'), ('minyar_rc.h','rc-observer.patch'), ('minyar_bounded_rc.h','poll-observer.patch')]:
            assert apply((base/'original/runtime'/name).read_bytes(), (base/patch).read_text()) == (base/'runtime'/name).read_bytes()
        prior = ROOT / data['baseline_comparison']['path']
        assert sha(prior) == data['baseline_comparison']['sha256']
        old = json.loads(prior.read_text())
        assert old['variant'] == 'baseline' and old['configuration'] == config
        assert len(old['observations']) == len(data['observations']) == 34
        assert [json.loads(x) for x in data['checks'][-1]['stdout'].splitlines()] == data['observations']
        expected_shapes = [('idle', n, t) for n in [0,1,2,3,7,15,31,32,1023,1024,4095,4096,8193] for t in [0,1]]
        expected_shapes += [(mode,31,t) for mode in ['object','frame','chunk'] for t in [0,1]] + [('references',4,t) for t in [0,1]]
        assert [(x['mode'],x['length'],x['take']) for x in data['observations']] == expected_shapes
        for a, b in zip(old['observations'], data['observations']):
            if b['mode'] == 'idle':
                excluded = {'add_entries','copy_entries','copy_bytes'}
                assert {k:v for k,v in a.items() if k not in excluded} == {k:v for k,v in b.items() if k not in excluded}
                assert b['add_entries'] == 1-b['take'] and b['take_entries'] == b['take']
                assert b['copy_entries'] == bool(b['length']) and b['copy_bytes'] == b['length']*8
                assert not b['guard_pending']
            else:
                assert a == b
            assert b['recovered']
        assert optimization(data['checks'][1]['command']) == ('-O1' if config['sanitize'] else '-O2')
        assert '--require-bulk' in data['checks'][2]['command'] and data['checks'][2]['returncode'] == 0
        report['gates'].append({'gate':'scalar trace','run':run,'configuration':config,'result_sha256':sha(base/'results.json'),
                                'distinct_shapes':34,'full_observation_rows':34,'target_executions':1,'full_executions':1,
                                'journal_records':4,'all_fields_equal_except_idle_source_entry_copy_counters':True,
                                'observer_patches_reconstruct_exact_executed_headers':True,'status':'accepted scoped saved results'})
    baseline, before = read('memory-research-list-bulk-caller', 'run-k78_be59')
    final, after = read('memory-research-list-bulk-caller', 'run-gx8pkm5l')
    assert before['status'] == after['status'] == 'passed'
    pin_runtime(baseline, 'runtime', BEFORE)
    pin_runtime(final, 'runtime', FINAL)
    assert len(before['checks']) == 4 and len(after['checks']) == 18
    assert (baseline/'tests/memory-research-list-bulk-caller.min').read_bytes() == (final/'tests/memory-research-list-bulk-caller.min').read_bytes()
    oracle = json.loads((OUT/'revision2-static-verification.json').read_text())['independent_expected_lines']
    expected = '\n'.join(oracle)+'\n'
    finalchecks = {x['label']:x for x in after['checks']}
    assert before['checks'][-1]['stdout'] == expected
    modes = ['system-o0','system-o2','fixed-o0','fixed-o2','system-sanitize']
    for mode in modes:
        assert finalchecks[mode]['stdout'] == expected and finalchecks[mode]['returncode'] == 0
        want = '-O1' if 'sanitize' in mode else '-O0' if mode.endswith('o0') else '-O2'
        assert optimization(finalchecks['link-'+mode]['command']) == want
        if mode in ['system-o2','fixed-o2','system-sanitize']:
            stack = mode != 'fixed-o2'
            native = ''.join(f'mode={m} length={n} stack={int(m==2 and stack)} recovered\n' for m in range(3) for n in [0,257])
            assert finalchecks[mode+'-native']['stdout'] == native
    assert after['middle_slot_output_calibration']['index'] == 26 and after['middle_slot_output_calibration']['rejected']
    actual = finalchecks['system-o2']['stdout'].splitlines()
    assert actual[26] == '48'
    actual[26] = '-999'
    assert '\n'.join(actual)+'\n' != expected
    assert after['output_only_oracle_calibration']['corrupted_stdout'] != expected
    report['gates'].append({'gate':'revised caller','baseline_run':baseline.name,'final_run':final.name,
                            'baseline_result_sha256':sha(baseline/'results.json'),'final_result_sha256':sha(final/'results.json'),
                            'baseline_generated_executions':1,'final_generated_executions':5,'native_configurations':3,
                            'native_owner_length_shapes_per_configuration':6,'expected_generated_output_lines':55,
                            'journal_records':18,'generated_asan_definitions':14,
                            'calibration':'Saved-output order and middle-slot mutation rejected; no native/source mutant or runtime defect',
                            'status':'accepted scoped saved results'})
    (OUT/'round1-gate-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
