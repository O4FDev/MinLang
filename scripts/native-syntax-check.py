#!/usr/bin/env python3
"""Build and check the experimental native Minyar SwiftSyntax parser.

Uses a separate source copy, leaving the pinned baseline compiler untouched.
Run scripts/native-toolchain.py fetch first. No Xcode installation is changed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(command, **kwargs):
    subprocess.run(list(map(str, command)), check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT / 'build/native-toolchain')
    args = parser.parse_args()
    workspace = args.root.resolve()
    source = workspace / 'swift-syntax'
    patch = ROOT / 'toolchains/native-swift/patches/swift-syntax.patch'
    manifest = json.loads((ROOT / 'toolchains/native-swift/sources.json').read_text())
    expected = manifest['repositories']['swift-syntax']['revision']
    actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != expected:
        parser.error('SwiftSyntax source revision differs from the pinned manifest')
    status = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True)
    if status:
        parser.error('SwiftSyntax baseline must be clean; no source copy was changed')
    digest = hashlib.sha256(patch.read_bytes()).hexdigest()
    work = workspace / 'syntax-check' / digest[:16]
    copied = work / 'source'
    build = work / 'build'
    marker = work / '.source-ready'
    if not marker.exists():
        if copied.exists():
            parser.error(f'incomplete source copy at {copied}; choose a fresh --root or inspect it manually')
        work.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, copied, ignore=shutil.ignore_patterns('.git'))
        run(['git', 'apply', '--check', patch], cwd=copied)
        run(['git', 'apply', patch], cwd=copied)
        marker.write_text(expected + '\n' + digest + '\n')
    if marker.read_text() != expected + '\n' + digest + '\n':
        parser.error(f'source provenance mismatch at {work}')
    swiftc = subprocess.check_output(['xcrun', '--find', 'swiftc'], text=True).strip()
    run(['cmake', '-G', 'Ninja', '-S', copied, '-B', build,
         '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_SHARED_LIBS=ON',
         '-DSWIFTSYNTAX_EMIT_MODULE=ON', f'-DCMAKE_Swift_COMPILER={swiftc}'])
    run(['cmake', '--build', build, '--target', 'SwiftParser', 'SwiftParserDiagnostics', '--parallel', '1'])
    host = build / 'lib/swift/host'
    executable = work / 'syntax-check'
    run([swiftc, ROOT / 'tests/native-swift/syntax.swift', '-I', host, '-L', host,
         '-lSwiftParser', '-lSwiftSyntax', '-lSwiftParserDiagnostics', '-lSwiftDiagnostics',
         '-Xlinker', '-rpath', '-Xlinker', host, '-o', executable])
    run([executable, ROOT / 'examples/swiftui/main.min', ROOT / 'tests/swiftui-features.min',
         ROOT / 'examples/swiftui-library/widgets.min', ROOT / 'tests/native-swift/syntax.min'])


if __name__ == '__main__':
    try:
        main()
    except (OSError, subprocess.CalledProcessError) as error:
        sys.exit(f'native syntax check: {error}')
