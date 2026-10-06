#!/usr/bin/env python3
"""Run previously unconnected scalar cleanup probes with assertions enabled."""
import json
import os
from pathlib import Path

from test_evidence import Evidence

ROOT = Path(__file__).resolve().parents[1]
PROBES = {
    'batched-transcript': None,
    'inline-scalar-leaf': b'inlined List leaf free preserves shared aliases and one-unit visits\n',
    'scalar-record-set': b'scalar-only setter preserves bounds/values; mixed-record scalar fields still service pending work\n',
    'unique-scalar-leaf': b'unique scalar fast free preserves1..8owners, mixed parents and exact units\n',
}


def main():
    inputs = [Path(__file__), ROOT / 'tests/test_evidence.py',
              ROOT / 'runtime/minyar_runtime.c', *sorted((ROOT / 'runtime').glob('*.h')),
              *(ROOT / f'tests/{name}.c' for name in PROBES)]
    native_transcripts = {}
    rows = []
    env = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0', 'UBSAN_OPTIONS': 'halt_on_error=1'}
    with Evidence('scalar-cleanup-probes', inputs=inputs) as evidence:
        for mode in ('native', 'sanitize'):
            flags = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if mode == 'sanitize' else []
            for budget in (1, 32, 1024):
                for name, expected in PROBES.items():
                    binary = evidence.path / f'{name}-{mode}-{budget}'
                    evidence.run([os.environ.get('CLANG', 'clang'), '-std=c11', '-O2', '-g',
                                  '-UNDEBUG', *flags, f'-DMINYAR_RC_POLL_BUDGET={budget}',
                                  ROOT / f'tests/{name}.c', '-o', binary],
                                 timeout=60, check=True, phase='compile-cleanup-probe')
                    result = evidence.run([binary], env=env, timeout=30, phase='execute-cleanup-probe')
                    assert result.returncode == 0 and result.stderr == b'', result
                    if expected is not None:
                        assert result.stdout == expected, result
                    else:
                        transcript = [list(map(int, line.split())) for line in result.stdout.splitlines()]
                        assert transcript and all(len(row) == 9 for row in transcript)
                        for index, row in enumerate(transcript):
                            assert row[0] == index and 0 <= row[1] <= budget, row
                        assert transcript[-1][2:4] == [0, 1], transcript[-1]
                        assert transcript[-1][-1] == 1, transcript[-1]
                        if mode == 'native':
                            native_transcripts[budget] = result.stdout
                        else:
                            assert result.stdout == native_transcripts[budget], 'Sanitizer changed cleanup transcript'
                    if name == 'scalar-record-set':
                        for argument, position in (('negative', -1), ('upper', 3)):
                            result = evidence.run([binary, argument], env=env, timeout=15,
                                                  phase='execute-scalar-bounds-rejection')
                            assert (result.returncode, result.stdout, result.stderr) == (
                                1, b'', f'Minyar stopped: List position {position} is outside its length of 3.\n'.encode()), result
                    rows.append({'probe': name, 'mode': mode, 'budget': budget})
    (ROOT / 'build/scalar-cleanup-probes.json').write_text(json.dumps({'status': 'passed', 'rows': rows}, indent=2) + '\n')
    print(f'{len(rows)} scalar cleanup probes and 12 bounds rejections passed')


if __name__ == '__main__':
    main()
