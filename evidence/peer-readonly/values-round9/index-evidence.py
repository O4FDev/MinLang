"""Seal a hash index of this lane's documents and retained raw evidence."""
import hashlib
import json
import pathlib

ROOT = pathlib.Path('/Users/luke/Projects/Minyar-Lang')
BASE = ROOT / 'evidence/peer-readonly/values-round9'
INDEX = BASE / 'evidence-index.json'
reports = [ROOT/'research/2026-10-memory/peer-readonly-values-round9.md',
           ROOT/'research/2026-10-memory/peer-readonly-values-round9.json']
paths = sorted([p for p in BASE.rglob('*') if p.is_file() and p != INDEX] + reports)
records = []
for p in paths:
    raw = p.read_bytes()
    if p.suffix == '.json':json.loads(raw)
    records.append(dict(path=str(p.relative_to(ROOT)),bytes=len(raw),
                        sha256=hashlib.sha256(raw).hexdigest(),physical_lines=len(raw.splitlines())))
index = dict(schema=1,scope='Only round9 owned reports/evidence; excludes the index itself to avoid recursive hashing. '
             'File/byte counts measure retained documentary artifacts, not reviewed semantic units or executed tests.',
             indexed_files=len(records),total_indexed_bytes=sum(r['bytes'] for r in records),files=records)
INDEX.write_text(json.dumps(index,indent=2)+'\n')
saved=json.loads(INDEX.read_text())
assert len({r['path'] for r in saved['files']})==saved['indexed_files']
assert all(hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()==r['sha256'] for r in saved['files'])
assert {str(p.relative_to(ROOT)) for p in paths}=={r['path'] for r in saved['files']}
print(json.dumps(dict(status='passed',indexed_files=len(records),independent_hash_checks=len(records),
                      index_path=str(INDEX.relative_to(ROOT)),index_sha256=hashlib.sha256(INDEX.read_bytes()).hexdigest()),indent=2))
