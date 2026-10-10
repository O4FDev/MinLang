#!/usr/bin/env python3
"""Real native crypto, locks, persistence, and abrupt-process-death recovery."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from clang_helpers import windows_host

ROOT=Path(__file__).resolve().parents[1]

def main():
    clang=os.environ.get('MINYAR_TEST_CLANG','clang')
    with tempfile.TemporaryDirectory(prefix='minyar-native-update-') as directory:
        root=Path(directory)
        for sanitize in ([False] if os.name=='nt' else [False,True]):
            binary=root/('probe-sanitize' if sanitize else 'probe')
            if windows_host(): binary=binary.with_suffix('.exe')
            flags=['-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer'] if sanitize else ['-O2']
            command=[clang,'-std=c11','-D_GNU_SOURCE','-DMINYAR_SYSTEM_HEAP=1','-DMINYAR_UPDATE_TEST_HOOK=1',
                '-Wall','-Wextra','-Werror',*flags,*[str(ROOT/path) for path in ['tests/update-native.c',
                'runtime/native/update.c','runtime/native/update_monocypher.c','runtime/native/update_ed25519.c',
                'runtime/minyar_runtime.c']],'-lm','-o',str(binary)]
            subprocess.run(command,check=True)
            env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1' if sys.platform.startswith('linux') else 'detect_leaks=0')
            installed=root/('state-sanitize' if sanitize else 'state');installed.mkdir(mode=0o700)
            subprocess.run([str(binary),str(installed)],env=env,check=True,timeout=30)
            for point in ['artifact-before-replace','artifact-after-replace','state-before-replace','state-after-replace']:
                target=root/(point+('-sanitize' if sanitize else ''));target.mkdir(mode=0o700)
                crashed=subprocess.run([str(binary),str(target),point],env=env,timeout=30)
                assert crashed.returncode==87,(point,crashed.returncode)
                expected=b'new' if point=='state-after-replace' else b'old'
                recovered=subprocess.check_output([str(binary),str(target),'reopen'],env=env,timeout=30)
                assert recovered==expected,(point,recovered)
                suffix='.exe' if windows_host() else '.bin'
                assert (target/'versions'/('a'*64+suffix)).read_bytes()==b'old'
        print('All publication transitions survive abrupt exit; OS releases updater locks')

if __name__=='__main__': main()
