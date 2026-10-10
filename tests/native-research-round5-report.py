#!/usr/bin/env python3
"""Derive round5 inventory, provenance, precise counts and handoff from saved results."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / 'research/2026-10-memory'
BASE = RESEARCH / 'evidence/native-application-round5'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def main():
    final = json.loads((BASE / 'final-matrix/results.json').read_text())
    assert final['status'] == 'passed' and all(row['passed'] for row in final['contracts'])
    inventory = []
    tested = {'save.min': ['loadWorld', 'loadPlayer', 'store'],
              'physics.min': ['update', 'move', 'moveAxis', 'collides', 'occupies', 'cell'],
              'terrain.min': ['get'], 'blocks.min': ['isSolid', 'isPlant']}
    for path in sorted((ROOT / 'examples/craft').glob('*.min')):
        functions = [{'name': m[1], 'line': path.read_text()[:m.start()].count('\n') + 1}
                     for m in re.finditer(r'^(?:public )?function (\w+)\(', path.read_text(), re.M)]
        inventory.append({'path': str(path.relative_to(ROOT)), 'sha256': digest(path),
                          'source_defined_functions': functions,
                          'round5_executed_functions': tested.get(path.name, []),
                          'note': 'Execution does not imply complete branch coverage; atmosphere only uses its record layout.'})
    gaps = [
        {'path': 'examples/craft/save.min', 'prior': 'round1-4 unexecuted',
         'round5': 'all3 public functions, exact store bytes, missing/0/short/long/valid length, flying0/1/2, alias and derived metadata preservation',
         'remaining': 'real full512x512x80world, read/write fatal faults in save workflow, interrupted publication/atomicity, malformed block IDs/NaN state validation, repeated long ownership accounting'},
        {'path': 'examples/craft/physics.min', 'prior': 'round1 cardinal aim and reach miss only; round2-4 no extended movement evidence',
         'round5': '16 analytical endpoints,22material collisions,3occupancy results; borrowed world/player and local World lifetimes complete per function',
         'remaining': 'yaw-dependent movement beyond0, z-wall collisions, arbitrary body shapes, spawn, aiming ties/noncardinal rays, arbitrary trajectories, full runtime cleanup statistics'},
        {'path': 'examples/craft/terrain.min', 'prior': 'round1 small meshes/repeatedtorch; round2 exact64x64x16edit/remesh trace, NOT generation',
         'round5': 'read-only get dependency in512byteworld; no new terrain edit/remesh claim',
         'remaining': 'create(20MiBblocks), terrainHeight/plantTree/placeVein/carveTunnel/generate and full prepareLighting; independently bounded generation proposal needed'},
        {'path': 'examples/craft/textures.min', 'prior': 'unexecuted atlas/icon generation', 'round5': 'inventory only',
         'remaining': 'build/drawTile/drawIcon/tiled/cell;256x256x4Bytes bounded public build seam is available'},
        {'path': 'examples/craft/atmosphere.min', 'prior': 'cloud/body geometry unexecuted', 'round5': 'Sky record fields exercised by save only',
         'remaining': 'advance day wrapping;create/buildClouds60x60cells; halo/body CPUgeometry;typed nonfatal geometry seam would need separate proposal'},
        {'path': 'runtime/native/graphics.c', 'prior': 'round1-4 bounded native PNG/mesh CPU mocks; round3 distinctnames; round4 finalPNG75checks',
         'round5': 'signature-only fatal seam39symbols, one deliberatecreateMesh call exits91; no renderer bodies linked',
         'remaining': 'push/overlay_quad/drawText/drawLine batching/highwater/clearrefill; true GPU/shader/display behavior'},
        {'path': 'examples/craft/main.min', 'prior': 'whole game/display lifetimes unexecuted', 'round5': 'source inspection of load->prepareLighting and autosave/quitting paths only',
         'remaining': 'full application lifecycle, long repeatedsave/load ownership and cleanup/cache accounting; partial function-scope lifetimes are not complete game proof'}]
    write(RESEARCH / 'native-application-round5-inventory.json',
          {'inventory': inventory, 'gap_mapping': gaps, 'reports_read': [
              'native-application-report.txt', 'native-application-round2-report.md',
              'native-application-round3-report.md', 'native-application-round4-report.md'],
           'source_inspection': 'Full selected save/physics/terrain modules, atmosphere CPUgeometry, texturebuild/icons and main load/save sequence; inventory is not exhaustive semantic review.'})
    protected = []
    for row in final['sources']:
        current = digest(ROOT / row['path'])
        protected.append({**row, 'current_sha256': current, 'matches': current == row['sha256']})
    assert all(row['matches'] for row in protected)
    historical = []
    for name in ['native-application-index.json', 'native-application-round2-index.json',
                 'native-application-round3-index.json', 'native-application-round4-index.json']:
        data = json.loads((RESEARCH / name).read_text())
        for row in data['records']:
            if 'sha256' not in row:
                continue
            path = RESEARCH / row['path']
            historical.append({'index': name, **row, 'matches': path.is_file() and digest(path) == row['sha256']})
    assert all(row['matches'] for row in historical), [r for r in historical if not r['matches']]
    formatter = '/Users/luke/.cache/uv/archive-v0/qir4EsQDYRgTcgFN/clang_format/data/bin/clang-format'
    commands = [[formatter, '--version'], [formatter, '--dry-run', '--Werror', 'tests/native-research-round5.c'],
                ['git', 'diff', '--check', '--', 'tests/native-research-round5.c',
                 'tests/native-research-round5.py', 'tests/native-research-round5.min']]
    checks = []
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        checks.append({'command': command, 'returncode': result.returncode,
                       'stdout': result.stdout, 'stderr': result.stderr})
        assert result.returncode == 0, checks[-1]
    for path in ROOT.glob('tests/native-research-round5*.py'):
        compile(path.read_text(), str(path), 'exec')
    write(BASE / 'verification.json', {'protected_current_sources': protected,
                                      'historical_indexed_artifacts': historical,
                                      'historical_hashed_records_checked': len(historical),
                                      'checks': checks, 'owned_python_syntax': 'passed',
                                      'compiler_sha256_matches': digest(ROOT / 'build/minyarc') == final['compiler_sha256'],
                                      'objects_unchanged': all(digest(Path(r['path'])) == r['sha256'] for r in final['objects'])})
    native = [row for row in final['commands'] if row['native']]
    builds = [row for row in final['commands'] if not row['native']]
    cohorts = {}
    for label in ('pilot1', 'counted-pilot', 'final-matrix'):
        data = json.loads((BASE / label / 'results.json').read_text())
        cohorts[label] = {'status': data['status'], 'contract_groups': len(data['contracts']),
                          'calibrations': len(data['calibrations']), 'counts_not_combined': True}
    summary = {'status': 'passed_bounded_round_campaign_continues', 'cohorts': cohorts,
               'final_configurations': ['system-O2', 'system-O0', 'system-O1-ASan+UBSan'],
               'final_contract_groups': len(final['contracts']), 'contract_groups_per_configuration': 12,
               'final_breakdown': {'store_groups': 6, 'load_groups': 27, 'physics_groups': 3},
               'within_physics_groups': {'endpoint_rows': 48, 'material_flags': 66, 'occupancy_flags': 9,
                                         'not_added_to_contract_group_total': True},
               'final_calibrations': final['calibrations'], 'generated_sanitizer': final['sanitizer_coverage'],
               'observed_save_api_counts': {key: sum(r.get('save_api_counts', {}).get(key, 0) for r in native)
                                            for key in ['save_read_calls', 'save_write_calls', 'save_read_bytes', 'save_write_bytes']},
               'resources': {'native_darwin_peak_rss_bytes': max(r['darwin_time_peak_rss_bytes'] for r in native),
                             'compile_darwin_peak_rss_bytes': max(r['darwin_time_peak_rss_bytes'] for r in builds),
                             'native_sampled_peak_rss_bytes': max(r['sampled_peak_rss_bytes'] for r in native),
                             'largest_observed_command_wall_seconds': max(r['wall_seconds'] for r in final['commands']),
                             'performance_claim': False, 'managed_live_object_maximum': 'unmeasured'},
               'production_edits': False, 'production_red_found': False, 'fresh_core_build': False,
               'core_runtime_sha256': digest(ROOT / 'runtime/minyar_runtime.c'),
               'graphics_sha256': digest(ROOT / 'runtime/native/graphics.c'),
               'compiler_sha256': final['compiler_sha256'], 'objects': final['objects']}
    write(RESEARCH / 'native-application-round5-results.json', summary)
    paths = list(BASE.rglob('*')) + list(ROOT.glob('tests/native-research-round5*'))
    paths += list(RESEARCH.glob('native-application-round5-*'))
    index_path = RESEARCH / 'native-application-round5-index.json'
    records = []
    for path in sorted(set(paths)):
        if path.is_file() and path != index_path:
            records.append({'path': str(path.relative_to(ROOT)), 'sha256': digest(path)})
    write(index_path, {'status': summary['status'], 'report': 'native-application-round5-report.md',
                       'records': records, 'no_campaign_completion_claim': True})
    print(json.dumps({'status': summary['status'], 'groups': summary['final_contract_groups'],
                      'historical_hashed_records_checked': len(historical)}))


if __name__ == '__main__':
    main()
