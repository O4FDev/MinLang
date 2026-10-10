#!/usr/bin/env python3
"""Derive bounded round8 summary; immutable cohort records remain untouched."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / 'research/2026-10-memory'
BASE = RESEARCH / 'evidence/native-application-round8'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    cohorts = []
    runs = {}
    for label in ('pilot2', 'followup'):
        runs[label] = json.loads((BASE / label / 'results.json').read_text())
        assert runs[label]['status'] == 'passed_bounded_cohorts'
        for cohort in runs[label]['cohorts']:
            cohorts.append({'label': label, **cohort})
    assert [c['mode'] for c in cohorts] == ['o2', 'o0', 'sanitize']
    reference = {p['name']: p['sha256'] for p in cohorts[0]['outputs']}
    for c in cohorts:
        assert {p['name']: p['sha256'] for p in c['outputs']} == reference
        for output in c['outputs']:
            assert digest(BASE / c['label'] / (c['mode'] + '-outputs') / output['name']) == output['sha256']
    initial = json.loads((BASE / 'output-calibrations/results.json').read_text())
    coherent = json.loads((BASE / 'coherent-output-calibrations/results.json').read_text())
    assert all(c['detected'] for c in initial['controls'] + coherent['controls'])
    pilot_hashes = json.loads((BASE / 'followup-entry-pilot-hashes.json').read_text())
    assert all(digest(ROOT / r['path']) == r['sha256'] for r in pilot_hashes)
    immutable_production = [r for r in runs['followup']['sources'] if r['path'].startswith(('examples/', 'runtime/', 'library/'))]
    assert all(digest(ROOT / r['path']) == r['sha256'] for r in immutable_production)
    assert all(digest(ROOT / r['path']) == r['sha256'] for r in runs['followup']['historical_hashes'])
    assert digest(ROOT / 'build/minyarc') == runs['followup']['compiler_sha256']
    native_rows = [r for run in runs.values() for r in run['commands'] if r['native']]
    compile_rows = [r for run in runs.values() for r in run['commands'] if not r['native']]
    groups = {'texture': ['atlas extent/material placement', 'designed material masks and transparent RGB',
                          'selected exact RGBA pixels', 'icon UV/scaling/polygon coverage', 'unused atlas texels remain zero'],
              'private_scalar': ['periodic tensor-weight values and translated coordinates'],
              'public_atmosphere': ['sky/day/timer state', 'capture order/light/fog/handles',
                                    'cloud exposed-face topology/whole-cell continuity conditional on observed occupancy',
                                    'body and halo geometry/UV/color']}
    summary = {'status': 'bounded_round8_complete', 'campaign_complete': False,
               'production_edits': [], 'native_workload_invocations_completed': len(cohorts),
               'launch_failure_before_module_work': 'pilot1: missing mode argument; exact source/LLVM/runtime diagnostic retained',
               'distinct_contract_group_definitions': groups,
               'distinct_contract_groups': sum(len(v) for v in groups.values()),
               'passing_configuration_groups': sum(c['groups'] for c in cohorts),
               'cohorts': [{'label': c['label'], 'mode': c['mode'], 'groups': c['groups'], 'flags': c['final_flags'],
                            'validations': c['validations'], 'runtime_sha256': c['runtime_sha256'],
                            'binary_sha256': c['binary_sha256'], 'generated_sanitizer': c['generated_sanitizer']} for c in cohorts],
               'all_retained_output_file_hashes_equal_across_modes': True,
               'output_files_per_configuration': len(reference),
               'capture_API_counts_all_configurations': {key: sum(c['validations']['atmosphere']['capture_api_counts'][key] for c in cohorts)
                                                        for key in cohorts[0]['validations']['atmosphere']['capture_api_counts']},
               'counter_scope': 'Test-only native capture API entry calls and serialized vertex/face rows; not graphics-driver calls, instructions, allocations, noise calls or timing.',
               'private_scalar_ABI_calls_all_configurations': sum(c['validations']['periodic']['private_ABI_calls'] for c in cohorts),
               'private_scalar_scope': '735scalar calls per cohort, distinct from ordinary generated module-call ownership coverage; exact fivei64->double emitted signature saved.',
               'separate_native_fatal_seam_control': runs['followup']['fatal_seam_control'],
               'output_calibrations': {'original_controls': initial['control_count'], 'coherent_controls': coherent['control_count'],
                                       'native_module_invocations': 0, 'coherent_target_diagnostics': [r['diagnostic'] for r in coherent['controls']]},
               'final_saved_output_oracle_audit': json.loads((BASE / 'final-oracle-audit/results.json').read_text()),
               'resources': {'native_OS_peak_bytes': max(r['darwin_time_child_peak_bytes'] for r in native_rows),
                             'native_sampled_group_peak_bytes': max(r['sampled_group_peak_bytes'] for r in native_rows),
                             'compiler_OS_peak_bytes': max(r['darwin_time_child_peak_bytes'] for r in compile_rows),
                             'compiler_sampled_group_peak_bytes': max(r['sampled_group_peak_bytes'] for r in compile_rows),
                             'maximum_command_supervised_wall_seconds': max(r['supervised_wall_seconds'] for r in native_rows + compile_rows),
                             'interpretation': 'Darwin time child high-water versus sparse descendant-group RSS sampling; no hard OS cap, exact managed storage, leak or performance claim.'},
               'compiler_sha256': runs['followup']['compiler_sha256'],
               'renderer_sha256': digest(ROOT / 'runtime/native/graphics.c'), 'core_runtime_sha256': digest(ROOT / 'runtime/minyar_runtime.c'),
               'source_preservation': {'pilot1_and_pilot2_records_unchanged': len(pilot_hashes), 'production_dependencies_unchanged': len(immutable_production),
                                       'historical_top_level_records_unchanged': len(runs['followup']['historical_hashes'])},
               'corrections': ['checkpoint-count-resource-correction.json derives82,164calls and0.309491s pilot maximum from exact saved JSON',
                               'Cformat only; pilot C retained and nonwhitespace-equality saved',
                               'final oracle adds both cloud triangle winding/opposite diagonal assertions, validated on retained outputs without module reruns'],
               'limitations': ['No independently predicted cloud density/occupancy: a whole-cell omission can escape conditional topology/continuity.',
                               'No complete atlas noisy palette/ore/cell oracle; periodic equality tests same coordinate +16, not pixel0 versus15 edge equality.',
                               'No complete body frame roll or per-corner UV orientation proof; three selected phases/camera only.',
                               'No exact managed-owner/deferred cleanup/allocation accounting, arbitrary trajectories or continuous/full-game lifetime.',
                               'Test-only float32 vertex packing/native capture: no renderer bodies, real GPU textures/fog/upload/shader/display proof.',
                               'Generated ASan/nativeASan+UBSan only; generatedUBSan andLSan unclaimed, defaultquarantine unchanged.',
                               'Round7 aborted generation is untouched and supplies no completed sanitizer result here.']}
    write_json(RESEARCH / 'native-application-round8-results.json', summary)
    write_json(BASE / 'verification.json', summary['source_preservation'])
    prereg = json.loads((RESEARCH / 'native-application-round8-preregistered.json').read_text())
    inventory = {'source_inventory_documentary_only': prereg['source_inventory'],
                 'documentary_function_entries': sum(len(r['functions']) for r in prereg['source_inventory']),
                 'prior_reports_and_exact_gap_inventory_hashes': prereg['reports_and_exact_gap_inventories'],
                 'selected_gap_map': prereg['selected_gaps'],
                 'actual_public_entrypoints': {'textures.min': ['build', 'iconU', 'iconV'],
                                              'atmosphere.min': ['create', 'advance', 'draw', 'drawClouds']},
                 'executed_dependency_bodies_source_grounded_not_instrumented': {'textures.min': [r['name'] for r in prereg['source_inventory'] if r['path'].endswith('/textures.min') for r in r['functions']],
                     'atmosphere.min': [r['name'] for r in prereg['source_inventory'] if r['path'].endswith('/atmosphere.min') for r in r['functions']],
                     'noise.min': ['hash', 'random', 'fade', 'valueNoise', 'fractalNoise'], 'blocks.min': ['isPlant', 'tile']},
                 'private_ABI_probe': {'function': 'textures.tiled', 'calls_per_cohort': 735, 'emitted_signature': runs['followup']['private_probe']['emitted_signature']},
                 'function_count_limitation': 'Defined-function inventory is documentary. Executed body extent follows fixed public build/control paths; no branch instrumentation or all-branch claim.',
                 'remaining_gaps': summary['limitations']}
    write_json(RESEARCH / 'native-application-round8-inventory.json', inventory)
    print(json.dumps({'status': summary['status'], 'passing_configuration_groups': summary['passing_configuration_groups'],
                      'documentary_function_entries': inventory['documentary_function_entries'], 'resources': summary['resources']}))


if __name__ == '__main__':
    main()
