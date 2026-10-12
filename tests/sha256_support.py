"""Small SHA-only compiler/link helpers; never bootstrap or build the compiler."""
import os
from pathlib import Path
import shlex
import subprocess
from llvm_sanitizer import prepare_llvm_for_link

ROOT = Path(__file__).resolve().parents[1]
RECORDED_COMMANDS = []


def run(arguments, **kwargs):
    RECORDED_COMMANDS.append(list(map(str, arguments)))
    result = subprocess.run(list(map(str, arguments)), capture_output=True, text=True,
                            timeout=int(os.environ.get('MINYAR_TEST_TIMEOUT', '120')), **kwargs)
    if result.returncode:
        raise RuntimeError(f'{arguments}\n{result.stdout}\n{result.stderr}')
    return result


def compile_min(source, directory, module='sha256', optimization='-O2', native=(), sanitize=False):
    compiler = Path(os.environ.get('MINYAR_TEST_COMPILER', ROOT / 'build/minyarc'))
    runtime = Path(os.environ.get('MINYAR_TEST_RUNTIME', ROOT / 'build/minyar-default-runtime.o'))
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    staged = directory / (source.stem + '-' + module + '.min')
    staged.write_text(source.read_text().replace('use "sha256" as sha', f'use "{module}" as sha'))
    llvm = staged.with_suffix('.ll')
    library = directory / 'library'
    library.mkdir(exist_ok=True)
    for item in (ROOT / 'library').iterdir():
        target = library / item.name
        if not target.exists():
            target.symlink_to(item, target_is_directory=item.is_dir())
    for name in ('sha256test', 'sha256pure'):
        target = library / (name + '.min')
        fixture = ROOT / 'tests' / (name + '.min')
        if fixture.exists() and not target.exists():
            target.symlink_to(fixture)
    run([compiler, staged, llvm, '--library', library])
    ir = llvm.read_text()
    if 'securecrypto' in ir or 'monocypher' in ir:
        raise AssertionError('standalone SHA unexpectedly depends on securecrypto')
    executable = staged.with_suffix('')
    flags = shlex.split(os.environ.get('MINYAR_TEST_LINK_FLAGS', ''))
    if sanitize:
        optimization = '-O1'
        flags += ['-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
        runtime = directory / 'sha256-runtime-sanitize.o'
        if not runtime.exists():
            run([clang, optimization, *flags, '-c', ROOT / 'runtime/minyar_default_runtime.c', '-o', runtime])
    prepare_llvm_for_link(llvm, flags)
    if sanitize and 'sanitize_address' not in llvm.read_text():
        raise AssertionError('generated Minyar IR was not ASan-annotated')
    if sanitize:
        definitions = [line for line in llvm.read_text().splitlines() if line.startswith('define ')]
        if not all('sanitize_address' in line for line in definitions):
            raise AssertionError('not every Minyar function was ASan-annotated')
        print(f'ASan annotated all {len(definitions)} generated functions; sanitized runtime/native sources: {source.name}')
    providers = []
    if module == 'sha256' and (ROOT / 'runtime/native/sha256.c').exists():
        providers.append(ROOT / 'runtime/native/sha256.c')
    if 'minyar_sha256test_' in ir:
        providers.append(ROOT / 'tests/sha256-test-native.c')
    if providers:
        cflags = shlex.split(run(['pkg-config', '--cflags', 'libcrypto']).stdout)
        flags += shlex.split(run(['pkg-config', '--libs', 'libcrypto']).stdout)
        for provider in providers:
            obj = directory / (provider.stem + ('-sanitize' if sanitize else '') + '.o')
            if not obj.exists():
                run([clang, optimization, *cflags, *flags, '-c', provider, '-o', obj])
            native = [obj, *native]
    # Deliberate IMAGE-3-style direct link: no automatic native package discovery.
    command = [clang, optimization, '-Wno-override-module', llvm, runtime, *native, *flags]
    if os.name != 'nt':
        command.append('-lm')
    run([*command, '-o', executable])
    return executable
