#!/usr/bin/env python3
"""Run actual loopback socket contracts against eager RC and ASan/UBSan."""
import argparse
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from clang_helpers import windows_host
from network_evidence import attempt, captured_run, digest, finalize_evidence as _shared_finalize

ROOT = Path(__file__).resolve().parents[1]
CLANG = os.environ.get('MINYAR_TEST_CLANG', 'clang')
WINDOWS = windows_host()


def selected_modes(parser, mode):
    if WINDOWS and mode == 'sanitize':
        parser.error('native network sanitizer mode is unavailable on Windows')
    return [mode] if mode else (['native'] if WINDOWS else ['native', 'sanitize'])



def finalize_evidence(directory, inputs, records, errors, modes, status, primary=None):
    return _shared_finalize(directory, inputs, records, errors, modes, status, primary, root=ROOT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('native', 'sanitize'))
    parser.add_argument('--evidence', type=Path)
    options = parser.parse_args()
    modes = selected_modes(parser, options.mode)
    (ROOT / 'build').mkdir(exist_ok=True)
    if options.evidence:
        directory = options.evidence.resolve()
        directory.mkdir(parents=True, exist_ok=True)
        if any(directory.iterdir()):
            parser.error('network evidence directory must be empty')
        workspace = nullcontext(str(directory))
    else:
        workspace = tempfile.TemporaryDirectory(prefix='net-native-', dir=ROOT / 'build')
    with workspace as directory:
        directory = Path(directory)
        records = []
        errors = []
        inputs = {}
        if options.evidence:
            sources = [Path(__file__), ROOT/'tests/network_evidence.py', ROOT/'tests/clang_helpers.py',
                       ROOT/'tests/net-native.c', ROOT/'tests/net-batch.c',
                       ROOT/'tests/net-contract.min', ROOT/'runtime/native/net.c',
                       ROOT/'runtime/minyar_runtime.c', ROOT/'minyar']
            sources.extend((ROOT/'runtime').rglob('*.h'))
            inputs = {str(path.relative_to(ROOT)): digest(path) for path in sources}

        def run(command, *, phase, **kwargs):
            if not options.evidence:
                return subprocess.run(command, **kwargs)
            return captured_run(directory, records, errors, command, phase=phase, **kwargs)

        status = 'failed'
        primary = None
        try:
            if options.evidence:
                run([CLANG, '--version'], phase='clang-version', check=True,
                    capture_output=True, timeout=10)
            for mode in modes:
                flags = ['-O2'] if mode == 'native' else [
                    '-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
                environment = os.environ.copy()
                environment['ASAN_OPTIONS'] = 'detect_leaks=1' if sys.platform.startswith('linux') else 'detect_leaks=0'
                for fixture in ('net-native', 'net-batch'):
                    executable = directory / (f'{fixture}-{mode}' + ('.exe' if WINDOWS else ''))
                    command = [CLANG, '-std=c11', '-D_GNU_SOURCE', '-DMINYAR_SYSTEM_HEAP=1',
                               '-Wall', '-Wextra', '-Werror', *flags,
                               str(ROOT / f'tests/{fixture}.c'), str(ROOT / 'runtime/native/net.c'),
                               str(ROOT / 'runtime/minyar_runtime.c'), '-lm', '-o', str(executable)]
                    if WINDOWS:
                        command += ['-lws2_32']
                    run(command, phase=f'{fixture}-{mode}-compile', check=True, cwd=ROOT)
                    run([executable], phase=f'{fixture}-{mode}-run', check=True,
                        env=environment, timeout=30)
            # Keep the original public launcher path and any caller-supplied flags;
            # this suite only selects sanitizer flags for the native C fixtures.
            if options.mode != 'sanitize':
                program = directory / ('net-contract.exe' if WINDOWS else 'net-contract')
                run([ROOT / 'minyar', ROOT / 'tests/net-contract.min', '-o', program],
                    phase='net-contract-compile', check=True, cwd=ROOT, capture_output=True)
                result = run([program], phase='net-contract-run', check=True,
                             capture_output=True, text=True, timeout=30)
                assert result.stdout == 'true\n' * 11, (result.stdout, result.stderr)
                print('Minyar network result contracts verified')
            else:
                print('Native network ASan/UBSan contracts verified')
            status = 'passed'
        except BaseException as error:
            primary = error
            raise
        finally:
            if options.evidence:
                finalize_evidence(directory, inputs, records, errors, modes, status, primary)



if __name__ == '__main__':
    main()
