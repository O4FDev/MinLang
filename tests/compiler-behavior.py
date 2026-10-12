import argparse
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]


def run(command):
    result = subprocess.run([str(item) for item in command], capture_output=True,
                            text=True, timeout=120)
    if result.returncode != 0:
        raise AssertionError(f'{command}: {result.returncode}\n{result.stderr}')
    return result


def check(compiler, directory, clang, runtime, profile):
    module = directory / 'values.min'
    module.write_text('public function value(): Integer { return 42 }\n')
    cases = [
        ('arithmetic', 'function sum(n: Integer): Integer {\n'
         'let value = 0\nwhile n > 0 { value = value + n; n = n - 1 }\n'
         'return value\n}\nprint(sum(100))\nprint(false && 1 / 0 == 0)\n',
         '5050\nfalse\n'),
        ('ownership', 'record Box { value: Text }\n'
         'function box(): Box { return Box { value: "hello" + " world" } }\n'
         'let boxes: List<Box> = [box(), box()]\nprint(boxes[1].value)\n'
         'print("é🙂".length)\nprint(Integer(\'中\'))\n',
         'hello world\n2\n20013\n'),
        ('modules', 'use "./values.min" as values\nprint(values.value())\n', '42\n'),
    ]
    if profile in ('callbacks', 'errors', 'calldepth', 'threads'):
        cases.append(('closure', 'let base = 40\n'
                      'let add: Callback<Integer, Integer> = function(value: Integer): Integer { return base + value }\n'
                      'print(add(2))\n', '42\n'))
    if profile in ('errors', 'calldepth', 'threads'):
        cases.append(('result', 'let value = Ok<Integer, Text>(42)\n'
                      'match value { Ok(number) { print(number) } Err(error) { print(error) } }\n',
                      '42\n'))
    for name, source, expected in cases:
        path = directory / (name + '.min')
        path.write_text(source)
        llvm = path.with_suffix('.ll')
        run([compiler, path, llvm])
        for optimization in ('-O0', '-O2'):
            executable = path.with_suffix('.' + optimization[1:])
            run(clang_command([clang, optimization, '-Wno-override-module', llvm,
                               runtime, '-o', executable]))
            result = run([executable])
            if result.stdout != expected or result.stderr:
                raise AssertionError(f'{compiler}: {name} {optimization}: {result}')
    for source, diagnostic in (
        ('print(missing)\n', 'unknown'),
        ('print(9223372036854775808)\n', 'outside the supported range'),
        ('let value: Integer = "wrong"\n', 'type'),
    ):
        path = directory / 'invalid.min'
        path.write_text(source)
        llvm = path.with_suffix('.ll')
        llvm.unlink(missing_ok=True)
        result = subprocess.run([str(compiler), str(path), str(llvm)],
                                capture_output=True, text=True, timeout=30)
        if result.returncode != 1 or diagnostic not in result.stderr.lower() or llvm.exists():
            raise AssertionError(f'{compiler}: rejection: {result}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--compiler', type=Path, action='append', default=[])
    parser.add_argument('--ir', type=Path, action='append', default=[])
    parser.add_argument('--profile', default='core')
    args = parser.parse_args()
    if not args.compiler and not args.ir:
        parser.error('at least one compiler or compiler IR is required')
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    runtime = ROOT / 'build/minyar-runtime.o'
    with tempfile.TemporaryDirectory(prefix='compiler-behavior-') as temporary:
        directory = Path(temporary)
        compilers = [path.resolve() for path in args.compiler]
        for index, llvm in enumerate(args.ir):
            compiler = directory / f'compiler-{index}'
            run(clang_command([clang, '-O2', '-Wno-override-module',
                               *shlex.split(os.environ.get('COMPILER_LTO_FLAGS', '-flto=thin')),
                               llvm.resolve(), ROOT / 'build/minyar-compiler-runtime.ll',
                               '-o', compiler]))
            compilers.append(compiler)
        for compiler in compilers:
            check(compiler, directory, clang, runtime, args.profile)
            print(f'{compiler.name}: compiler behaviour passed ({args.profile})')


if __name__ == '__main__':
    main()
