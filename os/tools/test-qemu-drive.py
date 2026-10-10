#!/usr/bin/env python3
"""Protocol regressions for the QMP test driver (no VM required)."""
import importlib.util
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest

spec = importlib.util.spec_from_file_location('drive', Path(__file__).with_name('qemu-drive.py'))
drive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drive)


class QMPTests(unittest.TestCase):
    def exchange(self, response, check):
        with tempfile.TemporaryDirectory() as directory:
            path = directory + '/qmp'
            with socket.socket(socket.AF_UNIX) as listener:
                listener.bind(path)
                listener.listen()
                failures = []

                def serve():
                    try:
                        connection, _ = listener.accept()
                        with connection, connection.makefile('rb') as reader:
                            connection.sendall(b'{"QMP":{}}\r\n')
                            capability = json.loads(reader.readline())
                            connection.sendall((json.dumps({'id': capability['id'], 'return': {}}) + '\n').encode())
                            request = json.loads(reader.readline())
                            for piece in response(request['id']):
                                connection.sendall(piece)
                    except BaseException as error:
                        failures.append(error)

                thread = threading.Thread(target=serve)
                thread.start()
                client = drive.QMP(path)
                try:
                    check(client)
                finally:
                    client.close()
                    thread.join(timeout=5)
                self.assertFalse(thread.is_alive())
                self.assertEqual(failures, [])

    def test_fragmented_reply_and_event(self):
        def response(identifier):
            data = b'{"event":"RESET"}\n' + json.dumps({'id': identifier, 'return': {'status': 'running'}}).encode() + b'\n'
            return [bytes([byte]) for byte in data]

        self.exchange(response, lambda client: self.assertEqual(client.command('query-status')['return']['status'], 'running'))

    def test_command_error_is_not_success(self):
        def response(identifier):
            return [(json.dumps({'id': identifier, 'error': {'desc': 'invalid input'}}) + '\n').encode()]

        def check(client):
            with self.assertRaisesRegex(RuntimeError, 'invalid input'):
                client.command('input-send-event')

        self.exchange(response, check)

    def test_disconnect_is_not_an_infinite_wait(self):
        def check(client):
            with self.assertRaises(EOFError):
                client.command('query-status')

        self.exchange(lambda identifier: [], check)


if __name__ == '__main__':
    unittest.main()
