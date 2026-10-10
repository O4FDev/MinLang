#!/usr/bin/env python3
"""RFC 9001/9369 published packet oracles, independent of our serializer.
Includes every-byte tampering/truncation and Retry binding to original DCID.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **options):
    result = subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=120, **options)
    if result.returncode:
        raise AssertionError(f'{args[0]} exited {result.returncode}:\n{result.stdout}\n{result.stderr[-4000:]}')
    return result.stdout.strip().splitlines()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sanitize', action='store_true')
    options = parser.parse_args()
    environment = dict(os.environ)
    if options.sanitize:
        flags = '-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
        for name in ('MINYAR_CLANG_FLAGS', 'MINYAR_NATIVE_FLAGS', 'MINYAR_RUNTIME_FLAGS'):
            environment[name] = flags
    with tempfile.TemporaryDirectory(prefix='minyar-quic-crypto-') as temporary:
        binary = Path(temporary) / 'quic-crypto.exe'
        command = [ROOT / 'minyar', '--library', ROOT / 'library', ROOT / 'tests/quic-crypto.min', '-o', binary]
        if os.name == 'nt':
            command.insert(0, shutil.which('bash') or 'bash')
        run(*command, env=environment)
        for rfc in (9001, 9369):
            fixture = json.loads((ROOT / f'tests/fixtures/quic-rfc{rfc}.json').read_text())
            version = fixture['version']
            for role, pn, offset in [('client', 2, 18), ('server', 1, 18)]:
                vector = fixture[role]
                payload = bytes.fromhex(vector['payload'])
                if role == 'client':
                    payload += bytes(1162 - len(payload))
                actual = run(binary, role, version, vector['header'], payload.hex(), pn, offset)
                assert actual == [vector['packet']], f'RFC {rfc} {role} mismatch'
            actual = run(binary, 'chacha', version, fixture['chacha_header'], '01', 654360564, 1)
            assert actual == [fixture['chacha_packet']], f'RFC {rfc} ChaCha mismatch'
            assert run(binary, 'retry', version, fixture['retry'], fixture['dcid']) == ['true']
            assert run(binary, 'retry-tag', version, fixture['retry'], fixture['dcid']) == [fixture['retry'][-32:]]
            assert run(binary, 'retry', version, fixture['retry'], '8394c8f03e515709') == ['false']
            bad = bytes.fromhex(fixture['retry'])
            for index in range(len(bad)):
                changed = bytearray(bad)
                changed[index] ^= 1
                assert run(binary, 'retry', version, changed.hex(), fixture['dcid']) == ['false']
            print(f'RFC {rfc}: Initial client/server, ChaCha, Retry, all-byte tamper/truncation passed')


if __name__ == '__main__':
    main()
