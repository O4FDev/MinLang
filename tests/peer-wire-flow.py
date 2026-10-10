#!/usr/bin/env python3
"""Independent metadata/order models plus two-sided bounded relay state tests."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tests' / filename)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


model = module('wire_model', 'peer-wire.py')
auth = module('auth_fixtures', 'peer-auth.py')
tls = module('tls_fixtures', 'tls-local.py')


def strict_object(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate decoded key')
            result[key] = value
        return result

    def scalar_strings(value):
        if isinstance(value, str):
            value.encode('utf-8')
        elif isinstance(value, dict):
            for key, child in value.items():
                scalar_strings(key); scalar_strings(child)
        elif isinstance(value, list):
            for child in value:
                scalar_strings(child)
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=unique)
    scalar_strings(value)
    if not isinstance(value, dict):
        raise ValueError('object required')
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sanitize', action='store_true')
    options = parser.parse_args()
    env = dict(os.environ, MINYAR_CLANG=os.environ.get('MINYAR_TEST_CLANG', 'clang'))
    if options.sanitize:
        for name in ('MINYAR_CLANG_FLAGS', 'MINYAR_NATIVE_FLAGS', 'MINYAR_RUNTIME_FLAGS'):
            env[name] = '-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
        env['ASAN_OPTIONS'] = 'detect_leaks=1'; env['UBSAN_OPTIONS'] = 'halt_on_error=1'
    with tempfile.TemporaryDirectory(prefix='minyar-peer-wire-flow-') as directory:
        directory = Path(directory)
        # Independent OpenSSL fixture generation, never Minyar signing.
        auth.KEY = auth.OpenSSLSigner(directory)
        jwt = auth.token()
        (directory / 'grant').write_bytes(jwt); (directory / 'keys').write_bytes(auth.jwks())
        binary = directory / 'flow'
        subprocess.run([str(ROOT / 'minyar'), str(ROOT / 'tests/peer-wire-flow.min'), '-o', str(binary)], env=env, check=True, timeout=240)

        def run(mode, raw=b'', extra=b'', trap=False):
            (directory / 'frames').write_bytes(raw); (directory / 'extra').write_bytes(extra)
            result = subprocess.run([str(binary), mode, str(directory / 'grant'), str(directory / 'keys'),
                                     str(directory / 'frames'), str(directory / 'extra')], env=env,
                                    capture_output=True, text=True, timeout=60)
            if trap:
                assert result.returncode != 0 and 'cannot read a rejected wire frame' in result.stderr, result
            else:
                assert result.returncode == 0 and result.stderr == '', (mode, result.returncode, result.stdout, result.stderr)
            return result.stdout

        start = strict_object(run('start').encode())
        assert start == dict(dial_grant_bytes=jwt.decode(), exit_id='exit-a', conn_id='conn-1', target_host='example.com', port=443, expires=1060), start
        signed = strict_object(__import__('base64').urlsafe_b64decode(jwt.split(b'.')[1] + b'=' * (-len(jwt.split(b'.')[1]) % 4)))
        for field in ('exit_id', 'conn_id', 'target_host', 'port'):
            assert start[field] == signed[field]
        assert start['expires'] == signed['exp'] and start['dial_grant_bytes'].encode() == jwt
        assert run('verify-start', model.encode(model.START, 1, model.compact(start))) == 'VERIFIED example.com 443\n'
        for field, bad in [('exit_id', 'exit-b'), ('conn_id', 'conn-2'), ('target_host', 'evil.example'),
                           ('port', 80), ('expires', 1061), ('dial_grant_bytes', 'bad')]:
            assert run('verify-start', model.encode(model.START, 1, model.compact(dict(start, **{field: bad})))) == 'ERROR 8\n', field
        assert run('verify-start', model.encode(model.START, 1, model.compact(dict(start, target_ip='192.0.2.1')))) == 'ERROR 8\n'
        open_json = dict(dial_grant_bytes=jwt.decode(), exit_id='exit-a', conn_id='conn-1', deadline=1060)
        expected = 'OPEN exit-a conn-1 1060 ' + jwt.decode() + '\n'
        assert run('open', model.encode(model.OPEN, 1, model.compact(open_json))) == expected
        metadata_cases = 0
        for raw in [b'{}', b'[]', b'{', b'{"in_flight":0,"in_flight":1}', b'{"x":{"a":1,"\\u0061":2}}',
                    b'{"x":"\xff"}', b'{"x":"\\ud800"}', b'{"x":"\\ud83d\\ude00"}',
                    b'{"x":true}', b'{"in_flight":1,"max_concurrent":5,"paused":false}']:
            try:
                strict_object(raw)
                expected = 'OK\n'
            except (ValueError, UnicodeError):
                expected = 'ERROR 6\n'
            assert run('heartbeat', model.encode(model.HEARTBEAT, 0, raw)) == expected, raw
            metadata_cases += 1
        for field, bad in [('exit_id', ''), ('conn_id', 'conn/a'), ('deadline', 0), ('deadline', '1060'),
                           ('deadline', 1060.0), ('deadline', 9223372036854775808), ('dial_grant_bytes', '\xff')]:
            candidate = dict(open_json, **{field: bad})
            assert run('open', model.encode(model.OPEN, 1, model.compact(candidate))) == 'ERROR 6\n', candidate
            metadata_cases += 1
        for field in open_json:
            candidate = dict(open_json); del candidate[field]
            assert run('open', model.encode(model.OPEN, 1, model.compact(candidate))) == 'ERROR 6\n', field
            metadata_cases += 1
        for raw in [model.compact(open_json)[:-1] + b',"exit\\u005fid":"exit-a"}',
                    model.compact(open_json)[:-1] + b',"target_host":"evil.example"}']:
            assert run('open', model.encode(model.OPEN, 1, raw)) == 'ERROR 6\n'
            metadata_cases += 1
        ca = tls.Certificates(directory)
        ca.root('root'); ca.leaf('device', 'root', san='URI:hearth://device/device-a', usage='clientAuth', ec=True)
        certificate = ca.path('device', 'der').read_bytes()
        hello = model.encode(model.HELLO, 0, model.compact(dict(device_id='device-a', exit_id='exit-a')))
        heartbeat = model.encode(model.HEARTBEAT, 0, b'{"in_flight":0}')
        assert run('device', hello + heartbeat, certificate) == 'READY true\n'
        assert run('device', heartbeat, certificate) == 'ERROR 10\n'
        assert run('device', hello + hello, certificate) == 'ERROR 10\n'
        for candidate in [dict(device_id='device-b', exit_id='exit-a'), dict(device_id='device-a', exit_id='exit-b'), dict(device_id='device-a')]:
            assert run('device', model.encode(model.HELLO, 0, model.compact(candidate)), certificate) == 'ERROR 11\n'
        relay_cases = 0
        status = lambda name: model.encode(model.STATUS, 1, name.encode())
        data = lambda payload, stream=1: model.encode(model.DATA, stream, payload)
        close = model.encode(model.CLOSE, 1)
        scenarios = [
            (status('ok') + data(b'ab') + data(b'\0cd'), b'ab\0cd', 'STATE true false ok 5\n'),
            (status('ok') + data(b'ab') + close, b'ab', 'STATE false true ok 2\n'),
            (data(b'x'), b'', 'ERROR 10\nSTATE false false  0\n'),
            (close, b'', 'ERROR 10\nSTATE false false  0\n'),
            (status('ok') + status('ok'), b'', 'ERROR 10\nSTATE false false ok 0\n'),
            (status('ok') + data(b'x', 2), b'', 'ERROR 10\nSTATE false false ok 0\n'),
            (status('ok') + close + data(b'x'), b'', 'ERROR 10\nSTATE false false ok 0\n'),
            (status('garbage'), b'', 'ERROR 10\nSTATE false false  0\n'),
        ]
        for rejected in ('grant_invalid', 'exit_offline', 'policy_denied'):
            scenarios.append((status(rejected), b'', f'STATE false true {rejected} 0\n'))
            scenarios.append((status(rejected) + data(b'x'), b'', f'ERROR 10\nSTATE false false {rejected} 0\n'))
        for raw, received, expected in scenarios:
            assert run('relay', raw, received) == expected, (raw, expected)
            relay_cases += 1
        left = bytes(range(256)) * 41 + b'LEFT-END'
        right = bytes(reversed(range(256))) * 37 + b'RIGHT-END'
        assert run('bidirectional', left, right) == 'BIDIRECTIONAL OK\n'
        remaining = b''.join(bytes([i]) + b'\0' * 65535 for i in range(1, 17))
        exact_buffer = model.encode(model.DATA, 1, b'x' * 65520) * 16
        assert len(exact_buffer) == 1048576
        assert run('backpressure', remaining, exact_buffer) == 'BACKPRESSURE OK\n'
        run('trap', trap=True)
        print(f'Peer wire flow: {metadata_cases} independent metadata cases, {relay_cases} order/identity cases, exact JWT/target forwarding, cert-bound hello, two-sided bytes and 1MiB retry bounds passed')


if __name__ == '__main__':
    main()
