"""Check evidence documents, not peer/local programs or proposed regressions."""
import collections
import hashlib
import json
import math
import pathlib
import re

ROOT = pathlib.Path('/Users/luke/Projects/Minyar-Lang')
BASE = ROOT / 'evidence/peer-readonly/values-round9'
JSON = ROOT / 'research/2026-10-memory/peer-readonly-values-round9.json'
MD = JSON.with_suffix('.md')
checks = []


def load(path):
    return json.loads(path.read_text())


def sha(b):
    return hashlib.sha256(b).hexdigest()


def check(name, ok, detail=None):
    checks.append(dict(name=name, passed=bool(ok), detail=detail))


def spans(name, ranges, line_count):
    for n, extent in enumerate(ranges):
        check(f'{name}:{n}',len(extent)==2 and 1<=extent[0]<=extent[1]<=line_count,extent)


data = load(JSON)
group_ids = [g['id'] for g in data['comparison_groups']]
check('unique group IDs',len(group_ids)==len(set(group_ids)))
check('group count',len(group_ids)==data['counts']['authored_comparison_groups'])
check('disposition counts',dict(collections.Counter(g['disposition'] for g in data['comparison_groups']))==data['counts']['group_dispositions'])
selected = {s['path']:s for s in data['selected_sources']}
check('exactly four complete selected files',len(selected)==4)
check('selected raw line count',sum(s['lines'] for s in selected.values())==data['counts']['selected_raw_physical_lines'])
all_sources=load(BASE/'sources.json')
source_by_path={s['path']:s for s in all_sources}
raw={s['path']:(ROOT/s['evidence_path']).read_bytes() for s in all_sources}
lines={path:b.decode().splitlines() for path,b in raw.items()}
for s in all_sources:
    path=s['path'];b=raw[path]
    check(f'source hash {path}',sha(b)==s['sha256'])
    check(f'source bytes/lines {path}',len(b)==s['bytes'] and len(b.splitlines())==s['lines'])
for path,s in selected.items():
    check(f'complete extent {path}',s['read_extent']==[[1,len(lines[path])]] and s['selected_unread_lines']==0)
    check(f'pinned URL {path}',s['commit'] in s['raw_url'] and s['commit'] in s['url'])
    for licpath in s['license_paths']:
        check(f'license retained {path}:{licpath}',any(l['path']==licpath and l['language']==s['language'] and l['commit']==s['commit'] for l in data['licenses']))

for g in data['comparison_groups']:
    src=selected[g['path']]
    check(f'group pin/hash {g["id"]}',g['sha256']==src['sha256'] and g['commit']==src['commit'])
    spans(f'group span {g["id"]}',g['source_spans'],len(lines[g['path']]))
    spans(f'group helper {g["id"]}',g['helper_spans'],len(lines[g['path']]))
    check(f'group source oracle lines {g["id"]}',all(1<=n<=len(lines[g['path']]) for n in g['oracle_lines']))
    check(f'group local references {g["id"]}',set(g['local_coverage_ids'])=={x['coverage_id'] for x in g['local_source_coverage']})
    check(f'group unexecuted {g["id"]}',g['port_status']=='not_implemented; not_compiled; not_executed')

expected_oracles=set()
for path in selected:
    for n,t in enumerate(lines[path],1):
        if re.search(r'\b(?:static_assert|assert)\s*\(',t):expected_oracles.add((path,n))
    if path.endswith('/array.go'):expected_oracles.update((path,n) for n in [47,60,113,127])
    if path.endswith('/shift.go'):expected_oracles.update((path,n) for n in [18,32])
actual_oracles=[(x['path'],x['line']) for x in data['oracle_source_index']]
check('oracle index exact site union',set(actual_oracles)==expected_oracles)
check('oracle index has no duplicate sites',len(actual_oracles)==len(set(actual_oracles)))
check('oracle kind counts',dict(collections.Counter(x['kind'] for x in data['oracle_source_index']))==data['counts']['oracle_sites_by_kind'])
for site in data['oracle_source_index']:
    attached={g['id'] for g in data['comparison_groups'] if g['path']==site['path'] and site['line'] in g['oracle_lines']}
    check(f'oracle attachment {site["path"]}:{site["line"]}',bool(attached) and attached==set(site['group_ids']))
    check(f'oracle raw text {site["path"]}:{site["line"]}',site['text']==lines[site['path']][site['line']-1])
for src in data['selected_file_nonassertion_review']:
    path=src['path'];spans(f'nonassertion {path}',src['spans'],len(lines[path]))
    reviewed={n for a,b in src['spans'] for n in range(a,b+1)} | {n for p,n in expected_oracles if p==path}
    check(f'every selected physical line accounted {path}',reviewed==set(range(1,len(lines[path])+1)))
for h in data['in_file_helper_reviews']:
    spans(f'helper {h["name"]}',h['reviewed_spans'],len(lines[h['path']]))
for s in data['support_helper_reviews']:
    path=s['path'];spans(f'support {path}',s['reviewed_spans'],len(lines[path]));spans(f'support complement {path}',s['unreviewed_complement'],len(lines[path]))
    reviewed={i for a,b in s['reviewed_spans'] for i in range(a,b+1)}
    complement={i for a,b in s['unreviewed_complement'] for i in range(a,b+1)}
    check(f'support partition {path}',not reviewed&complement and reviewed|complement==set(range(1,len(lines[path])+1)))
    for item in s['reviewed_span_sha256']:
        a,b=item['lines'];check(f'support span digest {path}:{a}',sha(b''.join(raw[path].splitlines(keepends=True)[a-1:b]))==item['sha256'])

refs=load(BASE/'reference-snapshots.json')
ref_by_path={r['path']:r for r in refs if 'snapshot' in r}
drift=[]
for r in refs:
    if 'snapshot' not in r:continue
    b=(ROOT/r['snapshot']).read_bytes()
    check(f'reference snapshot hash {r["path"]}',sha(b)==r['sha256'])
    check(f'reference snapshot byte/line count {r["path"]}',len(b)==r['bytes'] and len(b.splitlines())==r['physical_lines'])
    live=ROOT/r['path']
    if live.exists() and sha(live.read_bytes())!=r['sha256']:
        drift.append(dict(path=r['path'],frozen_sha256=r['sha256'],observed_sha256=sha(live.read_bytes()),meaning='Concurrent live change; round9 mappings still bind to retained source snapshot. This lane did not author outside-boundary changes.'))
for c in data['local_coverage_references']+data['implementation_reviews']:
    r=ref_by_path[c['path']]
    check(f'local coverage hash {c["id"]}',c['sha256']==r['sha256'])
    spans(f'local coverage {c["id"]}',c['reviewed_spans'],r['physical_lines'])
    c['reviewed_span_sha256']=[dict(lines=[a,b],sha256=sha(b''.join((ROOT/r['snapshot']).read_bytes().splitlines(keepends=True)[a-1:b]))) for a,b in c['reviewed_spans']]

# Independent arithmetic checks of literal documentary answers. No proposed source is run.
for g in data['comparison_groups']:
    if 'table_values' in g:
        a,b,expected=g['table_values'];check(f'gcd table answer {g["id"]}',math.gcd(a,b)==expected)
        check(f'gcd all18 subcall forms {g["id"]}',len(g['assertion_subcases'])==18)
        for s in g['assertion_subcases']:check(f'gcd subcall exact text {g["id"]}:{s["line"]}',s['source']==lines[g['path']][s['line']-1].strip())
    if 'original_root_bounds' in g:
        a,b=g['original_root_bounds'];check(f'array independent sum {g["id"]}',sum(range(a,b))==g['expected_sum'])
    if 'case_tuple' in g:
        t1,t2,t3=g['case_tuple'];operand=[1234,-1234,5678][t1];count=[0,5,1025][t2]
        expected=(operand<<count) if t3==0 and count<64 else (operand>>count) if t3==1 else 0
        check(f'shift independent answer {g["id"]}',expected==g['expected_value'])
    if 'exact_expanded_input_table' in g:
        check(f'limit size {g["id"]}',len(g['exact_expanded_input_table'])==27 and g['designed_ordered_pairs']==729)
        if g['disposition']=='adapt_pending':check(f'limit projection representable {g["id"]}',all(-(1<<63)<v<(1<<63) for v in g['exact_expanded_input_table']))

for p in data['proposed_original_regressions']:
    check(f'proposal source IDs {p["id"]}',set(p['source_group_ids'])<=set(group_ids))
    check(f'proposal expected stdout newline {p["id"]}',p['independent_expected_stdout'].endswith('\n'))
    check(f'proposal pending {p["id"]}',p['status']=='original_proposal; unimplemented_uncompiled_unexecuted')
proposal_by_id={p['id']:p for p in data['proposed_original_regressions']}
fixed_pairs=[(0,0),(0,-17),(-17,0),(25,30),(-25,30),(25,-30),(-25,-30),
             (9223372036854775807,9223372036854775806),(9223372036854775806,4611686018427387903),
             (1234,-2147483648),(-2147483648,1234)]
check('P1 mathematical literal answers',proposal_by_id['P1']['independent_expected_stdout']=='\n'.join(str(math.gcd(a,b)) for a,b in fixed_pairs)+'\n')
fixed_extrema=[(0,0),(0,1),(1,0),(-(1<<63),(1<<63)-1),((1<<63)-1,-(1<<63))]
check('P2 mathematical literal answers',proposal_by_id['P2']['independent_expected_stdout']=='\n'.join(str(v) for a,b in fixed_extrema for v in [min(a,b),max(a,b),100,200])+'\n')
check('at most3 original proposals',len(data['proposed_original_regressions'])<=3)
check('prior selected groups derive552',sum(p['groups'] for p in data['prior_selection'])==552)
paths={p for r in data['prior_selection'] for p in r['selected_paths']}
check('prior selected distinct complete files26',len(paths)==26)
check('selection no prior overlap',not paths&set(selected))
central=load(ROOT/ref_by_path['research/2026-10-memory/peers-review-ledger.json']['snapshot'])
check('selection no central overlap',not set(selected)&{r['path'] for r in central['reviewed_source_entries']})
check('selected union646/30',data['selected_report_union']['resulting_groups']==552+len(group_ids) and data['selected_report_union']['resulting_deduplicated_complete_files']==26+len(selected))
handoff=data['handoff']
check('pending ID handoff',set(handoff['pending_group_ids'])=={g['id'] for g in data['comparison_groups'] if g['disposition'].endswith('_pending')})
check('incompatible ID handoff',set(handoff['incompatible_group_ids'])=={g['id'] for g in data['comparison_groups'] if g['disposition']=='incompatible_as_written'})

prior_checks=[]
for saved in data['prior_runtime_evidence']:
    p=ROOT/saved['snapshot'];d=load(p)
    check(f'saved runtime hash {saved["run"]}',sha(p.read_bytes())==saved['sha256'])
    check(f'saved runtime summary {saved["run"]}',d['summary']==saved['saved_summary'])
    flags=collections.Counter()
    def scan(x):
        if isinstance(x,dict):
            for key,value in x.items():
                if key in ('argv','command') and isinstance(value,list) and value and any(isinstance(v,str) and v.endswith('.ll') for v in value):
                    opts=[v for v in value if isinstance(v,str) and re.fullmatch(r'-O(?:0|1|2|3|s|z|g|fast)',v)]
                    if opts:flags[opts[-1]]+=1
                else:scan(value)
        elif isinstance(x,list):
            for value in x:scan(value)
    scan(d)
    check(f'saved actual final optimization flags {saved["run"]}',dict(flags)==saved['actual_saved_last_link_optimization_flags'])
    prior_checks.append(dict(run=saved['run'],saved_summary=d['summary'],saved_flag_counts=saved['actual_saved_last_link_optimization_flags'],
                             locally_found_generated_link_flag_counts=dict(flags),status='documentary_only_no_new_run'))

md=MD.read_text()
for id in group_ids:check(f'markdown group {id}',len(re.findall(r'^### '+re.escape(id)+r' —',md,re.M))==1)
for target in re.findall(r'\]\((\.\./[^)]+)\)',md):
    resolved=(MD.parent/target.split('#')[0]).resolve()
    # Two documentary outputs are generated after this pass.
    check(f'markdown evidence target {target}',resolved.exists() or resolved in [BASE/'document-checks.json',BASE/'evidence-index.json'])
check('prohibited action counters remain zero',all(data['counts'][k]==0 for k in ['ports_implemented','peer_or_local_test_executions','compilations','installations','production_test_build_edits','central_manifest_edits','timing_measurements','commits','subagents']))
failed=[c for c in checks if not c['passed']]
result=dict(status='passed' if not failed else 'failed',check_count=len(checks),failed_count=len(failed),
            scope='Documentary hash/span/count/attribution/literal-arithmetic checks only. No peer/local/proposed program execution, compilation or timing.',
            checks=checks,concurrent_reference_changes=drift,prior_runtime_document_checks=prior_checks)
data['document_checks']=dict(path='evidence/peer-readonly/values-round9/document-checks.json',status=result['status'],check_count=len(checks),failed_count=len(failed),
                            initial_check_path='evidence/peer-readonly/values-round9/document-checks-initial.json',
                            corrections=['Included gcd Cases L31–42 in full physical-line accounting; each row already had a semantic group.',
                                         'Corrected local text-and-lists fixture extent to its actual12 physical lines.'])
data['concurrent_reference_changes']=drift
JSON.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
(BASE/'document-checks.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
marker='\nDocumentary final result: '
if marker in md:md=md.split(marker)[0].rstrip()+'\n'
md+='\nDocumentary final result: **'+str(len(checks))+' consistent checks**, '+str(len(failed))+' failed. '
md+='The retained [initial check](../../evidence/peer-readonly/values-round9/document-checks-initial.json) exposed two documentary extent/accounting errors, corrected above; no executable regression failure is inferred. '
if drift:
    md+='Concurrent live reference changes are recorded without rebinding frozen coverage:\n\n'
    for d in drift:md+='- '+d['path']+': frozen `'+d['frozen_sha256']+'`, observed `'+d['observed_sha256']+'`.\n'
MD.write_text(md)
print(json.dumps(dict(status=result['status'],check_count=len(checks),failed=failed,concurrent_reference_changes=drift,prior_runtime_document_checks=prior_checks),indent=2))
if failed:raise SystemExit(1)
