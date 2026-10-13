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
import re
import shutil
import subprocess
import sys
import time

from clang_helpers import asan_leak_options, launcher_command, windows_host
from test_evidence import Evidence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from host_paths import host_path
from sanitizer_llvm import address_sanitizer_enabled, instrument_address_sanitizer

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


def exact_integer(value, *, minimum=None, maximum=None):
    return type(value) is int and (minimum is None or value >= minimum) and (
        maximum is None or value <= maximum)


def sha256_value(value):
    return isinstance(value, str) and len(value) == 64 and all(
        character in '0123456789abcdef' for character in value)


def normalized_text(raw):
    return raw.decode('utf-8', errors='replace').replace('\r\n', '\n').replace('\r', '\n')


def declared_cases(path, symbol):
    tree = ast.parse(Path(path).read_text())
    nodes = [node.value for node in tree.body if isinstance(node, ast.Assign)
             and any(isinstance(target, ast.Name) and target.id == symbol
                     for target in node.targets)]
    require(len(nodes) == 1, 'case inventory must have one literal declaration')
    node = nodes[0]
    if isinstance(node, ast.Dict):
        keys = [ast.literal_eval(key) for key in node.keys]
        require(len(keys) == len(set(keys)), 'duplicate literal case key')
    value = ast.literal_eval(node)
    require(isinstance(value, (dict, tuple, list)), 'case inventory must be a literal collection')
    cases = list(value)
    require(cases and all(isinstance(case, str) and case for case in cases)
            and len(cases) == len(set(cases)), 'empty, duplicate or non-text author cases')
    return cases


def verify_result(kind, report, cases, binaries, source):
    require(isinstance(report, dict), 'author result must be an object')
    if kind == 'vn':
        require(report.get('result') == 'passed', 'version negotiation did not pass')
        require(report.get('server_sha256') == digest(binaries['server']),
                'version-negotiation binary mismatch')
        versions = report.get('versions')
        require(isinstance(versions, list) and versions
                and all(exact_integer(value, minimum=0, maximum=2**32-1) for value in versions)
                and len(versions) == len(set(versions)), 'invalid version-negotiation versions')
        require(isinstance(report.get('reserved_version'), str)
                and int(report['reserved_version'], 16) == 0x0a0a0a0a
                and 1 in versions and 0x0a0a0a0a not in versions,
                'version-negotiation policy mismatch')
        require(exact_integer(report.get('request_bytes')) and report['request_bytes'] == 1200
                and exact_integer(report.get('response_bytes'), minimum=1, maximum=3600),
                'version-negotiation response size mismatch')
        return
    rows = report.get('results')
    require(isinstance(rows, list) and all(isinstance(row, dict) for row in rows)
            and [row.get('case') for row in rows] == cases,
            'author case inventory missing, reordered or filtered')
    if kind in ('migration', 'cipher'):
        require(report.get('baseline') is False and report.get('compiler_invoked') is False,
                'old-code oracle or nested compiler invoked')
        require(report.get('binary_sha256') == digest(binaries[kind])
                and report.get('test_source_sha256') == digest(source),
                'author source or binary mismatch')
        for row in rows:
            require(all(exact_integer(row.get(key)) and row[key] == 0
                        for key in ('expected_returncode', 'returncode'))
                    and row.get('matched') is True and row.get('stderr') == '',
                    'protocol assertion or sanitizer diagnostic failed')
    else:
        require(report.get('binary_hashes') == {
            name: digest(binaries[name]) for name in ('client', 'server')},
            'local endpoint binary mismatch')
        for row in rows:
            require(all(exact_integer(row.get(key)) and row[key] == 0
                        for key in ('expected', 'semantic_status', 'client_status'))
                    and row.get('matched') is True and row.get('files_match') is True
                    and row.get('reciprocal_epoch_secrets') is True
                    and row.get('client_stderr') == '' and row.get('server_stderr') == '',
                    'local endpoint assertion or sanitizer diagnostic failed')
            if row.get('case') in ('rebind-routes', 'rebind-pending'):
                require(exact_integer(row.get('rebound_routes'), minimum=12),
                        'repeated rebinding did not exceed the old route bound')
            preferred = {
                'preferred': 'QNS authenticated preferred address ipv4=7f000001:44301 ipv6=00000000000000000000000000000000:0',
                'preferred-ipv6': 'QNS authenticated preferred address ipv4=00000000:0 ipv6=00000000000000000000000000000001:44301',
            }
            if row.get('case') in preferred:
                expected = [preferred[row['case']]]
                require(row.get('preferred_tuple_match') is True
                        and row.get('authenticated_preferred_tuples') == expected
                        and isinstance(row.get('client_stdout'), str)
                        and [line for line in row['client_stdout'].splitlines()
                             if line.startswith('QNS authenticated preferred address ')] == expected,
                        'authenticated preferred address tuple mismatch')


def retained_path(directory, relative):
    require(isinstance(relative, str) and relative and '\\' not in relative,
            'retained path must be POSIX relative text')
    path = Path(relative)
    require(not path.is_absolute() and '..' not in path.parts and '.' not in path.parts,
            'unsafe retained path')
    actual = directory / path
    require(actual.is_file() and not actual.is_symlink()
            and actual.resolve().is_relative_to(directory.resolve()),
            'missing or escaped retained file')
    return actual


def verify_binding(directory, row, *, immediate=False):
    require(isinstance(row, dict) and isinstance(row.get('original'), str)
            and host_path(row['original']).is_absolute(), 'missing absolute input identity')
    path = retained_path(directory, row.get('retained'))
    require(exact_integer(row.get('bytes'), minimum=0)
            and path.stat().st_size == row['bytes'], 'retained byte size mismatch')
    value = digest(path)
    fields = ('sha256', 'source_before_sha256', 'retained_sha256', 'source_after_sha256')
    if immediate:
        fields += ('pre_link_sha256', 'post_link_sha256')
    require(all(sha256_value(row.get(key)) and row[key] == value for key in fields),
            'input before/copy/after byte binding mismatch')
    return row['original']


def requested_flags(optimization, sanitize):
    flags = ['-O' + optimization, '-Wno-override-module']
    if sanitize:
        flags += ['-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    return flags


def effective_optimization(arguments):
    value = None
    for argument in arguments:
        if re.fullmatch(r'-O(?:[0-9]+|s|z|g|fast)?', argument):
            value = argument[2:] or '1'
    return value


def verify_server_shutdown_state(row):
    # This checks prior health/ownership consistency; the lifecycle proof below
    # must separately establish the final status of an intentional termination.
    require(isinstance(row, dict) and 'status_before_shutdown' in row
            and 'owned_termination_requested' in row and exact_integer(row.get('status')),
            'endpoint shutdown observation missing')
    prior = row['status_before_shutdown']
    requested = row['owned_termination_requested']
    require((prior is None or (exact_integer(prior) and prior == 0))
            and type(requested) is bool and requested is (prior is None),
            'endpoint exited unexpectedly or shutdown ownership is inconsistent')
    if prior is not None:
        require(row['status'] == 0, 'endpoint status changed after its normal exit')


def verify_server_lifecycle(row, raw_file):
    verify_server_shutdown_state(row)
    require(exact_integer(row.get('pid'), minimum=1), 'endpoint owned process identity missing')
    lifecycle = row.get('lifecycle')
    require(isinstance(lifecycle, dict)
            and all(lifecycle.get(name) is True for name in
                    ('healthy_before_shutdown', 'cleanup_complete', 'passed'))
            and lifecycle.get('cleanup_errors') == []
            and type(lifecycle.get('escalated')) is bool
            and exact_integer(lifecycle.get('expected_final_status'))
            and lifecycle['expected_final_status'] == row['status'],
            'endpoint lifecycle did not prove healthy complete cleanup')
    strategy, receipt = lifecycle.get('termination_strategy'), lifecycle.get('receipt')
    require(isinstance(receipt, dict), 'endpoint termination receipt missing')
    if row['status_before_shutdown'] == 0:
        require(strategy == 'already-exited' and lifecycle['expected_final_status'] == 0
                and lifecycle['escalated'] is False and receipt == {},
                'normal endpoint exit acquired an inconsistent termination receipt')
        return []
    require(strategy != 'already-exited', 'running endpoint lacks owned termination')
    pid = row['pid']

    def posix_action(action, signum, timed_out):
        require(isinstance(action, dict)
                and exact_integer(action.get('pid')) and action['pid'] == pid
                and exact_integer(action.get('pgid')) and action['pgid'] == pid
                and action.get('attempted') is True
                and exact_integer(action.get('signal')) and action['signal'] == signum
                and exact_integer(action.get('grace_seconds')) and action['grace_seconds'] == 5
                and action.get('wait_timed_out') is timed_out
                and action.get('result') == 'sent', 'unproved owned POSIX termination action')

    if strategy in ('posix-sigterm', 'posix-sigkill-after-grace'):
        require(not windows_host(), 'POSIX termination cannot certify a Windows endpoint')
        escalated = strategy == 'posix-sigkill-after-grace'
        require(lifecycle['escalated'] is escalated
                and lifecycle['expected_final_status'] == (-9 if escalated else -15),
                'POSIX final status differs from its exact termination action')
        posix_action(receipt, 9 if escalated else 15, False)
        if escalated:
            previous = receipt.get('previous')
            posix_action(previous, 15, True)
            require('previous' not in previous, 'ambiguous POSIX escalation chain')
        else:
            require('previous' not in receipt, 'unexplained POSIX prior termination action')
        return []
    require(strategy == 'windows-taskkill-tree' and windows_host()
            and lifecycle['escalated'] is False and lifecycle['expected_final_status'] == 1,
            'unsupported or unproved native termination strategy')
    native_pid = receipt.get('native_pid')
    python_os_name = receipt.get('python_os_name')
    require(exact_integer(receipt.get('pid')) and receipt['pid'] == pid
            and exact_integer(native_pid, minimum=1)
            and python_os_name in ('nt', 'posix')
            and receipt.get('pid_source') == ('popen' if python_os_name == 'nt' else 'proc-winpid')
            and (python_os_name != 'nt' or native_pid == pid)
            and receipt.get('argv') == ['taskkill.exe', '-F', '-T', '-PID', str(native_pid)]
            and exact_integer(receipt.get('timeout_seconds')) and receipt['timeout_seconds'] == 10
            and receipt.get('attempted') is True
            and exact_integer(receipt.get('status')) and receipt['status'] == 0
            and receipt.get('wait_timed_out', False) is False
            and 'previous' not in receipt, 'native termination ownership/action receipt differs')
    # This exact final-status prediction is fail-closed. Platform coverage still
    # requires native execution; taskkill success alone is not a target verdict.
    return [raw_file(receipt, stream) for stream in ('stdout', 'stderr')]


def verify_case_invocation(kind, case, command, endpoint, roles, directory, binaries):
    workspace = directory / 'fixtures'
    def fixture(name):
        relative = 'fixtures/' + name
        require(relative in roles['certificates'], 'invocation certificate fixture omitted')
        return str(retained_path(directory, relative))
    if kind in ('migration', 'cipher'):
        expected = [str(binaries[kind].resolve()), *[
            fixture(name) for name in ('root.der', 'server.der', 'server.pk8',
                                       'client.der', 'client.pk8')], case]
        require(command == expected and endpoint is None,
                'case label differs from complete migration/cipher argv')
        return
    if kind == 'local':
        mapping = {'multiplex1999': 'transfer', 'multiconnect50': 'multiconnect',
                   'ipv6': 'transfer', 'preferred': 'connectionmigration',
                   'preferred-ipv6': 'connectionmigration',
                   'resumption40': 'resumption', 'zerortt40': 'zerortt', 'rebind-routes': 'transfer', 'rebind-pending': 'transfer',
                   'keyupdate': 'keyupdate', 'chacha20': 'chacha20'}
        require(case in mapping, 'unknown local endpoint case')
        testcase = mapping[case]
        count = 1999 if case == 'multiplex1999' else (
            50 if case == 'multiconnect50' else 40 if case in ('resumption40', 'zerortt40') else 1)
        names = ['file' + str(index) for index in range(count)]
        expected = [str(binaries['client'].resolve()), fixture('root.der'),
                    '::1' if case in ('ipv6', 'preferred-ipv6') else '127.0.0.1',
                    '44302' if case in ('rebind-routes', 'rebind-pending') else '44300',
                    str(workspace / (case + '-client.keys')),
                    str(workspace / (case + '-downloads')), testcase, *names]
        expected_server = [str(binaries['server'].resolve()), fixture('server.pk8'),
            fixture('root.der'), str(workspace / (case + '-server.keys')),
            str(workspace / (case + '-www')), testcase, fixture('server.der'), '--port=44300']
        if case == 'preferred':
            expected_server += ['--preferred-ipv4=7f000001', '--preferred-port=44301']
        if case == 'preferred-ipv6':
            expected_server += ['--preferred-ipv4=00000000',
                                '--preferred-ipv6=00000000000000000000000000000001',
                                '--preferred-port=44301']
        require(command == expected and endpoint == expected_server,
                'local testcase/client-server/fixture argv binding mismatch')
        require(roles['payloads'] == ['fixtures/' + case + '-www/' + name for name in sorted(names)]
                and roles['downloads'] == ['fixtures/' + case + '-downloads/' + name for name in sorted(names)]
                and roles['keylogs'] == sorted(['fixtures/' + case + '-client.keys',
                                               'fixtures/' + case + '-server.keys']),
                'local payload/download/keylog case mapping mismatch')
        return
    require(kind == 'vn' and case == 'reserved-version', 'unknown version-negotiation case')
    expected_server = [str(binaries['server'].resolve()), fixture('server.pk8'),
        fixture('root.der'), str(workspace / 'keys'), str(workspace / 'www'),
        'transfer', fixture('server.der'), '--port=44300']
    require(command is None and endpoint == expected_server,
            'version-negotiation server/fixture argv binding mismatch')
    require(roles['packets'] == ['fixtures/request.bin', 'fixtures/response.bin']
            and roles['keylogs'] in ([], ['fixtures/keys']),
            'version-negotiation packet/keylog case mapping mismatch')


def verify_link(directory, binary, sanitize, optimization='0', compiler_identity=None):
    report = json.loads((directory / 'manifest.json').read_text())
    require(exact_integer(report.get('schema')) and report['schema'] == 2,
            'final-link schema 2 required')
    require(all(exact_integer(report.get(key)) and report[key] == 0
                for key in ('link_status', 'link_subprocess_status'))
            and report.get('link_attempted') is True
            and report.get('address_sanitizer_enabled') is sanitize
            and report.get('program_ir_cached') is False
            and report.get('runtime_reannotated') is False
            and report.get('mode') == ('asan' if sanitize else 'native')
            and report.get('optimization') == optimization
            and report.get('retention_errors') == [],
            'effective program sanitizer/link provenance mismatch')
    require(report.get('link_flags') == requested_flags(optimization, sanitize)
            and report.get('lto_flags') == [], 'requested flags changed')
    require(host_path(report.get('artifact_directory', '')).resolve() == directory.resolve(),
            'link artifact directory mismatch')
    raw = retained_path(directory, 'program.raw.ll').read_bytes()
    raw_hash = hashlib.sha256(raw).hexdigest()
    raw_original = verify_binding(directory, report.get('raw_program_input'), immediate=True)
    require(report.get('raw_program') == raw_original and report.get('raw_sha256') == raw_hash,
            'transient raw generated program binding mismatch')
    linked = retained_path(directory, 'program.asan.ll').read_bytes() if sanitize else raw
    if sanitize:
        require(linked == instrument_address_sanitizer(raw.decode()).encode() and linked != raw,
                'linked program is not canonical ASan annotation')
    program = report.get('program_input')
    linked_original = verify_binding(directory, program, immediate=True)
    require(program.get('role') == 'program' and program.get('format') == 'llvm'
            and program.get('retained') == ('program.asan.ll' if sanitize else 'program.raw.ll')
            and report.get('linked_program_sha256') == hashlib.sha256(linked).hexdigest(),
            'linked generated program changed')
    require((sanitize and host_path(linked_original).resolve() ==
             (directory / 'program.asan.ll').resolve())
            or (not sanitize and linked_original == raw_original),
            'actual generated input route mismatch')
    command, actual = report.get('command'), report.get('actual_command')
    require(isinstance(command, list) and command and all(isinstance(value, str) for value in command)
            and isinstance(actual, list) and actual == command + [
                '-o', report.get('staged_requested_path')], 'actual staged-output argv mismatch')
    require(command[0] == report.get('compiler_selected_command')
            and command[1:1+len(report['link_flags'])] == report['link_flags'],
            'selected compiler or link flags changed')
    require(effective_optimization(actual[1:-2]) == optimization
            and address_sanitizer_enabled(actual[1:-2]) is sanitize
            and not any(value.startswith('@') for value in actual[1:-2]),
            'actual argv overrides requested optimization or sanitizer mode')
    # The requested prefix owns both ASan and UBSan. Additional enable/disable
    # options could alter either set, including a disable followed by re-enable;
    # reject them instead of treating ASan's state as proof of the entire set.
    sanitizer_options = lambda values: [
        value for value in values if value.startswith(('-fsanitize=', '-fno-sanitize='))]
    require(sanitizer_options(actual[1:-2]) == sanitizer_options(report['link_flags']),
            'actual argv changes the exact requested sanitizer options')
    ir_inputs = [value for value in command[1:] if value.endswith(('.ll', '.bc'))]
    require(ir_inputs == [linked_original], 'extra or missing program/runtime LLVM input')
    inputs = report.get('inputs')
    require(isinstance(inputs, list) and all(isinstance(row, dict) for row in inputs),
            'native input inventory missing')
    runtimes = [row for row in inputs if row.get('role') == 'runtime']
    require(len(runtimes) == 1 and runtimes[0].get('retained') == 'runtime.o'
            and runtimes[0].get('format') == 'native_object'
            and runtimes[0].get('original', '').endswith('.o'),
            'runtime must be one native object, not LLVM')
    native_originals = [verify_binding(directory, row, immediate=True) for row in inputs]
    require(len(native_originals) == len(set(native_originals))
            and all(row.get('role') in ('runtime', 'provider')
                    and row.get('format') in ('native_object', 'native_input') for row in inputs),
            'ambiguous native link inventory')
    actual_native = [value for value in command[1:] if not value.startswith('-')
                     and value.endswith(('.o', '.obj', '.a', '.lib', '.so', '.dylib'))]
    require(actual_native == native_originals, 'unrepresented or unused native link input')
    tools, bindings = report.get('tools'), report.get('tool_bindings')
    names = {'clang-driver.py', 'sanitizer_llvm.py', 'clang.bin'}
    require(isinstance(tools, dict) and set(tools) == names
            and isinstance(bindings, dict) and set(bindings) == names,
            'canonical helper or compiler evidence missing')
    for name in names:
        verify_binding(directory, bindings[name])
        require(bindings[name]['retained'] == name and tools[name] == digest(directory / name),
                'retained tool binding mismatch')
    for name in ('clang-driver.py', 'sanitizer_llvm.py'):
        require(tools[name] == digest(ROOT / 'tools' / name), 'canonical link helper mismatch')
    compiler = report.get('compiler_pre_link')
    require(isinstance(compiler, dict)
            and compiler.get('selected_command') == command[0]
            and compiler.get('resolved_path') == report.get('compiler') ==
                bindings['clang.bin']['original']
            and compiler.get('sha256') == tools['clang.bin']
            and isinstance(report.get('compiler_version'), str) and report['compiler_version'],
            'actual compiler bytes/version mismatch')
    if compiler_identity is not None:
        require(compiler['sha256'] == compiler_identity, 'selected compiler byte identity changed')
    outputs = []
    for key, basename in (('staged_output', 'program.staged' + binary.suffix),
                          ('final_output', 'program' + binary.suffix)):
        row = report.get(key)
        require(isinstance(row, dict) and row.get('retained') == basename
                and isinstance(row.get('path'), str) and host_path(row['path']).is_absolute(),
                'staged/final output identity absent')
        path = retained_path(directory, basename)
        require(exact_integer(row.get('bytes'), minimum=1)
                and path.stat().st_size == row['bytes'] and row.get('sha256') == digest(path),
                'staged/final output bytes mismatch')
        outputs.append((row['sha256'], row['bytes']))
    staged = report['staged_output']['path']
    require(staged in (report['staged_requested_path'], report['staged_requested_path'] + '.exe'),
            'actual staged output path mismatch')
    require(host_path(report['final_output']['path']).resolve() == binary.resolve()
            and outputs[0] == outputs[1] == (digest(binary), binary.stat().st_size)
            and report.get('binary_sha256') == digest(binary), 'final binary binding mismatch')
    return report


def snapshot_inputs():
    paths = [ROOT / 'minyar', ROOT / 'Makefile']
    for name in ('bootstrap', 'compiler', 'library', 'runtime', 'tools',
                 'build-support', 'scripts'):
        paths += [path for path in sorted((ROOT / name).rglob('*'))
                  if path.is_file() and path.suffix in
                  ('.min', '.c', '.h', '.m', '.py', '.sh', '.mk', '.patch', '.inc', '.S', '.s')]
    # native_object hashes every monocypher glob entry, including LICENCE.md.
    paths += [path for path in sorted((ROOT / 'vendor').rglob('*')) if path.is_file()]
    paths += [ROOT / name for name in BINARIES.values()]
    paths += [ROOT / row[1] for row in DRIVERS]
    paths += [Path(__file__), ROOT / 'tests/quic-rfc-harness.py',
              ROOT / 'tests/tls-local.py', ROOT / 'tests/test_evidence.py',
              ROOT / 'tests/clang_helpers.py', ROOT / 'tests/quic_protocol_artifacts.py',
              ROOT / 'tests/quic-protocol-artifacts.py',
              ROOT / 'tests/interop/qns/endpoint.py']
    require(all(not path.is_symlink() for path in paths), 'symlink source snapshot input')
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in sorted(set(paths))}


def inventory(directory):
    require(directory.is_dir() and not directory.is_symlink(), 'missing inventory directory')
    paths = list(sorted(directory.rglob('*')))
    require(all(not path.is_symlink() for path in paths), 'symlink artifact inventory entry')
    return {path.relative_to(directory).as_posix(): digest(path)
            for path in paths if path.is_file()}


def bound_copy(source, target):
    before = digest(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    retained, after = digest(target), digest(source)
    require(before == retained == after, 'source before/copy/after changed: ' + str(source))
    return {'before': before, 'retained': retained, 'after': after,
            'source': str(source.resolve()), 'copy': str(target.resolve())}


def verify_driver_artifacts(directory, kind, parsed, cases, binaries, source_inputs, observed_tools=None):
    manifest = json.loads((directory / 'manifest.json').read_text())
    require(exact_integer(manifest.get('schema_version')) and manifest['schema_version'] == 1
            and manifest.get('status') == 'passed'
            and manifest.get('finalization_errors') == []
            and manifest.get('unhashed_files') == [],
            'author artifact manifest did not pass complete retention')
    require(json.loads((directory / 'results.json').read_text()) == parsed,
            'printed author results differ from retained results')
    cases = cases if cases is not None else parsed.get('declared_cases')
    require(isinstance(cases, list) and cases and len(cases) == len(set(cases))
            and all(isinstance(case, str) and case for case in cases),
            'author artifact case inventory missing')
    require(manifest.get('declared_cases') == parsed.get('declared_cases') == cases,
            'declared case artifact inventory mismatch')
    actual = inventory(directory)
    actual.pop('manifest.json', None)
    require(manifest.get('files') == actual, 'author exact file hash inventory mismatch')
    sizes = {name: retained_path(directory, name).stat().st_size for name in actual}
    require(manifest.get('file_bytes') == sizes
            and all(exact_integer(value, minimum=0) for value in manifest['file_bytes'].values()),
            'author exact file size inventory mismatch')
    inputs = manifest.get('inputs')
    expected = {str((ROOT / name).resolve()): value for name, value in source_inputs.items()}
    expected.update({str(path.resolve()): digest(path) for path in binaries.values()})
    require(isinstance(inputs, dict) and inputs and all(
        key in expected and value == expected[key] for key, value in inputs.items()),
        'author source/binary input binding mismatch')
    required = {str((ROOT / row[1]).resolve()) for row in DRIVERS if row[0] == kind}
    required |= {str((ROOT / 'tests/quic_protocol_artifacts.py').resolve()),
                 str((ROOT / 'tests/test_evidence.py').resolve())}
    required |= {str((ROOT / 'tests/tls-local.py').resolve())}
    required |= {str((ROOT / BINARIES[name]).resolve()) for name in (
        (kind,) if kind in ('migration', 'cipher') else ('client', 'server') if kind == 'local'
        else ('server',))}
    if kind in ('local', 'vn'):
        required.add(str((ROOT / 'tests/interop/qns/endpoint.py').resolve()))
    required |= {str(binaries[name].resolve()) for name in (
        (kind,) if kind in ('migration', 'cipher') else ('client', 'server') if kind == 'local'
        else ('server',))}
    require(required <= set(inputs), 'author required source/binary inputs omitted')
    commands, endpoints = manifest.get('commands'), manifest.get('endpoint_commands')
    require(isinstance(commands, list) and isinstance(endpoints, list),
            'author command/endpoint observations missing')
    def raw_file(row, stream):
        path = host_path(row.get(stream + '_path', ''))
        require(path.is_absolute() and path.resolve().is_relative_to(directory.resolve()),
                'author raw output escaped artifact directory')
        relative = path.relative_to(directory).as_posix()
        require(relative in actual and row.get(stream + '_sha256') == actual[relative]
                and exact_integer(row.get(stream + '_bytes'), minimum=0)
                and row[stream + '_bytes'] == sizes[relative], 'author raw output byte binding mismatch')
        return relative
    for row in commands:
        require(isinstance(row, dict) and isinstance(row.get('command'), list)
                and row['command'] and all(isinstance(value, str) for value in row['command'])
                and isinstance(row.get('cwd'), str) and host_path(row['cwd']).is_absolute()
                and exact_integer(row.get('timeout'), minimum=1)
                and exact_integer(row.get('returncode')) and row.get('returncode') == row.get('status')
                and exact_integer(row.get('status')) and row['status'] == 0 and row.get('timed_out') is False
                and sha256_value(row.get('executable_sha256')), 'author command observation incomplete')
        if row.get('phase') == 'certificate-fixture' and observed_tools is not None:
            identity = next((tool for tool in observed_tools.values()
                             if tool['source'] == str(host_path(row.get('executable', '')).resolve())), None)
            require(identity is not None and row['executable_sha256'] == identity['before'],
                    'certificate tool differs from recorded executable bytes/version')
        for stream in ('stdout', 'stderr'):
            raw_file(row, stream)
    for row in endpoints:
        require(isinstance(row, dict) and isinstance(row.get('argv'), list) and row['argv']
                and all(isinstance(value, str) for value in row['argv'])
                and exact_integer(row.get('status'))
                and exact_integer(row.get('peer_timeout_seconds'))
                and row['peer_timeout_seconds'] == (3 if kind == 'vn' else 180)
                and exact_integer(row.get('readiness_timeout_seconds'))
                and row['readiness_timeout_seconds'] == 10
                and exact_integer(row.get('shutdown_grace_seconds'))
                and row['shutdown_grace_seconds'] == 5
                and type(row.get('owned_termination_requested')) is bool
                and row.get('readiness_timed_out', False) is False and row.get('timed_out') is False,
                'author endpoint status/deadline observation incomplete')
        endpoint = host_path(row['argv'][0]).resolve()
        require(str(endpoint) in expected and row.get('binary_sha256') == expected[str(endpoint)],
                'author endpoint binary binding mismatch')
        for stream in ('stdout', 'stderr'):
            raw_file(row, stream)
        output = host_path(row['stdout_path']).read_bytes()
        first = output.splitlines(keepends=True)[0] if output else b''
        require(normalized_text(first) == 'QNS server ready\n'
                and row.get('ready_line_sha256') == hashlib.sha256(first).hexdigest(),
                'exact endpoint readiness marker changed')
        verify_server_lifecycle(row, raw_file)
    rows = manifest.get('case_inventory')
    require(isinstance(rows, list) and all(isinstance(row, dict) for row in rows)
            and [row.get('case') for row in rows] == cases
            and parsed.get('case_inventory') == rows, 'author case references missing/reordered')
    referenced_commands, referenced_endpoints = set(), set()
    for row in rows:
        case = row['case']
        ci, ei, files = row.get('command_indices'), row.get('endpoint_indices'), row.get('files')
        require(isinstance(ci, list) and isinstance(ei, list)
                and all(exact_integer(index, minimum=0, maximum=len(commands)-1) for index in ci)
                and all(exact_integer(index, minimum=0, maximum=len(endpoints)-1) for index in ei)
                and len(ci) == len(set(ci)) and len(ei) == len(set(ei)),
                'invalid per-case command/endpoint references')
        require(isinstance(files, list) and files and len(files) == len(set(files))
                and all(isinstance(name, str) and name in actual for name in files),
                'missing/wrong per-case fixture/hash references')
        roles = row.get('file_roles')
        required_roles = {'certificates', 'raw_output'}
        if kind == 'local':
            required_roles |= {'payloads', 'downloads', 'keylogs'}
        elif kind == 'vn':
            required_roles |= {'packets', 'keylogs'}
        require(isinstance(roles, dict) and set(roles) == required_roles
                and all(isinstance(values, list) and len(values) == len(set(values))
                        and all(isinstance(name, str) and name in actual for name in values)
                        for values in roles.values())
                and roles['certificates'] and roles['raw_output']
                and sorted(set(name for values in roles.values() for name in values)) == files,
                'per-case role/files inventory is incomplete')
        if kind == 'local':
            require(roles['payloads'] and roles['downloads'] and roles['keylogs'],
                    'local payload/download/keylog evidence omitted')
        own_commands = {i for i, command in enumerate(commands) if command.get('case') == case}
        prerequisites = {i for i, command in enumerate(commands)
                         if command.get('phase') == 'certificate-fixture'}
        own_endpoints = {i for i, endpoint in enumerate(endpoints) if endpoint.get('case') == case}
        require(set(ci) == own_commands | prerequisites and set(ei) == own_endpoints
                and (own_commands or own_endpoints), 'per-case execution references incomplete')
        require(host_path(row.get('fixture_workspace', '')).resolve() ==
                host_path(manifest.get('workspace', '')).resolve(),
                'per-case fixture workspace mismatch')
        def observation_raw(observation, endpoint=False):
            raw = [raw_file(observation, stream) for stream in ('stdout', 'stderr')]
            if endpoint:
                raw += verify_server_lifecycle(observation, raw_file)
            return raw
        for index in ci:
            require(all(name in files for name in observation_raw(commands[index])),
                    'per-case raw command files missing')
        for index in ei:
            require(all(name in files for name in observation_raw(endpoints[index], True)),
                    'per-case raw endpoint/termination files missing')
        expected_raw = sorted(set(name
            for observation, endpoint in [(commands[index], False) for index in ci] +
                                         [(endpoints[index], True) for index in ei]
            for name in observation_raw(observation, endpoint)))
        require(roles['raw_output'] == expected_raw, 'raw per-case role inventory mismatch')
        result_row = next((result for result in parsed.get('results', [])
                           if result.get('case') == case), None)
        if kind in ('migration', 'cipher', 'local'):
            require(len(own_commands) == 1, 'ambiguous per-case protocol execution')
            observation = commands[next(iter(own_commands))]
            executable = host_path(observation['command'][0]).resolve()
            selected = binaries[kind] if kind in ('migration', 'cipher') else binaries['client']
            require(executable == selected.resolve()
                    and observation['executable_sha256'] == digest(selected)
                    and observation['timeout'] == (180 if kind == 'local' else 60),
                    'per-case binary/timeout identity mismatch')
            prefix = 'client_' if kind == 'local' else ''
            require(result_row is not None
                    and result_row[prefix+'stdout'] ==
                        normalized_text(host_path(observation['stdout_path']).read_bytes())
                    and result_row[prefix+'stderr'] ==
                        normalized_text(host_path(observation['stderr_path']).read_bytes()),
                    'printed protocol result differs from retained raw bytes')
        if kind == 'local':
            require(len(own_endpoints) == 1, 'local server observation missing')
            observation = endpoints[next(iter(own_endpoints))]
            output = host_path(observation['stdout_path']).read_bytes()
            greeting = output.splitlines(keepends=True)[0]
            require(result_row['server_stdout'] == normalized_text(output[len(greeting):])
                    and result_row['server_stderr'] ==
                        normalized_text(host_path(observation['stderr_path']).read_bytes()),
                    'printed server result differs from retained raw bytes')
        case_command = commands[next(iter(own_commands))]['command'] if own_commands else None
        require(len(own_endpoints) <= 1, 'ambiguous per-case server invocation')
        case_endpoint = endpoints[next(iter(own_endpoints))]['argv'] if own_endpoints else None
        verify_case_invocation(kind, case, case_command, case_endpoint, roles, directory, binaries)
        referenced_commands.update(ci)
        referenced_endpoints.update(ei)
    require(referenced_commands == set(range(len(commands)))
            and referenced_endpoints == set(range(len(endpoints))), 'unreferenced author observations')
    if kind == 'vn':
        for stream in ('request', 'response'):
            relative = parsed.get(stream + '_path')
            path = retained_path(directory, relative)
            require(relative in rows[0]['files'] and path.stat().st_size == parsed[stream + '_bytes']
                    and digest(path) == parsed[stream + '_sha256'],
                    'version-negotiation packet bytes not retained')
    return manifest


def retention_attempt(report, phase, action):
    try:
        return action()
    except Exception as error:
        report['passed'] = False
        report['retention_errors'].append({'phase': phase, 'error': repr(error)})
        return None


def write_report(directory, report):
    try:
        value = json.dumps(report, indent=2) + '\n'
        (directory / 'manifest.json').write_text(value)
    except Exception as error:
        report['passed'] = False
        report['retention_errors'].append({'phase': 'manifest-write', 'error': repr(error)})
        try:
            (directory / 'manifest-retention-error.json').write_text(
                json.dumps(report, indent=2) + '\n')
        except Exception:
            pass


def run_gate(directory, sanitize, source_commit=None):
    # Retain a failure manifest even when snapshot/frontend/Evidence setup fails.
    report = {'schema_version': 1, 'passed': False, 'sanitize': sanitize,
              'optimization': list(OPTIMIZATIONS), 'platform': platform.platform(),
              'source_commit': source_commit, 'source_before': {},
              'source_copies': {}, 'frontends': {}, 'external_tools': {}, 'commands': [], 'links': [],
              'drivers': [], 'retention_errors': [],
              'runtime_scope': 'Observed native link object; compile count is not independently measured.'}
    write_report(directory, report)
    evidence = None
    before = None
    completed = False
    try:
        before = snapshot_inputs()
        report['source_before'] = before
        for name, value in before.items():
            row = bound_copy(ROOT / name, directory / 'source' / name)
            require(row['before'] == value, 'source changed before retention')
            report['source_copies'][name] = row
        for name in ('minyarc', 'minyarc-callbacks', 'minyarc-errors-request', 'minyarc-errors'):
            path = ROOT / 'build' / (name + ('.exe' if windows_host() else ''))
            if not path.is_file():
                path = ROOT / 'build' / name
            require(path.is_file(), 'public frontend prerequisite absent: ' + name)
            report['frontends'][name] = bound_copy(path, directory / 'frontends' / path.name)
        clang = os.environ.get('MINYAR_TEST_CLANG',
                               os.environ.get('MINYAR_CLANG', os.environ.get('LLVM_CC', 'clang')))
        environment = dict(os.environ, MAKEFLAGS='-j1', MINYAR_CLANG=clang)
        environment.pop('PYTHONOPTIMIZE', None)
        environment.pop('MINYAR_LINK_ARTIFACTS', None)
        environment.update(ASAN_OPTIONS=asan_leak_options() + ':halt_on_error=1',
                           UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
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
            # This only selects the existing Evidence process-tree portability
            # route. It changes no readiness, deadline, assertion or output.
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
                    row.update(label=label, wall_seconds=time.monotonic() - started)
                    for stream in ('stdout', 'stderr'):
                        def retain_stream(stream=stream):
                            encoded = row.get(stream + '_base64')
                            if encoded is not None:
                                raw = base64.b64decode(encoded, validate=True)
                                path = directory / (label + '.' + stream)
                                path.write_bytes(raw)
                                row[stream + '_path'] = path.name
                                row[stream + '_sha256'] = digest(path)
                                row[stream + '_bytes'] = len(raw)
                        retention_attempt(report, label + '-' + stream, retain_stream)
                write_report(directory, report)
            require(exact_integer(result.returncode), 'child status is not an integer')
            if result.returncode:
                raise subprocess.CalledProcessError(result.returncode, command,
                                                    output=result.stdout, stderr=result.stderr)
            return result

        version = run('clang-version', [clang, '--version'], environment, 30)
        report['compiler_version'] = version.stdout.decode(errors='replace')
        report['compiler_sha256'] = evidence.commands[-1].get('executable_sha256')
        require(sha256_value(report['compiler_sha256']), 'selected compiler identity missing')
        report['external_tools']['clang'] = bound_copy(
            host_path(evidence.commands[-1]['executable']), directory / 'tools' / 'clang.bin')
        require(report['external_tools']['clang']['before'] == report['compiler_sha256'],
                'selected compiler changed while retaining')
        tool_commands = [('python', [sys.executable, '--version']), ('openssl', ['openssl', 'version'])]
        if windows_host() and os.name != 'nt':
            tool_commands.append(('cygpath', ['cygpath', '--version']))
        for name, command in tool_commands:
            result = run(name + '-version', command, environment, 30)
            observation = evidence.commands[-1]
            row = bound_copy(host_path(observation['executable']), directory / 'tools' / (name + '.bin'))
            require(row['before'] == observation['executable_sha256'], 'version tool changed while retaining')
            row['version_stdout'] = result.stdout.decode(errors='replace')
            row['version_stderr'] = result.stderr.decode(errors='replace')
            report['external_tools'][name] = row
        import shlex
        for opt in OPTIMIZATIONS:
            flags = requested_flags(opt, sanitize)
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
                link_report = verify_link(link, binary, sanitize, opt, report['compiler_sha256'])
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
                cases = declared_cases(ROOT / source, symbol) if symbol else ['reserved-version']
                verify_result(kind, parsed, cases, binaries, ROOT / BINARIES.get(kind, source))
                child = verify_driver_artifacts(child_artifacts, kind, parsed, cases, binaries, before, report['external_tools'])
                report['drivers'].append(dict(kind=kind, optimization=opt, cases=cases,
                                              result=parsed, manifest=child))
                print('QUIC RFC O' + opt + ' ' + kind + ' passed', flush=True)
        completed = True
    except BaseException as error:
        report['error'] = {'type': type(error).__name__, 'message': str(error)}
        if isinstance(error, subprocess.CalledProcessError):
            report['failed_child_status'] = error.returncode
        raise
    finally:
        if evidence is not None:
            report['commands'] = evidence.commands
        after = retention_attempt(report, 'source-after', snapshot_inputs)
        if after is not None:
            report['source_after'] = after
        retained = retention_attempt(report, 'source-copy-inventory',
                                     lambda: inventory(directory / 'source'))
        if retained is not None:
            report['retained_inputs'] = retained
        for name, row in report['frontends'].items():
            current = retention_attempt(report, 'frontend-after-' + name,
                                        lambda row=row: digest(host_path(row['source'])))
            copied = retention_attempt(report, 'frontend-copy-' + name,
                                       lambda row=row: digest(host_path(row['copy'])))
            row.update(final_source=current, final_copy=copied)
        for name, row in report['external_tools'].items():
            row['final_source'] = retention_attempt(report, 'tool-after-' + name,
                lambda row=row: digest(host_path(row['source'])))
            row['final_copy'] = retention_attempt(report, 'tool-copy-' + name,
                lambda row=row: digest(host_path(row['copy'])))
        tools_match = bool(report['external_tools']) and all(
            row['before'] == row['retained'] == row['after'] ==
            row.get('final_source') == row.get('final_copy')
            for row in report['external_tools'].values())
        fronts_match = bool(report['frontends']) and all(
            row['before'] == row['retained'] == row['after'] ==
            row.get('final_source') == row.get('final_copy')
            for row in report['frontends'].values())
        report['passed'] = (completed and before is not None and after == before == retained
                            and fronts_match and tools_match and not report['retention_errors'])
        files = retention_attempt(report, 'artifact-inventory', lambda: inventory(directory))
        if files is not None:
            report['artifacts'] = {name: value for name, value in files.items()
                                   if name not in ('manifest.json', 'manifest-retention-error.json')}
        write_report(directory, report)
    require(report['passed'], 'input/frontend provenance or evidence retention failed')
    return 0


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
    return run_gate(directory, options.sanitize, os.environ.get('MINYAR_SOURCE_COMMIT'))


if __name__ == '__main__':
    raise SystemExit(main())
