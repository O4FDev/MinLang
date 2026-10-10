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
    # Every non-leaf call runs minyar_stack_enter, so its common path must stay
    # two comparisons (depth limit, distance from the stack's low end); the
    # exact checks and the first-use bounds query live in the cold slow path.
    llvm = work / 'stack-enter.ll'
    command = clang_command([CLANG, '-O2', '-S', '-emit-llvm', ROOT / 'tests/stack-limits.c', '-o', llvm])
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    text = llvm.read_text()
    start = text.index('@minyar_stack_enter()')
    body = text[start:text.index('\n}\n', start)]
    assert body.count(' icmp ') == 2, body
    for name in ('@minyar_stack_bounds_ready', '@minyar_stack_high', '@minyar_find_stack_bounds'):
        assert name not in body, (name, body)
    print(f'stack limits: {cases} exact boundaries across native/fallback and O0/O2 passed; '
          'the guard common path is two comparisons')
