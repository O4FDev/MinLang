"""Retain failing test workspaces and exact subprocess observations for replay."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_STDIN = object()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Evidence:
    def __init__(self, label, *, inputs=(), controls=None):
        if sys.flags.optimize:
            raise RuntimeError('Test evidence requires Python assertions; do not use -O')
        base = Path(os.environ.get('MINYAR_TEST_EVIDENCE', ROOT / 'build/test-evidence'))
        base.mkdir(parents=True, exist_ok=True)
        self.path = Path(tempfile.mkdtemp(prefix=label + '-', dir=base)).resolve()
        self.commands = []
        self.inputs = {str(Path(p).resolve()): digest(p) for p in inputs if Path(p).is_file()}
        self.controls = controls or {}
        self.closed = False
        self.tool_hashes = {}

    def reference_output(self, default, *, size=None, endian=None, system=None):
        """Select and record an exact oracle; most Minyar cases use the default.

        Optional variants follow the reviewed LLVM test-suite precedence:
        byte-order + size, size, byte-order, operating system, default.
        """
        default = Path(default).resolve()
        endian = endian or sys.byteorder
        system = system or sys.platform
        variants = ([f'{endian}-endian.{size}', size] if size else [])
        variants += [f'{endian}-endian', system, 'default']
        for variant in variants:
            path = default if variant == 'default' else default.with_name(default.name + '.' + variant)
            if path.is_file():
                self.inputs[str(path)] = digest(path)
                self.controls.setdefault('output_references', []).append({
                    'default': str(default), 'selected': str(path), 'variant': variant,
                    'byte_order': endian, 'system': system, 'size': size,
                    'sha256': self.inputs[str(path)],
                })
                return path.read_bytes()
        raise FileNotFoundError('No expected-output reference for ' + str(default))

    def run(self, command, *, timeout, cwd=None, capture_output=True, text=False,
            check=False, stdout=None, stderr=None, stdin=_DEFAULT_STDIN, input=None,
            env=None, phase='command', **kwargs):
        """subprocess.run subset with raw-byte evidence and descendant timeouts.

        Explicit streams (e.g. a closed stdout regression) retain their normal
        semantics. Only captured streams can be recorded. Test-controlled env
        changes are recorded, never the entire inherited environment.
        Stdin defaults to EOF. Supply input bytes (or str with text=True), an
        explicit stdin stream, or stdin=None to opt into inherited input.
        """
        input_bytes = None
        if input is not None:
            if stdin is not _DEFAULT_STDIN:
                raise ValueError('input cannot be combined with explicit stdin')
            if text:
                if not isinstance(input, str):
                    raise TypeError('input must be str when text=True')
                input_bytes = input.encode('utf-8')
            else:
                if not isinstance(input, (bytes, bytearray, memoryview)):
                    raise TypeError('input must be bytes when text=False')
                input_bytes = bytes(input)
            stdin = subprocess.PIPE
        elif stdin is _DEFAULT_STDIN:
            stdin = subprocess.DEVNULL
        if stdin == subprocess.DEVNULL:
            stdin_record = {'mode': 'eof'}
        elif stdin == subprocess.PIPE:
            stdin_record = {'mode': 'input', 'base64': base64.b64encode(input_bytes or b'').decode('ascii')}
        elif stdin is None:
            stdin_record = {'mode': 'inherited'}
        else:
            # Preserve arbitrary explicit streams, but only regular files with
            # a stable path/offset can be replayed without the original caller.
            stdin_record = {'mode': 'stream'}
            try:
                descriptor = stdin if isinstance(stdin, int) else stdin.fileno()
                opened = os.fstat(descriptor)
                name = getattr(stdin, 'name', None)
                if isinstance(name, (str, bytes, os.PathLike)) and stat.S_ISREG(opened.st_mode):
                    path = Path(os.fsdecode(name)).resolve()
                    named = path.stat()
                    if (named.st_dev, named.st_ino) == (opened.st_dev, opened.st_ino):
                        offset = os.lseek(descriptor, 0, os.SEEK_CUR)
                        fingerprint = digest(path)
                        self.inputs[str(path)] = fingerprint
                        stdin_record = {'mode': 'file', 'path': str(path), 'offset': offset,
                                        'sha256': fingerprint}
            except (AttributeError, OSError, TypeError, ValueError):
                pass
        command = [str(x) for x in command]
        cwd = str(Path(cwd or Path.cwd()).resolve())
        if capture_output:
            if stdout is not None or stderr is not None:
                raise ValueError('capture_output cannot be combined with explicit streams')
            stdout, stderr = subprocess.PIPE, subprocess.PIPE
        effective_env = os.environ if env is None else env
        requested_tool = str(kwargs.get('executable', command[0]))
        if os.path.dirname(requested_tool):
            executable = str((Path(cwd) / requested_tool).resolve())
        else:
            search = os.pathsep.join(str((Path(cwd) / entry).resolve())
                                     for entry in effective_env.get('PATH', os.defpath).split(os.pathsep))
            if os.name == 'nt':
                search = cwd + os.pathsep + search
            executable = shutil.which(requested_tool, path=search)
        tool_hash = None
        if executable and Path(executable).is_file():
            executable_stat = Path(executable).stat()
            identity = (executable, executable_stat.st_size, executable_stat.st_mtime_ns, executable_stat.st_ino)
            if identity not in self.tool_hashes:
                self.tool_hashes[identity] = digest(executable)
            tool_hash = self.tool_hashes[identity]
            kwargs['executable'] = executable
        row = {'command': command, 'cwd': cwd, 'timeout': timeout, 'phase': phase,
               'stdout_captured': stdout == subprocess.PIPE,
               'stderr_captured': stderr == subprocess.PIPE,
               'stdin': stdin_record,
               'executable': executable, 'executable_sha256': tool_hash, 'empty_environment': env == {},
               'environment': {k: v for k, v in effective_env.items()
                               if k.startswith('MINYAR_') or k in ('ASAN_OPTIONS', 'UBSAN_OPTIONS')
                               or (env is not None and os.environ.get(k) != v)},
               'removed_environment': sorted(set(os.environ) - set(effective_env)) if env else [],
               'timed_out': False}
        self.commands.append(row)
        start = time.monotonic()
        try:
            with subprocess.Popen(command, cwd=cwd, env=env, stdout=stdout, stderr=stderr, stdin=stdin,
                                  start_new_session=os.name != 'nt', **kwargs) as process:
                try:
                    out, err = process.communicate(input=input_bytes, timeout=timeout)
                except subprocess.TimeoutExpired:
                    row['timed_out'] = True
                    if os.name == 'nt':
                        try:
                            subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)],
                                           capture_output=True, timeout=10)
                        except (OSError, subprocess.TimeoutExpired) as error:
                            row['tree_termination_error'] = str(error)
                        finally:
                            process.kill()
                    else:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    out, err = process.communicate(timeout=10)
                row.update(returncode=process.returncode,
                           stdout_base64=base64.b64encode(out or b'').decode('ascii'),
                           stderr_base64=base64.b64encode(err or b'').decode('ascii'))
                if row['timed_out']:
                    raise subprocess.TimeoutExpired(command, timeout, output=out, stderr=err)
                result = subprocess.CompletedProcess(command, process.returncode,
                    out.decode('utf-8', errors='replace') if text and out is not None else out,
                    err.decode('utf-8', errors='replace') if text and err is not None else err)
                if check:
                    result.check_returncode()
                return result
        except BaseException as error:
            row['exception'] = type(error).__name__ + ': ' + str(error)
            raise
        finally:
            row['elapsed_seconds'] = time.monotonic() - start

    def close(self, failed=False):
        if self.closed:
            return
        self.closed = True
        if not failed:
            shutil.rmtree(self.path)
            return
        files = {str(p.relative_to(self.path)): digest(p)
                 for p in self.path.rglob('*') if p.is_file() and not p.is_symlink()}
        tools = {}
        versions = {}
        for row in self.commands:
            executable = row.get('executable')
            if executable and row.get('executable_sha256'):
                tools[executable] = row['executable_sha256']
                if re.fullmatch(r'(?:clang(?:\+\+)?|opt|FileCheck|python)(?:[-0-9.]+)?(?:\.exe)?', Path(executable).name) and executable not in versions:
                    try:
                        version = subprocess.run([executable, '--version'], capture_output=True, timeout=5)
                        versions[executable] = (version.stdout + version.stderr).decode('utf-8', errors='replace')
                    except (OSError, subprocess.TimeoutExpired) as error:
                        versions[executable] = str(error)
        report = {'schema_version': 1, 'status': 'failed', 'workspace': str(self.path),
                  'inputs': self.inputs, 'files': files, 'tools': tools,
                  'tool_versions': versions, 'controls': self.controls, 'commands': self.commands}
        (self.path / 'evidence.json').write_text(json.dumps(report, indent=2) + '\n')
        print(f'Test failure evidence retained: {self.path}', file=sys.stderr)

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        self.close(failed=kind is not None)


def replay(manifest, index):
    """Replay one recorded command in its retained original workspace.

    Verify frozen inputs before running. This intentionally does not silently
    rebuild a changed compiler or bless changed outputs.
    """
    data = json.loads(Path(manifest).read_text())
    for path, expected in {**data['inputs'], **data['tools']}.items():
        if not Path(path).is_file() or digest(path) != expected:
            raise ValueError('Replay input changed: ' + path)
    for path, expected in data['files'].items():
        source = Path(data['workspace']) / path
        if not source.is_file() or digest(source) != expected:
            raise ValueError('Replay artifact changed: ' + str(source))
    row = data['commands'][index]
    if not row['stdout_captured'] or not row['stderr_captured']:
        raise ValueError('Replay of redirected streams requires the original test scenario')
    stdin_record = row.get('stdin', {})
    stdin_mode = stdin_record.get('mode')
    if stdin_mode not in ('eof', 'input', 'file'):
        raise ValueError('Replay stdin requires the original test scenario: ' + (stdin_mode or 'unrecorded'))
    executable = row.get('executable')
    if executable and digest(executable) != row.get('executable_sha256'):
        raise ValueError('Replay command executable changed: ' + executable)
    env = {} if row.get('empty_environment') else os.environ.copy()
    for key in list(env):
        if key.startswith('MINYAR_') or key in ('ASAN_OPTIONS', 'UBSAN_OPTIONS') or key in row.get('removed_environment', []):
            del env[key]
    env.update(row['environment'])
    arguments = {'executable': executable} if executable else {}
    input_file = None
    if stdin_mode == 'input':
        arguments['input'] = base64.b64decode(stdin_record['base64'], validate=True)
    elif stdin_mode == 'file':
        path = Path(stdin_record['path'])
        if not path.is_file() or digest(path) != stdin_record['sha256']:
            raise ValueError('Replay stdin changed: ' + str(path))
        input_file = path.open('rb')
        try:
            input_file.seek(stdin_record['offset'])
        except BaseException:
            input_file.close()
            raise
        arguments['stdin'] = input_file
    try:
        with Evidence('replay', controls={'source_manifest': str(manifest), 'command_index': index}) as evidence:
            result = evidence.run(row['command'], cwd=row['cwd'], env=env, timeout=row['timeout'], **arguments)
            sys.stdout.buffer.write(result.stdout)
            sys.stderr.buffer.write(result.stderr)
            return result.returncode
    finally:
        if input_file is not None:
            input_file.close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--command', type=int, default=-1, help='zero-based recorded command; default last')
    args = parser.parse_args()
    sys.exit(replay(args.manifest, args.command))
