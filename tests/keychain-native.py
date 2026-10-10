#!/usr/bin/env python3
"""Disposable-keychain signatures with real Security.framework and eager RC."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if sys.platform != 'darwin':
    raise SystemExit('this mandatory macOS gate requires Security.framework')
with tempfile.TemporaryDirectory(prefix='minyar-keychain-', dir=ROOT/'build') as directory:
    temp = Path(directory)
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
                    '-subj','/CN=Minyar key test','-keyout',str(temp/'key.pem'),
                    '-out',str(temp/'cert.pem')], check=True, capture_output=True)
    subprocess.run(['openssl','pkcs12','-export','-legacy','-name','Minyar key test',
                    '-in',str(temp/'cert.pem'),'-inkey',str(temp/'key.pem'),
                    '-passout','pass:minyar-test','-out',str(temp/'identity.p12')],
                   check=True, capture_output=True)
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    for sanitized in (False, True):
        mode = 'sanitize' if sanitized else 'native'
        flags = ['-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer'] if sanitized else ['-O2']
        executable = temp/mode
        subprocess.run([clang,'-std=c11','-Wall','-Wextra','-Werror',
                        '-DMINYAR_SYSTEM_HEAP=1',*flags,str(ROOT/'tests/keychain-native.c'),
                        str(ROOT/'runtime/native/keychain.c'),str(ROOT/'runtime/native/tlsverify.c'),
                        str(ROOT/'runtime/minyar_runtime.c'),'-framework','Security',
                        '-framework','CoreFoundation','-o',str(executable)],check=True)
        subprocess.run([executable,temp/'identity.p12',temp/(mode+'.keychain-db')],check=True,
                       timeout=30,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0',UBSAN_OPTIONS='halt_on_error=1'))
