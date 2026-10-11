#!/usr/bin/env python3
"""Signed owned-process execution and independent hostile bundle construction."""
import hashlib
import os
from pathlib import Path
import platform
import plistlib
import struct
import subprocess
import tempfile
import unittest
from clang_helpers import windows_host

ROOT=Path(__file__).resolve().parents[1]
MAGIC=b'MINYAR-BUNDLE-1\n'
KEY='d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a'

def package(entries,main='App.app/Contents/MacOS/main'):
    name=main.encode('ascii')
    result=MAGIC+struct.pack('>I',len(name))+name+struct.pack('>I',len(entries))
    for kind,path,mode,data in entries:
        name=path.encode('ascii')
        result+=struct.pack('>BBIQ',ord(kind),mode,len(name),len(data))+name+data
    return result

class Launch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='minyar-update-launch-')
        cls.lab=Path(cls.temp.name).resolve()
        clang=os.environ.get('MINYAR_TEST_CLANG','clang')
        suffix='.exe' if windows_host() else ''
        cls.signer=cls.lab/('signer'+suffix)
        cls.driver=cls.lab/('driver'+suffix)
        cls.helper=cls.lab/('owned-helper'+suffix)
        subprocess.run([clang,'-O2',str(ROOT/'tests/update-sign.c'),
            str(ROOT/'vendor/monocypher/monocypher.c'),str(ROOT/'vendor/monocypher/monocypher-ed25519.c'),
            '-o',str(cls.signer)],check=True,timeout=60)
        subprocess.run([clang,'-O2','-Wall','-Wextra','-Werror',str(ROOT/'tests/update-owned-helper.c'),
            *(['-lshell32'] if windows_host() else ['-framework','CoreFoundation'] if platform.system()=='Darwin' else []),'-o',str(cls.helper)],check=True,timeout=60)
        subprocess.run([str(ROOT/'minyar'),'--library',str(ROOT/'library'),
            str(ROOT/'tests/update-launch-driver.min'),'-o',str(cls.driver)],
            env=dict(os.environ,LIMITED='',SANITIZER_LIMITED=''),check=True,timeout=180)
        cls.target=('windows' if windows_host() else {'Darwin':'macos','Linux':'linux'}[platform.system()])+'-'+(
            'arm64' if platform.machine().lower() in ('arm64','aarch64') else 'x86_64')
        cls.entries=[
            ('D','App.app',0,b''),('D','App.app/Contents',0,b''),
            ('F','App.app/Contents/Info.plist',0,plistlib.dumps({'CFBundleExecutable':'main','CFBundleIdentifier':'org.tolum.peer','CFBundlePackageType':'APPL','CFBundleName':'Owned Helper','CFBundleVersion':'1.1.0'})),
            ('D','App.app/Contents/MacOS',0,b''),
            ('F','App.app/Contents/MacOS/main',1,cls.helper.read_bytes()),
            ('D','App.app/Contents/Resources',0,b''),
            ('F','App.app/Contents/Resources/message.txt',0,b'signed resource'),
            ('D','Empty',0,b'')]
    @classmethod
    def tearDownClass(cls):
        if os.environ.get('MINYAR_UPDATE_EVIDENCE'):
            import shutil
            destination=Path(os.environ['MINYAR_UPDATE_EVIDENCE'])/'launch-fixtures'
            shutil.copytree(cls.lab,destination,dirs_exist_ok=True)
        cls.temp.cleanup()

    def setUp(self):
        self.lab=Path(tempfile.mkdtemp(dir=self.lab))
        self.root=self.lab/'installation';self.root.mkdir(mode=0o700)
        self.metadata=self.lab/'metadata';self.signature=self.lab/'signature'
        self.artifact=self.lab/'artifact'

    def install(self,data,version='1.1.0',sequence=1,rollout=100,device='test-device',corrupt=False):
        digest=hashlib.sha256(data).hexdigest();self.artifact.write_bytes(data)
        fields=['MINYAR-UPDATE-1','org.tolum.peer',self.target,'stable',str(sequence),version,
            '1799999990','1800003600',str(rollout),
            f'https://updates.example/releases/{digest}/artifact',digest,str(len(data))]
        self.metadata.write_bytes(('\n'.join(fields)+'\n').encode())
        sig=subprocess.check_output([str(self.signer),str(self.metadata)],timeout=10)
        self.signature.write_bytes(bytes([sig[0]^1])+sig[1:] if corrupt else sig)
        result=self.run_driver('install',str(self.artifact),device=device)
        return result,digest

    def run_driver(self,mode,current='1.0.0',args=(),device='test-device',now=1800000000):
        result=subprocess.run([str(self.driver),mode,str(self.root),str(self.metadata),str(self.signature),
            current,str(now),device,*args],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        return result.stdout.splitlines()

    def test_signed_bundle_launch_preserves_arguments_resources_and_handles(self):
        result,digest=self.install(package(self.entries))
        self.assertEqual(result,['true','true'])
        payload=self.root/'versions'/(digest+'.bundle')/'payload'
        self.assertEqual((payload/'App.app/Contents/Resources/message.txt').read_bytes(),b'signed resource')
        self.assertTrue((payload/'Empty').is_dir())
        arguments=['','space and tabs\t','quote"slash\\','é🦉','$(echo forbidden);*']
        output=self.run_driver('launch',args=arguments)
        self.assertIn('OWNED-HELPER',output)
        self.assertIn('RESOURCE:signed resource',output)
        if platform.system()=='Darwin':self.assertIn('NATIVE-BUNDLE-RESOURCE:signed resource',output)
        for value in arguments:self.assertIn(f'{len(value.encode())}:{value.encode().hex()}',output)
        if not windows_host():self.assertIn('LEAKED:0',output)
        self.assertIn('23',output)
        # Installed authorization remains usable offline after metadata expiry.
        self.assertIn('OWNED-HELPER',self.run_driver('launch',now=1801000000))

    def test_raw_owned_binary_launch_and_newer_trusted_floor(self):
        result,digest=self.install(self.helper.read_bytes())
        self.assertEqual(result,['true','true'])
        self.assertIn('OWNED-HELPER',self.run_driver('launch'))
        self.assertEqual(self.run_driver('launch',current='1.2.0')[0],'false')
        # Observing a failed newer release must preserve the current launch.
        self.install(b'future artifact',version='1.2.0',sequence=2,corrupt=True)
        self.assertIn('OWNED-HELPER',self.run_driver('launch'))
        state=(self.root/'state').read_text().splitlines()
        old_hash=state[7]
        # Reuse exactly the same artifact in a newer signed version.
        self.assertEqual(self.install(self.helper.read_bytes(),version='1.2.0',sequence=3)[0],['true','true'])
        self.assertNotEqual((self.root/'state').read_text().splitlines()[7],old_hash)
        self.assertIn('OWNED-HELPER',self.run_driver('launch',current='1.2.0'))
        self.assertTrue((self.root/'versions'/(digest+'.'+old_hash+'.receipt')).is_file())

    def test_newer_unselected_observation_preserves_active_authorization(self):
        self.install(package(self.entries))
        # Failed SHA validation records a new observation without switching active.
        future=b'future native artifact';digest=hashlib.sha256(future).hexdigest()
        self.artifact.write_bytes(b'bad download')
        fields=['MINYAR-UPDATE-1','org.tolum.peer',self.target,'stable','2','1.2.0',
            '1799999990','1800003600','100',f'https://updates.example/releases/{digest}/artifact',digest,str(len(future))]
        self.metadata.write_bytes(('\n'.join(fields)+'\n').encode())
        self.signature.write_bytes(subprocess.check_output([str(self.signer),str(self.metadata)],timeout=10))
        self.assertEqual(self.run_driver('install',str(self.artifact))[0],'false')
        self.assertEqual((self.root/'state').read_text().splitlines()[2],'1.2.0')
        self.assertIn('OWNED-HELPER',self.run_driver('launch'))

    def test_restart_has_successor_and_errors_remain_recoverable(self):
        self.install(package(self.entries))
        output=self.run_driver('restart',args=['successor'])
        self.assertIn('OWNED-HELPER',output)
        self.assertNotIn('true',output) # successful restart never returns
        self.assertEqual(self.run_driver('restart',current='9.0.0')[0],'false')
        self.assertNotIn('OWNED-HELPER',self.run_driver('launch',now=1799999999))
        self.assertEqual(self.run_driver('launch',args=['x']*256)[0],'false')
        self.assertEqual(self.run_driver('launch',args=['x'*32769])[0],'false')

    def test_launch_rechecks_signed_cohort_and_manifest_binding(self):
        self.install(package(self.entries),rollout=100)
        # Altering caller application identity is covered by inspect; installation
        # identity is also checked from the signed receipt when launching.
        wanted=None
        for index in range(1000):
            candidate=f'cohort-{index}'
            value=int.from_bytes(hashlib.sha256(('MINYAR-UPDATE-COHORT-V1\norg.tolum.peer\nstable\n'+candidate).encode()).digest()[:4],'big')%100
            if value==0:wanted=candidate;break
        self.assertIsNotNone(wanted)
        self.root=self.lab/'cohort-root';self.root.mkdir(mode=0o700)
        self.assertEqual(self.install(package(self.entries),rollout=1,device=wanted)[0],['true','true'])
        self.assertIn('OWNED-HELPER',self.run_driver('launch',device=wanted))
        for candidate in ['outsider-'+str(index) for index in range(100)]:
            value=int.from_bytes(hashlib.sha256(('MINYAR-UPDATE-COHORT-V1\norg.tolum.peer\nstable\n'+candidate).encode()).digest()[:4],'big')%100
            if value:
                self.assertEqual(self.run_driver('launch',device=candidate)[0],'false');break

    def test_legacy_generation_requires_fresh_authentication_and_can_migrate(self):
        _,digest=self.install(self.helper.read_bytes())
        state=(self.root/'state').read_text().splitlines()
        state[0]='MINYAR-UPDATER-STATE-1'
        (self.root/'state').write_text('\n'.join(state[:7])+'\n')
        self.assertEqual(self.run_driver('launch')[0],'false')
        # Exact signed same-version artifact supplies the missing authorization.
        result,_=self.install(self.helper.read_bytes())
        self.assertEqual(result,['true','true'])
        self.assertEqual((self.root/'state').read_text().splitlines()[0],'MINYAR-UPDATER-STATE-2')
        self.assertIn('OWNED-HELPER',self.run_driver('launch'))

    def test_signature_artifact_receipt_and_resource_mutation_fail_closed(self):
        original=package(self.entries)
        self.assertEqual(self.install(original,corrupt=True)[0][0],'false')
        self.assertFalse((self.root/'versions').exists())
        _,digest=self.install(original)
        generation=self.root/'versions'/(digest+'.bundle')
        active_hash=(self.root/'state').read_text().splitlines()[7]
        receipt=self.root/'versions'/(digest+'.'+active_hash+'.receipt');before=receipt.read_bytes()
        receipt.write_bytes(bytes([before[0]^1])+before[1:])
        self.assertEqual(self.run_driver('launch')[0],'false')
        receipt.write_bytes(before)
        resource=generation/'payload/App.app/Contents/Resources/message.txt'
        resource.chmod(0o600);resource.write_bytes(b'changed resource')
        self.assertEqual(self.run_driver('launch')[0],'false')
        self.assertNotIn('OWNED-HELPER',self.run_driver('launch'))

    def test_signed_hostile_packages_preserve_previous_active_generation(self):
        _,digest=self.install(self.helper.read_bytes())
        bad_paths=['../escape','/absolute','A/../../escape','A\\escape','A:stream',
            'NUL','con.txt','COM1','tail.','tail ','A//B','A/./B']
        hostile=[package([('F',path,1,b'owned')],main=path) for path in bad_paths]
        hostile += [b'MINYAR-BUNDLE-2\n',b'MINYAR-BUNDLE-',package(self.entries,main='missing'),package(self.entries)+b'extra',
            package(self.entries[:-1])[:-1],package([('L','linked',0,b'elsewhere')],main='linked'),
            package([('F','Main',1,self.helper.read_bytes()),('F','main',1,self.helper.read_bytes())],main='Main'),
            package([('F','A/file',1,self.helper.read_bytes())],main='A/file'),
            package([('F','main',1,b'#!/bin/sh\nexit 0\n')],main='main')]
        for index,data in enumerate(hostile):
            with self.subTest(index=index):
                result,_=self.install(data,version='1.2.0',sequence=2+index)
                self.assertEqual(result[0],'false',result)
                self.assertEqual((self.root/'state').read_text().splitlines()[5],digest)
                self.assertIn('OWNED-HELPER',self.run_driver('launch'))

    def test_production_encoder_feeds_signed_complete_bundle_activation(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('production_bundle',ROOT/'scripts/update-bundle.py')
        encoder=importlib.util.module_from_spec(spec);spec.loader.exec_module(encoder)
        source=self.lab/'production-tree';source.mkdir()
        for kind,path,mode,data in self.entries:
            target=source/path
            if kind=='D':target.mkdir()
            else:
                target.write_bytes(data);target.chmod(0o755 if mode else 0o644)
        artifact=self.lab/'production.pkg'
        encoder.prepare(source,artifact,'App.app/Contents/MacOS/main')
        self.assertEqual(self.install(artifact.read_bytes())[0],['true','true'])
        self.assertIn('RESOURCE:signed resource',self.run_driver('launch'))

    def test_missing_or_extra_payload_file_and_symlink_are_rejected(self):
        _,digest=self.install(package(self.entries))
        payload=self.root/'versions'/(digest+'.bundle')/'payload'
        resources=payload/'App.app/Contents/Resources'
        resources.chmod(0o700)
        (resources/'extra').write_bytes(b'unlisted')
        self.assertEqual(self.run_driver('launch')[0],'false')
        (resources/'extra').unlink()
        resource=resources/'message.txt';resource.unlink()
        self.assertEqual(self.run_driver('launch')[0],'false')
        if not windows_host():
            external=self.lab/'outside';external.write_bytes(b'signed resource')
            resource.symlink_to(external)
            self.assertEqual(self.run_driver('launch')[0],'false')

if __name__=='__main__':unittest.main()
