from pathlib import Path
import datetime, hashlib, json, sys
ROOT=Path.cwd(); OUT=ROOT/'evidence/peer-provenance-integration'; R=ROOT/'research/2026-10-memory'
d=json.loads((R/'peer-evidence-reconciliation.json').read_text());l=json.loads((R/'peers-review-ledger.json').read_text());checks=[]
def check(kind, identity, passed, detail): checks.append({'kind':kind,'identity':identity,'passed':bool(passed),'detail':detail})
def ptr(d,p):
 for t in p.lstrip('/').split('/'): d=d[int(t)] if isinstance(d,list) else d[t.replace('~1','/').replace('~0','~')]
 return d
repositories={s['language']:s['repository'] for s in d['sources']}
byid={s['id']:s for s in d['sources']}; stale={}
for o in d['central_pending_overlay']:
 for e in o['stale_pending_labels']:stale.setdefault(e['source_id'],[]).append(e['record']['json_pointer'])
for identity,pointers in sorted(stale.items()):
 rows=[ptr(l,p) for p in pointers]
 check('later_read_reflected_in_current_central_rows',identity,all(r['status']=='authored_review_record_available_with_explicit_extent' and r.get('current_source_review',{}).get('record')=='research/2026-10-memory/peer-provenance-integration.json' for r in rows),{'pointers':pointers,'statuses':[r['status'] for r in rows],'proven_review_extents':byid[identity]['review_extents']})
v=json.loads((R/'peer-swift-statement-directory.json').read_text())['validation']; md=(R/'peer-swift-statement-directory.md').read_text()
check('swift_statement_script_matches_manifest',v['test_script'],('python3 '+v['test_script']) in md and 'Run adaptations with `python3 tests/peer-research-semantics.py`' not in md,{'drafted_tests':v['drafted_tests'],'status':v['status']})
for field in ['original_inventory_paths','combined_bounded_inventory_paths']:
 from collections import Counter
 actual=dict(Counter(r['status'] for r in l[field]));check('central_counts_from_actual_rows',field,actual==l[field+'_by_status'],{'derived':actual,'recorded':l[field+'_by_status']})
record={'schema':'minyar.peer_provenance_integration.documentary_check.v1','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'JSON/status/reference/count inspection only; no test, compiler, native or model execution and no semantic correctness oracle.','checks':checks,'passed':sum(c['passed'] for c in checks),'failed':sum(not c['passed'] for c in checks),'unique_later_reviewed_paths':len(stale)}
out=OUT/(sys.argv[1] if len(sys.argv)>1 else 'documentary-current.json');assert not out.exists();out.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:v for k,v in record.items() if k!='checks'}));sys.exit(bool(record['failed']))
