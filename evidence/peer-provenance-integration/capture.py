from pathlib import Path
import datetime, hashlib, json, subprocess
ROOT=Path.cwd(); OUT=ROOT/'evidence/peer-provenance-integration'; R='research/2026-10-memory/'
def sha(b): return hashlib.sha256(b).hexdigest()
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
assert not (OUT/'before-manifest.json').exists(), 'Do not replace initial evidence'
started=now(); files=[]
for name in ['peers.json','peers.md','peers-review-ledger.json','peers-inventory.json','peers-expanded-pending-inventory.json','peer-swift-statement-directory.md','peer-swift-statement-directory.json','README.md','peer-evidence-reconciliation.json','peer-evidence-reconciliation.md']:
 rel=R+name; p=ROOT/rel; b=p.read_bytes(); dest=OUT/'before'/rel; dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(b)
 files.append({'path':rel,'before_path':str(dest.relative_to(ROOT)),'sha256':sha(b),'bytes':len(b),'changed_during_copy':p.read_bytes()!=b})
for name,args in [('git-status-before.txt',['git','status','--porcelain=v1','--untracked-files=all']),('git-diff-before.patch',['git','diff','--binary','HEAD']),('git-head-before.txt',['git','rev-parse','HEAD'])]:
 b=subprocess.check_output(args);(OUT/name).write_bytes(b);files.append({'path':None,'before_path':str((OUT/name).relative_to(ROOT)),'sha256':sha(b),'bytes':len(b)})
guards=[]
paths=list((ROOT/'evidence/peer-reconciliation').rglob('*'))+list((ROOT/R).glob('peer-readonly-*'))+[ROOT/(R+'runtime-peer-projections.md'),ROOT/(R+'runtime-peer-optimization-correction.json'),ROOT/(R+'peer-swift-statement-directory.json')]
for p in sorted(set(paths)):
 if p.is_file(): guards.append({'path':str(p.relative_to(ROOT)),'sha256':sha(p.read_bytes())})
(OUT/'before-manifest.json').write_text(json.dumps({'schema':'minyar.peer_provenance_integration.before.v1','started_utc':started,'captured_utc':now(),'files':files,'frozen_guards':guards,'campaign_readme_policy':'Read and captured only; root/core owns updates; no coordination needed because it will not be touched.','working_tree_policy':'Already dirty and untracked research/evidence; own patch will compare preserved bytes, not HEAD.'},indent=2)+'\n')
print(json.dumps({'captured_files':len(files),'changed_during_copy':sum(f.get('changed_during_copy',False) for f in files),'frozen_guard_files':len(guards),'diff_bytes':(OUT/'git-diff-before.patch').stat().st_size}))
