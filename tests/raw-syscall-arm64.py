import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    if platform.system() != 'Linux':
        raise SystemExit('Arm syscall execution requires Linux')
    native = platform.machine().lower() in ('aarch64', 'arm64')
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    compiler = os.environ.get('MINYAR_TEST_COMPILER', str(ROOT / 'build/minyarc'))
    runner = [] if native else shlex.split(os.environ.get('MINYAR_ARM64_RUNNER', 'qemu-aarch64'))
    if runner and not shutil.which(runner[0]):
        raise SystemExit('Arm syscall execution requires qemu-aarch64 or MINYAR_ARM64_RUNNER')
    cross_flags = [] if native else ['--target=aarch64-linux-gnu']
    sysroot = os.environ.get('MINYAR_ARM64_SYSROOT')
    toolchain = os.environ.get('MINYAR_ARM64_TOOLCHAIN')
    if sysroot:
        cross_flags.append('--sysroot=' + sysroot)
    if toolchain:
        cross_flags.append('--gcc-toolchain=' + toolchain)
    cross_flags += shlex.split(os.environ.get('MINYAR_ARM64_FLAGS', '-fuse-ld=lld -Wl,--threads=1 -static'))

    def command(arguments):
        subprocess.run(list(map(str, arguments)), cwd=ROOT, check=True, timeout=180)

    def execute(executable, arguments=()):
        process = subprocess.Popen([*runner, str(executable), *map(str, arguments)], cwd=ROOT,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            stdout, stderr = process.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise
        assert process.returncode == 0 and not stderr, (process.returncode, stdout, stderr)
        return process.pid, stdout

    with tempfile.TemporaryDirectory(prefix='minyar-arm64-syscalls-') as temporary:
        work = Path(temporary)
        source = ROOT / 'tests/fixtures/raw-syscall/linux.min'
        programs = []
        for variant, libraries in enumerate(((ROOT / 'library',),
                (ROOT / 'library/arch/arm64', ROOT / 'library'))):
            llvm = work / f'program-{variant}.ll'
            command([compiler, source, llvm,
                     *[argument for library in libraries for argument in ('--library', library)]])
            text = llvm.read_text()
            declaration = 'declare i64 @minyar_machine_syscall(i64, i64, i64, i64, i64, i64, i64)'
            assert text.splitlines().count(declaration) == 1
            assert 'call i64 @minyar_machine_syscall(' in text
            programs.append(llvm)
        for optimization in ('-O0', '-O2'):
            runtime = work / f'runtime-{optimization[1:]}.o'
            command([clang, *cross_flags, optimization, '-Wno-unused-command-line-argument',
                     '-c', ROOT / 'runtime/minyar_default_runtime.c', '-o', runtime])
            errno = work / f'errno-{optimization[1:]}'
            command([clang, *cross_flags, optimization, ROOT / 'tests/raw-syscall-native.c',
                     runtime, '-lm', '-o', errno])
            _, stdout = execute(errno)
            assert stdout == 'raw syscall preserves libc errno\n', stdout
            heap = work / f'heap-{optimization[1:]}'
            command([clang, *cross_flags, optimization, ROOT / 'tests/system-small-heap.c',
                     '-lm', '-o', heap])
            _, stdout = execute(heap)
            assert stdout == 'small heap alignment, size boundaries, resizing and page recovery passed\n', stdout
            for variant, llvm in enumerate(programs):
                executable = work / f'program-{variant}-{optimization[1:]}'
                command([clang, *cross_flags, optimization, '-Wno-override-module', llvm,
                         runtime, '-lm', '-o', executable])
                page = 4096
                initial = b'\x11' * page + b'\x72' * page
                path = work / f'file-{variant}-{optimization[1:]}'
                path.write_bytes(initial)
                pid, stdout = execute(executable, [path, work / 'missing/file', page,
                    172, 56, 57, 63, 64, 62, 29, 222, 227, 215])
                assert stdout == f'{pid}\n', (pid, stdout)
                expected = bytearray(initial)
                expected[page:page+2] = b'Z['
                expected[page+16:page+24] = b'Z[Crrrrr'
                assert path.read_bytes() == expected
    print('Arm64 Linux syscalls and default runtime passed at O0/O2: '
          'both machine packages, errno, Bytes, six-argument mmap offsets, writeback, '
          'unmap and small heap; ' + ('native execution' if native else 'QEMU user execution'))


if __name__ == '__main__':
    main()
