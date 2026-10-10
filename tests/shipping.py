#!/usr/bin/env python3
"""Release pipeline contracts: failed signing/notarization never publishes bytes.

Apple's notarization requirements and SignTool's warning exit codes drive these
checks. Temporary fake tools model refusals at every externally visible phase.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from clang_helpers import windows_host

SPEC = importlib.util.spec_from_file_location('release', Path(__file__).resolve().parents[1] / 'scripts/release.py')
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class Shipping(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app = self.root / 'A space.app'
        (self.app / 'Contents/MacOS').mkdir(parents=True)
        (self.app / 'Contents/MacOS/main').write_bytes(b'\xcf\xfa\xed\xfeexecutable')
        self.out = self.root / 'release.dmg'
        self.calls = []

    def tearDown(self):
        self.temp.cleanup()

    def tool(self, args, **kwargs):
        self.calls.append(args)
        if args[:2] == ['hdiutil', 'create']:
            Path(args[-1]).write_bytes(b'disk image')
        if args[:2] == ['ditto', '-c']:
            Path(args[-1]).write_bytes(b'zip')
        return subprocess.CompletedProcess(args, 0, json.dumps({'status': 'Accepted', 'id': 'test-request'}), '')

    def test_development_adhoc_or_missing_notary_credentials_cannot_ship(self):
        for identity, profile in [('-', 'profile'), ('Apple Development: Developer (ABC)', 'profile'),
                                  ('', 'profile'), ('Developer ID Application: Developer (ABC)', '')]:
            with self.subTest(identity=identity, profile=profile):
                with self.assertRaises(ValueError):
                    release.macos(self.app, self.out, identity, profile, run=self.tool)
                self.assertFalse(self.out.exists())
                self.assertEqual(self.calls, [])

    def test_macos_signs_hardened_code_then_notarizes_and_staples_app_and_dmg(self):
        release.macos(self.app, self.out, 'Developer ID Application: Developer (ABC)', 'profile', run=self.tool)
        signs = [c for c in self.calls if c[:2] == ['codesign', '--force']]
        self.assertGreaterEqual(len(signs), 3)
        for command in signs[:-1]:
            self.assertIn('runtime', command)
            self.assertIn('--timestamp', command)
        self.assertNotIn('--deep', sum(signs, []))
        self.assertEqual(sum(c[:3] == ['xcrun', 'notarytool', 'submit'] for c in self.calls), 2)
        self.assertEqual(sum(c[:3] == ['xcrun', 'stapler', 'staple'] for c in self.calls), 2)
        self.assertEqual(self.out.read_bytes(), b'disk image')
        self.assertEqual((self.app / 'Contents/MacOS/main').read_bytes(), b'\xcf\xfa\xed\xfeexecutable')

    def test_every_tool_failure_and_rejected_notarization_preserves_existing_output(self):
        release.macos(self.app, self.out, 'Developer ID Application: Developer (ABC)', 'profile', run=self.tool)
        count = len(self.calls)
        for failure in range(count):
            with self.subTest(failure=failure):
                self.out.write_bytes(b'previous release')
                calls = []
                def fail(args, **kwargs):
                    calls.append(args)
                    if len(calls) - 1 == failure:
                        raise subprocess.CalledProcessError(1, args)
                    return self.tool(args, **kwargs)
                with self.assertRaises(subprocess.CalledProcessError):
                    release.macos(self.app, self.out, 'Developer ID Application: Developer (ABC)', 'profile', run=fail)
                self.assertEqual(self.out.read_bytes(), b'previous release')
        for status in ['Rejected', 'In Progress', '', None]:
            def reject(args, **kwargs):
                result = self.tool(args, **kwargs)
                if args[:3] == ['xcrun', 'notarytool', 'submit']:
                    result.stdout = json.dumps({'status': status})
                return result
            with self.subTest(status=status), self.assertRaises(ValueError):
                release.macos(self.app, self.out, 'Developer ID Application: Developer (ABC)', 'profile', run=reject)
            self.assertEqual(self.out.read_bytes(), b'previous release')

    def test_windows_uses_explicit_certificate_sha256_timestamp_and_authenticode_policy(self):
        source = self.root / 'input with spaces.exe'
        source.write_bytes(b'MZfixture')
        out = self.root / 'signed.exe'
        release.windows(source, out, 'sdk/signtool.exe', 'AB' * 20, 'https://timestamp.example', run=self.tool)
        sign, verify = self.calls
        self.assertIn('/sha1', sign)
        self.assertNotIn('/a', sign)
        self.assertEqual(sign[sign.index('/fd') + 1], 'SHA256')
        self.assertEqual(sign[sign.index('/td') + 1], 'SHA256')
        self.assertEqual(verify[1:5], ['verify', '/pa', '/all', '/tw'])
        self.assertEqual(out.read_bytes(), b'MZfixture')

    def test_windows_missing_identity_invalid_timestamp_and_signing_warning_fail_closed(self):
        source = self.root / 'input.exe'
        source.write_bytes(b'MZfixture')
        out = self.root / 'signed.exe'
        for identity, timestamp in [('', 'https://timestamp.example'), ('AA', 'https://timestamp.example'),
                                    ('AB' * 20, 'http://timestamp.example')]:
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                release.windows(source, out, 'signtool.exe', identity, timestamp, run=self.tool)
            self.assertFalse(out.exists())
        def warning(args, **kwargs):
            return subprocess.CompletedProcess(args, 2, 'timestamp failed', '')
        with self.assertRaises(subprocess.CalledProcessError):
            release.windows(source, out, 'signtool.exe', 'AB' * 20, 'https://timestamp.example', run=warning)
        self.assertFalse(out.exists())

    def test_macos_rejects_development_entitlements_and_escaping_bundle_links(self):
        entitlements = self.root / 'development.plist'
        entitlements.write_text('<?xml version="1.0"?><plist version="1.0"><dict>'
            '<key>com.apple.security.get-task-allow</key><true/></dict></plist>')
        with self.assertRaises(ValueError):
            release.macos(self.app, self.out, 'Developer ID Application: Developer (ABC)',
                'profile', entitlements=entitlements, run=self.tool)
        outside = self.root / 'external'
        outside.write_bytes(b'external')
        link = self.app / 'Contents/escape'
        if windows_host() and os.name != 'nt':
            # The MSYS runtime defaults to copying the target, which is not a
            # symlink fixture. A fresh process reads nativestrict at startup:
            # fail if a real native link cannot be created; never test a copy.
            environment = os.environ.copy()
            flags = [flag for flag in environment.get('MSYS', '').split()
                     if not flag.startswith('winsymlinks')]
            environment['MSYS'] = ' '.join(flags + ['winsymlinks:nativestrict'])
            subprocess.run(['ln', '-s', '--', outside, link], check=True, env=environment,
                           capture_output=True, text=True, timeout=10)
        else:
            link.symlink_to(outside)
        self.assertTrue(link.is_symlink(), 'escaping-link fixture must be a real symlink')
        self.assertEqual(link.resolve(), outside.resolve())
        with self.assertRaises(ValueError):
            release.macos(self.app, self.out, 'Developer ID Application: Developer (ABC)',
                'profile', run=self.tool)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.out.exists())

    def test_azure_signing_requires_exact_endpoint_without_credentials_or_redirect_parts(self):
        source = self.root / 'input.exe'; source.write_bytes(b'MZfixture')
        out = self.root / 'signed.exe'
        dlib = self.root / 'signing.dll'; dlib.write_bytes(b'fixture')
        metadata = self.root / 'metadata.json'
        for endpoint in ['https://weu.codesigning.azure.net',
                'https://credential@weu.codesigning.azure.net',
                'https://weu.codesigning.azure.net/other',
                'https://weu.codesigning.azure.net?x=1',
                'https://weu.codesigning.azure.net#fragment',
                'https://weu.codesigning.azure.net:8443',
                'https://weu.codesigning.azure.net.attacker.example']:
            self.calls.clear()
            metadata.write_text(json.dumps({'Endpoint':endpoint,
                'CodeSigningAccountName':'tolum', 'CertificateProfileName':'public-trust'}))
            if endpoint == 'https://weu.codesigning.azure.net':
                release.windows(source,out,'signtool.exe','','https://timestamp.example',
                    azure_dlib=dlib,azure_metadata=metadata,run=self.tool)
                self.assertIn('/dlib',self.calls[0]); self.assertIn('/dmdf',self.calls[0])
                self.assertNotIn('/sha1',self.calls[0])
            else:
                with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                    release.windows(source,out,'signtool.exe','','https://timestamp.example',
                        azure_dlib=dlib,azure_metadata=metadata,run=self.tool)
                self.assertEqual(self.calls,[])


if __name__ == '__main__':
    unittest.main()
