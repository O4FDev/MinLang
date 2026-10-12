#!/usr/bin/env python3
"""Standalone SHA vectors and seeded split differential checks (no heavy builds)."""
import argparse
import hashlib
import os
from pathlib import Path
import random
import struct
import tempfile
from sha256_support import ROOT, compile_min, run


def corpus(seed, random_cases):
    rng = random.Random(seed)
    cases = []
    boundaries = [0, 1, 2, 3, 7, 31, 55, 56, 57, 63, 64, 65, 119, 120, 127, 128, 129, 255, 256, 257, 1024]
    # Every prefix, including every cloned tail, at these block/padding boundaries.
    for length in boundaries:
        for prefix in range(length + 1):
            cases.append((rng.randbytes(length), prefix, [1] * (length - prefix)))
    for _ in range(random_cases):
        length = rng.randrange(8193)
        prefix = rng.randrange(length + 1)
        remaining = length - prefix
        splits = [0]
        while remaining:
            chunk = min(remaining, rng.choice([1, 7, 55, 56, 63, 64, 65, 128, rng.randrange(1, 1025)]))
            splits.extend([chunk, 0])
            remaining -= chunk
        cases.append((rng.randbytes(length), prefix, splits))
    frames, expected = [], []
    for data, prefix, splits in cases:
        frames.append(struct.pack('<III', len(data), prefix, len(splits)))
        frames.append(struct.pack('<' + 'I' * len(splits), *splits))
        frames.append(data)
        full = hashlib.sha256(data).hexdigest()
        snapshot = hashlib.sha256(data[:prefix]).hexdigest()
        extended = hashlib.sha256(data + b'!').hexdigest()
        branch = hashlib.sha256(data[:prefix] + b'?').hexdigest()
        expected.append(' '.join([full, full, snapshot, branch, full, full, extended]))
    return b''.join(frames), expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module', default='sha256', choices=['sha256', 'sha256pure'])
    parser.add_argument('--cases', type=int, default=256)
    parser.add_argument('--seed', type=int, default=0x5A256)
    parser.add_argument('--sanitize', action='store_true', help='ASan-annotate Minyar IR; instrument runtime and native sources')
    args = parser.parse_args()
    if args.cases < 0:
        parser.error('--cases must be nonnegative')
    if args.sanitize:
        os.environ.setdefault('ASAN_OPTIONS', 'detect_leaks=0')
    with tempfile.TemporaryDirectory(prefix='minyar-sha256-') as temporary:
        directory = Path(temporary)
        focused = compile_min(ROOT / 'tests/sha256.min', directory, args.module, sanitize=args.sanitize)
        print(run([focused]).stdout, end='')
        data, expected = corpus(args.seed, args.cases)
        path = directory / 'corpus.bin'
        path.write_bytes(data)
        executable = compile_min(ROOT / 'tests/sha256-splits.min', directory, args.module, sanitize=args.sanitize)
        actual = run([executable, path]).stdout.splitlines()
        assert len(actual) == len(expected), (len(actual), len(expected))
        for index, (got, want) in enumerate(zip(actual, expected)):
            assert got == want, (index, got, want)
        memory = compile_min(ROOT / 'tests/sha256-memory.min', directory, args.module, sanitize=args.sanitize)
        print(run([memory]).stdout, end='')
        print(f'{len(expected)} seeded split cases passed; seed={args.seed}; direct custom link passed')


if __name__ == '__main__':
    main()
