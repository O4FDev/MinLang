"""Inspect only supplied saved result paths; never discover or run native jobs."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import sys

OUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(path):
    data = json.loads(path.read_text())
    base = path.parent
    checkpoint = OUT / 'result-inputs' / base.name
    checkpoint.mkdir(parents=True, exist_ok=True)
    (checkpoint / 'results.json').write_bytes(path.read_bytes())
    result = {'path': str(path), 'sha256': sha(path), 'status': data.get('status'),
              'top_level_fields': list(data), 'source_checks': [], 'journal': [], 'ir': []}
    for key in ['sources', 'instrumented_sources']:
        for entry in data.get(key, []):
            name = entry.get('snapshot', entry.get('path'))
            if not name:
                continue
            target = Path(name)
            if not target.is_absolute():
                target = base / target
            row = {'field': key, 'path': str(target), 'expected_sha256': entry.get('sha256'), 'present': target.exists()}
            if target.is_file():
                row['actual_sha256'] = sha(target)
                if entry.get('sha256'):
                    assert row['actual_sha256'] == entry['sha256'], row
                if target.is_relative_to(base):
                    retained = checkpoint / target.relative_to(base)
                    retained.parent.mkdir(parents=True, exist_ok=True)
                    retained.write_bytes(target.read_bytes())
            result['source_checks'].append(row)
    for row in data.get('checks', []):
        argv = row.get('command', row.get('argv', []))
        optimization = [x for x in argv if isinstance(x, str) and re.fullmatch(r'-O(?:[0123szg]|fast)', x)]
        result['journal'].append({'label': row.get('label'), 'returncode': row.get('returncode'),
                                  'timed_out': row.get('timed_out'), 'optimization_flags': optimization,
                                  'effective_last_optimization': optimization[-1] if optimization else None,
                                  'command': argv, 'stdout_lines': len(row.get('stdout', '').splitlines()),
                                  'peak_rss_bytes': row.get('peak_rss_bytes')})
    for p in sorted(base.glob('*.ll')):
        text = p.read_text()
        (checkpoint / p.name).write_bytes(p.read_bytes())
        headers = re.findall(r'^define[^\n]*', text, re.M)
        attr = [bool(re.search(r'\)\s+[^\n]*\bsanitize_address\b', x)) for x in headers]
        result['ir'].append({'name': p.name, 'sha256': sha(p), 'definitions': len(headers),
                              'asan_definitions': sum(attr),
                              'all_definitions_have_asan': bool(headers) and all(attr)})
    for key in ['summary', 'coverage', 'generated_modes', 'generated_sanitizer_metadata',
                'generated_asan_definitions', 'compiler_sha256', 'compiler_artifact_sha256',
                'baseline_comparison', 'configuration', 'phase', 'variant', 'runtime_entry_hashes',
                'production_frozen_hashes', 'output_only_oracle_calibration', 'middle_slot_output_calibration']:
        if key in data:
            result[key] = data[key]
    result['observations_count'] = len(data.get('observations', []))
    result['native_observations_count'] = len(data.get('native_observations', []))
    result['comparisons_count'] = len(data.get('comparisons', []))
    result['check_count'] = len(result['journal'])
    for p in base.rglob('*.patch'):
        retained = checkpoint / p.relative_to(base)
        retained.parent.mkdir(parents=True, exist_ok=True)
        retained.write_bytes(p.read_bytes())
    result['scope'] = 'Saved source/result/argv/IR inspection only; no compiler/native execution.'
    return result


if __name__ == '__main__':
    records = [inspect(Path(x).resolve()) for x in sys.argv[1:]]
    target = OUT / ('result-verification-' + datetime.datetime.now(datetime.timezone.utc).strftime('%H%M%S') + '.json')
    target.write_text(json.dumps({'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'records': records}, indent=2) + '\n')
    print(json.dumps({'evidence': str(target), 'records': [{'path': r['path'], 'status': r['status'],
          'checks': r['check_count'], 'sources': len(r['source_checks']), 'ir': r['ir']} for r in records]}, indent=2))
