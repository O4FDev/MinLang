#!/usr/bin/env python3
"""Exercise generated LLVM accesses through the public Clang link driver.

The unsafe control injects one volatile freed-byte store into actual compiler
output. Compile/link must succeed; only the instrumented access may reject it.
Every command and successful/failing workspace remains in --artifacts.
"""
import argparse
import hashlib
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
                     ROOT / 'tests/llvm_sanitizer.py', ROOT / 'runtime/minyar_runtime.c'):
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
                   'MINYAR_CLANG_FLAGS': options, 'MINYAR_NATIVE_FLAGS': options}
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path, required=True)
    args = parser.parse_args()
    observation = Observation(args.artifacts.resolve())
    try:
        unsafe_access(observation)
    except BaseException as error:
        observation.manifest['failure'] = repr(error)
        observation.save()
        raise
    observation.manifest['complete'] = True
    observation.save()


if __name__ == '__main__':
    main()
