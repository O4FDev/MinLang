#!/usr/bin/env python3
"""Run Clang with literal argv and content-addressed native package artifacts.

Flag environment variables use shell-style quoting; no shell evaluates them.
The launcher keeps configuration and temporary-file lifetime in one process.
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time


def flags(name, default):
    try:
        return shlex.split(os.environ.get(name, default))
    except ValueError as error:
        raise ValueError(f'{name}: {error}') from error


def run(args, **kwargs):
    result = subprocess.run(args, **kwargs)
    if result.returncode:
        # Preserve the public launcher's failure status even after a signal.
        sys.exit(result.returncode if result.returncode > 0 else 128 - result.returncode)


def glfw_flags():
    pkg = shutil.which('pkg-config')
    if pkg and subprocess.run([pkg, '--exists', 'glfw3'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode == 0:
        values = []
        for option in ('--cflags', '--libs'):
            values.append(shlex.split(subprocess.check_output([pkg, option, 'glfw3'], text=True)))
        return values
    brew = shutil.which('brew')
    if brew:
        result = subprocess.run([brew, '--prefix', 'glfw'], capture_output=True, text=True)
        prefix = Path(result.stdout.strip())
        if result.returncode == 0 and (prefix / 'include').is_dir():
            return [['-I' + str(prefix / 'include')], ['-L' + str(prefix / 'lib'), '-lglfw']]
    raise ValueError("the graphics package needs GLFW: 'brew install glfw' on macOS, "
                     "'sudo apt install libglfw3-dev' on Debian/Ubuntu, or "
                     "'pacman -S mingw-w64-ucrt-x86_64-glfw' in MSYS2 UCRT64")


def clang_identity(clang):
    """What a native object depends on besides its sources and flags."""
    identity = hashlib.sha256()
    executable = shutil.which(clang)
    if not executable:
        raise ValueError(f'cannot find Clang: {clang}')
    executable_path = Path(executable).resolve()
    # Compiler binaries can be hundreds of megabytes. File identity detects
    # replacement (including preserved mtime) without rereading one per link.
    stat = executable_path.stat()
    identity.update(json.dumps([stat.st_dev, stat.st_ino, stat.st_size,
                               stat.st_mtime_ns, stat.st_ctime_ns]).encode())
    identity.update(subprocess.check_output([clang, '--version']))
    identity.update(json.dumps([str(executable_path), platform.system(), platform.machine()]).encode())
    return identity


def native_object(project, clang, base, name, compile_flags):
    """Compile runtime/native/NAME once per distinct content and flags."""
    source = project / 'runtime/native' / name
    # Includes native ABI helpers and platform headers. Content keys prevent
    # stale artifacts after restores which preserve old timestamps.
    dependencies = [source, *sorted((project / 'runtime').rglob('*.h'))]
    identity = base.copy()
    identity.update(json.dumps([name, compile_flags]).encode())
    for dependency in dependencies:
        identity.update(str(dependency.relative_to(project)).encode() + b'\0')
        identity.update(dependency.read_bytes())
    directory = project / 'build/native'
    directory.mkdir(parents=True, exist_ok=True)
    stem = Path(name).stem
    output = directory / (stem + '-' + identity.hexdigest() + '.o')
    if not output.is_file():
        # Every build owns its temporary artifact; a concurrent compiler never
        # writes an object another linker is already reading.
        fd, temporary = tempfile.mkstemp(prefix=stem + '-', suffix='.o', dir=directory)
        os.close(fd)
        try:
            run([clang, *compile_flags, '-c', str(source), '-o', temporary])
            os.replace(temporary, output)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return str(output)


def graphics(project, clang, base, native_flags):
    cflags, libraries = glfw_flags()
    output = native_object(project, clang, base, 'graphics.c', [*native_flags, *cflags])
    system = platform.system()
    if system == 'Darwin':
        libraries += ['-framework', 'OpenGL', '-framework', 'Cocoa', '-framework', 'IOKit']
    elif system == 'Windows' or system.startswith(('MSYS', 'MINGW', 'CYGWIN')):
        libraries += ['-lopengl32']
    else:
        libraries += ['-lGL']
    return [output, *libraries]


def bootstrap(project, targets):
    project = Path(project)
    (project / 'build').mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    if 'MINYAR_CLANG' in environment:
        environment['LLVM_CC'] = environment['MINYAR_CLANG']
    if 'CC' not in environment:
        environment['CC'] = environment.get('LLVM_CC', 'clang')
    if 'COMPILER_LTO_FLAGS' not in environment:
        llvm_options = flags('LLVM_FLAGS', '-O2 -Wno-override-module')
        lto = lto_flags(environment.get('LLVM_CC', 'clang'), llvm_options)
        options = [*llvm_options, *lto]
        lld = any(option.startswith(('-fuse-ld=', '--ld-path=')) and
                  Path(option.split('=', 1)[1]).name in ('lld', 'ld.lld') for option in options)
        # Parallel ELF LLD workers reserve stacks and allocator arenas. Bound
        # bootstrap parallelism within the existing development address cap.
        if platform.system() == 'Linux' and lld and not any('--threads' in option for option in options):
            lto.append('-Wl,--threads=1')
        environment['COMPILER_LTO_FLAGS'] = shlex.join(lto)
    # Lock only shared bootstrap artifacts. The OS releases advisory locks if
    # an invocation exits; generated program compilation/linking stays parallel.
    with (project / 'build/bootstrap.lock').open('a+b') as lock:
        if os.name == 'nt':
            import errno
            import msvcrt
            lock.seek(0, os.SEEK_END)
            if not lock.tell():
                lock.write(b'\0')
                lock.flush()
            lock.seek(0)
            while True:
                try:
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as error:
                    if error.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        raise
                    time.sleep(0.05)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        run(['make', '-s', '-C', str(project), *targets], env=environment)


def lto_flags(clang, link_flags):
    # ThinLTO optimises the program and the runtime as separate modules after
    # importing what each one calls. Measured against full LTO it ran
    # Minyarcraft's world build in 5% fewer instructions, the compiler's
    # self-compile in 2% fewer and JSON parsing in 3% fewer, at the same
    # link time.
    lto = ['-flto=thin']
    # Linux's default GNU linker needs an optional LLVMgold plugin for LTO.
    # Prefer the toolchain's lld when available unless the user chose a linker.
    if platform.system() != 'Darwin' and not any(a.startswith(('-fuse-ld=', '--ld-path=')) for a in link_flags):
        system = platform.system()
        windows = system == 'Windows' or system.startswith(('MSYS', 'MINGW', 'CYGWIN'))
        names = ('ld.lld.exe', 'ld.lld') if windows else ('ld.lld',)
        directory = Path(shutil.which(clang) or clang).resolve().parent
        sibling = next((directory / name for name in names if (directory / name).is_file()), None)
        if sibling is not None:
            # MinGW checks the flavor literally before accepting bitcode.
            # An absolute -fuse-ld path selects lld but disables that support;
            # keep the flavor and executable location as separate arguments.
            lto += ['-fuse-ld=lld', '--ld-path=' + str(sibling)] if windows else ['-fuse-ld=' + str(sibling)]
        elif any(shutil.which(name) for name in names):
            lto += ['-fuse-ld=lld']
    return lto


def version(project):
    project = Path(project)
    sources = sorted((project / 'compiler').glob('*.min'))
    if sources:
        identity = hashlib.sha256()
        for source in sources:
            identity.update(source.name.encode() + b'\0' + source.read_bytes())
        print('Minyar development (source ' + identity.hexdigest()[:12] + ')')
    else:
        print('Minyar development')
    compiler = project / 'build/minyarc'
    if compiler.is_file():
        print('cached compiler: ' + hashlib.sha256(compiler.read_bytes()).hexdigest()[:12])
    else:
        print('compiler builds on first use')


def doctor(clang):
    c_compiler = os.environ.get('CC', clang)
    missing = [name for name in ('make', c_compiler, 'zsh') if not shutil.which(name)]
    if not shutil.which(clang):
        raise ValueError('Clang was not found. Install Clang and select it with MINYAR_CLANG or LLVM_CC: ' + clang)
    if missing:
        raise ValueError('missing prerequisites: ' + ', '.join(missing) +
                         '. Install the C compiler, Make, and zsh; see docs/toolchain.md.')
    print(subprocess.check_output([clang, '--version'], text=True).splitlines()[0], flush=True)
    with tempfile.TemporaryDirectory(prefix='minyar doctor ') as work:
        work = Path(work)
        llvm = work / 'probe.ll'
        llvm.write_text('define i32 @main() {\n  %slot = alloca ptr\n  store ptr null, ptr %slot\n'
                        '  %value = load ptr, ptr %slot\n  ret i32 0\n}\n')
        runtime = work / 'probe.c'
        runtime.write_text('#include <stdint.h>\n#include <stdio.h>\n'
                           '_Static_assert(sizeof(void *) == 8, "Minyar needs a 64-bit target");\n')
        options = flags('MINYAR_CLANG_FLAGS', '-O2 -Wno-override-module')
        result = subprocess.run([clang, *options, *lto_flags(clang, options), str(llvm), str(runtime),
                                 '-o', str(work / 'probe')], capture_output=True, text=True)
        if result.returncode:
            raise ValueError('the opaque IR / 64-bit C / LTO probe failed. Install matching Clang and lld '
                             '(Linux), or Xcode command-line tools (macOS). Check MINYAR_CLANG_FLAGS.\n' + result.stderr)
    print('Ready: 64-bit C headers, opaque LLVM pointers, and LTO linking verified.')


def publish_executable(command, output, source=None):
    destination = Path(output)
    # Stage on the destination filesystem so publishing is one atomic rename.
    # A failed or interrupted linker never truncates the last successful build.
    previous_handlers = {}

    def interrupted(number, frame):
        sys.exit(128 + number)

    try:
        for name in ('SIGTERM', 'SIGHUP'):
            number = getattr(signal, name, None)
            if number is not None:
                previous_handlers[number] = signal.signal(number, interrupted)
        with tempfile.TemporaryDirectory(prefix='.minyar-link-', dir=destination.parent) as temporary:
            staged = Path(temporary) / destination.name
            run([*command, '-o', str(staged)])
            # Some Windows drivers supply .exe when the requested name lacks it.
            if not staged.is_file() and Path(str(staged) + '.exe').is_file():
                staged = Path(str(staged) + '.exe')
                destination = Path(str(destination) + '.exe')
            if source and destination.exists() and destination.samefile(source):
                raise ValueError('refusing to replace the source file; choose a different -o path: ' +
                                 str(destination))
            os.replace(staged, destination)
    finally:
        for number, handler in previous_handlers.items():
            signal.signal(number, handler)


def main():
    if sys.version_info < (3, 9):
        raise ValueError('Python 3.9 or newer is required for the portable launcher')
    clang = os.environ.get('MINYAR_CLANG', os.environ.get('LLVM_CC', 'clang'))
    if len(sys.argv) >= 4 and sys.argv[1] == 'build':
        bootstrap(sys.argv[2], sys.argv[3:])
        return
    if len(sys.argv) == 3 and sys.argv[1] == 'version':
        version(sys.argv[2])
        return
    if len(sys.argv) == 2 and sys.argv[1] == 'doctor':
        doctor(clang)
        return
    if len(sys.argv) >= 4 and sys.argv[1] == 'compile':
        run([clang, *flags('MINYAR_RUNTIME_FLAGS', '-O2 -Wno-override-module'), *sys.argv[2:]])
        return
    if len(sys.argv) not in (7, 8, 9) or sys.argv[1] != 'link':
        raise ValueError('usage: clang-driver.py compile ARGS... | link PROJECT IR RUNTIME OUTPUT RELEASE')
    project, llvm, runtime, output, release = sys.argv[2:7]
    debug = len(sys.argv) >= 8 and sys.argv[7] == '1'
    source = sys.argv[8] if len(sys.argv) == 9 else None
    project = Path(project)
    link_flags = flags('MINYAR_CLANG_FLAGS', '-O2 -Wno-override-module' if release == '1'
                       else ('-O0 -g -Wno-override-module' if debug else '-O2 -Wno-override-module'))
    native = []
    libraries = set()
    with Path(llvm).open() as stream:
        for line in stream:
            if line.startswith('; minyar-native-library: '):
                libraries.add(line.removeprefix('; minyar-native-library: ').strip())
    native_flags = flags('MINYAR_NATIVE_FLAGS', shlex.join(link_flags))
    base = clang_identity(clang) if libraries - {'machine', 'machine_arm64'} else None
    for library in sorted(libraries):
        if library == 'graphics':
            native += graphics(project, clang, base, native_flags)
        elif library == 'macos':
            if platform.system() != 'Darwin':
                raise ValueError('the macos package requires macOS and the Apple command-line tools')
            native += [native_object(project, clang, base, 'macos.m', [*native_flags, '-fobjc-arc', '-fmodules']),
                       '-framework', 'AppKit']
        elif library == 'http':
            if platform.system() != 'Darwin':
                raise ValueError('the http package currently requires macOS and the Apple command-line tools')
            native += [native_object(project, clang, base, 'http.m', [*native_flags, '-fobjc-arc', '-fmodules']),
                       '-framework', 'AppKit']
        elif library in ('machine', 'machine_arm64'):
            pass  # Compiler intrinsics: the code is already inline in the program.
        elif library == 'net':
            native += [native_object(project, clang, base, 'net.c', native_flags)]
            if platform.system() == 'Windows' or platform.system().startswith(('MSYS', 'MINGW', 'CYGWIN')):
                native += ['-lws2_32']
        elif library == 'tlsverify':
            native += [native_object(project, clang, base, 'tlsverify.c', native_flags)]
            if platform.system() == 'Darwin':
                native += ['-framework', 'Security', '-framework', 'CoreFoundation']
            elif platform.system() == 'Windows' or platform.system().startswith(('MSYS', 'MINGW', 'CYGWIN')):
                native += ['-lcrypt32', '-lbcrypt', '-lncrypt', '-lws2_32']
            else:
                native += ['-lcrypto']
        else:
            raise ValueError(f'the program uses an unknown native library: {library}')
    lto = lto_flags(clang, link_flags) if release == '1' else []
    math_libraries = [] if platform.system() == 'Darwin' else ['-lm']
    publish_executable([clang, *link_flags, *lto, llvm, runtime, *native, *math_libraries], output, source)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'minyar: {error}', file=sys.stderr)
        sys.exit(1)
