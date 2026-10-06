from pathlib import Path
import hashlib,json,datetime,subprocess
root=Path.cwd(); dest=root/'evidence/peer-reconciliation/snapshot';dest.mkdir(parents=True,exist_ok=True)
start=datetime.datetime.now(datetime.timezone.utc).isoformat()
paths={Path('README.md'),Path('docs/architecture.md'),Path('docs/language.md'),Path('docs/runtime-memory.md'),Path('docs/testing.md'),Path('runtime/minyar_runtime.c'),Path('runtime/minyar_bytes.h'),Path('runtime/minyar_numbers.h'),Path('runtime/minyar_collections.h'),Path('tests/helpers.py'),Path('tests/clang_helpers.py')}
paths.update(Path('research/2026-10-memory').glob('peer*.json'));paths.update(Path('research/2026-10-memory').glob('peer*.md'))
paths.update(Path('research/2026-10-memory').glob('runtime-peer*'))
paths.update([Path('research/2026-10-memory/README.md'),Path('research/2026-10-memory/runtime-optimization-coverage-audit.json')])
paths.update(Path('tests').glob('*peer*.py'))
for folder in ['research/2026-10-memory/evidence/runtime-peer-projections','research/2026-10-memory/evidence/runtime-peer-calibrations']:
 for p in Path(folder).rglob('*'):
  if p.is_file() and p.suffix in ['.md','.json','.py','.log','.txt','.min','.ll','.c','.h','.stdout']:paths.add(p)
# All round2–9 documentary files, including frozen historical references.
for p in Path('evidence/peer-readonly').rglob('*'):
 if p.is_file() and p.suffix in ['.md','.json']:paths.add(p)
entries=[]
for p in sorted(paths):
 if not p.is_file():continue
 b=p.read_bytes();q=dest/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b)
 entries.append({'path':str(p),'snapshot':str(q.relative_to(root)),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'mtime_ns':p.stat().st_mtime_ns,'captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
end=datetime.datetime.now(datetime.timezone.utc).isoformat();changed=[]
for e in entries:
 p=root/e['path']
 if hashlib.sha256(p.read_bytes()).hexdigest()!=e['sha256']:changed.append(e['path'])
manifest={'started_utc':start,'cutoff_utc':end,'git_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'dirty_worktree':True,'atomic_snapshot':False,'files_changed_during_capture':changed,'entries':entries,'policy':'No compilation, test execution, fetch, installs or binaries; each path has exact captured hash. Concurrent later edits excluded.'}
(root/'evidence/peer-reconciliation/snapshot-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'start':start,'cutoff':end,'files':len(entries),'bytes':sum(e['bytes'] for e in entries),'changed':changed},indent=2))
