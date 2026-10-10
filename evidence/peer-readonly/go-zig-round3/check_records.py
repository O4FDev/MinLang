"""Research-record integrity checks only; does not execute any test/compiler program."""
import json,re,hashlib,datetime,collections
from pathlib import Path
root=Path.cwd();e=root/'evidence/peer-readonly/go-zig-round3';r=root/'research/2026-10-memory';j=json.loads((r/'peer-readonly-go-zig-round3.json').read_text());sources=json.loads((e/'sources.json').read_text());ss={s['path']:s for s in sources}
def end(ls,start):
 d=0
 for i in range(start-1,len(ls)):
  d+=ls[i].count('{')-ls[i].count('}')
  if not d:return i+1
 raise ValueError(start)
checks=[]
for s in sources:
 b=(root/s['evidence_path']).read_bytes();assert hashlib.sha256(b).hexdigest()==s['sha256'];assert len(b.splitlines())==s['lines'];assert len(b)==s['bytes']
checks.append('Every retained immutable source/license byte hash, size and physical line count matches sources.json.')
z=(e/'array.zig.txt').read_text().splitlines();zu=[u for u in j['units'] if u['language']=='zig'];starts=[i for i,l in enumerate(z,1) if i>=310 and l.startswith('test "')]
assert starts==[u['lines'][0] for u in zu]
prior=json.loads((r/'peer-readonly-go-zig-round2.json').read_text());p=json.loads((root/'evidence/peer-readonly/go-zig-round2/provenance.json').read_text());old=next(s for s in p['selected_sources_and_licenses'] if s['path']=='test/behavior/array.zig');assert old['sha256']==ss['test/behavior/array.zig']['sha256'];assert old['semantic_review_sha256']==hashlib.sha256(b''.join((e/'array.zig.txt').read_bytes().splitlines(keepends=True)[:309])).hexdigest()
checks.append('All remaining named Zig tests correspond one-to-one to authored groups. Round2 prefix and round3 remainder join without source-hash mismatch or duplicate group credit.')
assertions=[]
for u in zu:
 assert u['lines'][1]==end(z,u['lines'][0])
 spans=[u['lines']]+[h['lines'] for h in u['helpers_read']]
 actual={i for a,b in spans for i in range(a,b+1) if re.search(r'\b(?:expect(?:Equal(?:Slices|Strings|Sentinel)?)?|assert)\(',z[i-1])}
 authored={i for a in u['upstream_expectations'] for i in a['lines']}
 assert actual<=authored,(u['id'],actual-authored)
 for h in u['helpers_read']:assert h['lines'][1]==end(z,h['lines'][0]),h
 assertions.extend((u['id'],i) for i in sorted(actual))
 assert u['backend_skip_guards_read']==re.findall(r'builtin.zig_backend == \.(\w+)','\n'.join(z[u['lines'][0]-1:u['lines'][1]]))
checks.append('Every Zig assertion call site in each selected body/cross-referenced helper has an authored expectation; all helper endings and backend skip guards match raw physical lines.')
for h in j['imported_oracle_helpers_read']:
 ls=(root/ss[h['path']]['evidence_path']).read_text().splitlines();assert h['lines'][1]==end(ls,h['lines'][0]),h
checks.append('Selected imported oracle helper bodies have exact complete function spans; other support-file tests remain unreviewed/uncounted.')
for file,match in [('test/assign.go','// ERROR'),('test/if.go','assertequal(count')]:
 ls=(root/ss[file]['evidence_path']).read_text().splitlines();sites={i for i,l in enumerate(ls,1) if match in l};auth={i for u in j['units'] if u['path']==file for ex in u['upstream_expectations'] for i in ex['lines']};assert sites<=auth
checks.append('Every Go error annotation and if.go assertion call is recorded; every lexical assignment block has its own grouped record.')
for u in j['units']:
 ls=(root/ss[u['path']]['evidence_path']).read_text().splitlines()
 for ex in u['upstream_expectations']:assert all(1<=line<=len(ls) for line in ex['lines'])
 assert all(i in j['local_coverage_references'] for i in u['local_coverage_ids'])
 assert all(i in [p['id'] for p in j['proposed_regressions']] for i in u['proposed_regressions'])
 assert u['grouped_scope'] and u['port_status']=='not_implemented; not_executed'
for c in j['local_coverage_references'].values():assert 1<=c['lines'][0]<=c['lines'][1]<=len((root/c['path']).read_bytes().splitlines())
assert len(j['units'])==len({u['id'] for u in j['units']})==j['counts']['authored_comparison_groups'];assert dict(collections.Counter(u['disposition'] for u in j['units']))==j['counts']['dispositions']
checks.append('All IDs, expectations/local ranges, proposal references and derived group/disposition counts are consistent.')
summary=dict(checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),meaning='Research record integrity only; no compiler, test or peer program executed',checks=checks,derived_counts=j['counts'],zig_assertion_call_sites=len(assertions),zig_assertion_sites=[dict(unit=u,line=i) for u,i in assertions],go_error_annotation_sites=sum('// ERROR' in l for l in (e/'assign.go.txt').read_text().splitlines()),go_if_assertion_sites=sum('assertequal(count' in l for l in (e/'if.go.txt').read_text().splitlines()),zig_helper_bodies_attached=sum(len(u['helpers_read']) for u in zu),zig_complete_named_tests_across_rounds=len(zu)+sum(u['language']=='zig' for u in prior['units']),prohibited_actions_executed=[])
(e/'document-checks.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k not in ['zig_assertion_sites','checks']},indent=2))
