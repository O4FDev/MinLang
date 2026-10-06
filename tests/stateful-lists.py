#!/usr/bin/env python3
"""Seeded supported-List operations checked against a Python alias model."""
import os
import random
import unittest

from regressions import CompilerTestCase


def sequence(seed, steps=96):
    rng = random.Random(seed)
    names = ['first', 'second', 'third']
    model = [[], [], []]
    source = ['function observe(values: List<Integer>) {', 'print(values.length)',
              'let index = 0', 'while index < values.length { print(values[index]); index = index + 1 }',
              '}', *[f'let {name}: List<Integer> = []' for name in names]]
    expected, operations = [], []

    def checkpoint(lines):
        operations.append(lines)
        source.extend(lines)
        source.append(f'print({len(operations) - 1})')
        expected.append(str(len(operations) - 1))
        for name, values in zip(names, model):
            source.append(f'observe({name})')
            expected.extend([str(len(values)), *map(str, values)])

    checkpoint([])
    model[1] = model[0]
    checkpoint(['second = first'])
    # Cross several backing-store growth boundaries while an alias stays live.
    for value in range(65):
        model[0].append(value)
        checkpoint([f'first.add({value})'])
    # This changes order without changing length or sum, with both aliases live.
    model[0][0], model[0][64] = model[0][64], model[0][0]
    checkpoint(['let boundary = first[0]', 'first[0] = first[64]', 'first[64] = boundary'])
    model[2] = model[0] + [-1]
    checkpoint(['third = first.appended(-1)'])
    model[0][0] = 9999
    checkpoint(['first[0] = 9999'])
    model[0] = []
    checkpoint(['first = []'])
    model[1][64] = -8888
    checkpoint(['second[64] = -8888'])

    for step in range(steps):
        target, other = rng.randrange(3), rng.randrange(3)
        name, other_name = names[target], names[other]
        operation = rng.choice(['add', 'write', 'alias', 'fork', 'rebind', 'swap'])
        value = rng.randint(-10000, 10000)
        if operation in ('add', 'fork') and len(model[other if operation == 'fork' else target]) >= 128:
            operation = 'rebind'
        if operation in ('write', 'swap') and not model[target]:
            operation = 'add'
        if operation == 'add':
            model[target].append(value)
            lines = [f'{name}.add({value})']
        elif operation == 'write':
            index = rng.randrange(len(model[target]))
            model[target][index] = value
            lines = [f'{name}[{index}] = {value}']
        elif operation == 'alias':
            model[target] = model[other]
            lines = [f'{name} = {other_name}']
        elif operation == 'fork':
            model[target] = model[other] + [value]
            lines = [f'{name} = {other_name}.appended({value})']
        elif operation == 'rebind':
            model[target] = [rng.randint(-100, 100) for _ in range(rng.randrange(4))]
            lines = [f'{name} = [{", ".join(map(str, model[target]))}]']
        else:
            left, right = rng.randrange(len(model[target])), rng.randrange(len(model[target]))
            model[target][left], model[target][right] = model[target][right], model[target][left]
            lines = [f'let saved{step} = {name}[{left}]',
                     f'{name}[{left}] = {name}[{right}]', f'{name}[{right}] = saved{step}']
        checkpoint(lines)
    return '\n'.join(source) + '\n', '\n'.join(expected) + '\n', operations


class StatefulLists(CompilerTestCase):
    def test_seeded_alias_and_fork_model(self):
        variants = ('-O0', '-O2', '-O3', '-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1' else ('-O0', '-O2')
        for seed in (0, 1, 0xC0DE, 0x4D494E):
            with self.subTest(seed=seed):
                source, expected, operations = sequence(seed)
                self.evidence.controls.setdefault('stateful_list_sequences', {})[str(seed)] = operations
                self.executes(source, expected, optimizations=variants)


if __name__ == '__main__':
    unittest.main()
