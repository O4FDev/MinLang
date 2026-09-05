#!/usr/bin/env python3
"""Check that recursive-data tests detect faults in compiler copies.

Each mutant must compile and link before failing a targeted test for its
intended reason. Control runs use the same build and sanitizer paths."""
from __future__ import annotations

import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile

from regressions import CLANG, COMPILER, ROOT

SOURCE = ROOT / 'src/compiler.min'
RUNTIME = ROOT / 'build/ownership-runtime.o'
TARGETS = {
    'cycle': ('recursive-data.py',
              'RecursiveData.test_direct_self_cycle_add_and_overwrite_rejected'),
    'literal-owner': ('recursive-data.py',
                      'RecursiveData.test_literal_retains_earlier_projection_before_later_mutation'),
    'context': ('production-memory.py',
                'ProductionMemory.test_empty_literal_context_flows_through_nested_calls_and_add'),
}


def replace_once(source: str, before: str, after: str, name: str) -> str:
    count = source.count(before)
    if count != 1:
        raise AssertionError(f'{name}: expected one mutation site, found {count}')
    return source.replace(before, after, 1)


def mutate(original: str, name: str) -> str:
    if name == 'cycle':
        return replace_once(original,
            'function checkListMutation(listType: Integer, counts: List<Integer>, '
            'fields: List<Integer>, returnTypes: List<Integer>) {',
            'function checkListMutation(listType: Integer, counts: List<Integer>, '
            'fields: List<Integer>, returnTypes: List<Integer>) {\n    return', name)
    if name == 'literal-owner':
        start = original.index('function parseListLiteral(')
        end = original.index('\nfunction parseAtom(', start)
        body = replace_once(original[start:end],
            'addOutput(output, "  call void @minyar_list_add(ptr ")',
            'addOutput(output, "  call void @minyar_list_add_take(ptr ")', name)
        # Borrowed elements now incorrectly transfer an owner they do not own.
        # The earlier projection loses its only actual owner at rc_step, so the
        # existing later-mutation test must detect a genuine dangling element.
        return original[:start] + body + original[end:]
    if name == 'context':
        return replace_once(original,
            'argumentType[0] = functionParameterTypes[first + argumentValues.length]',
            'argumentType[0] = 0', name)
    raise AssertionError(f'unknown mutation: {name}')


def run(command: list[str], *, env: dict[str, str] | None = None,
        timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, env=env, text=True,
                          capture_output=True, timeout=timeout)


def build(source: str, directory: Path, name: str) -> Path:
    path = directory / f'{name}.min'
    llvm = path.with_suffix('.ll')
    executable = directory / name
    path.write_text(source, encoding='utf-8')
    result = run([str(COMPILER), str(path), str(llvm)])
    if result.returncode != 0 or not llvm.exists():
        raise AssertionError(f'{name}: mutant compiler did not compile:\n{result.stderr}')
    result = run([CLANG, '-O1', '-DMINYAR_COMPILER_ARENA',
                  '-Wno-override-module', str(llvm),
                  str(ROOT / 'runtime/minyar_runtime.c'), '-o', str(executable)])
    if result.returncode != 0:
        raise AssertionError(f'{name}: mutant compiler did not link:\n{result.stderr}')
    return executable


def exercise(compiler: Path, name: str) -> subprocess.CompletedProcess[str]:
    script, test = TARGETS[name]
    environment = os.environ.copy()
    environment['MINYAR_TEST_COMPILER'] = str(compiler)
    environment['MINYAR_TEST_RUNTIME'] = str(RUNTIME)
    environment['MINYAR_TEST_LINK_FLAGS'] = '-fsanitize=address,undefined'
    environment['ASAN_OPTIONS'] = 'detect_leaks=0:halt_on_error=1'
    environment['UBSAN_OPTIONS'] = 'halt_on_error=1:print_stacktrace=1'
    return run([sys.executable, str(ROOT / 'tests' / script), test],
               env=environment)


def main() -> None:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if not RUNTIME.is_file():
        raise AssertionError('build/ownership-runtime.o is required; build the exact-accounting sanitizer runtime first')
    original = SOURCE.read_text(encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='minyar-recursive-mutants-') as temporary:
        directory = Path(temporary)
        control = build(original, directory, 'control')
        for name in TARGETS:
            result = exercise(control, name)
            if result.returncode != 0:
                raise AssertionError(f'control {name} failed:\n{result.stdout}\n{result.stderr}')
        print('control compiler: all three targeted contracts pass; native cases pass at O0/O2', flush=True)
        for name in TARGETS:
            compiler = build(mutate(original, name), directory, name)
            result = exercise(compiler, name)
            output = result.stdout + result.stderr
            test_name = TARGETS[name][1].split('.')[-1]
            expected = {
                'cycle': 'AssertionError: 0 != 1',
                'literal-owner': 'AddressSanitizer: heap-use-after-free',
                'context': 'an argument passed to nodes has the wrong type',
            }[name]
            if result.returncode != 1 or test_name not in output or expected not in output:
                raise AssertionError(f'{name}: intended fault was not detected '
                    f'(expected {expected!r}):\n{output}')
            if name == 'literal-owner' and any(
                    f"optimization='{level}'" not in output for level in ('-O0', '-O2')):
                raise AssertionError(f'{name}: both optimization levels must detect the lifetime fault:\n{output}')
            print(f'{name}: detected by {test_name} ({expected})', flush=True)
    print('All three recursive compiler mutants detected')


if __name__ == '__main__':
    main()
