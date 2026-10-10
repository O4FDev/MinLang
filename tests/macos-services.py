#!/usr/bin/env python3
"""Real AppKit status-item lifetimes, with native and instrumented execution."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if sys.platform != 'darwin':
    raise SystemExit('this mandatory macOS gate requires AppKit')
with tempfile.TemporaryDirectory(prefix='macos-services-', dir=ROOT/'build') as directory:
    temp = Path(directory)
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    for sanitized in (False, True):
        flags = ['-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer'] if sanitized else ['-O2']
        runtime = temp/'runtime.o'
        subprocess.run([clang,*flags,'-DMINYAR_SYSTEM_HEAP=1','-c',str(ROOT/'runtime/minyar_runtime.c'),'-o',str(runtime)],check=True)
        executable = temp/('sanitize' if sanitized else 'native')
        subprocess.run([clang,'-fobjc-arc','-fmodules','-Wall','-Wextra','-Werror',*flags,
                        str(ROOT/'tests/macos-services.m'),str(runtime),'-framework','AppKit','-o',str(executable)],check=True)
        subprocess.run([executable],check=True,timeout=30,
                       env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0',UBSAN_OPTIONS='halt_on_error=1'))
    source = temp/'keychain-probe.min'
    source.write_text('''use "keychain" as keychain
use "errors" as errors
let result = keychain.findIdentity("missing identity", argument(0))
print(!keychain.found(result))
print(errors.isError(keychain.lookupError(result)))
''')
    program = temp/'probe'
    compiled = subprocess.run([ROOT/'minyar',source,'-o',program],capture_output=True,text=True)
    assert compiled.returncode == 0, compiled.stderr
    result = subprocess.run([program,temp/'missing.keychain-db'],check=True,capture_output=True,text=True,timeout=15)
    assert result.stdout == 'true\ntrue\n', result
