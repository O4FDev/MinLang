"""Retain exact successful and failed evidence for the optional Result suite."""
import hashlib
import json
import os
import shutil
from pathlib import Path

def retain(evidence, failed=False):
    if evidence.closed:
        return
    evidence.closed = True
    files = {str(p.relative_to(evidence.path)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in evidence.path.rglob('*') if p.is_file() and not p.is_symlink()}
    storage = Path(os.environ.get('MINYAR_ERRORS_EVIDENCE_OBJECTS',
                                   evidence.path.parent / 'objects'))
    storage.mkdir(parents=True, exist_ok=True)
    snapshots = {}
    for name, digest in evidence.inputs.items():
        source = Path(name)
        if source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest() == digest:
            target = storage / digest
            if not target.exists():
                shutil.copyfile(source, target)
            snapshots[name] = str(target.resolve())
        else:
            snapshots[name] = None
    report = {'schema_version': 1, 'status': 'failed' if failed else 'passed',
              'workspace': str(evidence.path), 'inputs': evidence.inputs,
              'input_snapshots': snapshots,
              'files': files, 'controls': evidence.controls,
              'tools': {c['executable']: c['executable_sha256'] for c in evidence.commands
                        if c.get('executable') and c.get('executable_sha256')},
              'commands': evidence.commands}
    (evidence.path / 'evidence.json').write_text(json.dumps(report, indent=2) + '\n')

