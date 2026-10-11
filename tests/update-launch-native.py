#!/usr/bin/env python3
"""Real OS handle pinning, publication death, resource races and ASan/UBSan."""
import hashlib
import importlib.util
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile
from clang_helpers import windows_host

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('update_launch',ROOT/'tests/update-launch.py')
launch=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(launch)

def main():
    with tempfile.TemporaryDirectory(prefix='minyar-launch-native-') as directory:
        lab=Path(directory).resolve()
        suffix='.exe' if windows_host() else ''
        clang=os.environ.get('MINYAR_TEST_CLANG','clang')
        helper=lab/('owned-helper'+suffix);signer=lab/('signer'+suffix)
        subprocess.run([clang,'-O2',str(ROOT/'tests/update-owned-helper.c'),
            *(['-lshell32'] if windows_host() else ['-framework','CoreFoundation'] if platform.system()=='Darwin' else []),'-o',str(helper)],check=True,timeout=60)
        subprocess.run([clang,'-O2',str(ROOT/'tests/update-sign.c'),str(ROOT/'vendor/monocypher/monocypher.c'),
            str(ROOT/'vendor/monocypher/monocypher-ed25519.c'),'-o',str(signer)],check=True,timeout=60)
        target=('windows' if windows_host() else {'Darwin':'macos','Linux':'linux'}[platform.system()])+'-'+(
            'arm64' if platform.machine().lower() in ('arm64','aarch64') else 'x86_64')
        def fixture(label,bundle,version,sequence,resource=b'signed resource'):
            folder=lab/label;folder.mkdir()
            data=launch.package([('D','App.app',0,b''),('D','App.app/Contents',0,b''),
                ('F','App.app/Contents/Info.plist',0,plistlib.dumps({'CFBundleExecutable':'main','CFBundleIdentifier':'org.tolum.peer','CFBundlePackageType':'APPL','CFBundleName':'Owned Helper','CFBundleVersion':version})),('D','App.app/Contents/MacOS',0,b''),('F','App.app/Contents/MacOS/main',1,helper.read_bytes()),
                ('D','App.app/Contents/Resources',0,b''),('F','App.app/Contents/Resources/message.txt',0,resource)]) if bundle else helper.read_bytes()
            digest=hashlib.sha256(data).hexdigest()
            metadata=('\n'.join(['MINYAR-UPDATE-1','org.tolum.peer',target,'stable',str(sequence),version,
                '1799999990','1800003600','100',f'https://updates.example/releases/{digest}/artifact',digest,str(len(data))])+'\n').encode()
            hash=hashlib.sha256(metadata).hexdigest()
            (folder/'metadata').write_bytes(metadata)
            signature=subprocess.check_output([str(signer),str(folder/'metadata')],timeout=10)
            (folder/'receipt').write_bytes(signature+metadata);(folder/'artifact').write_bytes(data)
            state=f'MINYAR-UPDATER-STATE-2\n{sequence}\n{version}\n{hash}\n{version}\n{digest}\n1800000000\n{hash}\n{sequence}\n'
            (folder/'state').write_text(state)
            return folder,digest,hash
        raw=fixture('raw',False,'1.1.0',1)
        old=fixture('old',True,'1.1.0',1)
        new=fixture('new',True,'1.2.0',2,b'new signed resource')
        for sanitize in ([False] if windows_host() else [False,True]):
            compiler=os.environ.get('MINYAR_SANITIZER_CLANG',clang) if sanitize else clang
            flags=['-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer'] if sanitize else ['-O2']
            binary=lab/('probe-sanitize' if sanitize else 'probe');binary=binary.with_suffix(suffix)
            subprocess.run([compiler,'-std=c11','-D_GNU_SOURCE','-DMINYAR_SYSTEM_HEAP=1',
                '-DMINYAR_UPDATE_TEST_HOOK=1','-Wall','-Wextra','-Werror',*flags,
                *[str(ROOT/path) for path in ['tests/update-launch-native.c','runtime/native/update.c',
                'runtime/native/update_monocypher.c','runtime/native/update_ed25519.c','runtime/minyar_runtime.c']],
                '-lm','-o',str(binary)],check=True,timeout=90)
            env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1' if sys.platform.startswith('linux') else 'detect_leaks=0')
            def invoke(root,item,mode='install',fault='',mutation='',expected=0):
                folder,digest,hash=item
                result=subprocess.run([str(binary),str(root),str(folder/'artifact'),str(folder/'receipt'),
                    digest,hash,str(folder/'state'),mode,fault,str(mutation)],
                    capture_output=True,text=True,env=env,timeout=15)
                assert result.returncode==expected,(mode,fault,result.returncode,result.stdout,result.stderr)
                return result.stdout.splitlines()
            prefix='san-' if sanitize else 'normal-'
            # Actual nonprivileged fork refusal is recoverable and must close
            # both status-pipe descriptors, preserving the installed journal.
            if sys.platform.startswith('linux') and os.geteuid()!=0:
                root=lab/(prefix+'fork-failure');root.mkdir(mode=0o700)
                assert invoke(root,old)==['ACTIVATED']
                before=(root/'state').read_bytes()
                output=invoke(root,old,'fork-failure')
                assert 'FORK-REFUSED-WITHOUT-LEAK' in output and 'ERROR' in output,output
                assert (root/'state').read_bytes()==before
                assert 'OWNED-HELPER' in invoke(root,old,'launch')
            # Deterministic post-verification mutation races.
            for mode in ['replace','write','extra','ancestor','parent','anchored-parent']:
                for bundled,item in [(False,raw),(True,old)]:
                    if mode=='extra' and not bundled:continue
                    root=lab/(prefix+mode+str(bundled))
                    if mode in ('parent','anchored-parent'):
                        root.mkdir(mode=0o700);root=root/'installation'
                    root.mkdir(mode=0o700)
                    assert invoke(root,item)==['ACTIVATED']
                    digest=item[1]
                    if bundled:
                        payload=root/'versions'/(digest+'.bundle')/'payload'
                        mutation=payload/('extra' if mode=='extra' else 'App.app/Contents/Resources/message.txt')
                    else:
                        mutation=root/'versions'/(digest+('.exe' if windows_host() else '.bin'))
                    if mode=='ancestor':mutation=root
                    if mode in ('parent','anchored-parent'):mutation=root.parent
                    output=invoke(root,item,mode,mutation=mutation)
                    if windows_host() and mode!='extra':
                        assert 'MUTATION-BLOCKED' in output and 'OWNED-HELPER' in output,output
                    else:
                        assert 'ERROR' in output and 'OWNED-HELPER' not in output,output
            # Existing non-CLOEXEC descriptors remain valid after reducing
            # RLIMIT_NOFILE; the updater must still exclude them from children.
            if not windows_host():
                for bundled,item in [(False,raw),(True,old)]:
                    root=lab/(prefix+'descriptor'+str(bundled));root.mkdir(mode=0o700)
                    assert invoke(root,item)==['ACTIVATED']
                    output=invoke(root,item,'descriptor')
                    assert 'OWNED-HELPER' in output and 'LEAKED:0' in output,output
            # Every new bundle publication phase preserves an old complete
            # generation or exposes exactly one complete new generation.
            for point in ['bundle-entry-written','bundle-before-replace','bundle-after-replace',
                          'receipt-after-replace','state-before-replace','state-after-replace']:
                root=lab/(prefix+point);root.mkdir(mode=0o700)
                assert invoke(root,old)==['ACTIVATED']
                invoke(root,new,fault=point,expected=87)
                active=new if point=='state-after-replace' else old
                assert (root/'state').read_bytes()==(active[0]/'state').read_bytes(),point
                assert 'OWNED-HELPER' in invoke(root,active,'launch'),point
                assert invoke(root,new)==['ACTIVATED'],point
                assert 'RESOURCE:new signed resource' in invoke(root,new,'launch'),point
            # A real second process cannot replace the journal while the first
            # owns the installation lock.
            root=lab/(prefix+'lock');root.mkdir(mode=0o700)
            assert invoke(root,old)==['ACTIVATED']
            folder,digest,hash=old
            process=subprocess.Popen([str(binary),str(root),str(folder/'artifact'),str(folder/'receipt'),
                digest,hash,str(folder/'state'),'hold','',''],stdout=subprocess.PIPE,text=True,env=env)
            assert process.stdout.readline().strip()=='LOCKED'
            before=(root/'state').read_bytes()
            assert invoke(root,new)[0]=='ERROR'
            assert (root/'state').read_bytes()==before
            assert process.wait(timeout=5)==0
            if not windows_host():
                actual=lab/(prefix+'real');actual.mkdir(mode=0o700)
                linked=lab/(prefix+'linked');linked.symlink_to(actual,target_is_directory=True)
                assert invoke(linked,old)[0]=='ERROR'
                parent=lab/(prefix+'alias');parent.symlink_to(lab,target_is_directory=True)
                assert invoke(parent/actual.name,old)[0]=='ERROR'
        if os.environ.get('MINYAR_UPDATE_EVIDENCE'):
            shutil.copytree(lab,Path(os.environ['MINYAR_UPDATE_EVIDENCE'])/'native-launch-fixtures',dirs_exist_ok=True,symlinks=True)
        print('Checked OS execution, exclusive writers, every bundle death boundary, deterministic TOCTOU races and cleanup passed')

if __name__=='__main__':main()
