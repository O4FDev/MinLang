"""Independent documentary accounting; never imports/runs peer or local test code."""
from pathlib import Path
from fractions import Fraction
import json,re,hashlib,collections,datetime
B=Path('evidence/peer-readonly/values-round5'); L=Path('research/2026-10-memory/peer-readonly-values-round5.json')
d=json.loads(L.read_text());raw=json.loads((B/'source-manifest.json').read_text())
reference_sets=[json.loads((B/'initial-references.json').read_text())['references'],json.loads((B/'local-manifest.json').read_text())]
checks=[]
def check(name,condition,detail=None):
 checks.append({'name':name,'consistent':bool(condition),'detail':detail});
 if not condition:raise ValueError(name)
for r in raw+[x for rs in reference_sets for x in rs]:
 data=Path(r['snapshot']).read_bytes();check('hash:'+r['snapshot'],hashlib.sha256(data).hexdigest()==r['sha256'])
 check('lines:'+r['snapshot'],len(data.splitlines())==r['physical_lines'])
index={r['path']:r for r in raw}; units=d['comparison_groups']
check('unique_unit_ids',len(set(u['id'] for u in units))==len(units))
check('disposition_counts',dict(collections.Counter(u['disposition'] for u in units))==d['counts']['dispositions'])
check('selected_file_count',len(d['scope']['selected'])==5)
check('selected_line_total',sum(len(Path(r['snapshot']).read_bytes().splitlines()) for r in d['scope']['selected'])==587)
for u in units:
 source=Path(index[u['path']]['snapshot']).read_text().splitlines();a,b=u['lines']
 check('unit_extent:'+u['id'],1<=a<=b<=len(source))
 check('unit_identity:'+u['id'],u['sha256']==index[u['path']]['sha256'] and u['commit']==index[u['path']]['commit'])
 for a,b in u['helper_spans']+u.get('call_spans',[]):check('helper_extent:'+u['id']+':'+str(a),1<=a<=b<=len(source))
 for site in u['source_assertion_sites']+u['backend_skip_guards']:
  check('source_site:'+u['id']+':'+str(site['line']),source[site['line']-1]==site['source'])
# Independently discover all explicit source sites, then require attribution exactly once.
p='test/floatcmp.go'; source=Path(index[p]['snapshot']).read_text().splitlines()
expected_rows=[n for n,l in enumerate(source,1) if re.match(r'\s*floatTest\{',l)]
actual=[a['line'] for u in units if u['path']==p for a in u['source_assertion_sites']]
check('all54_NaN_table_sites_once',len(expected_rows)==54 and sorted(actual)==expected_rows and len(actual)==len(set(actual)))
p='test/float_lit.go';source=Path(index[p]['snapshot']).read_text().splitlines()
expected_calls=[n for n,l in enumerate(source,1) if re.match(r'\s*if !close\(',l)]
actual=[a['line'] for u in units if u['path']==p for a in u['source_assertion_sites']]
check('all45_literal_call_sites_once',len(expected_calls)==45 and sorted(actual)==expected_calls and len(actual)==len(set(actual)))
# Cross-check lexeme grammar independently using the documented tokenizer conditions.
valid=[u for u in units if u['path']==p and not u['name'].startswith('+') and re.fullmatch(r'-?[0-9]+\.[0-9]+([Ee][+-]?[0-9]+)?',u['name'])]
check('8_supported_37_incompatible_lexemes',len(valid)==8 and sum(u['disposition']=='incompatible_as_written' for u in units if u['path']==p)==37)
p='test/behavior/cast_int.zig';source=Path(index[p]['snapshot']).read_text().splitlines()
expected_assert=[n for n,l in enumerate(source,1) if re.match(r'\s*try expect(?:Equal)?\(',l)]
actual=[a['line'] for u in units if u['path']==p for a in u['source_assertion_sites']]
check('all51_Zig_assertion_sites_once',len(expected_assert)==51 and sorted(actual)==expected_assert and len(actual)==len(set(actual)))
named=[n for n,l in enumerate(source,1) if re.match(r'test "',l)]
check('all6_Zig_named_tests_represented',len(named)==6 and sorted(set(u['named_test_span'][0] for u in units if u['path']==p))==named)
expected_skip=[n for n,l in enumerate(source,1) if 'return error.SkipZigTest' in l]
actual_skip=set(g['line'] for u in units if u['path']==p for g in u['backend_skip_guards'])
check('all19_Zig_guard_sites_represented',len(expected_skip)==19 and actual_skip==set(expected_skip))
check('no_comptime_test_phase_in_selected_Zig',not any('comptime' in l for l in source))
for p in ['test/Interpreter/conversions.swift','test/Interpreter/array_of_optional.swift']:
 source=Path(index[p]['snapshot']).read_text().splitlines()
 expected=[n for n,l in enumerate(source,1) if l.startswith('// CHECK:')]
 actual=[a['line'] for u in units if u['path']==p for a in u['source_assertion_sites']]
 check('all_Swift_CHECKs_once:'+p,sorted(actual)==expected and len(actual)==len(set(actual)))
 check('Swift_executable_requirement:'+p,'// REQUIRES: executable_test' in source)
# Original numeric expectations are exact documentary arithmetic, not observed program output.
w=int('1234567812345678',16)
low=[w%2**21,w%2**10,w%2**7]
check('independent_low_bits_by_modulus',low==[1332856,632,120])
check('signed8_mathematical_controls',(-5)%256==251 and 251-256==-5)
threshold=Fraction(1,2**1075)
below=Fraction(24703282292062327,10**340)
above=Fraction(24703282292062328,10**340)
check('exact_decimal_underflow_bracket',below<threshold<above)
check('negative_subnormal_signed64_bits',((1<<63)+1)-(1<<64)==-9223372036854775807)
# All source/helper pending spans must be explicit and disjoint from credited read spans.
for s in d['support_helper_reviews']:
 total=index[s['path']]['physical_lines'];covered=set(n for a,b in s['read_spans'] for n in range(a,b+1));pending=set(n for a,b in s['review_pending_spans'] for n in range(a,b+1))
 check('support_read_pending_partition:'+s['id'],not (covered&pending) and covered|pending==set(range(1,total+1)))
for s in d['scope']['selected']:check('complete_selected_extent:'+s['path'],s['reviewed_spans']==[[1,s['physical_lines']]] and not s['review_pending_spans'])
for s in d['availability']['unselected_discovery_candidates']:check('candidate_full_pending:'+s['path'],s['reviewed_spans']==[] and s['review_pending_spans']==[[1,s['physical_lines']]])
# Compare selected paths against old immutable review records, never mutate central ledgers.
central=json.loads((B/'local/research/2026-10-memory/peers-review-ledger.json').read_text())
previous={(s['language'],s['commit'],s['path']) for s in central['reviewed_source_entries']}
for old in ['peer-readonly-go-zig-round2.json','peer-readonly-go-zig-round3.json','peer-readonly-strings-round4.json']:
 obj=json.loads((B/'local/research/2026-10-memory'/old).read_text())
 for u in obj.get('units',obj.get('comparison_groups',[])):
  commit=u.get('commit')
  if commit is None:
   commit='56ebf80e57db9f61981fc0636fc6419dc6f68eda' if u['language']=='go' else '3db960767d12b6214bcf43f1966a037c7a586a12'
  previous.add((u['language'],commit,u['path']))
for s in d['scope']['selected']:check('not_previously_reviewed:'+s['path'],(s['language'],s['commit'],s['path']) not in previous)
# Fixture/reference live changes are concurrent observations; review stays tied to frozen bytes.
current=[]
for rs in reference_sets:
 for r in rs:
  data=Path(r['path']).read_bytes() if Path(r['path']).exists() else None
  now=None if data is None else hashlib.sha256(data).hexdigest()
  current.append({'path':r['path'],'snapshot_sha256':r['sha256'],'current_sha256':now,'unchanged':now==r['sha256'],'meaning':'Observed only; this research lane never writes this path.'})
protected=['research/2026-10-memory/peers.json','research/2026-10-memory/peers-review-ledger.json']
for p in protected:check('central_ledger_preserved:'+p,all(r['unchanged'] for r in current if r['path']==p))
result={'schema':'minyar.peer_readonly_values.document_checks.v1','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'consistent','method':'Separate document script: source-site attribution, raw byte hashes/line counts, immutable extent partitions and exact integer rational arithmetic. No compiler, peer program, repository test, installation or timing execution. No imported author-script functions.','counts_independently_derived':{'selected_files':5,'selected_physical_lines':587,'Go_NaN_rows':len(expected_rows),'Go_literal_calls':len(expected_calls),'Zig_named_tests':len(named),'Zig_assertion_sites':len(expected_assert),'Zig_guard_sites':len(expected_skip),'units':len(units),'source_license_support_candidate_hashes':len(raw),'local_reference_snapshot_hashes':sum(len(r) for r in reference_sets),'pending_adopt_adapt':sum(u['disposition'] in ['adopt_pending','adapt_pending'] for u in units)},'numeric_documentary_derivations':{'low_bits_modulus':low,'signed8':{'raw251':251,'signed':-5},'underflow_bracket':{'threshold':'2^-1075','below':'2.4703282292062327e-324','above':'2.4703282292062328e-324','method':'Exact Fraction integer ratios; no floating-point execution/oracle from Minyar'}},'checks':checks,'live_reference_observations':current,'concurrent_reference_changes':[r for r in current if not r['unchanged']]}
(B/'document-checks.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':result['status'],'counts':result['counts_independently_derived'],'checks':len(checks),'concurrent_changes':result['concurrent_reference_changes']},indent=2))
