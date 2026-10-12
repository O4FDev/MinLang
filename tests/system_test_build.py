"""Language fixture builds can use admitted compiler bytes without bootstrap."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
from clang_helpers import launcher_command, native_path

def build_language(root, source, binary, *, prebuilt=False, sanitize=False):
    if not prebuilt:
        subprocess.run([*launcher_command(root), source, '-o', binary], check=True, timeout=180)
        return
    compiler = root/'build/minyarc'
    if not compiler.exists(): compiler = compiler.with_suffix('.exe')
    before = hashlib.sha256(compiler.read_bytes()).hexdigest()
    runtime = root/'build/minyar-default-runtime.o'
    original_runtime = hashlib.sha256(runtime.read_bytes()).hexdigest()
    ir = Path(binary).with_suffix('.ll')
    command = [native_path(compiler), native_path(source), native_path(ir), '--bounded-owners', '32', '--library', native_path(root/'library')]
    print('prebuilt compiler', before, 'runtime', original_runtime, flush=True)
    print('compile', command, flush=True)
    subprocess.run(command, check=True, timeout=120)
    env = os.environ.copy()
    if sanitize:
        runtime = Path(binary).with_suffix('.runtime.o')
        flags = ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
        subprocess.run([os.environ.get('MINYAR_TEST_CLANG', 'clang'), '-std=c11', '-DMINYAR_SYSTEM_HEAP=1',
                        *flags, '-c', root/'runtime/minyar_runtime.c', '-o', runtime], check=True, timeout=60)
        env['MINYAR_CLANG_FLAGS'] = ' '.join(flags) + ' -Wno-override-module'
        env['MINYAR_NATIVE_FLAGS'] = ' '.join(flags)
    command = [sys.executable, str(root/'tools/clang-driver.py'), 'link', str(root), str(ir), str(runtime), str(binary), '0']
    print('link', command, flush=True)
    subprocess.run(command, env=env, check=True, timeout=120)
    assert hashlib.sha256(compiler.read_bytes()).hexdigest() == before
    assert hashlib.sha256((root/'build/minyar-default-runtime.o').read_bytes()).hexdigest() == original_runtime
