#!/usr/bin/env python3
"""Native-bound and fallback call limits keep their exact configured boundary."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]
CLANG = os.environ.get('MINYAR_TEST_CLANG', 'clang')
FLAGS = shlex.split(os.environ.get('MINYAR_TEST_LINK_FLAGS', ''))
MESSAGE = 'Minyar stopped: the program exceeded the maximum call depth.\n'

with tempfile.TemporaryDirectory(prefix='minyar-stack-limits-') as temporary:
    work = Path(temporary)
    cases = 0
    for maximum, fallback in ((8, 3), (2, 7)):
        for known in (True, False):
            for optimization in ('-O0', '-O2'):
                executable = work / f'limits-{maximum}-{fallback}-{known}-{optimization[1:]}'
                command = clang_command([CLANG, optimization, *FLAGS,
                    f'-DMINYAR_MAX_CALL_DEPTH={maximum}',
                    f'-DMINYAR_FALLBACK_CALL_DEPTH={fallback}',
                    *([] if known else ['-DMINYAR_TEST_NO_STACK_BOUNDS']),
                    ROOT / 'tests/stack-limits.c', '-o', executable])
                result = subprocess.run(command, capture_output=True, text=True, timeout=60)
                assert result.returncode == 0, result.stderr
                limit = maximum if known else min(maximum, fallback)
                for count in (1, limit, limit + 1):
                    result = subprocess.run([executable, str(count)], capture_output=True,
                                            text=True, timeout=10)
                    expected = 0 if count <= limit else 1
                    assert result.returncode == expected, (maximum, fallback, known, count, result)
                    assert result.stdout == '', result.stdout
                    assert result.stderr == (MESSAGE if expected else ''), result.stderr
                    cases += 1
    print(f'stack limits: {cases} exact boundaries across native/fallback and O0/O2 passed')
