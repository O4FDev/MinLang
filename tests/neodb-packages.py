#!/usr/bin/env python3
"""Qualify imported files/system and portable net additions with bounded runs."""
import argparse
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import tempfile

from clang_helpers import asan_leak_options, clang_command, launcher_command, windows_host

ROOT = Path(__file__).resolve().parents[1]


def run(command, environment, expected=None, timeout=180):
    print(shlex.join(map(str, command)), flush=True)
    result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, timeout=timeout)
    if result.returncode or (expected is not None and (result.stdout, result.stderr) != expected):
        raise AssertionError((command, result.returncode, result.stdout, result.stderr))
    print(f'exit {result.returncode}: {result.stdout.decode().strip()}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=('files-system', 'net-additions', 'all'), default='all')
    parser.add_argument('--mode', choices=('native', 'sanitize'), default='native')
    parser.add_argument('--native-only', action='store_true')
    options = parser.parse_args()
    if windows_host() and options.suite != 'net-additions':
        parser.error('files/system are not implemented on Windows')
    if windows_host() and options.mode == 'sanitize':
        parser.error('this suite does not qualify Windows sanitizer builds')
    suites = ['files-system', 'net-additions'] if options.suite == 'all' else [options.suite]
    clang = os.environ.get('MINYAR_TEST_CLANG', os.environ.get('MINYAR_CLANG', 'clang'))
    environment = dict(os.environ, MINYAR_CLANG=clang, ASAN_OPTIONS=asan_leak_options()+':halt_on_error=1',
                       UBSAN_OPTIONS='halt_on_error=1')
    flags = ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    configurations = [flags] if options.mode == 'sanitize' else [['-O0'], ['-O2']]
    with tempfile.TemporaryDirectory(prefix='minyar-neodb-packages-') as temporary:
        directory = Path(temporary)
        for suite in suites:
            fixture = 'files-sync-failures' if suite == 'files-system' else 'net-resolver-errors'
            for index, selected in enumerate(configurations):
                output = directory / (f'{fixture}-{index}' + ('.exe' if windows_host() else ''))
                command = [clang, '-std=c11', '-D_GNU_SOURCE', '-DMINYAR_SYSTEM_HEAP=1',
                           '-Wall', '-Wextra', '-Werror', *selected, ROOT / 'tests' / (fixture + '.c')]
                if suite == 'net-additions':
                    command += [ROOT / 'runtime/minyar_runtime.c']
                    if windows_host():
                        command += ['-lws2_32']
                else:
                    command += ['-pthread']
                command += ['-o', output]
                run(clang_command(command), environment)
                run([output], environment, timeout=10)
            if options.native_only:
                continue
            if options.mode == 'sanitize':
                for name in ('MINYAR_CLANG_FLAGS', 'MINYAR_NATIVE_FLAGS', 'MINYAR_RUNTIME_FLAGS'):
                    environment[name] = shlex.join([*flags, '-Wno-override-module'])
            for optimization in ('--debug', '--release'):
                output = directory / (suite + ('.exe' if windows_host() else ''))
                program_environment = environment.copy()
                if optimization == '--release' and platform.system() == 'Linux':
                    # Keep ELF LLD worker stacks within the existing 768 MiB
                    # development limit, as the launcher does for bootstrap.
                    link_flags = shlex.split(environment.get('MINYAR_CLANG_FLAGS', '-O2 -Wno-override-module'))
                    linker = next((option.split('=', 1)[1] for option in link_flags
                                   if option.startswith(('-fuse-ld=', '--ld-path='))), None)
                    sibling = Path(shutil.which(clang) or clang).resolve().parent / 'ld.lld'
                    lld = Path(linker).name in ('lld', 'ld.lld') if linker else sibling.is_file() or shutil.which('ld.lld')
                    if lld and not any('--threads' in option for option in link_flags):
                        program_environment.setdefault('MINYAR_NATIVE_FLAGS', shlex.join(link_flags))
                        program_environment['MINYAR_CLANG_FLAGS'] = shlex.join([*link_flags, '-Wl,--threads=1'])
                run([*launcher_command(ROOT), optimization, ROOT / 'tests' / (suite + '.min'),
                     '-o', output], program_environment)
                expected = ((suite + ': ok\n').encode(),
                            b'net-additions: stderr ok\n' if suite == 'files-system' else b'')
                run([output], program_environment, expected, timeout=30)
    print(f'{options.suite} {options.mode}: all selected contracts passed')


if __name__ == '__main__':
    main()
