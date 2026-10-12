#!/usr/bin/env python3
"""Raw syscall intrinsic: target ABI, memory ownership, errno and portability.

Default mode executes the native Linux regression or the hosted fallback.
--linux-native requires a supported Linux host instead of silently skipping it.
--abi checks cross assembly/IR and the real freestanding runtime; it does not
claim cross-target execution. --frontends checks all current optional compilers.
Retain inputs, commands, LLVM, binaries and SHA-256 manifests under --output.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from clang_helpers import clang_command, asan_leak_options
from llvm_sanitizer import prepare_llvm_for_link

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/raw-syscall'
# getpid, openat, close, read, write, lseek, ioctl, mmap, msync, munmap.
NUMBERS = {'x86_64': (39, 257, 3, 0, 1, 8, 16, 9, 26, 11),
           'aarch64': (172, 56, 57, 63, 64, 62, 29, 222, 227, 215)}
ORIGINAL_SHA256 = '9f805f32a94607708b3a0532d88df509891bd98383eb8e522de2d3b443791c92'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Run:
    def __init__(self, work):
        self.work = work
        self.commands = []
        self.environment = os.environ.copy()
        self.environment['ASAN_OPTIONS'] = asan_leak_options()
        self.environment['UBSAN_OPTIONS'] = 'halt_on_error=1'

    def command(self, arguments, timeout=120):
        arguments = [str(arg) for arg in arguments]
        result = subprocess.run(arguments, cwd=ROOT, capture_output=True, text=True,
                                env=self.environment, timeout=timeout)
        self.commands.append(dict(argv=arguments, status=result.returncode,
                                  stdout=result.stdout, stderr=result.stderr))
        self.save()
        if result.returncode:
            raise AssertionError(self.commands[-1])
        return result

    def execute(self, executable, arguments=()):
        process = subprocess.Popen([str(executable), *map(str, arguments)], cwd=ROOT,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, env=self.environment)
        try:
            stdout, stderr = process.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise
        self.commands.append(dict(argv=[str(executable), *map(str, arguments)],
                                  pid=process.pid, status=process.returncode,
                                  stdout=stdout, stderr=stderr))
        self.save()
        assert process.returncode == 0 and not stderr, self.commands[-1]
        return process.pid, stdout

    def save(self):
        (self.work / 'commands.json').write_text(json.dumps(self.commands, indent=2) + '\n')


def compile_program(run, compiler, source, llvm, library):
    directories = library if isinstance(library, tuple) else (library,)
    run.command([compiler, source, llvm, *[item for directory in directories for item in ('--library', directory)]])
    text = llvm.read_text()
    declaration = 'declare i64 @minyar_machine_syscall(i64, i64, i64, i64, i64, i64, i64)'
    assert text.splitlines().count(declaration) == 1, 'missing/duplicate runtime helper declaration'
    assert 'call i64 @minyar_machine_syscall(i64 %argument.0' in text
    assert '; minyar-native-library: machine\n' in text
    assert '; minyar-native-library: linux' not in text


def check_abi(run, clang):
    probe = ROOT / 'tests/raw-syscall-probe.c'
    supported = ('x86_64-unknown-linux-gnu', 'aarch64-unknown-linux-gnu')
    fallback = ('x86_64-apple-darwin', 'arm64-apple-darwin',
                'x86_64-pc-windows-msvc', 'aarch64-pc-windows-msvc',
                'riscv64-unknown-linux-gnu', 'x86_64-unknown-linux-gnux32')
    for target in (*supported, *fallback):
        for optimization in ('-O0', '-O2'):
            llvm = run.work / f'abi-{target}-{optimization[1:]}.ll'
            assembly = llvm.with_suffix('.s')
            run.command([clang, '-target', target, optimization, '-std=c11',
                         '-Wall', '-Wextra', '-Werror', '-S', '-emit-llvm', probe, '-o', llvm])
            run.command([clang, '-target', target, optimization, '-S', probe, '-o', assembly])
            text = llvm.read_text()
            if target in supported:
                assert 'asm sideeffect' in text
                registers = ('{ax}', '{di}', '{si}', '{dx}', '{r10}', '{r8}', '{r9}', '~{rcx}', '~{r11}', '~{memory}') if target.startswith('x86') else ('{x8}', '{x0}', '{x1}', '{x2}', '{x3}', '{x4}', '{x5}', '~{memory}')
                assert all(reg in text for reg in registers), text
                assert ('syscall' if target.startswith('x86') else 'svc') in assembly.read_text()
            else:
                assert 'asm sideeffect' not in text and 'ret i64 -38' in text
    resource = run.command([clang, '-print-resource-dir']).stdout.strip()
    for target in (*supported, 'x86_64-none-elf', 'aarch64-none-elf'):
        llvm = run.work / f'freestanding-probe-{target}.ll'
        run.command([clang, '-target', target, '-O2', '-ffreestanding', '-S',
                     '-emit-llvm', probe, '-o', llvm])
        assert 'ret i64 -38' in llvm.read_text() and 'asm sideeffect' not in llvm.read_text()
    for target in ('x86_64-none-elf', 'aarch64-none-elf'):
        llvm = run.work / f'freestanding-runtime-{target}.ll'
        run.command([clang, '-target', target, '-O2', '-ffreestanding', '-nostdinc',
                     '-isystem', Path(resource) / 'include', '-isystem',
                     ROOT / 'runtime/freestanding/include', '-S', '-emit-llvm',
                     ROOT / 'runtime/freestanding/runtime.c', '-o', llvm])
        helper = llvm.read_text().split('@minyar_machine_syscall(', 1)[1].split('\n}', 1)[0]
        assert 'ret i64 -38' in helper and 'asm sideeffect' not in helper
    print('ABI compile proof: Linux x86_64/AArch64 registers; macOS/Windows/x32/unsupported -38; real freestanding runtimes (no cross runtime claim)', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--linux-native', action='store_true')
    parser.add_argument('--abi', action='store_true')
    parser.add_argument('--frontends', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    machine = platform.machine().lower()
    machine = {'amd64': 'x86_64', 'arm64': 'aarch64'}.get(machine, machine)
    supported = platform.system() == 'Linux' and machine in NUMBERS
    if args.linux_native and not supported:
        parser.error('--linux-native requires a native Linux LP64 x86_64/AArch64 host')
    mode = 'sanitize' if args.sanitize else 'native'
    if args.abi:
        mode += '-abi'
    if args.frontends:
        mode += '-frontends'
    work = (args.output or ROOT / 'build/raw-syscall' / mode).resolve()
    work.mkdir(parents=True, exist_ok=True)
    run = Run(work)
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    compiler = Path(os.environ.get('MINYAR_TEST_COMPILER', ROOT / 'build/minyarc')).resolve()
    tool_paths = [compiler, Path(shutil.which(clang) or clang).resolve(), Path(sys.executable).resolve()]
    inputs = [ROOT / name for name in ('compiler/compiler.min', 'compiler/foundation-baseline.min',
              'runtime/minyar_runtime.c', 'runtime/minyar_default_runtime.c',
              'runtime/freestanding/runtime.c', 'library/machine.min',
              'library/arch/arm64/machine.min', 'tests/raw-syscall.py', 'tests/raw-syscall-native.c',
              'tests/raw-syscall-probe.c', 'tests/clang_helpers.py', 'tests/llvm_sanitizer.py',
              'tools/sanitizer_llvm.py')]
    inputs += sorted((ROOT / 'runtime').glob('minyar_*.h'))
    inputs += sorted((ROOT / 'runtime/freestanding/include').rglob('*.h'))
    inputs += sorted(p for p in FIXTURES.glob('*.min') if not p.name.startswith('._'))
    assert sha(FIXTURES / 'vmm-1-original.min') == ORIGINAL_SHA256
    run.command([clang, '--version'])
    if args.abi:
        check_abi(run, clang)
    # The actual neo-vm reproduction must compile. Running it would depend on
    # /dev/kvm, so linux.min converts it to a deterministic regular-file ioctl.
    compile_program(run, compiler, FIXTURES / 'vmm-1-original.min', work / 'vmm-1-original.ll', ROOT / 'library')
    flags = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if args.sanitize else []
    libraries = [ROOT / 'library', (ROOT / 'library/arch/arm64', ROOT / 'library')]
    for library_index, library in enumerate(libraries):
        llvm = work / f'program-{library_index}.ll'
        compile_program(run, compiler, FIXTURES / ('linux.min' if supported else 'fallback.min'), llvm, library)
        prepare_llvm_for_link(llvm, flags)
        for optimization in ('-O0', '-O2'):
            runtime = work / f'runtime-{optimization[1:]}.o'
            if library_index == 0:
                run.command(clang_command([clang, optimization, *flags, '-DMINYAR_SYSTEM_HEAP=1',
                            '-c', ROOT / 'runtime/minyar_runtime.c', '-o', runtime]))
                native = work / f'errno-{optimization[1:]}'
                run.command(clang_command([clang, optimization, *flags, ROOT / 'tests/raw-syscall-native.c', runtime, '-o', native]))
                _, stdout = run.execute(native)
                assert stdout == 'raw syscall preserves libc errno\n', stdout
                # The public launcher also includes stack-owner support and
                # deferred RC settings. Its exact wrapper must export the
                # same raw helper, without a test-only C shim.
                standard_runtime = run.work / f'standard-runtime-{optimization[1:]}.o'
                run.command(clang_command([clang, optimization, *flags, '-c',
                            ROOT / 'runtime/minyar_default_runtime.c', '-o', standard_runtime]))
                standard_native = run.work / f'standard-errno-{optimization[1:]}'
                run.command(clang_command([clang, optimization, *flags,
                            ROOT / 'tests/raw-syscall-native.c', standard_runtime, '-o', standard_native]))
                _, stdout = run.execute(standard_native)
                assert stdout == 'raw syscall preserves libc errno\n', stdout
            executable = work / f'program-{library_index}-{optimization[1:]}'
            run.command(clang_command([clang, optimization, *flags, '-Wno-override-module', llvm, runtime, '-o', executable]))
            if supported:
                page = os.sysconf('SC_PAGE_SIZE')
                path = work / f'file-{library_index}-{optimization[1:]}.bin'
                initial = b'\x11' * page + b'\x72' * page
                path.write_bytes(initial)
                # No unbounded nondeterminism or device dependency in this test.
                pid, stdout = run.execute(executable, [path, work / 'missing/file', page, *NUMBERS[machine]])
                assert stdout == f'{pid}\n', (pid, stdout)
                expected = bytearray(initial)
                expected[page:page+2] = b'Z['
                expected[page+16:page+24] = b'Z[Crrrrr'
                assert path.read_bytes() == expected, 'wrong mmap offset or writeback/Bytes payload'
                (work / 'expected-file.bin').write_bytes(expected)
            else:
                _, stdout = run.execute(executable)
                assert stdout == '-38\n5\n', stdout
    if args.frontends:
        for name in ('minyarc-modules', 'minyarc-callbacks', 'minyarc-errors'):
            frontend = ROOT / 'build' / name
            tool_paths.append(frontend)
            llvm = work / f'{name}.ll'
            compile_program(run, frontend, FIXTURES / ('linux.min' if supported else 'fallback.min'), llvm, ROOT / 'library')
            prepare_llvm_for_link(llvm, flags)
            executable = work / name
            run.command(clang_command([clang, '-O2', *flags, '-Wno-override-module', llvm, work / 'runtime-O2.o', '-o', executable]))
            if supported:
                path = work / f'{name}.bin'
                path.write_bytes(initial)
                pid, stdout = run.execute(executable, [path, work / 'missing/file', page, *NUMBERS[machine]])
                assert stdout == f'{pid}\n' and path.read_bytes() == expected, (name, stdout)
            else:
                _, stdout = run.execute(executable)
                assert stdout == '-38\n5\n'
    manifest = dict(platform=platform.platform(), machine=machine,
                    mode='ASan+UBSan' if args.sanitize else 'native',
                    abi=args.abi, frontends=args.frontends,
                    environment={name: run.environment[name] for name in ('ASAN_OPTIONS', 'UBSAN_OPTIONS')},
                    inputs={str(p.relative_to(ROOT)): sha(p) for p in inputs},
                    tools={str(p): sha(p) for p in tool_paths},
                    artifacts={str(p.relative_to(work)): sha(p) for p in sorted(work.rglob('*')) if p.is_file() and p.name != 'manifest.json'})
    (work / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Raw syscall {machine} {manifest["mode"]}: O0/O2, both machine APIs, original repro, errno, ' +
          ('PID/ENOSYS/ENOENT/EBADF/EFAULT/ENOTTY/Bytes/file-offset mmap+writeback+munmap' if supported else 'hosted -38 fallback') + f'; evidence {work}', flush=True)


if __name__ == '__main__':
    main()
