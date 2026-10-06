from pathlib import Path
from collections import Counter,defaultdict
import ast,datetime,hashlib,json,re
ROOT=Path.cwd();OUT=ROOT/'evidence/peer-reconciliation';S=OUT/'snapshot';R='research/2026-10-memory/'
d=json.loads((OUT/'reconciled-data.json').read_text());sha=lambda b:hashlib.sha256(b).hexdigest()
def ref(rel,pointer=''):
 p=S/rel;return {'path':rel,'snapshot':str(p.relative_to(ROOT)),'sha256':sha(p.read_bytes()),'json_pointer':pointer}
def walk(x,p=''):
 if isinstance(x,dict):
  yield p,x
  for k,v in x.items():yield from walk(v,p+'/'+k.replace('~','~0').replace('/','~1'))
 elif isinstance(x,list):
  for i,v in enumerate(x):yield from walk(v,p+'/'+str(i))
# Read every frozen round documentary file, including historical reference copies;
# detailed mappings come from authoritative central JSON, not duplicate markdown units.
index=[];restrictionrefs=[];failrefs=[];support=[]
for p in sorted((S/'evidence/peer-readonly').rglob('*')):
 if not p.is_file() or p.suffix not in ['.md','.json']:continue
 rel=str(p.relative_to(S));b=p.read_bytes();entry={'record':ref(rel),'bytes':len(b),'physical_lines':len(b.splitlines()),'inspection':'entire text parsed/indexed; selected detailed semantic inspection; not independent wholesale test verification'}
 if p.suffix=='.md':entry['headings']=[x for x in b.decode().splitlines() if x.startswith('#')];entry['boundary_lines']=[{'line':i,'text':line} for i,line in enumerate(b.decode().splitlines(),1) if re.search(r'(?i)(unavailable|restricted|restriction|blocked|earliest|union|unimplemented|not.executed|pending)',line)]
 else:
  x=json.loads(b);entry['top_level_keys']=list(x) if isinstance(x,dict) else {'list_entries':len(x)}
  for ptr,y in walk(x):
   for key in ['restrictions','availability','resource_dispositions','prohibited_actions_executed']:
    if key in y:restrictionrefs.append({'record':ref(rel,ptr+'/'+key),'value':y[key]})
   if ('initial' in p.name or 'failure' in p.name) and ptr=='':failrefs.append({'record':ref(rel),'recorded_status':y.get('status',y.get('summary')),'kind':'retained historical documentary failure; no new executable failure inferred'})
 index.append(entry)
(OUT/'document-read-index.json').write_text(json.dumps(index,indent=2)+'\n')
# Central source reports hold authoritative availability/support extents.
for n in [Path(x['record']).name for x in d['counts']['round2_through9']['rounds']]:
 rel=R+n;x=json.loads((S/rel).read_text())
 for key in ['availability','restrictions','resource_dispositions','new_unavailable_upstream_resources','content_or_service_restriction_this_round']:
  if key in x:restrictionrefs.append({'record':ref(rel,'/'+key),'value':x[key]})
 for key in ['support_helper_reviews','in_file_helper_contracts','read_auxiliary_definitions','selected_file_nonassertion_review','source_nonassertion_review']:
  if key in x:support.append({'record':ref(rel,'/'+key),'value':x[key]})
# Pinned license bytes, full notices retained; do not assert copied production code.
pins=json.loads((S/R/'peers.json').read_text())['peers'];licenses=[]
for peer in pins:
 rel='build/peer-research/sources/'+peer['language']+'/'+peer['license_path'];p=ROOT/rel
 candidates=[p]
 for q in (ROOT/'evidence/peer-readonly').rglob('*'):
  if q.is_file() and (q.name==Path(peer['license_path']).name or q.name.endswith('-LICENSE.txt')):candidates.append(q)
 found=None
 for p in candidates:
  if not p.is_file() or p.stat().st_size>200000:continue
  b=p.read_bytes()
  if sha(b)!=peer.get('license_sha256') and peer.get('license_sha256'):continue
  # initial peers manifest may omit license_sha256; use other same-pin manifests.
  if not peer.get('license_sha256'):
   hs=set()
   for n in ['peer-rust-expression-directory.json','peer-swift-statement-directory.json','peer-nim-koka-lean.json']:
    for other in json.loads((S/R/n).read_text()).get('peers',[]):
     if other['language']==peer['language']:hs.add(other.get('license_sha256'))
   if hs and sha(b) not in hs:continue
  rel=str(p.relative_to(ROOT));q=S/rel;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b)
  found={'path':rel,'snapshot':str(q.relative_to(ROOT)),'sha256':sha(b),'full_notice_retained':True};break
 licenses.append({'language':peer['language'],'repository':peer['repository'],'commit':peer['commit'],'upstream_license_path':peer['license_path'],'url':peer['license_url'],'identification':peer.get('license_identification'),'retained_license':found,'inspiration_vs_copy':'Conceptual/property inspiration in original Minyar programs; unchanged upstream code retained only as research evidence. Reports claim no copied maintained source; no exhaustive similarity/legal audit.'})
# Also preserve both LLVM/libc++ licenses and exact IDs from round9.
x=json.loads((S/R/'peer-readonly-values-round9.json').read_text());d['license_provenance']={'peer_pins':licenses,'round9_licenses':{'record':ref(R+'peer-readonly-values-round9.json','/licenses'),'content':x['licenses']}}
for li in licenses:
 if li['language']=='go':li['identification']='BSD-3-Clause'
 if li['language']=='zig':li['identification']='MIT'
 if li['language']=='llvm':li['identification']='Apache-2.0 WITH LLVM-exception; retained full notice contains legacy/third-party sections'
# Legacy execution proof remains appropriately weaker than the instrumented matrix.
legacy_methods={}
for u in d['legacy_units']:
 t=u['minyar_test']
 if not t:
  u['current_execution_state']='no_exact_unit_to_execution_crosslink; original incompatible/pending/existing-contract disposition retained';continue
 method=t.split('.')[-1];path=t.split('::')[0] if '::' in t else 'tests/peer-research-swift-statements.py'
 if not path.startswith('tests/'):path='tests/peer-research-swift-statements.py'
 identity=path+'::'+method;u['minyar_method_id']=identity
 if identity not in legacy_methods:
  tree=ast.parse((S/path).read_text());node=next((n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==method),None)
  legacy_methods[identity]={'id':identity,'record':ref(path),'ast_span':[node.lineno,node.end_lineno] if node else None,'body_sha256':sha(ast.get_source_segment((S/path).read_text(),node).encode()) if node else None,'source_unit_ids':[],'validation_claims':[],'status':'drafted_not_executed' if 'drafted_not_executed' in str(u['validation_as_recorded']) else 'native_O0_O2_reported; exact_per_method_argv_and_output_journal_unavailable_in_integrated_log','precision_limit':'No synthesized optimizer argv, sanitizer validation, full upstream contract or current-source pass. The aggregate log omits test identities in dot-only subsets and does not hash peer test files.'}
 legacy_methods[identity]['source_unit_ids'].append(u['id']);legacy_methods[identity]['validation_claims'].append(u['validation_as_recorded'])
 u['current_execution_state']=legacy_methods[identity]['status']
 if 'drafted_not_executed' not in str(u['validation_as_recorded']):u['archived_validation']={'results':ref(R+'profiling-integrated-focused.json'),'log':ref(R+'profiling-integrated-focused.log'),'runtime_c_optimization_as_logged':'O2','generated_optimizations_as_authored_and_recorded':['O0','O2'],'sanitizer_executed':False,'exact_per_method_argv_record':None,'scope':'earlier native semantic subset; not exact final formatted runtime snapshot'}
d['legacy_method_crosslinks']=list(legacy_methods.values());d['legacy_validation_records']=[ref(R+'profiling-integrated-focused.json'),ref(R+'profiling-integrated-focused.log'),ref(R+'peer-nim-koka-followups.json'),ref(R+'peer-nim-koka-lean.json','/port_trial_notes')]
d['availability_and_restrictions']=restrictionrefs;d['support_extents_and_pending_complements']=support;d['preserved_documentary_failures']=failrefs
# Native oracle calibrations are rejection evidence, never production passes or ports.
calibrations=[]
for p in sorted((S/R/'evidence/runtime-peer-calibrations').glob('*/results.json')):
 x=json.loads(p.read_text());rel=str(p.relative_to(S));calibrations.append({'record':ref(rel),'status':x['status'],'scope':x['scope'],'compiler_sha256':x['compiler_sha256'],'baseline_result_sha256':x['baseline_result_sha256'],'checks':x['checks'],'detections':x.get('detections',x.get('mutant_detections')),'sources':x['sources'],'claimed_generated_native_optimizations':['O0','O2'],'sanitizer':False,'production_pass_credit':0,'peer_port_credit':0})
d['oracle_calibrations']=calibrations
# Documentary checks: source extents, all recorded result source hashes, saved argv and output hashes.
checks=[]
for f in d['sources']:
 if f['retained_source_bytes']:
  entry=f['retained_source_bytes'][0];p=ROOT/entry['snapshot'];b=p.read_bytes();checks.append({'kind':'pinned_source_bytes','id':f['id'],'passed':sha(b)==f['sha256']})
  for e in f['review_extents']:checks.append({'kind':'raw_physical_extent','id':f['id'],'passed':e['physical_lines']==len(b.splitlines())})
for a in d['matrix_artifacts']:
 checks.append({'kind':'execution_denominator','id':a['run'],'passed':a['summary_as_recorded']['generated_executions']==a['derived_execution_records']})
 for source in a['sources']:
  rel=str(Path(a['results']['path']).parent/source['snapshot']);p=S/rel
  checks.append({'kind':'archived_matrix_source','id':rel,'passed':sha(p.read_bytes())==source['sha256'] if p.is_file() else None,'missing_reason':None if p.is_file() else 'historical snapshot source not retained in archive'})
for e in d['archived_execution_records']:
 if 'link_argv' in e:
  last=[x for x in e['link_argv'] if re.fullmatch(r'-O(?:[0123szg]|fast)',x)][-1]
  checks.append({'kind':'effective_optimizer_argv','id':e['id'],'passed':last==e['effective_last_optimization']==e['recorded_effective_flag']})
  checks.append({'kind':'saved_actual_stdout_hash','id':e['id'],'passed':e['output_hash_matches']})
for m in d['original_minyar_methods']:
 for o in m['archived_observations']:
  checks.append({'kind':'consistent_expected_line_count','id':m['method'],'passed':o['expected_lines']==m['archived_observations'][0]['expected_lines']})
(OUT/'documentary-checks.json').write_text(json.dumps({'scope':'Counts/hashes/JSON/AST only; no fixture execution','checks':checks,'passed':sum(x['passed'] is True for x in checks),'failed':sum(x['passed'] is False for x in checks),'unavailable':sum(x['passed'] is None for x in checks)},indent=2)+'\n')
# Label overlays cannot rewrite frozen source-lane statuses.
related={
 'peer-readonly-go-zig-round2.json#R6':('test_shared_row_and_explicit_snapshot_survive_outer_replacement','Row sharing/replacement only; literal-vs-shared topology and all four cells remain unproven by this exact projection.'),
 'peer-readonly-go-zig-round3.json#P1':('test_wide_returned_record_preserves_fields_effect_order_and_retained_alias','Related record/list replacement lifetime; exact Cell/Foo vectors and owner/helper replacement sequence pending.'),
 'peer-readonly-strings-round4.json#P1':('test_shared_bytes_and_independent_slice_survive_replacement','Copy/alias contract overlaps; clear-through-alias and retained2048-scalar Text substring remain outside this method.'),
 'peer-readonly-strings-round4.json#P3':('test_text_equality_after_nul_at_every_short_mismatch_position','Related Unicode lengths/scalars/slices; exact aé🙂b/aä本☺ sequences and Go byte-offset contrasts remain pending.'),
 'peer-readonly-strings-round4.json#P6':('test_text_equality_after_nul_at_every_short_mismatch_position','One Unicode partial slice; full nested ASCII, empty Bytes endpoints and diagnostic matrix not established.')}
for p in d['proposal_status_overlay']:
 if p['id'] in related:p['related_partial_coverage']={'method':related[p['id']][0],'limitation':related[p['id']][1]}
 if p['id']=='peer-readonly-strings-round4.json#P4':p['remaining_proposal_regions']=['Optional growing List visits1,2,3,sum6 not executed by producer-only method.','Original proposed Text byteLength7 is not separately printed/asserted in that method.']
d['later_user_status_addendum']={'noted_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'basis':'User message during reconciliation; no post-cutoff source/result inspection','round9':{'proposal_ids':['peer-readonly-values-round9.json#P1','peer-readonly-values-round9.json#P2'],'status':'core_authoring_two_original_methods; execution_not_yet_reported','execution_credit':0,'excluded_claims':['signed minimum abs success','C++ reference identity','full std::gcd or minmax parity']},'cutoff_policy':'This addendum does not alter archived11-method evidence or66 selected executions; new source/result hashes required for later execution overlay.'}
issues=[
 {'id':'C1','kind':'stale central source-review status','evidence':ref(R+'peers-review-ledger.json'),'finding':'24 unique bounded-inventory paths retain not_semantically_reviewed labels despite later complete source reviews. Six additional selected source paths lie outside those bounded inventory tables. Exact overlays enumerate every changed path.','correction':'Keep historical bytes; current view shows63 original-inventory authored entries (39+24) and70 combined bounded entries (46+24), with exact remaining2730 and4288 dispositions separated.'},
 {'id':'C2','kind':'stale current evidence-index aggregate','evidence':ref(R+'README.md'),'finding':'Evidence-index runtime row still says eight original tests/48 final executions. True for run-l5_218bk; incomplete as a current projection census. Later prose and runtime-peer-projections.md correctly distinguish wide/round8 targeted runs.','correction':'11 distinct original projection methods have separate saved scopes:8×6=48, wide1×6=6, round8P1×6=6, round8P2×6=6;66 selected records across four snapshots, no complete11-method matrix.'},
 {'id':'C3','kind':'historical proposal labels need current overlays','evidence':[ref(R+n,'/proposed_original_regressions' if 'proposed_original_regressions' in json.loads((S/R/n).read_text()) else '/proposed_regressions') for n in [Path(x['record']).name for x in d['counts']['round2_through9']['rounds']]],'finding':'11 of33 source-lane proposals have corresponding original executed extensions;22 lack exact execution crosslinks at cutoff. Historical zero-execution statements remain true for each source lane. Some unmapped proposals have partial overlap, and round4P4 retains unexecuted optional growth/byteLength regions.','correction':'Do not present proposal-only source ledgers as proof no Minyar adaptations now exist; retain original incompatible/pending dispositions plus method/assertion/argv overlay.'},
 {'id':'C4','kind':'historical optimization misstatement already corrected','evidence':ref(R+'runtime-peer-optimization-correction.json'),'finding':'Earlier requested O0/O2 sanitizer links actually ended at O1 twice. Preserve valid outputs/ASan checks; historical individual link argv absent. Correction also names run-klwzmyf0, whose runtime-projections durable directory is absent in the frozen bundle.','correction':'Native requestedO0/O2 and effective sanitizerO1 labeled separately; corrected6/8-method and targeted runs retain actual last link flagsO0/O2. No unsupported new run credit for absent archive.'},
 {'id':'C5','kind':'whole-file/selection aggregate guard','evidence':ref(R+'peer-readonly-values-round9.json','/selected_report_union'),'finding':'646 groups/30 complete selected files mechanically verified. Earlier central167 includes23 partial Koka sections; initial32/Rust13/Swift25/NimKokaLean106 have9 overlapping source paths.','correction':'Deduplicated four earlier manifests plus selected30 give197 source entries:174 whole-read,23 partial. This is not197 tests or a campaign-suite denominator; retain all unit counts per manifest.'},
 {'id':'C6','kind':'archival gap','evidence':ref('evidence/peer-readonly/go-zig-round2/provenance.json'),'finding':'Go test/for.go and test/simassign.go have source hashes and authored complete-read extents; no durable raw source located in saved evidence or pinned build-source cache.195/197 source bytes are independently rehashed; selected round set28/30.','correction':'Label two raw sources unavailable in this reconciliation. No fetch or retry; attribution remains provenance-only for those bytes.'},
 {'id':'C7','kind':'weak oracle/semantic transfer boundaries','evidence':ref(R+'peer-readonly-values-round9.json'),'finding':'C++ runtime minmax asserts scalar addresses; same values cannot prove identities. Go copy projections test an explicit algorithm, not copy intrinsic lowering. Commutative counts cannot prove order; Go len/cap conjunction does not assert both independently. Go prints without goldens and skipped/dormant/comptime branches cannot receive observed pass credit.','correction':'Keep source-specific semantic limits and independent Minyar expected constants. Explicitly exclude C++ reference identity, unsigned/type-phase parity, invalidUTF8 ordering, Zig writable views/value copies and Go oversized shifts.'},
 {'id':'C8','kind':'later in-progress work','evidence':{'kind':'user_status_message','archived_execution_artifact':None},'finding':'Core authoring round9P1/P2, execution not yet reported.','correction':'Planned/authored is not passed. The frozen crosswalk grants zero execution credit; later addendum records user status only.'}]
d['findings_and_current_view_corrections']=issues
d['oracle_review_limits']={'review':'Detailed inspection of11 projection bodies and expectations plus selected prior semantic/memory tests and upstream spans. No test modules imported; no claim to have independently verified every existing test.','mirroring_assessment':'No direct implementation-mirroring oracle found in the inspected11 projection methods: truth tables, integer vectors, exact decimal boundaries and bit constants are independent of runtime C output. Source construction and expected value loops sharing fixture parameters are weaker than external diversity but are not copies of the runtime equality/ownership algorithms.','specific_flags':['round4P2 explicit copying helper would test its own algorithm rather than Go copy lowering; use fixed complete destination arrays if later implemented.','round9 gcd expected generated by same Euclidean algorithm would be circular; proposal supplies fixed arithmetically justified outputs, retain those.','Do not equate identical source/helper outputs alone with correctness; existing bit/vector/truth constants distinguish both being wrong.','Allocation-producing source syntax and Text length oracles do not independently measure allocation count or destructor timing.','Signed-minimum abs is a stop contract; excludes成功 reinterpretation from C++ gcd.'],'tdd_classification':'Methods reported authored with expectations before baseline runs; all11 were alreadygreen, so coverage additions. Saved calibration reds are semantic rejections of isolated mutation/input control, not evidence of production defects or full mutation adequacy.'}
d['missing_regions']={'unlinked_round_group_ids':[g['id'] for g in d['round2_through9_groups'] if not g['original_minyar_methods']],'meaning':'527 group identities lack these11 projection crosslinks; includes incompatible and merely related fixtures.119 linked identities are inspiration references, including45 normal Go literal groups behind a different underflow boundary extension; never119 full ports.','pending_proposal_ids':[p['id'] for p in d['proposal_status_overlay'] if not p['method_ids']],'upstream_and_support':'Exact support pending complements stay in support_extents_and_pending_complements. Unselected/screened discovery candidates and restricted/unavailable resources receive no selected review/execution credit.','execution':'No complete11/13-method final-source matrix, peer backend run, generated UBSan, LSan, full compiler integration, native-model or AFL restart. Legacy per-method argv/current-source proof missing; only earlier native suite logs available.','reproduction':'Selected runtime text/helper/source snapshots and compiler artifact hashes retained; archived round8 bundles explicitly omit compiler binary, object, executable and LLVM. Matching installed compiler/toolchain remains external. No binary hash reread undertaken.','raw_source_files':['test/for.go','test/simassign.go'],'partial_koka':'23 companion golden files have ownership/core section reviews without exact line partition; never whole-file review credit.','campaign':'Active; earliest completion2026-10-04T06:54:29Z, this bounded reconciliation is not campaign completion.'}
d['documentary_verification']={'artifact':'evidence/peer-reconciliation/documentary-checks.json','passed':sum(x['passed'] is True for x in checks),'failed':sum(x['passed'] is False for x in checks),'unavailable':sum(x['passed'] is None for x in checks),'document_read_index':'evidence/peer-reconciliation/document-read-index.json','documents_indexed':len(index),'source_bytes_rehashed':sum(bool(f['retained_source_bytes']) for f in d['sources']),'not_runtime_execution':True}
# Final artifact is generated from reconciled JSON. Do not edit historical source ledgers.
(ROOT/R/'peer-evidence-reconciliation.json').write_text(json.dumps(d,indent=2)+'\n')
print(json.dumps({'verification':d['documentary_verification'],'legacy_methods':len(legacy_methods),'licenses_retained':sum(bool(x['retained_license']) for x in licenses),'failed_checks':[x for x in checks if x['passed'] is False],'unavailable_checks':[x['id'] for x in checks if x['passed'] is None]},indent=2))
