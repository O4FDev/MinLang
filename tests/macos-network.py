#!/usr/bin/env python3
"""Actual AppKit/kqueue integration, in native and ASan/UBSan builds."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if sys.platform != 'darwin':
    raise SystemExit('this mandatory macOS gate requires AppKit and kqueue')
(ROOT/'build').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='macos-network-', dir=ROOT/'build') as directory:
    temp = Path(directory)
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    for sanitized in (False, True):
        mode = 'sanitize' if sanitized else 'native'
        flags = ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if sanitized else ['-O2']
        runtime, net, executable = temp/(mode+'-runtime.o'), temp/(mode+'-net.o'), temp/mode
        subprocess.run([clang, *flags, '-DMINYAR_SYSTEM_HEAP=1', '-c',
                        ROOT/'runtime/minyar_runtime.c', '-o', runtime], check=True)
        subprocess.run([clang, '-std=c11', '-Wall', '-Wextra', '-Werror', *flags,
                        '-DMINYAR_APP_EVENT_LOOP=1', '-c', ROOT/'runtime/native/net.c', '-o', net], check=True)
        subprocess.run([clang, '-fobjc-arc', '-fmodules', '-Wall', '-Wextra', '-Werror', *flags,
                        '-DMINYAR_APP_EVENT_LOOP=1', ROOT/'tests/macos-network.m', runtime, net,
                        '-framework', 'AppKit', '-o', executable], check=True)
        subprocess.run([executable], check=True, timeout=30,
                       env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0', UBSAN_OPTIONS='halt_on_error=1'))
    # The public launcher must select matching desktop/reactor cache variants;
    # direct native tests alone cannot detect a missing compile-time adapter.
    source = temp/'contract.min'
    source.write_text('''use "macos" as macos
use "eventloop" as loop
use "errors" as errors
macos.initialize("shared loop contract")
macos.accessory(true)
let reactor = errors.integerValue(loop.create())
let shared = macos.shareNetworkLoop(reactor)
print(errors.integerOk(shared))
let timer = errors.integerValue(loop.timer(reactor, 10, 0, 77))
macos.nextEvent(0.5)
let batch = loop.wait(reactor, 0, 16)
print(!errors.isError(loop.batchError(batch)))
print(loop.events(batch).length == 1)
print(loop.events(batch)[0].token == 77)
print(errors.booleanOk(loop.close(reactor)))
''')
    for mode in ['--debug', '--release']:
        executable = temp/('contract-'+mode[2:])
        subprocess.run([ROOT/'minyar', mode, source, '-o', executable], check=True, timeout=120)
        result = subprocess.run([executable], check=True, capture_output=True, text=True, timeout=15)
        assert result.stdout == 'true\ntrue\ntrue\ntrue\ntrue\n', result
