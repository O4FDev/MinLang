#!/usr/bin/env python3
"""Pinned cross-language JSON corpus plus seeded mutations and UTF-8 oracles.

The upstream y_/n_ classifications are authoritative; i_ cases must return
normally. Python's strict UTF-8 decoder and independent JSON parser classify
generated cases. Compile once per optimization and run all frames together.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile

from clang_helpers import clang_command
from llvm_sanitizer import prepare_llvm_for_link

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/json-parser'


def accepts(payload):
    def reject_constant(value):
        raise ValueError(value)
    try:
        json.loads(payload.decode('utf-8'), parse_constant=reject_constant)
        return True
    except (UnicodeError, ValueError):
        return False


def cases():
    manifest = json.loads((FIXTURES / 'manifest.json').read_text())
    files = sorted((FIXTURES / 'test_parsing').glob('*.json'))
    assert len(files) == 318 and {p.name for p in files} == set(manifest['sha256'])
    for path in files:
        payload = path.read_bytes()
        assert hashlib.sha256(payload).hexdigest() == manifest['sha256'][path.name], path
        expected = {'y': 1, 'n': 0, 'i': 2}[path.name[0]]
        yield path.name, expected, payload

    # Every possible two-byte sequence inside a string, plus lone bytes and
    # four-byte scalar boundaries, catches overlong encodings, surrogates,
    # bad continuations, raw controls, escapes, and out-of-range scalars.
    for first in range(256):
        payload = b'"' + bytes([first]) + b'"'
        yield f'byte-{first}', int(accepts(payload)), payload
        for second in range(256):
            payload = b'"' + bytes([first, second]) + b'"'
            yield f'pair-{first}-{second}', int(accepts(payload)), payload
    for sequence in [bytes.fromhex(value) for value in (
            'e09fbf', 'e0a080', 'ed9fbf', 'eda080', 'efbfbf',
            'f08fbfbf', 'f0908080', 'f48fbfbf', 'f4908080', 'f5808080')]:
        for cut in range(len(sequence) + 1):
            payload = b'"' + sequence[:cut] + b'"'
            yield f'scalar-{sequence.hex()}-{cut}', int(accepts(payload)), payload

    rng = random.Random(0x4a534f4e)
    for index in range(10000):
        payload = rng.randbytes(rng.randrange(33))
        yield f'arbitrary-{index}', int(accepts(payload)), payload
    for index in range(250):
        value = {'id': index, 'nested': [rng.randrange(-100000, 100000),
                 bool(index % 2), None, 'é🙂\\"\n\t' + chr(rng.randrange(32))],
                 'float': rng.uniform(-100, 100)}
        payload = json.dumps(value, ensure_ascii=bool(index % 2), separators=(',', ':')).encode()
        yield f'generated-{index}', 1, payload
        for cut in (0, 1, len(payload) // 2, len(payload) - 1):
            candidate = payload[:cut]
            yield f'prefix-{index}-{cut}', int(accepts(candidate)), candidate
        for mutation in range(8):
            candidate = bytearray(payload)
            candidate[rng.randrange(len(candidate))] ^= 1 << rng.randrange(8)
            candidate = bytes(candidate)
            yield f'mutation-{index}-{mutation}', int(accepts(candidate)), candidate
        yield f'trailing-{index}', 0, payload + b' true'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sanitize', action='store_true')
    args = parser.parse_args()
    compiler = Path(os.environ.get('MINYAR_TEST_COMPILER', ROOT / 'build/minyarc'))
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    flags = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if args.sanitize else []
    environment = os.environ.copy()
    environment['ASAN_OPTIONS'] = 'detect_leaks=1' if sys.platform.startswith('linux') else 'detect_leaks=0'
    environment['UBSAN_OPTIONS'] = 'halt_on_error=1'
    (ROOT / 'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='json-parser-', dir=ROOT / 'build') as temporary:
        work = Path(temporary)
        framing = work / 'corpus.bin'
        names = []
        with framing.open('wb') as stream:
            for name, expected, payload in cases():
                names.append(name)
                stream.write(struct.pack('>BI', expected, len(payload)) + payload)
        llvm = work / 'parser.ll'
        subprocess.run([compiler, ROOT / 'tests/json-parser.min', llvm,
                        '--library', ROOT / 'library'], check=True, timeout=60)
        prepare_llvm_for_link(llvm, flags)
        for optimization in ('-O0', '-O2'):
            runtime = work / f'runtime-{optimization[1:]}.o'
            executable = work / f'parser-{optimization[1:]}'
            subprocess.run(clang_command([clang, optimization, *flags, '-DMINYAR_SYSTEM_HEAP=1',
                '-c', ROOT / 'runtime/minyar_runtime.c', '-o', runtime]), check=True, timeout=60)
            subprocess.run(clang_command([clang, optimization, *flags, '-Wno-override-module',
                llvm, runtime, '-o', executable]), check=True, timeout=60)
            result = subprocess.run([executable, framing], capture_output=True, text=True,
                                    env=environment, timeout=60)
            if result.returncode or result.stderr or result.stdout != f'{len(names)}\n':
                # Retain the ordered case names in the failure text; the case
                # number in Minyar's diagnostic identifies the exact oracle.
                (ROOT / 'build/json-parser-failed-cases.json').write_text(json.dumps(names))
                raise AssertionError((optimization, result.returncode, result.stdout, result.stderr))
        print(f'JSON parser: {len(names)} independent corpus/mutation/UTF-8 cases at O0/O2')


if __name__ == '__main__':
    main()
