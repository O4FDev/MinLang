from pathlib import Path
from collections import Counter, defaultdict
import datetime, difflib, hashlib, json, re, subprocess
ROOT=Path.cwd(); OUT=ROOT/'evidence/peer-provenance-integration'; R='research/2026-10-memory/'; REPORT=R+'peer-provenance-integration.json';output=OUT/'integrity-checks.json';checks=[]
def sha(b):return hashlib.sha256(b).hexdigest()
def load(p):return json.loads((ROOT/p).read_text())
def check(kind,identity,passed,detail=None):checks.append({'kind':kind,'identity':identity,'passed':bool(passed),'detail':detail})
def ptr(d,p):
 if not p:return d
 for t in p.lstrip('/').split('/'):
  t=t.replace('~1','/').replace('~0','~');d=d[int(t)] if isinstance(d,list) else d[t]
 return d
before=load('evidence/peer-provenance-integration/before-manifest.json');captured={f['path']:f for f in before['files'] if f['path']};d=load(REPORT);recon=load(R+'peer-evidence-reconciliation.json');ledger=load(R+'peers-review-ledger.json');legacy=load(captured[R+'peers-review-ledger.json']['before_path'])
# Own diff is against captured dirty working bytes, not HEAD.
allowed={R+n for n in ['peers.json','peers.md','peers-review-ledger.json','peers-inventory.json','peer-swift-statement-directory.md']};changed=[];patch=[];after=[]
for path in sorted(captured):
 b=(ROOT/captured[path]['before_path']).read_bytes();a=(ROOT/path).read_bytes()
 check('preserved_before_hash',path,sha(b)==captured[path]['sha256'])
 if b!=a:
  if path==R+'README.md':
   after.append({'path':path,'before_sha256':sha(b),'current_sha256':sha(a),'ownership':'root/core concurrent file; not touched by this round'});continue
  changed.append(path);patch.extend(difflib.unified_diff(b.decode().splitlines(keepends=True),a.decode().splitlines(keepends=True),fromfile='a/'+path,tofile='b/'+path))
  after.append({'path':path,'before_sha256':sha(b),'after_sha256':sha(a),'before_bytes':len(b),'after_bytes':len(a)})
check('minimal_maintained_file_set','files',set(changed)==allowed,changed)
(OUT/'own-maintained.patch').write_text(''.join(patch));(OUT/'after-maintained-manifest.json').write_text(json.dumps({'captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'changed_maintained_files':after,'own_patch':'evidence/peer-provenance-integration/own-maintained.patch','patch_sha256':sha((OUT/'own-maintained.patch').read_bytes()),'new_deliverables':[REPORT,R+'peer-provenance-integration.md'],'concurrent_work_policy':'Only own five maintained-file edits appear in this patch. Other work remains untouched; campaign README is owned by root/core.'},indent=2)+'\n')
for g in before['frozen_guards']:
 p=ROOT/g['path'];check('frozen_evidence_hash',g['path'],p.is_file() and sha(p.read_bytes())==g['sha256'])
check('historical_legacy_ledger_fields','four_manifest_cohort',all(ledger[k]==v for k,v in legacy.items() if k not in ['original_inventory_paths','combined_bounded_inventory_paths','original_inventory_paths_by_status','combined_bounded_inventory_paths_by_status']))
repo_by_language={s['language']:s['repository'] for s in recon['sources']}
def key(r):return repo_by_language[r['language']]+'|'+r['commit']+'|'+r['path']
source_by_id={s['id']:s for s in recon['sources']};selected_sources={g['source_id'] for g in recon['round2_through9_groups']}
check('immutable_pinned_keys','all_sources',len(source_by_id)==len(recon['sources']) and all(s['id']==s['repository']+'|'+s['commit']+'|'+s['path'] for s in recon['sources']))
expected_ids={key(row) for row in legacy['original_inventory_paths'] if row['status']=='not_semantically_reviewed_in_campaign_manifests' and key(row) in selected_sources}
updates={u['source_id']:u for u in d['source_review_updates']};check('exact_selected_later_paths','24keys',len(updates)==len(d['source_review_updates']) and set(updates)==expected_ids and len(expected_ids)==24)
for field in ['original_inventory_paths','combined_bounded_inventory_paths']:
 old=legacy[field];new=ledger[field];check('bounded_key_order_and_dedup',field,len(new)==len(old) and [key(x) for x in old]==[key(x) for x in new] and len({key(x) for x in new})==len(new))
 for i,(a,b) in enumerate(zip(old,new)):
  identity=key(a)
  if identity in expected_ids:
   permitted={'status','review_references','current_source_review'}
   check('exact_changed_row_fields',field+'/'+str(i),{k:v for k,v in a.items() if k not in permitted}=={k:v for k,v in b.items() if k not in permitted})
   link=b.get('current_source_review',{});target=ptr(d,link.get('json_pointer',''))
   check('row_source_extent_link',field+'/'+str(i),b['status']=='authored_review_record_available_with_explicit_extent' and link.get('record')==REPORT and target['source_id']==identity and target['sha256']==source_by_id[identity]['sha256'] and target['review_extents']==source_by_id[identity]['review_extents'] and target['whole_selected_file_reviewed'] is True and target['execution_credit_from_status_update']==0 and target['upstream_group_port_credit']==0)
  else:check('untargeted_row_unchanged',field+'/'+str(i),a==b)
 counts=dict(Counter(x['status'] for x in new));check('row_derived_status_counts',field,counts==ledger[field+'_by_status']==d['counts']['central_bounded'][field]['statuses'] and len(new)==d['counts']['central_bounded'][field]['entries'])
# Manifest snapshots with narrower discovery/validation semantics keep their original fields.
for path,additions in [(R+'peers-inventory.json',{'current_source_review_overlay'}),(R+'peers.json',{'cross_references'})]:
 old=load(captured[path]['before_path']);new=load(path);check('historical_manifest_fields',path,all(new[k]==v for k,v in old.items() if k not in additions))
 if 'cross_references' in additions:check('existing_crossrefs_unchanged',path,new['cross_references'][:-1]==old['cross_references'] and new['cross_references'][-1]['manifest']=='peer-provenance-integration.json')
# Raw-byte verification is independent of earlier boolean availability assertions.
raw_byid={r['source_id']:r for r in d['raw_source_verification']};check('raw_source_key_coverage','197keys',set(raw_byid)==set(source_by_id) and len(raw_byid)==len(d['raw_source_verification']))
verified=set()
for identity,r in raw_byid.items():
 a=r['verified_raw'];p=ROOT/a['path'] if a else None;good=p is not None and p.is_file() and sha(p.read_bytes())==source_by_id[identity]['sha256']==r['expected_sha256']==a['sha256'];check('source_raw_sha256',identity,good)
 if good:verified.add(identity)
newraw=d['new_raw_archival']['sources'];expected_new={i for i,s in source_by_id.items() if s['repository']=='golang/go' and s['commit']=='56ebf80e57db9f61981fc0636fc6419dc6f68eda' and s['path'] in ['test/for.go','test/simassign.go']};check('exact_two_official_fetches','go',len(newraw)==2 and {r['source_id'] for r in newraw}==expected_new and d['new_raw_archival']['alternate_routes_attempted']==0)
for r in newraw:
 p=ROOT/r['archive_path'];s=source_by_id[r['source_id']];url='https://raw.githubusercontent.com/'+s['repository']+'/'+s['commit']+'/'+s['path'];check('new_archive_provenance',r['source_id'],r['requested_url']==r['final_url']==url and r['http_status']==200 and sha(p.read_bytes())==s['sha256']==r['expected_sha256']==r['actual_sha256']==r['archive_sha256'] and r['bytes']==p.stat().st_size and r['physical_lines']==len(p.read_bytes().splitlines()) and r['retrieved_utc']>r['historical_cutoff_utc'] and r['historical_status']==s['source_byte_status'] and not s['retained_source_bytes'] and r['source_review_credit_added']==r['execution_credit_added']==0 and any(line.startswith('// Copyright') for line in p.read_text().splitlines()[:8]))
li=d['new_raw_archival']['license'];check('full_license_hash','go',sha((ROOT/li['archive_path']).read_bytes())==li['sha256']==li['copied_from_frozen_snapshot']['sha256'] and (ROOT/li['archive_path']).read_bytes()==(ROOT/li['copied_from_frozen_snapshot']['snapshot']).read_bytes() and li['full_notice_retained'] and not li['network_fetch'])
# Independent count derivation uses arrays and selected IDs, never summary prose.
methods=recon['original_minyar_methods']+recon['round9_execution_addendum']['methods'];execs=recon['archived_execution_records']+recon['round9_execution_addendum']['archived_execution_records'];exec_byid={e['id']:e for e in execs};ids={e for m in methods for e in m['execution_ids']};groups=recon['round2_through9_groups'];linked={g for m in methods for g in m['qualified_group_ids']};proposals=[];unit_count=0
for path in {g['record']['path'] for g in groups}:
 x=load(path);units=x.get('units',x.get('comparison_groups'));ps=x.get('proposed_regressions',x.get('proposed_original_regressions'));unit_count+=len(units);proposals+=ps
 current=[g for g in groups if g['record']['path']==path]
 for g in current:
  u=ptr(x,g['record']['json_pointer']);check('authored_group_pointer',g['id'],isinstance(u,dict) and g['authored_unit_id']==u['id'])
 check('round_group_array_count',path,len(units)==len(current))
check('execution_ID_dedup','selected',len(exec_byid)==len(execs) and set(d['selected_saved_execution_ids'])==ids and len(ids)==len(d['selected_saved_execution_ids']))
for m in methods:
 es=[exec_byid[i] for i in m['execution_ids']];check('selected_execution_scope',m['method'],len(es)==6 and all(e['method']==m['method'] and e['run']==m['run'] and e['returncode']==0 and e['stdout_sha256']==e['expected_stdout_sha256'] for e in es) and len({(e['config'],e['effective_last_optimization']) for e in es})==6)
partition=Counter(exec_byid[i]['run'] for i in ids);check('separate_execution_partitions','six_cohorts',sorted(partition.values())==[6,6,6,6,6,48] and {r['run']:r['executions'] for r in d['selected_execution_partition']}==dict(partition))
proposal_methods=defaultdict(set)
for m in methods:proposal_methods[m['ledger']+'#'+m['proposal']].add(m['method'])
for p in d['proposal_execution_overlay']:
 check('proposal_vs_execution_separation',p['id'],set(p['method_ids'])==proposal_methods[p['id']] and p['full_upstream_parity'] is False and p['historical_status']==next(x['frozen_status'] for x in recon['proposal_status_overlay'] if x['id']==p['id']))
bounded={key(row) for row in ledger['combined_bounded_inventory_paths']};outside=selected_sources-bounded;whole={s['id'] for s in recon['sources'] if any(e['whole_file_credit'] for e in s['review_extents']) or s['complete_selected_round_file']}
derived={'round2_through9_groups':unit_count,'distinct_selected_round_files':len(selected_sources),'complete_selected_round_files':sum(source_by_id[i]['complete_selected_round_file'] for i in selected_sources),'combined_pinned_source_entries':len(source_by_id),'whole_read_entries':len(whole),'partial_companion_entries':len(source_by_id)-len(whole),'verified_raw_entries_before':len(verified-expected_new),'verified_raw_entries_current':len(verified),'selected_round_raw_entries_current':len(verified & selected_sources),'unique_corrected_central_paths':len(expected_ids),'corrected_central_rows':sum(key(row) in expected_ids for field in ['original_inventory_paths','combined_bounded_inventory_paths'] for row in legacy[field]),'selected_files_outside_bounded_tables':len(outside),'original_projection_methods':len({m['method'] for m in methods}),'selected_saved_execution_records':len(ids),'source_proposals':len(proposals),'proposals_with_exact_extension_crosslinks':sum(bool(v) for v in proposal_methods.values()),'proposals_without_exact_extension_crosslinks':len(proposals)-sum(bool(v) for v in proposal_methods.values()),'group_inspiration_identities_with_extension_crosslinks':len(linked),'groups_without_these_extension_crosslinks':len(groups)-len(linked),'source_group_dispositions':dict(Counter(g['original_disposition'] for g in groups))}
for k,v in derived.items():check('array_derived_count',k,d['counts'][k]==v,{'derived':v,'recorded':d['counts'][k]})
check('outside_bounded_no_promotion','six',outside=={x['source_id'] for x in d['outside_bounded_selected_sources']} and all(x['bounded_inventory_update_credit']==0 for x in d['outside_bounded_selected_sources']))
for directory in load(R+'peers-expanded-pending-inventory.json')['directories']:
 keys={directory['repository']+'|'+directory['commit']+'|'+e['path'] for e in directory['entries']};check('expanded_directory_no_later_intersection',directory['directory'],not selected_sources & keys)
sw=d['swift_reference_correction'];old=(ROOT/captured[sw['path']]['before_path']).read_text();new=(ROOT/sw['path']).read_text();check('swift_exact_one_line_change',sw['path'],old.count(sw['before_text'])==1 and new==old.replace(sw['before_text'],sw['after_text']) and sw['manifest_validation']==load(R+'peer-swift-statement-directory.json')['validation'] and sw['manifest_validation']['status']=='not_executed_new_statement_ports' and sw['manifest_validation']['drafted_tests']==10 and not sw['execution_performed'])
# Validate every report reference with a SHA and every JSON pointer. Snapshot refs resolve to frozen bytes.
refs=set()
def visit(x):
 if isinstance(x,dict):
  if 'path' in x and 'sha256' in x and isinstance(x['path'],str) and ((ROOT/x['path']).exists() or 'snapshot' in x):
   path=x.get('snapshot',x['path']);p=ROOT/path;ident=(path,x['sha256'],x.get('json_pointer',''))
   if ident not in refs:
    refs.add(ident);good=p.is_file() and sha(p.read_bytes())==x['sha256'];detail=None
    if good and x.get('json_pointer'):
     try:ptr(json.loads(p.read_text()),x['json_pointer'])
     except Exception as e:good=False;detail=str(e)
    check('report_hash_pointer_reference',str(ident),good,detail)
  for v in x.values():visit(v)
 elif isinstance(x,list):
  for v in x:visit(v)
visit(d)
for rel in [R+'peer-provenance-integration.md',R+'peers.md',R+'peer-swift-statement-directory.md']:
 md=ROOT/rel
 for target in re.findall(r'\]\(([^)]+)\)',md.read_text()):
  if not target.startswith(('http:','https:')):
   p=(md.parent/target.split('#')[0]).resolve();check('markdown_file_link',rel+' '+target,p.exists() or p==output)
red=load('evidence/peer-provenance-integration/documentary-red.json');green=load('evidence/peer-provenance-integration/documentary-green.json');check('saved_red_then_green','current_view',red['failed']==25 and red['passed']==2 and green['failed']==0 and green['passed']==27 and red['checked_utc']<d['updated_utc']<green['checked_utc'])
record={'schema':'minyar.peer_provenance_integration.integrity.v1','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Documentary byte/hash/JSON/key/count/link/status checks only; no test/native/compiler/model execution and no semantic implementation oracle.','passed':sum(c['passed'] for c in checks),'failed':sum(not c['passed'] for c in checks),'checks':checks,'derived_counts':derived,'hash_pointer_references':len(refs),'frozen_guard_files':len(before['frozen_guards']),'own_changed_maintained_files':changed}
output.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:v for k,v in record.items() if k not in ['checks','derived_counts']},indent=2))
for c in checks:
 if not c['passed']:print('FAIL',json.dumps(c))
assert not record['failed']
