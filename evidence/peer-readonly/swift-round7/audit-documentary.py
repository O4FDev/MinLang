"""Independent byte/span/ledger arithmetic audit. Does not execute language or test code."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[3]
E=ROOT/'evidence/peer-readonly/swift-round7'
R=ROOT/'research/2026-10-memory'
d=json.loads((R/'peer-readonly-swift-round7.json').read_text())
checks=[]
def check(name, observed, expected):
    checks.append(dict(name=name,observed=observed,expected=expected,consistent=observed==expected))
def line_count(raw):
    return raw.count(b'\n')+int(bool(raw) and not raw.endswith(b'\n'))

sources=json.loads((E/'source-manifest.json').read_text())
local=json.loads((E/'local-manifest.json').read_text())
refs=json.loads((E/'reference-manifest.json').read_text())
candidate=json.loads((E/'candidate-retrieval.json').read_text())
latest_refs=json.loads((E/'latest-runtime-manifest.json').read_text())
hash_records={r['snapshot']:r for r in sources['selected']+sources['support']+[sources['license']]+local+refs+candidate+latest_refs if 'snapshot' in r}
for snapshot,r in hash_records.items():
    raw=(ROOT/snapshot).read_bytes()
    check('SHA256 '+snapshot,hashlib.sha256(raw).hexdigest(),r['sha256'])
    check('bytes '+snapshot,len(raw),r['bytes'])
    check('raw physical lines '+snapshot,line_count(raw),r['physical_lines'])

file_units={f['path']:[u for u in d['comparison_groups'] if u['path']==f['path']] for f in sources['selected']}
actual_sites=[]
actual_registered=[]
physical_lines=0
raw_bytes=0
for f in sources['selected']:
    raw=(ROOT/f['snapshot']).read_bytes();text=raw.decode();lines=text.splitlines()
    physical_lines+=line_count(raw);raw_bytes+=len(raw)
    check('complete selected extent '+f['path'],f['reviewed_spans'],[[1,line_count(raw)]])
    check('no selected unread extent '+f['path'],f['review_pending_spans'],[])
    check('pinned raw URL '+f['path'],f['raw_url'],f"https://raw.githubusercontent.com/swiftlang/swift/{f['commit']}/{f['path']}")
    check('RUN source requirement '+f['path'],lines[0], '// RUN: %target-run-simple-swift'+('' if f['path'].endswith('/structs.swift') else ' | %FileCheck %s'))
    check('executable source requirement '+f['path'],lines[1],'// REQUIRES: executable_test')
    discovered=[dict(path=f['path'],line=n,source=line,kind='expectEqual' if re.search(r'\bexpectEqual\(',line) else 'FileCheck_CHECK') for n,line in enumerate(lines,1) if re.search(r'\bexpectEqual\(',line) or re.search(r'//\s*CHECK:',line)]
    recorded=[dict(path=f['path'],**site) for u in file_units[f['path']] for site in u['source_assertion_sites']]
    key=lambda s:(s['path'],s['line'],s['source'],s['kind'])
    check('all oracle source sites exactly once '+f['path'],sorted(discovered,key=key),sorted(recorded,key=key))
    actual_sites.extend(discovered)
    actual_registered.extend(re.findall(r'^StructTestSuite\.test\("([^"\n]+)"\)',text,re.M))
    check('file backend/XFAIL guards '+f['path'],re.findall(r'^//\s*(?:UNSUPPORTED|XFAIL):.*$',text,re.M),[])
    for u in file_units[f['path']]:
        check('unit bounded source extent '+u['id'],1<=u['lines'][0]<=u['lines'][1]<=len(lines),True)
        for i,span in enumerate(u['in_file_helper_spans']):
            check('helper bounded source extent '+u['id']+f'#{i}',1<=span[0]<=span[1]<=len(lines),True)
        for s in u['source_assertion_sites']:
            check('exact raw assertion source '+u['id']+f" L{s['line']}",lines[s['line']-1],s['source'])

for s in sources['support']:
    if 'snapshot' not in s:continue
    n=s['physical_lines'];read=s['reviewed_spans'];pending=s['review_pending_spans']
    read_lines=[i for a,b in read for i in range(a,b+1)]
    all_lines=read_lines+[i for a,b in pending for i in range(a,b+1)]
    check('support read+pending exact partition '+s['path'],sorted(all_lines),list(range(1,n+1)))
for key,c in d['local_coverage_references'].items():
    for a,b in c['lines']:check(f'local bounded span {key} L{a}–{b}',1<=a<=b<=c['physical_lines'],True)
for rec in d['implementation_reviews']:
    for a,b in rec['reviewed_spans']:check(f'implementation bounded span {rec["path"]} L{a}–{b}',1<=a<=b<=rec['physical_lines'],True)

observed=Counter(u['disposition'] for u in d['comparison_groups']);observed['already_covered']=0
check('independent unit disposition totals',dict(observed),d['counts']['group_dispositions'])
check('unique unit IDs',len(set(u['id'] for u in d['comparison_groups'])),len(d['comparison_groups']))
check('independent comparison groups',len(d['comparison_groups']),d['counts']['authored_comparison_groups'])
check('independent selected physical lines',physical_lines,d['counts']['selected_raw_physical_lines'])
check('selected files',len(sources['selected']),5)
check('expectEqual sites',sum(s['kind']=='expectEqual' for s in actual_sites),36)
check('CHECK sites',sum(s['kind']=='FileCheck_CHECK' for s in actual_sites),35)
check('Struct registered names',actual_registered,['Interval','Big','Generic','InitStruct','InitStructAddrOnly'])

peer=json.loads((R/'peers.json').read_text())
swift=next(p for p in peer['peers'] if p['language']=='swift')
for f in sources['selected']:check('peer commit '+f['path'],f['commit'],swift['commit'])
check('license matches peer pin',sources['license']['sha256'],swift['license_sha256'])
central=json.loads((R/'peers-review-ledger.json').read_text())
prior_swift={x['path'] for x in central['reviewed_source_entries'] if x['language']=='swift'}
prior_units=0;prior_paths=set();prior_by_round=[]
for roundname in ['go-zig-round2','go-zig-round3','strings-round4','values-round5','evaluation-round6']:
    old=json.loads((R/f'peer-readonly-{roundname}.json').read_text())
    units=old.get('units',old.get('comparison_groups',[]))
    prior_units+=len(units);prior_by_round.append(dict(round=roundname,groups=len(units)))
    for u in units:
        language=u['language'];commit=u.get('commit') or u.get('source_commit') or next(p['commit'] for p in peer['peers'] if p['language']==language)
        prior_paths.add((language,commit,u['path']))
        if language=='swift':prior_swift.add(u['path'])
check('prior groups independently derived',prior_units,450)
check('prior complete selected paths independently deduplicated',len(prior_paths),17)
statement=json.loads((R/'peer-swift-statement-directory.json').read_text())
stmtfiles=statement['peers'][0]['files']
check('statement complete exclusion count',len(stmtfiles),25)
check('statement paths in exclusion set',sorted(set(f['path'] for f in stmtfiles)-prior_swift),[])
newpaths={(f['language'] if 'language' in f else 'swift',f['commit'],f['path']) for f in sources['selected']}
check('selected prior report overlap',sorted(newpaths&prior_paths),[])
check('selected prior Swift central/round5 overlap',sorted(set(f['path'] for f in sources['selected'])&prior_swift),[])
check('prior+round7 report groups',prior_units+len(d['comparison_groups']),488)
check('prior+round7 report distinct paths',len(prior_paths|newpaths),22)

# Documentary scalar/dictionary derivation of P1, independently of serializer's expected list.
letters=list('abcdefgh')
fields={letter:index*11 for index,letter in enumerate(letters,1)}
trace=0
for digit in range(8,0,-1):trace=trace*10+digit
snapshot=fields['a'];retained=fields;retained['a']=111
peer_vector=[]
struct=(ROOT/next(f['snapshot'] for f in sources['selected'] if f['path'].endswith('/structs.swift'))).read_text()
found=re.findall(r'expectEqual\((-?\d+), bs\.([a-h])\)',struct)
check('Big exact field names', [field for _,field in found],letters)
peer_vector=[int(value) for value,_ in found]
check('Big independent pinned field expectations',peer_vector,[1,6,1,8,0,3,4,0])
output=peer_vector+[index*11 for index in range(1,9)]+[trace,retained['a'],snapshot]+[peer_vector[-1] for _ in range(8)]+[retained[k] for k in letters]
expected=''.join(str(v)+'\n' for v in output)
check('P1 independently derived stdout',expected,d['proposed_original_regressions'][0]['independent_expected_stdout'])
check('P1 output lines',len(output),35)
check('P1 trace',trace,87654321)
check('constructor unselected markers',re.findall(r'// CHECK: ([a-z])\b',(E/'upstream/swift/test/Interpreter/constructor.swift').read_text()),list('abcdefghijk'))

# Read existing saved runtime evidence; never run its code or commands.
runtime=json.loads((R/'evidence/runtime-peer-projections/run-7m86apqr/results.json').read_text())
check('external recorded runtime status',runtime['status'],'passed')
links=[];executions=[]
for cohort in runtime['coverage']:
    check('external cohort recorded successful '+cohort['configuration'],cohort['successful'],True)
    for method in cohort['observed']:
        for cmd in method['commands']:
            if cmd['kind']=='link':
                flags=[a for a in cmd['argv'] if re.fullmatch(r'-O(?:[0123szg]|fast)',a)]
                check('saved actual effective flag '+cohort['configuration']+' '+method['test']+' '+flags[-1],cmd['effective_last_optimization_flag'],flags[-1])
                links.append(flags[-1])
            if cmd['kind']=='execute':executions.append(cmd['returncode'])
check('external saved links',dict(Counter(links)),{'-O0':18,'-O2':18})
check('external saved execution statuses',executions,[0]*36)
check('external six distinct methods',len(set(m['test'] for c in runtime['coverage'] for m in c['observed'])),6)

latest_snapshot=next(r['snapshot'] for r in latest_refs if r['path'].endswith('/run-l5_218bk/results.json'))
latest=json.loads((ROOT/latest_snapshot).read_text())
check('latest external recorded status',latest['status'],'passed')
check('latest external summary',latest['summary'],dict(test_methods=8,configurations=3,generated_executions=48))
latest_links=[];latest_exec=[];latest_methods=set();latest_sanitized=0
for cohort in latest['coverage']:
    check('latest external cohort successful '+cohort['configuration'],cohort['successful'],True)
    for method in cohort['observed']:
        latest_methods.add(method['test'].split('.')[-1])
        if 'sanitize' in cohort['configuration']:
            check('latest generated ASan definitions '+method['test'],method['asan_definitions'],method['generated_definitions'])
            latest_sanitized+=method['asan_definitions']
        for cmd in method['commands']:
            if cmd['kind']=='link':
                flags=[a for a in cmd['argv'] if re.fullmatch(r'-O(?:[0123szg]|fast)',a)]
                check('latest actual link flag '+cohort['configuration']+' '+method['test']+' '+flags[-1],cmd['effective_last_optimization_flag'],flags[-1])
                latest_links.append(flags[-1])
            if cmd['kind']=='execute':
                latest_exec.append(cmd['returncode'])
                check('latest saved stdout hash '+cohort['configuration']+' '+method['test']+' #'+str(len(latest_exec)),cmd['stdout_sha256'],hashlib.sha256(method['expected_stdout'].encode()).hexdigest())
check('latest saved O0/O2 links',dict(Counter(latest_links)),{'-O0':24,'-O2':24})
check('latest recorded statuses',latest_exec,[0]*48)
check('latest distinct methods',len(latest_methods),8)
check('latest newly implemented round6 originals',sorted(set(d['latest_runtime_update']['new_methods'])-latest_methods),[])
check('latest ASan definition total',latest_sanitized,120)
latest_provenance=json.loads((ROOT/next(r['snapshot'] for r in latest_refs if r['path'].endswith('/run-l5_218bk/provenance.json'))).read_text())
check('latest new method provenance',sorted(e['original_test'] for e in latest_provenance['source_to_test'] if e['read_only_record'].endswith('peer-readonly-evaluation-round6.json')),sorted(d['latest_runtime_update']['new_methods']))
for rec in latest_refs:
    if rec['path'].endswith('/tests/memory-research-peer-projections.py'):
        check('latest archive/current fixture hash '+rec['path'],rec['sha256'],d['local_coverage_references']['runtime-originals']['sha256'])

concurrent=[]
for r in refs+local:
    now=hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()
    if now!=r['sha256']:concurrent.append(dict(path=r['path'],snapshot_sha256=r['sha256'],observed_current_sha256=now,meaning='Concurrent change, not authored here; documentary mappings bind to frozen snapshot.'))
central_records=[r for r in refs if r['path'] in ['research/2026-10-memory/peers.json','research/2026-10-memory/peers-review-ledger.json']]
for r in central_records:check('central ledger unchanged '+r['path'],hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest(),r['sha256'])

summary=dict(consistent=all(c['consistent'] for c in checks),documentary_predicate_count=len(checks),
             distinct_retained_hash_records=len(hash_records),selected_files=5,selected_bytes=raw_bytes,selected_physical_lines=physical_lines,
             unit_groups=len(d['comparison_groups']),group_dispositions=dict(observed),expectEqual_source_sites=36,CHECK_source_sites=35,
             helper_lifecycle_source_sites=1,helper_lifecycle_attachments=5,
             prior_rounds=prior_by_round,prior_groups=prior_units,prior_deduplicated_paths=len(prior_paths),
             combined_groups=prior_units+len(d['comparison_groups']),combined_deduplicated_paths=len(prior_paths|newpaths),
             initial_runtime_record_read_here_executions=36,latest_runtime_record_read_here_executions=48,round7_test_executions=0,
             limits='Documentary byte/span/count/proposal-arithmetic checks only; not source execution, test passes, mutation proof, timing or peer feature parity.')
report=dict(schema='minyar.peer_readonly_swift_round7.document_checks.v1',summary=summary,checks=checks,concurrent_reference_changes=concurrent)
(E/'document-checks.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
handoff=dict(schema='minyar.peer_readonly_swift_round7.handoff.v1',status='bounded_selected_source_review_complete' if summary['consistent'] else 'documentary_audit_requires_correction',
             counts=d['counts'],independently_derived_documentary_totals=summary,selected=d['scope']['selected'],
             selected_remaining_review_spans=[],pending_units=[u['id'] for u in d['comparison_groups'] if u['disposition'] in ['adopt_pending','adapt_pending']],
             incompatible_units=[u['id'] for u in d['comparison_groups'] if u['disposition']=='incompatible_as_written'],
             original_proposals=['P1'],concurrent_reference_changes=concurrent,
             remaining_unselected_scope='Other Interpreter files/peers; unselected constructor screening gets no unit credit; exact support complements in source-manifest.json. No directory/repository exhaustion claim.',
             shared_lifetime_contract='One H1 source site attached to all5 named Struct tests; nonvacuous tracked objects only in InitStruct/InitStructAddrOnly. Swift ARC endpoint remains incompatible.',
             prior_proposal_deduplication=d['prior_runtime_evidence'],latest_runtime_update=d['latest_runtime_update'],availability=d['availability'],
             owned_write_boundary=d['handoff']['owned_write_boundary'],central_ledgers_untouched=True,
             existing_dirty_work_preserved=True,active_core_native_work_disturbed=False,
             prohibited_actions_executed=[],campaign_earliest_completion_utc='2026-10-04T06:54:29Z',campaign_completion_claim=False)
(E/'handoff.json').write_text(json.dumps(handoff,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(summary,indent=2))
for c in checks:
    if not c['consistent']:print('INCONSISTENT',c['name'],str(c['observed'])[:350],str(c['expected'])[:350])
