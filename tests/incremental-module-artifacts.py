#!/usr/bin/env python3
"""Compile cached module fragments independently, then link and execute them."""
from pathlib import Path
import os
import platform
import shlex
import shutil
import subprocess
import tempfile
from clang_helpers import clang_command
from llvm_sanitizer import address_sanitizer_enabled, prepare_llvm_for_link
from test_evidence import Evidence

ROOT = Path(__file__).resolve().parents[1]
COMPILER = Path(os.environ.get('MINYAR_TEST_COMPILER', ROOT / 'build/minyarc-modules'))
CLANG = os.environ.get('MINYAR_TEST_CLANG', 'clang')
RUNTIME = Path(os.environ.get('MINYAR_TEST_RUNTIME', ROOT / 'build/minyar-runtime.o'))
LINK_FLAGS = shlex.split(os.environ.get('MINYAR_TEST_LINK_FLAGS', ''))
LTO_LINK_FLAGS = ['-fuse-ld=lld'] if platform.system() == 'Linux' and shutil.which('ld.lld') else []


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


def pack(values):
    return ''.join(str(len(value)) + '\n' + value for value in values)


def runtime_prelude(source):
    """Cached bodies share declarations and reserved compiler helper definitions.

    Preserve complete LLVM function boundaries. Literal globals and language
    functions belong to individual cached bodies and must stay out of this part.
    """
    lines = source.splitlines(keepends=True)
    pieces = []
    position = 0
    while position < len(lines):
        line = lines[position]
        if line.startswith('declare '):
            pieces.append(line)
        elif line.startswith('define internal ') and '@.minyar.' in line:
            pieces.append(line)
            position += 1
            while position < len(lines) and lines[position].strip() != '}':
                assert not lines[position].startswith('define '), 'incomplete compiler helper'
                pieces.append(lines[position])
                position += 1
            assert position < len(lines), 'unterminated compiler helper'
            pieces.append(lines[position])
        position += 1
    return ''.join(pieces) + '\n'


def overlay(base, delta, identity):
    assert delta[:2] == ['minyar-module-delta-v3', identity]
    rows = {base[row]: base[row:row + 10] for row in range(3, len(base), 10)}
    rows.update({delta[row]: delta[row:row + 10] for row in range(4, len(delta), 10)})
    result = ['minyar-module-interface-v5', delta[2], delta[3] or base[2]]
    for path in fields(delta[2])[::2]:
        result += rows[path]
    return result


def link_lto_modules(modules, binary):
    bitcode = []
    for module in modules:
        bc = module.with_suffix('.bc')
        # LLVM input otherwise runs ASan while producing bitcode, then again
        # during LTO. Keep its function attributes and instrument only at link.
        run(clang_command([CLANG, '-O2', *LINK_FLAGS, '-Wno-override-module', '-flto',
                           '-Xclang', '-disable-llvm-passes', '-c', module, '-o', bc]))
        bitcode.append(bc)
    linked = run(clang_command([CLANG, '-O2', *LINK_FLAGS, *LTO_LINK_FLAGS, '-flto',
                                *bitcode, RUNTIME, '-o', binary]))
    assert 'Redundant instrumentation detected' not in linked.stderr, linked.stderr


def check_lto_sanitizer(directory):
    if not address_sanitizer_enabled(LINK_FLAGS):
        return
    # A cross-module volatile load proves the final LTO pipeline instruments
    # generated LLVM, rather than just supplying the sanitizer runtime.
    reader = directory / 'asan-reader.ll'
    reader.write_text('''define i8 @artifact_probe(ptr %memory, i64 %index) noinline {
entry:
  %address = getelementptr i8, ptr %memory, i64 %index
  %value = load volatile i8, ptr %address
  ret i8 %value
}
''')
    entry = directory / 'asan-entry.ll'
    entry.write_text('''declare ptr @malloc(i64)
declare void @free(ptr)
declare i8 @artifact_probe(ptr, i64)
define i32 @main() {
entry:
  %memory = call ptr @malloc(i64 8)
  %value = call i8 @artifact_probe(ptr %memory, i64 8)
  call void @free(ptr %memory)
  ret i32 0
}
''')
    for module in (reader, entry):
        prepare_llvm_for_link(module, LINK_FLAGS)
    binary = directory / 'asan-probe'
    link_lto_modules((reader, entry), binary)
    result = subprocess.run([binary], capture_output=True, text=True, timeout=60)
    assert result.returncode != 0 and 'AddressSanitizer: heap-buffer-overflow' in result.stderr, \
        'LTO-generated load was not checked by ASan: ' + result.stderr


def check_artifacts(directory, llvm, saved, expected, label):
    prelude = runtime_prelude(llvm.read_text())
    for helper in ('get.checked', 'set.scalar.checked', 'length'):
        assert '@.minyar.list.' + helper in prelude
    for optimization in ('-O0', '-O2'):
        objects = []
        modules = []
        for index, row in enumerate(range(3, len(saved), 10)):
            module = directory / f'{label}-{index}.ll'
            obj = module.with_suffix('.o')
            module.write_text(prelude + saved[row + 9] + '\n' + saved[row + 5])
            modules.append(module)
            prepare_llvm_for_link(module, LINK_FLAGS)
            run(clang_command([CLANG, optimization, *LINK_FLAGS, '-Wno-override-module', '-c', module, '-o', obj]))
            objects.append(obj)
        binary = directory / f'{label}-program'
        run(clang_command([CLANG, *LINK_FLAGS, *objects, RUNTIME, '-o', binary]))
        assert run([binary]).stdout == expected
    # Independently compiled modules must also link with full-program LTO.
    link_lto_modules(modules, binary)
    assert run([binary]).stdout == expected


with Evidence('module-artifacts', inputs=(COMPILER, __file__, ROOT / 'build/minyar-runtime.o',
              *sorted((ROOT / 'tests/modules').rglob('*.min')))) as evidence:
    d = evidence.path
    check_lto_sanitizer(d)
    empty = d / 'empty'; empty.write_text('')
    indexed = d / 'indexed'; indexed.mkdir()
    (indexed / 'leaf.min').write_text('public record Value { value: Integer }\npublic function make(): Value { return Value { value: 40 } }\n')
    (indexed / 'bridge.min').write_text('use "./leaf.min" as leaf\npublic function get(): leaf.Value { return leaf.make() }\n')
    (indexed / 'middle.min').write_text('use "./bridge.min" as bridge\npublic function answer(): Integer { return bridge.get().value }\n')
    (indexed / 'main.min').write_text('use "./leaf.min" as first\nuse "./leaf.min" as second\nuse "./middle.min" as middle\nprint(first.make().value + second.make().value + middle.answer())\n')
    lists = d / 'lists'; lists.mkdir()
    leaf = lists / 'leaf.min'
    leaf_source = '''public function floatValue(values: List<Float>): Float {
values[0] += 0.5
return values[0]
}
public function grow(values: List<Integer>): Integer { values.add(9); return values.length }
public function textValue(values: List<Text>): Text { values[0] = Text(42); return values[0] }
'''
    leaf.write_text(leaf_source)
    (lists / 'bridge.min').write_text('''use "./leaf.min" as leaf
public function report() {
let floats = [1.0]
print(leaf.floatValue(floats))
let integers = [1]
print(leaf.grow(integers))
let words = [Text(7)]
print(leaf.textValue(words))
}
''')
    (lists / 'main.min').write_text('''use "./bridge.min" as bridge
bridge.report()
let flags = [false]
flags[0] = true
print(flags[0])
let characters = ['a']
characters[0] = '🙂'
print(characters[0])
''')
    cases = [(ROOT / f'tests/modules/{case}/main.min', expected) for case, expected in
             [('basic', 'Hello, Ada\n42\nAda\n'), ('diamond', '42\n'), ('explicit-main', '42\n'), ('windows-path', '42\n')]]
    cases.append((indexed / 'main.min', '120\n'))
    cases.append((lists / 'main.min', '1.5\n2\n42\ntrue\n🙂\n'))
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
        assert saved[0] == 'minyar-module-interface-v5'
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
        check_artifacts(d, llvm, saved, expected, 'cold')
        if entry.parent == lists:
            warm = d / 'warm.ll'
            run([COMPILER, entry, warm, '--module-state', state, d / 'next', d / 'stats'])
            assert warm.read_bytes() == llvm.read_bytes()
            assert (d / 'next').read_bytes() == b''
            assert (d / 'stats').read_text().split()[:6] == ['3', '0', '0', '3', '0', '0']
            check_artifacts(d, warm, saved, expected, 'warm')
            # A real base/delta plan recompiles one module and keeps the other
            # two fragments. Independently link both the edit and its replay.
            delta = d / 'delta'; delta.write_text('')
            plan = d / 'plan'
            identity = 'artifact-base-generation'
            plan.write_text(pack(['minyar-module-plan-v1', str(state), str(delta), identity]))
            leaf.write_text(leaf_source.replace('+= 0.5', '+= 1.5'))
            edited = d / 'edited.ll'
            run([COMPILER, entry, edited, '--module-state', plan, delta, d / 'stats'])
            assert (d / 'stats').read_text().split()[:2] == ['2', '1']
            updated = overlay(saved, fields(delta.read_text()), identity)
            expected = expected.replace('1.5\n', '2.5\n')
            check_artifacts(d, edited, updated, expected, 'delta')
            run([COMPILER, entry, warm, '--module-state', plan, d / 'next', d / 'stats'])
            assert warm.read_bytes() == edited.read_bytes()
            assert (d / 'stats').read_text().split()[:6] == ['3', '0', '0', '3', '0', '0']
            check_artifacts(d, warm, updated, expected, 'delta-replay')

print('module artifacts: independent LLVM object compilation, native linking and LTO preserve fixture behavior')
