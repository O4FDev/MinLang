#!/usr/bin/env python3
"""Derive round2 reviewable counts, status, provenance and prose from saved JSON."""
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/2026-10-memory'
EVIDENCE = BASE / 'evidence/native-application-round2'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    matrix = json.loads((EVIDENCE / 'final-matrix/results.json').read_text())
    soak = json.loads((EVIDENCE / 'sustained/results.json').read_text())
    output_controls = json.loads((EVIDENCE / 'oracle-controls/results.json').read_text())
    supplemental = json.loads((EVIDENCE / 'supplemental/results.json').read_text())
    per_configuration = Counter('-'.join(row['label'].split('-')[:2]) for row in matrix['contracts'])
    mesh = [row['evidence'] for row in matrix['contracts'] if row['passed'] and '-mesh-' in row['label']]
    terrain = [row['evidence'] for row in matrix['contracts'] if row['passed'] and row['label'].endswith('-terrain')]
    cohort_rows = []
    for cohort in soak['cohorts']:
        native = cohort.get('final', cohort.get('latest', {}))
        cohort_rows.append({'configuration': cohort['configuration'], 'passed': cohort.get('passed', False),
                            'native': native, 'mesh_api_calls': sum(native.get(key, 0) for key in ('creates', 'deletes', 'updates', 'draw_calls')),
                            'sampled_aggregate_rss_peak_bytes': cohort.get('sampled_aggregate_rss_peak_bytes')})
    application = [row for row in soak['application_replays'] if row.get('passed')]
    native_record_integrity = []
    if soak['status'] == 'passed':
        for cohort in soak['cohorts']:
            log = EVIDENCE / 'sustained' / (cohort['configuration'] + '.ndjson')
            data = log.read_bytes()
            assert data.endswith(b'\n')
            rows = [json.loads(line) for line in data.splitlines()]
            assert rows and rows[-1] == cohort['final']
            for row in rows:
                assert row['mixed_iterations'] == row['batches'] * soak['proposal']['iterations_per_batch']
                assert row['creates'] == row['deletes'] and row['updates'] == row['uploads'] == row['draw_calls']
                assert row['registry_bytes'] == row['registry_peak'] == 4096 and row['realloc_calls'] == 3
                assert row['active'] == row['array_live'] == row['buffer_live'] == 0
            for before, after in zip(rows, rows[1:]):
                assert all(after[key] > before[key] for key in ('batches', 'mixed_iterations', 'wall_seconds', 'cpu_seconds'))
            native_record_integrity.append({'configuration': cohort['configuration'], 'rows': len(rows),
                                            'sha256': digest(log), 'all_complete_and_monotone': True})
    production = []
    prior = json.loads((BASE / 'evidence/native-application/final-expanded/results.json').read_text())
    for relative in ('runtime/native/graphics.c', 'examples/craft/terrain.min', 'examples/craft/meshing.min'):
        original = next(row['sha256'] for row in matrix['sources'] if row['path'] == relative)
        previous = next(row['sha256'] for row in prior['sources'] if row['path'] == relative)
        production.append({'path': relative, 'round2_entry_sha256': original,
                           'current_sha256': digest(ROOT / relative), 'round1_final_sha256': previous,
                           'round2_production_changed': original != digest(ROOT / relative),
                           'matches_round1_final': previous == original})
    summary = {
        'status': 'passed' if matrix['status'] == soak['status'] == 'passed' else soak['status'],
        'matrix': {'status': matrix['status'], 'contracts': len(matrix['contracts']),
                   'passed': sum(row['passed'] for row in matrix['contracts']),
                   'failures': matrix['failures'], 'contracts_per_configuration': dict(per_configuration),
                   'configurations': len(per_configuration), 'calibrations': len(matrix['calibrations']),
                   'calibrations_detected': sum(row['detected'] for row in matrix['calibrations']),
                   'calibration_details': matrix['calibrations'],
                   'actual_mixed_mesh_iterations': sum(row['mixed_iterations'] for row in mesh),
                   'actual_mesh_api_calls': sum(row[key] for row in mesh for key in ('creates', 'deletes', 'updates', 'draw_calls')),
                   'mesh_seed_traces': len(mesh), 'mesh_trace_hashes': sorted({row['trace_hash'] for row in mesh}),
                   'terrain_events': sum(row['events'] for row in terrain),
                   'terrain_vertices': sum(sum(row['vertices'].values()) for row in terrain),
                   'one_terrain_replay': terrain[0],
                   'terrain_snapshot_hashes': sorted({row['snapshots_sha256'] for row in terrain}),
                   'native_peak_rss_bytes': max(row['peak_rss_bytes'] for row in mesh),
                   'sanitizer_coverage': matrix['sanitizer_coverage']},
        'soak': {'status': soak['status'], 'cohorts': cohort_rows,
                 'actual_mixed_mesh_iterations': sum(row['native'].get('mixed_iterations', 0) for row in cohort_rows),
                 'actual_mesh_api_calls': sum(row['mesh_api_calls'] for row in cohort_rows),
                 'passed_application_replays': len(application),
                 'actual_terrain_events': sum(row['oracle']['events'] for row in application),
                 'actual_terrain_vertices': sum(sum(row['oracle']['vertices'].values()) for row in application),
                 'resource_accounting': soak.get('resource_accounting'),
                 'source_checks': len(soak['source_checks']),
                 'source_check_failures': [row for row in soak['source_checks'] if row['changed']]},
        'native_record_integrity': native_record_integrity,
        'sanitizers': matrix['sanitizers'], 'proposal': 'native-application-round2-soak-preregistered.json',
        'output_oracle_controls': {'status': output_controls['status'], 'controls': len(output_controls['controls']),
                                   'detected': output_controls['detected'], 'details': output_controls['controls']},
        'supplemental': {'status': supplemental['status'], 'png_open_failure_contracts': len(supplemental['contracts']),
                         'passed': supplemental['contracts_passed'],
                         'formatter_version': next(row['stdout'].strip() for row in supplemental['commands'] if row['label'] == 'formatter-version'),
                         'source_unchanged_from_final_matrix': all(row['unchanged'] for row in supplemental['source_unchanged_from_final_matrix'])},
        'production_provenance': production,
        'remaining_gaps': [
            {'topic': 'PNG dimension/size arithmetic and encoded chunk limits',
             'sources': ['runtime/native/graphics.c:398', 'runtime/native/graphics.c:411'],
             'extent': 'Small staged OOM/retry/open-failure controls do not prove huge products, signed pixel offsets or encoded length limits.'},
            {'topic': 'Actual GPU/display/shader integration',
             'sources': ['runtime/native/graphics.c:290', 'runtime/native/graphics.c:699'],
             'extent': 'Typed headless seams cannot prove actual driver object lifetime, shader output, readback or real frame behavior.'},
            {'topic': 'Distinct GL namespace identity calibration',
             'sources': ['tests/native-research-round2.c:118', 'tests/native-research-round2.c:129', 'tests/native-research-round2.c:315'],
             'extent': 'Both fake object generators start at1; expected array/buffer values coincide and may hide a wrong-field bind. The one-mesh array1/buffer513 control remains proposed, unexecuted.',
             'proposal': 'native-application-round2-gl-namespace-proposal.json'},
            {'topic': 'Other source-grounded native/application computations',
             'sources': ['runtime/native/graphics.c:78', 'runtime/native/graphics.c:750',
                         'examples/craft/terrain.min:284', 'examples/craft/physics.min:58',
                         'examples/craft/textures.min:513', 'examples/craft/atmosphere.min:175'],
             'extent': 'General matrix math; overlay/glyph/line batching and translucent GL state; full terrain generation and other materials; collision/movement/water/flight/aim ties; texture/icon/cloud computations are not covered by this round.'},
            {'topic': 'Continuous application lifetime and save/load behavior',
             'sources': ['tests/native-research-round2.min', 'examples/craft/save.min:11'],
             'extent': 'The native process retains its registry/buffer across batches, but each terrain replay creates a fresh prepared world; public application save/load and full owner/deferred cleanup accounting are not certified.'}],
        'limitations': [
            'Headless typed GL seams verify CPU ABI calls and consume borrowed data during upload; no display, shader or GPU lifetime proof.',
            'PNG OOM controls exercise fatal stop, no reads/files and exact diagnostic; successful staging memory remains live until process exit, so no OOM recovery or leak claim.',
            'Native registry counters cover requested registry bytes and mock GL object counts; they are not core runtime live-object accounting.',
            'Default ASan quarantine is unchanged. LSan is disabled. Native C ASan+UBSan and generated ASan remain separate; generated UBSan is not claimed.',
            'Source-frozen terrain trace covers only five materials in a prepared 64x64x16 world; no whole-game, world-generation or save/load completeness claim.',
            'Triangle geometry, UV endpoint coverage, ambient/directional colors and sky/glow are independently checked. UV-to-corner orientation and diagonal selection are not exact packing oracles.',
            'Dense-prefix adversary retains a linear scan; the hint is not a constant worst-case handle-allocation guarantee.',
            'RSS is sampled supporting evidence plus native getrusage peak; aggregate polling is not an operating-system-enforced memory reservation.',
            'External host CPU load remains. CPU/wall observations account for resources; no quiet-host speedup, throughput or latency claim.',
            'Very large PNG arithmetic/chunk ceiling, other renderer paths and real GPU behavior remain unverified.'],
        'records': [{'path': str(path.relative_to(BASE)), 'sha256': digest(path)} for path in
                    [EVIDENCE / name / 'results.json' for name in ['pilot1', 'pilot2', 'sanitizer-pilot', 'matrix',
                     'paced-short-pilot', 'final-matrix', 'final-paced-pilot', 'sustained', 'oracle-controls', 'supplemental']]],
        'earlier_evidence_policy': 'Prior pilots, fixture compilation failure, calibrations and round1 transcription corrections are preserved without overwriting.'}
    for path in [BASE / 'native-application-round2-gl-namespace-proposal.json',
                 EVIDENCE / 'sustained/process-lifecycle.json']:
        summary['records'].append({'path': str(path.relative_to(BASE)), 'sha256': digest(path)})
    (BASE / 'native-application-round2-results.json').write_text(json.dumps(summary, indent=2) + '\n')
    index = {'status': summary['status'], 'report': 'native-application-round2-report.md',
             'machine_summary': 'native-application-round2-results.json', 'records': summary['records'],
             'proposal': summary['proposal'], 'round1': 'native-application-index.json'}
    (BASE / 'native-application-round2-index.json').write_text(json.dumps(index, indent=2) + '\n')
    lines = [
        f"Round2 native/application validation is **{summary['status']}**. The final frozen matrix passed "
        f"{summary['matrix']['passed']}/{summary['matrix']['contracts']} contracts in "
        f"{summary['matrix']['configurations']} configurations; "
        f"{summary['matrix']['calibrations_detected']}/{summary['matrix']['calibrations']} deliberately broken source controls were detected.",
        'This lane added tests and research evidence only. No production edits, core runtime/compiler/launcher/build changes, commits or resets were made. '
        'The three lane production source hashes match the prior round and the saved entry snapshot. '
        'Exact entry dirty patches and status are retained alongside every matrix snapshot.',
        'Each configuration tests three distinct PNG staging allocation failures, six deferred zero frames followed by a successful 8x8 PNG retry, '
        'four seeded mesh traces with valid uploads/draws/clear/refill and fragmented handle churn, and one real terrain edit/remesh/upload trace. '
        'PNG failures report the exact memory diagnostic, leave the screenshot request pending, and perform no pixel reads or file open/write. '
        'Other successful staging allocations remain live until fatal process exit; this is explicitly not recoverability or leak evidence.',
        f"The matrix executed {summary['matrix']['actual_mixed_mesh_iterations']:,} mixed mesh iterations over "
        f"{summary['matrix']['mesh_seed_traces']} executions and {summary['matrix']['actual_mesh_api_calls']:,} actual mesh API calls including the directed prefix and drains. "
        'The independent occupied bitmap searches from slot zero. Typed GL seams separately validate layout, object association, upload length/hash and draw vertex count. '
        'Clear/refill never leaves a pointer retained by the seam. Registry growth is bounded at 256 slots/4096 requested bytes/three reallocations, '
        'with 512 mock GL objects maximum and zero after drain. Restoring the first handle then creating beyond a dense 128-slot prefix still checks 127 occupied slots; '
        'the optimization retains linear worst-case scans.',
        f"One terrain replay has {terrain[0]['events']} edits ({terrain[0]['event_kinds']['changed']} changes, "
        f"{terrain[0]['event_kinds']['unchanged']} unchanged writes, {terrain[0]['event_kinds']['outside']} outside controls), "
        f"{terrain[0]['vertices']['solid']:,} solid and {terrain[0]['vertices']['water']:,} water vertices. "
        'Every event compares all 65536 block bytes, 4096 column tops, 1024 dirty slots and exact distinct torch membership against an independent byte/set/rectangle model. '
        'The mesh oracle checks complete rectangle-face multisets, outward triangle winding, cube/water/torch bounds, atlas endpoints and four-corner UV coverage, '
        'exact ambient/directional RGB, sky light and distance-based glow. It allows either diagonal and does not certify exact UV-to-corner orientation. '
        f"The matrix checked {summary['matrix']['terrain_events']:,} actual event snapshots and "
        f"{summary['matrix']['terrain_vertices']:,} vertex rows. All configuration snapshot hashes match.",
        'Calibrations restore the original minimized-frame and repeated-placement behavior, bypass PNG OOM checks, remove mesh deletion hint maintenance, '
        'corrupt upload size/draw count, corrupt column tops/torch dirty reach, omit bottom faces, alter ambient brightness and alter atlas inset. '
        'Native assertion/trap exits and exact independent terrain mismatch diagnostics are saved. The first fixture compile failure is retained separately at pilot1; '
        'its GL stub naming collision and Darwin resource-header visibility were fixed only in the new fixture.',
        f"Separate saved output controls detected {output_controls['detected']}/{len(output_controls['controls'])} corruptions of "
        'block contents, column tops, dirty membership, duplicate torches, vertex positions, atlas UVs, ambient RGB, sky, glow and triangle winding. '
        'These are distinct oracle calibration cases and are not added to source-mutation or matrix execution counts. '
        f"The supplemental native run passed {supplemental['contracts_passed']}/{len(supplemental['contracts'])} exact PNG file-open failure controls "
        'across the same configurations without rebuilding. Each creates no file, emits the exact creation-error diagnostic, records one read and one failed open, '
        'and no writes/closes. As with OOM, staged memory remains live only until fatal process exit. '
        'Pinned ClangFormat 23.1.2, owned Python syntax and Git whitespace checks passed, and all matrix source hashes still match.',
        'The sustained run uses the saved preregistered resource thresholds and abort rules. O2 and native ASan+UBSan cohorts run serially for the requested duration, '
        'with active verified batches paced toward five percent of one CPU. Real generated terrain replays at scheduled checkpoints run while the native worker is suspended. '
        'The native process and its borrowed buffer/registry remain alive across batches; the application replay starts a fresh bounded world each time.',
        '| Cohort | Status | Actual wall s | Native CPU s | Mixed iterations | Mesh API calls | Native peak RSS bytes |\n'
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    table_rows = []
    for row in cohort_rows:
        data = row['native']
        table_rows.append(f"| {row['configuration']} | {'passed' if row['passed'] else 'running'} | "
                          f"{data.get('wall_seconds', 0):.3f} | {data.get('cpu_seconds', 0):.3f} | "
                          f"{data.get('mixed_iterations', 0):,} | {row['mesh_api_calls']:,} | {data.get('peak_rss_bytes', 0):,} |")
    lines[-1] += '\n' + '\n'.join(table_rows)
    lines += [
        f"The saved sustained records currently contain {summary['soak']['passed_application_replays']} passed application replays, "
        f"{summary['soak']['actual_terrain_events']:,} independently checked events and {summary['soak']['actual_terrain_vertices']:,} vertex rows. "
        f"Source checks performed: {summary['soak']['source_checks']}; changed-source reports: {len(summary['soak']['source_check_failures'])}.",
        '`ASAN_OPTIONS=detect_leaks=0:abort_on_error=1`; `UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1`. '
        'ASan default quarantine is untouched. Every sanitizer configuration has 96/96 generated ASan-attributed definitions. '
        'Generated UBSan and LSan are not claimed. RSS sampling supports the explicit input/storage bounds and does not prove all runtime live objects.',
        'Headless CPU evidence does not establish real GPU ownership, rendering/shader correctness, frame times or whole-game performance. '
        'Large PNG arithmetic/chunk ceilings, other materials, world generation and save/load remain outside this evidence. '
        'External host load persists and all CPU/wall values are resource observations, with no accepted timing comparison.',
        'Explicit remaining gaps for distinct follow-up:\n\n'
        '- PNG dimension/size arithmetic and encoded chunk limits (`graphics.c`, `png_chunk`/`write_screenshot`).\n'
        '- Actual GPU/display/shader/driver behavior, including translucent state and real readback.\n'
        '- GL namespace hypothesis: both fake generators start at1, so arrays/buffers get coincident values. '
        '`bound_buffer == expected[slot].buffer` and `buffers[name].used` may miss an array-valued bind. '
        'The smallest independent control uses one array1/buffer513,120-byte triangle upload/draw/delete plus a saved-copy wrong-field mutation. '
        '[The prepared proposal](native-application-round2-gl-namespace-proposal.json) is explicitly unexecuted and outside this cohort.\n'
        '- Other source-grounded computations: general matrix math; overlay/glyph/line buffers; terrain generation/other materials; '
        'physics collisions/movement/water/flight/aim ties; texture/icon and atmosphere cloud generation.\n'
        '- Continuous terrain/application lifetime, public save/load and full runtime owner/deferred cleanup accounting: '
        'terrain checkpoint processes restart their prepared world, while only native registry/borrowed buffer state persists across the soak.',
        'Reproduce a new matrix in an unused label:',
        '```sh\npython3 tests/native-research-round2.py --label replay-round2 --profiles eager system fixed lazy --modes o0 o2 sanitize --calibrate\n```',
        'Prepare and review a new resource proposal before starting a new sustained run; the soak tool requires an exact matching passing matrix. '
        'Binaries, large application output snapshots and LLVM stay disposable in build/native-research-round2. '
        'Durable evidence retains frozen sources, compiler/source/instrumentation hashes, exact commands/errors, small binary/JSON input trace, '
        'mutation anchors/hashes, native checkpoint NDJSON and all derived summaries.',
        '[Machine counts and provenance](native-application-round2-results.json), '
        '[matrix](evidence/native-application-round2/final-matrix/results.json), '
        '[sustained records](evidence/native-application-round2/sustained/results.json), '
        '[resource proposal](native-application-round2-soak-preregistered.json).']
    if soak.get('resource_accounting'):
        resources = soak['resource_accounting']
        aggregate_fraction = (resources['child_cpu_seconds'] + resources['coordinator_cpu_seconds']) / resources['wall_seconds']
        summary['soak']['resource_accounting']['aggregate_cpu_fraction_of_one_core'] = aggregate_fraction
        summary['soak']['resource_accounting']['scope'] = 'Child CPU includes native workers, generated application replays and ps sampling; coordinator CPU is separate.'
        lines.insert(-1, f"Native worker pacing is separate from monitoring/application overhead. Saved child CPU is "
                     f"{resources['child_cpu_seconds']:.3f}s (workers, terrain replays and ps sampling), coordinator CPU "
                     f"{resources['coordinator_cpu_seconds']:.3f}s, over {resources['wall_seconds']:.3f}s wall; "
                     f"their combined resource average is {aggregate_fraction * 100:.2f}% of one core. "
                     'This is resource accounting, not a latency or throughput measurement. '
                     'All completed native NDJSON rows parse completely, increase monotonically and match the final saved cohort records. '
                     '[Process lifecycle evidence](evidence/native-application-round2/sustained/process-lifecycle.json) '
                     'retains the actual sanitizer transition start at one-second ps resolution.')
        (BASE / 'native-application-round2-results.json').write_text(json.dumps(summary, indent=2) + '\n')
    (BASE / 'native-application-round2-report.md').write_text('\n\n'.join(lines) + '\n')
    print(json.dumps({'status': summary['status'], 'matrix_contracts': summary['matrix']['contracts'],
                      'soak_cohorts': len(cohort_rows), 'report': str(BASE / 'native-application-round2-report.md')}, indent=2))


if __name__ == '__main__':
    main()
