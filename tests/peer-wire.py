#!/usr/bin/env python3
"""Independent HPW1 model encoder, bounded decoder, all-prefix/mutation controls."""
import argparse
import json
import os
from pathlib import Path
import random
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HELLO, HEARTBEAT, OPEN, STATUS, DATA, CLOSE, START = range(1, 8)
LIMIT = 1048576


def encode(kind, stream_id, payload=b''):
    return struct.pack('>4sB3xII', b'HPW1', kind, stream_id, len(payload)) + payload


def decode(raw):
    frames = []
    at = 0
    while at < len(raw):
        if len(raw) - at < 16:
            return frames, 12
        magic, kind, reserved, stream_id, size = struct.unpack('>4sB3sII', raw[at:at + 16])
        if magic != b'HPW1' or reserved != b'\0' * 3 or kind not in range(1, 8):
            return frames, 10
        if (kind in (HELLO, HEARTBEAT)) != (stream_id == 0):
            return frames, 10
        maximum = 65536 if kind == DATA else (0 if kind == CLOSE else (16 if kind == STATUS else 16384))
        if size > maximum or (kind != CLOSE and size == 0):
            return frames, 10
        if len(raw) - at - 16 < size:
            return frames, 12
        frames.append((kind, stream_id, raw[at + 16:at + 16 + size]))
        at += 16 + size
    return frames, 4


def compact(value):
    return json.dumps(value, separators=(',', ':')).encode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--red', action='store_true')
    parser.add_argument('--sanitize', action='store_true')
    options = parser.parse_args()
    env = dict(os.environ, MINYAR_CLANG=os.environ.get('MINYAR_TEST_CLANG', 'clang'))
    if options.sanitize:
        for name in ('MINYAR_CLANG_FLAGS', 'MINYAR_NATIVE_FLAGS', 'MINYAR_RUNTIME_FLAGS'):
            env[name] = '-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
        env['ASAN_OPTIONS'] = 'detect_leaks=1'; env['UBSAN_OPTIONS'] = 'halt_on_error=1'
    with tempfile.TemporaryDirectory(prefix='minyar-peer-wire-') as directory:
        directory = Path(directory)
        binary = directory / 'probe'
        subprocess.run([str(ROOT / 'minyar'), str(ROOT / 'tests/peer-wire.min'), '-o', str(binary)], env=env, check=True, timeout=240)
        raw_path = directory / 'wire'; payload_path = directory / 'payload'

        def run(raw, piece=1, mode='frames', args=()):
            raw_path.write_bytes(raw)
            result = subprocess.run([str(binary), mode, str(raw_path), str(piece), *map(str, args)], env=env, capture_output=True, text=True, timeout=60)
            assert result.returncode == 0, (mode, result.returncode, result.stderr)
            assert result.stderr == '', result.stderr
            return result.stdout

        def check(raw, piece=1):
            frames, error = decode(raw)
            expected = ''.join(f'FRAME {kind} {stream_id} {len(payload)}\n' for kind, stream_id, payload in frames) + f'FRAME_ERROR {error}\n'
            actual = run(raw, piece)
            assert actual == expected, (raw[:64].hex(), piece, expected, actual)

        if options.red:
            raw = encode(STATUS, 1, b'ok')
            assert decode(raw) == ([(STATUS, 1, b'ok')], 4)
            actual = run(raw)
            assert actual != 'FRAME 4 1 2\nFRAME_ERROR 4\n' and 'FRAME_ERROR 10' in actual, actual
            print('RED: independent valid HPW1 status rejected by initial stub')
            return
        fixtures = [
            (HELLO, 0, compact(dict(device_id='device-a', exit_id='exit-a'))),
            (HEARTBEAT, 0, compact(dict(in_flight=1, max_concurrent=5, paused=False))),
            (OPEN, 1, compact(dict(dial_grant_bytes='fixture.jwt.signature', exit_id='exit-a', conn_id='conn-1', deadline=1060))),
            (STATUS, 1, b'ok'), (DATA, 1, b'hello\0world'), (CLOSE, 1, b''),
            (START, 1, compact(dict(exit_id='exit-a', conn_id='conn-1', target_host='example.com', port=443, expires=1060))),
            (DATA, 4294967295, bytes(range(256)) * 256),
        ]
        prefix_count = 0
        for kind, stream_id, payload in fixtures:
            raw = encode(kind, stream_id, payload)
            check(raw, 1); check(raw, 7); check(raw, len(raw) + 1)
            raw_path.write_bytes(raw); payload_path.write_bytes(payload)
            result = subprocess.run([str(binary), 'prefixes', str(raw_path), str(kind), str(stream_id), str(payload_path)], env=env, capture_output=True, text=True, timeout=120)
            assert result.returncode == 0 and result.stdout == f'PREFIXES {len(raw) + 1}\n' and result.stderr == '', (kind, result.returncode, result.stdout, result.stderr)
            prefix_count += len(raw) + 1
        combined = b''.join(encode(*fixture) for fixture in fixtures)
        for piece in (1, 7, 16, 65536, len(combined)):
            check(combined, piece)
        for raw in [encode(0, 1, b'x'), encode(255, 1, b'x'), encode(HELLO, 1, b'{}'), encode(DATA, 0, b'x'),
                    encode(CLOSE, 1, b'x'), encode(DATA, 1, b'x' * 65537), encode(OPEN, 1, b'x' * 16385),
                    encode(STATUS, 1, b'x' * 17), encode(STATUS, 1, b''),
                    b'BAD1' + encode(DATA, 1, b'x')[4:]]:
            check(raw, 1)
        for offset in (5, 6, 7):
            raw = bytearray(encode(DATA, 1, b'x')); raw[offset] = 1; check(bytes(raw), 1)
        rng = random.Random(0x48505731)
        for index in range(500):
            raw = bytearray(encode(*rng.choice(fixtures[:-1])))
            if index % 4 == 0:
                raw = raw[:rng.randrange(len(raw) + 1)]
            else:
                for _ in range(1 + index % 3):
                    at = rng.randrange(len(raw)); raw[at] ^= 1 << rng.randrange(8)
            check(bytes(raw), rng.choice((1, 7, len(raw) + 1)))
        print(f'Peer wire framing: {prefix_count} complete all-prefix controls + 500 seeded independent model mutations passed')


if __name__ == '__main__':
    main()
