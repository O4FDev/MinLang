"""Retain network harness commands without hiding their primary failure."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

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
                           ('ASAN_OPTIONS', 'UBSAN_OPTIONS', 'MINYAR_TEST_CLANG',
                            'MINYAR_CLANG_FLAGS', 'MINYAR_NATIVE_FLAGS', 'MINYAR_RUNTIME_FLAGS')
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


def finalize_evidence(directory, inputs, records, errors, modes, status, primary=None, *, root):
    after = {}
    for name, expected in inputs.items():
        after[name] = attempt(errors, 'input after hash: '+name, lambda name=name: digest(root/name))
        if after[name] != expected:
            errors.append({'operation': 'input binding', 'error': 'source input changed: '+name})
    files = {}
    paths = attempt(errors, 'artifact listing', lambda: sorted(directory.iterdir())) or []
    for path in paths:
        if attempt(errors, 'artifact classification: '+path.name,
                   lambda path=path: path.is_file() and not path.is_symlink()):
            files[path.name] = attempt(errors, 'artifact hash: '+path.name, lambda path=path: digest(path))
    report = {'schema_version': 1, 'status': 'failed' if errors or primary else status,
              'modes': modes, 'public_program_sanitizer_enabled_by_suite': False,
              'public_program_scope': 'ordinary-launcher-path' if any(mode.endswith('native') for mode in modes) else None,
              'windows_sanitizer_enabled_by_suite': False, 'inputs': inputs,
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


