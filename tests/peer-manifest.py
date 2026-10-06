#!/usr/bin/env python3
"""Validate the peer regression catalogue and its required gate declarations."""
import ast
import copy
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'tests/peer-cases.json'


def validate(data):
    if data.get('schema_version') != 1 or not data.get('cases'):
        raise ValueError('Missing schema or empty case selection')
    seen = set()
    sources = {}
    contracts = {}
    ownership = set()
    for row in data['cases']:
        identity = (row['source'], row['id'])
        if identity in seen:
            raise ValueError('Duplicate case identity')
        seen.add(identity)
        path = (ROOT / row['source']).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ValueError('Case source is missing or outside the repository')
        if row['source'] not in sources:
            methods = [node for node in ast.walk(ast.parse(path.read_text()))
                       if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]
            sources[row['source']] = {node.name for node in methods}
            for method in methods:
                for decorator in method.decorator_list:
                    if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name) and decorator.func.id == 'peer_configurations':
                        try:
                            variants = [ast.literal_eval(arg) for arg in decorator.args]
                        except (ValueError, TypeError) as error:
                            raise ValueError('Campaign configurations must be literal') from error
                        contracts[row['source'], method.name] = variants
        if row['id'] not in sources[row['source']]:
            raise ValueError('Unknown test method')
        if not row.get('origins') or not row.get('feature') or not row.get('phases'):
            raise ValueError('Case lacks provenance, feature or phase')
        gates = row.get('gates', {})
        if not gates or set(gates) - {'check-peer-regressions', 'check-peer-optimizations', 'check-peer-sanitize', 'check-peer-ownership'}:
            raise ValueError('Unknown or missing required gate')
        for variants in gates.values():
            if not variants or len(variants) != len(set(variants)) or set(variants) - {'frontend', 'harness', 'O0', 'O1', 'O2', 'O3', 'Os', 'O2-LTO'}:
                raise ValueError('Empty, duplicate or unsupported configurations')
        if identity in contracts:
            expected = {'check-peer-regressions': contracts[identity], 'check-peer-optimizations': contracts[identity]}
        elif row['id'].startswith('test_lto_'):
            expected = {'check-peer-optimizations': ['O2-LTO']}
        elif set(row['phases']) <= {'compile', 'compile-reject'}:
            expected = {'check-peer-regressions': ['frontend'], 'check-peer-optimizations': ['frontend']}
        else:
            expected = {'check-peer-regressions': ['O0', 'O2'], 'check-peer-optimizations': ['O0', 'O2', 'O3', 'Os']}
        for gate in ('check-peer-sanitize', 'check-peer-ownership'):
            if gate in gates:
                if 'check-peer-regressions' not in expected:
                    raise ValueError('LTO pilot cannot claim a sanitizer configuration')
                expected[gate] = expected['check-peer-regressions']
        if gates != expected:
            raise ValueError(f'Required configurations mismatch for {identity}: expected {expected}, got {gates}')
        if 'check-peer-ownership' in gates:
            tree = ast.parse(path.read_text())
            owners = [node.name for node in tree.body if isinstance(node, ast.ClassDef)
                      and any(isinstance(method, ast.FunctionDef) and method.name == row['id']
                              for method in node.body)]
            if len(owners) != 1:
                raise ValueError('Ownership method must belong to one test class')
            ownership.add(owners[0] + '.' + row['id'])
    for source, methods in sources.items():
        if {name for path, name in seen if path == source} != methods:
            raise ValueError('Executable test omitted from catalogue')
    # Discover whole suites as well as methods: removing every declaration for
    # a newly split suite must not make that source invisible to this gate.
    discovered = set()
    for path in (ROOT / 'tests').glob('peer-*.py'):
        tree = ast.parse(path.read_text())
        if any(isinstance(node, ast.ClassDef) and any(
                isinstance(base, ast.Name) and base.id == 'CompilerTestCase'
                for base in node.bases) for node in tree.body):
            discovered.add(path.relative_to(ROOT).as_posix())
    if set(sources) != discovered:
        raise ValueError('Peer regression suite omitted from catalogue or unknown suite declared')
    makefile = (ROOT / 'Makefile').read_text()
    recipe = re.search(r'^check-peer-ownership:[^\n]*\n((?:[\t ].*\n|\n)*)', makefile, re.M)
    selected = re.findall(r'\b(Peer\w+\.test_\w+)\b', recipe.group(1) if recipe else '')
    if len(selected) != len(set(selected)) or set(selected) != ownership:
        raise ValueError('Ownership Make selection differs from declared methods')
    # Codegen source/oracle pairs are part of the same maintained pilot.
    sources = set((ROOT / 'tests/codegen').glob('*.min'))
    oracles = set((ROOT / 'tests/codegen').glob('*.stdout'))
    if not sources or {source.with_suffix('.stdout') for source in sources} != oracles:
        raise ValueError('Missing or orphan codegen oracle')


def main():
    data = json.loads(MANIFEST.read_text())
    validate(data)
    mutations = []
    empty = copy.deepcopy(data); empty['cases'] = []; mutations.append(empty)
    duplicate = copy.deepcopy(data); duplicate['cases'].append(duplicate['cases'][0]); mutations.append(duplicate)
    missing = copy.deepcopy(data); missing['cases'].pop(); mutations.append(missing)
    variant = copy.deepcopy(data); variant['cases'][0]['gates']['check-peer-regressions'] = ['O0']; mutations.append(variant)
    unknown = copy.deepcopy(data); unknown['cases'][0]['id'] = 'test_does_not_exist'; mutations.append(unknown)
    omitted_suite = copy.deepcopy(data)
    source = omitted_suite['cases'][0]['source']
    omitted_suite['cases'] = [row for row in omitted_suite['cases'] if row['source'] != source]
    mutations.append(omitted_suite)
    campaign = copy.deepcopy(data)
    fixed = next(row for row in campaign['cases'] if row['id'] == 'test_reviewed_allocator_workloads')
    fixed['gates']['check-peer-regressions'] = ['O0', 'O2']
    mutations.append(campaign)
    missing_ownership = copy.deepcopy(data)
    next(row for row in missing_ownership['cases'] if 'check-peer-ownership' in row['gates'])['gates'].pop('check-peer-ownership')
    mutations.append(missing_ownership)
    for mutant in mutations:
        try:
            validate(mutant)
        except ValueError:
            pass
        else:
            raise AssertionError('Manifest gate accepted an invalid catalogue')
    print(f"{len(data['cases'])} peer case declarations across {len({row['source'] for row in data['cases']})} suites and codegen oracles valid; {len(mutations)} invalid catalogues rejected")


if __name__ == '__main__':
    main()
