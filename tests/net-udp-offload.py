#!/usr/bin/env python3
"""Real native and public Minyar UDP offload contracts at O0/O2."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import time

from clang_helpers import windows_host

ROOT = Path(__file__).resolve().parents[1]



def text_stdout(stdout, windows):
    # Preserve the raw evidence; only native Windows CRT text uses CRLF.
    return stdout.replace(b'\r\n', b'\n') if windows else stdout


def native_diagnostics(stderr, linux):
    if not linux:
        assert stderr == b'', stderr
        return None
    match = re.fullmatch(
        rb'UDP readiness deadline: 30ms requested, ([0-9]+\.[0-9]{3})ms observed, ([0-9]+) signals\n',
        stderr)
    assert match, stderr
    elapsed_ms, signals = float(match[1]), int(match[2])
    assert 20 <= elapsed_ms < 100 and signals > 0, stderr
    return {'requested_ms': 30, 'observed_ms': elapsed_ms, 'signals': signals}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--evidence', type=Path)
    options = parser.parse_args()
    output = options.evidence or ROOT / 'build' / (
        'net-udp-offload-sanitize' if options.sanitize else 'net-udp-offload')
    output.mkdir(parents=True, exist_ok=True)
    output = output.resolve()
    windows = windows_host()
    linux = platform.system() == 'Linux'
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    inputs = [Path(__file__), ROOT / 'tests/net-udp-offload.c',
              ROOT / 'tests/net-udp-offload.min', ROOT / 'runtime/native/net.c',
              ROOT / 'runtime/minyar_runtime.c', ROOT / 'library/net.min',
              ROOT / 'library/errors.min', ROOT / 'library/eventloop.min',
              ROOT / 'minyar', ROOT / 'tools/clang-driver.py',
              *sorted((ROOT / 'runtime').rglob('*.h'))]
    compiler = Path(shutil.which(clang) or clang)
    report = {
        'passed': False, 'sanitize': options.sanitize,
        'platform': platform.platform(), 'linux_feature_required': linux,
        'source_commit': os.environ.get('MINYAR_SOURCE_COMMIT'),
        'inputs': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in inputs},
        'cases': []}
    if compiler.is_file():
        report['compiler_sha256'] = hashlib.sha256(compiler.read_bytes()).hexdigest()
    environment = dict(os.environ, MAKEFLAGS='-j1', MINYAR_CLANG=clang)
    if options.sanitize:
        environment.update(
            ASAN_OPTIONS='detect_leaks=' + ('1' if linux else '0') + ':halt_on_error=1',
            UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')

    def run(label, command, *, env=environment, binary=None, timeout=120):
        started = time.monotonic()
        result = subprocess.run([str(value) for value in command], cwd=ROOT,
                                env=env, capture_output=True, timeout=timeout)
        (output / (label + '.stdout')).write_bytes(result.stdout)
        (output / (label + '.stderr')).write_bytes(result.stderr)
        row = {'label': label, 'argv': [str(value) for value in command],
               'status': result.returncode, 'seconds': time.monotonic() - started,
               'stdout_sha256': hashlib.sha256(result.stdout).hexdigest(),
               'stderr_sha256': hashlib.sha256(result.stderr).hexdigest()}
        if binary and binary.is_file():
            row['binary_sha256'] = hashlib.sha256(binary.read_bytes()).hexdigest()
        report['cases'].append(row)
        if result.returncode:
            raise AssertionError(f'{label}: status {result.returncode}\n'
                                 + (result.stdout + result.stderr).decode(errors='replace'))
        return result

    try:
        version = run('compiler-version', [clang, '--version'])
        report['compiler_version'] = version.stdout.decode(errors='replace')
        for optimization in ('-O0', '-O2'):
            label = optimization[1:]
            flags = [optimization]
            if options.sanitize:
                flags += ['-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
            binary = output / ('native-' + label + ('.exe' if windows else ''))
            # The fixture includes production net.c to exercise syscall seams;
            # linking another net.c would define every native symbol twice.
            command = [clang, '-std=c11', '-Wall', '-Wextra', '-Werror',
                       '-DMINYAR_SYSTEM_HEAP=1', *flags,
                       ROOT / 'tests/net-udp-offload.c', ROOT / 'runtime/minyar_runtime.c',
                       '-lm', '-o', binary]
            if windows:
                command += ['-lws2_32']
            run('native-build-' + label, command, binary=binary)
            native = run('native-run-' + label, [binary], binary=binary, timeout=30)
            if linux:
                assert b'UDP offload explicitly unavailable' not in native.stdout
                assert b'GRO' in native.stdout, native.stdout
                assert b'signal-interrupted UDP readiness retains its original deadline\n' in native.stdout
            else:
                assert text_stdout(native.stdout, windows) == b'UDP offload explicitly unavailable on this OS\n', native.stdout
            deadline = native_diagnostics(native.stderr, linux)
            if deadline:
                report['cases'][-1]['readiness_deadline'] = deadline

            typed = output / ('typed-' + label + ('.exe' if windows else ''))
            typed_environment = dict(environment)
            typed_flags = [*flags, '-Wno-override-module']
            for name in ('MINYAR_CLANG_FLAGS', 'MINYAR_RUNTIME_FLAGS', 'MINYAR_NATIVE_FLAGS'):
                typed_environment[name] = shlex.join(typed_flags)
            command = [ROOT / 'minyar', ROOT / 'tests/net-udp-offload.min', '-o', typed]
            if os.name == 'nt':
                bash = shutil.which('bash')
                if not bash:
                    raise RuntimeError('Bash is required for the native Windows launcher')
                command.insert(0, bash)
            run('typed-build-' + label, command, env=typed_environment, binary=typed)
            result = run('typed-run-' + label, [typed], env=typed_environment,
                         binary=typed, timeout=30)
            expected = (b'typed UDP offload boundaries verified\n' if linux
                        else b'UDP offload unavailable\n')
            assert text_stdout(result.stdout, windows) == expected and result.stderr == b'', result
            print(label + ': native and typed ' + ('Linux offload' if linux else
                  'explicit unavailable contracts') + ' passed', flush=True)
        report['passed'] = True
    finally:
        (output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
