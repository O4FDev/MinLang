"""Bounded documentary validation only; never imports or executes campaign tools."""
import datetime, hashlib, json, re
from pathlib import Path
ROOT=Path('/Users/luke/Projects/Minyar-Lang')
BASE=ROOT/'research/2026-10-memory'
OUT=BASE/'evidence/campaign-final-closure-review'
checks=[]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check(label,condition,detail=None):
 checks.append({'check':label,'passed':bool(condition),'detail':detail})
def capture(p,extent):
 p=p if p.is_absolute() else ROOT/p
 data=p.read_bytes(); target=OUT/'checkpoint-inputs'/p.relative_to(ROOT)
 target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
 return {'path':str(p.relative_to(ROOT)),'snapshot':str(target.relative_to(OUT)),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'reading_extent':extent}
files=[]
for n in ['README.md','campaign-findings.md','campaign-findings.json','campaign-delivery-audit.md','campaign-delivery-audit.json','runtime-joint-final-source-review.md','runtime-joint-final-source-review.json','runtime-scalar-production-performance-review.md','runtime-scalar-production-performance-review.json','runtime-joint-final-results.json','runtime-joint-endurance.md','runtime-joint-endurance-preregister.json','runtime-abi-final-source-map.json','runtime-abi-evidence-map.json','paper-methods-and-claims.md','paper-methods-and-claims.json']:
 p=BASE/n
 if p.exists():files.append(capture(p,'full status/claim/provenance text or structured field inspection; no repeat numerical/semantic proof audit'))
final={'minyar_runtime.c':'d919f066a0e71c80cb079a22659928541e958b68b81a645d7631f52ec8531a51','minyar_collections.h':'3b7ce602bc256dc8a42f49d87fd6cccd0eb28132d952e3eb34284614c4725810','minyar_bounded_rc.h':'7d40e4f2469150840b4527a85f4234a677ed177803793372fd4104b0e8e7304e','graphics.c':'736bc64a8bea8edb134d7752cdb9ad9f0f3e8174cbe0ef7f716e4698e8f33eed'}
# Graphics is separate native provenance; discover exact matching live file without executing it.
for name,h in final.items():
 candidates=list(ROOT.glob('runtime/**/'+name))
 if name=='graphics.c' and not candidates:candidates=[p for p in (ROOT/'runtime').rglob('*') if p.is_file() and 'graphics' in p.name]
 match=[p for p in candidates if digest(p)==h]
 check('final live identity '+name,len(match)==1,{'expected':h,'paths':[str(p.relative_to(ROOT)) for p in match]})
 for p in match:files.append(capture(p,'identity only; semantics inherited from named source review'))
prior=BASE/'evidence/runtime-joint-final-source-review'
m=json.loads((prior/'review-manifest.json').read_text());bad=[]
for row in m['files']:
 p=prior/row['path']
 if not p.exists() or p.stat().st_size!=row['bytes'] or digest(p)!=row['sha256']:bad.append(row['path'])
check('prior final-source review manifest preserved',not bad,{'entries':len(m['files']),'mismatches':bad})
files.append(capture(prior/'review-manifest.json','all manifest entries rehashed; no semantic reading inferred'))
joint=json.loads((BASE/'runtime-joint-final-results.json').read_text())
check('consolidated focused result identity',digest(BASE/'runtime-joint-final-results.json')=='1b9e80d0e12a189880895240de8b59f2c6fe54b5c354c83ca24f18638a2d141d')
check('focused counts/status',joint['status']=='passed' and len(joint['groups'])==12 and len(joint['supplemental_and_provenance'])==3)
for row in joint['groups']+joint['supplemental_and_provenance']:
 p=ROOT/row['path'];check('focused referenced identity '+row.get('label','supplement'),digest(p)==row['sha256']);files.append(capture(p,'result identity and disposition; detailed numeric/IR/oracle reviews inherited'))
app=BASE/'evidence/runtime-joint-final/run-xc_5g2zj/application.json';a=json.loads(app.read_text());files.append(capture(app,'formatter record and source identities'))
for row in a['files']:check('formatter no-byte delta '+row['name'],row['raw_sha256']==row['final_sha256']==final[row['name']])
own=BASE/'evidence/runtime-joint-final/run-xc_5g2zj/own-production'
x=json.loads((own/'index.json').read_text());check('own patch original reviewed identity',digest(own/'own-production.patch')==x['patch_sha256']=='a780a41d56b78f52eac3de05f0ff426e87f7adcceb6091f7896fb3703aacd400')
for n in ['index.json','own-production.patch']:files.append(capture(own/n,'identity and prior independent reconstruction correspondence; no patch command run'))
prod=BASE/'evidence/runtime-list-bulk-production-cpu/run-x3798c1e'
a=json.loads((prod/'archive-patch-addendum.json').read_text())
check('scalar additive exact patch closure',digest(prod/a['added_path'])==a['sha256']=='aca55490803528a0aeabbc8d21760a00ea8531c41f7edc2f066e4c7f8a31be66' and (prod/a['added_path']).stat().st_size==a['bytes'])
check('scalar original archive index unchanged',digest(prod/'index.json')==a['original_index_sha256']=='ce8f21a9db1f277c63eb5dffd685c9a3430297f14d6a273c52693a35701d1e2b')
for n in ['archive-patch-addendum.json','index.json',a['added_path']]:files.append(capture(prod/n,'archive correction identity; original checkpoint retained'))
abi=json.loads((BASE/'runtime-abi-final-source-map.json').read_text());old=json.loads((BASE/'runtime-abi-evidence-map.json').read_text())
check('ABI unchanged105 names and evidence summaries',len(abi['functions'])==105 and [x['name'] for x in abi['functions']]==[x['name'] for x in old['functions']] and abi['summary']==old['summary'])
for x,y in zip(abi['functions'],old['functions']):
 check('ABI historical evidence unchanged '+x['name'],{k:v for k,v in x.items() if k not in ['definitions','final_joint_evidence']}=={k:v for k,v in y.items() if k not in ['definitions','final_joint_evidence']})
 if 'final_joint_evidence' in x:
  check('ABI focused pointer '+x['name'],x['final_joint_evidence']['sha256']==digest(BASE/x['final_joint_evidence']['result']))
 for row in x['definitions']:
  p=ROOT/row['path'];line=p.read_text().splitlines()[row['line']-1]
  check('ABI final definition '+x['name'],digest(p)==row['sha256'] and (re.sub(r'\s+',' ',row['signature'].strip()) in re.sub(r'\s+',' ',' '.join(p.read_text().splitlines()[row['line']-1:row['line']+2])) if 'signature' in row else row['macro'] in line and row['cast'] in line),{'path':row['path'],'line':row['line']})
for row in abi['runtime_sources']:check('ABI fragment hash '+row['path'],digest(ROOT/row['path'])==row['sha256'])
check('ABI compiler source hash',digest(ROOT/abi['compiler_declaration_source']['path'])==abi['compiler_declaration_source']['sha256'])
links=[]
for n in ['README.md','campaign-findings.md','runtime-joint-endurance.md','paper-methods-and-claims.md','campaign-delivery-audit.md']:
 p=BASE/n
 if not p.exists():continue
 for target in re.findall(r'\]\(([^)]+)\)',p.read_text()):
  if '://' in target or target.startswith('#'):continue
  target=target.split('#')[0]; q=p.parent/target
  if not q.exists():links.append({'document':n,'target':target})
result={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'bounded documentary identity/count/reference review; zero new native/compiler tests','checks':checks,'failed_checks':[x for x in checks if not x['passed']],'broken_local_links':links,'long_run':'pending owner outcome; no polling/no elapsed-time inference','source_hashes':final}
(OUT/'checkpoint-documentary-checks.json').write_text(json.dumps(result,indent=2)+'\n')
(OUT/'checkpoint-manifest.json').write_text(json.dumps({'utc':result['utc'],'files':files},indent=2)+'\n')
print(json.dumps({'checks':len(checks),'failures':result['failed_checks'],'broken_local_links':links,'captured_files':len(files)},indent=2))
