"""Pure saved loop/archive/consolidation source and oracle audit."""
import datetime,hashlib,json,re,shutil
from pathlib import Path
from audit_source import ROOT,OUT,apply
from audit_round1 import FINAL,pin_runtime
B=ROOT/'research/2026-10-memory/evidence/runtime-joint-final/run-xc_5g2zj'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def retain(p):
 target=OUT/'round4-inputs'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
def main():
 out={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'gates':[]}
 consolidated=ROOT/'research/2026-10-memory/runtime-joint-final-results.json';d=json.loads(consolidated.read_text());assert d['status']=='passed'
 for row in d['groups']+d['supplemental_and_provenance']:
  p=ROOT/row['path'];assert sha(p)==row['sha256'];retain(p)
 for path,h in d['source_hashes'].items():assert sha(ROOT/path)==h
 out['consolidated']={'sha256':sha(consolidated),'groups':12,'supplemental_provenance_records':3,'all_hashes_match':True};retain(consolidated)
 b=B/'gates/run-2zao0jio';d=json.loads((b/'results.json').read_text());assert d['status']=='passed';pin_runtime(b,'runtime',FINAL)
 idx=json.loads((b/'archive-index.json').read_text());retained=0
 for row in idx['files']:
  if row['archived']:
   p=b/row['path'];assert sha(p)==row['sha256'] and p.stat().st_size==row['bytes'];retain(p);retained+=1
 captured=0;rebound=0;trace=0;values=[4,7,9,13]
 for pos in range(3):captured=captured*100+values[pos];values[pos]+=100;rebound+=900+pos;trace=trace*10+pos+1
 expected='\n'.join(map(str,[captured,3,3,1,rebound,trace,9,*values]))+'\n';h=hashlib.sha256(expected.encode()).hexdigest();assert h=='e1c35bcae02ab58eb72a6e2f17069b30975c651a69958ea5d44440ddb18791fe'
 paths=[]
 for cfg in d['coverage']:
  assert cfg['tests_run']==1 and len(cfg['observed'])==1;o=cfg['observed'][0];assert o['expected_stdout']==expected and o['effective_optimizations']==['O0','O2']
  links=[x for x in o['commands'] if x['kind']=='link'];runs=[x for x in o['commands'] if x['kind']=='execute'];assert len(links)==len(runs)==2
  assert all(x['returncode']==0 and x['stdout_sha256']==h for x in runs)
  for x in links:
   ir=x['linked_llvm'];p=Path(ir['snapshot']);q=b/p.parent.name/p.name;assert p.parent.name==cfg['configuration']+'-llvm' and sha(q)==ir['sha256'];paths.append(str(q))
   definitions=re.findall(r'^define[^\n]*',q.read_text(),re.M);asan=sum(bool(re.search(r'\)\s+[^\n]*\bsanitize_address\b',z)) for z in definitions)
   assert len(definitions)==ir['definitions']==12 and asan==ir['asan_definitions']==(12 if 'sanitize' in cfg['configuration'] else 0)
 assert len(set(paths))==6
 out['gates'].append({'gate':'loop capture projection','run':b.name,'result_sha256':sha(b/'results.json'),'retained_archive_files':retained,'methods':1,'configurations':3,'generated_executions':6,'immutable_before_link_IRs':6,'output_lines':11,'ASan_definitions_sanitized_IR':12,'status':'accepted exact saved outputs/IR; generated ASan only'})
 p=B/'archive-only-results.json';d=json.loads(p.read_text());assert d['status']=='passed';fresh=Path(d['fresh_directory']);existing=0
 for row in d['sources']:
  archived=ROOT/row['archived_source'];assert sha(archived)==row['sha256'];retain(archived)
  copied=fresh/row['copied']
  if copied.is_file():assert sha(copied)==row['sha256'];existing+=1
 assert len(d['sources'])==24
 checks={x['label']:x for x in d['checks']};assert len(checks)==7
 assert checks['rawbits']['returncode']==0 and checks['rawbits']['stdout']=='10 raw words, mutation independence, empty backed scalar, empty and immortal/null reference controls recovered\n'
 assert checks['aggregate-object']['returncode']==0 and checks['aggregate-object']['stdout']=='native aggregate contents, metadata and debt recovery verified\n'
 phases=[json.loads(x) for x in checks['aggregate-object']['stderr'].splitlines() if x.startswith('{')]
 assert phases[-1]=={'phase':'final','profile':'system','objects':0,'requested_bytes':0,'heap_allocations':0}
 assert phases[0]['all_poll_work']==phases[0]['actual_queued_units']==64 and phases[0]['index_builds']==0
 assert checks['aggregate-invalid']['returncode']==1 and 'Minyar stopped: Text contained invalid UTF-8.' in checks['aggregate-invalid']['stderr']
 for x in d['checks']:
  if x['label'].endswith('-compile'):
   assert all('/build/' not in z and '/Projects/Minyar-Lang/runtime/' not in z for z in x['command']);assert '-O2' in x['command'] and '-DNDEBUG' not in x['command']
 out['gates'].append({'gate':'archive-only replay','result_sha256':sha(p),'source_files_rehashed':24,'still_retained_executed_temp_files_rehashed':existing,'builds':2,'native_boundary_executions':3,'journal_records':7,'status':'accepted saved archived-source boundaries','reproduction_limits':'Installed external Darwin Clang/SDK/libc; aggregate observer source distinct from pristine final hashes; no fully hermetic/compiler rebuild claim'})
 p=B/'own-production/index.json';d=json.loads(p.read_text());patch=B/'own-production/own-production.patch';assert sha(patch)==d['patch_sha256']=='a780a41d56b78f52eac3de05f0ff426e87f7adcceb6091f7896fb3703aacd400';retain(patch)
 for row in d['files']:
  name=Path(row['path']).name;initial=B/'own-production/baseline'/name;assert sha(initial)==row['initial_dirty_sha256']
 out['own_patch_register_matches_independent_reconstruction']=True
 (OUT/'round4-gate-verification.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
