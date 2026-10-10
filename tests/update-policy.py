#!/usr/bin/env python3
"""TUF-inspired rollback/freeze/equivocation cases through compiled Minyar.

RFC8032 vectors test the native primitive separately. Policy cases are signed
with a public test fixture seed, so malformed signed metadata is tested too.
"""
import hashlib
import os
import platform
from pathlib import Path
import subprocess
import tempfile
import unittest
from clang_helpers import windows_host

ROOT = Path(__file__).resolve().parents[1]


class UpdatePolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='minyar-update-policy-')
        cls.directory = Path(cls.temp.name)
        clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
        cls.signer = cls.directory / ('signer.exe' if windows_host() else 'signer')
        subprocess.run([clang, '-O2', str(ROOT/'tests/update-sign.c'),
            str(ROOT/'vendor/monocypher/monocypher.c'), str(ROOT/'vendor/monocypher/monocypher-ed25519.c'),
            '-o', str(cls.signer)], check=True)
        cls.driver = cls.directory / ('driver.exe' if windows_host() else 'driver')
        env = dict(os.environ, LIMITED='', SANITIZER_LIMITED='')
        subprocess.run([str(ROOT/'minyar'), '--library', str(ROOT/'library'), str(ROOT/'tests/update-driver.min'),
            '-o', str(cls.driver)], env=env, check=True, capture_output=True, text=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.artifact = b'fixture executable\x00\xffbinary'
        self.digest = hashlib.sha256(self.artifact).hexdigest()
        target=('windows' if windows_host() else {'Darwin':'macos','Linux':'linux'}[platform.system()])+'-'+('arm64' if platform.machine().lower() in ('arm64','aarch64') else 'x86_64')
        self.fields = ['MINYAR-UPDATE-1', 'org.tolum.peer', target, 'stable', '1', '1.1.0',
            '1799999990', '1800003600', '100', f'https://updates.example/releases/{self.digest}/agent',
            self.digest, str(len(self.artifact))]

    def invoke(self, fields=None, *, raw=None, corrupt=False, floor=0, highest='1.0.0', previous='', device='device',
               root=None, artifact=None, now=1800000000):
        metadata = ('\n'.join(self.fields if fields is None else fields) + '\n').encode() if raw is None else raw
        manifest = self.directory/'release.manifest'
        signature = self.directory/'release.sig'
        manifest.write_bytes(metadata)
        signed = subprocess.check_output([str(self.signer), str(manifest)])
        self.assertEqual(len(signed), 64, 'the signer must preserve binary signature bytes')
        signature.write_bytes(bytes([signed[0] ^ 1]) + signed[1:] if corrupt else signed)
        if root is None:
            args = ['inspect', device, str(floor), highest, previous]
        else:
            package = self.directory/'artifact'
            package.write_bytes(self.artifact if artifact is None else artifact)
            args = [str(root), str(package), str(now)]
        result = subprocess.run([str(self.driver), str(manifest), str(signature), *args],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.splitlines(), metadata

    def test_valid_metadata_and_signature_mutation(self):
        self.assertEqual(self.invoke()[0], ['true', 'true', '0'])
        self.assertEqual(self.invoke(corrupt=True)[0], ['false', 'false', '10'])

    def test_signer_binary_output_survives_every_byte_value(self):
        # Vary public fixture input independently of policy. Across these signatures,
        # every possible byte (including LF, CR and DOS EOF) crosses the real pipe.
        observed = set()
        for index in range(256):
            manifest = self.directory/'binary-signature-input'
            manifest.write_bytes(f'binary-signature-{index}'.encode())
            signed = subprocess.check_output([str(self.signer), str(manifest)])
            self.assertEqual(len(signed), 64)
            observed.update(signed)
        self.assertEqual(observed, set(range(256)))

    def test_signed_malformed_fields_are_recoverable(self):
        replacements = {
            0: ['', 'MINYAR-UPDATE-2'], 1: ['org.attacker.app'], 2: ['other-platform'], 3: ['beta'],
            4: ['0', '-1', '+1', '01', '2147483648', '999999999999999999999'],
            5: ['1.0.0-beta', '01.2.3', '1.2', '1.2.3.4', '1..3', '1.2.2147483648', '0.9.0'],
            6: ['1800000301', '-1', '999999999999999999999'],
            7: ['1800000000', '1799999990', '1801000000'], 8: ['0', '2', '9', '11', '99', '101', '010'],
            9: ['http://updates.example/agent', 'https://updates.example.evil/agent',
                f'https://updates.example/releases/{self.digest}/../evil',
                f'https://updates.example/releases/{self.digest}/%2e%2e',
                f'https://updates.example/releases/{self.digest}/agent?x=1'],
            10: ['a'*63, 'A'*64, 'g'*64], 11: ['0', '-1', '134217729', '2.0', '02']}
        for index, choices in replacements.items():
            for replacement in choices:
                fields = self.fields.copy(); fields[index] = replacement
                with self.subTest(index=index, value=replacement):
                    self.assertEqual(self.invoke(fields)[0], ['false', 'false', '10'])
        valid = ('\n'.join(self.fields)+'\n').encode()
        for data in [valid[:-1], valid+b'junk', b'\n'+valid, valid.replace(b'\n',b'\r\n'),
                     valid.replace(b'org.tolum.peer', b'org.tolum.peer\x00'), valid+b'\n']:
            with self.subTest(raw=data[:60]):
                self.assertEqual(self.invoke(raw=data)[0], ['false', 'false', '10'])

    def test_replay_equivocation_and_version_order_are_independent(self):
        _, metadata = self.invoke()
        digest = hashlib.sha256(metadata).hexdigest()
        self.assertEqual(self.invoke(floor=1, previous=digest)[0], ['true', 'true', '0'])
        self.assertEqual(self.invoke(floor=2, previous=digest)[0], ['false', 'false', '10'])
        self.assertEqual(self.invoke(floor=1, previous='a'*64)[0], ['false', 'false', '10'])
        self.assertEqual(self.invoke(highest='1.2.0')[0], ['false', 'false', '10'])
        fields=self.fields.copy(); fields[5]='1.10.0'
        self.assertEqual(self.invoke(fields, highest='1.9.99')[0], ['true', 'true', '0'])

    def test_rollouts_use_nested_stable_cohorts_at_all_boundaries(self):
        devices={}
        for index in range(5000):
            device=f'device-{index}'
            digest=hashlib.sha256(('MINYAR-UPDATE-COHORT-V1\norg.tolum.peer\nstable\n'+device).encode()).digest()
            cohort=int.from_bytes(digest[:4], 'big')%100
            devices.setdefault(cohort, device)
        self.assertEqual(len(devices),100)
        for rollout in [1,10,100]:
            fields=self.fields.copy(); fields[8]=str(rollout)
            for cohort in [0,1,9,10,99]:
                with self.subTest(rollout=rollout,cohort=cohort):
                    self.assertEqual(self.invoke(fields,device=devices[cohort])[0],
                        ['true',str(cohort<rollout).lower(),'0'])

    def test_failed_artifact_persists_floor_and_retry_recovers(self):
        root=self.directory/'installation'
        root.mkdir(mode=0o700)
        self.assertEqual(self.invoke(root=root,artifact=b'malicious')[0], ['false','6'])
        self.assertTrue((root/'state').is_file())
        self.assertFalse((root/'versions').exists())
        self.assertEqual(self.invoke(root=root)[0], ['true','true'])
        suffix='.exe' if windows_host() else '.bin'
        self.assertEqual((root/'versions'/ (self.digest+suffix)).read_bytes(), self.artifact)
        self.assertEqual(self.invoke(root=root)[0], ['true','false'])
        fields=self.fields.copy(); fields[4]='2'; fields[5]='1.0.0'
        before=(root/'state').read_bytes()
        self.assertEqual(self.invoke(fields,root=root)[0], ['false','10'])
        self.assertEqual((root/'state').read_bytes(),before)
        self.assertEqual(self.invoke(root=root,now=1799999999)[0], ['false','7'])
        (root/'state').write_bytes(b'corrupt')
        self.assertEqual(self.invoke(root=root)[0], ['false','7'])


if __name__ == '__main__':
    unittest.main()
