#!/usr/bin/env python3
"""Compile cached module fragments independently, then link and execute them."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
COMPILER = Path(os.environ.get('MINYAR_TEST_COMPILER', ROOT / 'build/minyarc-modules'))


def run(command):
    result = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return result


def fields(source):
    result = []
    while source:
        n, source = source.split('\n', 1)
        length = int(n)
        result.append(source[:length]); source = source[length:]
    return result


with tempfile.TemporaryDirectory(prefix='minyar-artifacts-') as name:
    d = Path(name)
    empty = d / 'empty'; empty.write_text('')
    indexed = d / 'indexed'; indexed.mkdir()
    (indexed / 'leaf.min').write_text('public record Value { value: Integer }\npublic function make(): Value { return Value { value: 40 } }\n')
    (indexed / 'bridge.min').write_text('use "./leaf.min" as leaf\npublic function get(): leaf.Value { return leaf.make() }\n')
    (indexed / 'middle.min').write_text('use "./bridge.min" as bridge\npublic function answer(): Integer { return bridge.get().value }\n')
    (indexed / 'main.min').write_text('use "./leaf.min" as first\nuse "./leaf.min" as second\nuse "./middle.min" as middle\nprint(first.make().value + second.make().value + middle.answer())\n')
    cases = [(ROOT / f'tests/modules/{case}/main.min', expected) for case, expected in
             [('basic', 'Hello, Ada\n42\nAda\n'), ('diamond', '42\n'), ('explicit-main', '42\n'), ('windows-path', '42\n')]]
    cases.append((indexed / 'main.min', '120\n'))
    for entry, expected in cases:
        llvm = d / 'combined.ll'; state = d / 'state'
        run([COMPILER, entry, llvm, '--module-state', empty, state, d / 'stats'])
        saved = fields(state.read_text())
        assert saved[0] == 'minyar-module-interface-v4'
        if entry.parent == indexed:
            # Aliases must not duplicate modules/prototypes. A type exported to
            # one consumer must remain private in another consumer's closure.
            rows = {Path(saved[row]).name: saved[row:row + 10] for row in range(3, len(saved), 10)}
            assert len(rows) == 4
            contexts = {}
            for path, row in rows.items():
                context = fields(row[4]); symbols = {}; position = 0
                while position < len(context):
                    symbol, visible, kind, _, count = context[position:position + 5]
                    symbols[symbol] = (visible, kind)
                    position += 5 + int(count) * (2 if kind == '2' else 1)
                contexts[path] = symbols
                declarations = row[9].splitlines()
                assert len(declarations) == len(set(declarations)), row[9]
            record, = [symbol for symbol, (_, kind) in contexts['leaf.min'].items() if kind == '2']
            assert {path: context[record][0] for path, context in contexts.items()} == {
                'main.min': 'exported', 'leaf.min': 'private-type',
                'middle.min': 'private-type', 'bridge.min': 'exported'}
            run([COMPILER, entry, d / 'warm.ll', '--module-state', state, d / 'next', d / 'stats'])
            assert (d / 'warm.ll').read_bytes() == llvm.read_bytes()
            assert (d / 'stats').read_text().split()[:6] == ['4', '0', '0', '4', '0', '0']
        runtime = '\n'.join(line for line in llvm.read_text().splitlines() if line.startswith('declare ')) + '\n'
        objects = []
        for index, row in enumerate(range(3, len(saved), 10)):
            module = d / f'{index}.ll'; obj = d / f'{index}.o'
            module.write_text(runtime + saved[row + 9] + '\n' + saved[row + 5])
            run(['clang', '-O0', '-Wno-override-module', '-c', module, '-o', obj])
            objects.append(obj)
        binary = d / 'program'
        run(['clang', *objects, ROOT / 'build/minyar-runtime.o', '-o', binary])
        assert run([binary]).stdout == expected
        # LLVM modules remain valid under full-program LTO as well.
        bitcode = []
        for index in range(len(objects)):
            bc = d / f'{index}.bc'
            run(['clang', '-O2', '-Wno-override-module', '-flto', '-c', d / f'{index}.ll', '-o', bc])
            bitcode.append(bc)
        run(['clang', '-flto', *bitcode, ROOT / 'build/minyar-runtime.o', '-o', binary])
        assert run([binary]).stdout == expected

print('module artifacts: independent LLVM object compilation, native linking and LTO preserve fixture behavior')
