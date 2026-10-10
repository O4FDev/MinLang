"""Independent retained probes; no LLVM execution. Run only after CPU release."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
checker = HERE / 'inputs/repaired-checker-d2607ac5.py'
expected_checker_sha = 'd2607ac5c8d638b1d25dcd157be7aa459e021d94f7f51dded5fbf736194f96d5'
assert hashlib.sha256(checker.read_bytes()).hexdigest() == expected_checker_sha
spec = importlib.util.spec_from_file_location('review_checkpoint', checker)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
# Only relocate read-only frozen catalog inputs for the copied checker.
module.DESIGN = ROOT / 'research/2026-10-memory/evidence/local-cleanup-certifier-design'
rows = json.loads((HERE / 'probe-manifest.json').read_text())
results = []
for row in rows:
    source = (ROOT / row['path']).read_text()
    assert hashlib.sha256(source.encode()).hexdigest() == row['sha256']
    start = time.monotonic()
    actual = module.analyze(source, row['entry'])
    results.append(dict(row, actual=actual, expectation_met=actual['status'] == row['expected_status'],
                        elapsed_seconds=time.monotonic() - start))
print(json.dumps(dict(checker_sha256=expected_checker_sha,
    catalog_path=str(module.DESIGN), relocation_only=True, llvm_execution=False,
    results=results), indent=2))
