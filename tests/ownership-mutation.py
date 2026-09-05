#!/usr/bin/env python3
"""Check that exact accounting detects independently injected ownership leaks.

Only disposable source copies are mutated. This complements compiler mutation
tests and sanitizers, which do not detect leaks on every supported platform.
"""
import os
from pathlib import Path
import shutil
import resource
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    mutations = {
        'local retains transferred ownership': ('minyar_rc.h',
            'void minyar_rc_local_take(long long index, void *value) {\n',
            'void minyar_rc_local_take(long long index, void *value) {\n    minyar_rc_retain(value);\n'),
        'local replacement forgets previous owner': ('minyar_rc.h',
            '    minyar_rc_release(previous);', '    (void)previous;'),
        'list retains transferred ownership': ('minyar_runtime.c',
            'void minyar_list_add_take(MinyarList *list, long long value) {',
            'void minyar_list_add_take(MinyarList *list, long long value) {\n'
            '    minyar_rc_retain((void *)(intptr_t)value);'),
        'record retains transferred ownership': ('minyar_runtime.c',
            'void minyar_record_set_take(MinyarRecord *record, long long field, long long value) {',
            'void minyar_record_set_take(MinyarRecord *record, long long field, long long value) {\n'
            '    minyar_rc_retain((void *)(intptr_t)value);'),
    }
    with tempfile.TemporaryDirectory(prefix='minyar-ownership-mutants-') as temporary:
        directory = Path(temporary)
        (directory / 'runtime').mkdir()
        (directory / 'tests').mkdir()
        shutil.copyfile(ROOT / 'tests/runtime-unit.c', directory / 'tests/runtime-unit.c')
        for name, mutation in [('control', None), *mutations.items()]:
            for filename in ('minyar_rc.h', 'minyar_runtime.c'):
                text = (ROOT / 'runtime' / filename).read_text()
                if mutation and mutation[0] == filename:
                    assert text.count(mutation[1]) == 1, (name, 'mutation site changed')
                    text = text.replace(mutation[1], mutation[2])
                (directory / 'runtime' / filename).write_text(text)
            executable = directory / 'unit'
            subprocess.run([os.environ.get('MINYAR_TEST_CLANG', 'clang'), '-std=c11', '-O2',
                            str(directory / 'tests/runtime-unit.c'), '-o', str(executable)],
                           check=True, capture_output=True, timeout=30)
            result = subprocess.run([str(executable)], capture_output=True, timeout=15)
            if mutation:
                assert result.returncode != 0 and b'Assertion' in result.stderr, (name, result.stderr)
            else:
                assert result.returncode == 0, result.stderr
            print(name + ': ' + ('detected' if mutation else 'passed'), flush=True)
    print(f'All {len(mutations)} ownership mutants detected')


if __name__ == '__main__':
    main()
