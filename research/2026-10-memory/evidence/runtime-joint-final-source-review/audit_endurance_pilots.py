"""Frozen pilot/calibration audit; pure Python, no execution of cohort code."""
import datetime,hashlib,json,re,shutil
from pathlib import Path
from audit_source import ROOT,OUT
from audit_round1 import FINAL,pin_runtime

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 b=ROOT/'research/2026-10-memory/evidence/runtime-joint-endurance/run-77p_xuej'
 d=json.loads((b/'results.json').read_text());p=json.loads((b/'preregister.json').read_text());assert d['status']=='passed' and p['revision']==4
 assert sha(b/'tests/memory-research-joint-endurance.c')==p['fixture_sha256']=='e6510c6da4e1ad54ff4a713e44fad7bf450cebcc6eae31ded39dc77a2547a47b'
 assert sha(b/'tests/memory-research-joint-endurance.py')==p['driver_sha256']=='55fc84b62ebe89376b2f635ef1df19f4bd5b8f26721729ac025b822cc6a9f36d'
 driver=(b/'tests/memory-research-joint-endurance.py').read_bytes();assert driver==(OUT/'endurance-preflight-inputs/memory-research-joint-endurance.py').read_bytes()
 old=(OUT/'endurance-preflight-inputs/memory-research-joint-endurance.c').read_text();assert (b/'tests/memory-research-joint-endurance.c').read_text()==old.replace('#define MINYAR_RC_TESTING 1\n#define memcpy observed_memcpy','#define MINYAR_RC_TESTING 1\n#undef memcpy\n#define memcpy observed_memcpy')
 pin_runtime(b,'runtime',FINAL)
 for path,h in d['source_hashes'].items():assert sha(b/'runtime'/Path(path).name)==h
 assert sha(ROOT/d['gates_record']['path'])==d['gates_record']['sha256']=='1b9e80d0e12a189880895240de8b59f2c6fe54b5c354c83ca24f18638a2d141d'
 builds={x['label']:x for x in d['builds']};assert len(builds)==3 and len(d['runs'])==4
 for name,row in builds.items():
  assert row['returncode']==0 and sha(b/name)==row['binary_sha256'] and '-DNDEBUG' not in row['command']
  macros=(b/(name+'-macros.txt')).read_text()
  for macro,val in [('MINYAR_SYSTEM_HEAP','1'),('MINYAR_RC_TESTING','1'),('MINYAR_RC_POLL_BUDGET','32')]:assert re.search(r'^#define '+macro+' '+val+'$',macros,re.M)
  if name=='sanitize':assert '-O1' in row['command'] and '-fsanitize=address,undefined' in row['command']
  else:assert '-O2' in row['command']
  assert ('-DMINYAR_RESEARCH_HIDE_PREFIX_COPY=1' in row['command'])==(name=='observer-omission')
 rows=[]
 for row in d['runs']:
  label=row['label'];binary=Path(row['command'][2]);assert binary.parent==b and sha(binary)==row['binary_sha256'] and row['binary_hash_unchanged']
  stderr=(b/row['stderr']).read_text();summaries=[json.loads(x) for x in (b/row['summaries']).read_text().splitlines()];assert summaries[-1]==row['latest_summary']
  rss=int(re.search(r'(\d+)\s+maximum resident set size',stderr).group(1));assert rss==row['completed_peak_RSS_bytes']<=128*1024*1024
  monitors=[json.loads(x) for x in (b/row['monitor']).read_text().splitlines()];assert monitors and all(x['sampled_rss_bytes']<=128*1024*1024 and x['native_pid']==str(row['native_pid']) for x in monitors)
  if label.endswith('calibration'):
   assert row['returncode']==90 and row['status']=='expected calibration rejection'
   ring=[json.loads(x) for x in stderr.splitlines() if x.startswith('{')];end=1 if label.startswith('observer') else 512
   assert ring[-1]['epoch']==end and ring[-1]['debt']==0 and ring[-1]['length']==(2 if end==1 else 31)
   assert ('observed_prefix_copies ==' if end==1 else 'bits == expected') in stderr.splitlines()[0]
   assert len(ring)==(2 if end==1 else 64)
   rows.append({'label':label,'exit':90,'calibration_epoch':end,'ring_descriptors':len(ring),'status':'accepted intended oracle rejection, not runtime red'})
  else:
   s=summaries[-1];assert row['returncode']==0 and s['final']==1 and s['elapsed_native_seconds']>=row['duration_native_seconds']
   n=s['epochs'];debt=sum(e%17==0 for e in range(n));empty=sum(e%17!=0 and e%6==0 for e in range(n))
   assert s['pending_debt_fallbacks']==debt and s['eligible_scalar']==n-debt and s['eligible_empty']==empty and s['observed_nonempty_prefix_copies']==n-debt-empty
   assert s['recoveries']==n//128+1 and [s[k] for k in ['certified_ascii_joins','unknown_ascii_joins','unicode_joins']]==[sum(e%3==i for e in range(n)) for i in range(3)]
   assert s['seed']==int('4a01',16) and s['completed_epoch_requested_sample_max']==0
   rows.append({'label':label,'elapsed_native_seconds':s['elapsed_native_seconds'],'elapsed_observer_seconds':row['observer_elapsed_seconds'],'epochs':n,'recoveries':s['recoveries'],'completed_peak_RSS_bytes':rss,'total_process_cpu_seconds':s['total_process_cpu_seconds'],'counts_independently_rederived':True,'status':'accepted short pilot'})
 for pth in b.rglob('*'):
  if pth.is_file() and pth.suffix in ['.c','.h','.py','.json','.jsonl','.log','.txt']:
   target=OUT/'endurance-pilot-inputs'/pth.relative_to(b);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(pth,target)
 failed=ROOT/'research/2026-10-memory/evidence/runtime-joint-endurance/run-p0prt2oc/results.json';prior=json.loads(failed.read_text());assert prior['status']=='failed' and not prior['runs'] and prior['builds'][0]['returncode']==1 and 'macro redefined' in prior['builds'][0]['stderr'];shutil.copyfile(failed,OUT/'endurance-pilot-inputs/preexecution-p0prt2oc-results.json')
 out={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'result_sha256':sha(b/'results.json'),'preregister_sha256':sha(b/'preregister.json'),'fixture_sha256':p['fixture_sha256'],'driver_sha256':p['driver_sha256'],'native_binary_sha256':builds['native']['binary_sha256'],'runs':rows,'recommendation':'release exact preregistered native1800s cohort using this pilot native binary after root authorization; no prelaunch blocker','conditions':['unchanged pilot fixture/driver/runtime/nativebinary identities enforced by driver','same 180CPU/1850wall/16MiBfile/120progress limits and defaultASanquarantine policy; no relaxed thresholds','correctness/accounted observer scope only,5percentbatchtarget not wholeprocess guarantee','endepoch0requested sample is not construction/transient maximum; periodic/completedRSS not continuouscap','separate native and Python monotonic origins; do not subtract cross-clock values','first unexpected failure preserved, no automatic retry'],'native_execution_by_reviewer':False,'long_result':'pending not inferred'}
 (OUT/'endurance-pilot-verification.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
