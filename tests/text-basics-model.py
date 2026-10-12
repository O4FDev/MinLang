#!/usr/bin/env python3
"""Independent Python scalar/string and unbounded-integer runtime oracles.

Use --quick for a small native check; full profile/sanitizer matrices run on Boat.
"""
import argparse
import os
from pathlib import Path
import random
import subprocess
import tempfile
from clang_helpers import clang_command, windows_host

ROOT = Path(__file__).resolve().parents[1]
# Unicode White_Space, deliberately not Python's broader str.isspace set.
SPACE = ''.join(map(chr, [*range(9, 14), 32, 133, 160, 5760,
                        *range(8192, 8203), 8232, 8233, 8239, 8287, 12288]))

def cases():
    values = ['', ':', '::', 'a::b:', 'é🍊e\u0301零', '\0a\0', SPACE,
              '\u200b\ufeff\u001c', 'x' * 130 + '🍊' + 'x' * 65]
    needles = ['', ':', 'a', 'é', '🍊', 'e\u0301', '\0', 'xx', 'missing']
    pairs = [(text, needle) for text in values for needle in needles]
    rng = random.Random(0x573354)
    alphabet = 'ab:é零🍊\u0301\0' + SPACE + '\u200b\ufeff'
    for _ in range(500):
        text = ''.join(rng.choice(alphabet) for _ in range(rng.randrange(100)))
        needle = ''.join(rng.choice(alphabet) for _ in range(rng.randrange(5)))
        if rng.randrange(2) and text:
            start = rng.randrange(len(text))
            needle = text[start:start + rng.randrange(5)]
        pairs.append((text, needle))
    return pairs

def check(executable, env):
    pairs = cases()
    encoded = lambda text: text.encode().hex()
    source = ''.join(f'{encoded(t) or "-"} {encoded(n) or "-"}\n' for t, n in pairs)
    result = subprocess.run([str(executable)], input=source, capture_output=True,
                            text=True, env=env, timeout=30)
    assert result.returncode == 0, (result.stdout[-1000:], result.stderr)
    actual = result.stdout.splitlines()
    assert len(actual) == len(pairs)
    for (text, needle), line in zip(pairs, actual):
        pieces = text.split(needle) if needle else list(text)
        expected = (f'{text.find(needle)} {int(text.startswith(needle))} '
                    f'{int(text.endswith(needle))} {encoded(text.strip(SPACE))}|'
                    + '|'.join([str(len(pieces)), *map(encoded, pieces)]))
        assert line == expected, (text, needle, line, expected)
    valid = ['0', '-0', '+0', ' \t\r\n\v\f-42 \t', '00042',
             str(-(2**63)), str(2**63 - 1), '+' + str(2**63 - 1)]
    for source in valid:
        result = subprocess.run([str(executable), 'integer', encoded(source), ''],
                                capture_output=True, text=True, env=env, timeout=10)
        assert result.returncode == 0 and result.stdout == f'{int(source)}\n', result.stderr
    invalid = ['', ' ', '+', '-', '1x', '1 2', '0x2a', '1_000', '１２',
               '\u00a01', '1\0', str(2**63), str(-(2**63) - 1), '9' * 100]
    for source in invalid:
        result = subprocess.run([str(executable), 'integer', encoded(source), ''],
                                capture_output=True, text=True, env=env, timeout=10)
        assert result.returncode == 1 and 'Integer' in result.stderr, result
    malformed = ['80', 'c080', 'eda080', 'f4908080', 'e282', 'f0808080', '61ff']
    for bad in malformed:
        for operation in ('find', 'starts', 'ends', 'split', 'trim', 'integer'):
            operands = [(bad, '')]
            if operation not in ('trim', 'integer'):
                operands += [('', bad), ('61', '6162' + bad)]
            for left, right in operands:
                result = subprocess.run([str(executable), operation, left, right],
                                        capture_output=True, text=True, env=env, timeout=10)
                assert result.returncode == 1 and 'invalid UTF-8' in result.stderr, result
    return len(pairs)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clang', default=os.environ.get('MINYAR_TEST_CLANG', 'clang'))
    parser.add_argument('--quick', action='store_true')
    parser.add_argument('--cycles', action='store_true')
    parser.add_argument('--budget', type=int, choices=(1, 32), default=32)
    args = parser.parse_args()
    profiles = {'system': ['-DMINYAR_SYSTEM_HEAP=1'], 'eager': [],
                'fixed': ['-DMINYAR_BOUNDED_HEAP=1'],
                'lazy': ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_LAZY_HEAP=1'],
                'arena': ['-DMINYAR_COMPILER_ARENA=1']}
    if windows_host(): del profiles['lazy']
    if args.quick: profiles = {'system': profiles['system']}
    if args.cycles:
        import sys
        sys.path.insert(0, str(ROOT / 'tools'))
        from cycle_runtime import engine_source
        (ROOT / 'build').mkdir(exist_ok=True)
        (ROOT / 'build/managed-graphs-engine.c').write_text(engine_source(ROOT))
    env = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:halt_on_error=1',
           'UBSAN_OPTIONS': 'halt_on_error=1'}
    with tempfile.TemporaryDirectory(prefix='minyar-text-basics-') as tmp:
        for profile, flags in profiles.items():
            for sanitize in ([False] if args.quick else [False, True]):
                executable = Path(tmp) / (f'{profile}-{sanitize}' + ('.exe' if windows_host() else ''))
                command = [args.clang, '-std=c11', '-O1', '-I' + str(ROOT / 'runtime'),
                           f'-DMINYAR_RC_POLL_BUDGET={args.budget}', *flags]
                if args.cycles: command += ['-DTEXT_TEST_CYCLES=1']
                if sanitize: command += ['-fsanitize=address,undefined']
                command += [str(ROOT / 'tests/text-basics.c'), '-o', str(executable)]
                built = subprocess.run(clang_command(command), capture_output=True, text=True, timeout=60)
                assert built.returncode == 0, built.stderr
                count = check(executable, env)
                print(f'{profile} sanitize={sanitize} cycles={args.cycles} budget={args.budget}: {count} models, '
                      'parsing, malformed UTF-8 and ownership passed', flush=True)

if __name__ == '__main__': main()
