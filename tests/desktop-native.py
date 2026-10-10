#!/usr/bin/env python3
"""Native desktop snapshots and adversarial asynchronous completion ordering."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if sys.platform != 'darwin':
    raise SystemExit('this macOS correctness gate requires Apple frameworks')

FRAMEWORKS = ['AppKit', 'UserNotifications', 'ServiceManagement', 'Network', 'IOKit']
with tempfile.TemporaryDirectory(prefix='desktop-native-', dir=ROOT/'build') as directory:
    temp = Path(directory)
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    for sanitized in (False, True):
        flags = ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if sanitized else ['-O2']
        runtime = temp/'runtime.o'
        subprocess.run([clang, *flags, '-DMINYAR_SYSTEM_HEAP=1', '-c', ROOT/'runtime/minyar_runtime.c', '-o', runtime], check=True)
        executable = temp/('sanitize' if sanitized else 'native')
        framework_flags = [item for name in FRAMEWORKS for item in ('-framework', name)]
        subprocess.run([clang, '-fobjc-arc', '-fmodules', '-Wall', '-Wextra', '-Werror', *flags,
                        ROOT/'tests/desktop-native.m', runtime, *framework_flags, '-o', executable], check=True)
        subprocess.run([executable], check=True, timeout=30,
                       env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0', UBSAN_OPTIONS='halt_on_error=1'))
    source = temp/'desktop-contract.min'
    source.write_text('''use "desktop" as desktop
use "errors" as errors
let login = desktop.launchAtLoginStatus()
print(!errors.integerOk(login))
print(errors.code(errors.integerError(login)) == errors.unavailableCode())
let notification = desktop.notify("test", "body")
print(!errors.integerOk(notification))
let stopped = desktop.networkStop()
print(errors.integerOk(stopped))
''')
    executable = temp/'contract'
    subprocess.run([ROOT/'minyar', source, '-o', executable], check=True, timeout=60)
    result = subprocess.run([executable], check=True, capture_output=True, text=True, timeout=15)
    assert result.stdout == 'true\ntrue\ntrue\ntrue\n', result
