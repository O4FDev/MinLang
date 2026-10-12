#!/usr/bin/env python3
"""Replay official JSON results through the controller without Docker or peers."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/quic-interop'
spec = importlib.util.spec_from_file_location('interop_results', ROOT / 'tests/quic-interop.py')
interop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(interop)


class OfficialResults(unittest.TestCase):
    def invoke(self, matrix, servers='minyar', clients='quinn',
               cases='handshake,transfer,retry', runner_status=0, must_include='minyar', expected_status=None):
        with tempfile.TemporaryDirectory(prefix='minyar-interop-results-') as temporary:
            work = Path(temporary)
            runner = work / 'runner'
            runner.mkdir()
            artifacts = work / 'artifacts'
            artifacts.mkdir()
            (runner / 'implementations_quic.json').write_text('{}')
            (runner / 'docker-compose.yml').write_text('services: {}\n')
            matrix_path = artifacts / 'matrix.json'
            raw = None
            if matrix is not None:
                raw = matrix if isinstance(matrix, bytes) else json.dumps(matrix).encode()
                matrix_path.write_bytes(raw)

            def path(value):
                if str(value) == '/home/minyar/lab/quic-runner-tmp':
                    return work / 'runner-tmp'
                return Path(value)

            process = mock.Mock(returncode=runner_status)
            process.poll.return_value = runner_status
            arguments = ['quic-interop.py', '--runner', str(runner), '--artifacts', str(artifacts),
                         '--servers', servers, '--clients', clients, '--tests', cases,
                         '--must-include', must_include]
            with mock.patch.object(sys, 'argv', arguments), \
                    mock.patch.object(interop, 'Path', side_effect=path), \
                    mock.patch.object(interop.platform, 'system', return_value='Linux'), \
                    mock.patch.object(interop.os, 'geteuid', return_value=0, create=True), \
                    mock.patch.dict(os.environ, {'MINYAR_REMOTE_LOAD': '1'}), \
                    mock.patch.object(interop.subprocess, 'Popen', return_value=process), \
                    mock.patch.object(interop.subprocess, 'run') as cleanup, \
                    mock.patch.object(interop.subprocess, 'check_output', side_effect=lambda args, **kw: 'TShark (Wireshark) 4.6.0\n' if args[0]=='tshark' else 'frozen-runner\n'), \
                    contextlib.redirect_stdout(io.StringIO()):
                status = interop.main()
            cleanup.assert_called_once()
            if expected_status is not None:
                self.assertEqual(status, expected_status)
            manifest = json.loads((artifacts / 'manifest.json').read_text())
            if raw is not None:
                self.assertEqual(matrix_path.read_bytes(), raw, 'controller rewrote official raw JSON')
                self.assertEqual(manifest['matrix_sha256'], hashlib.sha256(raw).hexdigest())
                self.assertEqual(manifest['matrix_bytes'], len(raw))
            self.assertEqual(manifest['runner_status'], runner_status)
            self.assertEqual(manifest['status'], status)
            return status, manifest

    def test_actual_status_zero_all_unsupported_is_failure(self):
        raw = (FIXTURES / 'unsupported-quinn.json').read_bytes()
        status, manifest = self.invoke(raw, expected_status=1)
        self.assertEqual(status, 1)
        self.assertEqual(manifest['result_validation']['status'], 'failed')
        self.assertIn('handshake', manifest['result_validation']['error'])

    def test_old_or_unidentified_tshark_is_rejected(self):
        for version in ('TShark (Wireshark) 4.2.2', 'unidentified tshark'):
            with self.subTest(version=version), mock.patch.object(interop.subprocess, 'check_output', return_value=version):
                with self.assertRaisesRegex(RuntimeError, '4.5.0 or newer'):
                    interop.require_tshark()

    def test_supported_tshark_is_accepted(self):
        for version in ('TShark (Wireshark) 4.5.0', 'TShark (Wireshark) 4.6.0'):
            with self.subTest(version=version), mock.patch.object(interop.subprocess, 'check_output', return_value=version):
                self.assertEqual(interop.require_tshark(), version)

    def test_actual_multipeer_and_ngtcp2_results_succeed(self):
        for filename, servers, clients, cases, count in (
                ('succeeded-multipeer.json', 'quiche,msquic', 'minyar', 'handshake,transfer', 4),
                ('succeeded-ngtcp2.json', 'minyar', 'ngtcp2', 'handshake,transfer,retry', 3)):
            with self.subTest(filename=filename):
                status, manifest = self.invoke((FIXTURES / filename).read_bytes(),
                                               servers, clients, cases)
                self.assertEqual(status, 0)
                self.assertEqual(manifest['result_validation']['status'], 'succeeded')
                self.assertEqual(manifest['result_validation']['succeeded_cases'], count)

    def valid(self):
        return json.loads((FIXTURES / 'succeeded-ngtcp2.json').read_text())

    def test_missing_and_malformed_json_are_failures(self):
        for matrix in (None, b'', b'{', b'[]', b'null', b'{}', b'{"servers":[],"servers":[]}'):
            with self.subTest(matrix=matrix):
                status, manifest = self.invoke(matrix, clients='ngtcp2')
                self.assertEqual(status, 1)
                self.assertEqual(manifest['result_validation']['status'], 'failed')

    def test_empty_missing_failed_and_ambiguous_cells_are_failures(self):
        mutations = [
            lambda data: data.update(results=[]),
            lambda data: data.update(results=[[]]),
            lambda data: data['results'][0].pop(),
            lambda data: data['results'][0][0].update(result=None),
            lambda data: data['results'][0][0].update(result='failed'),
            lambda data: data['results'][0][0].update(result='unsupported'),
            lambda data: data['results'][0][0].pop('result'),
            lambda data: data['results'][0][0].update(name='other'),
            lambda data: data['results'][0][0].update(abbr='other'),
            lambda data: data['results'][0].append(copy.deepcopy(data['results'][0][0])),
            lambda data: data['results'][0].append({'name': 'handshake', 'abbr': 'different',
                                                  'result': 'succeeded'}),
            lambda data: data.update(results={'0': data['results'][0]}),
            lambda data: data['results'].__setitem__(0, None),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                matrix = self.valid()
                mutate(matrix)
                self.assertEqual(self.invoke(matrix, clients='ngtcp2')[0], 1)

    def test_selected_axes_and_test_metadata_must_match(self):
        mutations = [
            lambda data: data.update(servers=['quiche']),
            lambda data: data.update(clients=['quinn']),
            lambda data: data.update(clients=[]),
            lambda data: data.update(servers=['minyar', 'minyar']),
            lambda data: data.update(tests={}),
            lambda data: data['tests']['H'].update(name='different'),
            lambda data: data['tests'].update(X={'name': 'handshake'}),
            lambda data: data['tests'].__setitem__('H', None),
            lambda data: data.update(results=data['results'] + [[]]),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                matrix = self.valid()
                mutate(matrix)
                self.assertEqual(self.invoke(matrix, clients='ngtcp2')[0], 1)

    def test_client_major_pair_selection_ignores_unrequested_pairs(self):
        matrix = self.valid()
        matrix['servers'] = ['minyar', 'quiche']
        matrix['clients'] = ['msquic', 'minyar']
        succeeded = matrix['results'][0]
        unsupported = [dict(row, result=None) for row in succeeded]
        matrix['results'] = [copy.deepcopy(succeeded), copy.deepcopy(unsupported),
                             copy.deepcopy(succeeded), copy.deepcopy(succeeded)]
        status, manifest = self.invoke(matrix, servers='quiche,minyar', clients='minyar,msquic')
        self.assertEqual(status, 0)
        self.assertEqual(manifest['result_validation']['succeeded_cases'], 9)
        self.assertEqual(manifest['result_validation']['pairs'],
                         [{'server': 'minyar', 'client': 'msquic'},
                          {'server': 'minyar', 'client': 'minyar'},
                          {'server': 'quiche', 'client': 'minyar'}])
        # This cell is mandatory under client-major export ordering.
        matrix['results'][3][0]['result'] = None
        self.assertEqual(self.invoke(matrix, servers='quiche,minyar', clients='minyar,msquic')[0], 1)

    def test_nonzero_runner_is_preserved_even_with_valid_results(self):
        status, manifest = self.invoke(self.valid(), clients='ngtcp2', runner_status=13)
        self.assertEqual(status, 13)
        self.assertEqual(manifest['result_validation']['status'], 'succeeded')
        status, manifest = self.invoke((FIXTURES / 'unsupported-quinn.json').read_bytes(),
                                       runner_status=23)
        self.assertEqual(status, 23)
        self.assertEqual(manifest['result_validation']['status'], 'failed')

    def test_empty_selection_and_no_minyar_pair_cannot_pass(self):
        for options in ({'cases': ''}, {'cases': 'handshake,handshake'},
                        {'servers': 'minyar,minyar'}, {'must_include': 'minyar,quiche'}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.invoke(self.valid(), clients='ngtcp2', **options)
        self.assertEqual(self.invoke(self.valid(), clients='ngtcp2', must_include='absent')[0], 1)


if __name__ == '__main__':
    unittest.main()
