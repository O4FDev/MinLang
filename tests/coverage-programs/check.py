import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tests'))
from clang_helpers import clang_command
from cycle_runtime import engine_source
from llvm_sanitizer import prepare_llvm_for_link

COMPILER = Path(os.environ.get('MINYAR_TEST_COMPILER', ROOT / 'build/minyarc')).resolve()
CLANG = os.environ.get('MINYAR_TEST_CLANG', 'clang')
FLAGS = shlex.split(os.environ.get('MINYAR_TEST_LINK_FLAGS', ''))
SUITES = ('callbacks', 'errors-language', 'errors-values', 'thread-compiler',
          'incremental-language-hardening', 'incremental-modules')
CASES = {
    'nested': '7\n-1\n',
    'ownership': '0\nfresh text\n3\n',
    'control-flow': '42\nfalse\nfalse\n10\n',
    'limits': '-1\n0\n14\n14\n0\nfalse\n42\n-1\n',
    'results-imports': '12\nfalse\n',
}


def checked(command, **options):
    result = subprocess.run(command, capture_output=True, text=True, timeout=600, **options)
    if result.returncode:
        raise RuntimeError(f'{command}:\n{result.stdout}{result.stderr}')
    return result


def main():
    environment = dict(os.environ, MINYAR_CALLBACK_COMPILER=str(COMPILER),
        MINYAR_ERRORS_COMPILER=str(COMPILER), MINYAR_TEST_MODULE_COMPILER=str(COMPILER),
        MINYAR_MODULE_CALLBACK_COMPILER=str(COMPILER))
    suites = list(SUITES)
    if (ROOT / 'compiler/stages/c-layout.min').is_file():
        suites.append('c-layout-records')
    for suite in suites:
        result = checked([sys.executable, str(ROOT / 'tests' / (suite + '.py'))],
                         cwd=ROOT, env=environment)
        print(suite + ': passed', flush=True)
    with tempfile.TemporaryDirectory(prefix='minyar-integrated-coverage-') as temporary:
        work = Path(temporary)
        runtime_source = work / 'runtime.c'
        runtime_source.write_text(engine_source(ROOT) + '\n#include "minyar_stack_frames.h"\n')
        runtime = work / 'runtime.o'
        checked(clang_command([CLANG, '-O1', *FLAGS, '-DMINYAR_SYSTEM_HEAP=1',
            '-iquote', ROOT / 'runtime', '-c', runtime_source, '-o', runtime]))
        for name, expected in CASES.items():
            llvm = work / (name + '.ll')
            checked([str(COMPILER), str(ROOT / 'tests/calldepth' / (name + '.min')),
                str(llvm), '--bounded-owners', '32', '--library', str(ROOT / 'library')])
            prepare_llvm_for_link(llvm, FLAGS)
            for optimization in ('-O0', '-O2'):
                executable = work / (name + optimization)
                checked(clang_command([CLANG, optimization, *FLAGS, '-Wno-override-module',
                    llvm, runtime, '-pthread', '-lm', '-o', executable]))
                result = checked([str(executable)])
                if (result.stdout, result.stderr) != (expected, ''):
                    raise RuntimeError(f'{name}: unexpected output {result.stdout!r} {result.stderr!r}')
            print(name + ': passed', flush=True)


if __name__ == '__main__':
    main()
