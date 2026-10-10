#!/usr/bin/env python3
"""Pinned independent h2/HPACK peer, RFC controls and hostile-input campaign."""
import argparse
import os
from pathlib import Path
import random
import struct
import subprocess
import tempfile
import h2.connection
import h2.config
import h2.events
import hpack

ROOT = Path(__file__).resolve().parents[1]
PREFACE = b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'
FIELDS = [(':method', 'POST'), (':scheme', 'https'), (':authority', 'peer.test'), (':path', '/hearth.peer.v1.PeerGateway/Dial'), ('content-type', 'application/grpc'), ('te', 'trailers')]

def frame(kind, flags=0, stream=0, body=b''):
    return len(body).to_bytes(3, 'big') + bytes([kind, flags]) + struct.pack('>I', stream) + body

def frames(raw):
    at = 0; result = []
    while at < len(raw):
        assert len(raw) - at >= 9
        size = int.from_bytes(raw[at:at + 3], 'big'); kind, flags = raw[at + 3:at + 5]; stream = int.from_bytes(raw[at + 5:at + 9], 'big')
        assert at + 9 + size <= len(raw)
        result.append((kind, flags, stream, raw[at + 9:at + 9 + size])); at += 9 + size
    return result

def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--red', action='store_true'); parser.add_argument('--sanitize', action='store_true'); options = parser.parse_args()
    env = dict(os.environ, MINYAR_CLANG=os.environ.get('MINYAR_TEST_CLANG', 'clang'))
    if options.sanitize:
        for name in ('MINYAR_CLANG_FLAGS', 'MINYAR_NATIVE_FLAGS', 'MINYAR_RUNTIME_FLAGS'):
            env[name] = '-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
        env['ASAN_OPTIONS'] = 'detect_leaks=1'; env['UBSAN_OPTIONS'] = 'halt_on_error=1'
    with tempfile.TemporaryDirectory(prefix='minyar-http2-') as directory:
        directory = Path(directory); binary = directory / 'probe'
        subprocess.run([str(ROOT / 'minyar'), str(ROOT / 'tests/http2.min'), '-o', str(binary)], env=env, check=True, timeout=240)
        def run(raw, mode='', piece=0):
            (directory / 'input').write_bytes(raw)
            result = subprocess.run([str(binary), str(directory / 'input'), str(directory / 'output'), mode, str(piece)], env=env, capture_output=True, text=True, timeout=60)
            assert result.returncode == 0 and result.stderr == '', (mode, result.returncode, result.stdout, result.stderr)
            return result.stdout, (directory / 'output').read_bytes() if mode != 'prefixes' else b''
        client = h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=True, header_encoding='utf-8'))
        client.initiate_connection(); client.send_headers(1, FIELDS)
        initial = client.data_to_send()
        output, encoded = run(initial)
        if options.red:
            assert output.startswith('ERROR 10'), output
            print('RED: independent valid HTTP/2 preface and HPACK request rejected by initial stub'); return
        expected = 'REQUEST 1\n' + ''.join(name + ' ' + value + '\n' for name, value in FIELDS)
        assert output == expected, output
        events = client.receive_data(encoded)
        assert any(isinstance(e, h2.events.RemoteSettingsChanged) for e in events)
        assert any(isinstance(e, h2.events.SettingsAcknowledged) for e in events)
        assert run(initial, 'prefixes')[0] == f'PREFIXES {len(initial) + 1}\n'
        prefix_count = len(initial) + 1
        for piece in (1, 7, 9, 31): assert run(initial, piece=piece)[0] == expected
        prefix = PREFACE + frame(4)
        encoder = hpack.Encoder()
        # Dynamic indexed references across streams, resize updates and continuation assembly.
        first = encoder.encode(FIELDS + [('x-shared', 'dynamic-value')]); second = encoder.encode(FIELDS + [('x-shared', 'dynamic-value')])
        assert len(second) < len(first)
        maximum_frame = prefix + frame(1, 4, 1, first) + frame(0, 1, 1, bytes(range(256)) * 64)
        assert run(maximum_frame, 'prefixes')[0] == f'PREFIXES {len(maximum_frame) + 1}\n'
        prefix_count += len(maximum_frame) + 1
        raw = prefix + frame(1, 0, 1, first[:5]) + frame(9, 4, 1, first[5:]) + frame(1, 4, 3, second)
        output, encoded = run(raw, piece=1); assert 'REQUEST 1\n' in output and 'REQUEST 3\n' in output and output.count('x-shared dynamic-value\n') == 2
        encoder.header_table_size = 0; third = encoder.encode(FIELDS)
        assert 'REQUEST 5\n' in run(raw + frame(1, 4, 5, third))[0]
        # Official RFC7541 C.4.1 Huffman request vector, independent of the peer encoder.
        rfc = bytes.fromhex('828684418cf1e3c2e5f23a6ba0ab90f4ff')
        assert ':authority www.example.com\n' in run(prefix + frame(1, 4, 1, rfc))[0]
        visible = '!' + ''.join(chr(i) for i in range(32, 127)) + '!'
        assert 'x-symbols ' + visible + '\n' in run(prefix + frame(1, 4, 1, hpack.Encoder().encode(FIELDS + [('x-symbols', visible)])))[0]
        # Exercise every octet symbol through the independent encoder. Opaque
        # non-ASCII fields violate our gateway contract, so the stream is reset
        # only after successful Huffman decoding (not COMPRESSION_ERROR).
        symbols_encoder = hpack.Encoder()
        all_symbols = symbols_encoder.encode(FIELDS + [(b'x-all-symbols', bytes(range(256)))])
        after_symbols = symbols_encoder.encode(FIELDS + [('x-next', 'valid-after-rejection')])
        output, encoded = run(prefix + frame(1, 4, 1, all_symbols) + frame(1, 4, 3, after_symbols))
        assert output.startswith('REQUEST 3\n') and 'valid-after-rejection' in output and any(kind == 3 and int.from_bytes(body, 'big') == 1 for kind, flags, sid, body in frames(encoded))
        errors = [
            (b'X' + initial[1:], 1), (PREFACE + frame(6, body=b'12345678'), 1),
            (prefix + frame(4, 1, body=b'x'), 6), (prefix + frame(4, stream=1), 1),
            (prefix + frame(4, body=b'x'), 6), (prefix + frame(4, body=struct.pack('>HI', 4, 0x80000000)), 3),
            (prefix + frame(4, body=struct.pack('>HI', 5, 16383)), 1),
            (prefix + frame(6, body=b'x'), 6), (prefix + frame(6, stream=1, body=b'12345678'), 1),
            (prefix + frame(1, 4, 2, first), 1), (prefix + frame(1, 4, 0, first), 1),
            (prefix + frame(9, 4, 1, first), 1), (prefix + frame(1, 0, 1, first) + frame(6, body=b'12345678'), 1),
            (prefix + frame(1, 4, 1, b'\x80'), 9), (prefix + frame(1, 4, 1, b'\xff\xff\xff\xff\xff\xff'), 9),
            (prefix + frame(1, 4, 1, b'\x3f\xe2\x1f'), 9),
            (prefix + frame(1, 4, 1, b'\x00\x81\xff\x00'), 9), # Excessive Huffman EOS padding.
            (prefix + frame(1, 4, 1, b'\x00\x84\xff\xff\xff\xff\x00'), 9), # Explicit EOS.
            (prefix + frame(0, stream=1, body=b'x'), 1), (prefix + frame(3, stream=1, body=b'\0'*4), 1),
            (prefix + frame(8, body=b'\0'*4), 1), (prefix + frame(8, body=b'x'), 6),
            (prefix + frame(5, stream=2, body=b'\0'*4), 1),
            (prefix + b'\x00\x40\x01\x00\x00\x00\x00\x00\x01', 6),
        ]
        for raw, code in errors:
            output, encoded = run(raw, piece=1)
            assert output == f'ERROR 10 {code}\n', (raw[-32:].hex(), output, code)
            assert any(kind == 7 and int.from_bytes(body[4:8], 'big') == code for kind, flags, sid, body in frames(encoded))
        malformed = [FIELDS + [('Upper', 'bad')], FIELDS + [('invalid/name', 'bad')], FIELDS + [('connection', 'close')], FIELDS + [('te', 'gzip')],
                     FIELDS + [(':method', 'GET')], FIELDS + [('x-test', '\r\n')], FIELDS + [('x-test', ' leading')],
                     FIELDS + [('content-length', '1')], FIELDS + [('content-length', '0'), ('content-length', '0')],
                     [(':method', 'POST'), (':scheme', 'https')]]
        for fields in malformed:
            raw = prefix + frame(1, 5, 1, hpack.Encoder().encode(fields))
            output, encoded = run(raw)
            assert output == '', output
            # Invalid control octets fail bounded HPACK ASCII contract; generic field errors reset stream.
            assert any((kind == 3 and sid == 1 and int.from_bytes(body, 'big') == 1) or kind == 7 for kind, flags, sid, body in frames(encoded)), fields
        payload = bytes(range(256)) * 100
        client = h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=True, header_encoding='utf-8'))
        client.initiate_connection(); client.send_headers(1, FIELDS)
        for at in range(0, len(payload), 8000): client.send_data(1, payload[at:at + 8000], end_stream=at + 8000 >= len(payload))
        output, encoded = run(client.data_to_send(), 'echo', 7); events = client.receive_data(encoded)
        assert b''.join(e.data for e in events if isinstance(e, h2.events.DataReceived)) == payload
        assert any(isinstance(e, h2.events.TrailersReceived) and ('x-final', 'done') in e.headers for e in events)
        assert any(isinstance(e, h2.events.StreamEnded) for e in events)
        assert run(prefix, 'timer')[0] == 'TIMER OK\n'
        # True flow-control stall, exact send budget, no-consumption overload and retry.
        bounds = directory / 'bounds'
        subprocess.run([str(ROOT / 'minyar'), str(ROOT / 'tests/http2-bounds.min'), '-o', str(bounds)], env=env, check=True, timeout=240)
        peer = h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=True, header_encoding='utf-8'))
        peer.initiate_connection(); peer.update_settings({h2.settings.SettingCodes.INITIAL_WINDOW_SIZE: 0}); peer.send_headers(1, FIELDS)
        (directory / 'input').write_bytes(peer.data_to_send())
        credits = frame(8, stream=1, body=struct.pack('>I', 65535))
        (directory / 'credits').write_bytes(credits)
        result = subprocess.run([str(bounds), str(directory / 'input'), str(directory / 'credits'), str(directory / 'output')], env=env, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0 and result.stdout == 'BOUNDS OK\n' and result.stderr == '', result
        emitted = frames((directory / 'output').read_bytes())
        assert b''.join(body for kind, flags, sid, body in emitted if kind == 0) == bytes(range(256)) * 255 + bytes(range(255))
        # Seeded hostile frame/HPACK mutations: repeat in 1-byte and whole-input chunks.
        rng = random.Random(0x48325031)
        for i in range(250):
            raw = bytearray(initial)
            for _ in range(1 + i % 3):
                at = rng.randrange(len(raw)); raw[at] ^= 1 << rng.randrange(8)
            if i % 5 == 0: raw = raw[:rng.randrange(len(raw) + 1)]
            one = run(bytes(raw), piece=1); all_at_once = run(bytes(raw))
            assert one == all_at_once, (i, raw.hex(), one, all_at_once)
        print(f'HTTP/2: {prefix_count} request/maximum-DATA prefixes, RFC7541/all-symbol Huffman, dynamic table/continuations, {len(errors)} errors, {len(malformed)} header controls, 1MiB/flow retry boundaries, binary response/trailers and 250 seeded mutations passed')

if __name__ == '__main__':
    main()
