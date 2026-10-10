#!/usr/bin/env python3
"""macOS desktop integration, including real target/action and bundle launching."""
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def run(args, *, ok=True, env=None):
    result = subprocess.run([str(x) for x in args], cwd=ROOT, text=True,
                            capture_output=True, timeout=600, env=env)
    if ok and result.returncode:
        raise AssertionError(f'{args}\n{result.stdout}\n{result.stderr}')
    if not ok:
        assert result.returncode != 0, args
    return result

if sys.platform != 'darwin':
    print('macOS desktop tests skipped: requires macOS with a GUI session')
    sys.exit(0)

print(run([sys.executable,ROOT/'tests/macos-packaging.py']).stdout.strip(),flush=True)
run(['make','-s','build/minyarc','build/minyar-default-runtime.o'])
with tempfile.TemporaryDirectory(prefix='macos-test-',dir=ROOT/'build') as directory:
    temp = Path(directory)
    probe = temp / 'swift-appkit.ll'
    run(['xcrun','swiftc','-parse-as-library','-emit-ir','-Onone',ROOT/'tests/macos-swift-probe.swift','-o',probe])
    ir = probe.read_text()
    for symbol in ['objc_msgSend','initWithContentRect:styleMask:backing:defer:',
                   'setTitle:', 'buttonWithTitle:target:action:', 'addSubview:']:
        assert symbol in ir, symbol
    print('Swift-to-AppKit selector lowering verified',flush=True)
    for sanitized in [False, True]:
        harness = temp / ('native-sanitize' if sanitized else 'native')
        flags = ['-fsanitize=address,undefined','-fno-omit-frame-pointer'] if sanitized else []
        runtime = temp / 'runtime.o'
        run(['clang','-O1',*flags,'-c',ROOT/'runtime/minyar_default_runtime.c','-o',runtime])
        run(['clang','-fobjc-arc','-fmodules','-Wall','-Wextra','-Werror','-O1',*flags,
             ROOT/'tests/macos-native.m',runtime,'-framework','AppKit','-o',harness])
        env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0')
        print(run([harness],env=env).stdout.strip(),flush=True)
        for mode, message in [('stale','invalid or destroyed'),('wrong-type','requires a checkbox'),
                              ('range','outside its range'),('timeout','event timeout'),
                              ('parent','parent must be'),('duplicate-init','only be called once'),
                              ('dimension','dimensions'),('thread','main thread'),('overflow','event queue is full'),
                              ('uninitialized','call macos.initialize'),
                              ('hover','requires a button, row, or column'),('shape','shape paths support'),
                              ('color','0xRRGGBB'),('list-line','list lines are 0'),('list-type','wrong object type')]:
            result = run([harness,mode],ok=False,env=env)
            assert result.returncode == 1 and message in result.stderr, result
            assert 'ERROR: AddressSanitizer' not in result.stderr and 'runtime error:' not in result.stderr
    # The real Minyar app uses returned Text ownership and bool/integer/float ABI.
    app = temp / 'Minyar Notes & Unicode é.app'
    for flags in [[],['--release'],['--memory-profile','eager'],['--memory-profile','fixed'],['--memory-profile','lazy']]:
        run([ROOT/'minyar',*flags,'--app','--bundle-id','org.minyar.desktop-test',
             ROOT/'examples/macos/main.min','-o',app])
        info = plistlib.loads((app/'Contents/Info.plist').read_bytes())
        assert info['CFBundleIdentifier'] == 'org.minyar.desktop-test'
        assert info['CFBundleName'] == app.stem
        assert info['CFBundlePackageType'] == 'APPL'
        binary = app / 'Contents/MacOS' / info['CFBundleExecutable']
        result = run([binary,'--smoke'])
        assert result.stdout == 'Minyar → AppKit 🙂\n',result
        assert 'Unable to simultaneously satisfy constraints' not in result.stderr,result.stderr
        run(['codesign','--verify','--strict',app])
        contract = temp / 'language-contract'
        run([ROOT/'minyar',*flags,ROOT/'tests/macos-contract.min','-o',contract])
        assert run([contract]).stdout == 'Minyar desktop ABI and Text ownership verified\n'
        dependencies = run(['otool','-L',binary]).stdout
        assert 'AppKit.framework' in dependencies
        assert 'libswift' not in dependencies
        print(f"app and language ownership verified: {flags or ['debug']}",flush=True)
    # A bad ID cannot replace the previous successful build.
    before = (app/'Contents/Info.plist').read_bytes()
    result = run([sys.executable,ROOT/'scripts/macos-app.py','--binary',binary,
                  '--output',app,'--identifier','bad/id'],ok=False)
    assert 'bundle ID' in result.stderr and (app/'Contents/Info.plist').read_bytes() == before
    foreign = temp/'Unrelated.app'; foreign.mkdir(); (foreign/'keep').write_text('keep')
    result = run([sys.executable,ROOT/'scripts/macos-app.py','--binary',binary,
                  '--output',foreign,'--identifier','org.minyar.test'],ok=False)
    assert 'refusing to replace' in result.stderr and (foreign/'keep').read_text() == 'keep'
    print('debug/release and all memory profiles: Minyar app builds, Unicode, signatures and safe replacement verified')
print('macOS desktop integration passed')
