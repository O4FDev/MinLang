"""Saved aggregate/Text/supplement oracles and traces; no native execution."""
from pathlib import Path
import datetime
import hashlib
import json
import re
from audit_source import apply, ROOT, OUT
from audit_round1 import FINAL, pin_runtime, optimization


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    report = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'gates': []}
    base = ROOT/'build/memory-research-text-join-index/run-ll48qw5d'
    data = json.loads((base/'results.json').read_text())
    assert data['status'] == 'passed' and len(data['checks']) == 107
    pin_runtime(base, 'runtime', FINAL)
    expected = [f'{p}-k{k}-{m}' for p in ['eager','system','fixed','lazy']
                for k in ([32] if p=='eager' else [1,32]) for m in ['o0','o2','sanitize']]
    assert data['coverage']['expected_configurations'] == expected and len(expected)==21
    checks = {x['label']: x for x in data['checks']}
    unicode_names = json.loads((OUT/'prerequisite-inputs/metadata-red.json').read_text())['checks'][-1]['stdout']
    generated_expected = (base/'tests/memory-research-text-join-index.stdout').read_text()
    for label in expected:
        assert checks[label]['returncode']==0 and checks[label]['stdout']==unicode_names
        trap = checks[label+'-invalid-utf8']
        assert trap['returncode']==1 and 'Text contained invalid UTF-8' in trap['stderr']
        assert checks[label+'-language']['stdout']==generated_expected
        want='-O1' if 'sanitize' in label else '-O0' if label.endswith('o0') else '-O2'
        assert optimization(checks[label+'-compile']['command']) == want
        assert optimization(checks[label+'-language-link']['command']) == want
    metadata = data['generated_sanitizer_metadata']
    assert len(metadata)==7 and {x['configuration'] for x in metadata}=={x for x in expected if 'sanitize' in x}
    irhash = sha(base/'generated-sanitize.ll')
    for row in metadata:
        assert row['definitions']==row['sanitize_address_definitions']==12 and row['llvm_sha256']==irhash
    assert all(x['named_unicode_cases']==18 and x['unprinted_aggregate_metadata_groups']==4 for x in data['coverage']['c_runs'])
    report['gates'].append({'gate':'Text profiles','run':base.name,'result_sha256':sha(base/'results.json'),
                           'journal_records':107,'C_configurations':21,'generated_executions':21,'UTF8_traps':21,
                           'printed_names_per_C_run':18,'unprinted_metadata_groups_per_C_run':4,
                           'generated_sanitizer_configurations':7,'ASan_definitions_per_generated_IR':12,
                           'sanitizer_attestation_scope':'Explicit count/hash before each link plus retained shared same-hash IR; unique immutable per-link files not claimed for this original runner.',
                           'status':'accepted scoped saved final-source results'})
    base=ROOT/'build/memory-research-aggregate-join/run-118uclu0'
    data=json.loads((base/'results.json').read_text())
    assert data['status']=='passed' and len(data['checks'])==33
    pin_runtime(base,'original/runtime',FINAL)
    for name, patch in [('minyar_runtime.c','runtime-instrumentation.patch'),('minyar_rc.h','ownership-instrumentation.patch'),('minyar_bounded_rc.h','poll-instrumentation.patch')]:
        assert apply((base/'original/runtime'/name).read_bytes(),(base/patch).read_text())==(base/'runtime'/name).read_bytes()
    prior=ROOT/data['baseline_comparison']['path']
    assert sha(prior)==data['baseline_comparison']['sha256']
    before=json.loads(prior.read_text())
    assert len(data['observations'])==18 and len(data['native_observations'])==8
    checked=0
    measured=['events','object_payload_requests','data_requests','data_payload_request_bytes','service_hooks',
              'offered_queued_units','actual_queued_units','all_poll_calls','all_poll_offered_units','all_poll_work']
    for key,field in [('observations','phases'),('native_observations','phase')]:
        assert len(before[key])==len(data[key])
        for a,b in zip(before[key],data[key]):
            assert (a['configuration'],a['mode'])==(b['configuration'],b['mode'])
            ap=a[field] if isinstance(a[field],list) else [a[field]]
            bp=b[field] if isinstance(b[field],list) else [b[field]]
            assert len(ap)==len(bp)
            for old,new in zip(ap,bp):
                assert all(old.get(k)==new.get(k) for k in measured)
                if 'events' in new:
                    checked+=1
                    polls=[x for x in new['events'] if x[0]==5]
                    helpers=[x for x in new['events'] if x[0]==4]
                    assert len(polls)==new['all_poll_calls']
                    assert sum(x[1] for x in polls)==new['all_poll_offered_units']
                    assert sum(x[3] for x in polls)==new['all_poll_work']
                    assert len(helpers)==new['service_hooks']
                    assert sum(x[1] for x in helpers)==new['offered_queued_units']
                    assert sum(x[3] for x in helpers)==new['actual_queued_units']
    assert checked==98
    raw={'ascii':r'left\ncenter\tend','unicode':'é\\n🙂\\éend','unknown':r'left\ncenter\tend','no-query':r'left\ncenter\tend','empty':'','single':'one'}
    values={'ascii':'left\ncenter\tend','unicode':'é\n🙂éend','unknown':'left\ncenter\tendtail','no-query':'left\ncenter\tend','empty':'','single':'one'}
    for check in data['checks']:
        for cfg in ['system-k32','compiler-arena','system-k32-sanitize']:
            for mode,value in values.items():
                if check['label']==cfg+'-'+mode:
                    query='' if mode=='no-query' else f'{len(value)}\n{sum(map(ord,value))}\n'
                    expected_stdout='-10001\n-10002\n-10003\n'+query+'-10004\n'+query+'-10005\n'+value+'\n'+str(len(value.encode()))+'\n'+raw[mode]+'\n'+raw[mode]+'!\n-10006\n'
                    assert check['stdout']==expected_stdout and check['returncode']==0
    for row in data['native_observations']:
        if row['mode']!='invalid':
            assert row['phase']['actual_queued_units']==row['phase']['all_poll_work']==64
            assert row['phase']['index_builds']==0
    traps=[x for x in data['checks'] if x['label'].endswith('-invalid')]
    assert len(traps)==2 and all(x['returncode']==1 and 'Text contained invalid UTF-8.' in x['stderr'] for x in traps)
    report['gates'].append({'gate':'aggregate','run':base.name,'result_sha256':sha(base/'results.json'),
                           'journal_records':33,'generated_executions':18,'native_debt_controls':6,'UTF8_traps':2,
                           'matched_nonfinal_phase_event_arrays':98,'poll_kind5_count_budget_work_sums_independently_verified':True,
                           'helper_nested_poll_work_not_double_counted':True,'generated_ASan_definitions':13,
                           'compiler_arena_recovery':'inapplicable, process-lifetime arena accounting; no leak-freedom claim',
                           'status':'accepted scoped saved final-source results'})
    base=ROOT/'research/2026-10-memory/evidence/runtime-joint-final/run-xc_5g2zj/list-reserve-asan-supplement'
    data=json.loads((base/'results.json').read_text())
    assert data['status']=='passed' and len(data['checks'])==14
    original=ROOT/'build/memory-research-list-reserve/run-l_bci80g'
    assert sha(original/'results.json')==data['original_results_sha256']
    for name,h in data['source_hashes'].items():
        assert sha(original/'runtime'/name)==h
    expected_names=[f'{p}-sanitize-k{k}' for p in ['eager','system','fixed','lazy'] for k in ([32] if p=='eager' else [1,32])]
    assert [x['configuration'] for x in data['immutable_generated_llvm']]==expected_names
    expected_stdout=f'1024\n37851\n1152\n0\n127\n{sum(i*37 for i in range(1024))+sum(range(128))}\n257\n256\nMINYAR\n258\nMINYAR\nNEW!\n'
    for row in data['immutable_generated_llvm']:
        p=base/row['path'];assert sha(p)==row['sha256']
        headers=re.findall(r'^define[^\n]*',p.read_text(),re.M)
        assert len(headers)==row['definitions']==row['sanitize_address_definitions']==13
        assert all(re.search(r'\)\s+[^\n]*\bsanitize_address\b',x) for x in headers)
    for row in data['checks']:
        assert row['returncode']==0
        if row['label'].endswith('-execute'):
            assert row['stdout']==expected_stdout and row['peak_rss_bytes']<=128*1024*1024
        else:
            assert optimization(row['command'])=='-O1'
            llvm=Path(next(x for x in row['command'] if x.endswith('.ll')))
            assert sha(llvm)==sha(base/llvm.name)
    report['gates'].append({'gate':'List ASan supplement','result_sha256':sha(base/'results.json'),
                           'supplementary_links':7,'supplementary_executions':7,'journal_records':14,
                           'distinct_new_tests':0,'immutable_before_link_IRs':7,'ASan_definitions_each':13,
                           'original_matrix_unchanged':True,'status':'accepted supplementary per-link attestation; original overwritten-path limit remains historical'})
    (OUT/'round2-gate-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
