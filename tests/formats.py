#!/usr/bin/env python3
"""One OCI layer through tar, gzip/zstd and standalone SHA under both link paths."""
import argparse
import ctypes
import ctypes.util
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import tempfile

from clang_helpers import clang_command, asan_leak_options
from llvm_sanitizer import prepare_llvm_for_link
from tar_support import strict_scan

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from compression_provider import codec_provider
from format_provider import format_provider


def qualify(options, directory):
    compiler = Path(os.environ.get('MINYAR_TEST_COMPILER', ROOT / 'build/minyarc'))
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    flags = ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if options.sanitize else ['-O2']
    environment = dict(os.environ, ASAN_OPTIONS=asan_leak_options(), UBSAN_OPTIONS='halt_on_error=1')
    commands = []
    def run(arguments, env=environment):
        result = subprocess.run(list(map(str, arguments)), capture_output=True, env=env, timeout=120)
        commands.append({'argv': list(map(str, arguments)), 'status': result.returncode,
                         'stderr': result.stderr.decode(errors='replace')})
        if result.returncode:
            raise RuntimeError(f'{arguments}\n{result.stdout.decode(errors="replace")}\n{commands[-1]["stderr"]}')
        return result.stdout
    raw = directory / 'formats.ll'
    run([compiler, ROOT / 'tests/formats.min', raw, '--library', ROOT / 'library'])
    assert 'securecrypto' not in raw.read_text() and 'monocypher' not in raw.read_text()
    manual_ir = directory / 'formats-manual.ll'
    manual_ir.write_bytes(raw.read_bytes())
    prepare_llvm_for_link(manual_ir, flags)
    runtime = directory / 'runtime.o'
    run(clang_command([clang, *flags, '-DMINYAR_SYSTEM_HEAP=1', '-c', ROOT / 'runtime/minyar_runtime.c', '-o', runtime]))
    native, libraries = [], []
    for kind in ('zstd', 'deflate', 'sha256', 'tararchive'):
        provider = codec_provider if kind in ('zstd', 'deflate') else format_provider
        cflags, libs = provider(kind, clang, flags)
        obj = directory / (kind + '.o')
        run(clang_command([clang, *flags, *cflags, '-c', ROOT / 'runtime/native' / (kind + '.c'), '-o', obj]))
        native.append(obj); libraries.extend(libs)
    manual = directory / 'formats-manual'
    run(clang_command([clang, *flags, '-Wno-override-module', manual_ir, runtime, *native, *libraries, '-o', manual]))
    normal = directory / 'formats-driver'
    driver_env = dict(environment, MINYAR_CLANG=clang, MINYAR_CLANG_FLAGS=shlex.join(flags), MINYAR_NATIVE_FLAGS=shlex.join(flags))
    run([sys.executable, ROOT / 'tools/clang-driver.py', 'link', ROOT, raw, runtime, normal, '0'], driver_env)
    output = run([manual])
    assert run([normal]) == output, 'manual and standard driver differ'
    rows = dict(line.split('=', 1) for line in output.decode().splitlines())
    layer, packed = bytes.fromhex(rows['tar']), bytes.fromhex(rows['zstd'])
    assert hashlib.sha256(layer).hexdigest() == rows['sha256']
    assert gzip.decompress(bytes.fromhex(rows['gzip'])) == layer
    library = ctypes.CDLL(ctypes.util.find_library('zstd'))
    library.ZSTD_decompress.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]
    library.ZSTD_decompress.restype = ctypes.c_size_t
    target = ctypes.create_string_buffer(len(layer))
    assert library.ZSTD_decompress(target, len(layer), packed, len(packed)) == len(layer)
    assert target.raw == layer
    spans, failure = strict_scan(layer)
    assert failure is None and len(spans) == 3
    assert spans[0][-1][b'VENDOR.binary'] == b'\x00\xff\n='
    with tarfile.open(fileobj=io.BytesIO(layer)) as archive:
        entries = archive.getmembers()
        assert [entry.name for entry in entries] == ['layer/binary', 'layer/.wh.deleted', 'layer/link']
        assert archive.extractfile(entries[0]).read() == bytes(range(256))
        assert entries[0].uid == 123 and entries[0].gid == 456 and entries[0].mtime == -1.25
        assert entries[1].size == 0 and entries[2].issym() and entries[2].linkname == 'binary'
    receipt = {'sanitize': options.sanitize, 'commands': commands,
               'layer_sha256': rows['sha256'], 'source_hashes': {}}
    for path in [ROOT / 'tests/formats.min', ROOT / 'tests/formats.py', raw, manual_ir,
                 *[ROOT / 'runtime/native' / (kind + '.c') for kind in ('zstd', 'deflate', 'sha256', 'tararchive')]]:
        receipt['source_hashes'][str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    (directory / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('formats: OCI layer, byte metadata, gzip/zstd, standalone streaming SHA, manual+standard link passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--artifacts', type=Path)
    options = parser.parse_args()
    if options.artifacts:
        options.artifacts.mkdir(parents=True, exist_ok=True)
        qualify(options, options.artifacts.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix='minyar-formats-') as name:
            qualify(options, Path(name))
