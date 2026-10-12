#!/usr/bin/env python3
"""Files-only controls, each with a bounded process and platform-selected native backend."""
import argparse
import os
from pathlib import Path
import platform
import shlex
import subprocess
import tempfile
from clang_helpers import asan_leak_options, clang_command, windows_host
from llvm_sanitizer import instrument_address_sanitizer

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    'files-ranges': ['huge', 'invalid', 'pseudo', 'large', 'eof', 'partial-error', 'read-file'],
    'files-prepare': ['preallocate', 'stale', 'active-close', 'saturated', 'write-error', 'short', 'stop',
                      'sync-error', 'allocate-error', 'zero-write', 'capacity', 'cross-kind',
                      'sparse-tail', 'sparse-middle', 'fresh-preallocate', 'fresh-prepare',
                      'dense-extension', 'truncate-error', 'prefix-write-error',
                      'clone-prefix',
                      *[f'setup-fd-{i}' for i in range(1, 11)],
                      'setup-pair', 'setup-mutex', 'setup-condition', 'setup-create'],
}


def run(command, environment, cwd=ROOT, expected=None, timeout=60):
    print(shlex.join(map(str, command)), flush=True)
    result = subprocess.run(command, cwd=cwd, env=environment, capture_output=True, timeout=timeout)
    if result.returncode:
        print(result.stdout.decode(errors='replace'), end='', flush=True)
        print(result.stderr.decode(errors='replace'), end='', flush=True)
        result.check_returncode()
    if expected is not None:
        assert (result.stdout, result.stderr) == expected, (command, result.stdout, result.stderr)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--native-only', action='store_true')
    options = parser.parse_args()
    windows = windows_host()
    if windows:
        parser.error('Windows files backend is pending; this POSIX chunk cannot qualify Windows')
    cases = {key: list(value) for key, value in CASES.items()}
    if platform.system() == 'Linux':
        cases['files-ranges'].append('procfs')
        cases['files-prepare'] += ['unshare-supported', 'unshare-error', 'unshare-unsupported',
                                  'unshare-stat-error', 'unshare-fresh', 'unshare-tmpfs']
    if platform.system() == 'Darwin':
        cases['files-prepare'] += ['sharing-query-error', 'sharing-query-missing']
    clang = os.environ.get('MINYAR_TEST_CLANG', os.environ.get('MINYAR_CLANG', 'clang'))
    environment = dict(os.environ, ASAN_OPTIONS=asan_leak_options()+':halt_on_error=1',
                       UBSAN_OPTIONS='halt_on_error=1')
    configurations = [['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']] if options.sanitize else [
        ['-O0'], ['-O2']]
    checks = 0
    test_root = Path(os.environ.get('TMPDIR', ROOT/'build/files-tests')).resolve()
    test_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='minyar-files-focused-', dir=test_root) as directory:
        directory = Path(directory)
        environment['TMPDIR'] = str(directory)
        for fixture, selected in cases.items():
            for index, flags in enumerate(configurations):
                exe = directory/(fixture+str(index)+('.exe' if windows else ''))
                command = clang_command([clang, '-std=c11', '-D_GNU_SOURCE', '-DMINYAR_SYSTEM_HEAP=1',
                    '-Wall', '-Wextra', '-Werror', *flags, ROOT/'tests'/(fixture+'.c'),
                    ROOT/'runtime/minyar_runtime.c', *(['-lws2_32'] if windows else ['-pthread']), '-o', exe])
                run(command, environment)
                for case in selected:
                    result = run([exe, case], environment, timeout=10)
                    if result.stdout:
                        print(result.stdout.decode(errors='replace'), end='', flush=True)
                    checks += 1
                    print(f'{fixture} {flags[0]} {case}: passed', flush=True)
        if not options.native_only:
            for fixture, expected in [('files-eventloop', b'files-eventloop: ok\n'),
                                      ('files-r2', b'files-r2: ok\nfiles-r2: rmdir and releaseFreeMemory ok\n')]:
                llvm = directory/(fixture+'.ll')
                run([ROOT/'build/minyarc', ROOT/'tests'/(fixture+'.min'), llvm,
                     '--bounded-owners', '32', '--library', ROOT/'library'], environment)
                if options.sanitize:
                    llvm.write_text(instrument_address_sanitizer(llvm.read_text()))
                for index, flags in enumerate(configurations):
                    exe = directory/(fixture+str(index)+('.exe' if windows else ''))
                    command = clang_command([clang, *flags, '-Wno-override-module', '-DMINYAR_SYSTEM_HEAP=1',
                        llvm, ROOT/'runtime/minyar_default_runtime.c', ROOT/'runtime/native/files.c',
                        ROOT/'runtime/native/net.c', ROOT/'runtime/native/system.c', *(['-lws2_32'] if windows else ['-pthread']), '-o', exe])
                    run(command, environment)
                    run([exe], environment, cwd=directory, expected=(expected, b''), timeout=20)
                    checks += 1
    print(f'{checks} files {"sanitizer" if options.sanitize else "native"} controls passed', flush=True)


if __name__ == '__main__':
    main()
