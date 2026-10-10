#!/usr/bin/env python3
"""Offline R2 publication must bind content and publish one signed envelope."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SPEC=importlib.util.spec_from_file_location('manifest',Path(__file__).resolve().parents[1]/'scripts/update-manifest.py')
manifest=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(manifest)

class Publication(unittest.TestCase):
    def test_real_openssl_signer_matches_rfc8032_public_key_and_domain_binding(self):
        openssl = os.environ.get('MINYAR_TEST_OPENSSL', shutil.which('openssl'))
        if not openssl:
            self.skipTest('OpenSSL 3 is required for the offline publisher only')
        version = subprocess.run([openssl,'version'],check=True,capture_output=True,text=True).stdout
        if not version.startswith('OpenSSL 3.'):
            self.skipTest('OpenSSL 3 is required for the offline publisher only')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            # Public RFC 8032 section 7.1 test seed; never a production key.
            seed=bytes.fromhex('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60')
            der=bytes.fromhex('302e020100300506032b657004220420')+seed
            key=root/'fixture.der'; key.write_bytes(der)
            value,public=manifest.signed(b'fixture metadata\n',key,openssl)
            self.assertEqual(public.hex(),'d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
            self.assertEqual(len(value),64)
            pub=root/'public.der';pub.write_bytes(bytes.fromhex('302a300506032b6570032100')+public)
            signature=root/'signature';signature.write_bytes(value)
            message=root/'message';message.write_bytes(b'fixture metadata\n')
            wrong_domain=subprocess.run([openssl,'pkeyutl','-verify','-rawin','-pubin','-keyform','DER',
                '-inkey',str(pub),'-sigfile',str(signature),'-in',str(message)],capture_output=True)
            self.assertNotEqual(wrong_domain.returncode,0)

    def test_stages_content_addressed_artifact_and_uncached_channel_last(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); artifact=root/'agent';artifact.write_bytes(b'\0\xfffixture')
            output=root/'static'
            manifest.prepare(artifact,output,'org.tolum.peer','macos-arm64','stable',1,'1.1.0',
                1800000000,1800003600,1,'https://updates.example',sign=lambda data:(b'S'*64,b'P'*32))
            plan=json.loads((output/'r2-publish-plan.json').read_text())
            self.assertEqual(len(plan['objects']),2)
            asset,pointer=plan['objects']
            self.assertIn('/releases/', '/'+asset['key'])
            self.assertEqual((output/asset['key']).read_bytes(),artifact.read_bytes())
            self.assertIn('immutable',asset['httpMetadata']['cacheControl'])
            self.assertEqual(pointer['key'],'channels/stable/macos-arm64.update')
            self.assertEqual(pointer['httpMetadata']['cacheControl'],'no-store')
            envelope=(output/pointer['key']).read_bytes()
            self.assertEqual(envelope[:64],b'S'*64)
            fields=envelope[64:].decode().splitlines()
            self.assertEqual(len(fields),12)
            self.assertEqual(fields[8],'1')
            self.assertEqual(fields[9],'https://updates.example/'+asset['key'])
            self.assertNotIn('credential',json.dumps(plan).lower())

    def test_invalid_rollout_version_or_expiration_never_invokes_signer_or_publishes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); artifact=root/'agent';artifact.write_bytes(b'fixture')
            calls=[]
            for version,rollout,expires in [('1.0-beta',1,1800003600),('01.1.0',1,1800003600),
                    ('1.1.0',2,1800003600),('1.1.0',100,1801000000),('1.1.0',10,1800000000)]:
                output=root/'static'
                with self.subTest(version=version,rollout=rollout),self.assertRaises(ValueError):
                    manifest.prepare(artifact,output,'org.tolum.peer','macos-arm64','stable',1,version,
                        1800000000,expires,rollout,'https://updates.example',sign=lambda data:calls.append(data))
                self.assertFalse(output.exists())
            self.assertEqual(calls,[])

if __name__=='__main__': unittest.main()
