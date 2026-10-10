#!/usr/bin/env python3
"""Exercise a real cold public incremental bootstrap with development limits."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if os.name == 'nt' or platform.system().startswith(('MSYS', 'MINGW', 'CYGWIN')):
    print('cold incremental bootstrap skipped: this frontend requires POSIX descriptors')
    sys.exit(0)
clang = shutil.which(os.environ.get('MINYAR_TEST_CLANG', os.environ.get('MINYAR_CLANG', 'clang')))
assert clang, 'Clang is required for the cold bootstrap test'

with tempfile.TemporaryDirectory(prefix='minyar cold toolchain ') as temporary:
    work = Path(temporary)
    project = work / 'project with spaces'
    project.mkdir()
    for name in ('compiler', 'bootstrap', 'runtime', 'vendor', 'tools', 'scripts', 'build-support', 'library'):
        shutil.copytree(ROOT / name, project / name)
    for name in ('Makefile', 'minyar'):
        shutil.copy2(ROOT / name, project / name)
    # A real compiler wrapper and matching linker exercise literal paths with
    # spaces, including Make's shell-quoted bootstrap LTO flag variable.
    selected = work / 'clang with spaces'
    selected.write_text('#!' + sys.executable + '\nimport os,sys\n'
                        'os.execv(' + repr(clang) + ',[' + repr(clang) + ',*sys.argv[1:]])\n')
    selected.chmod(0o755)
    matching = Path(clang).resolve().parent / 'ld.lld'
    linker = matching if matching.is_file() else Path(shutil.which('ld.lld') or '')
    if linker.is_file():
        (work / 'ld.lld').symlink_to(linker)
    environment = dict(os.environ)
    for name in ('LIMITED', 'SANITIZER_LIMITED', 'MAKEFLAGS', 'MFLAGS', 'COMPILER_LTO_FLAGS',
                 'LLVM_FLAGS', 'CC', 'LLVM_CC', 'MINYAR_CLANG_FLAGS', 'MINYAR_RUNTIME_FLAGS'):
        environment.pop(name, None)
    environment['MINYAR_CLANG'] = str(selected)
    (project / 'leaf.min').write_text('public function answer(values: List<Integer>): Integer {\n'
                                    'values.add(2)\nreturn values[0] + values[1]\n}\n')
    source = project / 'main.min'
    source.write_text('use "./leaf.min" as leaf\nprint(leaf.answer([40]))\n')
    binary = project / 'answer program'
    command = [str(project / 'minyar'), '--incremental', '--release', str(source), '-o', str(binary)]
    result = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=240)
    assert result.returncode == 0, result.stdout + result.stderr
    assert subprocess.check_output([binary], text=True) == '42\n'
    stamp = json.loads((project / 'build/.toolchain.json').read_text())
    options = shlex.split(stamp['flags']['COMPILER_LTO_FLAGS'])
    if platform.system() == 'Linux' and linker.is_file():
        assert '-Wl,--threads=1' in options, options
        assert '-fuse-ld=' + str(work / 'ld.lld') in options, options
    # Explicitly supplying the same safe flags is a supported opt-in and must
    # keep the caller's exact string, rather than rewriting configuration.
    explicit = stamp['flags']['COMPILER_LTO_FLAGS']
    result = subprocess.run(command, env=dict(environment, COMPILER_LTO_FLAGS=explicit),
                            capture_output=True, text=True, timeout=240)
    assert result.returncode == 0, result.stdout + result.stderr
    assert subprocess.check_output([binary], text=True) == '42\n'
    assert json.loads((project / 'build/.toolchain.json').read_text())['flags']['COMPILER_LTO_FLAGS'] == explicit
    report = {'platform': platform.platform(), 'clang': subprocess.check_output([clang, '--version'], text=True),
              'cold_default_returncode': 0, 'explicit_flags_returncode': 0, 'output': '42\n',
              'compiler_lto_options': options, 'limited_override': False,
              'resource_limits': {name: environment.get(name, default) for name, default in
                                  [('MINYAR_MAX_MEMORY_MIB', '768'), ('MINYAR_MAX_CPU_SECONDS', '240'),
                                   ('MINYAR_MAX_FILE_BLOCKS', '262144'), ('MINYAR_NICE_PRIORITY', '15')]},
              'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                for name in ('tools/clang-driver.py', 'compiler/compiler.min',
                                             'scripts/with-limits.sh', 'tests/toolchain-bootstrap.py')}}
    if os.environ.get('MINYAR_BOOTSTRAP_EVIDENCE'):
        Path(os.environ['MINYAR_BOOTSTRAP_EVIDENCE']).write_text(json.dumps(report, indent=2) + '\n')

print('cold public incremental bootstrap: default development limits, spaced toolchain paths and explicit LTO flags verified')
