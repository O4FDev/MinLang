#!/usr/bin/env python3
"""Fetch or build the pinned baseline or experimental native Minyar compiler.

Builds are local to --root; this command does not install into Xcode. The
baseline has no Minyar parser modifications. See docs/native-frontend.md.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def apply_native_patches(workspace):
    patch_root = ROOT / 'toolchains/native-swift/patches'
    patches = {'swift': ['swift-parser.patch', 'swift-macros.patch'],
               'swift-syntax': ['swift-syntax.patch']}
    identity = {name: hashlib.sha256((patch_root / name).read_bytes()).hexdigest()
                for names in patches.values() for name in names}
    marker = workspace / '.minyar-patches.json'
    if marker.exists():
        if json.loads(marker.read_text()) != identity:
            raise ValueError('native patches changed; use a fresh --root or reconcile the existing source tree manually')
        for repository, names in patches.items():
            subprocess.run(['git', '-C', str(workspace / repository), 'apply', '--reverse', '--check',
                            *[str(patch_root / name) for name in names]], check=True)
        return
    # Check every source tree and patch before changing any checkout.
    for repository, names in patches.items():
        source = workspace / repository
        status = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True)
        if status:
            raise ValueError(f'native patch installation requires clean sources: {source}')
        subprocess.run(['git', '-C', str(source), 'apply', '--check',
                        *[str(patch_root / name) for name in names]], check=True)
    for repository, names in patches.items():
        subprocess.run(['git', '-C', str(workspace / repository), 'apply',
                        *[str(patch_root / name) for name in names]], check=True)
    marker.write_text(json.dumps(identity, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['fetch', 'baseline', 'native'])
    parser.add_argument('--root', type=Path, default=ROOT / 'build/native-toolchain')
    parser.add_argument('--jobs', type=int, default=3)
    args = parser.parse_args()
    if sys.platform not in ('darwin', 'linux'):
        parser.error('native compiler builds currently require macOS or Linux')
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    workspace = args.root.resolve()
    if any(c.isspace() for c in str(workspace)):
        parser.error('the upstream compiler build requires a path without spaces')
    workspace.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / 'toolchains/native-swift/sources.json').read_text())
    try:
        # An advisory lock is released by the OS if the process is terminated.
        with (workspace / '.minyar-build-lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError(f'another toolchain operation owns {workspace}') from None
            for name, repo in manifest['repositories'].items():
                source = workspace / name
                if not source.exists():
                    subprocess.run(['git', 'clone', '--depth', '1', '--single-branch',
                                    '--branch', manifest['tag'], repo['url'], str(source)], check=True)
                actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
                if actual != repo['revision']:
                    raise ValueError(f'{source}: expected {repo["revision"]}, found {actual}; no checkout was changed')
            if args.action == 'fetch':
                print(f'pinned sources verified in {workspace}')
                return
            if args.action == 'baseline':
                for name in manifest['repositories']:
                    changed = subprocess.check_output(['git', '-C', str(workspace / name),
                                                       'status', '--porcelain', '--untracked-files=no'], text=True)
                    if changed:
                        raise ValueError(f'baseline requires unmodified sources: {workspace / name}')
            free_gib = shutil.disk_usage(workspace).free / 1024**3
            print(f'Available storage: {free_gib:.1f} GiB; build jobs: {args.jobs}', flush=True)
            if free_gib < 40:
                raise ValueError('less than 40 GiB available for the compiler build; select a larger --root volume')
            architecture = subprocess.check_output(['uname', '-m'], text=True).strip()
            if architecture not in ('arm64', 'aarch64', 'x86_64'):
                raise ValueError(f'unsupported host architecture: {architecture}')
            if args.action == 'native':
                apply_native_patches(workspace)
            command = [sys.executable, 'utils/build-script', '--release', '--reconfigure',
                       '--skip-early-swift-driver', '--skip-build-benchmarks',
                       '--skip-build-osx', '--skip-build-ios', '--skip-build-tvos',
                       '--skip-build-watchos', '--skip-build-xros', '--skip-build-lld',
                       '--skip-build-clang-tools-extra', '--skip-build-compiler-rt',
                       '--no-llvm-include-tests',
                       '--llvm-targets-to-build', 'X86' if architecture == 'x86_64' else 'AArch64',
                       '--bootstrapping', 'hosttools', '--jobs', str(args.jobs),
                       '--extra-cmake-options=-DCMAKE_POLICY_VERSION_MINIMUM=3.5 '
                       '-DSWIFT_BUILD_REGEX_PARSER_IN_COMPILER:BOOL=TRUE '
                       '-DSWIFT_BUILD_STDLIB_EXTRA_TOOLCHAIN_CONTENT:BOOL=FALSE '
                       '-DSWIFT_BUILD_STDLIB_CXX_MODULE:BOOL=FALSE']
            if sys.platform == 'darwin':
                # Apple SDKs supply the target runtime and overlays.
                command += ['--swift-darwin-supported-archs', architecture,
                            '--build-swift-dynamic-stdlib=false', '--build-swift-static-stdlib=false',
                            '--build-swift-dynamic-sdk-overlay=false', '--build-swift-static-sdk-overlay=false',
                            '--build-swift-libexec=false']
            else:
                # Linux needs matching target runtime/modules from this source
                # revision, not modules from the bootstrap compiler package.
                command += ['--use-linker=lld', '--build-swift-static-stdlib=false']
            # Keep the same working Python interpreter in upstream subprocesses.
            env = dict(os.environ)
            env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + env.get('PATH', '')
            # LLVM invokes nested CMake builds for host TableGen tools.
            env['CMAKE_BUILD_PARALLEL_LEVEL'] = str(args.jobs)
            subprocess.run(command, cwd=workspace / 'swift', env=env, check=True)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'native toolchain: {error}\n')


if __name__ == '__main__':
    main()
