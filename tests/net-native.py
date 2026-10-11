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

ROOT = Path(__file__).resolve().parents[1]
CLANG = os.environ.get('MINYAR_TEST_CLANG', 'clang')
WINDOWS = windows_host()


def selected_modes(parser, mode):
    if WINDOWS and mode == 'sanitize':
        parser.error('native network sanitizer mode is unavailable on Windows')
    return [mode] if mode else (['native'] if WINDOWS else ['native', 'sanitize'])



def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def attempt(errors, label, action):
    try:
        return action()
    except Exception as error:
        errors.append({'operation': label, 'error': type(error).__name__ + ': ' + str(error)})
        return None


def captured_run(directory, records, errors, command, *, phase, **kwargs):
    command = [str(argument) for argument in command]
    capture = kwargs.pop('capture_output', False)
    text = kwargs.pop('text', False)
    check = kwargs.pop('check', False)
    environment = kwargs.get('env', os.environ)
    tool = shutil.which(command[0], path=environment.get('PATH'))
    if tool is None and Path(command[0]).is_file():
        tool = str(Path(command[0]).resolve())
    row = {'argv': command, 'phase': phase,
           'cwd': str(Path(kwargs.get('cwd', Path.cwd())).resolve()),
           'tool': tool, 'tool_sha256': digest(tool) if tool else None,
           'environment': {name: environment[name] for name in
                           ('ASAN_OPTIONS', 'UBSAN_OPTIONS', 'MINYAR_TEST_CLANG')
                           if name in environment}}
    records.append(row)
    start = time.monotonic()
    primary = None
    out, err = b'', b''
    try:
        result = subprocess.run(command, capture_output=True, **kwargs)
        row['status'] = result.returncode
        out, err = result.stdout, result.stderr
        if check:
            result.check_returncode()
    except BaseException as error:
        primary = error
        row['exception'] = type(error).__name__ + ': ' + str(error)
        if isinstance(error, subprocess.TimeoutExpired):
            row['timed_out'] = True
            out, err = error.stdout or b'', error.stderr or b''
    finally:
        row['elapsed_seconds'] = time.monotonic() - start
        for stream, data in (('stdout', out), ('stderr', err)):
            path = directory/f'{len(records):02d}-{phase}.{stream}'
            attempt(errors, stream+' write', lambda path=path, data=data: path.write_bytes(data))
            fingerprint = attempt(errors, stream+' hash', lambda path=path: digest(path))
            row[stream] = {'path': path.name, 'sha256': fingerprint, 'bytes': len(data)}
        if tool:
            row['tool_after_sha256'] = attempt(errors, 'tool after hash', lambda: digest(tool))
            if row['tool_after_sha256'] != row['tool_sha256']:
                errors.append({'operation': 'tool binding', 'error': 'command executable changed'})
        if not capture:
            attempt(errors, 'stdout forward', lambda: sys.stdout.buffer.write(out))
            attempt(errors, 'stderr forward', lambda: sys.stderr.buffer.write(err))
    if primary is not None:
        raise primary
    if errors:
        raise RuntimeError('network evidence capture failed: ' + json.dumps(errors))
    if text:
        result.stdout = result.stdout.decode().replace('\r\n', '\n').replace('\r', '\n')
        result.stderr = result.stderr.decode().replace('\r\n', '\n').replace('\r', '\n')
    return result


def finalize_evidence(directory, inputs, records, errors, modes, status, primary=None):
    after = {}
    for name, expected in inputs.items():
        after[name] = attempt(errors, 'input after hash: '+name, lambda name=name: digest(ROOT/name))
        if after[name] != expected:
            errors.append({'operation': 'input binding', 'error': 'source input changed: '+name})
    files = {}
    paths = attempt(errors, 'artifact listing', lambda: sorted(directory.iterdir())) or []
    for path in paths:
        if attempt(errors, 'artifact classification: '+path.name,
                   lambda path=path: path.is_file() and not path.is_symlink()):
            files[path.name] = attempt(errors, 'artifact hash: '+path.name, lambda path=path: digest(path))
    report = {'schema_version': 1, 'status': 'failed' if errors or primary else status,
              'modes': modes, 'public_program_sanitized': False,
              'windows_sanitizer_capability': False, 'inputs': inputs,
              'inputs_after': after, 'commands': records, 'files': files,
              'primary_error': None if primary is None else type(primary).__name__+': '+str(primary),
              'evidence_errors': errors}
    attempt(errors, 'manifest write', lambda: (directory/'manifest.json').write_text(
        json.dumps(report, indent=2)+'\n'))
    if errors:
        # Outer raw stderr remains available even when this directory cannot be written.
        attempt(errors, 'finalization stderr', lambda: print(
            'Network evidence finalization errors: '+json.dumps(errors), file=sys.stderr))
        if primary is None:
            raise RuntimeError('network evidence finalization failed')


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
            sources = [Path(__file__), ROOT/'tests/clang_helpers.py',
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
            # This public program was ordinary code in the original combined suite.
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
