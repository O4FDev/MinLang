from pathlib import Path
import json,hashlib,re
root=Path.cwd();report=root/'research/2026-10-memory/peer-evidence-reconciliation.json';d=json.loads(report.read_text());errors=[];checked=0;refs=set()
def visit(x):
 global checked
 if isinstance(x,dict):
  # Archive results.sources snapshot paths are relative to their enclosing run,
  # not the repository. Their resolution/hashes are checked in documentary-checks.
  if all(k in x for k in ['snapshot','sha256']) and (x['snapshot'].startswith('evidence/peer-reconciliation/') or Path(x['snapshot']).is_absolute()):
   p=root/x['snapshot'];key=(str(p),x['sha256'],x.get('json_pointer'))
   if key not in refs:
    refs.add(key);checked+=1
    if not p.is_file():errors.append(('missing',str(p)))
    elif hashlib.sha256(p.read_bytes()).hexdigest()!=x['sha256']:errors.append(('hash',str(p)))
    elif x.get('json_pointer'):
     v=json.loads(p.read_text())
     try:
      for part in x['json_pointer'].lstrip('/').split('/'):
       token=part.replace('~1','/').replace('~0','~');v=v[int(token)] if isinstance(v,list) else v[token]
     except Exception as e:errors.append(('pointer',str(p),x['json_pointer'],str(e)))
  for v in x.values():visit(v)
 elif isinstance(x,list):
  for v in x:visit(v)
visit(d)
md=report.with_suffix('.md');broken=[]
for target in re.findall(r'\]\(([^)]+)\)',md.read_text()):
 if not target.startswith('http') and not (md.parent/target).resolve().exists():broken.append(target)
record={'provenance_references_checked':checked,'errors':errors,'broken_markdown_links':broken,'scope':'Documentary read/JSON pointer/hash/link checks only. Relative archive source snapshots resolved separately in765 base checks and round9 checks.'}
(root/'evidence/peer-reconciliation/final-reference-checks.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2));assert not errors and not broken
