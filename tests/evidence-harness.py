#!/usr/bin/env python3
"""Exercise real subprocess evidence, timeout cleanup, and strict output checks."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from test_evidence import Evidence, replay
from regressions import CompilerTestCase
from peer_runner import PeerRunner


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.environment = patch.dict(os.environ, {'MINYAR_TEST_EVIDENCE': str(self.base)})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_file_outputs_require_fresh_exact_bytes_for_every_optimization(self):
        destination = self.base / 'result.bin'

        class FileProgram(CompilerTestCase):
            def runTest(self):
                self.executes('writeTextFile(argument(0), "fresh")\nprint("done")\n',
                              'done\n', arguments=[str(destination)],
                              file_outputs=((destination, b'fresh'),))

        successful = unittest.TextTestRunner(stream=io.StringIO()).run(FileProgram())
        self.assertTrue(successful.wasSuccessful())
        original_run = Evidence.run
        mutations = []

        def omit_second_write(evidence, command, **kwargs):
            if kwargs.get('phase') != 'link' or '-O2' not in command:
                return original_run(evidence, command, **kwargs)
            inputs = [Path(value) for value in command if str(value).endswith('.ll')]
            self.assertEqual(len(inputs), 1)
            llvm = inputs[0]
            before = llvm.read_bytes()
            lines = before.splitlines(keepends=True)
            removed = [line for line in lines if b'call void @minyar_write_text_file(' in line]
            self.assertEqual(len(removed), 1)
            mutations.append(removed[0])
            llvm.write_bytes(b''.join(line for line in lines if line not in removed))
            try:
                return original_run(evidence, command, **kwargs)
            finally:
                llvm.write_bytes(before)

        with patch.object(Evidence, 'run', omit_second_write):
            missing = unittest.TextTestRunner(stream=io.StringIO()).run(FileProgram())
        self.assertEqual(len(mutations), 1)
        self.assertFalse(missing.wasSuccessful())
        self.assertFalse(missing.errors)
        self.assertEqual(len(missing.failures), 1)
        self.assertIn('program did not create', missing.failures[0][1])

        class WrongBytes(CompilerTestCase):
            def runTest(self):
                self.executes('writeTextFile(argument(0), "wrong")\nprint("done")\n',
                              'done\n', arguments=[str(destination)],
                              optimizations=('-O2',), file_outputs=((destination, b'fresh'),))

        wrong = unittest.TextTestRunner(stream=io.StringIO()).run(WrongBytes())
        self.assertFalse(wrong.wasSuccessful())
        self.assertFalse(wrong.errors)
        self.assertEqual(len(wrong.failures), 1)
        self.assertIn("b'wrong' != b'fresh'", wrong.failures[0][1])


    def test_optimized_python_cannot_disable_runner_oracles(self):
        script = 'from test_evidence import Evidence; Evidence("optimized")'
        result = subprocess.run([sys.executable, '-O', '-c', script],
                                cwd=Path(__file__).resolve().parent, capture_output=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'requires Python assertions', result.stderr)

    def test_success_removes_workspace(self):
        with Evidence('success') as evidence:
            evidence.run([sys.executable, '-c', 'print(42)'], timeout=5)
            path = evidence.path
        self.assertFalse(path.exists())

    def test_default_stdin_is_eof_and_inheritance_requires_explicit_opt_in(self):
        # Different real parent pipes are the negative control: default input
        # must stay empty, while explicit inheritance must see each exact pipe.
        script = '''
import base64,json,sys
from test_evidence import Evidence
with Evidence("stdin-parent") as evidence:
    command = [sys.executable,"-c","import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"]
    default = evidence.run(command,timeout=5)
    inherited = evidence.run(command,timeout=5,stdin=None)
    print(json.dumps({"default":base64.b64encode(default.stdout).decode(),
                      "inherited":base64.b64encode(inherited.stdout).decode(),
                      "modes":[row["stdin"]["mode"] for row in evidence.commands]}))
'''
        for payload in (b'parent one\n', b'\x00\xffparent two'):
            with self.subTest(payload=payload):
                result = subprocess.run([sys.executable, '-c', script], input=payload,
                                        cwd=Path(__file__).resolve().parent,
                                        capture_output=True, timeout=10)
                self.assertEqual((result.returncode, result.stderr), (0, b''))
                observed = json.loads(result.stdout)
                self.assertEqual(base64.b64decode(observed['default']), b'')
                self.assertEqual(base64.b64decode(observed['inherited']), payload)
                self.assertEqual(observed['modes'], ['eof', 'inherited'])

    def test_explicit_binary_and_text_input_are_recorded_and_replayed(self):
        command = [sys.executable, '-c', 'import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())']
        for payload, text in ((b'\x00\xffbinary\n', False), ('é🙂\x00\n', True)):
            with self.subTest(text=text):
                expected = payload.encode('utf-8') if text else payload
                evidence = Evidence('stdin-payload')
                observed = evidence.run(command, input=payload, text=text, timeout=5)
                self.assertEqual(observed.stdout, payload)
                self.assertEqual(base64.b64decode(evidence.commands[0]['stdin']['base64']), expected)
                evidence.close(failed=True)
                replayed = subprocess.run([sys.executable, str(Path(__file__).with_name('test_evidence.py')),
                                           str(evidence.path / 'evidence.json')],
                                          input=b'wrong inherited input', capture_output=True, timeout=10)
                self.assertEqual((replayed.returncode, replayed.stdout, replayed.stderr), (0, expected, b''))

    def test_explicit_file_input_preserves_offset_and_rejects_changed_input(self):
        evidence = Evidence('stdin-file')
        path = self.base / 'input.bin'
        payload = b'ignored prefix\x00\xffkept tail\n'
        path.write_bytes(payload)
        offset = len(b'ignored prefix')
        with path.open('rb') as stream:
            stream.seek(offset)
            observed = evidence.run(
                [sys.executable, '-c', 'import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())'],
                stdin=stream, timeout=5)
        self.assertEqual(observed.stdout, payload[offset:])
        self.assertEqual(evidence.commands[0]['stdin'],
                         {'mode': 'file', 'path': str(path.resolve()), 'offset': offset,
                          'sha256': hashlib.sha256(payload).hexdigest()})
        evidence.close(failed=True)
        command = [sys.executable, str(Path(__file__).with_name('test_evidence.py')),
                   str(evidence.path / 'evidence.json')]
        replayed = subprocess.run(command, input=b'wrong parent input', capture_output=True, timeout=10)
        self.assertEqual((replayed.returncode, replayed.stdout, replayed.stderr), (0, payload[offset:], b''))
        path.write_bytes(b'changed file\n')
        with self.assertRaisesRegex(ValueError, 'Replay input changed'):
            replay(evidence.path / 'evidence.json', 0)

    def test_conflicting_input_is_rejected_and_explicit_empty_pipe_is_eof(self):
        with Evidence('stdin-conflict') as evidence:
            command = [sys.executable, '-c', 'import sys; print(len(sys.stdin.buffer.read()))']
            for stdin in (None, subprocess.DEVNULL, subprocess.PIPE):
                with self.subTest(stdin=stdin), self.assertRaisesRegex(ValueError, 'input cannot be combined'):
                    evidence.run(command, input=b'payload', stdin=stdin, timeout=5)
            with self.assertRaisesRegex(TypeError, 'input must be str'):
                evidence.run(command, input=b'payload', text=True, timeout=5)
            with self.assertRaisesRegex(TypeError, 'input must be bytes'):
                evidence.run(command, input='payload', timeout=5)
            self.assertEqual(evidence.commands, [])
            observed = evidence.run(command, stdin=subprocess.PIPE, timeout=5)
            self.assertEqual(observed.stdout, b'0\n')
            self.assertEqual(evidence.commands[0]['stdin'], {'mode': 'input', 'base64': ''})

    def test_replay_refuses_inherited_or_unrecorded_stdin(self):
        evidence = Evidence('stdin-unreplayable')
        evidence.run([sys.executable, '-c', 'pass'], stdin=None, timeout=5)
        evidence.close(failed=True)
        manifest = evidence.path / 'evidence.json'
        with self.assertRaisesRegex(ValueError, 'Replay stdin.*inherited'):
            replay(manifest, 0)
        report = json.loads(manifest.read_text())
        del report['commands'][0]['stdin']
        manifest.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'Replay stdin.*unrecorded'):
            replay(manifest, 0)

    def test_timeout_with_unconsumed_input_retains_bytes_and_closes_process(self):
        payload = b'x' * (512 * 1024)
        with self.assertRaises(subprocess.TimeoutExpired):
            with Evidence('stdin-timeout') as evidence:
                evidence.run([sys.executable, '-c',
                              'import time; print("ready",flush=True); time.sleep(30)'],
                             input=payload, timeout=.5)
        row = json.loads((evidence.path / 'evidence.json').read_text())['commands'][0]
        self.assertTrue(row['timed_out'])
        self.assertEqual(base64.b64decode(row['stdin']['base64']), payload)
        self.assertEqual(base64.b64decode(row['stdout_base64']), b'ready\n')

    def test_output_reference_priority_and_missing_oracle(self):
        with Evidence('reference-output') as evidence:
            default = evidence.path / 'case.stdout'
            variants = ['big-endian.small', 'small', 'big-endian', 'test-os', 'default']
            paths = [default if variant == 'default' else default.with_name(default.name + '.' + variant)
                     for variant in variants]
            for path, variant in zip(paths, variants):
                path.write_bytes(variant.encode())
            # A different OS or byte order must not steal the chosen oracle.
            default.with_name(default.name + '.other-os').write_bytes(b'wrong system')
            default.with_name(default.name + '.little-endian.small').write_bytes(b'wrong byte order')
            for path, variant in zip(paths, variants):
                self.assertEqual(evidence.reference_output(default, size='small', endian='big', system='test-os'), variant.encode())
                selected = evidence.controls['output_references'][-1]
                self.assertEqual(selected['variant'], variant)
                self.assertEqual(selected['selected'], str(path))
                self.assertEqual(selected['sha256'], evidence.inputs[str(path)])
                path.unlink()
            with self.assertRaises(FileNotFoundError):
                evidence.reference_output(default, size='small', endian='big', system='test-os')

    def test_peer_report_preserves_exclusions_and_skips_after_success(self):
        class Partial(unittest.TestCase):
            def runTest(self):
                with Evidence('partial', controls={'platform_exclusions': ['normalization-sensitive-name']}) as self.evidence:
                    self.evidence.run([sys.executable, '-c', 'print(42)'], timeout=5, phase='execute')

        @unittest.skip('requires a Linux character device')
        class Skipped(unittest.TestCase):
            def runTest(self):
                self.fail('a skipped body must not execute')

        class SubtestSkip(unittest.TestCase):
            def runTest(self):
                with self.subTest(capability='unavailable'):
                    self.skipTest('missing optional capability')

        class FixtureSkip(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                raise unittest.SkipTest('class capability unavailable')

            def runTest(self):
                self.fail('unavailable fixture executed')

        partial = Partial()
        with patch.dict(os.environ, {'MINYAR_PEER_RESULTS': str(self.base / 'results')}):
            result = PeerRunner(stream=io.StringIO()).run(unittest.TestSuite([partial, Skipped(), SubtestSkip(), FixtureSkip()]))
        self.assertTrue(result.wasSuccessful())
        report = json.loads(next((self.base / 'results').glob('*.json')).read_text())
        self.assertFalse(report['complete_selection'])
        self.assertEqual([row['outcome'] for row in report['selected']], ['partial', 'skipped', 'partial'])
        self.assertEqual(report['selected'][0]['exclusions'], ['normalization-sensitive-name'])
        self.assertEqual(report['selected'][1]['skips'][0]['reason'], 'requires a Linux character device')
        self.assertEqual(report['selected'][2]['skips'][0]['reason'], 'missing optional capability')
        self.assertEqual(report['fixture_skips'][0]['reason'], 'class capability unavailable')
        self.assertFalse(partial.evidence.path.exists())

    def test_peer_report_records_domain_omissions_without_claiming_full_pass(self):
        class DomainPartial(unittest.TestCase):
            def runTest(self):
                with Evidence('domain-partial', controls={
                    'domain_exclusions': [{'domain': 'overflow', 'count': 3, 'reason': 'normal-exit selection'}],
                    'domain_coverage': {'overflow_processes_executed': 0},
                }) as self.evidence:
                    pass
        with patch.dict(os.environ, {'MINYAR_PEER_RESULTS': str(self.base / 'results'),
                                     'MINYAR_PEER_GATE': 'check-peer-ownership'}):
            result = PeerRunner(stream=io.StringIO()).run(DomainPartial())
        report = json.loads(next((self.base / 'results').glob('*.json')).read_text())
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(report['gate'], 'check-peer-ownership')
        self.assertFalse(report['complete_selection'])
        self.assertEqual(report['selected'][0]['outcome'], 'partial')
        self.assertEqual(report['selected'][0]['domain_exclusions'][0]['count'], 3)
        self.assertEqual(report['selected'][0]['domain_coverage']['overflow_processes_executed'], 0)

    def test_peer_report_never_promotes_subtest_or_setup_failure_to_pass(self):
        class WrongResult(unittest.TestCase):
            def runTest(self):
                with self.subTest(variant='O2'):
                    self.assertEqual(1, 2)

        class SetupFailure(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                raise RuntimeError('required compiler unavailable')

            def runTest(self):
                pass

        with patch.dict(os.environ, {'MINYAR_PEER_RESULTS': str(self.base / 'results')}):
            result = PeerRunner(stream=io.StringIO()).run(unittest.TestSuite([WrongResult(), SetupFailure()]))
        report = json.loads(next((self.base / 'results').glob('*.json')).read_text())
        self.assertFalse(result.wasSuccessful())
        self.assertFalse(report['successful'])
        self.assertFalse(report['complete_selection'])
        self.assertEqual(report['selected'][0]['outcome'], 'failed')
        self.assertEqual(len(report['failures']), 1)
        self.assertIn('required compiler unavailable', report['errors'][0]['detail'])

    def test_failure_retains_raw_bytes_source_and_command(self):
        with self.assertRaises(subprocess.CalledProcessError):
            with Evidence('binary') as evidence:
                (evidence.path / 'case.min').write_text('print(42)\n')
                evidence.run([sys.executable, '-c',
                              "import os; os.write(2,b'\\xffbroken'); raise SystemExit(23)"],
                             timeout=5, check=True)
        report = json.loads((evidence.path / 'evidence.json').read_text())
        self.assertEqual(base64.b64decode(report['commands'][0]['stderr_base64']), b'\xffbroken')
        self.assertEqual(report['commands'][0]['returncode'], 23)
        self.assertIn('case.min', report['files'])
        self.assertFalse(report['commands'][0]['timed_out'])

    def test_replay_and_changed_input_rejection(self):
        evidence = Evidence('reproduction')
        source = evidence.path / 'program.py'
        source.write_text('raise SystemExit(23)\n')
        evidence.run([sys.executable, str(source)], timeout=5)
        evidence.close(failed=True)
        manifest = evidence.path / 'evidence.json'
        self.assertEqual(replay(manifest, -1), 23)
        source.write_text('raise SystemExit(0)\n')
        with self.assertRaisesRegex(ValueError, 'Replay artifact changed'):
            replay(manifest, -1)

    @unittest.skipIf(os.name == 'nt', 'POSIX process-group descendant check')
    def test_timeout_terminates_descendant_and_next_case_runs(self):
        heartbeat = self.base / 'heartbeat'
        child = "import pathlib,time; p=pathlib.Path(%r);\nwhile True: p.write_text(str(time.time())); time.sleep(.03)" % str(heartbeat)
        parent = ('import subprocess,sys,time; '
                  'subprocess.Popen([sys.executable,"-c",%r]); print("started",flush=True); time.sleep(30)' % child)
        with self.assertRaises(subprocess.TimeoutExpired):
            with Evidence('timeout') as evidence:
                evidence.run([sys.executable, '-c', parent], timeout=.5)
        self.assertTrue(heartbeat.exists())
        before = heartbeat.read_text()
        time.sleep(.15)
        self.assertEqual(heartbeat.read_text(), before)
        row = json.loads((evidence.path / 'evidence.json').read_text())['commands'][0]
        self.assertTrue(row['timed_out'])
        self.assertIn(b'started', base64.b64decode(row['stdout_base64']))
        with Evidence('following') as following:
            self.assertEqual(following.run([sys.executable, '-c', 'print(7)'], timeout=5).stdout, b'7\n')

    @unittest.skipIf(os.name == 'nt', 'POSIX executable fixture')
    def test_executable_resolution_uses_command_directory_and_path(self):
        work = self.base / 'command-directory'
        work.mkdir()
        probe = work / 'probe'
        probe.write_text('#!/bin/sh\nexit 23\n')
        probe.chmod(0o755)
        evidence = Evidence('relative-executable')
        for command in ('./probe', 'probe'):
            result = evidence.run([command], cwd=work, env={'PATH': '.'}, timeout=5)
            self.assertEqual(result.returncode, 23)
        evidence.close(failed=True)
        manifest = evidence.path / 'evidence.json'
        report = json.loads(manifest.read_text())
        self.assertIn(str(probe.resolve()), report['tools'])
        self.assertEqual(replay(manifest, 0), 23)
        self.assertEqual(replay(manifest, 1), 23)
        probe.write_text('#!/bin/sh\nexit 0\n')
        with self.assertRaisesRegex(ValueError, 'Replay input changed'):
            replay(manifest, 0)

    def test_empty_environment_is_not_recorded_as_inherited(self):
        with Evidence('empty-environment') as evidence:
            result = evidence.run([sys.executable, '-c', 'import os; print(os.environ.get("MINYAR_TEST_EVIDENCE", "absent"))'],
                                  env={}, timeout=5)
            self.assertEqual(result.stdout, b'absent\n')
            self.assertEqual(evidence.commands[0]['environment'], {})
            self.assertTrue(evidence.commands[0]['empty_environment'])

    @unittest.skipIf(os.name == 'nt', 'executable helper fixture uses a POSIX shebang')
    def test_replay_restores_explicit_path_locale_and_environment_removals(self):
        evidence = Evidence('environment-delta')
        helper = evidence.path / 'peer-helper'
        helper.write_text('#!' + sys.executable + '\nprint("helper found")\n')
        helper.chmod(0o755)
        script = ('import os,subprocess; '
                  'assert "PEER_REMOVED" not in os.environ; '
                  'assert os.environ["LC_ALL"] == "C"; '
                  'subprocess.run(["peer-helper"],check=True)')
        with patch.dict(os.environ, {'PEER_REMOVED': 'must not survive'}):
            environment = dict(os.environ, PATH=str(evidence.path), LC_ALL='C')
            del environment['PEER_REMOVED']
            result = evidence.run([sys.executable, '-c', script], env=environment, timeout=5)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'helper found\n', b''))
            evidence.close(failed=True)
            manifest = evidence.path / 'evidence.json'
            row = json.loads(manifest.read_text())['commands'][0]
            self.assertEqual(row['environment']['PATH'], str(evidence.path))
            self.assertIn('PEER_REMOVED', row['removed_environment'])
            self.assertEqual(replay(manifest, 0), 0)

    def test_correct_stdout_with_unexpected_stderr_is_rejected_and_retained(self):
        class StrayStderr(CompilerTestCase):
            def runTest(self):
                source = self.directory / 'case.ll'
                source.write_text('; harness fixture\n')
                compiled = subprocess.CompletedProcess([], 0, '', '')
                linked = subprocess.CompletedProcess([], 0, '', '')
                executed = subprocess.CompletedProcess([], 0, b'42\n', b'unexpected\n')
                with patch.object(self, 'compile', return_value=(compiled, source)), \
                     patch.object(self.evidence, 'run', side_effect=[linked, executed, linked, executed]):
                    self.executes('print(42)', '42\n')
        result = unittest.TextTestRunner(stream=io.StringIO()).run(StrayStderr())
        self.assertEqual(len(result.failures), 2)
        manifests = list(self.base.glob('regression-*/evidence.json'))
        self.assertEqual(len(manifests), 1)
        self.assertEqual(json.loads(manifests[0].read_text())['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
