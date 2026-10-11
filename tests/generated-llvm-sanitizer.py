#!/usr/bin/env python3
"""Exercise generated LLVM accesses through the public Clang link driver.

The unsafe control injects one volatile freed-byte store into actual compiler
output. Compile/link must succeed; only the instrumented access may reject it.
Every command and successful/failing workspace remains in --artifacts.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from clang_helpers import asan_leak_options
from test_evidence import terminate_process_tree

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / 'tools/clang-driver.py'
CLANG = os.environ.get('MINYAR_TEST_CLANG', os.environ.get('LLVM_CC', 'clang'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Observation:
    def __init__(self, directory):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=False)
        self.manifest = {'schema': 1, 'commands': [], 'files': {},
                         'source_commit': os.environ.get('MINYAR_SOURCE_COMMIT'),
                         'source_inputs': {}}
        for path in (DRIVER, ROOT / 'tests/generated-llvm-sanitizer.min',
                     ROOT / 'tests/generated-llvm-sanitizer.py',
                     ROOT / 'tests/llvm_sanitizer.py', ROOT / 'tools/sanitizer_llvm.py',
                     ROOT / 'runtime/minyar_runtime.c'):
            self.manifest['source_inputs'][path.relative_to(ROOT).as_posix()] = digest(path)
        for path in sorted((ROOT / 'runtime').rglob('*.h')):
            self.manifest['source_inputs'][path.relative_to(ROOT).as_posix()] = digest(path)
        for label, path in (('minyarc', ROOT / 'build/minyarc'),
                            ('clang', Path(shutil.which(CLANG)).resolve())):
            shutil.copyfile(path, directory / label)
            self.manifest['files'][label] = digest(path)
        self.save()

    def save(self):
        (self.directory / 'manifest.json').write_text(json.dumps(self.manifest, indent=2) + '\n')

    def run(self, label, command, *, environment=None):
        env = dict(os.environ, ASAN_OPTIONS=asan_leak_options() + ':halt_on_error=1',
                   UBSAN_OPTIONS='halt_on_error=1')
        env.update(environment or {})
        started = time.monotonic()
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   env=env, start_new_session=True)
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=180)
        except subprocess.TimeoutExpired:
            timed_out = True
            terminate_process_tree(process)
            stdout, stderr = process.communicate()
        for suffix, content in (('stdout', stdout), ('stderr', stderr)):
            path = self.directory / (label + '.' + suffix)
            path.write_bytes(content)
            self.manifest['files'][path.name] = hashlib.sha256(content).hexdigest()
        self.manifest['commands'].append(dict(label=label, argv=list(map(str, command)),
                status=process.returncode, timed_out=timed_out,
                seconds=time.monotonic()-started, environment=environment or {},
                stdout_sha256=hashlib.sha256(stdout).hexdigest(),
                stderr_sha256=hashlib.sha256(stderr).hexdigest()))
        self.save()
        assert not timed_out, label + ' timed out'
        return process.returncode, stdout, stderr

    def success(self, label, command, **kwargs):
        status, stdout, stderr = self.run(label, command, **kwargs)
        assert status == 0, (label, status, stderr.decode(errors='replace'))
        return stdout, stderr


def unsafe_access(observation):
    out = observation.directory
    source = ROOT / 'tests/generated-llvm-sanitizer.min'
    raw = out / 'compiler.raw.ll'
    observation.success('compiler', [str(ROOT/'build/minyarc'), str(source), str(raw),
                                     '--bounded-owners', '32'])
    text = raw.read_text()
    assert len(re.findall(r'^define i32 @main\(', text, re.M)) == 1
    marker = re.search(r'(^define i32 @main\([^\n]*\{\nentry:\n)', text, re.M)
    assert marker, 'generated main entry changed'
    text = text[:marker.end()] + '  call void @".minyar.bad(quoted)"()\n' + text[marker.end():]
    for declaration in ('declare ptr @malloc(i64)', 'declare void @free(ptr)'):
        if declaration not in text:
            text += '\n' + declaration + '\n'
    text += '''
define void @".minyar.bad(quoted)"() {
entry:
  %bad = call ptr @malloc(i64 8)
  call void @free(ptr %bad)
  store volatile i8 7, ptr %bad
  ret void
}
'''
    llvm = out / 'unsafe.raw.ll'
    llvm.write_text(text)
    native_source = out / 'runtime.c'
    native_source.write_text('#define MINYAR_SYSTEM_HEAP 1\n#define MINYAR_RC_POLL_BUDGET 32\n#include "minyar_runtime.c"\n')
    runtime = out / 'runtime.o'
    options = '-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer'
    environment = {'MINYAR_CLANG': CLANG, 'MINYAR_RUNTIME_FLAGS': options,
                   'MINYAR_CLANG_FLAGS': options, 'MINYAR_NATIVE_FLAGS': options,
                   'MINYAR_LINK_ARTIFACTS': str(out / 'link-inputs')}
    observation.success('runtime-compile', [sys.executable, str(DRIVER), 'compile',
            '-iquote', str(ROOT/'runtime'), '-c', str(native_source), '-o', str(runtime)],
            environment=environment)
    before = {path.name: digest(path) for path in (raw, llvm, runtime)}
    binary = out / ('unsafe.exe' if os.name == 'nt' else 'unsafe')
    observation.success('public-link', [sys.executable, str(DRIVER), 'link', str(ROOT),
            str(llvm), str(runtime), str(binary), '0'], environment=environment)
    status, stdout, stderr = observation.run('unsafe-run', [str(binary)])
    observation.manifest['files'].update({path.name: digest(path)
                                        for path in (raw, llvm, runtime, binary)})
    observation.manifest['control'] = dict(compile_status=0, link_status=0,
            unsafe_status=status, unsafe_stdout=stdout.decode(errors='replace'),
            expected='AddressSanitizer: heap-use-after-free', input_before=before,
            input_after={path.name:digest(path) for path in (raw,llvm,runtime)})
    observation.save()
    assert before == {path.name:digest(path) for path in (raw,llvm,runtime)}
    assert status != 0 and b'AddressSanitizer: heap-use-after-free' in stderr, (
            'public link driver omitted generated-access instrumentation', status, stdout, stderr)
    assert b'42\n' not in stdout

    retained = json.loads((out / 'link-inputs/manifest.json').read_text())
    assert retained['address_sanitizer_enabled'] and not retained['runtime_reannotated']
    assert retained['raw_sha256'] == before[llvm.name]
    assert (out / 'link-inputs/program.raw.ll').read_bytes() == llvm.read_bytes()
    assert (out / 'link-inputs/runtime.o').read_bytes() == runtime.read_bytes()
    assert retained['linked_program_sha256'] != retained['raw_sha256']
    assert retained['link_status'] == 0
    assert digest(out / 'link-inputs/program.asan.ll') == retained['linked_program_sha256']
    observation.manifest['instrumented_access_proof'] = retained
    observation.save()



def helper_controls(observation):
    spec = importlib.util.spec_from_file_location('canonical_sanitizer',
                                                ROOT / 'tools/sanitizer_llvm.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    spec = importlib.util.spec_from_file_location('compat_sanitizer',
                                                ROOT / 'tests/llvm_sanitizer.py')
    compatibility = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compatibility)
    assert compatibility.instrument_address_sanitizer is helper.instrument_address_sanitizer or \
            compatibility.instrument_address_sanitizer.__code__.co_code == helper.instrument_address_sanitizer.__code__.co_code
    variants = [
        'define void @sanitize_address() {\n  ret void\n}\n',
        'define void @"name({escaped\\22})"(ptr %"arg(name)") "sanitize_address"="value" {\n  ret void\n}\n',
        'define void @plain() sanitize_address {\n  ret void\n}\n',
        'define void @group() #0 {\n  ret void\n}\nattributes #0 = { sanitize_address }\n',
        'define void @group() #0 {\n  ret void\n}\nattributes #0 = { "sanitize_address"="text" }\n',
        'define void @crlf() {\r\n  ret void\r\n}\r\n',
        'define void @attr() alignstack(16) {\n  ret void\n}\n',
        'define void @personality() personality ptr @sanitize_address {\n ret void\n}\n',
    ]
    observed = []
    for index, raw in enumerate(variants):
        transformed = helper.instrument_address_sanitizer(raw)
        assert helper.instrument_address_sanitizer(transformed) == transformed
        (observation.directory / f'header-{index}.raw.ll').write_bytes(raw.encode())
        (observation.directory / f'header-{index}.asan.ll').write_bytes(transformed.encode())
        observed.append(dict(index=index, raw_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                             annotated_sha256=hashlib.sha256(transformed.encode()).hexdigest()))
    for raw in ('declare void @only()\n', 'define void @bad( {\n',
                'define void @multiline(\n) {\n}\n', 'define void @"bad() {\n',
                'define void @bad() #9 {\n}\n', 'define void @bad() {\n}\ndefine void @no_body()\n'):
        try:
            helper.instrument_address_sanitizer(raw)
        except ValueError:
            pass
        else:
            raise AssertionError('malformed function header accepted: ' + repr(raw))
    flag_controls = [
        ([], False), (['-fsanitize=undefined'], False),
        (['-fsanitize=address'], True),
        (['-fsanitize=address', '-fno-sanitize=address'], False),
        (['-fsanitize=address,undefined', '-fno-sanitize=all'], False),
        (['-fno-sanitize=all', '-fsanitize=address'], True),
        (['-fsanitize=address', '-fno-sanitize=undefined'], True),
    ]
    for flags, expected in flag_controls:
        assert helper.address_sanitizer_enabled(flags) == expected, flags
    raw = 'declare void @no_definitions()\n'
    untouched = observation.directory / 'off-unvalidated.ll'
    untouched.write_text(raw)
    helper.prepare_llvm_for_link(untouched, ['-fsanitize=address', '-fno-sanitize=all'])
    assert untouched.read_bytes() == raw.encode()
    observation.manifest['header_controls'] = observed
    observation.manifest['flag_controls'] = flag_controls
    observation.save()


def link_controls(observation):
    out = observation.directory
    original = out / 'compiler.raw.ll'
    raw_before = original.read_bytes()
    native = out / 'ordinary-runtime.o'
    source = out / 'runtime.c'
    observation.success('ordinary-runtime-compile', [sys.executable, str(DRIVER), 'compile',
            '-iquote', str(ROOT/'runtime'), '-c', str(source), '-o', str(native)],
            environment={'MINYAR_CLANG': CLANG, 'MINYAR_RUNTIME_FLAGS': '-O1'})
    native_before = digest(native)
    controls = [
        ('ordinary', '-O1', False),
        ('disabled-address', '-O1 -fsanitize=address -fno-sanitize=address', False),
        ('disabled-all', '-O1 -fsanitize=address,undefined -fno-sanitize=all', False),
        ('reenabled', '-O1 -fno-sanitize=all -fsanitize=address,undefined', True),
        ('enabled', '-O1 -fsanitize=address,undefined', True),
    ]
    for label, flags, enabled in controls:
        binary = out / (label + ('.exe' if os.name == 'nt' else ''))
        evidence = out / (label + '-inputs')
        environment = {'MINYAR_CLANG': CLANG, 'MINYAR_CLANG_FLAGS': flags,
                       'MINYAR_LINK_ARTIFACTS': str(evidence)}
        observation.success(label + '-link', [sys.executable, str(DRIVER), 'link', str(ROOT),
                str(original), str(native), str(binary), '0'], environment=environment)
        stdout, stderr = observation.success(label + '-run', [str(binary)])
        assert stdout == b'42\n' and not stderr, (label, stdout, stderr)
        manifest = json.loads((evidence / 'manifest.json').read_text())
        assert manifest['address_sanitizer_enabled'] == enabled
        assert not manifest['runtime_reannotated'] and not manifest['program_ir_cached']
        assert (evidence / 'program.raw.ll').read_bytes() == raw_before
        assert digest(evidence / 'runtime.o') == native_before
        if enabled:
            assert manifest['linked_program_sha256'] != manifest['raw_sha256']
        else:
            assert manifest['linked_program_sha256'] == manifest['raw_sha256']
            assert not (evidence / 'program.asan.ll').exists()
        # Reusing an evidence generation must fail without replacing its bytes.
        if label == 'enabled':
            status, _, stderr = observation.run('artifact-collision', [sys.executable, str(DRIVER),
                    'link', str(ROOT), str(original), str(native), str(binary), '0'],
                    environment=environment)
            assert status != 0 and b'File exists' in stderr
    assert original.read_bytes() == raw_before and digest(native) == native_before

    # A real public link compiles the native bridge once. Program annotation
    # cannot change its cache key; changing a native header must change it.
    project = out / 'native-project'
    (project / 'runtime/native').mkdir(parents=True)
    (project / 'runtime/value.h').write_text('#define VALUE 1\n')
    (project / 'runtime/native/net.c').write_text('#include "../value.h"\nint fixture(void) { return VALUE; }\n')
    llvm = out / 'native-cache.raw.ll'
    llvm.write_bytes(b'; minyar-native-library: net\n' + raw_before)
    identities = []
    stamps = []
    for index in range(3):
        if index == 2:
            (project / 'runtime/value.h').write_text('#define VALUE 2\n')
        evidence = out / f'cache-{index}-inputs'
        observation.success(f'cache-link-{index}', [sys.executable, str(DRIVER), 'link', str(project),
                str(llvm), str(native), str(out/f'cache-{index}'), '0'],
                environment={'MINYAR_CLANG': CLANG, 'MINYAR_CLANG_FLAGS': '-O1 -fsanitize=address,undefined',
                             'MINYAR_LINK_ARTIFACTS': str(evidence)})
        manifest = json.loads((evidence/'manifest.json').read_text())
        obj = next(x for x in manifest['inputs'] if x['retained'].startswith('native-'))
        identities.append(obj['original'])
        stamps.append(Path(obj['original']).stat().st_mtime_ns)
        assert digest(Path(obj['original'])) == obj['sha256']
    assert identities[0] == identities[1] and stamps[0] == stamps[1]
    assert identities[2] != identities[1]

    malformed = out / 'malformed.raw.ll'
    malformed.write_text('define void @bad(\n) {\nret void\n}\n')
    protected = out / 'protected-output'
    protected.write_bytes(b'prior published executable')
    environment = {'MINYAR_CLANG': CLANG, 'MINYAR_CLANG_FLAGS': '-fsanitize=address',
                   'MINYAR_LINK_ARTIFACTS': str(out/'invalid-header-inputs')}
    status, _, stderr = observation.run('reject-invalid-header', [sys.executable, str(DRIVER),
            'link', str(ROOT), str(malformed), str(native), str(protected), '0'],
            environment=environment)
    assert status != 0 and b'sanitizer coverage cannot be assumed' in stderr
    assert protected.read_bytes() == b'prior published executable'
    failure = json.loads((out/'invalid-header-inputs/manifest.json').read_text())
    assert failure['phase'] == 'program-annotation' and not failure['link_attempted']
    assert (out/'invalid-header-inputs/program.raw.ll').read_bytes() == malformed.read_bytes()
    for option, expected in (('-O1 -fsanitize=address,undefined', b'object\n'),
                             ('-O1', b'llvm\n')):
        stdout, stderr = observation.success('runtime-format-' + expected.strip().decode(),
            [sys.executable, str(DRIVER), 'runtime-format'],
            environment={'MINYAR_RUNTIME_FLAGS': option})
        assert stdout == expected and not stderr
    observation.manifest['native_cache_controls'] = dict(objects=identities, stamps=stamps,
                                                       runtime_sha256=native_before)
    observation.save()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path, required=True)
    args = parser.parse_args()
    observation = Observation(args.artifacts.resolve())
    try:
        unsafe_access(observation)
        helper_controls(observation)
        link_controls(observation)
    except BaseException as error:
        observation.manifest['failure'] = repr(error)
        observation.save()
        raise
    observation.manifest['source_after_mismatches'] = [name for name, old in
            observation.manifest['source_inputs'].items() if digest(ROOT/name) != old]
    assert not observation.manifest['source_after_mismatches']
    observation.manifest['complete'] = True
    observation.save()


if __name__ == '__main__':
    main()
