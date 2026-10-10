#!/usr/bin/env python3
"""Actual disposable Redis fencing, replacement, corruption and TTL checks."""
import json
import shutil
import socket
import subprocess
import time
import unittest
from regressions import CompilerTestCase, ROOT

class PeerLiveRedis(CompilerTestCase):
    compiler_arguments = ('--library', str(ROOT / 'library'))

    def test_actual_redis_fences_replaced_owners_and_preserves_exact_ttl(self):
        # This is an independent Redis server, using the exact commands emitted
        # by Minyar. No Python copy of the fencing script supplies the oracle.
        executable = shutil.which('redis-server')
        if not executable:
            self.fail('redis-server is required for the live-state gate')
        paths = [self.directory / f'{name}.resp' for name in ('bind-a', 'bind-b', 'refresh-a', 'refresh-b', 'drop-a', 'drop-b')]
        source = '''use "peerlive" as live
use "errors" as errors
let health = live.heartbeat(Bytes("{\\"in_flight\\":0,\\"max_concurrent\\":8,\\"paused\\":false,\\"policy_hash\\":\\"HASH\\",\\"public_ip\\":\\"203.0.113.2\\",\\"asn\\":64500,\\"country\\":\\"GB\\"}"))
let first = "FIRST"; let second = "SECOND"
let a = errors.bytesValue(live.payload(health,"exit-a","edge-a",first,1000,0,false,false,1.0))
let b = errors.bytesValue(live.payload(health,"exit-a","edge-b",second,1001,0,false,false,1.0))
writeBytesFile(argument(0),errors.bytesValue(live.bindCommand("exit-a",first,a)))
writeBytesFile(argument(1),errors.bytesValue(live.bindCommand("exit-a",second,b)))
writeBytesFile(argument(2),errors.bytesValue(live.refreshCommand("exit-a",first,a)))
writeBytesFile(argument(3),errors.bytesValue(live.refreshCommand("exit-a",second,b)))
writeBytesFile(argument(4),errors.bytesValue(live.dropCommand("exit-a",first)))
writeBytesFile(argument(5),errors.bytesValue(live.dropCommand("exit-a",second)))
print("ready")
'''.replace('HASH', 'a' * 64).replace('FIRST', 'b' * 64).replace('SECOND', 'c' * 64)
        self.executes(source, 'ready\n', arguments=tuple(map(str, paths)))
        commands = [path.read_bytes() for path in paths]
        with socket.socket() as reserved:
            reserved.bind(('127.0.0.1', 0)); port = reserved.getsockname()[1]
        server = subprocess.Popen([executable, '--bind', '127.0.0.1', '--port', str(port), '--save', '',
                                   '--appendonly', 'no', '--protected-mode', 'yes', '--dir', str(self.directory)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while True:
                try:
                    client = socket.create_connection(('127.0.0.1', port), timeout=1); break
                except OSError:
                    self.assertIsNone(server.poll(), 'Redis failed to start')
                    if time.monotonic() >= deadline:
                        self.fail('Redis startup timed out')
                    time.sleep(.01)
            with client, client.makefile('rb') as incoming:
                def read():
                    line = incoming.readline()
                    self.assertTrue(line.endswith(b'\r\n'), line)
                    if line[:1] == b':': return int(line[1:-2])
                    if line[:1] == b'+': return line[1:-2]
                    if line[:1] == b'$':
                        size = int(line[1:-2])
                        if size == -1: return None
                        data = incoming.read(size); self.assertEqual(incoming.read(2), b'\r\n'); return data
                    self.fail(f'unexpected Redis response {line!r}')

                def command(*parts):
                    encoded = [part if isinstance(part, bytes) else str(part).encode() for part in parts]
                    client.sendall(b'*' + str(len(encoded)).encode() + b'\r\n' + b''.join(
                        b'$' + str(len(part)).encode() + b'\r\n' + part + b'\r\n' for part in encoded))
                    return read()

                def emitted(index): client.sendall(commands[index]); return read()
                key = 'peer:live:{exit-a}'
                self.assertEqual(emitted(0), b'OK')
                self.assertTrue(44000 <= command('PTTL', key) <= 45000)
                self.assertEqual(emitted(1), b'OK')
                replacement = command('GET', key)
                self.assertEqual(json.loads(replacement)['_epoch'], 'c' * 64)
                self.assertEqual(emitted(2), 0)  # delayed old heartbeat
                self.assertEqual(emitted(4), 0)  # delayed old disconnect
                self.assertEqual(command('GET', key), replacement)
                self.assertEqual(emitted(3), 1)
                self.assertTrue(44000 <= command('PTTL', key) <= 45000)
                self.assertEqual(command('SET', key, b'{malformed'), b'OK')
                self.assertEqual(emitted(3), 0)
                self.assertEqual(emitted(5), 0)
                self.assertEqual(command('GET', key), b'{malformed')
                self.assertEqual(emitted(1), b'OK')
                self.assertEqual(emitted(5), 1)
                self.assertIsNone(command('GET', key))
                self.assertEqual(emitted(2), 0)  # absent key never resurrects old owner
                self.assertEqual(emitted(1), b'OK')
                self.assertEqual(command('PEXPIRE', key, 1), 1)
                time.sleep(.02)
                self.assertIsNone(command('GET', key))
                self.assertEqual(emitted(3), 0)
        finally:
            if server.poll() is None:
                server.terminate()
            _, error = server.communicate(timeout=5)
            self.assertEqual(server.returncode, 0, error)


if __name__ == '__main__':
    unittest.main()
