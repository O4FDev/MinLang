#!/usr/bin/env python3
"""Independent integer/frame oracle, all proper prefixes, seeded mutation.
ngtcp2's tests motivate exhaustive truncation; Quinn's protocol harness motivates
clock/socket-independent parsing. The oracle never calls Minyar's serializer.
"""
import argparse
import json
import os
from pathlib import Path
import random
import struct
import tempfile
from importlib.util import module_from_spec, spec_from_file_location

ROOT = Path(__file__).resolve().parents[1]
spec = spec_from_file_location('quic_crypto_tests', ROOT / 'tests/quic-crypto.py')
helpers = module_from_spec(spec)
spec.loader.exec_module(helpers)


def vi(value, length=None):
    if length is None:
        length = next(n for n in (1, 2, 4, 8) if value < 1 << (8 * n - 2))
    return (value | ({1: 0, 2: 1, 4: 2, 8: 3}[length] << (8 * length - 2))).to_bytes(length, 'big')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sanitize', action='store_true')
    options = parser.parse_args()
    env = dict(os.environ)
    if options.sanitize:
        for name in ('MINYAR_CLANG_FLAGS', 'MINYAR_NATIVE_FLAGS', 'MINYAR_RUNTIME_FLAGS'):
            env[name] = '-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
    rng = random.Random(9000)
    with tempfile.TemporaryDirectory(prefix='minyar-quic-wire-') as temporary:
        temporary = Path(temporary)
        binary = temporary / 'wire.exe'
        command = [ROOT / 'minyar', '--library', ROOT / 'library', ROOT / 'tests/quic-wire.min', '-o', binary]
        if os.name == 'nt':
            command.insert(0, helpers.shutil.which('bash') or 'bash')
        helpers.run(*command, env=env)

        def check(mode, cases):
            corpus = temporary / f'{mode}.bin'
            corpus.write_bytes(b''.join(struct.pack('>I', len(data)) + data for data, _ in cases))
            actual = helpers.run(binary, mode, corpus)
            assert len(actual) == len(cases), (mode, len(actual), len(cases))
            for index, ((data, wanted), output) in enumerate(zip(cases, actual)):
                if wanted == 'accepted':
                    assert output.startswith('ok '), (mode, index, data.hex(), output)
                elif wanted is not None:
                    assert output == wanted, (mode, index, data.hex(), wanted, output)

        ints = [0, 1, 63, 64, 16383, 16384, (1 << 30) - 1, 1 << 30, (1 << 62) - 1]
        ints += [rng.randrange(1 << 62) for _ in range(2000)]
        cases = [(b'', 'rejected')]
        for value in ints:
            for n in (1, 2, 4, 8):
                if value >= 1 << (8 * n - 2):
                    continue
                data = vi(value, n)
                cases.append((data + b'\xff', f'{value} {n}'))
                cases.extend((data[:i], 'rejected') for i in range(n))
        check('varint', cases)

        # Every RFC 9000 base frame. STREAM with explicit length permits
        # testing that every truncated prefix is rejected.
        frames = [b'\x01', b'\x02' + vi(9) + vi(0) + vi(1) + vi(2) + vi(1) + vi(1),
                  b'\x03' + vi(9) + vi(0) + vi(0) + vi(2) + vi(1) + vi(2) + vi(3),
                  b'\x04' + vi(0) + vi(4) + vi(19), b'\x05' + vi(0) + vi(7),
                  b'\x06' + vi(12) + vi(5) + b'hello', b'\x07' + vi(5) + b'token']
        frames += [bytes([kind]) + vi(4) + (vi(9) if kind & 4 else b'') + vi(5) + b'hello'
                   for kind in (10, 11, 14, 15)]
        frames += [bytes([kind]) + vi(1000) for kind in (16, 18, 19, 20, 22, 23, 25)]
        frames += [bytes([kind]) + vi(4) + vi(1000) for kind in (17, 21)]
        frames += [b'\x18' + vi(2) + vi(1) + b'\x08abcdefgh' + bytes(range(16)),
                   b'\x1a12345678', b'\x1b12345678',
                   b'\x1c' + vi(10) + vi(6) + vi(3) + b'bye', b'\x1d' + vi(10) + vi(3) + b'bye', b'\x1e']
        cases = [(frame, 'accepted') for frame in frames]
        cases += [(frame[:i], 'rejected') for frame in frames for i in range(1, len(frame))]
        cases += [(vi(kind, 2) + frame[1:], 'rejected') for kind, frame in zip([f[0] for f in frames], frames)]
        cases += [(b'\x02\x00\x00\x00\x01', 'rejected'),  # ACK underflow
                  (b'\x02\x01\x00\x01\x00\x00\x00', 'rejected'),
                  (b'\x06' + vi((1 << 62) - 1) + vi(1) + b'a', 'rejected'),
                  (b'\x12' + vi((1 << 60) + 1), 'rejected'),
                  (b'\x18\x01\x02\x08abcdefgh' + bytes(16), 'rejected'),
                  (b'\x18\x01\x00\x00' + bytes(16), 'rejected'),
                  (b'\x07\x00', 'rejected'), (b'\x1f', 'rejected')]
        cases += [(bytes(rng.randrange(256) for _ in range(rng.randrange(512))), None) for _ in range(10000)]
        cases += [(bytes(65535), 'ok 0:0:0:false:0:;'), (bytes(65536), 'rejected')]
        check('frames', cases)

        # Published headers, independently known packet-number offset and
        # packet boundary; coalescing must stop at the long-header Length.
        cases = []
        for rfc in (9001, 9369):
            fixture = json.loads((ROOT / f'tests/fixtures/quic-rfc{rfc}.json').read_text())
            for role in ('client', 'server'):
                packet = bytes.fromhex(fixture[role]['packet'])
                cases.append((packet, f'0 {len(packet)} 18'))
                cases.append((packet + bytes.fromhex(fixture['server']['packet']), f'0 {len(packet)} 18'))
                cases.extend((packet[:i], 'rejected') for i in range(len(packet)))
            packet = bytes.fromhex(fixture['retry'])
            cases.append((packet, f'3 {len(packet)} 0'))
        cases += [(b'\x80\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01', '5 11 0'),
                  (b'\x80\x00\x00\x00\x00\x00\x00\x01', 'rejected'),
                  (b'\xc0\x00\x00\x00\x01\x15' + bytes(100), 'rejected')]
        cases += [(bytes(rng.randrange(256) for _ in range(rng.randrange(512))), None) for _ in range(10000)]
        check('header', cases)
        identifier=b'abcdefgh'
        prefix=b'\xc0'+bytes.fromhex('00000001')+b'\x08'+identifier
        check('destination', [(prefix,identifier.hex()),(b'\x40'+identifier,identifier.hex())]+
             [(b'\x40'+identifier[:i],'rejected') for i in range(8)]+
             [(prefix[:i],'rejected') for i in range(len(prefix))]+
             [(b'\x00'+identifier,'rejected'),(b'\xc0'+bytes(4)+b'\x15'+bytes(21),'rejected')])
        unsupported=b'\xc0'+bytes.fromhex('57414954')+b'\x08'+identifier+b'\x04peer'
        # First byte contains random reserved bits; the remaining bytes are an
        # independent RFC 9000 Section 6 CID-swap/version-list oracle.
        check('negotiate', [(unsupported+bytes(1200-len(unsupported)),
              '00000000047065657208616263646566676800000001')]+
              [(unsupported[:i],'rejected') for i in range(len(unsupported))]+
              [(prefix+bytes(1200-len(prefix)),'rejected')])

        parameters = vi(15) + vi(8) + b'abcdefgh'
        cases = [(parameters, 'ok 1')]
        cases += [(parameters[:i], 'rejected') for i in range(len(parameters))]
        for key, value in ((3, 1199), (10, 21), (11, 16384), (14, 1), (8, (1 << 60) + 1)):
            body = vi(value)
            cases.append((parameters + vi(key) + vi(len(body)) + body, 'rejected'))
        cases += [(parameters + parameters, 'rejected'), (parameters + b'\x0c\x01a', 'rejected')]
        cases += [(bytes(rng.randrange(256) for _ in range(rng.randrange(256))), None) for _ in range(10000)]
        check('parameters', cases)
        print('QUIC wire: independent varints, RFC headers, all frame prefixes, constraints, 30,000 seeded parser mutations passed')


if __name__ == '__main__':
    main()
