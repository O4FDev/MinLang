#!/usr/bin/env python3
"""Independent TLS/yamux device, Redis and gateway exercise the edge binary."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import queue
import shutil
import socket
import subprocess
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tls_fixtures', ROOT / 'tests/tls-local.py')
fixtures = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixtures)

def lines(process):
    output = queue.Queue()
    def reader():
        for line in process.stdout:
            output.put(line.decode().strip())
        output.put(None)
    threading.Thread(target=reader, daemon=True).start()
    return output


class Redis:
    def __init__(self, port):
        self.socket = socket.create_connection(('127.0.0.1', port), timeout=2)
        self.input = self.socket.makefile('rb')

    def close(self):
        self.input.close(); self.socket.close()

    def command(self, *parts):
        args = [part if isinstance(part, bytes) else str(part).encode() for part in parts]
        self.socket.sendall(b'*' + str(len(args)).encode() + b'\r\n' + b''.join(
            b'$' + str(len(arg)).encode() + b'\r\n' + arg + b'\r\n' for arg in args))
        line = self.input.readline()
        assert line.endswith(b'\r\n'), line
        if line[:1] == b'+': return line[1:-2]
        if line[:1] == b':': return int(line[1:-2])
        if line[:1] == b'$':
            length = int(line[1:-2])
            if length == -1: return None
            data = self.input.read(length); assert self.input.read(2) == b'\r\n'; return data
        raise AssertionError(f'unexpected Redis response {line!r}')


def eventually(condition, timeout=5):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        result = condition()
        if result: return result
        time.sleep(.02)
    raise AssertionError('edge condition did not become true before deadline')


def integration(binary, directory):
    executable = shutil.which('redis-server'); assert executable, 'redis-server is required'
    go = shutil.which('go'); assert go, 'Go is required for the independent device'
    device_binary = directory / 'independent-device'
    built = subprocess.run([go, 'build', '-trimpath', '-o', str(device_binary), '.'],
                           cwd=ROOT / 'tests/interop/peeredge', capture_output=True, timeout=120)
    assert built.returncode == 0, built.stderr
    certificates = fixtures.Certificates(directory)
    certificates.root('ca')
    certificates.leaf('server', 'ca', ec=True)
    certificates.leaf('device', 'ca', san='URI:hearth://device/device-a', usage='clientAuth', ec=True)
    certificates.leaf('wrong-device', 'ca', san='URI:hearth://device/device-b', usage='clientAuth', ec=True)
    certificates.leaf('gateway', 'ca', usage='clientAuth', ec=True)
    import hashlib
    registry_path = directory / 'registry.ndjson'
    registry_path.write_text(json.dumps(dict(role='device', device_id='device-a', exit_id='exit-a',
                              revoked=False, paused=False, quarantined=False, max_concurrent=8)) + '\n' +
                             json.dumps(dict(role='gateway', sha256=hashlib.sha256(certificates.path('gateway', 'der').read_bytes()).hexdigest())) + '\n')
    key_path = directory / 'jwks.json'
    key_path.write_text('{"keys":[{"kty":"OKP","crv":"Ed25519","kid":"pop-1","alg":"EdDSA","use":"sig","x":"11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo"}]}')
    with socket.socket() as reserved:
        reserved.bind(('127.0.0.1', 0)); redis_port = reserved.getsockname()[1]
    redis_process = subprocess.Popen([executable, '--bind', '127.0.0.1', '--port', str(redis_port),
        '--save', '', '--appendonly', 'no', '--dir', str(directory)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    edge = None; devices = []; client = None
    try:
        def connect():
            try: return Redis(redis_port)
            except OSError: return None
        client = eventually(connect)
        config = dict(host='127.0.0.1', device_port=0, gateway_port=0, redis_host='127.0.0.1',
                      redis_port=redis_port, edge_instance='localhost:0', edge_region='eu-west', max_connections=128,
                      certificate=str(certificates.path('server', 'der')), private_key=str(certificates.path('server', 'pk8')),
                      device_roots=str(certificates.path('ca', 'der')), gateway_roots=str(certificates.path('ca', 'der')),
                      registry=str(registry_path), jwks=str(key_path))
        config_path = directory / 'edge.json'; config_path.write_text(json.dumps(config))
        edge = subprocess.Popen([str(binary), str(config_path), '10000'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        edge_lines = lines(edge); ready = edge_lines.get(timeout=10)
        assert ready and ready.startswith('READY '), ready
        udp_port, device_port, gateway_port = map(int, ready.split()[1:])
        assert udp_port == device_port and gateway_port > 0
        health = dict(in_flight=0, max_concurrent=99, paused=False, policy_hash='a'*64,
                      public_ip='203.0.113.2', asn=64500, country='GB')
        def device(certificate='device'):
            process = subprocess.Popen([str(device_binary), str(device_port), str(certificates.path('ca', 'pem')),
                str(certificates.path(certificate, 'pem')), str(certificates.path(certificate, 'key')),
                'device-a', 'exit-a', json.dumps(health)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            devices.append(process); output = lines(process)
            assert output.get(timeout=10) == 'READY'
            return process, output
        key = 'peer:live:{exit-a}'
        first, first_lines = device()
        state = json.loads(eventually(lambda: client.command('GET', key)))
        assert state['exit_id'] == 'exit-a' and state['edge_instance'] == f'localhost:{gateway_port}' and state['edge_region'] == 'eu-west', state
        assert state['capacity_weight'] == 1 and state['in_flight'] == 0 and state['max_concurrent'] == 8, state
        assert 43000 <= client.command('PTTL', key) <= 45000
        original_epoch = state['_epoch']
        health['paused'] = True
        first.stdin.write(json.dumps(health).encode() + b'\n'); first.stdin.flush()
        assert first_lines.get(timeout=5) == 'SENT'
        eventually(lambda: json.loads(client.command('GET', key))['capacity_weight'] == 0)
        # A real Redis outage must retire pending requests, avoid replay and
        # claim a fresh owner epoch after the transport reconnects.
        client.close(); client = None
        redis_process.terminate(); redis_process.communicate(timeout=5)
        redis_process = subprocess.Popen([executable, '--bind', '127.0.0.1', '--port', str(redis_port),
            '--save', '', '--appendonly', 'no', '--dir', str(directory)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        client = eventually(connect)
        reclaimed = json.loads(eventually(lambda: client.command('GET', key)))
        assert reclaimed['_epoch'] != original_epoch and reclaimed['capacity_weight'] == 0, reclaimed
        original_epoch = reclaimed['_epoch']
        health['paused'] = False
        second, second_lines = device()
        replacement = eventually(lambda: (value := client.command('GET', key)) and json.loads(value)['_epoch'] != original_epoch and json.loads(value))
        assert replacement['capacity_weight'] == 1
        # The old socket may still be unwinding. Its delayed disconnect cannot
        # delete a replacement owner's live state.
        first.stdin.write(b'close\n'); first.stdin.flush(); first.communicate(timeout=5)
        time.sleep(.1)
        assert json.loads(client.command('GET', key))['_epoch'] == replacement['_epoch']
        second.stdin.write(b'halfclose\n'); second.stdin.flush()
        assert second_lines.get(timeout=5) == 'HALFCLOSED'
        eventually(lambda: client.command('GET', key) is None)
        wrong, _ = device('wrong-device')
        time.sleep(.2)
        assert client.command('GET', key) is None, 'different URI SAN impersonated a registered device'
        assert edge.poll() is None, 'invalid device killed the edge process'
        edge.wait(timeout=12)
        assert edge.returncode == 0, edge.stderr.read()
        print('Peer edge: actual TLS/yamux mTLS admission, fragmented control, heartbeats, fencing, half-close and identity rejection passed')
    finally:
        for process in devices:
            if process.poll() is None: process.terminate()
            _, error = process.communicate(timeout=5)
        if edge is not None:
            if edge.poll() is None: edge.terminate()
            _, error = edge.communicate(timeout=5)
            assert b'ERROR: AddressSanitizer' not in error and b'runtime error:' not in error, error
        if client is not None: client.close()
        if redis_process.poll() is None: redis_process.terminate()
        redis_process.communicate(timeout=5)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--sanitize', action='store_true'); options = parser.parse_args()
    if options.sanitize:
        for name in ('MINYAR_CLANG_FLAGS', 'MINYAR_NATIVE_FLAGS', 'MINYAR_RUNTIME_FLAGS'):
            os.environ[name] = '-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
        os.environ['ASAN_OPTIONS'] = 'detect_leaks=1'
        os.environ['UBSAN_OPTIONS'] = 'halt_on_error=1'
    with tempfile.TemporaryDirectory(prefix='minyar-peer-edge-') as temporary:
        directory = Path(temporary); binary = directory / 'peer-edge'
        fixtures.compile_program(ROOT / 'examples/peer-edge.min', binary)
        # The configuration parser must return an ordinary failure before any
        # socket or Redis operation, including malformed/truncated input.
        for data in (b'{}', b'{"host":', b'\xff', b'[]'):
            path = directory / 'invalid.json'; path.write_bytes(data)
            result = subprocess.run([str(binary), str(path), '1000'], capture_output=True, timeout=5)
            assert result.returncode == 2 and b'invalid edge configuration' in result.stdout, result
        print('Peer edge: malformed startup configuration returns a normal failure')
        integration(binary, directory)


if __name__ == '__main__':
    main()
