#!/usr/bin/env python3
"""Remote Linux QUIC/mTLS fault soak. Never starts load without remote opt-in.
The Minyar server, Quinn peers and loss proxy are measured separately. Raw
Linux process RSS/CPU samples are retained; this is not a throughput benchmark.
"""
import argparse
import hashlib
import heapq
import importlib.util
import json
import os
from pathlib import Path
import platform
import random
import selectors
import shutil
import socket
import subprocess
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tls_tests', ROOT / 'tests/tls-local.py')
fixtures = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixtures)


class FaultProxy:
    def __init__(self, server_port, loss, reorder, address='127.0.0.1'):
        self.front = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.back = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.front.bind((address, 0)); self.back.bind(('127.0.0.1', 0))
        self.server = ('127.0.0.1', server_port); self.client = None
        self.loss, self.reorder = loss, reorder
        self.stop = threading.Event(); self.blocked = threading.Event(); self.blocked_dropped = 0
        self.dropped = 0; self.delayed = 0; self.forwarded = 0
        self.thread = threading.Thread(target=self.drive, daemon=True); self.thread.start()

    def drive(self):
        rng = random.Random(9002); pending = []; serial = 0
        selector = selectors.DefaultSelector()
        selector.register(self.front, selectors.EVENT_READ); selector.register(self.back, selectors.EVENT_READ)
        try:
            while not self.stop.is_set():
                now = time.monotonic()
                while pending and pending[0][0] <= now:
                    _, _, sock, packet, address = heapq.heappop(pending)
                    if self.blocked.is_set(): self.dropped += 1; self.blocked_dropped += 1
                    else: sock.sendto(packet, address); self.forwarded += 1
                wait=max(0,min(1,pending[0][0]-now)) if pending else 1
                for key, _ in selector.select(wait):
                    data, source = key.fileobj.recvfrom(65535)
                    if key.fileobj is self.front:
                        self.client = source; target, address = self.back, self.server
                    else:
                        if self.client is None: continue
                        target, address = self.front, self.client
                    if self.blocked.is_set():
                        self.dropped += 1; self.blocked_dropped += 1; continue
                    if rng.random() < self.loss:
                        self.dropped += 1; continue
                    if rng.random() < self.reorder:
                        serial += 1; self.delayed += 1
                        heapq.heappush(pending, (now + 0.015, serial, target, data, address))
                    else:
                        target.sendto(data, address); self.forwarded += 1
        finally:
            selector.close()

    def close(self):
        self.stop.set(); self.thread.join(2); self.front.close(); self.back.close()


def process_sample(pid):
    # stat's parenthesized process name can contain spaces.
    fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    return {'state': fields[0], 'rss_bytes': int(fields[21]) * os.sysconf('SC_PAGE_SIZE'),
            'cpu_seconds': (int(fields[11]) + int(fields[12])) / os.sysconf('SC_CLK_TCK')}


def peer_observation(process):
    # A completed peer has no live RSS. Keep its last real sample and exit
    # status separately; a zombie is not a zero-memory observation.
    status = process.poll()
    if status is not None: return status, None
    try:
        sample = process_sample(process.pid)
    except FileNotFoundError:
        status = process.poll()
        if status is None: raise
        return status, None
    if sample['state'] in ('Z', 'X', 'x'): return process.poll(), None
    return None, sample


def ready_line(process, timeout=15):
    selector = selectors.DefaultSelector()
    try:
        selector.register(process.stdout, selectors.EVENT_READ)
        if not selector.select(timeout):
            raise TimeoutError('QUIC server did not become ready')
        return process.stdout.readline().strip()
    finally:
        selector.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, help='use a separately built matching native server')
    parser.add_argument('--peer-binary', type=Path, help='use the separately built pinned Quinn peer')
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--duration', type=int, default=7200)
    parser.add_argument('--peers', type=int, default=64)
    parser.add_argument('--interval-ms', type=int, default=15000)
    parser.add_argument('--loss', type=float, default=0.01)
    parser.add_argument('--reorder', type=float, default=0.01)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--server-only', action='store_true', help='independent peer runs on another remote host')
    parser.add_argument('--front-address', default='127.0.0.1')
    parser.add_argument('--fixtures', type=Path, help='retain disposable test certificates for the remote peer')
    parser.add_argument('--setup-grace-seconds', type=int, default=0, help='bounded staggered handshake setup allowance')
    parser.add_argument('--idle-seconds',type=int,default=0,help='separate connected-idle fixture, no peer keepalive')
    options = parser.parse_args()
    for binary in (options.binary, options.peer_binary):
        if binary is not None and not binary.is_file(): parser.error('prebuilt binaries must be files')
    if options.sanitize:
        for name in ('MINYAR_CLANG_FLAGS','MINYAR_NATIVE_FLAGS','MINYAR_RUNTIME_FLAGS'):
            os.environ[name]='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
        os.environ['ASAN_OPTIONS']='detect_leaks=1'
        os.environ['UBSAN_OPTIONS']='halt_on_error=1'
    if platform.system() != 'Linux' or os.environ.get('MINYAR_REMOTE_LOAD') != '1':
        parser.error('sustained load requires remote Linux execution with MINYAR_REMOTE_LOAD=1')
    if options.duration < 1 or not 1 <= options.peers <= 16384 or options.interval_ms < 1 or not 0 <= options.loss < 1 or not 0 <= options.reorder < 1 or not 0 <= options.setup_grace_seconds <= 1800 or not 0<=options.idle_seconds<=120:
        parser.error('invalid soak duration, peer count, heartbeat interval or fault rates')
    if options.server_only and options.fixtures is None:
        parser.error('--server-only requires --fixtures')
    peer_build_command = None
    if not options.server_only and options.peer_binary is None:
        peer_build_command = ['cargo','build','--locked','--manifest-path',str(ROOT/'tests/interop/quinn/Cargo.toml'),'--target-dir',str(ROOT/'build/interop-quinn'),'--bin','minyar-quinn-interop','-j1']
        subprocess.run(peer_build_command,check=True,timeout=300,env=dict(os.environ,CARGO_BUILD_JOBS='1'))
    peer_binary = options.peer_binary.resolve() if options.peer_binary else ROOT/'build/interop-quinn/debug/minyar-quinn-interop'
    with tempfile.TemporaryDirectory(prefix='minyar-quic-soak-') as directory:
        if options.fixtures:
            options.fixtures.mkdir(parents=True, exist_ok=True); directory = str(options.fixtures)
        ca = fixtures.Certificates(directory); ca.root('root'); ca.leaf('server', 'root'); ca.leaf('client', 'root', usage='clientAuth')
        binary = options.binary.resolve() if options.binary else Path(directory)/'soak-server'
        compile_command = None
        if options.binary is None:
            compile_command=[str(ROOT/'minyar'),'--library',str(ROOT/'library'),str(ROOT/'tests/quic-soak-server.min'),'-o',str(binary)]
            fixtures.compile_program(ROOT/'tests/quic-soak-server.min',binary)
        teardown_seconds=(options.peers*5+999)//1000 if options.idle_seconds else 0
        server_command=[str(binary), str(ca.path('server', 'der')), str(ca.path('server', 'pk8')), str(ca.path('root', 'der')), str((options.duration + options.setup_grace_seconds + options.idle_seconds + teardown_seconds + 15) * 1000), str(options.peers + 16)]
        if options.idle_seconds:server_command.append('idle')
        server = subprocess.Popen(server_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        proxy = None; client = None; peer_command = None
        try:
            ready = ready_line(server); assert ready.startswith('READY '), ready
            proxy = FaultProxy(int(ready.split()[1]), options.loss, options.reorder, options.front_address)
            if options.server_only:
                print('READY ' + json.dumps({'address': options.front_address, 'port': proxy.front.getsockname()[1], 'fixtures': directory, 'server_pid': server.pid}), flush=True)
            else:
                peer_command=[str(peer_binary),str(proxy.front.getsockname()[1]),str(ca.path('root','der')),str(ca.path('client','der')),str(ca.path('client','pk8')),str(options.duration),str(options.peers),str(options.interval_ms)]
                client = subprocess.Popen(peer_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,env=dict(os.environ,MINYAR_QUINN_IDLE_SECONDS=str(options.idle_seconds)))
            started = time.monotonic(); samples = []
            deadline = started + options.duration + options.setup_grace_seconds + options.idle_seconds + teardown_seconds + 60
            configuration={key:str(value) if isinstance(value,Path) else value for key,value in vars(options).items()}
            versions = {}
            for command in ('openssl', 'clang-23', 'rustc', 'cargo'):
                if shutil.which(command):
                    versions[command] = subprocess.run([command, 'version' if command == 'openssl' else '--version'], capture_output=True, text=True, check=True).stdout.splitlines()[0]
            source = hashlib.sha256()
            for path in sorted(list((ROOT / 'library').glob('quic*.min')) + [ROOT / 'library/tls.min', ROOT / 'library/tlsserver.min', ROOT / 'runtime/native/aes.c', ROOT / 'runtime/native/tlsverify.c']):
                source.update(str(path.relative_to(ROOT)).encode()); source.update(path.read_bytes())
            report = {'host': socket.gethostname(), 'platform': platform.platform(), 'configuration': configuration,
                      'versions': versions, 'source_sha256': source.hexdigest(), 'server_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                      'server_pid':server.pid,'controller_pid':os.getpid(),'peer_pid':client.pid if client else None,
                      'controller_role':'QUIC fault proxy and observer share this process','samples':samples,
                      'command':server_command,'peer_command':peer_command,'compile_command':compile_command,'peer_build_command':peer_build_command,
                      'peer_sha256':hashlib.sha256(peer_binary.read_bytes()).hexdigest() if not options.server_only else None}
            options.report.parent.mkdir(parents=True, exist_ok=True)
            # The server's bounded lifetime includes setup and teardown grace.
            # Keep observing it after a successful peer finishes.
            while server.poll() is None and (client is None or client.poll() in (None, 0)):
                if time.monotonic() > deadline:
                    raise TimeoutError('QUIC soak exceeded its independent wall-clock deadline')
                sample = process_sample(server.pid); sample['elapsed_seconds'] = time.monotonic() - started
                sample['controller'] = process_sample(os.getpid())
                sample['peer_status'], sample['peer'] = peer_observation(client) if client else (None, None)
                sample['host_load_average'] = list(os.getloadavg())
                sample['proxy_forwarded']=proxy.forwarded;sample['proxy_dropped']=proxy.dropped;sample['proxy_delayed']=proxy.delayed
                if samples:
                    sample['interval_cpu_percent'] = 100 * (sample['cpu_seconds'] - samples[-1]['cpu_seconds']) / (sample['elapsed_seconds'] - samples[-1]['elapsed_seconds'])
                samples.append(sample); options.report.write_text(json.dumps(report, indent=2) + '\n')
                print(json.dumps(sample), flush=True); time.sleep(min(10, options.duration))
            stdout, stderr = client.communicate(timeout=30) if client else ('', '')
            server_stdout, server_stderr = server.communicate(timeout=30)
            report.update({'client_status': client.returncode if client else None, 'server_status': server.returncode, 'client_stdout': stdout, 'client_stderr': stderr,
                           'server_stdout': server_stdout, 'server_stderr': server_stderr, 'faults': {'dropped': proxy.dropped, 'reordered': proxy.delayed, 'forwarded': proxy.forwarded}})
            options.report.write_text(json.dumps(report, indent=2) + '\n')
            assert server.returncode == 0 and not server_stderr and (client is None or (client.returncode == 0 and not stderr)), {key:report[key] for key in ('server_status','client_status','server_stdout','server_stderr','client_stdout','client_stderr')}
            print(stdout, end=''); print(server_stdout, end='')
        finally:
            if proxy: proxy.close()
            for process in (client, server):
                if process and process.poll() is None: process.kill(); process.communicate()


if __name__ == '__main__': main()
