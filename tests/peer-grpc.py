#!/usr/bin/env python3
"""Independent protobuf/HTTP2 clients for Tolum's normative PeerEdgeDial schema."""
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
import h2.events
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

ROOT = Path(__file__).resolve().parents[1]
PATH = '/PeerEdgeDial/OpenExitStream'

def proto():
    file = descriptor_pb2.FileDescriptorProto(name='peer.proto', syntax='proto3')
    opened = file.message_type.add(name='OpenExitStreamRequest')
    for number, name, kind in [(1, 'dial_grant', 12), (2, 'exit_id', 9), (3, 'conn_id', 9)]:
        opened.field.add(name=name, number=number, type=kind, label=1)
    status = file.message_type.add(name='ExitStatus'); codes = status.enum_type.add(name='Code')
    for number, name in enumerate(['OK', 'GRANT_INVALID', 'EXIT_OFFLINE', 'POLICY_DENIED', 'CONCURRENCY_FULL']):
        codes.value.add(name=name, number=number)
    status.field.add(name='code', number=1, type=14, type_name='.ExitStatus.Code', label=1)
    status.field.add(name='detail', number=2, type=9, label=1)
    frame = file.message_type.add(name='ExitByteFrame'); frame.oneof_decl.add(name='body')
    frame.field.add(name='open', number=1, type=11, type_name='.OpenExitStreamRequest', label=1, oneof_index=0)
    frame.field.add(name='status', number=2, type=11, type_name='.ExitStatus', label=1, oneof_index=0)
    frame.field.add(name='data', number=3, type=12, label=1, oneof_index=0)
    pool = descriptor_pool.DescriptorPool(); pool.Add(file)
    return tuple(message_factory.GetMessageClass(pool.FindMessageTypeByName(name)) for name in ['OpenExitStreamRequest', 'ExitByteFrame', 'ExitStatus'])

Open, Request, Status = proto(); Response = Request

def opened(connection='conn-1'):
    return Request(open=Open(dial_grant=b'fixture.jwt.signature', exit_id='exit-a', conn_id=connection))

def envelope(message):
    data = message.SerializeToString(); return b'\0' + struct.pack('>I', len(data)) + data

def messages(events):
    raw = b''.join(e.data for e in events if isinstance(e, h2.events.DataReceived)); result = []
    while raw:
        assert raw[0] == 0 and len(raw) >= 5
        size = int.from_bytes(raw[1:5], 'big'); assert len(raw) >= size + 5
        result.append(Response.FromString(raw[5:5+size])); raw = raw[5+size:]
    return result

def client(timeout=None, route=PATH):
    result = h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=True, header_encoding='utf-8'))
    result.initiate_connection()
    fields = [(':method', 'POST'), (':scheme', 'https'), (':authority', 'peer.test'), (':path', route), ('content-type', 'application/grpc'), ('te', 'trailers')]
    if timeout is not None: fields.append(('grpc-timeout', timeout))
    result.send_headers(1, fields)
    return result

def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--compat-red', action='store_true'); parser.add_argument('--sanitize', action='store_true'); parser.add_argument('--library', type=Path); options = parser.parse_args()
    env = dict(os.environ, MINYAR_CLANG=os.environ.get('MINYAR_TEST_CLANG', 'clang'))
    if options.sanitize:
        for name in ('MINYAR_CLANG_FLAGS', 'MINYAR_NATIVE_FLAGS', 'MINYAR_RUNTIME_FLAGS'):
            env[name] = '-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
        env['ASAN_OPTIONS'] = 'detect_leaks=1'; env['UBSAN_OPTIONS'] = 'halt_on_error=1'
    with tempfile.TemporaryDirectory(prefix='minyar-peer-grpc-') as directory:
        directory = Path(directory); binary = directory / 'probe'
        source = ROOT / 'tests/peer-grpc.min'
        if options.compat_red:
            source = directory / 'red.min'
            source.write_text('use "peergrpc" as grpc\nuse "errors" as errors\nlet server = grpc.create()\ngrpc.receive(server, readBytesFile(argument(0)))\nlet open = grpc.requests(server, 1000000)\nif grpc.openOk(open) { print("OPEN") } else { print("ERROR " + Text(errors.code(grpc.openError(open)))) }\nwriteBytesFile(argument(1), grpc.takeOutgoing(server, 1048576))\n')
        compiler = [str(ROOT / 'minyar')]
        if options.library: compiler += ['--library', str(options.library)]
        compiler += [str(source), '-o', str(binary)]
        subprocess.run(compiler, env=env, check=True, timeout=240)
        path = directory / 'input'; followup = directory / 'followup'
        def run(raw, mode='', trap=False, extra=''):
            path.write_bytes(raw)
            result = subprocess.run([str(binary), str(path), str(directory / 'output'), mode, str(extra)], env=env, capture_output=True, text=True, timeout=60)
            if trap: assert result.returncode != 0 and 'cannot read rejected gRPC open' in result.stderr, result
            else: assert result.returncode == 0 and result.stderr == '', (result.returncode, result.stdout, result.stderr)
            return result.stdout, (directory / 'output').read_bytes()
        peer = client(); peer.send_data(1, envelope(opened()))
        raw = peer.data_to_send(); output, encoded = run(raw)
        if options.compat_red:
            assert output == 'ERROR 10\n', output
            print('RED: committed private schema rejects normative PeerEdgeDial OpenExitStream request')
            return
        assert output == 'OPEN 1 exit-a conn-1 1010 fixture.jwt.signature\n', output
        peer.receive_data(encoded)
        for number, status in enumerate(('grant_invalid', 'exit_offline', 'policy_denied', 'concurrency_full'), 1):
            peer = client(); peer.send_data(1, envelope(opened()))
            output, encoded = run(peer.data_to_send(), 'reject', extra=status); events = peer.receive_data(encoded)
            response = messages(events)
            assert len(response) == 1 and response[0].WhichOneof('body') == 'status'
            assert response[0].status.code == number and response[0].status.detail == 'capacity reason'
            assert any(isinstance(e, h2.events.TrailersReceived) and ('grpc-status', '0') in e.headers for e in events)
        for mode in ('timeout', 'timeout-wall'):
            peer = client('500m'); peer.send_data(1, envelope(opened()))
            output, encoded = run(peer.data_to_send(), mode); assert output == 'TIMEOUT OK\n'
            assert any(isinstance(e, h2.events.TrailersReceived) and ('grpc-status', '4') in e.headers for e in peer.receive_data(encoded))
        # OPEN is fed before status, DATA separately after the fixture queues status OK.
        peer = client(); peer.send_data(1, envelope(opened())); initial = peer.data_to_send()
        data = bytes(range(256)) * 100; msg = envelope(Request(data=data))
        for at in range(0, len(msg), 8000): peer.send_data(1, msg[at:at+8000], end_stream=at + 8000 >= len(msg))
        followup.write_bytes(peer.data_to_send()); output, encoded = run(initial, 'echo', extra=followup)
        events = peer.receive_data(encoded); response = messages(events)
        assert response[0].WhichOneof('body') == 'status' and response[0].status.code == 0
        assert b''.join(m.data for m in response[1:]) == data
        assert any(isinstance(e, h2.events.TrailersReceived) and ('grpc-status', '0') in e.headers and ('grpc-message', 'done %25%0A') in e.headers for e in events)
        # Default timeout bounds establishment; it must not cut off established streams.
        peer = client(); peer.send_data(1, envelope(opened()))
        output, encoded = run(peer.data_to_send(), 'established'); assert output == 'ESTABLISHED OK\n'
        malformed = [b'\1\0\0\0\0', b'\0\0\1\0\5', envelope(Request(data=b'not-open')),
                     envelope(Request(status=Status(code=0))),
                     envelope(Request(open=Open(dial_grant=b'x', exit_id='exit-a'))),
                     envelope(Request(open=Open(dial_grant=b'x', exit_id='exit/a', conn_id='conn-1'))),
                     envelope(Request(open=Open(dial_grant=b'\xff', exit_id='exit-a', conn_id='conn-1'))),
                     envelope(opened()) + envelope(Request(data=b'early')),
                     envelope(opened()) + envelope(opened()), envelope(opened()) + envelope(Request(status=Status(code=0)))]
        for bad in malformed:
            peer = client(); peer.send_data(1, bad, end_stream=True)
            output, encoded = run(peer.data_to_send()); assert output == 'ERROR 10\n', (bad, output)
            assert any(isinstance(e, h2.events.TrailersReceived) and ('grpc-status', '13') in e.headers for e in peer.receive_data(encoded))
        # No silent alias of the old invented private route.
        peer = client(route='/hearth.peer.v1.PeerGateway/Dial'); peer.send_data(1, envelope(opened()))
        assert run(peer.data_to_send())[0] == 'ERROR 10\n'
        open_message = envelope(opened()); data_message = envelope(Request(data=bytes(range(256)))); prefix_count = 0
        # Even a single buffered byte of a later message arrived before admission.
        for cut in range(1, len(data_message) + 1):
            peer = client(); peer.send_data(1, open_message + data_message[:cut])
            assert run(peer.data_to_send())[0] == 'ERROR 10\n', cut
        for cut in range(len(open_message) + 1):
            peer = client(); peer.send_data(1, open_message[:cut], end_stream=True)
            output, encoded = run(peer.data_to_send())
            assert output.startswith('OPEN 1 ') if cut == len(open_message) else output == 'ERROR 10\n', (cut, output)
            prefix_count += 1
        for cut in range(len(data_message) + 1):
            peer = client(); peer.send_data(1, open_message); initial = peer.data_to_send()
            peer.send_data(1, data_message[:cut], end_stream=True); followup.write_bytes(peer.data_to_send())
            output, encoded = run(initial, 'echo', extra=followup)
            assert output.startswith('OPEN 1 ')
            assert ('READERROR 10\n' in output) == (cut not in (0, len(data_message))), (cut, output)
            prefix_count += 1
        rng = random.Random(0x47525043)
        for index in range(150):
            bad = bytearray(open_message)
            for _ in range(1 + index % 3):
                at = rng.randrange(len(bad)); bad[at] ^= 1 << rng.randrange(8)
            peer = client(); peer.send_data(1, bytes(bad), end_stream=True)
            output, encoded = run(peer.data_to_send())
            assert output.startswith('OPEN 1 ') or output == 'ERROR 10\n', (index, bad.hex(), output)
            if output.startswith('OPEN 1 '):
                assert bad[0] == 0 and int.from_bytes(bad[1:5], 'big') == len(bad) - 5
                assert Request.FromString(bytes(bad[5:])).WhichOneof('body') == 'open'
        run(b'', 'trap', trap=True)
        serving = directory / 'serve'
        subprocess.run([str(ROOT / 'minyar'), str(ROOT / 'tests/peer-grpc-serve.min'), '-o', str(serving)], env=env, check=True, timeout=240)
        process = subprocess.Popen([str(serving)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            port = int(process.stdout.readline().strip())
            with grpc.insecure_channel(f'127.0.0.1:{port}') as channel:
                rpc = channel.stream_stream(PATH, request_serializer=Request.SerializeToString, response_deserializer=Response.FromString)
                def transfer(index):
                    payload = bytes(range(256))[index:] * (200 + index * 5) + f'TAIL-{index}'.encode(); admitted = threading.Event()
                    def outgoing():
                        yield opened(f'conn-{index}')
                        assert admitted.wait(5), 'server never admitted stream'
                        yield Request(data=bytes(range(256)) * 256)
                        for at in range(0, len(payload), 8192): yield Request(data=payload[at:at+8192])
                    call = rpc(outgoing(), timeout=8)
                    first = next(call); assert first.WhichOneof('body') == 'status' and first.status.code == 0
                    admitted.set(); responses = list(call)
                    assert b''.join(message.data for message in responses) == bytes(range(256)) * 256 + payload
                    assert call.code() == grpc.StatusCode.OK
                with ThreadPoolExecutor(max_workers=3) as pool: list(pool.map(transfer, range(3)))
                stopped = threading.Event()
                def stalled():
                    yield opened('cancel-me'); stopped.wait(3)
                cancelled = rpc(stalled(), timeout=5); assert next(cancelled).status.code == 0
                assert cancelled.cancel(); stopped.set(); transfer(3)
            process.wait(timeout=15)
            assert process.returncode == 0 and process.stderr.read() == '', process.returncode
        finally:
            if process.poll() is None: process.kill(); process.wait()
            diagnostic = process.stderr.read()
            if process.returncode != 0 or diagnostic: print('Native gRPC fixture diagnostics:', process.returncode, diagnostic)
        print(f'gRPC: {prefix_count} prefixes + 150 mutations, normative PeerEdgeDial schema/all nested statuses/details, early coalesced DATA rejection, immutable 500ms/default deadlines and concurrent grpcio 64KiB binary streams passed')

if __name__ == '__main__': main()
