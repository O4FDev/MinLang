#!/usr/bin/env python3
"""Run Clang with literal argv and content-addressed native package artifacts.

Flag environment variables use shell-style quoting; no shell evaluates them.
The launcher keeps configuration and temporary-file lifetime in one process.
"""
import hashlib
import argparse
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from host_paths import host_path, pinned_llvm, pinned_lld
from sanitizer_llvm import address_sanitizer_enabled, thread_sanitizer_enabled, instrument_program_sanitizers


def flags(name, default):
    try:
        return shlex.split(os.environ.get(name, default))
    except ValueError as error:
        raise ValueError(f'{name}: {error}') from error


def run(args, *, observation=None, **kwargs):
    result = subprocess.run(args, **kwargs)
    if observation is not None:
        observation['link_subprocess_status'] = result.returncode
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
    executable_path = host_path(executable).resolve()
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
    if name.startswith(('securecrypto', 'update')):
        dependencies += sorted((project / 'vendor/monocypher').glob('*'))
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


def package_native_inputs(arguments):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--native-source', action='append', default=[])
    parser.add_argument('--native-object', action='append', default=[])
    options = parser.parse_args(arguments)
    inputs = {}
    for kind, values in (('source', options.native_source), ('object', options.native_object)):
        for value in values:
            name, separator, filename = value.partition('=')
            if not separator or not re.fullmatch(r'[A-Za-z0-9_]+', name) or not filename:
                raise ValueError(f'native {kind} requires NAME=FILE: {value}')
            path = host_path(filename).resolve()
            suffixes = ('.c', '.m') if kind == 'source' else ('.o', '.a', '.obj', '.lib')
            if path.suffix not in suffixes or not path.is_file():
                raise ValueError(f'native {kind} must be a readable {", ".join(suffixes)} file: {path}')
            inputs.setdefault(name, []).append((kind, path))
    return inputs


def link_package_inputs(project, clang, native_flags, inputs, libraries, native, link):
    with tempfile.TemporaryDirectory(prefix='minyar-package-native-') as temporary:
        for name in sorted(libraries & inputs.keys()):
            for kind, path in inputs[name]:
                if kind == 'source':
                    output = Path(temporary) / f'{len(native)}.o'
                    run([clang, *native_flags, '-iquote', str(project / 'runtime'),
                         '-c', str(path), '-o', str(output)])
                    native.append(str(output))
                else:
                    native.append(str(path))
        link(native)


def cycle_runtime_object(project, clang, runtime, release, link_flags):
    from cycle_runtime import configured_source
    source = configured_source(project, runtime)
    options = flags('MINYAR_RUNTIME_FLAGS', '-O2 -Wno-override-module')
    if release == '1':
        options += lto_flags(clang, link_flags)[:1]
    identity = clang_identity(clang)
    identity.update(json.dumps(options).encode() + source.encode())
    for header in sorted((project / 'runtime').rglob('*.h')):
        identity.update(str(header.relative_to(project)).encode() + header.read_bytes())
    directory = project / 'build/native'
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / ('cycle-runtime-' + identity.hexdigest() + '.o')
    if not output.is_file():
        with tempfile.TemporaryDirectory(prefix='cycle-runtime-', dir=directory) as temporary:
            temporary = Path(temporary)
            configured = temporary / 'runtime.c'
            configured.write_text(source)
            staged = temporary / 'runtime.o'
            run([clang, *options, '-iquote', str(project / 'runtime'),
                 '-c', str(configured), '-o', str(staged)])
            os.replace(staged, output)
    return str(output)


def thread_runtime_object(project, clang, runtime, release, link_flags, cycles):
    from thread_runtime import source as thread_source
    source = thread_source(project, runtime, cycles)
    options = flags('MINYAR_RUNTIME_FLAGS', '-O2 -Wno-override-module')
    if release == '1':
        options += lto_flags(clang, link_flags)[:1]
    if platform.system() != 'Windows' and not platform.system().startswith(('MSYS', 'MINGW', 'CYGWIN')):
        options += ['-pthread']
    identity = clang_identity(clang)
    identity.update(json.dumps(options).encode() + source.encode())
    for dependency in sorted((project / 'runtime').rglob('*')):
        if dependency.is_file() and dependency.suffix in ('.h', '.c'):
            identity.update(str(dependency.relative_to(project)).encode() + dependency.read_bytes())
    directory = project / 'build/native'
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / ('thread-runtime-' + identity.hexdigest() + '.o')
    if not output.is_file():
        with tempfile.TemporaryDirectory(prefix='thread-runtime-', dir=directory) as temporary:
            temporary = Path(temporary)
            configured = temporary / 'runtime.c'
            configured.write_text(source)
            staged = temporary / 'runtime.o'
            run([clang, *options, '-iquote', str(project / 'runtime'), '-c', str(configured), '-o', str(staged)])
            os.replace(staged, output)
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
    project = host_path(project)
    (project / 'build').mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    selected = environment.get('MINYAR_CLANG', environment.get('LLVM_CC'))
    resolved = pinned_llvm(selected)
    environment['LLVM_CC'] = selected or resolved
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
        run(['make', '-s', '-C', str(project), *flags('MINYAR_MAKE_FLAGS', ''), *targets], env=environment)


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
        if system == 'Linux':
            linker = subprocess.check_output([clang, '-print-prog-name=ld.lld'], text=True, timeout=10).strip()
            return lto + ['-fuse-ld=' + pinned_lld(linker)]
        windows = system == 'Windows' or system.startswith(('MSYS', 'MINGW', 'CYGWIN'))
        names = ('ld.lld.exe', 'ld.lld') if windows else ('ld.lld',)
        directory = host_path(shutil.which(clang) or clang).resolve().parent
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
    project = host_path(project)
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


def file_binding(path, retained):
    """Bind transient source bytes to the independently retained copy."""
    original = host_path(path).resolve()
    retained = host_path(retained).resolve()
    before = original.read_bytes()
    if original != retained:
        shutil.copyfile(original, retained)
    copied = retained.read_bytes()
    after = original.read_bytes()
    hashes = [hashlib.sha256(value).hexdigest() for value in (before, copied, after)]
    if len(set(hashes)) != 1:
        raise ValueError('link input changed while retaining evidence')
    return {'original': str(original), 'retained': retained.name,
            'sha256': hashes[0], 'source_before_sha256': hashes[0],
            'retained_sha256': hashes[1], 'source_after_sha256': hashes[2],
            'bytes': len(before)}


def effective_optimization(options):
    value = None
    for option in options:
        if re.fullmatch(r'-O(?:[0-9]+|s|z|g|fast)?', option):
            value = option[2:] or '1'
    return value


def publish_executable(command, output, source=None, *, observation=None):
    destination = host_path(output)
    source = host_path(source) if source else None
    # Stage on the destination filesystem so publishing is one atomic rename.
    # Metadata observes this same invocation; it does not select another tool
    # or change the program, flags, publication behavior or signal status.
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
            actual = [*command, '-o', str(staged)]
            if observation is not None:
                observation['actual_command'] = list(map(str, actual))
                observation['staged_requested_path'] = str(staged.resolve())
                compiler = host_path(shutil.which(str(command[0])) or command[0]).resolve()
                compiler_hash = hashlib.sha256(compiler.read_bytes()).hexdigest()
                observation['compiler_pre_link'] = {'selected_command': str(command[0]),
                    'resolved_path': str(compiler), 'sha256': compiler_hash}
                if (str(compiler) != observation['compiler']
                        or compiler_hash != observation['tools']['clang.bin']):
                    raise ValueError('selected link compiler changed')
                for row in [observation['raw_program_input'], observation['program_input'],
                            *observation['inputs']]:
                    value = hashlib.sha256(host_path(row['original']).read_bytes()).hexdigest()
                    row['pre_link_sha256'] = value
                    if value != row['retained_sha256']:
                        raise ValueError('retained link input changed before Clang')
                observation['link_attempted'] = True
            run(actual, **({'observation': observation} if observation is not None else {}))
            # Some Windows drivers supply .exe when the requested name lacks it.
            if not staged.is_file() and Path(str(staged) + '.exe').is_file():
                staged = Path(str(staged) + '.exe')
                destination = Path(str(destination) + '.exe')
            if observation is not None:
                retained = host_path(observation['artifact_directory']) / ('program.staged' + staged.suffix)
                binding = file_binding(staged, retained)
                observation['staged_output'] = {'path': str(staged.resolve()),
                    'retained': retained.name, 'sha256': binding['sha256'],
                    'bytes': binding['bytes']}
                for row in [observation['raw_program_input'], observation['program_input'],
                            *observation['inputs']]:
                    value = hashlib.sha256(host_path(row['original']).read_bytes()).hexdigest()
                    row['post_link_sha256'] = value
                    if value != row['pre_link_sha256']:
                        raise ValueError('link input changed while Clang ran')
            if source and destination.exists() and destination.samefile(source):
                raise ValueError('refusing to replace the source file; choose a different -o path: ' +
                                 str(destination))
            os.replace(staged, destination)
            if observation is not None:
                retained = host_path(observation['artifact_directory']) / ('program' + destination.suffix)
                binding = file_binding(destination, retained)
                observation['final_output'] = {'path': str(destination.resolve()),
                    'retained': retained.name, 'sha256': binding['sha256'],
                    'bytes': binding['bytes']}
                if (observation['staged_output']['sha256'] != binding['sha256']
                        or observation['staged_output']['bytes'] != binding['bytes']):
                    raise ValueError('published link output changed')
    finally:
        for number, handler in previous_handlers.items():
            signal.signal(number, handler)



def link_program(clang, link_flags, lto, llvm, runtime, native, libraries, output, source):
    """Sanitize only generated program IR; optionally retain exact link inputs.

    Schema 2 binds the actual staged-output argv and immediately observed input
    bytes. It does not measure internal runtime compilation counts or promise
    atomic pathname resolution against another same-user process.
    """
    address_enabled = address_sanitizer_enabled(link_flags)
    thread_enabled = thread_sanitizer_enabled(link_flags)
    enabled = address_enabled or thread_enabled
    requested = os.environ.get('MINYAR_LINK_ARTIFACTS')
    if not enabled and not requested:
        publish_executable([clang, *link_flags, *lto, llvm, runtime, *native, *libraries],
                           output, source)
        return
    artifacts = host_path(requested).resolve() if requested else None
    if artifacts:
        artifacts.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='minyar-program-sanitize-') as temporary:
        directory = artifacts or Path(temporary)
        manifest = {'schema': 2, 'address_sanitizer_enabled': address_enabled,
                    'thread_sanitizer_enabled': thread_enabled,
                    'program_ir_cached': False, 'runtime_reannotated': False,
                    'link_flags': list(link_flags), 'lto_flags': list(lto),
                    'optimization': effective_optimization([*link_flags, *lto]),
                    'mode': 'asan' if address_enabled else ('tsan' if thread_enabled else 'native'),
                    'compiler_selected_command': str(clang),
                    'inputs': [], 'tools': {}, 'tool_bindings': {}, 'link_attempted': False,
                    'artifact_directory': str(directory), 'retention_errors': []}
        try:
            raw = host_path(llvm).read_bytes()
            program = llvm
            manifest.update(raw_program=str(host_path(llvm).resolve()),
                            raw_sha256=hashlib.sha256(raw).hexdigest())
            if artifacts:
                manifest['raw_program_input'] = file_binding(llvm, directory / 'program.raw.ll')
            if enabled:
                program = str(directory / ('program.asan.ll' if address_enabled else 'program.tsan.ll'))
                try:
                    Path(program).write_bytes(instrument_program_sanitizers(raw.decode('utf-8'), link_flags).encode('utf-8'))
                except (UnicodeError, ValueError) as error:
                    manifest.update(phase='program-annotation', error=repr(error))
                    raise
            command = [clang, *link_flags, *lto, program, runtime, *native, *libraries]
            manifest.update(command=list(map(str, command)),
                linked_program_sha256=hashlib.sha256(host_path(program).read_bytes()).hexdigest())
            if artifacts:
                manifest['program_input'] = file_binding(program, directory /
                    ('program.asan.ll' if address_enabled else ('program.tsan.ll' if thread_enabled else 'program.raw.ll')))
                manifest['program_input'].update(role='program', format='llvm')
                for label, role, path in [('runtime', 'runtime', runtime),
                        *[(f'native-{i}', 'provider', value) for i, value in enumerate(native)]]:
                    path = host_path(path)
                    if not path.is_file():
                        continue
                    row = file_binding(path, directory / (label + path.suffix))
                    row.update(role=role, format=('native_object' if path.suffix == '.o' else
                                                 'llvm' if path.suffix in ('.ll', '.bc') else 'native_input'))
                    manifest['inputs'].append(row)
                for name in ('clang-driver.py', 'sanitizer_llvm.py'):
                    path = Path(__file__).resolve().parent / name
                    row = file_binding(path, directory / name)
                    manifest['tools'][name] = row['sha256']
                    manifest['tool_bindings'][name] = row
                compiler = host_path(shutil.which(clang) or clang).resolve()
                row = file_binding(compiler, directory / 'clang.bin')
                manifest['tools']['clang.bin'] = row['sha256']
                manifest['tool_bindings']['clang.bin'] = row
                manifest['compiler'] = str(compiler)
                manifest['compiler_version'] = subprocess.check_output([clang, '--version'], text=True)
            publish_executable(command, output, source,
                               **({'observation': manifest} if artifacts else {}))
            manifest['link_status'] = 0
            if artifacts:
                manifest['binary_sha256'] = manifest['final_output']['sha256']
        except BaseException as error:
            manifest['link_error'] = repr(error)
            raise
        finally:
            if artifacts:
                # A retention failure cannot replace a linker signal/status.
                active_error = sys.exc_info()[0] is not None
                for name in ('clang-driver.py', 'sanitizer_llvm.py'):
                    try:
                        path = Path(__file__).resolve().parent / name
                        if not (directory / name).exists():
                            shutil.copyfile(path, directory / name)
                    except (OSError, ValueError) as error:
                        manifest['retention_errors'].append({'phase': 'helper-retention',
                                                             'error': repr(error)})
                try:
                    (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
                except (OSError, ValueError) as error:
                    manifest['retention_errors'].append({'phase': 'manifest-retention',
                                                         'error': repr(error)})
                    try:
                        (directory / 'manifest-retention-error.json').write_text(
                            json.dumps(manifest, indent=2) + '\n')
                    except (OSError, ValueError):
                        pass
                if manifest['retention_errors'] and not active_error:
                    raise ValueError('could not retain complete final link evidence')


def main():
    if sys.version_info < (3, 9):
        raise ValueError('Python 3.9 or newer is required for the portable launcher')
    clang = os.environ.get('MINYAR_CLANG', os.environ.get('LLVM_CC'))
    if len(sys.argv) >= 4 and sys.argv[1] == 'build':
        bootstrap(sys.argv[2], sys.argv[3:])
        return
    if len(sys.argv) == 3 and sys.argv[1] == 'version':
        version(sys.argv[2])
        return
    if len(sys.argv) == 2 and sys.argv[1] == 'toolchain':
        print(pinned_llvm(clang))
        return
    if len(sys.argv) == 2 and sys.argv[1] == 'doctor':
        doctor(pinned_llvm(clang))
        return
    if len(sys.argv) == 2 and sys.argv[1] == 'runtime-format':
        # Clang has already instrumented C emitted as LLVM. Feeding that IR
        # through a second sanitizer pipeline instruments shadow accesses and
        # can crash before main. Keep a native object under sanitizer flags;
        # ordinary release builds retain their existing LLVM/LTO path.
        options = flags('MINYAR_RUNTIME_FLAGS', '-O2 -Wno-override-module')
        print('object' if any(option.startswith('-fsanitize=') for option in options) else 'llvm')
        return
    if len(sys.argv) >= 4 and sys.argv[1] == 'compile':
        clang = pinned_llvm(clang)
        run([clang, *flags('MINYAR_RUNTIME_FLAGS', '-O2 -Wno-override-module'), *sys.argv[2:]])
        return
    if len(sys.argv) < 7 or sys.argv[1] != 'link':
        raise ValueError('usage: clang-driver.py compile ARGS... | link PROJECT IR RUNTIME OUTPUT RELEASE')
    clang = pinned_llvm(clang)
    project, llvm, runtime, output, release = sys.argv[2:7]
    debug = len(sys.argv) >= 8 and sys.argv[7] == '1'
    source = sys.argv[8] if len(sys.argv) >= 9 else None
    package_inputs = package_native_inputs(sys.argv[9:])
    output_path = host_path(output)
    for inputs in package_inputs.values():
        for _, path in inputs:
            if path == output_path.resolve() or (output_path.exists() and path.samefile(output_path)):
                raise ValueError(f'refusing to replace a native input; choose a different -o path: {output}')
    project = host_path(project)
    link_flags = flags('MINYAR_CLANG_FLAGS', '-O2 -Wno-override-module' if release == '1'
                       else ('-O0 -g -Wno-override-module' if debug else '-O2 -Wno-override-module'))
    native = []
    libraries = set()
    cycles = False
    threaded = False
    c_layout_metadata = []
    with host_path(llvm).open() as stream:
        for line in stream:
            if line.startswith(('; minyar-c-layout: ', '; minyar-c-value: ')):
                c_layout_metadata.append(line)
            if line.startswith('; minyar-native-library: '):
                library = line.removeprefix('; minyar-native-library: ').strip()
                libraries.add(library)
                if library == 'callbackruntime': cycles = True
            if line in ('; minyar-cycle-runtime: 1\n', '; minyar-callback-runtime: 1\n'):
                cycles = True
            if line == '; minyar-thread-runtime: 1\n':
                threaded = True
    if threaded:
        runtime = thread_runtime_object(project, clang, runtime, release, link_flags, cycles)
        if platform.system() != 'Windows' and not platform.system().startswith(('MSYS', 'MINGW', 'CYGWIN')):
            native += ['-pthread']
    elif cycles:
        runtime = cycle_runtime_object(project, clang, runtime, release, link_flags)
    native_flags = flags('MINYAR_NATIVE_FLAGS', shlex.join(link_flags))
    if c_layout_metadata:
        from c_layout_abi import native_object as c_layout_object
        bridge = c_layout_object(project, clang, native_flags, c_layout_metadata, clang_identity(clang), run)
        if bridge:
            native.append(bridge)
    if cycles and 'macos' in libraries:
        native_flags = [*native_flags, '-DMINYAR_APP_MANAGED_CLEANUP=1']
    if {'macos', 'net'} <= libraries or {'windows', 'net'} <= libraries:
        native_flags = [*native_flags, '-DMINYAR_APP_EVENT_LOOP=1']
    base = clang_identity(clang) if libraries - {'machine', 'machine_arm64'} else None
    if (libraries - package_inputs.keys()) & {'securecrypto', 'update'}:
        native += [native_object(project, clang, base, 'update_monocypher.c', native_flags)]
    for library in sorted(libraries):
        if library in package_inputs:
            continue
        elif library == 'graphics':
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
                       '-framework', 'AppKit', '-framework', 'Security']
        elif library == 'windows':
            if not (platform.system() == 'Windows' or platform.system().startswith(('MSYS', 'MINGW', 'CYGWIN'))):
                raise ValueError('the windows package requires Windows and its native UI')
            native += [native_object(project, clang, base, 'windows.c', native_flags),
                       '-luser32', '-lgdi32', '-lshell32', '-lcomctl32']
        elif library == 'schannel':
            if not (platform.system() == 'Windows' or platform.system().startswith(('MSYS', 'MINGW', 'CYGWIN'))):
                raise ValueError('the schannel package requires Windows and its TLS provider')
            native += [native_object(project, clang, base, 'schannel.c', native_flags),
                       '-lsecur32', '-lcrypt32', '-lbcrypt', '-lncrypt', '-lws2_32']
            if 'tlsverify' not in libraries:
                native += [native_object(project, clang, base, 'tlsverify.c', native_flags)]
        elif library == 'wincert':
            if not (platform.system() == 'Windows' or platform.system().startswith(('MSYS', 'MINGW', 'CYGWIN'))):
                raise ValueError('the wincert package requires Windows and its certificate store')
            native += [native_object(project, clang, base, 'wincert.c', native_flags),
                       '-lcrypt32', '-lbcrypt', '-lncrypt']
        elif library in ('machine', 'machine_arm64'):
            pass  # Compiler intrinsics: the code is already inline in the program.
        elif library == 'net':
            native += [native_object(project, clang, base, 'net.c', native_flags)]
            if platform.system() == 'Windows' or platform.system().startswith(('MSYS', 'MINGW', 'CYGWIN')):
                native += ['-lws2_32']
        elif library == 'update':
            native += [native_object(project, clang, base, name, native_flags)
                       for name in ('update.c', 'update_ed25519.c')]
        elif library == 'workers':
            native += [native_object(project, clang, base, 'workers.c', native_flags)]
            if platform.system() == 'Windows' or platform.system().startswith(('MSYS', 'MINGW', 'CYGWIN')):
                native += ['-ladvapi32']
            else:
                native += ['-pthread']
        elif library == 'callbackruntime':
            # This bounded service entry is supplied by the opt-in engine.
            pass
        elif library == 'system':
            native += [native_object(project, clang, base, 'system.c', native_flags)]
            if platform.system() == 'Windows' or platform.system().startswith(('MSYS', 'MINGW', 'CYGWIN')):
                native += ['-lpsapi']
            else:
                native += ['-pthread']
        elif library == 'files':
            if platform.system() == 'Windows' or platform.system().startswith(('MSYS', 'MINGW', 'CYGWIN')):
                raise ValueError(f'the {library} package currently supports macOS and Linux')
            native += [native_object(project, clang, base, library + '.c', native_flags)]
            if library == 'files':
                native += ['-pthread']
        elif library == 'quicinteropio':
            native += [native_object(project, clang, base, 'quicinteropio.c', native_flags)]
        elif library == 'erofs':
            if platform.system() != 'Linux':
                raise ValueError('the erofs package currently supports Linux')
            from format_provider import format_provider
            from compression_provider import codec_provider
            cflags, provider_libraries = format_provider('lz4', clang, native_flags, link_flags)
            archive_flags, archive_libraries = format_provider('tararchive', clang, native_flags, link_flags)
            codec_flags, codec_libraries = codec_provider('zstd', clang, native_flags, link_flags)
            native += [native_object(project, clang, base, 'erofs.c',
                                     [*native_flags, *cflags, *archive_flags, *codec_flags]), *provider_libraries, *archive_libraries, *codec_libraries]
        elif library in ('sha256', 'tararchive'):
            from format_provider import format_provider
            cflags, provider_libraries = format_provider(library, clang, native_flags, link_flags)
            native += [native_object(project, clang, base, library + '.c',
                                     [*native_flags, *cflags]), *provider_libraries]
        elif library == 'aes':
            native += [native_object(project, clang, base, 'aes.c', native_flags)]
            if platform.system() == 'Windows' or platform.system().startswith(('MSYS', 'MINGW', 'CYGWIN')):
                native += ['-lbcrypt']
            elif platform.system() != 'Darwin':
                native += ['-lcrypto']
        elif library in ('zstd', 'deflate'):
            from compression_provider import codec_provider
            cflags, archives = codec_provider(library, clang, native_flags, link_flags)
            native += [native_object(project, clang, base, library + '.c', [*native_flags, *cflags]), *archives]
        elif library == 'securecrypto':
            native += [native_object(project, clang, base, 'securecrypto.c', native_flags)]
        elif library == 'tlsverify':
            native += [native_object(project, clang, base, 'tlsverify.c', native_flags)]
            if platform.system() == 'Darwin':
                native += ['-framework', 'Security', '-framework', 'CoreFoundation']
            elif platform.system() == 'Windows' or platform.system().startswith(('MSYS', 'MINGW', 'CYGWIN')):
                native += ['-lcrypt32', '-lbcrypt', '-lncrypt', '-lws2_32']
            else:
                native += ['-lcrypto']
        elif library == 'keychain':
            if platform.system() != 'Darwin':
                raise ValueError('the keychain package requires macOS')
            native += [native_object(project, clang, base, 'keychain.c', native_flags),
                       '-framework', 'Security', '-framework', 'CoreFoundation']
        elif library == 'winnotify':
            if not (platform.system() == 'Windows' or platform.system().startswith(('MSYS', 'MINGW', 'CYGWIN'))):
                raise ValueError('the winnotify package requires Windows')
            notification_object = native_object(project, clang, base, 'winnotify.c', native_flags)
            if notification_object not in native:
                native += [notification_object]
            native += ['-luser32', '-lshell32', '-ladvapi32', '-lole32', '-luuid', '-lbcrypt', '-lruntimeobject']
        elif library == 'desktop':
            if platform.system() == 'Darwin':
                native += [native_object(project, clang, base, 'desktop.m',
                                         [*native_flags, '-fobjc-arc', '-fmodules'])]
                for framework in ('AppKit', 'UserNotifications', 'ServiceManagement', 'Network', 'IOKit'):
                    native += ['-framework', framework]
            else:
                native += [native_object(project, clang, base, 'desktop.c', native_flags)]
                if platform.system() == 'Windows' or platform.system().startswith(('MSYS', 'MINGW', 'CYGWIN')):
                    notification_object = native_object(project, clang, base, 'winnotify.c', native_flags)
                    if notification_object not in native:
                        native += [notification_object]
                    native += ['-luser32', '-lshell32', '-ladvapi32', '-lole32', '-loleaut32', '-liphlpapi',
                               '-luuid', '-lws2_32', '-lbcrypt', '-lruntimeobject']
        else:
            raise ValueError(f'the program uses an unknown native library: {library}')
    lto = lto_flags(clang, link_flags) if release == '1' else []
    math_libraries = [] if platform.system() == 'Darwin' else ['-lm']
    link_package_inputs(project, clang, native_flags, package_inputs, libraries, native,
                        lambda objects: link_program(clang, link_flags, lto, llvm, runtime,
                                                     objects, math_libraries, output, source))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'minyar: {error}', file=sys.stderr)
        sys.exit(1)
