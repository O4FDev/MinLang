#!/usr/bin/env python3
"""Semantic oracles kill scalar-record capture and escape-analysis faults.

Mutants are compiled from temporary source copies by the actual compiler. Both
must compile and link before their specific wrong output or sanitizer failure
counts; incidental compiler/build failures never count as successful detection.
"""
import os
from pathlib import Path
import resource
import subprocess
import tempfile
from regressions import CLANG, COMPILER, ROOT
from llvm_sanitizer import prepare_llvm_for_link

CASES = {
    'capture': ('''record Pair { x: Integer; y: Integer }
function bump(state: List<Integer>, delta: Integer): Integer {
state[0] = state[0] + delta
return state[0]
}
function work(state: List<Integer>): Integer {
let p = Pair { y: bump(state, 10); x: bump(state, 1) }
return p.x * 100 + p.y
}
let state = [0]
print(work(state))
print(state[0])
''', '1110\n11\n'),
    'escape': ('''record Pair { x: Integer; y: Integer }
function save(p: Pair, values: List<Pair>): Integer {
values.add(p)
return p.x
}
function work(values: List<Pair>): Integer {
let p = Pair { x: 9; y: 4 }
return save(p, values)
}
let values: List<Pair> = []
print(work(values))
print(values[0].y)
''', '9\n4\n'),
}


def run(args, env=None):
    return subprocess.run(list(map(str, args)), text=True, capture_output=True,
                          timeout=120, env=env, cwd=ROOT)


def checked(args, purpose):
    result = run(args)
    if result.returncode:
        raise AssertionError(f'{purpose}: {result.stdout}\n{result.stderr}')


def main():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    source_root = COMPILER.parent.parent
    source = (source_root / 'src/compiler.min').read_text()
    changes = {
        'capture': ('raw = output[scalarValues + (field - first) * 3 + 1]',
                    'raw = output[scalarValues + 1]'),
        'escape': ('if position + 1 >= tokenTexts.length || tokenTexts[position + 1] != "." { return }',
                   'if position + 1 >= tokenTexts.length { return }'),
    }
    env = os.environ.copy()
    env['ASAN_OPTIONS'] = 'detect_leaks=0:halt_on_error=1'
    # The oracle requires the fault diagnostic and a failing exit, not a
    # backtrace. UBSan's backtrace unwinder can stall on emulated x86 musl.
    env['UBSAN_OPTIONS'] = 'halt_on_error=1:print_stacktrace=0'
    with tempfile.TemporaryDirectory(prefix='minyar-scalar-mutants-') as temporary:
        directory = Path(temporary)
        compilers = {'control': COMPILER}
        for name, (before, after) in changes.items():
            assert source.count(before) == 1, f'{name}: mutation site changed'
            path = directory / f'{name}.min'
            path.write_text(source.replace(before, after, 1))
            checked([COMPILER, path, path.with_suffix('.ll')], f'{name} compiler build')
            exe = directory / name
            checked([CLANG, '-O1', '-DMINYAR_COMPILER_ARENA', '-Wno-override-module',
                     path.with_suffix('.ll'), ROOT / 'runtime/minyar_runtime.c', '-o', exe],
                    f'{name} compiler link')
            compilers[name] = exe
        for name, (program, expected) in CASES.items():
            for mode in ('control', name):
                path = directory / f'{name}-{mode}.min'
                path.write_text(program)
                llvm = path.with_suffix('.ll')
                checked([compilers[mode], path, llvm], f'{name}/{mode} program compile')
                prepare_llvm_for_link(llvm, ['-fsanitize=address'])
                for optimization in ('-O0', '-O2'):
                    exe = directory / f'{name}-{mode}-{optimization[1:]}'
                    checked([CLANG, optimization, '-fsanitize=address,undefined',
                             '-Wno-override-module', llvm, ROOT / 'build/ownership-runtime.o',
                             '-o', exe], f'{name}/{mode} program link')
                    result = run([exe], env)
                    if mode == 'control':
                        assert result.returncode == 0 and result.stdout == expected, result
                    elif name == 'capture':
                        assert result.returncode == 0 and result.stdout == '1111\n11\n', result
                    else:
                        assert result.returncode != 0 and ('runtime error: member access within null pointer' in result.stderr
                            or 'AddressSanitizer: SEGV' in result.stderr), result
            print(f'{name}: intended fault detected at O0 and O2', flush=True)
    print('Both scalar-record compiler mutants detected')


if __name__ == '__main__':
    main()
