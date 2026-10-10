"""Read saved external execution documents; never import or execute tests."""
from pathlib import Path
import datetime
import hashlib
import json

B = Path('evidence/peer-readonly/values-round5')
manifest = json.loads((B / 'latest-runtime-manifest.json').read_text())
checks = []

def check(name, condition):
    checks.append({'name': name, 'passed': bool(condition)})
    assert condition, name

for record in manifest:
    data = Path(record['snapshot']).read_bytes()
    check('snapshot_hash:' + record['path'], hashlib.sha256(data).hexdigest() == record['sha256'])

def saved(suffix):
    return Path(next(r['snapshot'] for r in manifest if r['path'].endswith(suffix)))

results = json.loads(saved('/results.json').read_text())
provenance = json.loads(saved('/provenance.json').read_text())
check('external_run_passed', results['status'] == 'passed')
check('external_run_commands_returned_zero', all(c['returncode'] == 0 for c in results['checks']))
check('results_and_provenance_summaries_agree', results['summary'] == provenance['summary'])
check('four_projection_provenance_entries', len(provenance['source_to_test']) == 4)
names = {p['original_test'] for p in provenance['source_to_test']}
execution_count = 0
for configuration in ['system-k32', 'fixed-k1', 'system-k32-sanitize']:
    coverage = json.loads(saved('/' + configuration + '-coverage.json').read_text())
    observed = coverage['observed']
    check(configuration + ':successful_four_methods', coverage['successful'] and coverage['tests_run'] == len(observed) == 4)
    check(configuration + ':provenance_names_match', {c['test'].split('.')[-1] for c in observed} == names)
    check(configuration + ':both_optimization_records', all(c['linked_optimizations'] == ['O0', 'O2'] for c in observed))
    if configuration.endswith('sanitize'):
        check(configuration + ':all_generated_definitions_asan', all(c['generated_definitions'] == c['asan_definitions'] > 0 for c in observed))
    execution_count += sum(len(c['linked_optimizations']) for c in observed)
check('derived_twenty_four_external_executions', execution_count == 24 == results['summary']['generated_executions'])
fixture = saved('/tests/memory-research-peer-projections.py').read_bytes()
fixture_record = next(r for r in results['sources'] if r['snapshot'] == 'tests/memory-research-peer-projections.py')
check('external_test_snapshot_matches_results_hash', hashlib.sha256(fixture).hexdigest() == fixture_record['sha256'])
report = {
    'schema': 'minyar.peer_readonly_values.latest_runtime_document_checks.v1',
    'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'status': 'consistent',
    'method': 'Documentary reading of saved external records only; no test import, compilation or execution in round5.',
    'external_run': 'research/2026-10-memory/evidence/runtime-peer-projections/run-crettoqb',
    'derived_external_counts': {'test_methods': len(names), 'configurations': 3, 'generated_executions': execution_count},
    'new_round5_proposals': {'P1': 'NaN comparison and negation matrix', 'P2': 'Source underflow bit boundary', 'P3': 'Cross-32-bit explicit masks'},
    'deduplication': 'The four external methods observe Bytes sharing/copying, row alias/snapshot retention, literal effects/order, and iterable producer/body retention. They assert no NaN relational/negation matrix, no neighboring half-minimum source literals, and no cross-32-bit masks. Round5 proposals remain proposals; no new execution credit.',
    'limits': 'External generated ASan and runtime C ASan/UBSan only; no generated UBSan, LSan, timing or peer feature equivalence claim.',
    'checks': checks,
}
(B / 'latest-runtime-document-checks.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'status': report['status'], 'checks': len(checks), 'external_counts': report['derived_external_counts']}))
