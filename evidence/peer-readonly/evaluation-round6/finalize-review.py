"""Finalize source-only report, ledger and handoff."""
import datetime,hashlib,json,pathlib
R=pathlib.Path('.');E=R/'evidence/peer-readonly/evaluation-round6';P=R/'research/2026-10-memory/peer-readonly-evaluation-round6.json'
def readj(p):return json.loads(pathlib.Path(p).read_text())
def writej(p,x):pathlib.Path(p).write_text(json.dumps(x,indent=2)+'\n')
d=readj(P);checks=readj(E/'document-checks.json');assert checks['status']=='consistent'
for u in d['comparison_groups']:
 u['local_source_test_coverage']=[dict(coverage_id=k,**d['local_coverage_references'][k]) for k in u['local_coverage_ids']]
lm=readj(E/'local-manifest.json')
for key,path,spans,meaning in [
 ('near2^53-format','tests/runtime-numeric.py',[[25,26],[36,61],[64,75]],'Goldens at 2^53 and neighbor bit patterns feed formatter; no language +1/+2 boundary arithmetic.'),
 ('near2^53-label','tests/numeric-formatting.min',[[1,19]],'Record/Text formatting includes2^53-1, not2^53+1/+2 addition rounding.')]:
 m=next(x for x in lm if x['path']==path);d['local_coverage_references'][key]=dict(path=path,snapshot=m['snapshot'],sha256=m['sha256'],lines=spans,proves=meaning,verification='frozen_fixture_source_only')
d['proposed_original_regressions'][1]['local_coverage_ids']=['floats','near2^53-format','near2^53-label']
p1='''function observe(events: List<Integer>, id: Integer, result: Boolean): Boolean {
    events.add(id)
    return result
}
function decisive(events: List<Integer>, result: Boolean): Boolean {
    let temporary = Text(3) + "!"
    events.add(3)
    return result
}
let events: List<Integer> = []
print(observe(events, 1, true) && observe(events, 2, true) && false && observe(events, 9, true))
print(events.length)
for id in events { print(id) }
events = []
print(observe(events, 1, true) && observe(events, 2, true) && decisive(events, false) && observe(events, 9, true))
print(events.length)
for id in events { print(id) }
events = []
print(observe(events, 1, false) || observe(events, 2, false) || true || observe(events, 9, false))
print(events.length)
for id in events { print(id) }
events = []
print(observe(events, 1, false) || observe(events, 2, false) || decisive(events, true) || observe(events, 9, false))
print(events.length)
for id in events { print(id) }
'''
p2='''function add(left: Float, right: Float): Float {
    return left + right
}
let x = 9007199254740992.0
print(x + 1.0 == x)
print(x + 2.0 == 9007199254740994.0)
print((x + 2.0) - x)
print(add(x, 1.0) == x)
print(add(x, 2.0) == 9007199254740994.0)
print(add(x, 2.0) - x)
'''
for p,src,stdout in zip(d['proposed_original_regressions'],[p1,p2],['false\n2\n1\n2\nfalse\n3\n1\n2\n3\ntrue\n2\n1\n2\ntrue\n3\n1\n2\n3\n','true\ntrue\n2.0\ntrue\ntrue\n2.0\n']):
 p['proposed_minyar_source']=src;p['independent_expected_stdout']=stdout
d['prior_runtime_evidence']['corrected_run']=dict(results='research/2026-10-memory/evidence/runtime-peer-projections/run-7m86apqr/results.json',provenance='research/2026-10-memory/evidence/runtime-peer-projections/run-7m86apqr/provenance.json',correction='research/2026-10-memory/runtime-peer-optimization-correction.json',verified_durable_status='passed',methods=6,configurations=3,generated_executions=36,link_argv_last_flag_counts={'-O0':18,'-O2':18},scope='Saved documentary checks only:36 recorded outputs/status/effective generated link flags. Sanitized generated definitions ASan; runtime C nativeO2/sanitizedO1. No generated UBSan/LSan/full-suite or round6 execution claim.',snapshot_manifest='evidence/peer-readonly/evaluation-round6/corrected-runtime-manifest.json')
d['prior_runtime_evidence']['initial_summary']='run-crettoqb:four methods/three configurations/24 actual executions;16 native links O0/O2,8 sanitized generated links effectivelyO1. Historical individual argv absent; modes derived from archived runner/helper flag order. Real outputs/ASan evidence preserved.'
changes=[]
for m in readj(E/'local-manifest.json')+readj(E/'reference-manifest.json'):
 current=hashlib.sha256(pathlib.Path(m['path']).read_bytes()).hexdigest()
 if current!=m['sha256']:changes.append(dict(path=m['path'],frozen_sha256=m['sha256'],current_sha256=current,meaning='Concurrent lane/reference update observed; initial bytes preserved, not edited by round6. Correction retained separately.'))
d['concurrent_reference_changes']=changes
d['document_checks']=dict(path='evidence/peer-readonly/evaluation-round6/document-checks.json',status=checks['status'],checks=checks['check_count'],meaning='Independent documentary checks, not test executions/coverage.')
d['handoff']['completed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
d['handoff']['pending_projection_group_ids']=[u['id'] for u in d['comparison_groups'] if u['disposition'] in ['adopt_pending','adapt_pending']]
d['handoff']['incompatible_group_ids']=[u['id'] for u in d['comparison_groups'] if u['disposition']=='incompatible_as_written']
writej(P,d)
out=['# Read-only evaluation and type-identity peer review, round6','',
'Source review is complete for Go `test/convert.go` L1–46 and Zig `test/behavior/eval.zig` L1–1759. The retained raw bytes were hashed against immutable source provenance before review; no refetch. All selected lines, helpers, backend skips, comptime cases and dormant bodies were read. Zero selected lines remain unread. These round5 retrieval-only candidates receive semantic-review status here.',
'',
'**114 heterogeneous groups**: 110 Zig test blocks, 1 Zig module comptime block, 3 Go reflected-type predicates. Dispositions: **25 adapt pending, 1 adopt pending, 88 incompatible**. Zero exact peer units are credited already covered; related local fixtures have explicit limits. **203 Zig oracle-call source sites, 9 compile-error sites, 98 guards, 3 Go failure predicates** are attributed once. Wrapper/helper call sites are separate source sites, not extra dynamic assertion executions/ports.',
'',
'Two original narrow proposals remain unimplemented/unexecuted: ordered effects before a decisive Boolean literal/helper, and binary64 arithmetic rounding at 2^53. No tests, compiles, installations, commits, timings, subagents, production/test/build edits or central-manifest edits occurred. The campaign earliest completion remains **2026-10-04 06:54:29 UTC**; bounded-round completion does not complete the campaign.',
'',
'## Primary sources, attribution and immutable hashes','',
'The [source manifest](../../evidence/peer-readonly/evaluation-round6/source-manifest.json) retains raw bytes, immutable URLs and original retrieval provenance. Go source Copyright 2009 The Go Authors and BSD notice are preserved with the BSD-3-Clause repository license; Zig retains MIT/Expat with Copyright Zig contributors. Full licenses/conditions remain intact. Support snapshots are selective helper reviews, not whole-file test review.',
'',
'| Primary pinned source | SHA-256 | Bytes / physical lines |','| --- | --- | --- |']
for m in readj(E/'source-manifest.json'):
 out.append(f"| [{('Go ' if '/go/' in m['snapshot'] else 'Zig ')+m['upstream_path']}]({m['url']}) | `{m['sha256']}` | {m['bytes']} / {m['physical_lines']} |")
out += ['',f"Go commit: `{d['scope']['selected'][0]['commit']}`. Zig commit: `{d['scope']['selected'][1]['commit']}`.",'',
'## Findings and limits','',
'- Go’s filename/comment does not make this numeric conversion coverage: all checks compare reflected type names. f/g are never invoked and arithmetic values are unasserted. Minyar has no reflected named-derived-type contract.',
'- Type/layout/comptime contracts remain excluded: no generic type factory, type-valued field, optional, arbitrary-width Integer, raw/aligned pointer, sentinel or comptime evaluator is assumed. Constants are single literals.',
'- Runtime projections preserve specified values using current syntax, excluding peer phase/lowering semantics. Binary64 +1 at 2^53 transfers with explicit Float operands. f32 +1 at 2^24 and f128 at 2^113 do not.',
'- Identical effects or commutative sums prove counts/values, not order. P1 uses independent ordered IDs. Existing literal-order, row-snapshot and producer-once controls are excluded from new proposals.',
'- Repeated Zig rows are recursively initialized by-value arrays, compared structurally over all 16 cells. Minyar rows share mutable references, Bytes.slice copies, Text views share immutable backing. Matching values do not prove copy/lifetime equivalence.',
'- `container level const and var have unique addresses` checks p.x==S.c.x before/after S.v.x=2, without independently asserting post-mutation c.x==1 or v.x==2. The explicit equality oracle alone does not establish the title’s full independence claim.',
'- Runtimefalse L1407–1417 never reaches its assertion. L1448–1463 andL1465–1482 are unconditionally skipped. Bodies remain source-reviewed, with zero execution/pass credit.',
'- Pointer identity, discarded allocations and global memoization have no retained-owner/destructor oracle. The string memoization commentL615–626 says the specification guarantee is unsettled.',
'',
'## Correction to prior runtime evidence','',
'Immutable [run-crettoqb results](evidence/runtime-peer-projections/run-crettoqb/results.json) have 24 real executions: 16 native links at O0/O2 and 8 sanitized generated links effectively O1. The appended sanitizer-O1 overrode requested flags. Earlier O0/O2 sanitizer wording was too broad. Historical individual argv were absent; effective modes derive from archived runner/helper ordering. The [correction record](runtime-peer-optimization-correction.json) is separately retained; old snapshots/ledgers remain unchanged.',
'',
'Durable [run-7m86apqr results](evidence/runtime-peer-projections/run-7m86apqr/results.json) have status passed: 6 methods × 3 configurations × 2 generated link levels =36 executions. Documentary checks verify 18 last-O0 and 18 last-O2 actual link flags, saved successful outputs/status and sanitizer ASan definition counts. Native runtime C objects remain O2; sanitized runtime C objects O1. The [current runtime report](runtime-peer-projections.md) disclaims generated UBSan/LSan/full-suite validation. Added NaN relation/negation and source-subnormal methods concern round5; no low-mask implementation inferred. These are separate runtime-lane originals, not literal peer ports or round6 executions.',
'',
'Initial four-method fixture bytes remain frozen; correction/latest result/report have a separate [manifest](../../evidence/peer-readonly/evaluation-round6/corrected-runtime-manifest.json). Concurrent reference changes are recorded in JSON. No unrelated runtime audit/measurement is reinterpreted here.',
'',
'## Frozen local source coverage','',
'See [local manifest](../../evidence/peer-readonly/evaluation-round6/local-manifest.json). Spans establish inspected source assertions/expected bytes only, not a new pass or exact peer phase/type/copy coverage.',
'',
'| ID | Source/test spans | Property and limitation |','| --- | --- | --- |']
for k,m in d['local_coverage_references'].items():
 spans=', '.join(f'L{a}–{b}' for a,b in m['lines']);ep=''
 if 'expected_path' in m:ep='; expected '+m['expected_path']+' '+', '.join(f'L{a}–{b}' for a,b in m['expected_lines'])
 out.append(f"| {k} | `{m['path']}` {spans}{ep} | {m['proves'].replace(chr(124),chr(92)+chr(124))} |")
out += ['','## Complete semantic ledger','',
'Every selected unit below has manually authored outcomes and compatibility reasoning. The [JSON ledger](peer-readonly-evaluation-round6.json) retains exact source expressions, per-site dispositions, guard text/line, comptime lines, helper spans, failure alternatives and direct local coverage spans. A pending group projection does not hide excluded comptime/compileError/typed-width sites. No arbitrary prefixes are selected.','']
for u in d['comparison_groups']:
 out += [f"### {u['id']} — {u['name']}",'',f"[{u['path']} L{u['lines'][0]}–{u['lines'][1]}]({u['url']}). **{u['disposition']}**.",'',f"Expected: {u['upstream_expected']}",'',f"Minyar: {u['minyar_mapping']}",'']
 if u['source_assertion_sites']:
  out += ['| Exact source site | Disposition | Oracle |','| --- | --- | --- |']
  for s in u['source_assertion_sites']:
   expr=s['source'].replace('\n',' ').replace('|',r'\|')
   out.append(f"| L{s['line']}"+(f"–{s['end_line']}" if s['end_line']!=s['line'] else '')+f" | {s['disposition']} | `{expr}` |")
  out.append('')
 else:out += ['No value assertion: successful analysis/driver completion is the selected oracle.','']
 out += ['Related local source: '+'; '.join(m['coverage_id']+': '+m['path']+' '+', '.join(f"L{a}–{b}" for a,b in m['lines']) for m in u['local_source_test_coverage'])+'.','']
 if u['helper_spans']:out += ['Additional in-file helper/declaration extents: '+', '.join(f'L{a}–{b}' for a,b in u['helper_spans'])+'.','']
 if u['backend_skip_guards']:out += ['Skip guards: '+'; '.join(f"L{g['line']} `{g['source']}`" for g in u['backend_skip_guards'])+'.','']
 if u.get('terminal_failure_paths'):out += ['Failure alternatives: '+'; '.join(f"L{x['line']} `{x['source']}`" for x in u['terminal_failure_paths'])+'.','']
out += ['## Required helper contracts and remaining support extents','']
for h in d['support_helper_reviews']:
 out += [f"- [{h['path']}]({h['url']}), reviewed "+', '.join(f'L{a}–{b}' for a,b in h['reviewed_spans'])+': '+h['contract']+' Pending complement: '+', '.join(f'L{a}–{b}' for a,b in h['review_pending_spans'])+'.']
out += ['','External/nested selected-file functions all have explicit helper contracts in JSON, independently reconciled against every fn definition. Go typeof L13 calls reflect.TypeOf(x).String(); f/gL15–17 return0 but are never invoked; typeT/mapmL19–21 and B/b/xL24–28 are unasserted support. Go reflect implementation was not retained/read; no reflect internals review claimed. Zig needed structural-equality/zeroes/byte-equality contracts are explicit. Diagnostic formatting/transitive utility internals outside needed extents remain unreviewed.',
'',
'## Original proposals, implementation pending','']
for p in d['proposed_original_regressions']:
 out += [f"### {p['id']} — {p['name']}",'',p['gap'],'','Current-syntax program authored only in report/ledger, not compiled/executed:','','```minyar',p['proposed_minyar_source'].rstrip(),'```','','Exact independent expected stdout:','','```text',p['independent_expected_stdout'].rstrip(),'```','',p['independent_oracle'],'','Excluded peer contracts: '+', '.join(p['excluded_peer_contracts'])+'.','']
out += ['## Documentary checks and handoff','',
f"The independent audit has **{checks['check_count']} consistent documentary checks**: retained hashes/sizes/lines, complete selected extents, all oracle sites/guards, all fn helper contracts, support partitions, local spans, deduplicated prior paths, central bytes and saved corrected runtime argv/outputs. [Checks](../../evidence/peer-readonly/evaluation-round6/document-checks.json) are not test executions or correctness validation.",
'',
'Prior groups 32+66+120+118=336 span 15 distinct selected files; array.zig is deduplicated across rounds2/3. Adding 114/two gives **450 selected heterogeneous comparisons across17 distinct files**. This selected-report union is not campaign coverage, suite denominator, ports or passing validation.',
'',
'All 26 adopt/adapt groups and both proposals remain pending executable adaptation; 88 incompatible groups excluded. Zero selected review-pending lines; exact support complements and all other peer files/directories remain outside this round. No extra file selected: complete eval supplies distinct relevant contracts within the bounded selection.',
'',
'Restricted Rust remains excluded, not retried/bypassed. Round5 directory API failure preserved without retry. Stopped compiler-integration/literature lanes not revived. No new resource restriction and zero network calls this round. Active core/native experiments and dirty work were left to their owners.',
'',
'Only `research/2026-10-memory/peer-readonly-evaluation-round6.md/.json` and `evidence/peer-readonly/evaluation-round6/` authored. Central manifests unchanged. [Handoff](../../evidence/peer-readonly/evaluation-round6/handoff.json) retains IDs/counts/pending gaps and campaign boundary. Completion applies only to this bounded source round.']
(R/'research/2026-10-memory/peer-readonly-evaluation-round6.md').write_text('\n'.join(out)+'\n')
writej(E/'handoff.json',dict(schema='minyar.round6.handoff.v1',status='bounded_source_review_complete; documentary_consistent',counts=d['counts'],document_checks=checks['check_count'],source_review_remaining_selected_lines=0,scope=d['scope'],handoff=d['handoff'],prior_runtime_evidence=d['prior_runtime_evidence'],availability=d['availability'],concurrent_reference_changes=changes))
print('Report groups',len(d['comparison_groups']),'concurrent reference changes',len(changes))
