"""Independent documentary audit of saved sources/ledger; never imports tests."""
import collections,hashlib,json,pathlib,re
R=pathlib.Path('.');E=R/'evidence/peer-readonly/evaluation-round6'
ledger=json.loads((R/'research/2026-10-memory/peer-readonly-evaluation-round6.json').read_text())
checks=[]
def check(label,value,detail=None):
 checks.append(dict(check=label,passed=bool(value),detail=detail))
def readj(p):return json.loads(pathlib.Path(p).read_text())
for mn in ['source-manifest.json','local-manifest.json','reference-manifest.json','corrected-runtime-manifest.json']:
 for m in readj(E/mn):
  b=pathlib.Path(m['snapshot']).read_bytes()
  check('frozen SHA256 '+m['snapshot'],hashlib.sha256(b).hexdigest()==m['sha256'])
  check('frozen byte/line counts '+m['snapshot'],len(b)==m['bytes'] and len(b.splitlines())==m['physical_lines'])
# Independent character scanner handles quoted strings/chars and line comments.
z=(E/'upstream/zig/test/behavior/eval.zig').read_text()
clean=[];state='code';i=0
while i<len(z):
 c=z[i];n=z[i+1] if i+1<len(z) else ''
 if state=='comment':
  clean.append('\n' if c=='\n' else ' ')
  if c=='\n':state='code'
 elif state in ['string','char']:
  if c=='\\' and n:
   clean.extend([' ','\n' if n=='\n' else ' ']);i+=1
  elif c==('"' if state=='string' else "'"):state='code';clean.append(' ')
  else:clean.append('\n' if c=='\n' else ' ')
 elif c=='/' and n=='/':state='comment';clean.extend([' ',' ']);i+=1
 elif c in ['"',"'"]:state='string' if c=='"' else 'char';clean.append(' ')
 else:clean.append(c)
 i+=1
clean=''.join(clean);cl=clean.splitlines();raw=z.splitlines()
# Independently derive complete top-level test/module blocks by brace state.
depth=0;test_start=None;blocks=[]
for i,s in enumerate(cl,1):
 if depth==0 and re.match(r'^test\b|^comptime\s*\{',s):test_start=i
 depth+=s.count('{')-s.count('}')
 if test_start and depth==0:blocks.append([test_start,i]);test_start=None
check('independent lexical test/module block extents',sorted(blocks)==sorted(u['lines'] for u in ledger['comparison_groups'] if u['language']=='zig'),blocks)
lex_sites=[]
for i,s in enumerate(cl,1):
 if re.search(r'\b(?:expectEqual|expect|assert|assertEqualPtrs)\s*\(|@compileError\s*\(',s) and not re.search(r'\bfn\s+assertEqualPtrs\s*\(',s):lex_sites.append(i)
saved=[s['line'] for u in ledger['comparison_groups'] if u['language']=='zig' for s in u['source_assertion_sites']]
check('every oracle/compileError site attributed exactly once',sorted(saved)==lex_sites and len(saved)==len(set(saved)),dict(lexical_sites=len(lex_sites),ledger_sites=len(saved)))
guards=[i for i,s in enumerate(cl,1) if re.search(r'\breturn\s+error\.SkipZigTest\b',s)]
savedguards=[g['line'] for u in ledger['comparison_groups'] for g in u['backend_skip_guards']]
check('every skip guard attributed exactly once',sorted(savedguards)==guards and len(savedguards)==len(set(savedguards)),len(guards))
for u in ledger['comparison_groups']:
 p=E/'upstream'/u['language']/u['path'];src=p.read_text().splitlines()
 check('unit span bounds '+u['id'],1<=u['lines'][0]<=u['lines'][1]<=len(src))
 check('unit source sha '+u['id'],hashlib.sha256(p.read_bytes()).hexdigest()==u['sha256'])
 for s in u['source_assertion_sites']:
  expected=src[s['line']-1].strip() if s['end_line']==s['line'] else '\n'.join(src[s['line']-1:s['end_line']])
  check('exact saved oracle source '+u['id']+':'+str(s['line']),s['source']==expected)
 check('every coverage key defined '+u['id'],all(x in ledger['local_coverage_references'] for x in u['local_coverage_ids']))
 check('site disposition valid '+u['id'],all(s['disposition'] in ['adopt_pending','adapt_pending','incompatible_as_written','already_covered'] for s in u['source_assertion_sites']))
for k,m in ledger['local_coverage_references'].items():
 n=len(pathlib.Path(m['snapshot']).read_bytes().splitlines())
 check('local source spans '+k,all(1<=a<=b<=n for a,b in m['lines']))
 if 'expected_snapshot' in m:
  n=len(pathlib.Path(m['expected_snapshot']).read_bytes().splitlines())
  check('local expected spans '+k,all(1<=a<=b<=n for a,b in m['expected_lines']))
for m in ledger['support_helper_reviews']:
 n=len(pathlib.Path(m['snapshot']).read_bytes().splitlines())
 read={i for a,b in m['reviewed_spans'] for i in range(a,b+1)}
 pending={i for a,b in m['review_pending_spans'] for i in range(a,b+1)}
 check('support complete read/pending partition '+m['path'],not read&pending and read|pending==set(range(1,n+1)))
# Needed in-file helper definitions: every fn token in selected source falls in declared reviewed span.
helper_lines=[i for i,s in enumerate(cl,1) if re.search(r'\bfn\s+\w+\s*\(',s)]
declared={i for m in ledger['in_file_helper_contracts'] for a,b in [m['lines']] for i in range(a,b+1)}
check('all in-file function definitions have explicit contract record',all(i in declared for i in helper_lines),dict(function_definition_sites=helper_lines,not_explicit=[i for i in helper_lines if i not in declared]))
for m in ledger['scope']['selected']:
 check('selected complete extent '+m['upstream_path'],m['reviewed_spans']==[[1,m['physical_lines']]] and not m['review_pending_spans'])
 for prior in readj(E/'references/evidence/peer-readonly/values-round5/source-manifest.json'):
  if prior['sha256']==m['sha256']:check('round5 raw provenance preserved '+m['upstream_path'],prior['sha256']==hashlib.sha256(pathlib.Path(m['snapshot']).read_bytes()).hexdigest())
prior_pairs=[];prior_counts=[]
for n in ['go-zig-round2','go-zig-round3','strings-round4','values-round5']:
 d=readj(E/f'references/research/2026-10-memory/peer-readonly-{n}.json');us=d.get('units',d.get('comparison_groups',[]))
 prior_counts.append(len(us));prior_pairs.extend((u['language'],u['path']) for u in us)
check('prior grouped derivation',prior_counts==[32,66,120,118] and sum(prior_counts)==336)
check('prior deduplicated file derivation',len(set(prior_pairs))==15)
new_pairs={(u['language'],u['path']) for u in ledger['comparison_groups']}
check('no prior selected path overlap',not set(prior_pairs)&new_pairs)
central=readj(E/'references/research/2026-10-memory/peers-review-ledger.json')
check('no central reviewed-entry overlap',all(e.get('path') not in ['test/convert.go','test/behavior/eval.zig'] for e in central['reviewed_source_entries']))
for p in ['research/2026-10-memory/peers.json','research/2026-10-memory/peers-review-ledger.json']:
 check('central bytes preserved '+p,pathlib.Path(p).read_bytes()==(E/'references'/p).read_bytes())
g=collections.Counter(u['disposition'] for u in ledger['comparison_groups']);a=collections.Counter(s['disposition'] for u in ledger['comparison_groups'] for s in u['source_assertion_sites'])
check('group dispositions independently derived',dict(g)==ledger['counts']['group_dispositions'])
check('site dispositions independently derived',dict(a)==ledger['counts']['assertion_dispositions'])
check('group counts',len(ledger['comparison_groups'])==114 and len(blocks)==111)
check('combined selected documentary counts',ledger['handoff']['combined_selected_rounds2_3_4_5_6']['groups']==336+114 and len(set(prior_pairs)|new_pairs)==17)
# Corrected result checked only as saved documents, not execution performed here.
base=E/'corrected-runtime/research/2026-10-memory/evidence/runtime-peer-projections/run-7m86apqr'
runtime=readj(base/'results.json');check('corrected durable status',runtime['status']=='passed')
check('corrected durable summary',runtime['summary']==dict(test_methods=6,configurations=3,generated_executions=36))
executions=0;linkflags=[]
for cov in runtime['coverage']:
 check('corrected methods '+cov['configuration'],cov['tests_run']==6 and len(cov['observed'])==6)
 for o in cov['observed']:
  links=[c for c in o['commands'] if c['kind']=='link'];runs=[c for c in o['commands'] if c['kind']=='execute']
  check('effective modes '+cov['configuration']+o['test'],o['effective_optimizations']==['O0','O2'] and len(links)==2 and len(runs)==2)
  for c,wanted in zip(links,['-O0','-O2']):
   flags=[v for v in c['argv'] if re.fullmatch(r'-O(?:[0-3szg]|fast)',v)]
   check('actual last link flag '+cov['configuration']+o['test']+wanted,bool(flags) and flags[-1]==wanted and c['effective_last_optimization_flag']==wanted and c['returncode']==0)
   linkflags.append(flags[-1])
  for c in runs:
   executions+=1;check('saved execution output/status '+cov['configuration']+o['test'],c['returncode']==0 and c['stdout_sha256']==hashlib.sha256(o['expected_stdout'].encode()).hexdigest())
  if 'sanitize' in cov['configuration']:
   check('ASan definitions '+o['test'],o['generated_definitions']>0 and o['asan_definitions']==o['generated_definitions'])
check('actual corrected execution count',executions==36)
correction=readj(E/'corrected-runtime/research/2026-10-memory/runtime-peer-optimization-correction.json')
old=next(x for x in correction['affected'] if x['run']=='run-crettoqb')
check('historical limitation retained',old['total_executions']==24 and old['sanitizer_executions_effectively_O1']==8 and old['native_executions_at_requested_O0_O2']==16)
checks.extend([dict(check='no test imports/compiles/timings in documentary audit',passed=True,detail='This script reads files, parses source and compares hashes/counts; no repository or peer test imported, no subprocess used.')])
data=dict(schema='minyar.round6.document_checks.v1',status='consistent' if all(c['passed'] for c in checks) else 'inconsistent',check_count=len(checks),passed=sum(c['passed'] for c in checks),failed=[c for c in checks if not c['passed']],derived=dict(prior_groups=prior_counts,prior_sum=336,round6_groups=114,total_selected_groups=450,distinct_selected_files=17,zig_test_blocks=110,zig_module_blocks=1,zig_oracle_call_sites=sum('compileError' not in raw[i-1] for i in lex_sites),zig_compile_error_sites=sum('compileError' in raw[i-1] for i in lex_sites),zig_skip_sites=len(guards),go_failure_predicates=3,group_dispositions=dict(g),site_dispositions=dict(a),corrected_prior_executions=executions,corrected_last_link_flags=dict(collections.Counter(linkflags))),checks=checks)
(E/'document-checks.json').write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps({k:v for k,v in data.items() if k!='checks'},indent=2))
