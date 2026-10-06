#!/usr/bin/env python3
"""Check audit ledger consistency; never confuse an inventory with a review.

--require-complete fails on pending discovery, file review, case enumeration,
deferred decisions or implementation. Passing ordinary validation does NOT
certify exhaustive reading.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from peer_go_domains import validate_inline_domain
from peer_zig_domains import validate_domain as validate_zig_domain, validate_reference as validate_zig_reference

LANGUAGES = ('python', 'swift', 'cpp', 'rust', 'go', 'zig', 'javascript', 'java', 'ruby', 'lua')
KEYS = ('language', 'repo', 'revision', 'path', 'case_id')


def key(row):
    return tuple(row[k] for k in KEYS)


def jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_generated_domain(path, sha256, cache):
    identity = (str(path), sha256)
    if identity not in cache:
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != sha256:
            raise ValueError('Generated domain artifact hash mismatch')
        domains = {}
        if path.suffix == '.json':
            domain = json.loads(data)
            validate_zig_domain(domain)
            domains[domain['domain_id']] = domain
        else:
            for domain in (json.loads(line) for line in data.splitlines() if line.strip()):
                if domain['schema_version'] != 1 or domain['domain_id'] in domains:
                    raise ValueError('Invalid/duplicate generated domain')
                values = domain['ordered_values']
                if not values or any(type(value) is not int or value == 0 or not -(1 << 31) <= value < (1 << 31) for value in values) or len(set(values)) != len(values):
                    raise ValueError('Division domain requires distinct nonzero Integer operands')
                excluded = {(item['dividend'], item['divisor']) for item in domain['excluded_pairs']}
                if len(excluded) != len(domain['excluded_pairs']) or any(a not in values or b not in values for a, b in excluded):
                    raise ValueError('Invalid domain exclusions')
                count = 0
                for a in values:
                    for b in values:
                        if (a, b) in excluded:
                            continue
                        q = (abs(a) // abs(b)) * (-1 if (a < 0) != (b < 0) else 1)
                        remainder = a - q * b
                        if not (-(1 << 31) <= q < (1 << 31) and -(1 << 31) <= remainder < (1 << 31)
                                and abs(remainder) < abs(b) and (not remainder or (remainder < 0) == (a < 0))):
                            raise ValueError('Signed int32 removal proof fails for generated pair')
                        count += 1
                cohorts = domain['cohorts']
                if {c['operation'] for c in cohorts} != {'truncating-division', 'remainder', 'floor-division'} or len(cohorts) != 3:
                    raise ValueError('Unknown division-domain cohorts')
                if any(c['count'] != count or not c.get('rule') or c['disposition'] not in ('adapt', 'covered', 'reject', 'defer') for c in cohorts):
                    raise ValueError('Generated cohort cardinality/disposition mismatch')
                if domain['total_instances'] != count * len(cohorts) or domain['reviewed_instances'] != domain['total_instances']:
                    raise ValueError('Incomplete generated instance decisions')
                if not domain.get('case_identity') or not domain.get('review_method') or not domain.get('oracle_rules'):
                    raise ValueError('Missing generated instance identity/review/oracle rules')
                domains[domain['domain_id']] = domain
        cache[identity] = domains
    return identity


def check_generated_domain(root, language, row, cache):
    reference = row['generated_domain']
    name = Path(reference['artifact']).name
    if reference['artifact'] != f'docs/research/exhaustive/{language}/{name}':
        raise ValueError('Generated domain artifact must be inside its language directory')
    identity = load_generated_domain(root / language / name, reference['sha256'], cache)
    domain = cache[identity][reference['domain_id']]
    if domain.get('schema') == 'zig-log-int-v1':
        cohort = validate_zig_reference(row, reference, domain)
        return identity, domain['domain_id'], cohort
    if any(domain[key] != row[key] for key in ('repo', 'revision', 'path', 'source_sha256')):
        raise ValueError('Generated domain does not match its reviewed source')
    cohort = next(c for c in domain['cohorts'] if c['operation'] == reference['cohort'])
    if cohort['count'] != reference['instances'] or cohort['disposition'] != row['disposition']:
        raise ValueError('Generated reference disagrees with its cohort')
    return identity, domain['domain_id'], cohort['operation']


def inspect(root, source_root=None):
    errors, summary = [], []
    resolutions = {}
    workspace = Path(__file__).resolve().parents[1]
    python_functions = {}
    for row in jsonl(root / 'implementations.jsonl'):
        identity = key(row)
        if identity in resolutions:
            errors.append(f'Duplicate implementation resolution: {identity}')
        if not row.get('tests') or not row.get('validation'):
            errors.append(f'Implementation lacks tests/validation: {identity}')
        for reference in row.get('tests', []):
            relative, _, target = reference.partition(':')
            path = (workspace / relative).resolve()
            if not path.is_relative_to(workspace) or not path.is_file():
                errors.append(f'Implementation test file missing or outside workspace: {reference}')
                continue
            if path.suffix == '.py' and target.split('.')[-1].startswith('test_'):
                if path not in python_functions:
                    try:
                        tree = ast.parse(path.read_text())
                        names = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
                        names.update(node.name + '.' + method.name for node in ast.walk(tree)
                                     if isinstance(node, ast.ClassDef) for method in node.body
                                     if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)))
                        python_functions[path] = names
                    except (SyntaxError, UnicodeError) as error:
                        errors.append(f'Cannot parse implementation test file {relative}: {error}')
                        python_functions[path] = set()
                if target not in python_functions[path]:
                    errors.append(f'Implementation test method missing: {reference}')
        resolutions[identity] = row
    seen_resolutions = set()
    generated_domains = {}
    for language in LANGUAGES:
        directory = root / language
        path = directory / 'inventory.json'
        if not path.exists():
            errors.append(f'Missing inventory: {language}')
            continue
        inventory = json.loads(path.read_text())
        if inventory.get('schema_version') != 1:
            errors.append(f'Unknown inventory schema: {language}')
        repositories = inventory.get('repositories', [inventory])
        files, reviewed = {}, set()
        for repo in repositories:
            for entry in repo.get('files', []):
                identity = (repo['repo'], repo['sha'], entry['path'])
                if identity in files:
                    errors.append(f'Duplicate inventory path: {identity}')
                files[identity] = entry
                if entry.get('status', entry.get('review_status')) == 'reviewed':
                    reviewed.add(identity)
            for entry in repo.get('reviewed_file_scopes', []):
                identity = (repo['repo'], repo['sha'], entry['path'])
                if identity not in files or files[identity]['sha256'] != entry['sha256']:
                    errors.append(f'Review scope missing/hash mismatch: {identity}')
                reviewed.add(identity)
        # Discover maintained domain artifacts independently of ledger rows.
        # Deleting every reference must not erase a generated review obligation.
        artifacts = set(directory.glob('*generated*domain*.json'))
        if (directory / 'generated-domains.jsonl').exists():
            artifacts.add(directory / 'generated-domains.jsonl')
        for artifact in sorted(artifacts):
            try:
                load_generated_domain(artifact, hashlib.sha256(artifact.read_bytes()).hexdigest(), generated_domains)
            except (KeyError, TypeError, ValueError, OSError) as error:
                errors.append(f'Malformed generated domain in {language}: {error}')
        decisions = jsonl(directory / 'decisions.jsonl')
        seen, needs_implementation, checked_sources = set(), 0, {}
        decided_files = set()
        unchecked_domains = 0
        deferred_decisions = 0
        referenced_cohorts = set()
        for row in decisions:
            try:
                identity = key(row)
                if identity in seen:
                    errors.append(f'Duplicate decision: {identity}')
                seen.add(identity)
                file_key = (row['repo'], row['revision'], row['path'])
                entry = files.get(file_key)
                decided_files.add(file_key)
                if row['language'] != language or not entry or entry['sha256'] != row['source_sha256']:
                    errors.append(f'Decision not matched to frozen inventory: {identity}')
                if row.get('generated_domain'):
                    if 'artifact' in row['generated_domain']:
                        referenced_cohorts.add(check_generated_domain(root, language, row, generated_domains))
                    elif not validate_inline_domain(row):
                        # Unknown families stay explicit until a validator can
                        # check their finite source-derived domains.
                        unchecked_domains += 1
                start, end = row['lines']
                if type(start) is not int or type(end) is not int or start < 1 or end < start:
                    errors.append(f'Invalid source span: {identity}')
                if row['disposition'] not in ('adapt', 'covered', 'reject', 'defer') or not row.get('reason'):
                    errors.append(f'Missing/invalid disposition: {identity}')
                if row['disposition'] == 'defer':
                    deferred_decisions += 1
                if not isinstance(row.get('implementation_needed'), bool):
                    errors.append(f'Missing implementation decision: {identity}')
                if row.get('implementation_needed'):
                    if identity in resolutions:
                        seen_resolutions.add(identity)
                        recorded_hash = resolutions[identity].get('source_sha256')
                        if recorded_hash is not None and recorded_hash != row['source_sha256']:
                            errors.append(f'Implementation source hash differs from reviewed decision: {identity}')
                    else:
                        needs_implementation += 1
                if source_root is not None:
                    if file_key not in checked_sources:
                        name = row['repo'].split('/')[-1]
                        candidates = [source_root / name, source_root / (name + '-' + row['revision'])]
                        parent = next((p for p in candidates if p.is_dir()), None)
                        source = parent / row['path'] if parent else None
                        if source is None or not source.is_file():
                            errors.append(f'Missing acquired source: {file_key}')
                            checked_sources[file_key] = None
                        else:
                            data = source.read_bytes()
                            if hashlib.sha256(data).hexdigest() != row['source_sha256']:
                                errors.append(f'Acquired source hash mismatch: {file_key}')
                            checked_sources[file_key] = data
                    data = checked_sources[file_key]
                    length = (len(data.split(b'\n')) if row.get('line_numbering') == 'lf'
                              else len(data.splitlines())) if data is not None else None
                    if length is not None and end > length:
                        errors.append(f'Source span beyond EOF: {identity}')
            except (KeyError, TypeError, ValueError, OSError, StopIteration) as error:
                errors.append(f'Malformed decision in {language}: {error}')
        # Loading one cohort does not establish dispositions for the rest of
        # that artifact. Every declared cohort needs its own checked ledger row.
        for artifact, domains in generated_domains.items():
            if Path(artifact[0]).parent != directory:
                continue
            for domain_id, domain in domains.items():
                for cohort in domain['cohorts']:
                    if (artifact, domain_id, cohort.get('operation', cohort.get('id'))) not in referenced_cohorts:
                        unchecked_domains += 1
        for identity in reviewed - decided_files:
            entry = files.get(identity, {})
            if not (entry.get('no_tests') is True and entry.get('review_reason')
                    and entry.get('scope_disposition') == 'support'):
                errors.append(f'Reviewed file lacks decisions or explicit support scope: {identity}')
        totals = inventory.get('totals', {})
        declared_total = inventory.get('total', totals.get('files'))
        declared_reviewed = inventory.get('reviewed', totals.get('reviewed_files'))
        if declared_total != len(files) or declared_reviewed != len(reviewed):
            errors.append(f'Inconsistent file counts: {language}: declared {declared_total}/{declared_reviewed}, actual {len(files)}/{len(reviewed)}')
        summary.append({'language': language, 'inventory_files': len(files), 'reviewed_files': len(reviewed),
                        'pending_files': len(files) - len(reviewed), 'decision_rows': len(decisions),
                        'unresolved_implementations': needs_implementation,
                        'deferred_decisions': deferred_decisions,
                        'unchecked_generated_domains': unchecked_domains,
                        'discovery_complete': inventory.get('discovery_complete', False),
                        'case_enumeration_complete': inventory.get('case_enumeration_complete', False)})
    for identity in resolutions.keys() - seen_resolutions:
        errors.append(f'Implementation resolution has no matching needed decision: {identity}')
    complete = len(summary) == len(LANGUAGES) and not errors and all(
        row['pending_files'] == row['unresolved_implementations'] == row['unchecked_generated_domains'] == row['deferred_decisions'] == 0
        and row['discovery_complete'] and row['case_enumeration_complete'] for row in summary)
    return {'consistency': 'failed' if errors else 'passed', 'complete': complete,
            'scope': 'Recorded evidence consistency, not independent proof that source was read',
            'languages': summary, 'errors': errors}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1] / 'docs/research/exhaustive')
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    report = inspect(args.root, args.source_root)
    print(json.dumps(report, indent=2))
    raise SystemExit(1 if report['errors'] or (args.require_complete and not report['complete']) else 0)
