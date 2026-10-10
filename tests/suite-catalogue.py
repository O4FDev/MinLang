#!/usr/bin/env python3
"""Require an explicit disposition for every host test source, including new files.

This checks inventory and declared consumers, not execution or Make semantics.
Minyar fixtures and data/oracles remain owned by their individual harnesses.
"""
import copy
import json
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXTENSIONS = {'.py', '.c', '.h', '.sh'}
ROLES = {'suite', 'support', 'fixture', 'manual', 'ungated'}


def discover(root):
    return {p.relative_to(root).as_posix() for p in (root / 'tests').rglob('*')
            if p.is_file() and p.suffix in EXTENSIONS}


def validate(data, root):
    if data.get('schema_version') != 1 or not data.get('sources'):
        raise ValueError('Missing schema or empty source catalogue')
    seen = set()
    for row in data['sources']:
        name = row['path']
        path = root / name
        if name in seen:
            raise ValueError('Duplicate source: ' + name)
        seen.add(name)
        if (not path.resolve().is_relative_to(root.resolve()) or
                not name.startswith('tests/') or Path(name).as_posix() != name or
                '..' in Path(name).parts or not path.is_file()):
            raise ValueError('Missing or unsafe source: ' + name)
        if row.get('role') not in ROLES or not row.get('reason', '').strip():
            raise ValueError('Missing disposition: ' + name)
        consumers = row.get('consumers', [])
        if row['role'] in {'manual', 'ungated'}:
            if consumers:
                raise ValueError('Manual/ungated source cannot claim a runner')
            continue
        if not consumers or len(consumers) != len(set(consumers)):
            raise ValueError('Missing or duplicate consumers: ' + name)
        for consumer in consumers:
            owner = (root / consumer).resolve()
            if (not owner.is_relative_to(root.resolve()) or not owner.is_file()
                    or owner == path.resolve()):
                raise ValueError('Missing or unsafe consumer: ' + consumer)
            # Support imports use a module stem; C harnesses sometimes append
            # the extension dynamically. This is a reference check, not proof
            # that the consumer executes the test in every configuration.
            text = owner.read_text()
            token = re.escape(path.stem)
            sibling_c = (path.suffix == '.c' and owner.with_suffix('.c') == path.resolve()
                         and "Path(__file__).with_suffix('.c')" in text)
            if not sibling_c and path.name not in text and not re.search(r'(?<![\w-])' + token + r'(?![\w-])', text):
                raise ValueError('Consumer no longer references source: ' + name)
    actual = discover(root)
    if seen != actual:
        raise ValueError(f'Uncatalogued sources: {sorted(actual - seen)}; stale entries: {sorted(seen - actual)}')


def controls():
    with tempfile.TemporaryDirectory(prefix='minyar-catalogue-') as tmp:
        root = Path(tmp)
        (root / 'tests').mkdir()
        source = root / 'tests/example.py'
        source.write_text('pass\n')
        (root / 'Makefile').write_text('check-example:\n\tpython3 tests/example.py\n')
        data = {'schema_version': 1, 'sources': [dict(path='tests/example.py', role='suite',
                reason='Example control suite', consumers=['Makefile'])]}
        validate(data, root)
        rejected = 0

        def reject(candidate):
            nonlocal rejected
            try:
                validate(candidate, root)
            except ValueError:
                rejected += 1
            else:
                raise AssertionError('Accepted invalid source catalogue')

        extra = root / 'tests/nested/new-suite.py'
        extra.parent.mkdir()
        extra.write_text('pass\n')
        reject(data)  # Actual newly created source, not a simulated set mutation.
        extra.unlink()
        mutant = copy.deepcopy(data)
        mutant['sources'].append(mutant['sources'][0])
        reject(mutant)
        source.unlink()
        reject(data)
        source.write_text('pass\n')
        for changes in ({'role': 'unknown'}, {'reason': ''}, {'consumers': []},
                        {'consumers': ['missing.py']}, {'consumers': ['tests/example.py']},
                        {'role': 'ungated'}, {'path': '../outside.py'}):
            mutant = copy.deepcopy(data)
            mutant['sources'][0].update(changes)
            reject(mutant)
        (root / 'Makefile').write_text('check-example:\n\ttrue\n')
        reject(data)
        return rejected


if __name__ == '__main__':
    data = json.loads((ROOT / 'tests/suite-catalogue.json').read_text())
    validate(data, ROOT)
    count = controls()
    exceptions = [row['path'] for row in data['sources'] if row['role'] in {'manual', 'ungated'}]
    print(f'{len(data["sources"])} host test sources catalogued; {count} invalid controls rejected')
    print('Explicit manual/ungated sources: ' + ', '.join(exceptions))
