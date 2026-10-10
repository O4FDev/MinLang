#!/usr/bin/env python3
"""Disposable-keychain signatures with real Security.framework and eager RC."""
import os
from contextlib import ExitStack
from pathlib import Path
import subprocess
import sys
import tempfile
from os_tls_fixture import Peer

ROOT = Path(__file__).resolve().parents[1]
if sys.platform != 'darwin':
    raise SystemExit('this mandatory macOS gate requires Security.framework')
with tempfile.TemporaryDirectory(prefix='minyar-keychain-', dir=ROOT/'build') as directory, ExitStack() as cleanup:
    temp = Path(directory)
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
                    '-subj','/CN=Minyar key test','-keyout',str(temp/'key.pem'),
                    '-out',str(temp/'cert.pem')], check=True, capture_output=True)
    subprocess.run(['openssl','pkcs12','-export','-legacy','-name','Minyar key test',
                    '-in',str(temp/'cert.pem'),'-inkey',str(temp/'key.pem'),
                    '-passout','pass:minyar-test','-out',str(temp/'identity.p12')],
                   check=True, capture_output=True)
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    peer = Peer(temp, temp/'cert.pem') if os.environ.get('GITHUB_ACTIONS') == 'true' else None
    if peer:
        cleanup.callback(peer.close)
    def execute(executable, keychain, *, rejected=False):
        environment=dict(os.environ,ASAN_OPTIONS='detect_leaks=0',UBSAN_OPTIONS='halt_on_error=1')
        if peer:
            environment['MINYAR_TEST_OS_TLS_URL']=peer.url
            environment['MINYAR_TEST_OS_TLS_REDIRECT']=peer.url+'redirect'
        if rejected:
            environment['MINYAR_TEST_OS_TLS_REJECT']='1'
        subprocess.run([executable,temp/'identity.p12',keychain],check=True,timeout=30,env=environment)
    for sanitized in (False, True):
        mode = 'sanitize' if sanitized else 'native'
        flags = ['-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer'] if sanitized else ['-O2']
        executable = temp/mode
        runtime=temp/(mode+'-runtime.o')
        objc=temp/(mode+'-http.o')
        subprocess.run([clang,*flags,'-DMINYAR_SYSTEM_HEAP=1','-c',
                        ROOT/'runtime/minyar_runtime.c','-o',runtime],check=True)
        subprocess.run([clang,'-fobjc-arc','-fmodules','-Wall','-Wextra','-Werror',*flags,
                        '-c',ROOT/'tests/http-identity-native.m','-o',objc],check=True)
        subprocess.run([clang,'-std=c11','-Wall','-Wextra','-Werror',
                        '-DMINYAR_SYSTEM_HEAP=1','-DMINYAR_TEST_HTTP=1',*flags,str(ROOT/'tests/keychain-native.c'),
                        str(ROOT/'runtime/native/keychain.c'),str(ROOT/'runtime/native/tlsverify.c'),
                        runtime,objc,'-framework','Security','-framework','AppKit',
                        '-framework','CoreFoundation','-o',str(executable)],check=True)
        if peer:
            execute(executable,temp/(mode+'-untrusted.keychain-db'),rejected=True)
            before=peer.accepted
            with peer.trusted():
                execute(executable,temp/(mode+'.keychain-db'))
            assert peer.accepted==before+2 and peer.spied==0, (peer.accepted,peer.spied)
        else:
            execute(executable,temp/(mode+'.keychain-db'))
