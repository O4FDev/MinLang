#!/usr/bin/env python3
"""Compile cached module fragments independently, then link and execute them."""
from pathlib import Path
import os
import subprocess
from test_evidence import Evidence

ROOT = Path(__file__).resolve().parents[1]
COMPILER = Path(os.environ.get('MINYAR_TEST_COMPILER', ROOT / 'build/minyarc-modules'))


def run(command):
    result = evidence.run(list(map(str, command)), capture_output=True, text=True, timeout=60,
                          phase='module-artifact')
    assert result.returncode == 0, result.stderr
    assert not result.stderr, result.stderr
    return result


def fields(source):
    result = []
    while source:
        n, source = source.split('\n', 1)
        length = int(n)
        result.append(source[:length]); source = source[length:]
    return result


with Evidence('module-artifacts', inputs=(COMPILER, __file__, ROOT / 'build/minyar-runtime.o',
              *sorted((ROOT / 'tests/modules').rglob('*.min')))) as evidence:
    d = evidence.path
    empty = d / 'empty'; empty.write_text('')
    indexed = d / 'indexed'; indexed.mkdir()
    (indexed / 'leaf.min').write_text('public record Value { value: Integer }\npublic function make(): Value { return Value { value: 40 } }\n')
    (indexed / 'bridge.min').write_text('use "./leaf.min" as leaf\npublic function get(): leaf.Value { return leaf.make() }\n')
    (indexed / 'middle.min').write_text('use "./bridge.min" as bridge\npublic function answer(): Integer { return bridge.get().value }\n')
    (indexed / 'main.min').write_text('use "./leaf.min" as first\nuse "./leaf.min" as second\nuse "./middle.min" as middle\nprint(first.make().value + second.make().value + middle.answer())\n')
    cases = [(ROOT / f'tests/modules/{case}/main.min', expected) for case, expected in
             [('basic', 'Hello, Ada\n42\nAda\n'), ('diamond', '42\n'), ('explicit-main', '42\n'), ('windows-path', '42\n')]]
    cases.append((indexed / 'main.min', '120\n'))
    aliases = d / 'aliases'; aliases.mkdir()
    (aliases / 'worker.min').write_text('''public function reload(write: List<Integer>, read: List<Integer>): Integer {
write[0] = 1
read[0] = 2
return write[0]
}
public function loop(write: List<Integer>, read: List<Integer>, forward: Boolean): Integer {
let index = 0
let total = 0
while index < 3 {
if forward { write[0] = index + 1; read[0] = index + 10 } else { read[0] = index + 1; write[0] = index + 10 }
total = total + write[0]
index = index + 1
}
return total
}
''')
    source = ['use "./worker.min" as worker']
    expected = []
    for shared in (False, True):
        for forward in (False, True):
            source += ['let first = [0]', 'let second = first' if shared else 'let second = [0]',
                       'print(worker.reload(first, second))', 'print(first[0])', 'print(second[0])',
                       'print(worker.loop(first, second, ' + str(forward).lower() + '))',
                       'print(first[0])', 'print(second[0])']
            expected += [2 if shared else 1, 2 if shared else 1, 2]
            expected += [33 if shared or not forward else 6,
                         12 if shared or not forward else 3,
                         12 if shared or forward else 3]
    (aliases / 'main.min').write_text('\n'.join(source) + '\n')
    cases.append((aliases / 'main.min', ''.join(str(value) + '\n' for value in expected)))
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
        binary = d / 'program'
        for optimization in ('-O0', '-O2'):
            objects = []
            for index, row in enumerate(range(3, len(saved), 10)):
                module = d / f'{index}.ll'; obj = d / f'{index}.o'
                module.write_text(runtime + saved[row + 9] + '\n' + saved[row + 5])
                run(['clang', optimization, '-Wno-override-module', '-c', module, '-o', obj])
                objects.append(obj)
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
