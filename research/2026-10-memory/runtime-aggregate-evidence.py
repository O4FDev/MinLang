#!/usr/bin/env python3
"""Archive selected aggregate experiment JSON and verified source snapshots."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'research/2026-10-memory/evidence/runtime-aggregate'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', nargs='+')
    args = parser.parse_args()
    entries = []
    for name in args.runs:
        source = ROOT / 'build/memory-research-aggregate-join' / name
        target = DEST / name
        report = json.loads((source / 'results.json').read_text())
        files = ['results.json', 'runtime-instrumentation.patch', 'ownership-instrumentation.patch']
        for record in report.get('sources', []) + report.get('instrumented_sources', []):
            path = source / record['snapshot']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256'], path
            files.append(record['snapshot'])
        for optional in ['opaque-ascii.txt', 'candidate.patch', 'comparison.json', 'poll-instrumentation.patch']:
            if (source / optional).is_file():
                files.append(optional)
        copied = []
        for relative in dict.fromkeys(files):
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / relative, path)
            copied.append({'path': relative, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        index = {'run': name, 'status': report['status'], 'files': copied,
                 'scope': 'Selected JSON, exact source snapshots and local diffs; no LLVM/binaries. '
                          'Generated reproduction requires a matching compiler/toolchain and repository helpers.'}
        (target / 'archive-index.json').write_text(json.dumps(index, indent=2) + '\n')
        entries.append({'run': name, 'status': report['status']})
    print(json.dumps(entries, indent=2))


if __name__ == '__main__':
    main()
