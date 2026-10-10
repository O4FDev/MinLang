"""Serial read-only input pinning; writes only this audit's evidence directory."""
from pathlib import Path
import datetime
import hashlib
import json

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
RESEARCH = ROOT / 'research/2026-10-memory'

def digest(data):
    return hashlib.sha256(data).hexdigest()

files = [ROOT / 'README.md', ROOT / 'docs/architecture.md', ROOT / 'docs/runtime-memory.md',
         ROOT / 'scripts/with-limits.sh']
for name in ['README.md', 'campaign-findings.md', 'campaign-findings.json',
             'performance-evidence-audit.md', 'performance-evidence-audit.json',
             'runtime-scalar-bulk-review.md', 'runtime-scalar-bulk-review.json',
             'runtime-list-bulk.md', 'runtime-list-bulk-results.json',
             'runtime-list-bulk-followup-results.json', 'runtime-list-bulk-cpu-proposal.md',
             'runtime-list-bulk-cpu-proposal.json', 'runtime-list-bulk-cpu-proposal-revision2.json',
             'runtime-list-bulk-cpu-proposal-revision3.json', 'runtime-list-bulk-cpu-results.json',
             'runtime-list-bulk-bits-provenance-reconciliation.json',
             'runtime-joint-adoption-preregister.md', 'runtime-joint-adoption-preregister.json',
             'runtime-joint-adoption-preregister-initial.json', 'runtime-list-bulk-figure.py',
             'runtime-list-bulk-figure.json', 'runtime-list-bulk-timing.svg',
             'runtime-list-bulk-timing.pdf', 'runtime-list-bulk-timing.png']:
    files.append(RESEARCH / name)
for name in ['memory-research-list-bulk-cpu.py', 'memory-research-list-bulk-cpu.c',
             'memory-research-list-bulk-checksum.c', 'memory-research-list-bulk-cpu-calibration.py',
             'memory-research-list-bulk.py', 'memory-research-list-bulk.c', 'clang_helpers.py']:
    files.append(ROOT / 'tests' / name)
files.extend(p for p in (ROOT / 'runtime').glob('minyar_*') if p.is_file())
for folder in ['runtime-list-bulk-cpu/run-ws0ma9zu', 'runtime-list-bulk-cpu/run-63_142as',
               'runtime-list-bulk-cpu/run-pt288kkw', 'runtime-list-bulk-cpu-calibration/run-fe4pyup4']:
    files.extend(p for p in (RESEARCH / 'evidence' / folder).rglob('*') if p.is_file())
records = []
for p in sorted(set(files)):
    data = p.read_bytes()
    relative = p.relative_to(ROOT)
    target = OUT / 'inputs' / relative
    assert not target.exists(), target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    assert digest(p.read_bytes()) == digest(data), ('changed during pin', p)
    records.append({'path': str(relative), 'snapshot': str(target.relative_to(OUT)),
                    'sha256': digest(data), 'bytes': len(data)})
manifest = {'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'scope': 'Saved evidence/source bytes only; no execution or new measurement',
            'root': str(ROOT), 'files': records}
(OUT / 'inputs.json').write_text(json.dumps(manifest, indent=2) + '\n')
(OUT / 'inputs.sha256').write_text(''.join(f"{r['sha256']}  {r['snapshot']}\n" for r in records))
print(json.dumps({'files': len(records), 'bytes': sum(r['bytes'] for r in records),
                  'manifest_sha256': digest((OUT / 'inputs.json').read_bytes())}))
