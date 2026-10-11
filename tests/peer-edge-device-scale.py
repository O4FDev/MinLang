#!/usr/bin/env python3
"""Remote peer-edge QUIC capacity fixture with independently observed live state.

The Rust client uses Quinn/rustls and a distinct URI certificate for every
device. A measured connection must be admitted into the real Redis live-state
plane and renew its fifteen-second heartbeat. Gateway socket counts cannot
satisfy this fixture. Run under the remote host resource supervisor.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import socket
import subprocess
import time

EPOCH = re.compile(r'[0-9a-f]{64}\Z')


def validate_states(records, count, edge, now, previous=None, minimum_timestamp=None):
    """Validate the complete independent Redis observation, without repairing it."""
    expected = {f'exit-{index:05d}' for index in range(count)}
    epochs = {}
    for key, state in records:
        if not isinstance(state, dict):
            raise ValueError('live state must be an object')
        exit_id = state.get('exit_id')
        if exit_id not in expected or exit_id in epochs or key != f'peer:live:{{{exit_id}}}':
            raise ValueError('duplicate, unexpected or incorrectly bound device state')
        epoch = state.get('_epoch')
        if not isinstance(epoch, str) or not EPOCH.fullmatch(epoch):
            raise ValueError('invalid live owner epoch')
        if previous is not None and previous.get(exit_id) != epoch:
            raise ValueError('live owner changed during the measured window')
        fixed = dict(edge_instance=edge, edge_region='eu-west', paused=False,
                     policy_hash='a' * 64, public_ip='203.0.113.2', asn=64500, country='GB')
        if any(type(state.get(name)) is not type(value) or state.get(name) != value
               for name, value in fixed.items()):
            raise ValueError('incorrect trusted live-state fields')
        for name, value in (('in_flight', 0), ('max_concurrent', 8)):
            if type(state.get(name)) is not int or state[name] != value:
                raise ValueError('incorrect reported capacity')
        weight = state.get('capacity_weight')
        if type(weight) not in (int, float) or weight != 1:
            raise ValueError('device is not available for routing')
        timestamp = state.get('ts')
        if type(timestamp) is not int or not 0 <= now - timestamp <= 30:
            raise ValueError('missing, future or stale heartbeat timestamp')
        if minimum_timestamp is not None and timestamp < minimum_timestamp:
            raise ValueError('heartbeat did not advance during the measured window')
        epochs[exit_id] = epoch
    if set(epochs) != expected:
        raise ValueError('not every requested device is admitted')
    return epochs


class Redis:
    """Small independent RESP reader, including SCAN/MGET arrays."""
    def __init__(self, port):
        self.socket = socket.create_connection(('127.0.0.1', port), timeout=5)
        self.input = self.socket.makefile('rb')

    def read(self, depth=0):
        if depth > 4:
            raise ValueError('RESP nesting')
        line = self.input.readline(65537)
        if not line.endswith(b'\r\n'):
            raise ValueError('truncated RESP line')
        kind, value = line[:1], line[1:-2]
        if kind == b'+':
            return value
        if kind == b'-':
            raise ValueError('Redis error: ' + value.decode(errors='replace'))
        length = int(value)
        if kind == b':':
            return length
        if kind == b'$':
            if length == -1:
                return None
            if not 0 <= length <= 16777216:
                raise ValueError('RESP bulk length')
            data = self.input.read(length)
            if len(data) != length or self.input.read(2) != b'\r\n':
                raise ValueError('truncated RESP bulk')
            return data
        if kind == b'*' and 0 <= length <= 32768:
            return [self.read(depth + 1) for _ in range(length)]
        raise ValueError('unsupported RESP value')

    def command(self, *parts):
        args = [x if isinstance(x, bytes) else str(x).encode() for x in parts]
        self.socket.sendall(b'*' + str(len(args)).encode() + b'\r\n' + b''.join(
            b'$' + str(len(x)).encode() + b'\r\n' + x + b'\r\n' for x in args))
        return self.read()

    def states(self):
        cursor, records = 0, {}
        while True:
            cursor_raw, keys = self.command('SCAN', cursor, 'MATCH', 'peer:live:*', 'COUNT', 1000)
            cursor = int(cursor_raw)
            if keys:
                for key, raw in zip(keys, self.command('MGET', *keys), strict=True):
                    if raw is None:
                        raise ValueError('live state disappeared during independent observation')
                    state = json.loads(raw)
                    name = key.decode()
                    if name in records and records[name] != state:
                        raise ValueError('live state changed during duplicate SCAN observation')
                    records[name] = state
            if cursor == 0:
                return list(records.items())

    def close(self):
        self.input.close()
        self.socket.close()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def process_sample(pid):
    fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    return dict(rss_kib=int(fields[21]) * os.sysconf('SC_PAGE_SIZE') / 1024,
                cpu_seconds=(int(fields[11]) + int(fields[12])) / os.sysconf('SC_CLK_TCK'))


def make_fixtures(directory, count):
    # Only disposable lab keys. Reusing a lab leaf key reduces setup cost;
    # every certificate still has a distinct signed URI and serial number.
    import datetime
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    directory.mkdir(parents=True, exist_ok=False)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    leaf_key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Minyar disposable scale root')])
    now = datetime.datetime.now(datetime.timezone.utc)
    ca = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
          .public_key(ca_key.public_key()).serial_number(1)
          .not_valid_before(now - datetime.timedelta(minutes=5))
          .not_valid_after(now + datetime.timedelta(days=2))
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
          .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
          .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
          .sign(ca_key, hashes.SHA256()))
    (directory / 'root.der').write_bytes(ca.public_bytes(serialization.Encoding.DER))
    (directory / 'leaf.pk8').write_bytes(leaf_key.private_bytes(
        serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    registry = []
    for index in range(-2, count):
        server = index == -2
        gateway = index == -1
        label = 'server' if server else 'gateway' if gateway else f'device-{index:05d}'
        san = x509.DNSName('localhost') if server else x509.UniformResourceIdentifier('hearth://device/' + label)
        cert = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, label)]))
                .issuer_name(name).public_key(leaf_key.public_key()).serial_number(index + 4)
                .not_valid_before(now - datetime.timedelta(minutes=5))
                .not_valid_after(now + datetime.timedelta(days=2))
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .add_extension(x509.SubjectKeyIdentifier.from_public_key(leaf_key.public_key()), critical=False)
                .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
                .add_extension(x509.SubjectAlternativeName([san]), critical=False)
                .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH if server else ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
                .add_extension(x509.KeyUsage(True, False, False, False, False, False, False, False, False), critical=True)
                .sign(ca_key, hashes.SHA256()))
        encoded = cert.public_bytes(serialization.Encoding.DER)
        (directory / (label + '.der')).write_bytes(encoded)
        if gateway:
            registry.append(dict(role='gateway', sha256=hashlib.sha256(encoded).hexdigest()))
        elif not server:
            registry.append(dict(role='device', device_id=label, exit_id=f'exit-{index:05d}',
                                 revoked=False, paused=False, quarantined=False, max_concurrent=8))
    (directory / 'registry.ndjson').write_text(''.join(json.dumps(x) + '\n' for x in registry))
    (directory / 'jwks.json').write_text('{"keys":[{"kty":"OKP","crv":"Ed25519","kid":"pop-1","alg":"EdDSA","use":"sig","x":"11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo"}]}\n')
    (directory / 'fixtures.json').write_text(json.dumps(dict(peers=count,
        certificates='unique signed device URI SAN and serial; shared disposable lab leaf key',
        sha256={p.name:digest(p) for p in sorted(directory.iterdir()) if p.is_file()}), indent=2) + '\n')


def wait_start(path, deadline):
    while not path.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError('measurement start was not supplied before setup deadline')
        time.sleep(.2)
    value = json.loads(path.read_text())
    start = value['utc_start']
    if type(start) is not int or not 0 <= start - time.time() <= 30:
        raise ValueError('measurement requires one fresh future UTC start within thirty seconds')
    while time.time() < start:
        time.sleep(min(.1, max(0, start - time.time())))
    return start


def serve(options):
    # No compiler invocation here. The caller supplies a separately qualified
    # binary, allowing one source/binary to serve both short and sustained runs.
    directory = options.output
    directory.mkdir(parents=True, exist_ok=False)
    with socket.socket() as reserved:
        reserved.bind(('127.0.0.1', 0))
        redis_port = reserved.getsockname()[1]
    config = dict(host=options.host, device_port=options.port, gateway_port=0,
        redis_host='127.0.0.1', redis_port=redis_port, edge_instance='localhost:0',
        edge_region='eu-west', max_connections=options.peers + 16,
        certificate=str(options.fixtures / 'server.der'), private_key=str(options.fixtures / 'leaf.pk8'),
        device_roots=str(options.fixtures / 'root.der'), gateway_roots=str(options.fixtures / 'root.der'),
        registry=str(options.fixtures / 'registry.ndjson'), jwks=str(options.fixtures / 'jwks.json'))
    (directory / 'edge.json').write_text(json.dumps(config))
    redis_process = edge = client = None
    samples = []
    result = dict(status='NONPASS', peers=options.peers, role='QUIC devices',
                  binary_sha256=digest(options.binary), fixtures_sha256=digest(options.fixtures / 'fixtures.json'))
    stdout = (directory / 'edge.stdout').open('w')
    stderr = (directory / 'edge.stderr').open('w')
    try:
        redis_process = subprocess.Popen(['redis-server', '--bind', '127.0.0.1', '--port', str(redis_port),
            '--save', '', '--appendonly', 'no', '--dir', str(directory)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + options.setup_seconds
        while client is None:
            try:
                client = Redis(redis_port)
            except OSError:
                if time.monotonic() > deadline:
                    raise TimeoutError('Redis setup')
                time.sleep(.05)
        duration_ms = (options.setup_seconds + options.seconds + 180) * 1000
        edge = subprocess.Popen([str(options.binary), str(directory / 'edge.json'), str(duration_ms)],
                                stdout=stdout, stderr=stderr)
        ready = None
        while time.monotonic() < deadline:
            lines = (directory / 'edge.stdout').read_text().splitlines()
            if lines:
                ready = lines[0]
                break
            if edge.poll() is not None:
                raise ValueError('edge failed before READY')
            time.sleep(.1)
        if not ready or not ready.startswith('READY '):
            raise TimeoutError('edge listener setup')
        udp, tcp, gateway = map(int, ready.split()[1:])
        if udp != tcp or udp <= 0 or gateway <= 0:
            raise ValueError('inconsistent peer listeners')
        ready_monotonic = time.monotonic()
        print('READY ' + json.dumps(dict(port=udp, gateway_port=gateway, pid=edge.pid)), flush=True)
        advertised = f'localhost:{gateway}'
        while time.monotonic() < deadline:
            if edge.poll() is not None:
                raise ValueError('edge exited before device admission')
            if client.command('DBSIZE') == options.peers:
                epochs = validate_states(client.states(), options.peers, advertised, int(time.time()))
                break
            time.sleep(.5)
        else:
            raise TimeoutError('not every device reached the Redis live-state plane')
        result['admitted'] = len(epochs)
        (directory / 'admitted.json').write_text(json.dumps(dict(epochs=epochs, edge=advertised), indent=2) + '\n')
        print('ADMITTED', len(epochs), flush=True)
        utc_start = wait_start(options.start_file, deadline)
        started = time.monotonic()
        last_state = started
        with (directory / 'samples.jsonl').open('w') as evidence:
            while time.monotonic() - started < options.seconds:
                if edge.poll() is not None:
                    raise ValueError('edge exited during device measurement')
                now = time.monotonic()
                row = dict(elapsed_seconds=now - started, target=process_sample(edge.pid),
                           controller=process_sample(os.getpid()), redis=process_sample(redis_process.pid))
                samples.append(row)
                evidence.write(json.dumps(row, sort_keys=True) + '\n')
                evidence.flush()
                if now - last_state >= 30:
                    validate_states(client.states(), options.peers, advertised, int(time.time()),
                                    previous=epochs, minimum_timestamp=int(utc_start) if now - started >= 45 else None)
                    last_state = now
                time.sleep(min(1, max(0, options.seconds - (time.monotonic() - started))))
        validate_states(client.states(), options.peers, advertised, int(time.time()),
                        previous=epochs, minimum_timestamp=int(utc_start))
        warm = [row for row in samples if row['elapsed_seconds'] >= (60 if options.seconds >= 7200 else 5)]
        if len(warm) < 2:
            raise ValueError('insufficient measured device samples')
        cpu = (warm[-1]['target']['cpu_seconds'] - warm[0]['target']['cpu_seconds']) / (warm[-1]['elapsed_seconds'] - warm[0]['elapsed_seconds'])
        rss = [x['target']['rss_kib'] for x in warm]
        xmean = sum(x['elapsed_seconds'] for x in warm) / len(warm)
        ymean = sum(rss) / len(rss)
        slope = sum((x['elapsed_seconds'] - xmean) * (x['target']['rss_kib'] - ymean) for x in warm) / sum((x['elapsed_seconds'] - xmean) ** 2 for x in warm)
        result.update(seconds_observed=time.monotonic() - started, mean_connected_cpu=cpu,
                      rss_min_kib=min(rss), rss_max_kib=max(rss), rss_slope_kib_per_second=slope)
        if cpu > .02:
            raise ValueError(f'connected device CPU exceeded unchanged 2% of one CPU: {cpu}')
        if options.seconds >= 7200 and (max(rss) - min(rss) > 16384 or slope > .2):
            raise ValueError('device RSS exceeded unchanged span or growth gate')
        # The peer fixture holds connections for ten seconds beyond measurement
        # and staggers teardown. Native shutdown must be normal, with no retained
        # device/relay state; forced cleanup never establishes a pass.
        while client.command('DBSIZE') != 0:
            if time.monotonic() - started > options.seconds + 140:
                raise TimeoutError('device live state did not retire after peer teardown')
            time.sleep(.2)
        native_deadline = ready_monotonic + duration_ms / 1000 + 10
        edge.wait(timeout=max(1, native_deadline - time.monotonic()))
        stdout.flush()
        stderr.flush()
        counts = next((line for line in (directory / 'edge.stdout').read_text().splitlines() if line.startswith('EDGE_COUNTS ')), None)
        if not counts or edge.returncode != 0 or (directory / 'edge.stderr').read_text():
            raise ValueError('edge did not exit normally with empty stderr and counts')
        fields = dict(part.split('=') for part in counts.split()[1:])
        if int(fields['active']) != 0 or int(fields['retained_relays']) != 0 or int(fields['calls_opened']) != int(fields['calls_released']):
            raise ValueError('edge retained peers or relay calls')
        result.update(status=0, counts=fields)
        print('GREEN ' + json.dumps(result), flush=True)
    except BaseException as error:
        result['failure'] = repr(error)
        raise
    finally:
        for process in (edge, redis_process):
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        if client:
            client.close()
        stdout.close()
        stderr.close()
        (directory / 'report.json').write_text(json.dumps(result, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--peers', type=int, default=32)
    parser.add_argument('--make-fixtures', action='store_true')
    parser.add_argument('--binary', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--start-file', type=Path)
    parser.add_argument('--seconds', type=int, default=7200)
    parser.add_argument('--setup-seconds', type=int, default=1200)
    parser.add_argument('--host', default='::')
    parser.add_argument('--port', type=int, default=24567)
    options = parser.parse_args()
    if platform.system() != 'Linux' or os.environ.get('MINYAR_REMOTE_LOAD') != '1':
        parser.error('remote Linux with MINYAR_REMOTE_LOAD=1 is required')
    if not 1 <= options.peers <= 20000 or not 30 <= options.seconds <= 82800 or not 30 <= options.setup_seconds <= 1800 or not 1 <= options.port <= 65535:
        parser.error('invalid bounded remote fixture configuration')
    if options.make_fixtures:
        make_fixtures(options.fixtures, options.peers)
    else:
        if not all((options.binary, options.output, options.start_file)):
            parser.error('server requires binary, output and start-file')
        serve(options)


if __name__ == '__main__':
    main()
