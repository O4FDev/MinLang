"""Finalize this lane's report and before/after hash checkpoint only."""
from pathlib import Path
import datetime
import hashlib
import json

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
R = ROOT / 'research/2026-10-memory'

def read(path):
    return json.loads(path.read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

manifest = read(OUT / 'inputs.json')
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
changes = []
checked = []
for entry in manifest['files']:
    snapshot = OUT / entry['snapshot']
    assert sha(snapshot) == entry['sha256']
    original = ROOT / entry['path']
    after = sha(original) if original.exists() else None
    row = {'path': entry['path'], 'before_sha256': entry['sha256'], 'after_sha256': after,
           'snapshot_matches': True, 'original_unchanged': after == entry['sha256']}
    checked.append(row)
    if not row['original_unchanged']:
        changes.append(row)
checkpoint = {'completed_utc': now, 'input_files_checked': len(checked),
              'all_frozen_copies_match': True, 'live_input_changes': changes, 'files': checked}
(OUT / 'finish-checkpoint.json').write_text(json.dumps(checkpoint, indent=2) + '\n')
stats = read(OUT / 'reanalysis.json')
provenance = read(OUT / 'provenance-verification.json')
documentary = read(OUT / 'documentary-verification.json')
correction = read(OUT / 'owner-correction-checkpoint.json')
for entry in correction['files']:
    assert sha(OUT / entry['snapshot']) == entry['sha256']
finding = [
    {'id': 'F1', 'severity': 'medium', 'type': 'build_scope_deviation',
     'finding': 'MINYAR_RC_TESTING=1 retains object/byte/system-allocation accounting and cleanup telemetry in all timing builds.',
     'custom_observers_enabled': False, 'sanitizers_enabled': False, 'lto_enabled': False,
     'effect': 'Original no-counters wording is inaccurate; no accounting-free production ratio or complete preregistered build compliance.',
     'root_notified': True, 'root_acknowledged': True,
     'resolution': 'Accept current observations only with actual test-accounted primitive scope; preserve original evidence, no replacement acquisition authorized.'},
    {'id': 'F2', 'severity': 'medium', 'type': 'inference_limit',
     'finding': 'System empty passes point-estimate controls but its geometric interval does not establish 3% noninferiority.',
     'candidate_point_cpu_increase': stats['summaries'][0]['candidate_point_cpu_change'],
     'candidate_geometric_cpu_change_interval95': stats['summaries'][0]['inverted_interval_candidate_cpu_change'],
     'resolution': 'Retain all adverse rows, estimators and order/half-run sensitivity; no supported guarantee of less than3% regression.'},
    {'id': 'F3', 'severity': 'low', 'type': 'provenance_limit',
     'finding': 'Four executables/two objects were removed after owner hashing; reviewer verifies saved listings and documentary hash correspondence, not deleted bytes.',
     'external_environment': 'Clang version, SDK/linker paths and /usr/bin/clang hash are saved; full selected toolchain/SDK/linker bytes and environment are not.',
     'resolution': 'No hermetic reproduction or fresh independent executable hash check claimed.'},
    {'id': 'F4', 'severity': 'low', 'type': 'exploratory_amendment',
     'finding': 'Two capped-short baseline pilot cohorts caused disclosed, separately authorized repeat-ceiling increases before any paired observations.',
     'resolution': 'All original attempts, source/proposal revisions and changed freeze-metadata recording preserved; thresholds/caps unchanged.'}
]
report = {
    'status': 'completed saved-evidence audit; conditional acceptance within actual test-accounted scope',
    'completed_utc': now, 'reviewer_model': 'GPT-6.1 Sol', 'reasoning_effort': 'high',
    'decision': {'current_cohort': 'conditionally approve exact isolated test-accounted primitive performance observations',
                 'numerical_usefulness_gates_passed': True, 'accounting_free_build_requirement_met': False,
                 'all_preregistration_conditions_certified': False,
                 'accounting_free_production_speed_claim': 'reject from these rows',
                 'production_adoption_authorized': False, 'campaign_complete': False,
                 'new_acquisition_authorized': False},
    'findings': finding,
    'identities': {k: provenance[k] for k in ['candidate_patch_sha256', 'baseline_collections_sha256',
                                            'candidate_collections_sha256', 'runtime_c_sha256']},
    'raw_final_result': {'path': 'research/2026-10-memory/evidence/runtime-list-bulk-cpu/run-ws0ma9zu/results.json',
                         'sha256': sha(OUT / 'inputs/research/2026-10-memory/evidence/runtime-list-bulk-cpu/run-ws0ma9zu/results.json')},
    'coverage': {'paired_cases': 16, 'blocks_per_case': 12, 'pairs': 192, 'paired_children': 384,
                 'final_baseline_pilot_attempts': 203, 'native_final_records_checked': 587,
                 'all_acquisition_operations': 606, 'untimed_calibration_observations': 32,
                 'published_summary_fields_recomputed_exactly': True, 'seeded_plan_exactly_reproduced': True,
                 'final_stdout_argv_checksums_recovery_records_checked': True,
                 'machine_code_builds_inspected': 4, 'surviving_freeze_files_rehashed': 47,
                 'removed_executables_objects_owner_hash_records_only': 6,
                 'archive_indices': provenance['archive_indices'],
                 'calibration_index_files_rehashed': documentary['calibration_archive_files_verified'],
                 'frozen_input_files': len(checked)},
    'estimators': {'primary': 'exp(mean(log(baseline_cpu_ns/candidate_cpu_ns))) within case',
                   'pointwise_pair_resamples': 10000, 'seed_reset_per_case': 0x6b17,
                   'sorted_zero_based_interval_endpoints': [249, 9749],
                   'alternative': ['paired median with interval', 'ratio of summed batch CPU',
                                   'first six/last six geometric ratios', 'AB/BA order strata'],
                   'not_claimed': ['joint confidence guarantee', 'independent-host replication',
                                   'population tail or noninferiority bound', 'workload-weighted cross-case effect']},
    'summaries': stats['summaries'], 'all_adverse_rows': stats['adverse_rows'],
    'all_raw_pairs': 'evidence/runtime-scalar-bulk-performance-audit/reanalysis.json#/rows',
    'pilots': stats['pilot_summary'], 'amendments': provenance['amendments'],
    'resources': {**stats['resources'],
                  'source_child_cpu_rlimit_seconds': 5, 'source_child_file_rlimit_bytes': 8388608,
                  'child_timeout_seconds': 'min(10,remaining runner deadline)',
                  'completed_native_rss_limit_bytes': 134217728,
                  'runner_aggregate_cpu_limit_seconds': 180, 'runner_wall_limit_seconds': 600,
                  'continuous_aggregate_cpu_enforcement': False, 'continuous_rss_enforcement': False,
                  'darwin_taskpolicy': 'memory pressure policy -m128; not hard RSS bound',
                  'stdout_pipe_bounded_by_fsize': False,
                  'outer_wrapper_independently_observed': False},
    'source_and_machine_code': {
        'runtime_pair_only_collections_different': True, 'exact_patch_diff_verified': True,
        'all_common_test_helper_sources_equal': True,
        'bulk_gate': 'fresh truthful scalar, protected source, post-common-header all-task pending_count zero captured before unchanged n+1 reserve',
        'prefix': 'copy initialized nonoverlapping n*8 bytes only if n>0, then publish length n; unchanged tail add/take',
        'reference_and_initial_debt': 'old loop; no new allocation/service policy',
        'opaque_checksum': 'separate noinline TU, ordinary O2 object link without LTO; loaded word XOR/multiply loop survives in all four linked listings',
        'copy_and_fallback_machine_code': provenance['machine_code'],
        'accounting_scope_evidence': 'evidence/runtime-scalar-bulk-performance-audit/accounting-scope.json',
        'accounting_eligibility_effect': 'test fields do not feed bulk eligibility; ordinary rc_pending_count and references do',
        'accounting_cost_inference': 'equal logical bookkeeping cannot be subtracted or assumed to cancel to infer accounting-free speed'},
    'oracle_scope': {
        'per_iteration': 'result pointer/length checks plus opaque full-word unsigned hash comparison, release/drain',
        'independent_expected': 'Python literal seed/tail/reference normalization modulo2^64 plus exact accumulated XOR',
        'integer_overflow': 'uint64_t arithmetic wraps by definition; memcpy bit transport on supported ABI',
        'reference_normalization': 'every slot loaded and compared with shared pointer; expected word1 independent of ASLR',
        'hash_limit': 'full reader/digest, not collision-free exhaustive per-word proof for every timed result',
        'final_control_outside_clock': 'all source/prefix words, exact tail, backing independence, result mutation preserving source, retained owner and accounting/pool recovery',
        'timing_does_not_validate': ['allocation/poll event arrays', 'every intermediate full-word dump',
                                    'both-direction mutation coverage', 'all generated caller lifetimes'],
        'untimed_calibration': '32 rows; object pending1/reference32 retained; fixed debt backing move copies2/192 bytes equal, not fast prefix',
        'supplemental_provenance_reconciliation': 'separate retained correction read, earlier review unchanged; formatter not rerun here'},
    'scope': {
        'timed': 'process CPU append, checks/assertions, opaque full checksum, unsigned accumulation, release/drain and test accounting; object debt construction inside',
        'outside_clock': 'source/shared Text construction, initial drain, final full-value/mutation/recovery control and stdout',
        'input_reuse': 'one source per fresh child, repeated hot input/fresh results',
        'host': 'single external-loaded host and paced system soak; no quiet-host claim or independent host census',
        'allowed_claim': 'Exact isolated test-accounted primitive workload passes stated numerical usefulness/control thresholds with reported ratios/pointwise intervals and all adverse rows retained.',
        'excluded_claims': ['accounting-free production ratio', 'application prevalence or hot-path benefit',
                            'compiler or whole-language speed', 'fewer logical prefix bytes', 'memory footprint benefit',
                            'isolated memcpy speed', 'latency/HFT guarantee', 'novel collector', 'joint formatted runtime performance']},
    'pending_gates': ['Root system-soak successful normal final recovery/source identity and source-freeze release',
                      'Generated/temporary/active caller source-protection controls',
                      'Exact combined scalar/aggregate formatted final-source identity and applicable focused native/generated/Text checks',
                      'Coordinator-owned archive reproduction/final adoption decision'],
    'unchanged_prior_gates': 'CPU approval does not discharge source-review caller/generated/final-source premises; both soaks cover pre-adoption source.',
    'campaign_earliest_finish_utc': '2026-10-04T06:54:29Z',
    'actions': {'native_execution': False, 'new_measurements': False, 'compiler_or_llvm_execution': False,
                'rebuilds': False, 'plots_regenerated': False, 'production_test_build_edits': False,
                'installations': False, 'commits_or_resets': False, 'subagents': False,
                'blocked_lanes_restarted': False},
    'input_manifest': {'path': 'evidence/runtime-scalar-bulk-performance-audit/inputs.json',
                       'sha256': sha(OUT / 'inputs.json'),
                       'sha256_lines_path': 'evidence/runtime-scalar-bulk-performance-audit/inputs.sha256'},
    'finish_checkpoint': {'path': 'evidence/runtime-scalar-bulk-performance-audit/finish-checkpoint.json',
                          'sha256': sha(OUT / 'finish-checkpoint.json'),
                          'all_frozen_copies_match': True, 'live_input_changes': changes},
    'owner_correction_checkpoint': {'path': 'evidence/runtime-scalar-bulk-performance-audit/owner-correction-checkpoint.json',
                                    'sha256': sha(OUT / 'owner-correction-checkpoint.json'),
                                    'late_input_files': len(correction['files']),
                                    'six_original_derived_figure_artifacts_preserved_exactly': True,
                                    'current_derived_numeric_summaries_unchanged': True,
                                    'new_production_fixture_validation_or_measurement_certified': False},
    'human_report_sha256': sha(R / 'runtime-scalar-bulk-performance-audit.md')
}
(R / 'runtime-scalar-bulk-performance-audit.json').write_text(json.dumps(report, indent=2) + '\n')
artifacts = []
for p in sorted(OUT.rglob('*')):
    if p.is_file() and p.name != 'audit-artifacts.json' and 'inputs' not in p.relative_to(OUT).parts:
        artifacts.append({'path': str(p.relative_to(ROOT)), 'sha256': sha(p), 'bytes': p.stat().st_size})
for p in [R / 'runtime-scalar-bulk-performance-audit.md', R / 'runtime-scalar-bulk-performance-audit.json']:
    artifacts.append({'path': str(p.relative_to(ROOT)), 'sha256': sha(p), 'bytes': p.stat().st_size})
(OUT / 'audit-artifacts.json').write_text(json.dumps({'created_utc': now, 'files': artifacts}, indent=2) + '\n')
print(json.dumps({'completed_utc': now, 'inputs': len(checked), 'live_input_changes': changes,
                  'report_json_sha256': sha(R / 'runtime-scalar-bulk-performance-audit.json')}))
