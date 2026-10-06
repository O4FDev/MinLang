"""Documentary reconciliation only. Reads frozen text; never imports test modules."""
from pathlib import Path
from collections import Counter,defaultdict
import ast,datetime,hashlib,json,re
ROOT=Path.cwd();OUT=ROOT/'evidence/peer-reconciliation';SNAP=OUT/'snapshot';R='research/2026-10-memory/'
def sha(b):return hashlib.sha256(b).hexdigest()
def read(rel):return json.loads((SNAP/rel).read_text())
def walk(x,p=''):
 if isinstance(x,dict):
  yield p,x
  for k,v in x.items():yield from walk(v,p+'/'+k.replace('~','~0').replace('/','~1'))
 elif isinstance(x,list):
  for i,v in enumerate(x):yield from walk(v,p+'/'+str(i))
def ref(rel,p=''):return {'path':rel,'snapshot':str((SNAP/rel).relative_to(ROOT)),'sha256':sha((SNAP/rel).read_bytes()),'json_pointer':p}
manifest=read('evidence/peer-reconciliation/snapshot-manifest.json') if (SNAP/'evidence/peer-reconciliation/snapshot-manifest.json').exists() else json.loads((OUT/'snapshot-manifest.json').read_text())
roundnames=['peer-readonly-go-zig-round2.json','peer-readonly-go-zig-round3.json','peer-readonly-strings-round4.json','peer-readonly-values-round5.json','peer-readonly-evaluation-round6.json','peer-readonly-swift-round7.json','peer-readonly-text-loops-round8.json','peer-readonly-values-round9.json']
oldnames=['peers.json','peer-rust-expression-directory.json','peer-swift-statement-directory.json','peer-nim-koka-lean.json']
pins={p['language']:p for p in read(R+'peers.json')['peers']}
docs={str(p.relative_to(SNAP)):json.loads(p.read_text()) for p in SNAP.rglob('*.json')}
metadata=defaultdict(list)
for rel,d in docs.items():
 for pointer,x in walk(d):
  path=x.get('path');h=x.get('sha256',x.get('source_sha256'));url=x.get('url',x.get('source_url',''))
  if path and h and re.fullmatch('[a-f0-9]{64}',str(h)) and ('github.com/' in url or x.get('commit') in [p['commit'] for p in pins.values()]):
   metadata[path].append((rel,pointer,x))
def language(path):
 if path.startswith(('llvm/','libcxx/')):return 'llvm'
 return {'.go':'go','.zig':'zig','.swift':'swift','.rs':'rust','.nim':'nim','.kk':'koka','.lean':'lean'}.get(Path(path).suffix)
def sourcekey(lang,path,commit=None):return '|'.join([pins[lang]['repository'],commit or pins[lang]['commit'],path])
files={};groups=[];roundcounts=[];legacy=[]
for n in oldnames:
 d=read(R+n);count=0
 for pi,p in enumerate(d['peers']):
  for fi,f in enumerate(p['files']):
   key=sourcekey(p['language'],f['path'],p['commit']);entry=files.setdefault(key,{'id':key,'language':p['language'],'repository':p['repository'],'commit':p['commit'],'path':f['path'],'sha256':f['sha256'],'url':f['url'],'review_extents':[],'groups':[],'legacy_units':[]})
   assert entry['sha256']==f['sha256']
   extent={'record':ref(R+n,f'/peers/{pi}/files/{fi}'),'status':f['status'],'extent':f.get('review_scope',f.get('review_method')),'spans':[[1,f['lines']]] if f['status']=='source_read_and_semantically_reviewed' else None,'physical_lines':f['lines'],'whole_file_credit':f['status']=='source_read_and_semantically_reviewed'}
   entry['review_extents'].append(extent)
   for ui,u in enumerate(f.get('review_units',[])):
    qid=n+'#'+f['path']+'#'+u['id'];entry['legacy_units'].append(qid)
    legacy.append({'id':qid,'source_id':key,'record':ref(R+n,f'/peers/{pi}/files/{fi}/review_units/{ui}'),'authored_unit_id':u['id'],'source_span':u.get('source_line',u.get('lines')),'original_disposition':u.get('disposition'),'existing_contract_and_limits':u.get('reason'),'minyar_test':u.get('minyar_test',u.get('test')),'validation_as_recorded':u.get('validation'),'raw_fields':{k:v for k,v in u.items() if k not in ['id','reason','disposition','minyar_test','validation']}});count+=1
 roundcounts.append({'record':R+n,'source_entries':sum(len(p['files']) for p in d['peers']),'authored_unit_entries':count,'scope':'legacy; never added to round2–9 heterogeneous groups'})
legacykeys=set(files)
# Locate all selected source metadata in each report / its provenance, without counting cached candidates.
for ri,n in enumerate(roundnames,2):
 d=read(R+n);gkey='units' if 'units' in d else 'comparison_groups';us=d[gkey];localfiles=defaultdict(list)
 for i,u in enumerate(us):
  path=u['path'];lang=u.get('language') or language(path);commit=u.get('commit',u.get('source_commit')) or pins[lang]['commit'];key=sourcekey(lang,path,commit)
  metas=[m for m in metadata[path] if m[2].get('commit',m[2].get('source_commit',commit))==commit]
  # Prefer metadata from the selected report, then same-round provenance; supplied hashes must agree.
  metas.sort(key=lambda m:(m[0]!=R+n,'/references/' in m[0], '/latest-runtime/' in m[0],len(m[0])))
  hashes={m[2].get('sha256',m[2].get('source_sha256')) for m in metas};h=u.get('sha256',u.get('source_sha256')) or (metas[0][2].get('sha256',metas[0][2].get('source_sha256')) if metas else None)
  assert h and len(hashes)==1,(n,path,hashes)
  f=files.setdefault(key,{'id':key,'language':lang,'repository':pins[lang]['repository'],'commit':commit,'path':path,'sha256':h,'url':u.get('url',u.get('source_url')),'review_extents':[],'groups':[],'legacy_units':[]});assert f['sha256']==h
  qid=n+'#'+u['id'];f['groups'].append(qid);localfiles[key].append(qid)
  groups.append({'id':qid,'source_id':key,'authored_unit_id':u['id'],'record':ref(R+n,f'/{gkey}/{i}'),'source_spans':u.get('source_spans',[u['lines']] if 'lines' in u else None),'upstream_unit':u.get('name',u.get('upstream_unit')),'original_disposition':u.get('disposition'),'upstream_expected':u.get('upstream_expected',u.get('upstream_expectations')),'compatible_existing_contract':u.get('minyar_mapping',u.get('minyar_compatibility')),'excluded_peer_contracts':u.get('excluded_contracts',u.get('incompatible_or_excluded_contract')),'frozen_local_coverage':u.get('local_source_test_coverage',u.get('local_coverage_references',u.get('local_coverage_ids',u.get('current_local_coverage')))),'original_status':u.get('port_status',u.get('status')),'proposal_ids':u.get('proposal_ids',u.get('proposed_regressions',[u['proposal']] if u.get('proposal') else [])),'original_minyar_methods':[],'current_view':'incompatible_as_written' if 'incompatible' in u.get('disposition','') else 'documentary_only_no_exact_execution_crosslink','full_upstream_parity':False})
 for key in localfiles:
  f=files[key];path=f['path'];lang=f['language'];ms=[m for m in metadata[path] if m[2].get('sha256',m[2].get('source_sha256'))==f['sha256']]
  ms.sort(key=lambda m:(m[0]!=R+n,'/references/' in m[0],len(m[0])))
  phys=next((m[2].get('physical_lines',m[2].get('lines')) for m in ms if isinstance(m[2].get('physical_lines',m[2].get('lines')),int)),None)
  if n==roundnames[0] and lang=='zig':spans=[[1,309]]
  elif n==roundnames[1] and lang=='zig':spans=[[310,1127]]
  else:spans=[[1,phys]]
  f['review_extents'].append({'record':ref(R+n),'status':'selected_semantic_read','spans':spans,'physical_lines':phys,'whole_file_credit':not(n in roundnames[:2] and lang=='zig'),'extent_basis':'reported whole selected file; array prefix/remainder preserved separately'})
 roundcounts.append({'record':R+n,'derived_groups':len(us),'reported_groups':d['counts']['authored_comparison_groups'],'dispositions':dict(Counter(u['disposition'] for u in us)),'source_entries':len(localfiles),'reported_counts':d['counts']});assert len(us)==d['counts']['authored_comparison_groups']
roundkeys={g['source_id'] for g in groups}
# Source evidence: only hash-matched small documentary sources, not native binaries.
late=[]
for key,f in files.items():
 ms=[m for m in metadata[f['path']] if m[2].get('sha256',m[2].get('source_sha256'))==f['sha256']]; f['provenance_records']=[ref(a,b) for a,b,c in ms if '/references/' not in a][:12]
 candidates=[str(ROOT/'build/peer-research/sources'/f['language']/f['path'])]
 for a,b,c in ms:
  for field in ['snapshot','evidence_path','cached_path','cache_path']:
   if isinstance(c.get(field),str):candidates.append(c[field])
 # Original source archives and flat round3/4 evidence have various naming conventions.
 for p in ROOT.joinpath('evidence/peer-readonly').rglob('*'):
  if p.is_file() and (p.name==Path(f['path']).name or p.name==Path(f['path']).name+'.txt' or p.name.endswith('-'+Path(f['path']).name+'.txt')):candidates.append(str(p.relative_to(ROOT)))
 found=[]
 for rel in dict.fromkeys(candidates):
  p=Path(rel);p=p if p.is_absolute() else ROOT/p
  if not p.is_file() or p.stat().st_size>2_000_000:continue
  b=p.read_bytes()
  if sha(b)!=f['sha256']:continue
  if p.is_relative_to(ROOT):r=str(p.relative_to(ROOT));q=SNAP/r
  else:r=str(p);q=OUT/'pinned-sources'/f['sha256']
  if not q.exists():
   q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b);late.append({'path':r,'snapshot':str(q.relative_to(ROOT)),'sha256':sha(b),'captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'binding':'hash-identical immutable source; no post-cutoff status imported'})
  found.append({'path':r,'snapshot':str(q.relative_to(ROOT)),'sha256_matches_pin':True,'physical_lines':len(b.splitlines())})
  break
 f['retained_source_bytes']=found;f['source_byte_status']='hash_verified' if found else 'pinned_hash_and_authored_review_only_no_located_durable_raw_bytes'
 spans=[s for e in f['review_extents'] for s in (e['spans'] or [])];merged=[]
 for lo,hi in sorted(spans):
  if lo is None or hi is None:continue
  if merged and lo<=merged[-1][1]+1:merged[-1][1]=max(merged[-1][1],hi)
  else:merged.append([lo,hi])
 f['combined_reviewed_spans']=merged
 f['complete_selected_round_file']=key in roundkeys and len(merged)==1 and merged[0][0]==1 and merged[0][1]==max(e['physical_lines'] or 0 for e in f['review_extents'])
# Exact matrix executions, source/config/argv hashes and output equality. Never execute a fixture.
artifacts=[];executions=[];method_observations=defaultdict(list);document_errors=[]
for p in sorted((SNAP/R/'evidence/runtime-peer-projections').glob('*/results.json')):
 rel=str(p.relative_to(SNAP));run=p.parent.name;d=json.loads(p.read_text());coverages=[]
 coverage_inputs=[(str(cp.relative_to(SNAP)), '', json.loads(cp.read_text()), cp.name[:-len('-coverage.json')]) for cp in sorted(p.parent.glob('*-coverage.json'))]
 if not coverage_inputs:coverage_inputs=[(rel, f'/coverage/{i}', c, c['configuration']) for i,c in enumerate(d['coverage'])]
 for cr,basepointer,c,config in coverage_inputs:
  coverages.append(ref(cr,basepointer));runtimecheck=next((x for x in d['checks'] if x['label']==config+'-runtime'),None)
  for oi,o in enumerate(c['observed']):
   method=o['test'].split('.')[-1];method_observations[method].append({'run':run,'coverage':ref(cr,basepointer+f'/observed/{oi}'),'source_sha256':sha(o['source'].encode()),'expected_sha256':sha(o['expected_stdout'].encode()),'expected_lines':len(o['expected_stdout'].splitlines()),'generated_definitions':o.get('generated_definitions'),'asan_definitions':o.get('asan_definitions')})
   commands=o.get('commands',[])
   if commands:
    for ci,command in enumerate(commands):
     if command['kind']!='execute':continue
     link=commands[ci-1];flags=[x for x in link['argv'] if re.fullmatch(r'-O(?:[0123szg]|fast)',x)];expected=sha(o['expected_stdout'].encode())
     good=command['returncode']==0 and command['stdout_sha256']==expected
     if not good:document_errors.append({'path':cr,'method':method,'error':'execution hash or status mismatch'})
     executions.append({'id':f'{run}/{config}/{method}/{flags[-1]}','run':run,'method':method,'config':config,'coverage':ref(cr,basepointer+f'/observed/{oi}/commands/{ci}'),'link':ref(cr,basepointer+f'/observed/{oi}/commands/{ci-1}'),'link_argv':link['argv'],'effective_last_optimization':flags[-1],'recorded_effective_flag':link.get('effective_last_optimization_flag'),'execution_argv':command['argv'],'returncode':command['returncode'],'stdout_sha256':command['stdout_sha256'],'expected_stdout_sha256':expected,'output_hash_matches':good,'runtime_compile':runtimecheck,'runtime_optimization':'O1' if 'sanitize' in config else 'O2','runtime_asan_ubsan':'sanitize' in config,'generated_asan_definition_check':{'definitions':o.get('generated_definitions'),'asan_definitions':o.get('asan_definitions')} if 'sanitize' in config else None,'generated_ubsan_claim':False,'lsan_enabled':False if 'sanitize' in config else None})
   else:
    # Historical records did not save argv. Preserve correction without invented commands.
    for req,eff in zip(o.get('linked_optimizations',[]),o.get('effective_optimizations',o.get('linked_optimizations',[]))):
     if 'sanitize' in config and run in ['run-ki_43p1a','run-crettoqb','run-u1gz8lmr','run-klwzmyf0']:eff='O1'
     executions.append({'id':f'{run}/{config}/{method}/{req}','run':run,'method':method,'config':config,'coverage':ref(cr,basepointer+f'/observed/{oi}'),'requested_optimization':req,'effective_last_optimization':eff,'effective_flag_basis':'archived runner/shared-helper order plus runtime-peer-optimization-correction.json; individual argv not recorded','returncode':None,'status_from_archive':d['status'],'output_hash_matches':None,'runtime_optimization':'O1' if 'sanitize' in config else 'O2','runtime_asan_ubsan':'sanitize' in config,'generated_ubsan_claim':False,'lsan_enabled':False if 'sanitize' in config else None})
 observed=[e for e in executions if e['run']==run]
 artifacts.append({'run':run,'results':ref(rel),'status':d['status'],'compiler_sha256':d.get('compiler_sha256'),'sources':d.get('sources'),'summary_as_recorded':d.get('summary'),'coverage_records':coverages,'derived_execution_records':len(observed),'derived_methods':len({e['method'] for e in observed}),'effective_optimization_counts':dict(Counter(e['effective_last_optimization'] for e in observed)),'scope':d.get('scope'),'source_snapshots_present':(p.parent/'tests/memory-research-peer-projections.py').is_file()})
# Current methods are inspected via AST, not loaded/imported. Explicit independent semantic crosslinks.
testrel='tests/memory-research-peer-projections.py';tree=ast.parse((SNAP/testrel).read_text());astmethods={n.name:{'start':n.lineno,'end':n.end_lineno,'sha256':sha(ast.get_source_segment((SNAP/testrel).read_text(),n).encode())} for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')}
maps=read(R+'evidence/runtime-peer-projections/run-l5_218bk/provenance.json')['source_to_test']
methodmaps=[{'method':m['original_test'],'ledger':Path(m['read_only_record']).name,'proposal':m['proposal'],'group_ids':[u['id'] for u in m['units']],'crosslink_basis':ref(R+'evidence/runtime-peer-projections/run-l5_218bk/provenance.json',f'/source_to_test/{i}'),'run':'run-l5_218bk'} for i,m in enumerate(maps)]
methodmaps += [
 {'method':'test_wide_returned_record_preserves_fields_effect_order_and_retained_alias','ledger':roundnames[5],'proposal':'P1','group_ids':['S4'],'run':'run-1a2ft1yr','crosslink_basis':ref(R+'evidence/runtime-peer-projections/run-1a2ft1yr/provenance.json')},
 {'method':'test_text_equality_after_nul_at_every_short_mismatch_position','ledger':roundnames[6],'proposal':'P1','group_ids':['C2','K5','K6','L1','L3','L6','L11'],'run':'run-egbfb2e0','crosslink_basis':ref(R+'runtime-peer-round8-preregister.json')},
 {'method':'test_scalar_loop_capture_survives_mutation_continue_and_break','ledger':roundnames[6],'proposal':'P2','group_ids':['Z1','Z9'],'run':'run-d29wceo4','crosslink_basis':ref(R+'runtime-peer-round8-preregister.json')}]
semantic=[
 ('Bytes writes share owners; slice copy independent and survives both source drops. Explicit numeric byte outputs.','Zig pointer/slice view and comptime excluded; source must remain azaa after copy write, azya only after direct write.','independent complete outputs, 15 lines'),
 ('Plain row captures share mutation15, fresh scalar snapshot remains0, second row5; both live after outer/source drops.','Zig by-value row assignment is incompatible; explicit Minyar copy algorithm is an extension.','independent scalar/length outputs, 7 lines'),
 ('Unused two-call literal increments2; four distinct weights preserve vector1/2/4/8, sum15 and ordered trace1234.','No comptime/result-location/address equivalence. Sum alone cannot prove order.','count, vector and noncommutative trace; 7 lines'),
 ('List/Bytes/Text producers evaluate once for empty/nonempty, counters1/2/3 then6 and trace123123; bodies emit independent values, counts, sums and text lengths.','No Go index-only range elision, UTF8-byte iteration, array copy, dynamic List growth schedule or allocation-count claim.','full 35-line oracle; allocation-derived lengths do not independently prove allocations occurred'),
 ('All six binary64 relations with NaN in three orientations; direct/helper, !/!!, finite controls and trace12.','No NaN payload, Float formatting or all compiler fcmp predicate verification.','explicit truth-table expectations; 112 lines including 108 relation expectations'),
 ('Neighbor decimals independently straddle2^-1075; source/helper signs and exponent zeros yield six explicit signed64 bits twice.','The 45 Go normal-literal groups are inspiration; these are different boundary inputs, not 45 literal ports.','Decimal rational boundary checks and explicit 12 bit values'),
 ('AND/OR retain mandatory IDs1/2 before decisive literal; helper control records1/2/3, trailing9 absent.','No Zig compile-time knownness, block expression or compileError.','exact event vector and Boolean output, 18 lines'),
 ('At2^53 +1 rounds even, +2 reaches next; direct/helper Booleans, difference2 and exact bits.','Only binary64 runtime arithmetic; excludes f32/f128 and comptime.','10 explicit value/bit outputs'),
 ('Eight distinct returned fields, reverse initializer trace87654321, shared mutation111 vs saved scalar11 and retention across replacement.','Swift struct value-copy/generics/destructor counts/ABI register allocation excluded.','all field vectors and trace; 35 output lines'),
 ('Equality/inequality for sizes0–17,31/32/33 and every changed position including after NUL; unequal lengths; Unicode three scalars/seven bytes/index0/slice.','libc++ lexicographic ordering, arbitrary bytes/invalidUTF8/null pointers, Go Text ordering and literal-escape parity excluded. Embedded-NUL mismatch is original extension.','independent Boolean/value constants; 611 lines; native strcmp calibration rejects after-NUL mismatch'),
 ('Captured scalar4/7/9 ->40709 despite source104/107/109; three visits/positions, continue/break, rebound2703, trace123, length9 and untouched13.','No Zig array by-value copy, record snapshot, labeled loop or mutation-growth semantics. Length9 is not allocation-count evidence.','11 independent outputs; native input-source calibration changes only first answer to1050809')]
methods=[]
for m,(meaning,exclude,oracle) in zip(methodmaps,semantic):
 selected=[e['id'] for e in executions if e['run']==m['run'] and e['method']==m['method']]
 obs=[o for o in method_observations[m['method']] if o['run']==m['run']]
 assert len(selected)==6,(m,len(selected))
 matched=[]
 for g in groups:
  if g['record']['path']==R+m['ledger'] and g['authored_unit_id'] in m['group_ids']:
   matched.append(g['id']);g['original_minyar_methods'].append(m['method']);g['current_view']='original_minyar_projection_executed_for_selected_semantic_extent; original_disposition_retained; not_full_peer_port'
 methods.append({**m,'qualified_group_ids':matched,'current_source':{'record':ref(testrel),'ast_span':astmethods[m['method']]},'archived_observations':obs,'execution_ids':selected,'compatible_existing_contract_and_assertion_extent':meaning,'excluded_semantics':exclude,'oracle_review':oracle,'status':'saved_narrow_matrix_pass; documentary_reconciliation_only','full_upstream_parity':False,'copied_upstream_code':'none claimed in authored reports; conceptual/property inspiration only; not independently proven by a code-similarity audit'})
proposals=[]
for n in roundnames:
 d=read(R+n);pkey='proposed_original_regressions' if 'proposed_original_regressions' in d else 'proposed_regressions'
 for i,p in enumerate(d[pkey]):
  matches=[m for m in methods if m['ledger']==n and m['proposal']==p['id']]
  proposals.append({'id':n+'#'+p['id'],'record':ref(R+n,f'/{pkey}/{i}'),'name':p['name'],'frozen_status':p['status'],'current_view':'selected_original_extension_executed; proposal_scope_not_wholly_dischargeable' if matches else 'proposal_only_no_exact_execution_crosslink_at_cutoff','method_ids':[m['method'] for m in matches],'source_unit_ids_as_recorded':p.get('source_units',p.get('source_group_ids',p.get('source_unit_starts'))),'pending_semantic_regions':p.get('excluded_contracts',p.get('excluded_peer_contracts'))})
# Central inventory pending is an as-of ledger, overlaid rather than rewritten.
central=read(R+'peers-review-ledger.json');pending=[];prior_statuses={};bounded_unique={}
for field in ['original_inventory_paths','combined_bounded_inventory_paths']:
 rows=central[field];before=Counter();after=Counter();changed=[]
 for i,x in enumerate(rows):
  key=sourcekey(x['language'],x['path'],x['commit']);before[x['status']]+=1;status=x['status']
  if key in files and status!='authored_review_record_available':status='authored_review_record_available_with_explicit_extent';changed.append({'source_id':key,'original_status':x['status'],'record':ref(R+'peers-review-ledger.json',f'/{field}/{i}'),'current_review_refs':[e['record'] for e in files[key]['review_extents']]})
  after[status]+=1;bounded_unique[key]=x
 pending.append({'field':field,'entries':len(rows),'before':dict(before),'after_overlay':dict(after),'stale_pending_labels':changed})
# Independent inventories retain directory/pending limitations. No invented suite denominator.
inventories=[]
for name in ['peers-inventory.json','peers-expanded-pending-inventory.json','peer-nim-koka-lean-inventory.json']:
 d=read(R+name);rows=[]
 for di,p in enumerate(d['directories']):
  ik=next(k for k in ['files','entries','paths'] if k in p);es=p[ik];cnt=Counter(x['status'] for x in es);matching=[]
  for i,x in enumerate(es):
   key=sourcekey(p['language'],x['path'],p['commit'])
   if key in files:matching.append({'source_id':key,'original_status':x['status'],'pointer':f'/directories/{di}/{ik}/{i}'})
  rows.append({'directory':p['directory'],'language':p['language'],'entries':len(es),'statuses_as_recorded':dict(cnt),'listing_complete':p.get('listing_complete',p.get('truncated')),'review_overlay_entries':matching})
 inventories.append({'record':ref(R+name),'directories':rows,'scope':d.get('scope')})
roundfilelist=[files[k] for k in sorted(roundkeys)]
union={'round2_through9':{'groups':len(groups),'distinct_pinned_files':len(roundkeys),'complete_selected_files':sum(f['complete_selected_round_file'] for f in roundfilelist),'rounds':roundcounts[4:],'duplicate_group_identity_keys':len(groups)-len({g['id'] for g in groups}),'scope':'heterogeneous authored semantic groups, not ports/assertions/executions/suite denominator'},'legacy':{'reported_central_distinct':central['distinct_source_entries_with_authored_reviews'],'derived_distinct':len(legacykeys),'per_manifest':roundcounts[:4],'overlap_sources':len([k for k in legacykeys if sum(1 for e in files[k]['review_extents'] if Path(e['record']['path']).name in oldnames)>1]),'units_must_not_be_summed':True},'combined':{'distinct_pinned_source_entries':len(files),'overlap_between_legacy_and_rounds':sorted(legacykeys&roundkeys),'whole_read_source_entries':sum(any(e['whole_file_credit'] for e in f['review_extents']) or f['complete_selected_round_file'] for f in files.values()),'partial_only_source_entries':sum(not(any(e['whole_file_credit'] for e in f['review_extents']) or f['complete_selected_round_file']) for f in files.values()),'scope':'includes diagnostic/golden/partial support entries; not197 upstream test files or a global denominator'}}
assert len(groups)==646 and len(roundkeys)==30 and union['round2_through9']['complete_selected_files']==30
result={'schema':'minyar.peer_evidence_reconciliation.v1','cutoff':{'status_cutoff_utc':manifest['cutoff_utc'],'snapshot_start_utc':manifest['started_utc'],'git_head':manifest['git_head'],'dirty_worktree':True,'snapshot_manifest':'evidence/peer-reconciliation/snapshot-manifest.json','snapshot_changed_during_capture':manifest['files_changed_during_capture'],'post_cutoff_pinned_byte_copies':late,'note':'Git HEAD is not final-source revision; path hashes are authoritative. Status never rebound to concurrent later changes.'},'scope':'Documentary reconciliation; no test/native/model/build execution, source fetch, installs, production/test edits, central edits, commits or subagents. Latest cut-off only; campaign active; no global/full-suite/HFT proof.','counts':union,'sources':sorted(files.values(),key=lambda f:f['id']),'round2_through9_groups':groups,'legacy_units':legacy,'original_minyar_methods':methods,'proposal_status_overlay':proposals,'matrix_artifacts':artifacts,'archived_execution_records':executions,'central_pending_overlay':pending,'inventory_overlays':inventories,'historical_optimization_correction':{'record':ref(R+'runtime-peer-optimization-correction.json'),'content':read(R+'runtime-peer-optimization-correction.json')},'checks':{'errors':document_errors,'all_selected_groups_have_pinned_hash':all(files[g['source_id']]['sha256'] for g in groups),'all11methods_have6selectedexecution_records':all(len(m['execution_ids'])==6 for m in methods),'executed_methods_in_frozen_current_test':len(astmethods),'selected_execution_records':sum(len(m['execution_ids']) for m in methods),'reviewed_group_ids_with_projection_inspiration':sum(bool(g['original_minyar_methods']) for g in groups),'not_a_port_count':True}}
(OUT/'reconciled-data.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'counts':union,'checks':result['checks'],'raw_source_missing':[f['path'] for f in roundfilelist if not f['retained_source_bytes']],'pending_overlay_counts':[(x['field'],len(x['stale_pending_labels'])) for x in pending]},indent=2))
