#!/usr/bin/env python3
"""Run every retained QUIC RFC driver through public O0/O2 native builds.

Link artifacts prove the program and native runtime object that reached Clang.
They do not count the launcher's internal runtime compilations.
"""
import argparse
import base64
import ast
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

from clang_helpers import asan_leak_options, launcher_command, windows_host
from test_evidence import Evidence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from host_paths import host_path
from sanitizer_llvm import instrument_address_sanitizer

BINARIES = {
    'migration': 'tests/quic-migration-cids.min',
    'cipher': 'tests/quic-cipher-policy.min',
    'client': 'tests/interop/qns/client.min',
    'server': 'tests/interop/qns/server.min',
}
DRIVERS = (
    ('migration', 'tests/quic-migration-cids.py', 'BASELINE',
     ('--binary', 'migration')),
    ('cipher', 'tests/quic-cipher-policy.py', 'BASELINE',
     ('--binary', 'cipher')),
    ('local', 'tests/quic-qns-local.py', 'CASES',
     ('--client', 'client', '--server', 'server')),
    ('vn', 'tests/quic-vn-probe.py', None, ('--server', 'server')),
)
OPTIMIZATIONS = ('0', '2')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def declared_cases(path, symbol):
    tree = ast.parse(Path(path).read_text())
    values = [ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == symbol
                      for target in node.targets)]
    require(len(values) == 1, 'case inventory must have one literal declaration')
    cases = list(values[0])
    require(cases and len(cases) == len(set(cases))
            and all(isinstance(value, str) for value in cases),
            'empty, duplicate or non-text author cases')
    return cases


def verify_result(kind, report, cases, binaries, source):
    if kind == 'vn':
        require(report.get('result') == 'passed', 'version negotiation did not pass')
        require(report.get('server_sha256') == digest(binaries['server']),
                'version-negotiation binary mismatch')
        require(1 in report.get('versions', []) and
                int(report['reserved_version'], 16) not in report['versions'],
                'version-negotiation policy mismatch')
        require(report.get('request_bytes') == 1200 and
                0 < report.get('response_bytes', 0) <= 3 * report['request_bytes'],
                'version-negotiation response size mismatch')
        return
    rows = report.get('results')
    require(isinstance(rows, list) and [row.get('case') for row in rows] == cases,
            'author case inventory missing, reordered or filtered')
    if kind in ('migration', 'cipher'):
        require(report.get('baseline') is False and
                report.get('compiler_invoked') is False,
                'old-code oracle or nested compiler invoked')
        require(report.get('binary_sha256') == digest(binaries[kind]) and
                report.get('test_source_sha256') == digest(source),
                'author source or binary mismatch')
        for row in rows:
            require(row.get('expected_returncode') == 0 and
                    row.get('returncode') == 0 and row.get('matched') is True
                    and row.get('stderr') == '',
                    'protocol assertion or sanitizer diagnostic failed')
    else:
        require(report.get('binary_hashes') == {
            name: digest(binaries[name]) for name in ('client', 'server')},
            'local endpoint binary mismatch')
        for row in rows:
            require(row.get('expected') == 0 and row.get('semantic_status') == 0
                    and row.get('client_status') == 0 and row.get('matched') is True
                    and row.get('files_match') is True
                    and row.get('reciprocal_epoch_secrets') is True
                    and row.get('client_stderr') == ''
                    and row.get('server_stderr') == '',
                    'local endpoint assertion or sanitizer diagnostic failed')


def verify_link(directory, binary, sanitize):
    report = json.loads((directory / 'manifest.json').read_text())
    raw = (directory / 'program.raw.ll').read_bytes()
    require(report.get('link_status') == 0 and
            report.get('address_sanitizer_enabled') is sanitize and
            report.get('program_ir_cached') is False and
            report.get('runtime_reannotated') is False,
            'effective program sanitizer/link provenance mismatch')
    require(report.get('raw_sha256') == hashlib.sha256(raw).hexdigest(),
            'raw generated program changed')
    linked = ((directory / 'program.asan.ll').read_bytes() if sanitize else raw)
    if sanitize:
        require(linked == instrument_address_sanitizer(raw.decode()).encode(),
                'linked program is not canonical ASan annotation')
        require(linked != raw, 'generated program was not annotated')
    require(report.get('linked_program_sha256') == hashlib.sha256(linked).hexdigest(),
            'linked generated program changed')
    command = report.get('command', [])
    expected_program = directory / 'program.asan.ll' if sanitize else host_path(report.get('raw_program', ''))
    require(any(host_path(argument).resolve() == expected_program.resolve()
                for argument in command if str(argument).endswith('.ll')),
            'link command does not use the recorded generated program')
    require(isinstance(report.get('compiler_version'), str) and report['compiler_version']
            and 'clang.bin' in report.get('tools', {}),
            'actual compiler bytes/version are absent')
    inputs = report.get('inputs', [])
    runtimes = [row for row in inputs if row.get('retained') == 'runtime.o']
    require(len(runtimes) == 1 and str(runtimes[0].get('original', '')).endswith('.o'),
            'runtime must be one native object, not LLVM')
    require(any(host_path(argument).resolve() == host_path(runtimes[0]['original']).resolve()
                for argument in command if str(argument).endswith('.o')),
            'link command does not use the retained native runtime object')
    for row in inputs:
        require(isinstance(row.get('retained'), str) and
                Path(row['retained']).name == row['retained'],
                'unsafe retained native input path')
        path = directory / row['retained']
        require(path.is_file() and digest(path) == row['sha256'],
                'retained native link input changed')
    require(report.get('binary_sha256') == digest(binary) and
            (directory / ('program' + binary.suffix)).read_bytes() == binary.read_bytes(),
            'linked binary evidence mismatch')
    require(set(report.get('tools', {})) == {'clang-driver.py', 'sanitizer_llvm.py', 'clang.bin'},
            'canonical helper or compiler evidence is missing')
    for name, value in report.get('tools', {}).items():
        require(digest(directory / name) == value, 'retained link tool changed')
    for name in ('clang-driver.py', 'sanitizer_llvm.py'):
        require(report.get('tools', {}).get(name) == digest(ROOT / 'tools' / name),
                'canonical link helper mismatch')
    return report


def snapshot_inputs():
    paths = [ROOT / 'minyar', ROOT / 'Makefile']
    for name in ('bootstrap', 'compiler', 'library', 'runtime', 'tools', 'build-support', 'vendor'):
        paths += [path for path in sorted((ROOT / name).rglob('*'))
                  if path.is_file() and path.suffix in
                  ('.min', '.c', '.h', '.m', '.py', '.sh', '.mk')]
    paths += [ROOT / name for name in BINARIES.values()]
    paths += [ROOT / row[1] for row in DRIVERS]
    paths += [Path(__file__), ROOT / 'tests/quic-rfc-harness.py',
              ROOT / 'tests/tls-local.py', ROOT / 'tests/test_evidence.py',
              ROOT / 'tests/clang_helpers.py']
    # Author-owned portable endpoint helpers are included when exported.
    paths += [path for path in sorted((ROOT / 'tests').glob('quic_qns_*.py'))]
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in sorted(set(paths))}


def inventory(directory):
    return {path.relative_to(directory).as_posix(): digest(path)
            for path in sorted(directory.rglob('*')) if path.is_file()
            and not path.is_symlink()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--optimization', choices=('both',), default='both')
    parser.add_argument('--artifacts', type=Path, required=True)
    options = parser.parse_args()
    require(not sys.flags.optimize, 'QUIC RFC assertions require non-optimized Python')
    require(options.artifacts.is_absolute(), 'evidence path must be absolute')
    directory = options.artifacts.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    before = snapshot_inputs()
    for name in before:
        target = directory / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    frontend_hashes = {}
    for name in ('minyarc', 'minyarc-callbacks', 'minyarc-errors-request', 'minyarc-errors'):
        path = ROOT / 'build' / (name + ('.exe' if windows_host() else ''))
        if not path.is_file():
            path = ROOT / 'build' / name
        require(path.is_file(), 'public frontend prerequisite absent: ' + name)
        target = directory / 'frontends' / path.name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(path, target)
        frontend_hashes[name] = digest(path)
    clang = os.environ.get('MINYAR_TEST_CLANG',
                           os.environ.get('MINYAR_CLANG', os.environ.get('LLVM_CC', 'clang')))
    environment = dict(os.environ, MAKEFLAGS='-j1', MINYAR_CLANG=clang)
    environment.pop('PYTHONOPTIMIZE', None)
    environment.pop('MINYAR_LINK_ARTIFACTS', None)
    environment.update(ASAN_OPTIONS=asan_leak_options() + ':halt_on_error=1',
                       UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    report = {'passed': False, 'sanitize': options.sanitize,
              'optimization': list(OPTIMIZATIONS), 'platform': platform.platform(),
              'source_commit': os.environ.get('MINYAR_SOURCE_COMMIT'),
              'source_before': before, 'frontend_hashes': frontend_hashes,
              'runtime_scope': 'Observed native link object; compile count is not independently measured.',
              'commands': [], 'links': [], 'drivers': []}
    previous = os.environ.get('MINYAR_TEST_EVIDENCE')
    os.environ['MINYAR_TEST_EVIDENCE'] = str(directory / 'observations')
    try:
        evidence = Evidence('quic-rfc', inputs=[ROOT / name for name in before])
    finally:
        if previous is None:
            os.environ.pop('MINYAR_TEST_EVIDENCE', None)
        else:
            os.environ['MINYAR_TEST_EVIDENCE'] = previous
    original_popen = subprocess.Popen

    def run(label, command, env, timeout):
        # Evidence already supplies the POSIX process group. MSYS is a native
        # Windows host and must use the shared Windows tree cleanup without a
        # POSIX session, matching the native-Windows evidence convention.
        def platform_popen(*args, **kwargs):
            if windows_host():
                kwargs['start_new_session'] = False
            return original_popen(*args, **kwargs)
        started = time.monotonic()
        subprocess.Popen = platform_popen
        try:
            result = evidence.run(command, timeout=timeout, cwd=ROOT, env=env, phase=label)
        finally:
            subprocess.Popen = original_popen
            report['commands'] = evidence.commands
            if evidence.commands:
                row = evidence.commands[-1]
                for stream in ('stdout', 'stderr'):
                    value = row.get(stream + '_base64')
                    if value is not None:
                        (directory / (label + '.' + stream)).write_bytes(base64.b64decode(value))
            (directory / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
        (directory / (label + '.stdout')).write_bytes(result.stdout)
        (directory / (label + '.stderr')).write_bytes(result.stderr)
        require(result.returncode == 0, label + ' failed: ' +
                (result.stdout + result.stderr).decode(errors='replace'))
        report['commands'][-1]['label'] = label
        report['commands'][-1]['wall_seconds'] = time.monotonic() - started
        return result

    try:
        version = run('clang-version', [clang, '--version'], environment, 30)
        report['compiler_version'] = version.stdout.decode(errors='replace')
        report['compiler_sha256'] = evidence.commands[-1].get('executable_sha256')
        require(isinstance(report['compiler_sha256'], str)
                and len(report['compiler_sha256']) == 64, 'selected compiler identity missing')
        for opt in OPTIMIZATIONS:
            flags = ['-O' + opt, '-Wno-override-module']
            if options.sanitize:
                flags += ['-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
            import shlex
            mode_env = dict(environment)
            for name in ('MINYAR_CLANG_FLAGS', 'MINYAR_NATIVE_FLAGS', 'MINYAR_RUNTIME_FLAGS'):
                mode_env[name] = shlex.join(flags)
            binaries = {}
            for name, source in BINARIES.items():
                binary = directory / (name + '-O' + opt + ('.exe' if windows_host() else ''))
                link = directory / ('link-' + name + '-O' + opt)
                build_env = dict(mode_env, MINYAR_LINK_ARTIFACTS=str(link))
                command = launcher_command(ROOT) + ['--library', str(ROOT / 'library'),
                                                    str(ROOT / source), '-o', str(binary)]
                run('build-' + name + '-O' + opt, command, build_env, 180)
                binaries[name] = binary
                link_report = verify_link(link, binary, options.sanitize)
                require(link_report['tools']['clang.bin'] == report['compiler_sha256'],
                        'link compiler differs from selected tool identity')
                report['links'].append(dict(name=name, optimization=opt, manifest=link_report))
            for kind, source, symbol, arguments in DRIVERS:
                child_artifacts = directory / ('driver-' + kind + '-O' + opt)
                command = [sys.executable, str(ROOT / source)]
                for argument in arguments:
                    command.append(str(binaries[argument]) if argument in binaries else argument)
                command += ['--artifacts', str(child_artifacts)]
                result = run('run-' + kind + '-O' + opt, command, mode_env, 600)
                require(result.stderr == b'', 'unexpected driver or sanitizer stderr')
                parsed = json.loads(result.stdout)
                cases = declared_cases(ROOT / source, symbol) if symbol else None
                verify_result(kind, parsed, cases, binaries, ROOT / BINARIES.get(kind, source))
                require(child_artifacts.is_dir() and any(child_artifacts.rglob('*')),
                        'author driver did not retain its child evidence')
                report['drivers'].append(dict(kind=kind, optimization=opt, cases=cases,
                    result=parsed, artifacts=inventory(child_artifacts)))
                print('QUIC RFC O' + opt + ' ' + kind + ' passed', flush=True)
        after = snapshot_inputs()
        require(after == before, 'QUIC RFC source changed during execution')
        report['source_after'] = after
        report['passed'] = True
    finally:
        report['commands'] = evidence.commands
        try:
            report['source_after'] = snapshot_inputs()
        except (OSError, ValueError) as error:
            report['source_after_error'] = repr(error)
            report['passed'] = False
        report['frontend_after'] = {}
        for name in frontend_hashes:
            path = ROOT / 'build' / (name + ('.exe' if windows_host() else ''))
            if not path.is_file():
                path = ROOT / 'build' / name
            if path.is_file():
                report['frontend_after'][name] = digest(path)
        if report.get('source_after') != before or report['frontend_after'] != frontend_hashes:
            report['passed'] = False
        report['retained_inputs'] = inventory(directory / 'source')
        report['artifacts'] = {name: value for name, value in inventory(directory).items()
                               if name != 'manifest.json'}
        (directory / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    require(report['passed'], 'input or frontend provenance changed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
