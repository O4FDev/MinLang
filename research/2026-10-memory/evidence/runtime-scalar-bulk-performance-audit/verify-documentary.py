"""Hash, in-memory patch and plot-data checks; no native execution or plotting."""
from pathlib import Path
import hashlib
import json
import re

OUT = Path(__file__).resolve().parent
INPUT = OUT / 'inputs'
R = INPUT / 'research/2026-10-memory'

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def load(p):
    return json.loads(p.read_text())

def apply(text, patch):
    original = text.splitlines(True)
    lines = patch.splitlines(True)
    output = []
    cursor = 0
    i = 0
    while i < len(lines):
        match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', lines[i])
        if not match:
            i += 1
            continue
        start = int(match[1]) - 1
        assert start >= cursor
        output.extend(original[cursor:start])
        cursor = start
        i += 1
        while i < len(lines) and not lines[i].startswith('@@ '):
            line = lines[i]
            if line.startswith((' ', '-')):
                assert original[cursor] == line[1:], (original[cursor], line)
                cursor += 1
            if line.startswith((' ', '+')):
                output.append(line[1:])
            i += 1
    output.extend(original[cursor:])
    return ''.join(output)

cal = R / 'evidence/runtime-list-bulk-cpu-calibration/run-fe4pyup4'
index = load(cal / 'archive-index.json')
for f in index['files']:
    assert digest(cal / f['path']) == f['sha256']
    assert (cal / f['path']).stat().st_size == f['bytes']
for variant in ['baseline', 'candidate']:
    directory = cal / variant
    for p in (INPUT / 'runtime').glob('*'):
        compiled = (directory / 'runtime' / p.name).read_text()
        expected = p.read_text()
        if variant == 'candidate' and p.name == 'minyar_collections.h':
            expected = apply(expected, (directory / 'candidate.patch').read_text())
        observer = {'minyar_rc.h': 'rc-observer.patch', 'minyar_bounded_rc.h': 'poll-observer.patch',
                    'minyar_collections.h': 'list-observer.patch'}.get(p.name)
        if observer:
            expected = apply(expected, (directory / observer).read_text())
        assert compiled == expected, (variant, p.name)
for p in (cal / 'baseline/tests').glob('*'):
    assert p.read_bytes() == (cal / 'candidate/tests' / p.name).read_bytes()
freeze = load(cal / 'results.json')['production_frozen_hashes']
for path, value in freeze.items():
    assert digest(INPUT / 'runtime' / Path(path).name) == value

fig = load(R / 'runtime-list-bulk-figure.json')
assert digest(R / 'runtime-list-bulk-figure.py') == fig['generator_sha256']
assert digest(R / fig['input']) == fig['input_sha256']
for f in fig['outputs']:
    assert digest(R / f['path']) == f['sha256']
rows = load(OUT / 'reanalysis.json')['rows']
assert all(0.88 <= r['ratio'] <= 2.65 for r in rows)
zoom = [r for r in rows if r['case'][2] != 0 or r['case'][1] < 31]
assert all(0.89 <= r['ratio'] <= 1.12 for r in zoom)
result = {'calibration_archive_files_verified': len(index['files']),
          'calibration_instrumented_sources_reconstructed': True,
          'calibration_common_tests_equal': True,
          'production_freeze_hashes_verified': len(freeze),
          'plot_generator_input_exports_hashes_verified': True,
          'full_panel_pairs_within_limits': len(rows), 'zoom_pairs_within_limits': len(zoom),
          'plot_regenerated': False, 'native_execution': False}
(OUT / 'documentary-verification.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
