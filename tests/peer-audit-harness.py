#!/usr/bin/env python3
"""Reject false audit completion using small controlled ledgers."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('peer_audit', ROOT / 'tools/check-peer-audit.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AuditHarness(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for language in audit.LANGUAGES:
            directory = self.root / language
            directory.mkdir()
            inventory = dict(schema_version=1, repo='example/' + language, sha='frozen',
                             files=[dict(path='test', sha256='hash', status='reviewed')],
                             total=1, reviewed=1, discovery_complete=True,
                             case_enumeration_complete=True)
            (directory / 'inventory.json').write_text(json.dumps(inventory))
            row = dict(language=language, repo=inventory['repo'], revision='frozen',
                       path='test', source_sha256='hash', case_id='assertion', lines=[1, 1],
                       disposition='covered', reason='Controlled fixture', implementation_needed=False)
            self.write_rows(directory / 'decisions.jsonl', [row])

    def write_rows(self, path, rows):
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))

    def mutate_inventory(self, **updates):
        path = self.root / 'python/inventory.json'
        row = json.loads(path.read_text())
        row.update(updates)
        path.write_text(json.dumps(row))

    def test_complete_control_and_pending_discovery(self):
        self.assertTrue(audit.inspect(self.root)['complete'])
        self.mutate_inventory(discovery_complete=False)
        self.assertFalse(audit.inspect(self.root)['complete'])

    def test_pending_file_cannot_be_hidden_by_declared_count(self):
        self.mutate_inventory(files=[dict(path='test', sha256='hash', status='pending')])
        report = audit.inspect(self.root)
        self.assertFalse(report['complete'])
        self.assertTrue(report['errors'])

    def test_reviewed_file_requires_case_or_support_explanation(self):
        (self.root / 'python/decisions.jsonl').write_text('')
        self.assertTrue(audit.inspect(self.root)['errors'])
        self.mutate_inventory(files=[dict(path='test', sha256='hash', status='reviewed',
                                         no_tests=True, scope_disposition='support',
                                         review_reason='Empty fixture consumed by import case')])
        self.assertTrue(audit.inspect(self.root)['complete'])

    def test_missing_case_enumeration_blocks_completion(self):
        self.mutate_inventory(case_enumeration_complete=False)
        report = audit.inspect(self.root)
        self.assertFalse(report['complete'])
        self.assertFalse(report['errors'])

    def test_deferred_disposition_blocks_completion_after_source_review(self):
        path = self.root / 'python/decisions.jsonl'
        row = json.loads(path.read_text())
        row.update(disposition='defer', implementation_needed=False,
                   reason='Source read; applicability decision still unresolved')
        self.write_rows(path, [row])
        report = audit.inspect(self.root)
        self.assertFalse(report['errors'])
        self.assertFalse(report['complete'])
        self.assertEqual(report['languages'][0]['deferred_decisions'], 1)

    def test_implementation_needs_matching_evidence(self):
        path = self.root / 'python/decisions.jsonl'
        row = json.loads(path.read_text())
        row.update(disposition='adapt', implementation_needed=True)
        self.write_rows(path, [row])
        self.assertFalse(audit.inspect(self.root)['complete'])
        resolution = {key: row[key] for key in audit.KEYS}
        self.write_rows(self.root / 'implementations.jsonl', [resolution])
        self.assertTrue(audit.inspect(self.root)['errors'])
        resolution.update(tests=['tests/peer-audit-harness.py:AuditHarness.test_implementation_needs_matching_evidence'],
                          validation=['controlled-pass'])
        self.write_rows(self.root / 'implementations.jsonl', [resolution])
        self.assertTrue(audit.inspect(self.root)['complete'])
        resolution['source_sha256'] = row['source_sha256']
        self.write_rows(self.root / 'implementations.jsonl', [resolution])
        self.assertTrue(audit.inspect(self.root)['complete'])
        resolution['source_sha256'] = 'different-source'
        self.write_rows(self.root / 'implementations.jsonl', [resolution])
        self.assertTrue(audit.inspect(self.root)['errors'])
        resolution['source_sha256'] = row['source_sha256']
        valid_test = resolution['tests'][0]
        for invalid in ('tests/nonexistent-peer-test.py',
                        'tests/peer-audit-harness.py:AuditHarness.test_missing',
                        'tests/peer-audit-harness.py:WrongClass.test_implementation_needs_matching_evidence'):
            resolution['tests'] = [invalid]
            self.write_rows(self.root / 'implementations.jsonl', [resolution])
            self.assertTrue(audit.inspect(self.root)['errors'])
        resolution['tests'] = [valid_test]
        resolution['case_id'] = 'different-case'
        self.write_rows(self.root / 'implementations.jsonl', [resolution])
        self.assertTrue(audit.inspect(self.root)['errors'])

    def test_orphan_review_scope_reports_error(self):
        self.mutate_inventory(reviewed_file_scopes=[dict(path='missing', sha256='hash')])
        report = audit.inspect(self.root)
        self.assertFalse(report['complete'])
        self.assertTrue(report['errors'])

    def test_generated_domain_hash_and_cardinality_are_required(self):
        row_path = self.root / 'python/decisions.jsonl'
        row = json.loads(row_path.read_text())
        artifact = self.root / 'python/generated-domains.jsonl'
        domain = {key: row[key] for key in ('repo', 'revision', 'path', 'source_sha256')}
        domain.update(schema_version=1, domain_id='controlled-domain', ordered_values=[-2, -1, 1, 2],
                      excluded_pairs=[], case_identity='operator/a-index/b-index', review_method='controlled finite proof',
                      oracle_rules={'integer': 'exact quotient and remainder'}, total_instances=48, reviewed_instances=48,
                      cohorts=[dict(operation=operation, count=16, disposition='covered', rule='controlled rule')
                               for operation in ('truncating-division', 'remainder', 'floor-division')])
        self.write_rows(artifact, [domain])
        row['generated_domain'] = dict(artifact='docs/research/exhaustive/python/generated-domains.jsonl',
                                       sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
                                       domain_id='controlled-domain', cohort='remainder', instances=16)
        rows = []
        for cohort in domain['cohorts']:
            rows.append(dict(row, case_id=cohort['operation'], generated_domain=dict(
                row['generated_domain'], cohort=cohort['operation'])))
        self.write_rows(row_path, rows)
        self.assertTrue(audit.inspect(self.root)['complete'])
        self.write_rows(row_path, rows[:1])
        incomplete = audit.inspect(self.root)
        self.assertFalse(incomplete['complete'])
        self.assertFalse(incomplete['errors'])
        self.assertEqual(incomplete['languages'][0]['unchecked_generated_domains'], 2)
        self.write_rows(row_path, rows)
        domain['cohorts'][0]['count'] = 15
        self.write_rows(artifact, [domain])
        self.assertTrue(audit.inspect(self.root)['errors'])
        for row in rows:
            row['generated_domain']['sha256'] = hashlib.sha256(artifact.read_bytes()).hexdigest()
        self.write_rows(row_path, rows)
        self.assertTrue(audit.inspect(self.root)['errors'])

    def test_all_generated_references_cannot_be_deleted(self):
        self.test_generated_domain_hash_and_cardinality_are_required()
        # Restore the valid domain before deleting every reference.
        artifact = self.root / 'python/generated-domains.jsonl'
        domain = json.loads(artifact.read_text())
        domain['cohorts'][0]['count'] = 16
        self.write_rows(artifact, [domain])
        path = self.root / 'python/decisions.jsonl'
        row = json.loads(path.read_text().splitlines()[0])
        row.pop('generated_domain')
        self.write_rows(path, [row])
        report = audit.inspect(self.root)
        self.assertFalse(report['errors'])
        self.assertFalse(report['complete'])
        self.assertEqual(report['languages'][0]['unchecked_generated_domains'], 3)

    def test_zig_domain_requires_every_reference_and_resolution(self):
        from peer_zig_domains import expected_domain, SOURCE
        domain = expected_domain()
        directory = self.root / 'zig'
        artifact = directory / 'log-int-generated-domain.json'
        artifact.write_text(json.dumps(domain))
        inventory = dict(schema_version=1, repo=SOURCE['repo'], sha=SOURCE['revision'],
                         files=[dict(path=SOURCE['path'], sha256=SOURCE['source_sha256'], status='reviewed')],
                         total=1, reviewed=1, discovery_complete=True, case_enumeration_complete=True)
        (directory / 'inventory.json').write_text(json.dumps(inventory))
        rows = []
        for cohort in domain['cohorts']:
            rows.append(dict(SOURCE, case_id='generated-domain/' + cohort['id'], lines=[1, 1],
                             disposition=cohort['disposition'], reason='Controlled exact domain',
                             implementation_needed=cohort['disposition'] == 'adapt',
                             generated_domain=dict(artifact='docs/research/exhaustive/zig/' + artifact.name,
                                                   sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
                                                   domain_id=domain['domain_id'], cohort=cohort['id'],
                                                   instances=cohort['instances'])))
        path = directory / 'decisions.jsonl'
        self.write_rows(path, rows)
        report = audit.inspect(self.root)
        self.assertFalse(report['errors'])
        self.assertFalse(report['complete'])
        resolutions = [dict(row, tests=['tests/peer-audit-harness.py:AuditHarness.test_zig_domain_requires_every_reference_and_resolution'],
                            validation=['controlled-pass']) for row in rows if row['implementation_needed']]
        self.write_rows(self.root / 'implementations.jsonl', resolutions)
        self.assertTrue(audit.inspect(self.root)['complete'])
        self.write_rows(path, rows[:-1])
        self.assertFalse(audit.inspect(self.root)['complete'])
        self.write_rows(self.root / 'implementations.jsonl', [])
        self.write_rows(path, [dict(SOURCE, case_id='ordinary', lines=[1, 1], disposition='covered',
                                   implementation_needed=False, reason='Another ordinary source case')])
        report = audit.inspect(self.root)
        self.assertFalse(report['errors'])
        self.assertFalse(report['complete'])
        self.assertEqual(next(row for row in report['languages'] if row['language'] == 'zig')['unchecked_generated_domains'], 4)

    def test_duplicate_and_mismatched_decisions_rejected(self):
        path = self.root / 'python/decisions.jsonl'
        row = json.loads(path.read_text())
        self.write_rows(path, [row, row])
        self.assertTrue(audit.inspect(self.root)['errors'])
        row['source_sha256'] = 'different'
        self.write_rows(path, [row])
        self.assertTrue(audit.inspect(self.root)['errors'])


if __name__ == '__main__':
    unittest.main()
