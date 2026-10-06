"""Read-only final saved-artifact validation after owner outcome; no cohort imports/execution."""
import datetime,hashlib,json,re,sys
from pathlib import Path
ROOT=Path('/Users/luke/Projects/Minyar-Lang');BASE=ROOT/'research/2026-10-memory';OUT=BASE/'evidence/campaign-final-closure-review'
checks=[];manifest=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ck(label,condition,detail=None):checks.append({'check':label,'passed':bool(condition),'detail':detail})
def pin(p,extent):
 data=p.read_bytes();target=OUT/'final-endurance-inputs'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
 manifest.append({'path':str(p.relative_to(ROOT)),'snapshot':str(target.relative_to(OUT)),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'reading_extent':extent});return target

def main():
 # Explicit command line requires owner-supplied terminal outcome; no polling path.
 if len(sys.argv)!=2:raise SystemExit('Supply final result path only after owner terminal outcome')
 result=Path(sys.argv[1]).resolve();b=result.parent
 d=json.loads(result.read_text());p=json.loads((b/'preregister.json').read_text())
 if d['status']=='running':raise SystemExit('Result still running: closure pending; no elapsed-time pass')
 pin(result,'full final status/source/provenance/run fields')
 pin(b/'preregister.json','exact revision4 preregistration')
 ck('final result normal passed',d['status']=='passed' and d.get('production_sources_unchanged') is True)
 ck('single exact long run and zero new builds',len(d['runs'])==1 and not d['builds'])
 ck('preregister revision duration resource thresholds',p['revision']==4 and p['duration_native_seconds']==1800 and p['resource']=={'CPU_seconds_hard':180,'wall_seconds_hard':1850,'output_file_bytes_hard':16777216,'progress_watchdog_seconds':120,'native_progress_interval_seconds':60,'RSS_bytes_threshold':134217728})
 # Full expected prereg digest is read from the already accepted immutable pilot audit.
 prior=Path(d['pilot_evidence']['path']);pilot=json.loads((prior/'results.json').read_text());audit=json.loads((BASE/'evidence/runtime-joint-final-source-review/endurance-pilot-verification.json').read_text())
 ck('preregister identical accepted pilot audit',sha(b/'preregister.json')==audit['preregister_sha256']==sha(prior/'preregister.json'))
 ck('pilot immutable result and source reuse',sha(prior/'results.json')==d['pilot_evidence']['results_sha256']==audit['result_sha256'] and pilot['status']=='passed' and d['source_hashes']==pilot['source_hashes'])
 pin(prior/'results.json','accepted pilot record identity, no repeat full pilot audit');pin(BASE/'evidence/runtime-joint-final-source-review/endurance-pilot-verification.json','accepted prereg/fixture/driver/binary identities and prior pilot disposition')
 for name,key,expected in [('memory-research-joint-endurance.c','fixture_sha256','e6510c6da4e1ad54ff4a713e44fad7bf450cebcc6eae31ded39dc77a2547a47b'),('memory-research-joint-endurance.py','driver_sha256','55fc84b62ebe89376b2f635ef1df19f4bd5b8f26721729ac025b822cc6a9f36d')]:
  x=b/'tests'/name;ck('exact fixture/driver '+name,sha(x)==p[key]==expected==sha(prior/'tests'/name)==sha(ROOT/'tests'/name));pin(x,'whole static fixture/driver read, identity and final-drain/count/resource behavior')
 for name,h in d['source_hashes'].items():
  live=Path(name);arch=b/'runtime'/live.name
  ck('source freeze live/archive/pilot '+live.name,sha(live)==h==sha(arch)==sha(prior/'runtime'/live.name));pin(arch,'frozen identity only, named earlier source review owns semantic inspection')
 ck('focused prerequisite identity',sha(Path(d['gates_record']['path']))==d['gates_record']['sha256']=='1b9e80d0e12a189880895240de8b59f2c6fe54b5c354c83ca24f18638a2d141d')
 row=d['runs'][0];binary=Path(row['command'][2]);expected='7d96b6445f53af67d591d230980b89b69854c5b38c6b578d4e41444ad6ce4016'
 pin(binary,'original reused native binary identity only')
 ck('exact reused native binary',binary==prior/'native' and sha(binary)==row['binary_sha256']==expected==audit['native_binary_sha256'] and row['binary_hash_unchanged'] is True)
 ck('long exact argv/duration/status',row['command']==['/usr/bin/time','-l',str(prior/'native'),'1800','4a01'] and row['duration_native_seconds']==1800 and row['label']=='joint-1800-seconds' and row.get('returncode')==0 and row.get('status')=='passed')
 # Record original macro identities, not a new preprocessor invocation.
 macros=(prior/'native-macros.txt').read_text();pin(prior/'native-macros.txt','actual native pilot preprocessing output reused with exact binary')
 for macro,value in [('MINYAR_RC_TESTING','1'),('MINYAR_SYSTEM_HEAP','1'),('MINYAR_RC_POLL_BUDGET','32')]:ck('actual native macro '+macro,bool(re.search(r'^#define '+macro+' '+value+r'$',macros,re.M)))
 ck('native O2 assertions scope',next(x for x in pilot['builds'] if x['label']=='native')['binary_sha256']==expected and '-O2' in next(x for x in pilot['builds'] if x['label']=='native')['command'] and '-DNDEBUG' not in next(x for x in pilot['builds'] if x['label']=='native')['command'])
 stderr=b/row['stderr'];summaries=b/row['summaries'];monitor=b/row['monitor']
 for x in [stderr,summaries,monitor]:pin(x,'full final raw log/summary/monitor inspection')
 lines=[json.loads(x) for x in summaries.read_text().splitlines()];mons=[json.loads(x) for x in monitor.read_text().splitlines()];s=lines[-1]
 ck('latest_summary exact raw final',s==row['latest_summary'] and s['final']==1 and all(x['final']==0 for x in lines[:-1]))
 ck('actual native duration >=1800',s['elapsed_native_seconds']>=1800,{'actual':s['elapsed_native_seconds'],'required':1800})
 ck('initial native summary',lines[0]['epochs']==0 and lines[0]['recoveries']==0 and lines[0]['final']==0)
 cumulative=['epochs','recoveries','eligible_scalar','eligible_empty','observed_nonempty_prefix_copies','pending_debt_fallbacks','certified_ascii_joins','unknown_ascii_joins','unicode_joins','completed_epoch_requested_sample_max','total_process_cpu_seconds','elapsed_native_seconds']
 for key in cumulative:ck('monotone summary '+key,all(y[key]>=x[key] for x,y in zip(lines,lines[1:])))
 origin=s['native_monotonic_origin_seconds'];ck('native origin stable seed',all(x['native_monotonic_origin_seconds']==origin and x['seed']==0x4a01 for x in lines))
 ck('summary interval within120s progress criterion',all(y['elapsed_native_seconds']-x['elapsed_native_seconds']<=120 for x,y in zip(lines,lines[1:])),{'summaries':len(lines),'largest_gap_native_seconds':max(y['elapsed_native_seconds']-x['elapsed_native_seconds'] for x,y in zip(lines,lines[1:]))})
 def multiple(n,k):return (n+k-1)//k
 for index,x in enumerate(lines):
  n=x['epochs'];debt=multiple(n,17);empty=multiple(n,6)-multiple(n,102);expected_counts={'eligible_scalar':n-debt,'eligible_empty':empty,'observed_nonempty_prefix_copies':n-debt-empty,'pending_debt_fallbacks':debt,'certified_ascii_joins':(n+2)//3,'unknown_ascii_joins':(n+1)//3,'unicode_joins':n//3,'recoveries':n//128+x['final']}
  ck('independent epoch schedule summary'+str(index),all(x[k]==v for k,v in expected_counts.items()) and n%16==0 and x['completed_epoch_requested_sample_max']<=4*1024*1024,{'epochs':n,'expected_counts':expected_counts})
 ck('final count conservation',s['eligible_scalar']+s['pending_debt_fallbacks']==s['epochs'] and s['observed_nonempty_prefix_copies']+s['eligible_empty']==s['eligible_scalar'] and s['certified_ascii_joins']+s['unknown_ascii_joins']+s['unicode_joins']==s['epochs'])
 ck('final recovery follows static CHECKs', 'recover();\n    CHECK(copied + empty_eligible == eligible);' in (b/'tests/memory-research-joint-endurance.c').read_text() and s['recoveries']==s['epochs']//128+1)
 logs=stderr.read_text();match=re.search(r'(\d+)\s+maximum resident set size',logs);rss=int(match.group(1)) if match else None
 ck('completed kernel peak and threshold',rss is not None and rss==row['completed_peak_RSS_bytes']<=134217728,{'completed_peak_RSS_bytes':rss})
 ck('no saved unexpected fatal diagnostics','FAILED line' not in logs and 'ERROR: AddressSanitizer' not in logs and 'runtime error:' not in logs)
 time_cpu=re.search(r'([\d.]+)\s+real\s+([\d.]+)\s+user\s+([\d.]+)\s+sys',logs)
 ck('observer wall <=1850 and native total CPU <=180',row['observer_elapsed_seconds']<=1850 and s['total_process_cpu_seconds']<=180,{'observer_wall_seconds':row['observer_elapsed_seconds'],'native_total_process_cpu_seconds':s['total_process_cpu_seconds'],'time_l_real_user_sys':list(map(float,time_cpu.groups())) if time_cpu else None})
 ck('monitor identity/memory/monotone',bool(mons) and all(int(x['native_pid'])==row['native_pid'] and 0<=x['sampled_rss_bytes']<=134217728 for x in mons) and all(y['observer_elapsed_seconds']>x['observer_elapsed_seconds'] for x,y in zip(mons,mons[1:])))
 ck('monitor recorded same observer domain',all(0<=x['observer_elapsed_seconds']<=row['observer_elapsed_seconds'] for x in mons))
 sizes={x.name:x.stat().st_size for x in [stderr,summaries,monitor]};ck('retained long output sizes bounded',all(v<=16777216 for v in sizes.values()),sizes)
 utc=datetime.datetime.now(datetime.timezone.utc).isoformat();fail=[x for x in checks if not x['passed']]
 out={'utc':utc,'status':'accepted exact saved final endurance' if not fail else 'requires resolution','result_sha256':sha(result),'run':str(result.relative_to(ROOT)),'checks':checks,'failed_checks':fail,'raw_final_summary':s,'summary_count':len(lines),'monitor_count':len(mons),'max_sampled_RSS_bytes':max(x['sampled_rss_bytes'] for x in mons),'completed_peak_RSS_bytes':rss,'observer_elapsed_seconds':row['observer_elapsed_seconds'],'native_execution_by_reviewer':False,'interpretation_limits':['Instrumented native systemK32 correctness endurance, not production timing','native and observer monotonic origins distinct','5percent batch target excludes setup/summary/drain overhead','endepoch requested sample is not construction/transient peak','RSS sample/completedpeak thresholds are not continuous enforcement','scalar length/Text category schedule correlated, not fullcrossproduct','final0gauges derive static recovery CHECKs followed by normal final1, no extra gauge fields claimed','64CHECKring only ownfailure diagnosis, no arbitraryfatal guarantee','finalbroadintegration/wholeappreadiness remains unvalidated']}
 (OUT/'final-endurance-verification.json').write_text(json.dumps(out,indent=2)+'\n');(OUT/'final-endurance-manifest.json').write_text(json.dumps({'utc':utc,'files':manifest},indent=2)+'\n');print(json.dumps({'status':out['status'],'predicates':len(checks),'failures':fail,'result_sha256':out['result_sha256'],'final_summary':s},indent=2))
if __name__=='__main__':main()
