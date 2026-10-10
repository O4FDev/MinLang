"""Saved pressure/raw-bit/projection audit only; no compiler or native execution."""
import datetime, hashlib, json, re, shutil
from pathlib import Path
from audit_source import ROOT, OUT, apply
from audit_round1 import BEFORE, FINAL, pin_runtime, optimization
B=ROOT/'research/2026-10-memory/evidence/runtime-joint-final/run-xc_5g2zj/gates'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 report={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'gates':[]}
 for n in ['run-5al7elms','run-5c_mqfda','run-y7m0xz6y']:
  b=B/n;d=json.loads((b/'results.json').read_text());assert d['status']=='passed'
  index=json.loads((b/'archive-index.json').read_text());retained=0;omitted=[]
  for row in index['files']:
   p=b/row['path']
   if row['archived']:
    assert p.is_file() and sha(p)==row['sha256'] and p.stat().st_size==row['bytes'];retained+=1
    if p.suffix in ['.h','.c','.py','.ll','.patch']:
     out=OUT/'round3-inputs'/n/row['path'];out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,out)
   else:omitted.append(row['path'])
  rec={'run':n,'result_sha256':sha(b/'results.json'),'retained_index_files_verified':retained,'omitted_archive_entries':omitted}
  checks={x['label']:x for x in d['checks']};assert len(checks)==len(d['checks'])
  if n=='run-5al7elms':
   pin_runtime(b,'original/runtime',BEFORE)
   for variant in ['baseline','candidate']:
    uninstrumented=b/'original/runtime' if variant=='baseline' else ROOT/'research/2026-10-memory/evidence/runtime-joint-final/run-xc_5g2zj/final/runtime'
    for name,patch in [('minyar_collections.h','list-observer.patch'),('minyar_rc.h','rc-observer.patch'),('minyar_bounded_rc.h','poll-observer.patch')]:
     assert apply((uninstrumented/name).read_bytes(),(b/variant/patch).read_text())==(b/variant/'runtime'/name).read_bytes()
    for name in ['minyar_runtime.c','minyar_heap.h','minyar_pool.h','minyar_bytes.h','minyar_native.h','minyar_numbers.h','minyar_stack_frames.h','minyar_default_runtime.c']:
     assert (uninstrumented/name).read_bytes()==(b/variant/'runtime'/name).read_bytes()
   success=0;traps=0
   for row in d['checks']:
    label=row['label']
    if not label.startswith('candidate-'):continue
    old=checks[label.replace('candidate-','baseline-',1)]
    assert row['returncode']==old['returncode'] and not row['timed_out']
    assert row['peak_rss_bytes']<=128*1024*1024
    parsed=[json.loads(x) for x in row['stdout'].splitlines() if x.startswith('{')]
    assert parsed==row['observations']
    if '-errors-' in label:
     assert row['returncode']==1 and row['observations']==old['observations'];traps+=1
     diag=[x for x in row['stderr'].splitlines() if x.startswith('Minyar stopped:')]
     assert diag==[x for x in old['stderr'].splitlines() if x.startswith('Minyar stopped:')]
    else:
     success+=1;a=old['observations'];z=row['observations'];assert a[1:]==z[1:]
     requests=[x for x in z if x['kind']=='request'];assert len(requests)==9
     if label.endswith('-idle'):
      ignore={'add_entries','copy_entries','copy_bytes'}
      assert {k:v for k,v in a[0].items() if k not in ignore}=={k:v for k,v in z[0].items() if k not in ignore}
      assert z[0]['guard_pending']==0 and z[0]['add_entries']==1 and z[0]['copy_entries']==1
      assert z[0]['copy_bytes']==(127 if '-K1-' in label else 511)*8
     else:assert a==z and z[0]['guard_pending']>0
   builds=[x for x in d['checks'] if x['label'].startswith('compile-')]
   assert len(builds)==16 and success==18 and traps==6 and len(d['checks'])==65
   assert all('-DNDEBUG' not in x['command'] and optimization(x['command'])==('-O1' if 'san1' in x['label'] else '-O2') for x in builds)
   rec.update(gate='pressure/admission/errors',builds=16,executions=48,success_control_pairs=18,fatal_control_pairs=6,journal_records=65,source_identity='c4/01ae baseline and d919/3b final before exact observer patches',status='accepted bounded saved comparisons; no universal admission theorem')
  elif n=='run-5c_mqfda':
   pin_runtime(b,'baseline/runtime',BEFORE);pin_runtime(b,'candidate/runtime',FINAL)
   for p in (b/'baseline/runtime').iterdir():
    if p.name not in BEFORE:assert p.read_bytes()==(b/'candidate/runtime'/p.name).read_bytes()
   executions=[x for x in d['checks'] if x['label']!='toolchain' and not x['label'].startswith('compile-')]
   assert len(executions)==6 and len(d['checks'])==13
   for x in executions:
    assert x['returncode']==0 and x['stdout']=='10 raw words, mutation independence, empty backed scalar, empty and immortal/null reference controls recovered\n' and not x['timed_out'] and x['peak_rss_bytes']<=128*1024*1024
   for x in d['checks']:
    if x['label'].startswith('compile-'):assert '-DNDEBUG' not in x['command'] and optimization(x['command'])==('-O1' if 'san1' in x['label'] else '-O2')
   rec.update(gate='raw-bit ownership',builds=6,executions=6,journal_records=13,raw_words=10,status='accepted saved scalar bit/alias/recovery controls')
  else:
   pin_runtime(b,'runtime',FINAL)
   sizes=list(range(18))+[31,32,33];lines=[]
   for size in sizes:lines+=['true','false',str(size),str(size),'false']+['false','true']*size
   lines+=['true','false','false','true','3','7','0','true'];expected='\n'.join(lines)+'\n'
   assert len(lines)==611 and hashlib.sha256(expected.encode()).hexdigest()=='019ff24347f479b271b9d2f145338bfd574d355a0b52eda1b5bb75e812c06a8c'
   assert len(d['checks'])==6 and d['summary']['generated_executions']==6
   paths=[]
   for cfg in d['coverage']:
    assert cfg['tests_run']==1 and len(cfg['observed'])==1;o=cfg['observed'][0]
    assert o['expected_stdout']==expected and o['effective_optimizations']==['O0','O2']
    commands=o['commands'];links=[x for x in commands if x['kind']=='link'];execs=[x for x in commands if x['kind']=='execute']
    assert len(links)==len(execs)==2
    for x in execs:assert x['returncode']==0 and x['stdout_sha256']==hashlib.sha256(expected.encode()).hexdigest()
    for x in links:
     assert x['returncode']==0;ir=x['linked_llvm'];p=Path(ir['snapshot']);rel=Path(p.parent.name)/p.name;q=b/rel
     assert p.parent.name==cfg['configuration']+'-llvm' and sha(q)==ir['sha256'];paths.append(str(rel))
     headers=re.findall(r'^define[^\n]*',q.read_text(),re.M);asan=sum(bool(re.search(r'\)\s+[^\n]*\bsanitize_address\b',h)) for h in headers)
     assert len(headers)==ir['definitions']==13 and asan==ir['asan_definitions']==(13 if 'sanitize' in cfg['configuration'] else 0)
     if 'sanitize' in cfg['configuration']:assert '-fsanitize=address,undefined' in x['argv']
   assert len(set(paths))==6
   rec.update(gate='NUL equality projection',methods=1,configurations=3,generated_executions=6,before_link_immutable_IRs=6,output_lines=611,mismatch_positions=sum(sizes),ASan_definitions_per_sanitized_IR=13,status='accepted saved method; generated ASan only, runtime C ASan/UBSan')
  report['gates'].append(rec)
 (OUT/'round3-gate-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
