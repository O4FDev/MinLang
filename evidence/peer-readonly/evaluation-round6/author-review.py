"""Build documentary review ledger; no tests imported or invoked."""
import collections,datetime,hashlib,json,pathlib,re
R=pathlib.Path('.');E=R/'evidence/peer-readonly/evaluation-round6'
def readj(p):return json.loads(pathlib.Path(p).read_text())
def writej(p,d):pathlib.Path(p).write_text(json.dumps(d,indent=2)+'\n')
M=readj(E/'source-manifest.json');LM=readj(E/'local-manifest.json')
Z=next(x for x in M if x.get('upstream_path')=='test/behavior/eval.zig')
G=next(x for x in M if x.get('upstream_path')=='test/convert.go')
lines=pathlib.Path(Z['snapshot']).read_text().splitlines()
D={}
for row in (E/'review-units.tsv').read_text().splitlines():
 st,mode,contract,mapping,cov,helper=row.split('\t')
 D[int(st)]=dict(mode=mode,contract=contract,mapping=mapping,cov=cov.split(',') if cov else [],helper=[list(map(int,a.split('-'))) for a in helper.split(',') if a])
def block_end(st):
 depth=0;started=False
 for i in range(st-1,len(lines)):
  s=re.sub(r'"(?:\\.|[^"\\])*"','""',lines[i].split('//')[0])
  depth+=s.count('{')-s.count('}');started|='{' in s
  if started and not depth:return i+1
 raise ValueError(st)
def complement(spans,n):
 covered={i for a,b in spans for i in range(a,b+1)};out=[]
 for i in range(1,n+1):
  if i not in covered:
   if out and out[-1][1]+1==i:out[-1][1]=i
   else:out.append([i,i])
 return out
starts=[i for i,s in enumerate(lines,1) if re.match(r'^test\b',s)]+[1697]
assert set(starts)==set(D) and len(starts)==111
helper_owner={612:604,717:709,718:709,589:584,592:584,595:584,598:584}
site_lines=[i for i,s in enumerate(lines,1) if re.search(r'\b(?:expectEqual|expect|assert|assertEqualPtrs)\(|@compileError\(',s) and not re.search(r'\bfn\s+assertEqualPtrs\(',s)]
units=[];mode={'I':'incompatible_as_written','A':'adapt_pending','D':'adopt_pending'}
for n,st in enumerate(sorted(starts),1):
 r=D[st];end=block_end(st);title=re.search(r'^test "(.*)"',lines[st-1])
 sites=[]
 for i in site_lines:
  if st<=i<=end or helper_owner.get(i)==st:
   disp=mode[r['mode']];reason=r['mapping']
   if '@compileError(' in lines[i-1]:disp='incompatible_as_written';reason='Compile-time known-condition/rejection proof unavailable locally; numeric runtime projection cannot prove it.'
   if st==55 and i==57 or st==93 and 102<=i<=105:disp='incompatible_as_written';reason='Explicit comptime assertion excluded; runtime sibling value projection tracked separately.'
   if st==467 and i>=476:disp='incompatible_as_written';reason='Typed narrow/wide complement or out-of-range arbitrary-width literals; signed64 substitution changes contract.'
   src=lines[i-1].strip() if i!=1317 else '\n'.join(lines[1316:1322])
   reach='unconditional_skip_before_body' if st in [1448,1465] else 'runtime_condition_false; not_reached' if st==1407 else 'conditional_compile_error_must_be_unreachable' if '@compileError' in src else 'only_if_recorded_skip_guards_allow'
   sites.append(dict(line=i,end_line=1322 if i==1317 else i,source=src,disposition=disp,rationale=reason,expected='predicate true/equality succeeds; compileError site must be unreachable; explicit operands and manual semantic outcomes retained',reachability=reach))
 guards=[dict(line=i,source=lines[i-1].strip()) for i in range(st,end+1) if 'return error.SkipZigTest' in lines[i-1]]
 units.append(dict(id=f'Z{n}',language='zig',commit=Z['commit'],path=Z['upstream_path'],sha256=Z['sha256'],lines=[st,end],name=title[1] if title else 'anonymous f128 equality' if st==423 else 'module comptime partial array assignment',url=Z['url']+f'#L{st}-L{end}',disposition=mode[r['mode']],upstream_expected=r['contract'],minyar_mapping=r['mapping'],local_coverage_ids=r['cov'],helper_spans=r['helper'],source_assertion_sites=sites,backend_skip_guards=guards,comptime_source_lines=[i for i in range(st,end+1) if re.search(r'\bcomptime\b',lines[i-1])],terminal_failure_paths=[dict(line=i,source=lines[i-1].strip()) for i in [1387,1401,1730,1736] if st<=i<=end],verification='whole_selected_file_and_in_file_helpers_manually_read; source_only',port_status='not_implemented; not_executed'))
for n,(span,site,outcome,mapping) in enumerate([
 ([31,35],32,'typeof(f)==typeof(g), both func() int. Neither function is executed.','No first-class function values/interface boxing/type reflection; return0 replacement changes assertion.'),
 ([37,41],38,'typeof(+a)==typeof(a), named main.A preserved under unary plus; value unasserted.','No named Integer-derived types/unary-plus reflected type preservation.'),
 ([42,45],42,'typeof(a+0)==typeof(a), named main.A plus untyped constant0 preserves type; value unasserted.','No Go named-type/untyped-constant/reflection semantics.')],1):
 units.append(dict(id=f'G{n}',language='go',commit=G['commit'],path=G['upstream_path'],sha256=G['sha256'],lines=span,name=outcome,url=G['url']+f'#L{span[0]}-L{span[1]}',disposition='incompatible_as_written',upstream_expected=outcome,minyar_mapping=mapping,local_coverage_ids=['numbers'],helper_spans=[[13,13],[15,19],[21,28],[30,46]],source_assertion_sites=[dict(line=site,end_line=site,source=pathlib.Path(G['snapshot']).read_text().splitlines()[site-1].strip(),disposition='incompatible_as_written',rationale=mapping,expected='failure predicate false; reflected type strings equal',reachability='main')],backend_skip_guards=[],verification='whole46_line_file_and_helpers_read; source_only',port_status='not_implemented; not_executed'))
# Frozen local fixture spans, with explicit limits; no execution inferred.
coverage=[
 ('numbers','tests/conformance/numbers-and-comparisons/program.min',[[1,9]],'Signed64 arithmetic/comparisons, not named/reflected/narrow types.','tests/conformance/numbers-and-comparisons/expected.stdout',[[1,9]]),
 ('loops','tests/conformance/loops-and-assignment/program.min',[[9,15],[45,64]],'Runtime for/while break/continue, nested innermost break; no labeled exits/comptime quotas.','tests/conformance/loops-and-assignment/expected.stdout',[[1,1],[14,16]]),
 ('records','tests/conformance/loops-and-assignment/program.min',[[1,7],[26,43]],'Shared record scalar/Text mutation via functions/outer records, health15/99, blocks42; no identical read helper on same record across mutation.','tests/conformance/loops-and-assignment/expected.stdout',[[8,13]]),
 ('literal','tests/recursive-data.py',[[148,184]],'Left-to-right List values1/2/3; earlier projected record retains old! during replacement. No fixed-array operators/static copies.',None,[]),
 ('row','tests/memory-research-peer-projections.py',[[63,80]],'Shared row vs explicit scalar snapshot survives replacement, exact15,0,5,15,0,3,3. No implicit by-value record/array copy.',None,[]),
 ('short','tests/peer-research-semantics.py',[[80,97]],'Basic ||/&& skip traps and ordered IDs1,2,3,4; decisive literal examples place literal FIRST, not after mandatory effects.',None,[]),
 ('short-temp','tests/adversarial.py',[[145,161]],'Boolean producer temporary Text, precedence and IDs3,4,5,6,8; no middle decisive literal after two mandatory effects.',None,[]),
 ('floats','tests/conformance/floats-and-bits/program.min',[[1,28]],'Binary64 ordinary arithmetic/NaN equality/Float List; no2^53 addition tie or f32/f128 phase evaluation.','tests/conformance/floats-and-bits/expected.stdout',[[1,21]]),
 ('bits','tests/conformance/floats-and-bits/program.min',[[29,38]],'Small &,|,^,~0=-1,1<<10,-16>>2,wrapping; no wide or type-dependent contract.','tests/conformance/floats-and-bits/expected.stdout',[[22,29]]),
 ('bytes','tests/conformance/bytes/program.min',[[1,38]],'Zero-filled/shared Bytes, endian storage, iteration and slice values; this fixture does not assert slice independence. No writable view/sentinel/layout.','tests/conformance/bytes/expected.stdout',[[1,16]]),
 ('text','tests/conformance/text-and-lists/program.min',[[1,12]],'Content equality,indexing,slicing,Lists; no pointer identity/type reflection/factory.','tests/conformance/text-and-lists/expected.stdout',[[1,6]]),
 ('existing-projections','tests/memory-research-peer-projections.py',[[41,153]],'Four prior originals in initial frozen fixture; execution records separate. Duplicates excluded.',None,[]),
 ('list-targets','tests/list-access.py',[[68,111]],'Index/RHS growth,receiver capture,Text compound RHS lifetime; not raw-pointer/phase equivalence.',None,[]),
 ('target-order','tests/compiler-hardening.py',[[292,320]],'Field/Bytes receiver captured before effects; not type memoization/global purity.',None,[]),
 ('local-oracle','tests/regressions.py',[[54,65]],'When invoked, asserts status/exact UTF8 stdout at O0/O2; read only this round. Prior sanitizer flags correction separately disclosed.',None,[])]
cmap={}
for key,path,spans,proves,ep,esp in coverage:
 m=next(x for x in LM if x['path']==path);cmap[key]=dict(path=path,snapshot=m['snapshot'],sha256=m['sha256'],lines=spans,proves=proves,verification='frozen_fixture_source_only; no_current_pass_claim')
 if ep:
  m=next(x for x in LM if x['path']==ep);cmap[key].update(expected_path=ep,expected_snapshot=m['snapshot'],expected_sha256=m['sha256'],expected_lines=esp)
helper_specs=[
 ('lib/std/testing.zig',[[69,218],[363,377],[604,608]],'expect false returns TestUnexpectedResult. expectEqual peer-resolves commonT; scalar != fails; ordinary struct fields recurse, array routes expectEqualSlices. Slice helper tests every element via meta.eql and equal length, errors otherwise. Needed branches for bool,int and repeated M/S arrays; diagnostic formatting outside extent unreviewed.'),
 ('lib/std/debug.zig',[[545,560]],'assert false invokes unreachable. Comptime failures invalid; ReleaseFast/Small runtime assert can disappear, unlike expect. Do not infer always-active runtime oracle.'),
 ('lib/std/mem.zig',[[257,345],[675,689],[693,707],[729,787],[4344,4357]],'zeroes recurses integers0/ordinary fields and arrays via by-value splat, so repeated S rows are independent Zig values. eql validates lengths/value equality; optional unique-representation byte path. Selected byte runtime equality tiny strings, or comptime; no SIMD result claim. sliceAsBytes representation cast, zero-bit branch and checked size multiplication. No ownership oracle.'),
 ('lib/std/meta.zig',[[707,765],[1108,1151]],'eql recursively checks ordinary structs/arrays/scalars, enabling all16 repeated-matrix cells. Pointers compare identity, slices address+length. hasUniqueRepresentation integer gate size*8==bits. No pointee/lifetime evidence.')]
support=[]
for p,spans,meaning in helper_specs:
 m=next(x for x in M if x.get('upstream_path')==p)
 support.append(dict(path=p,commit=m['commit'],url=m['url'],sha256=m['sha256'],snapshot=m['snapshot'],reviewed_spans=spans,review_pending_spans=complement(spans,m['physical_lines']),contract=meaning,status='selective_needed_helper_contract_review; remainder_unreviewed'))
# Inline helper bodies are inside each completely reviewed block. External definitions explicitly described.
external=[
(11,14,'fibonacci','base x<=1->1; recursive fib(x-1)+fib(x-2);7->21'),
(16,18,'unwrapAndAddOne','force unwrap ?i32 then+1;1234->1235'),
(35,41,'gimme1or2','comptime bool chooses1/2 and mutable z address taken'),
(51,53,'staticAdd','a+b;1,2->3'),
(60,70,'constExprEvalOnSingleExprBlocksFn','if b labeled block literal3, elsex'),
(81,89,'max','Tbool uses or; otherwise larger numeric argument'),(90,92,'letsTryToCompareBools','specialize max(bool)'),
(114,117,'fnWithSetRuntimeSafety','safetytrue;1234'),(168,172,'MakeType','anonymous struct type fieldT'),
(178,185,'testTryToTrickEvalWithRuntimeIf','inline ten iterations discarding runtime expression; returns comptime i10'),
(250,255,'makePoint','Point{x,y}'),(282,284,'one','value+1'),(285,287,'two','value+2'),(288,290,'three','value+3'),
(292,301,'performFn','filter command name first byte by comptime prefix; sequential accumulator calls'),
(322,329,'generateTable','1010 elements index casts'),(331,337,'doesAlotT','quota5000,comptime table,runtime lookup'),
(366,368,'doNothingWithType','discard type parameter'),(427,436,'copyWithPartialInline','four big-endian groups of four bytes via OR shifts24,16,8,0'),
(547,551,'vec3','data[x,y,z]'),(579,582,'modifySomeBytes','write a0/b9 only'),(587,600,'testCompTimeUIntComparisons','four unsigned inequalities compileError if not folded'),
(611,613,'assertEqualPtrs','expect ptr1==ptr2; callsite608'),(634,639,'TypeWithCompTimeSlice','discard field_name; construct struct nestedNode TYPE'),
(651,653,'increment','pointer i32+=1'),(667,669,'SingleFieldStruct.read_x','current self.x via constpointer'),(681,683,'wrap','Wrapper{T} type field'),
(704,707,'loopNTimes','comptime n inline empty loop'),(713,720,'testVarInsideInlineLoop','tuple args i0true,i1Integer42 checks'),
(747,749,'oneItem','fixed[1]i32 x'),(751,753,'scalar','u32identity')]
infile=[dict(lines=[a,b],name=name,contract=meaning) for a,b,name,meaning in external]
nested={
377:'foo_zero()->u0 zero',685:'b(comptime self)->a2',869:'A.d creates default A.c=B{} then e discards; undefined byte buffer never read',898:'foo()->comptime_int1234',937:'declarations(T)->enum.decls',956:'b(c) defines local D field @TypeOf(c), checks1234',981:'bar increments count,foo checks byteb,doTheTest assertions true/count2',1013:'bar ignores outer byte,count++;foo checksb; labeled outer exit',1049:'doTheTest inline searchabc,break operandb,elsez,runtime+comptime callers',1065:'doTheTest switch searchabc,break operandb,elsez,runtime+comptime callers',1084:'C(B)/D(F) recursive aligned type factory; doTheTest buffer field mutation43',1122:'C(B)/D(F) bare-union recursive aligned types; mutate43',1160:'C(B)/D(F) tagged-union recursive aligned types;mutate43',1203:'Foobar.foo fills1024a with type fields undefined; S.foo discards first10 slice',1232:'foo(ptr) setsok(*ptr==1234);doTheTest checksok',1373:'foo(a)->a==4',1437:'foo asserts global array len1024 at comptime',1484:'foo x++returnstrue;resetx between scenarios',1511:'foo x++returnsfalse;resetx between scenarios',1549:'inline doNothing()->void used only TypeOf',1557:'fnPtr->function value address;Nil()->u8 zero never called',1586:'NewType(T) sizeof condition selects void elseT',1601:'some(V) switchconst2 returnsV; invalid V.foo branch not evaluated',1631:'T1.v()->error{}!usize1;T2.v()->error{Error}!usize2',1663:'foo(bool)->u16,true u8FF widen,falseu16FFFF',1685:'inComptime forwards phase query'}
for st,meaning in nested.items():infile.append(dict(lines=[st,block_end(st)],name='nested helper(s) in complete unit',contract=meaning))
proposals=[
dict(id='P1',name='Ordered mandatory effects before decisive Boolean literal/helper',source_unit_starts=[1484,1511],local_coverage_ids=['short','short-temp','existing-projections'],gap='Existing literal decisiveness examples put literal FIRST; producer/precedence tests decide on effectful returns. No inspected fixture has two mandatory effects then a middle false/true literal and forbidden trailing effect. Peer identical increments prove count, not order.',minyar_sketch='observe(events,id,result):Boolean adds id. AND observe1true && observe2true && false && observe9true; repeat with third helper observe3false replacing literal. Reset before every scenario; OR observe1false || observe2false || true || observe9false; repeat with observe3true helper. Third helper may allocate Text(3)+\"!\".',expected=['AND literal false; exact events[1,2],count2','AND helper false; exact events[1,2,3],count3','OR literal true; exact events[1,2],count2','OR helper true; exact events[1,2,3],count3'],independent_oracle='Ordered ID list and Boolean result, trailing9 absent; explicit reset; no commutative-order inference.',excluded_peer_contracts=['comptime known-condition','compileError','Zig block expression'],status='original_narrow_proposal; not_implemented; not_executed'),
dict(id='P2',name='Binary64 unit-spacing tie arithmetic at2^53',source_unit_starts=[419],local_coverage_ids=['floats'],gap='Ordinary Float/NaN fixtures and parse/formatting near2^53 do not perform +1/+2 arithmetic. Round5 subnormal literal and NaN relations are distinct.',minyar_sketch='x=9007199254740992.0; compare x+1.0==x, x+2.0==9007199254740994.0, print((x+2.0)-x). Repeat via add(left:Float,right:Float):Float returning left+right.',expected=['direct/helper +1 equality true','direct/helper +2 equality true','direct/helper difference2.0'],independent_oracle='Binary64 spacing2 at2^53; halfway+1 rounds even, next representable+2 differs2. Explicit decimal constants/expected Booleans, not solely variant equality.',excluded_peer_contracts=['f32/f128','comptime','implicit Integer/Float mixing'],status='original_narrow_proposal; not_implemented; not_executed')]
for u in units:
 u['proposal_ids']=[p['id'] for p in proposals if u['language']=='zig' and u['lines'][0] in p['source_unit_starts']]
 u['coverage_status']='related_frozen_source_only; exact_peer_core_not_covered' if u['disposition']=='incompatible_as_written' else 'transferable_value_projection_pending; not_already_covered_as_exact_peer_test'
prior_pairs=[];prior_counts=[]
for n in ['go-zig-round2','go-zig-round3','strings-round4','values-round5']:
 d=readj(E/f'references/research/2026-10-memory/peer-readonly-{n}.json');us=d.get('units',d.get('comparison_groups',[]))
 prior_counts.append(len(us));prior_pairs.extend((u['language'],u['path']) for u in us)
assert sum(prior_counts)==336 and len(set(prior_pairs))==15
assert not set(prior_pairs)&{('go',G['upstream_path']),('zig',Z['upstream_path'])}
nonassert=[]
for m,lang in [(G,'go'),(Z,'zig')]:
 used=[u['lines'] for u in units if u['language']==lang]
 if lang=='zig':used += [h['lines'] for h in infile]
 nonassert.append(dict(path=m['upstream_path'],reviewed_spans=complement(used,m['physical_lines']),meaning='All imports,global declarations,comments,drivers,initialized but unasserted fields and whitespace read; no extra comparison credit. Go mapm, namedB,b2,x support only; f/g are not called.'))
selected=[]
for m,lang in [(G,'go'),(Z,'zig')]:
 lic=next(x for x in M if x.get('upstream_path')=='LICENSE' and '/'+lang+'/' in x['snapshot'])
 selected.append(dict(**m,language=lang,reviewed_spans=[[1,m['physical_lines']]],review_pending_spans=[],status='retrieved_round5; complete_file_semantic_review_round6',license='BSD-3-Clause; Go Authors2009' if lang=='go' else 'MIT/Expat; Zig contributors',license_sha256=lic['sha256'],license_url=lic['url']))
counts=dict(selected_source_entries=2,complete_selected_files_reviewed=2,selected_raw_physical_lines=1805,zig_test_blocks=110,zig_module_comptime_blocks=1,go_type_identity_assertion_groups=3,authored_comparison_groups=len(units),group_dispositions=dict(collections.Counter(u['disposition'] for u in units)),assertion_dispositions=dict(collections.Counter(s['disposition'] for u in units for s in u['source_assertion_sites'])),zig_assertion_and_compile_error_source_sites=sum(len(u['source_assertion_sites']) for u in units if u['language']=='zig'),zig_skip_guard_source_sites=sum(len(u['backend_skip_guards']) for u in units),go_failure_predicates=3,original_proposals=len(proposals))
counts.update({k:0 for k in ['ports_implemented','peer_or_local_test_executions','compilations','installations','production_build_test_edits','commits','subagents','timing_measurements']})
ledger=dict(schema='minyar.peer_readonly_evaluation.round6.v1',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),mode='bounded_source_only_review',scope=dict(selected=selected,optional_extra_file_selected=False,reason='Full eval selection already supplies distinct relevant contracts; no extra whole accessible retained candidate needed.',prior_rounds2_3_4_5_groups=336,prior_distinct_files=15,central_manifests_changed=False,remaining_selected_review=[]),counts=counts,grouping_policy='One complete Zig test block or module comptime block and three Go predicates. Mixed groups have explicit per-site disposition overrides; group projection does not imply all sites transferable. These heterogeneous groups/sites are not ports, dynamic assertion executions, language-suite coverage or campaign totals.',outcome_policy='Pinned manual source expectations only. All selected extents/helper definitions read. Backend guards restrict reached assertions; two unconditional skips and one runtimefalse dormant assertion identified. No peer/backend/local compilation or execution.',local_coverage_policy='Frozen source/test spans and exact expected bytes only, no new pass claim. Matching values not copy/lifetime/pointer proof; absence statements bounded to inspected fixtures.',contract_references=[dict(path='docs/language.md',lines=[[20,66],[68,103],[134,193],[253,285]],meaning='signed64,binary64,literal-only constants,ordinary loops,shared values,explicit records'),dict(path='docs/syntax-review.md',lines=[[24,38]],meaning='conditional expressions/generics/immutable bindings not promised'),dict(path='docs/runtime-memory.md',lines=[[39,73],[75,104]],meaning='shared references,construction retention,reference return ownership')],local_coverage_references=cmap,comparison_groups=units,support_helper_reviews=support,in_file_helper_contracts=infile,selected_file_nonassertion_review=nonassert,proposed_original_regressions=proposals,availability=dict(new_unavailable_selected_resources=[],content_or_service_restriction_this_round=None,network_calls=0,prior_restricted_rust='Excluded; not retried/bypassed.',round5_directory_api='Unavailable record preserved; not retried/bypassed.',stopped_lanes='Compiler integration/literature execution not revived.',unreviewed_support='Support complements explicit; diagnostic formatting/transitive utilities outside necessary extents unreviewed. Go reflect implementation not retained/read: typeof helper calls TypeOf(x).String() and compares type names; excluded all three predicates, no reflect implementation claim.',unselected='All other peer files/directories outside selection unreviewed by round6.'),prior_runtime_evidence=dict(initial_run='run-crettoqb',initial_summary='Four original tests/three configs/24 actual generated executions; prior sanitizer link flags appended-O1, so sanitized execution effectivelyO1, not O0/O2. ASan definition checks/executions remain real.',correction='User/runtime-owner correction incorporated; prior immutable snapshots preserved. Corrected run-7m86apqr separately verified below; none are literal peer ports or round6 executions.',round5_proposals='NaN/negation and subnormal methods are in corrected separate runtime result; low-bit mask implementation not inferred.'),handoff=dict(owned_writes=['research/2026-10-memory/peer-readonly-evaluation-round6.md','research/2026-10-memory/peer-readonly-evaluation-round6.json','evidence/peer-readonly/evaluation-round6/'],prohibited_actions_executed=[],parent_campaign_earliest_completion_utc='2026-10-04T06:54:29Z',campaign_completion_claim=False,source_review_complete=True,proposal_implementation_pending=['P1','P2'],combined_selected_rounds2_3_4_5_6=dict(groups=336+len(units),distinct_complete_files=17,meaning='Selected heterogeneous documentary comparisons only, not campaign coverage/ports.'),merge_policy='No central edits. Add two whole-file extents at exact commit/hash; do not turn retrievals/helpers/source sites/skips/prior runtime runs into port credit.'))
writej(R/'research/2026-10-memory/peer-readonly-evaluation-round6.json',ledger)
print(json.dumps(counts,indent=2))
