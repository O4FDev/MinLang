#!/usr/bin/env python3
"""Python-only TEST signing fail-closed contracts; no native tool execution."""
import hashlib
import importlib.util
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('release', ROOT / 'scripts/release.py')
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)
SPEC = importlib.util.spec_from_file_location('release_pipeline', ROOT / 'tests/release-pipeline.py')
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)


class TestSigning(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app = self.root / 'input.app'
        (self.app / 'Contents/MacOS').mkdir(parents=True)
        (self.app / 'Contents/MacOS/main').write_bytes(bytes.fromhex('cffaedfe') + b'unsigned fixture')
        (self.app / 'Contents/Resources').mkdir()
        (self.app / 'Contents/Resources/text').write_bytes(b'unsigned resource')
        self.exe = self.root / 'input.exe'
        self.exe.write_bytes(b'MZunsigned fixture')
        self.cert = self.root / 'TEST-certificate.der'
        self.cert.write_bytes(b'contract certificate')
        self.thumb = hashlib.sha1(self.cert.read_bytes()).hexdigest().upper()
        self.keychain = self.root / 'TEST.keychain-db'
        self.keychain.write_bytes(b'fixture')
        self.calls = []
        self.subject = 'CN=Minyar TEST ONLY ' + 'a' * 32

    def tearDown(self):
        self.temp.cleanup()

    def tool(self, args, **kwargs):
        self.calls.append(args)
        stdout = ''
        if args[:2] == ['openssl', 'x509'] and '-subject' in args:
            stdout = 'subject=' + self.subject + '\nissuer=' + self.subject + '\n'
        elif args[:2] == ['openssl', 'x509'] and '-ext' in args:
            stdout = 'X509v3 Extended Key Usage:\n    Code Signing\n'
        return subprocess.CompletedProcess(args, 0, stdout, '')

    def sign(self, native, output, run=None):
        if native == 'macos':
            release.test_macos(self.app, output, self.cert, self.thumb, self.keychain, run=run or self.tool)
        else:
            release.test_windows(self.exe, output, self.cert, self.thumb, 'signtool.exe', run=run or self.tool)

    def test_non_test_or_existing_outputs_are_refused_before_tools(self):
        for native, suffix in [('macos', '.app'), ('windows', '.exe')]:
            for name in ['release' + suffix, 'test-fixture' + suffix, 'TEST-fixture.wrong']:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    self.sign(native, self.root / name)
            existing = self.root / ('TEST-existing' + suffix)
            if native == 'macos':
                existing.mkdir()
                (existing / 'previous').write_bytes(b'previous')
            else:
                existing.write_bytes(b'previous')
            with self.assertRaises(FileExistsError):
                self.sign(native, existing)
            self.assertEqual(self.calls, [])

    def test_certificate_identity_pin_and_code_signing_usage_are_mandatory(self):
        out = self.root / 'TEST-output.exe'
        with self.assertRaisesRegex(ValueError, 'thumbprint mismatch'):
            release.test_windows(self.exe, out, self.cert, 'B' * 40, 'signtool.exe', run=self.tool)
        self.assertEqual(self.calls, [])
        for subject in ['CN=Developer ID Application: Owner', 'CN=Minyar TEST ONLY',
                        'CN=Minyar TEST ONLY ' + 'a' * 32 + ',O=Unexpected']:
            self.subject = subject
            with self.subTest(subject=subject), self.assertRaisesRegex(ValueError, 'randomized'):
                self.sign('windows', out)
        self.subject = 'CN=Minyar TEST ONLY ' + 'a' * 32
        def issuer(args, **kwargs):
            result = self.tool(args, **kwargs)
            if '-issuer' in args:
                result.stdout = 'subject=' + self.subject + '\nissuer=CN=production CA\n'
            return result
        with self.assertRaises(ValueError):
            self.sign('windows', out, issuer)
        for usage in ['', 'X509v3 Extended Key Usage:\n    TLS Web Server Authentication\n',
                      'X509v3 Extended Key Usage:\n    Code Signing, TLS Web Server Authentication\n']:
            def invalid(args, **kwargs):
                result = self.tool(args, **kwargs)
                if '-ext' in args:
                    result.stdout = usage
                return result
            with self.subTest(usage=usage), self.assertRaisesRegex(ValueError, 'Code Signing'):
                self.sign('windows', out, invalid)
        self.assertFalse(out.exists())
        self.assertFalse(any(c[1:2] == ['sign'] for c in self.calls))

    def test_explicit_test_macos_and_windows_never_invoke_production_services(self):
        mac = self.root / 'TEST-signed.app'
        self.sign('macos', mac)
        signs = [c for c in self.calls if c[:2] == ['codesign', '--force']]
        self.assertEqual(len(signs), 2)
        for command in signs:
            self.assertIn('--timestamp=none', command)
            self.assertIn('--keychain', command)
            self.assertIn(self.thumb, command)
            self.assertNotIn('--deep', command)
        verify = [c for c in self.calls if c[:2] == ['codesign', '--verify']][0]
        self.assertEqual(verify[verify.index('-R') + 1], 'certificate leaf = H"' + self.thumb + '"')
        self.assertFalse(any(c[0] in ('xcrun', 'spctl', 'hdiutil') for c in self.calls))
        self.assertEqual((mac / 'Contents/Resources/text').read_bytes(), b'unsigned resource')
        self.calls.clear()
        win = self.root / 'TEST-signed.exe'
        self.sign('windows', win)
        sign = [c for c in self.calls if c[:2] == ['signtool.exe', 'sign']][0]
        verify = [c for c in self.calls if c[:2] == ['signtool.exe', 'verify']][0]
        self.assertEqual(sign[2:-1], ['/fd', 'SHA256', '/sha1', self.thumb, '/s', 'My'])
        self.assertEqual(verify[2:-1], ['/pa', '/all'])
        self.assertTrue(any(c[0] == 'powershell.exe' for c in self.calls))
        self.assertEqual(self.exe.read_bytes(), b'MZunsigned fixture')

    def test_every_tool_failure_and_warning_leaves_no_test_publication_or_stage(self):
        for native, suffix in [('macos', '.app'), ('windows', '.exe')]:
            baseline = self.root / ('TEST-baseline-' + native + suffix)
            self.calls.clear()
            self.sign(native, baseline)
            count = len(self.calls)
            for phase in range(count):
                for code in (1, 2):
                    calls = []
                    output = self.root / ('TEST-failure-' + native + suffix)
                    def fail(args, **kwargs):
                        calls.append(args)
                        if len(calls) - 1 == phase:
                            return subprocess.CompletedProcess(args, code, 'failed phase', '')
                        return self.tool(args, **kwargs)
                    with self.subTest(native=native, phase=phase, code=code), self.assertRaises(subprocess.CalledProcessError):
                        self.sign(native, output, fail)
                    self.assertFalse(output.exists())
                    self.assertEqual(list(self.root.glob('.minyar-test-sign-*')), [])
            self.assertEqual(self.exe.read_bytes(), b'MZunsigned fixture')
            self.assertEqual((self.app / 'Contents/MacOS/main').read_bytes(), bytes.fromhex('cffaedfe') + b'unsigned fixture')

    def test_late_output_collision_preserves_other_owners_generation(self):
        for native, suffix in [('macos', '.app'), ('windows', '.exe')]:
            output = self.root / ('TEST-race-' + native + suffix)
            def collide(args, **kwargs):
                if (native == 'macos' and args[:2] == ['codesign', '--verify']) or (native == 'windows' and args[0] == 'powershell.exe'):
                    if native == 'macos':
                        output.mkdir()
                        (output / 'previous').write_bytes(b'prior generation')
                    else:
                        output.write_bytes(b'prior generation')
                return self.tool(args, **kwargs)
            with self.assertRaises(FileExistsError):
                self.sign(native, output, collide)
            self.assertEqual((output / 'previous' if native == 'macos' else output).read_bytes(), b'prior generation')
            self.assertEqual(list(self.root.glob('.minyar-test-sign-*')), [])

    def test_native_modes_refuse_wrong_host_before_any_tool_or_output(self):
        for native in ('macos', 'windows'):
            with patch.object(sys, 'argv', ['pipeline', '--native', native, '--output', str(self.root / 'TEST-output'),
                                            '--openssl', 'openssl', '--cc', 'clang']), \
                 patch.object(pipeline.sys, 'platform', 'linux'), patch.object(pipeline.os, 'name', 'posix'), \
                 patch.object(pipeline, 'run') as tool:
                with self.assertRaises(SystemExit) as result:
                    pipeline.main()
                self.assertEqual(result.exception.code, 1)
                tool.assert_not_called()
        self.assertFalse((self.root / 'TEST-output').exists())

    def test_macos_default_and_incomplete_ci_refuse_before_any_tool_or_output(self):
        configurations = [({}, []), ({}, ['--ephemeral-macos-ci']),
            ({'GITHUB_ACTIONS': 'true', 'RUNNER_OS': 'macOS',
              'RUNNER_ENVIRONMENT': 'self-hosted', 'RUNNER_TEMP': str(self.root)}, ['--ephemeral-macos-ci']),
            ({'GITHUB_ACTIONS': 'false', 'RUNNER_OS': 'macOS',
              'RUNNER_ENVIRONMENT': 'github-hosted', 'RUNNER_TEMP': str(self.root)}, ['--ephemeral-macos-ci'])]
        for environment, flags in configurations:
            with self.subTest(environment=environment), patch.dict(os.environ, environment, clear=True), \
                 patch.object(sys, 'argv', ['pipeline', '--native', 'macos', '--output', str(self.root / 'TEST-output'),
                     '--openssl', 'openssl', '--cc', 'clang', *flags]), \
                 patch.object(pipeline.sys, 'platform', 'darwin'), patch.object(pipeline, 'run') as tool, \
                 patch.object(Path, 'mkdir') as mkdir, patch.object(pipeline.tempfile, 'TemporaryDirectory') as stage:
                with self.assertRaises(SystemExit) as result:
                    pipeline.main()
                self.assertEqual(result.exception.code, 1)
                tool.assert_not_called()
                mkdir.assert_not_called()
                stage.assert_not_called()
        self.assertFalse((self.root / 'TEST-output').exists())

    def test_direct_macos_credential_context_is_guarded_before_tools(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(pipeline, 'run') as tool:
            with self.assertRaisesRegex(ValueError, 'ephemeral'):
                with pipeline.macos_credentials(self.root, 'openssl', {}):
                    self.fail('owner Mac credential setup was allowed')
            tool.assert_not_called()

    def test_pipeline_api_default_refuses_before_fixture_tools_or_certdirs(self):
        args = SimpleNamespace(native='macos', output=self.root / 'TEST-output', signtool=None,
            macos_certificate=None, macos_thumbprint=None, macos_keychain=None,
            owned_boat_windows=False, ephemeral_macos_ci=False, cc='clang')
        with patch.dict(os.environ, {}, clear=True), patch.object(pipeline.sys, 'platform', 'darwin'), \
             patch.object(pipeline, 'native_fixture') as fixture, patch.object(pipeline, 'run') as tool, \
             patch.object(Path, 'mkdir') as mkdir:
            with self.assertRaisesRegex(ValueError, 'defaults to refusal'):
                pipeline.pipeline(args, self.root, self.root / 'TEST-output', {})
            fixture.assert_not_called()
            tool.assert_not_called()
            mkdir.assert_not_called()

    def test_windows_requires_owned_boat_context_before_any_tool_or_directory(self):
        for flags in ([], ['--owned-boat-windows']):
            with patch.dict(os.environ, {}, clear=True), \
                 patch.object(sys, 'argv', ['pipeline', '--native', 'windows', '--output', str(self.root / 'TEST-output'),
                     '--openssl', 'openssl', '--cc', 'clang', '--signtool', 'signtool', *flags]), \
                 patch.object(pipeline.sys, 'platform', 'win32'), patch.object(pipeline.os, 'name', 'nt'), \
                 patch.object(pipeline, 'run') as tool, patch.object(Path, 'mkdir') as mkdir:
                with self.assertRaises(SystemExit) as result:
                    pipeline.main()
                self.assertEqual(result.exception.code, 1)
                tool.assert_not_called()
                mkdir.assert_not_called()

    def test_provisioned_macos_identity_never_creates_or_cleans_os_credentials(self):
        report = {}
        with patch.object(pipeline, 'run') as tool:
            with pipeline.provisioned_macos_credentials(self.cert, self.thumb, self.keychain, report) as identity:
                self.assertEqual(identity['signer'], self.thumb)
                self.assertEqual(identity['certificate'], self.cert.resolve())
            tool.assert_not_called()
        self.assertIn('operator-owned', report['macosCredentialCleanup'])

    def test_ci_guard_requires_work_under_runner_temp(self):
        environment = {'GITHUB_ACTIONS': 'true', 'RUNNER_OS': 'macOS',
                       'RUNNER_ENVIRONMENT': 'github-hosted', 'RUNNER_TEMP': str(self.root)}
        with patch.dict(os.environ, environment, clear=True), patch.object(pipeline.sys, 'platform', 'darwin'):
            pipeline.require_ephemeral_macos_ci(self.root / 'credentials', explicit=True)
            with self.assertRaises(ValueError):
                pipeline.require_ephemeral_macos_ci(self.root.parent / 'outside', explicit=True)
            with self.assertRaises(ValueError):
                pipeline.require_ephemeral_macos_ci(self.root / 'credentials', explicit=False)

    def test_mac_ci_cleanup_attempts_all_steps_and_refuses_failures_or_drift(self):
        environment = {'GITHUB_ACTIONS': 'true', 'RUNNER_OS': 'macOS',
                       'RUNNER_ENVIRONMENT': 'github-hosted', 'RUNNER_TEMP': str(self.root)}
        for failure in ('trust removal', 'keychain deletion', 'search list drift', 'trust drift', 'partial setup'):
            with self.subTest(failure=failure):
                credentials = self.root / failure.replace(' ', '-')
                credentials.mkdir()
                report, calls = {}, []
                closing = False
                def fake(args, **kwargs):
                    nonlocal closing
                    args = [str(value) for value in args]
                    calls.append(args)
                    if args[:2] == ['openssl', 'req']:
                        Path(args[args.index('-out') + 1]).write_bytes(b'TEST cert')
                    if args[:2] == ['openssl', 'x509']:
                        Path(args[args.index('-out') + 1]).write_bytes(b'TEST DER')
                    if args[:2] == ['security', 'create-keychain']:
                        Path(args[-1]).touch()
                    if args[:4] == ['sudo', '-n', 'security', 'add-trusted-cert'] and failure == 'partial setup':
                        raise subprocess.CalledProcessError(1, args)
                    if args[:4] == ['sudo', '-n', 'security', 'remove-trusted-cert']:
                        closing = True
                        if failure == 'trust removal':
                            raise subprocess.CalledProcessError(1, args)
                    if args[:2] == ['security', 'delete-keychain']:
                        if failure == 'keychain deletion':
                            raise subprocess.CalledProcessError(1, args)
                        Path(args[-1]).unlink()
                    stdout = b''
                    if args[:2] == ['security', 'list-keychains']:
                        stdout = b'drift' if closing and failure == 'search list drift' else b'login'
                    if args[:2] == ['security', 'dump-trust-settings'] and closing and failure == 'trust drift':
                        stdout = b'drift'
                    return subprocess.CompletedProcess(args, 0, stdout, b'')
                with patch.dict(os.environ, environment, clear=True), patch.object(pipeline.sys, 'platform', 'darwin'), \
                     patch.object(pipeline, 'run', side_effect=fake):
                    with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                        with pipeline.macos_credentials(credentials, 'openssl', report, ephemeral_ci=True):
                            pass
                self.assertTrue(any(c[:2] == ['security', 'delete-keychain'] for c in calls))
                self.assertTrue(any(c[:2] == ['security', 'dump-trust-settings'] for c in calls[-3:]))
                self.assertEqual(report['macosCredentialCleanup']['status'], 'verified' if failure == 'partial setup' else 'FAILED')

    def test_independent_decoder_refuses_escape_duplicates_and_truncation(self):
        import struct
        def encoded(names):
            entry = b'main'
            data = b'MINYAR-BUNDLE-1\n' + struct.pack('>I', len(entry)) + entry + struct.pack('>I', len(names))
            for name in names:
                value = name.encode('ascii')
                data += struct.pack('>BBIQ', ord('F'), 1, len(value), 1) + value + b'x'
            return data
        for index, data in enumerate([encoded(['../main']), encoded(['main', 'MAIN']), encoded(['main'])[:-1], encoded(['main']) + b'tail']):
            with self.subTest(index=index), self.assertRaises(ValueError):
                pipeline.decode(data, self.root / ('decoded-' + str(index)))

    def test_windows_partial_creation_still_cleans_exact_recorded_ownership(self):
        credentials = self.root / 'credentials'
        credentials.mkdir()
        report = {}
        calls = []
        def fail_create(script, environment):
            calls.append(script)
            if script == pipeline.WINDOWS_CREATE:
                Path(environment['MINYAR_TEST_STATE']).write_text(json.dumps({'certificates': []}))
                raise subprocess.CalledProcessError(1, 'powershell')
        with patch.object(pipeline, 'ps', side_effect=fail_create), patch.object(pipeline, 'require_owned_boat_windows'):
            with self.assertRaises(subprocess.CalledProcessError):
                with pipeline.windows_credentials(credentials, report):
                    self.fail('failed credential setup yielded')
        self.assertEqual(calls, [pipeline.WINDOWS_CREATE, pipeline.WINDOWS_CLEANUP])
        self.assertIn('windowsCredentialCleanup', report)

    def test_windows_cleanup_failure_is_a_failed_credential_context(self):
        credentials = self.root / 'credentials'
        credentials.mkdir()
        report = {}
        def tool(script, environment):
            if script == pipeline.WINDOWS_CREATE:
                Path(environment['MINYAR_TEST_STATE']).write_text(json.dumps({
                    'certificates': [{'name': 'signer', 'thumbprint': self.thumb}]}))
            else:
                raise subprocess.CalledProcessError(1, 'powershell cleanup')
        with patch.object(pipeline, 'ps', side_effect=tool), patch.object(pipeline, 'require_owned_boat_windows'):
            with self.assertRaises(subprocess.CalledProcessError):
                with pipeline.windows_credentials(credentials, report):
                    pass
        self.assertIn('FAILED', report['windowsCredentialCleanup'])

    def test_cleanup_failure_prevents_atomic_pipeline_publication(self):
        temporary_directory = tempfile.TemporaryDirectory
        publish_directory = pipeline.release.publish_directory
        write_report = pipeline.write_report
        class FailingStagingCleanup:
            def __init__(self, **kwargs):
                self.directory = temporary_directory(**kwargs)
            def __enter__(self):
                return self.directory.__enter__()
            def __exit__(self, *args):
                self.directory.__exit__(*args)
                raise OSError('private staging cleanup failed')
        for index, failure in enumerate(('openssl', 'credential cleanup', 'staging cleanup', 'publication', 'report', None)):
            output = self.root / ('TEST-output-' + str(index))
            report_path = self.root / ('TEST-status-' + str(index) + '.json')
            stages, stderr = [], io.StringIO()
            def completed(args, work, publication, report):
                stages.append(work)
                (publication / 'TEST-evidence.txt').write_text('public fixture')
                if failure == 'credential cleanup':
                    raise ValueError('credential cleanup failed')
            def publish(source, destination):
                self.assertTrue(stages and all(not stage.exists() for stage in stages))
                value = json.loads((source / 'TEST-report.json').read_text())
                self.assertEqual(value['stagingCleanup'], 'verified: removed before publication')
                if failure == 'publication':
                    raise OSError('atomic commit failed')
                publish_directory(source, destination)
            def report_file(path, value):
                if failure == 'report':
                    raise OSError('external report failed')
                write_report(path, value)
            with patch.object(sys, 'argv', ['pipeline', '--native', 'macos', '--output', str(output), '--openssl', 'openssl', '--cc', 'clang', '--ephemeral-macos-ci', '--report', str(report_path)]), \
                 patch.object(pipeline.sys, 'platform', 'darwin'), patch.object(pipeline.platform, 'machine', return_value='arm64'), \
                 patch.object(pipeline, 'require_ephemeral_macos_ci'), \
                 patch.object(pipeline, 'run', side_effect=subprocess.CalledProcessError(1, 'openssl') if failure == 'openssl' else None,
                     return_value=subprocess.CompletedProcess([], 0, 'OpenSSL 3.6.0', '')), \
                 patch.object(pipeline, 'pipeline', side_effect=completed), \
                 patch.object(pipeline.tempfile, 'TemporaryDirectory', FailingStagingCleanup if failure == 'staging cleanup' else temporary_directory), \
                 patch.object(pipeline.release, 'publish_directory', side_effect=publish) as commit, \
                 patch.object(pipeline, 'write_report', side_effect=report_file), \
                 redirect_stderr(stderr), redirect_stdout(io.StringIO()):
                if failure is None:
                    pipeline.main()
                else:
                    with self.assertRaises(SystemExit):
                        pipeline.main()
                self.assertEqual(commit.call_count, 0 if failure in ('openssl', 'credential cleanup', 'staging cleanup') else 1)
            self.assertEqual(output.exists(), failure in ('report', None))
            self.assertEqual(list(self.root.glob('.minyar-test-pipeline-*')), [])
            self.assertEqual(list(self.root.glob('.minyar-test-generation-*')), [])
            if failure == 'report':
                self.assertIn('generation published; external status reporting failed', stderr.getvalue())
                self.assertIn('"generationPublished": true', stderr.getvalue())
            else:
                value = json.loads(report_path.read_text())
                self.assertEqual(value['status'], 'passed' if failure is None else 'FAILED')
                self.assertEqual(value['generationPublished'], failure is None)
                if failure == 'openssl':
                    self.assertEqual(value['stagingCleanup'], 'not created')
                if failure:
                    self.assertIn('no successful generation', stderr.getvalue())

    def test_test_cli_has_no_production_credential_or_service_options(self):
        for native in ('test-macos', 'test-windows'):
            for option in ('--notary-profile', '--timestamp', '--machine-store', '--azure-dlib'):
                result = subprocess.run([sys.executable, str(ROOT / 'scripts/release.py'), native, option, 'production'], capture_output=True)
                self.assertNotEqual(result.returncode, 0)
        help_text = subprocess.run([sys.executable, str(ROOT / 'scripts/release.py'), '--help'], check=True, capture_output=True, text=True).stdout
        self.assertIn('TEST ONLY', help_text)

    def test_production_macos_uses_only_explicit_provisioned_keychain_paths(self):
        def tool(args, **kwargs):
            result = self.tool(args, **kwargs)
            if args[:2] == ['hdiutil', 'create']:
                Path(args[-1]).write_bytes(b'contract DMG')
            if args[:3] == ['xcrun', 'notarytool', 'submit']:
                result.stdout = json.dumps({'status': 'Accepted'})
            return result
        release.macos(self.app, self.root / 'production.dmg', 'Developer ID Application: Owner (TEAM)',
                      'owner-notary', keychain=self.keychain, notary_keychain=self.keychain, run=tool)
        for command in self.calls:
            if command[:2] == ['codesign', '--force'] or command[:3] == ['xcrun', 'notarytool', 'submit']:
                self.assertEqual(command[command.index('--keychain') + 1], str(self.keychain.resolve()))
        self.assertFalse(any(c[0] in ('security', 'sudo') for c in self.calls))


if __name__ == '__main__':
    unittest.main()
