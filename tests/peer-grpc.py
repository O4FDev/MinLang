#!/usr/bin/env python3
"""Independent protobuf and HTTP/2 encoders for Hearth's bidi gRPC mapping."""
import argparse
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import random
import threading
from concurrent.futures import ThreadPoolExecutor
import grpc
import h2.connection
import h2.config
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

ROOT = Path(__file__).resolve().parents[1]
PATH = '/hearth.peer.v1.PeerGateway/Dial'

def proto():
    file = descriptor_pb2.FileDescriptorProto(name='peer.proto', package='hearth.peer.v1', syntax='proto3')
    opened = file.message_type.add(name='Open')
    for number, name, kind in [(1, 'dial_grant_bytes', 12), (2, 'exit_id', 9), (3, 'conn_id', 9), (4, 'deadline', 4)]:
        opened.field.add(name=name, number=number, type=kind, label=1)
    request = file.message_type.add(name='DialRequest'); request.oneof_decl.add(name='frame')
    request.field.add(name='open', number=1, type=11, type_name='.hearth.peer.v1.Open', label=1, oneof_index=0)
    request.field.add(name='data', number=2, type=12, label=1, oneof_index=0)
    status = file.enum_type.add(name='DialStatus')
    for number, name in enumerate(['UNSPECIFIED', 'OK', 'GRANT_INVALID', 'EXIT_OFFLINE', 'POLICY_DENIED']):
        status.value.add(name=name, number=number)
    response = file.message_type.add(name='DialResponse'); response.oneof_decl.add(name='frame')
    response.field.add(name='status', number=1, type=14, type_name='.hearth.peer.v1.DialStatus', label=1, oneof_index=0)
    response.field.add(name='data', number=2, type=12, label=1, oneof_index=0)
    pool = descriptor_pool.DescriptorPool(); pool.Add(file)
    return tuple(message_factory.GetMessageClass(pool.FindMessageTypeByName('hearth.peer.v1.' + name)) for name in ['Open', 'DialRequest', 'DialResponse'])

Open, Request, Response = proto()

def envelope(message):
    data = message.SerializeToString(); return b'\0' + struct.pack('>I', len(data)) + data

def client(timeout=None):
    result = h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=True, header_encoding='utf-8'))
    result.initiate_connection()
    fields = [(':method', 'POST'), (':scheme', 'https'), (':authority', 'peer.test'), (':path', PATH), ('content-type', 'application/grpc'), ('te', 'trailers')]
    if timeout is not None:
        fields.append(('grpc-timeout', timeout))
    result.send_headers(1, fields)
    return result

def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--red', action='store_true'); parser.add_argument('--sanitize', action='store_true'); options = parser.parse_args()
    env = dict(os.environ, MINYAR_CLANG=os.environ.get('MINYAR_TEST_CLANG', 'clang'))
    if options.sanitize:
        for name in ('MINYAR_CLANG_FLAGS', 'MINYAR_NATIVE_FLAGS', 'MINYAR_RUNTIME_FLAGS'):
            env[name] = '-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
        env['ASAN_OPTIONS'] = 'detect_leaks=1'; env['UBSAN_OPTIONS'] = 'halt_on_error=1'
    with tempfile.TemporaryDirectory(prefix='minyar-peer-grpc-') as directory:
        directory = Path(directory); binary = directory / 'probe'
        subprocess.run([str(ROOT / 'minyar'), str(ROOT / 'tests/peer-grpc.min'), '-o', str(binary)], env=env, check=True, timeout=240)
        peer = client(); peer.send_data(1, envelope(Request(open=Open(dial_grant_bytes=b'fixture.jwt.signature', exit_id='exit-a', conn_id='conn-1', deadline=1060))))
        path = directory / 'input'
        def run(raw, mode='', trap=False, extra=''):
            path.write_bytes(raw)
            result = subprocess.run([str(binary), str(path), str(directory / 'output'), mode, extra], env=env, capture_output=True, text=True, timeout=60)
            if trap:
                assert result.returncode != 0 and 'cannot read rejected gRPC open' in result.stderr, result
            else:
                assert result.returncode == 0 and result.stderr == '', (result.returncode, result.stdout, result.stderr)
            return result.stdout, (directory / 'output').read_bytes()
        raw = peer.data_to_send(); output, encoded = run(raw)
        if options.red:
            assert output == 'ERROR 1\n', output
            print('RED: independently encoded valid protobuf gRPC open rejected by initial stub')
        else:
            assert output == 'OPEN 1 exit-a conn-1 1060 fixture.jwt.signature\n', output
            peer.receive_data(encoded)
            for number, status in enumerate(('grant_invalid', 'exit_offline', 'policy_denied'), 2):
                peer = client(); peer.send_data(1, envelope(Request(open=Open(dial_grant_bytes=b'fixture.jwt.signature', exit_id='exit-a', conn_id='conn-1', deadline=1060))))
                output, encoded = run(peer.data_to_send(), 'reject', extra=status); events = peer.receive_data(encoded)
                response = b''.join(e.data for e in events if isinstance(e, h2.events.DataReceived))
                assert response[0] == 0 and len(response) == 7 and Response.FromString(response[5:]).status == number
                assert any(isinstance(e, h2.events.TrailersReceived) and ('grpc-status', '0') in e.headers for e in events)
            # Exact 500ms deadline remains authorized while time is left, despite Unix-second auth policy.
            for mode in ('timeout', 'timeout-wall'):
                peer = client('500m'); peer.send_data(1, envelope(Request(open=Open(dial_grant_bytes=b'fixture.jwt.signature', exit_id='exit-a', conn_id='conn-1', deadline=1060))))
                output, encoded = run(peer.data_to_send(), mode); assert output == 'TIMEOUT OK\n'
                events = peer.receive_data(encoded)
                assert any(isinstance(e, h2.events.TrailersReceived) and ('grpc-status', '4') in e.headers for e in events)
            # Independent protobuf bytes, first status, percent-encoded trailers and opaque data roundtrip.
            peer = client(); peer.send_data(1, envelope(Request(open=Open(dial_grant_bytes=b'fixture.jwt.signature', exit_id='exit-a', conn_id='conn-1', deadline=1060))))
            data = bytes(range(256)) * 100
            msg = envelope(Request(data=data))
            for at in range(0, len(msg), 8000): peer.send_data(1, msg[at:at+8000], end_stream=at + 8000 >= len(msg))
            output, encoded = run(peer.data_to_send(), 'echo'); events = peer.receive_data(encoded)
            response = b''.join(e.data for e in events if isinstance(e, h2.events.DataReceived))
            messages = []
            while response:
                assert response[0] == 0; size = int.from_bytes(response[1:5], 'big'); messages.append(Response.FromString(response[5:5+size])); response = response[5+size:]
            assert messages[0].status == 1 and messages[0].WhichOneof('frame') == 'status'
            assert b''.join(m.data for m in messages[1:]) == data
            assert any(isinstance(e, h2.events.TrailersReceived) and ('grpc-status', '0') in e.headers and ('grpc-message', 'done %25%0A') in e.headers for e in events)
            # Independent schema rejects repeated open, wrong oneof, missing IDs, bad deadline and compression.
            malformed = [b'\1\0\0\0\0', b'\0\0\1\0\5', envelope(Request(data=b'not-open')),
                         envelope(Request(open=Open(dial_grant_bytes=b'x', exit_id='exit-a', conn_id='conn-1'))),
                         envelope(Request(open=Open(dial_grant_bytes=b'x', exit_id='exit/a', conn_id='conn-1', deadline=1060))),
                         envelope(Request(open=Open(dial_grant_bytes=b'x', exit_id='exit-a', conn_id='conn-1', deadline=1000)))]
            for bad in malformed:
                peer = client(); peer.send_data(1, bad, end_stream=True)
                output, encoded = run(peer.data_to_send()); assert output == 'ERROR 10\n', (bad, output)
                assert any(isinstance(e, h2.events.TrailersReceived) and ('grpc-status', '13') in e.headers for e in peer.receive_data(encoded))
            opened = envelope(Request(open=Open(dial_grant_bytes=b'fixture.jwt.signature', exit_id='exit-a', conn_id='conn-1', deadline=1060)))
            data_message = envelope(Request(data=bytes(range(256))))
            prefix_count = 0
            for before, message in [(b'', opened), (opened, data_message)]:
                for cut in range(len(message) + 1):
                    peer = client(); peer.send_data(1, before + message[:cut], end_stream=True)
                    output, encoded = run(peer.data_to_send())
                    valid_boundary = cut == len(message) or (before and cut == 0)
                    assert output.startswith('OPEN 1 ') if valid_boundary else output == 'ERROR 10\n', (cut, len(message), output)
                    prefix_count += 1
            rng = random.Random(0x47525043)
            for index in range(150):
                bad = bytearray(opened)
                for _ in range(1 + index % 3):
                    at = rng.randrange(len(bad)); bad[at] ^= 1 << rng.randrange(8)
                peer = client(); peer.send_data(1, bytes(bad), end_stream=True)
                output, encoded = run(peer.data_to_send())
                assert output.startswith('OPEN 1 ') or output == 'ERROR 10\n', (index, bad.hex(), output)
                # Independent protobuf determines validity for mutations; native policy is stricter on IDs/deadlines.
                if output.startswith('OPEN 1 '):
                    assert bad[0] == 0 and int.from_bytes(bad[1:5], 'big') == len(bad) - 5
                    decoded = Request.FromString(bytes(bad[5:])); assert decoded.WhichOneof('frame') == 'open'
            run(b'', 'trap', trap=True)
            # Actual independent grpcio HTTP/2 client, simultaneous bidi calls, windows, cancellation and trailers.
            serving = directory / 'serve'
            subprocess.run([str(ROOT / 'minyar'), str(ROOT / 'tests/peer-grpc-serve.min'), '-o', str(serving)], env=env, check=True, timeout=240)
            process = subprocess.Popen([str(serving)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                port = int(process.stdout.readline().strip())
                with grpc.insecure_channel(f'127.0.0.1:{port}') as channel:
                    rpc = channel.stream_stream(PATH, request_serializer=Request.SerializeToString, response_deserializer=Response.FromString)
                    def transfer(index):
                        payload = bytes(range(256))[index:] * (200 + index * 5) + f'TAIL-{index}'.encode()
                        def outgoing():
                            yield Request(open=Open(dial_grant_bytes=b'fixture.jwt.signature', exit_id='exit-a', conn_id=f'conn-{index}', deadline=1060))
                            yield Request(data=bytes(range(256)) * 256) # Exact 64KiB crosses the initial flow-control window.
                            for at in range(0, len(payload), 8192): yield Request(data=payload[at:at+8192])
                        call = rpc(outgoing(), timeout=8)
                        responses = list(call)
                        assert responses[0].WhichOneof('frame') == 'status' and responses[0].status == 1
                        assert b''.join(message.data for message in responses[1:]) == bytes(range(256)) * 256 + payload
                        assert call.code() == grpc.StatusCode.OK
                    with ThreadPoolExecutor(max_workers=3) as pool:
                        list(pool.map(transfer, range(3)))
                    stopped = threading.Event()
                    def stalled():
                        yield Request(open=Open(dial_grant_bytes=b'fixture.jwt.signature', exit_id='exit-a', conn_id='cancel-me', deadline=1060))
                        stopped.wait(3)
                    cancelled = rpc(stalled(), timeout=5)
                    assert next(cancelled).status == 1
                    assert cancelled.cancel()
                    stopped.set()
                    transfer(3) # RST_STREAM must not poison concurrent connection state.
                process.wait(timeout=15)
                assert process.returncode == 0 and process.stderr.read() == '', (process.returncode, process.stderr.read())
            finally:
                if process.poll() is None:
                    process.kill(); process.wait()
                diagnostic = process.stderr.read()
                if process.returncode != 0 or diagnostic:
                    print('Native gRPC fixture diagnostics:', process.returncode, diagnostic)
            print(f'gRPC: {prefix_count} message prefixes + 150 protobuf mutations, independent open/status/data/trailers, 500ms backward-clock deadline, malformed controls and 3 concurrent grpcio 64KiB binary streams passed')

if __name__ == '__main__':
    main()
