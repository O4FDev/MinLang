#!/usr/bin/env python3
"""Matched full SHA-256 operations. Run samples only in a parent-granted quiet slot.

Boat: flock /tmp/ws5-benchmark.lock python3 tests/sha256-bench.py ...
Portable C is unmodified Mbed TLS SHA-256 built with a minimal no-assembly config.
Set MINYAR_SHA256_PORTABLE_PREFIX to its source checkout (see evidence README).
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import statistics
import tempfile
from sha256_support import ROOT, RECORDED_COMMANDS, compile_min, run


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(directory):
    RECORDED_COMMANDS.clear()
    directory.mkdir(parents=True, exist_ok=True)
    binaries = {module: compile_min(ROOT / 'tests/sha256-bench.min', directory, module, '-O3')
                for module in ('sha256pure', 'sha256')}
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    openssl = directory / 'openssl-reference'
    command = [clang, '-O3', '-Wno-deprecated-declarations', ROOT / 'tests/sha256-bench.c',
               *shlex.split(run(['pkg-config', '--cflags', '--libs', 'libcrypto']).stdout), '-o', openssl]
    run(command)
    binaries.update(openssl_evp=openssl, openssl_sha=openssl, openssl_no_hw=openssl)
    portable = os.environ.get('MINYAR_SHA256_PORTABLE_PREFIX')
    portable_sources = []
    if portable:
        prefix = Path(portable)
        config = directory / 'portable-config.h'
        config.write_text('#define MBEDTLS_SHA256_C\n')
        portable_sources = [prefix / 'library/sha256.c', prefix / 'library/platform_util.c']
        executable = directory / 'portable-reference'
        run([clang, '-O3', '-DSHA256_PORTABLE_MBEDTLS', '-DMBEDTLS_CONFIG_FILE="portable-config.h"',
             '-I' + str(directory), '-I' + str(prefix / 'include'), '-I' + str(prefix / 'library'),
             ROOT / 'tests/sha256-bench.c', *portable_sources,
             *shlex.split(run(['pkg-config', '--cflags', '--libs', 'libcrypto']).stdout), '-o', executable])
        binaries['portable_c'] = executable
    libdir = Path(run(['pkg-config', '--variable=libdir', 'libcrypto']).stdout.strip())
    provider_files = [path.resolve() for path in [libdir / 'libcrypto.so', libdir / 'libcrypto.dylib'] if path.exists()]
    compiler = Path(os.environ.get('MINYAR_TEST_COMPILER', ROOT / 'build/minyarc'))
    runtime = Path(os.environ.get('MINYAR_TEST_RUNTIME', ROOT / 'build/minyar-default-runtime.o'))
    manifest = {
        'binaries': {name: str(path.resolve()) for name, path in binaries.items()},
        'host': platform.platform(),
        'clang': run([clang, '--version']).stdout,
        'openssl': run(['openssl', 'version', '-a']).stdout,
        'cpu': run(['sh', '-c', 'lscpu 2>/dev/null || sysctl -n machdep.cpu.brand_string']).stdout,
        'source_hashes': {str(path.relative_to(ROOT)): sha(path) for path in [
            ROOT / 'library/sha256.min', ROOT / 'tests/sha256pure.min',
            ROOT / 'tests/sha256-bench.min', ROOT / 'tests/sha256-bench.c', ROOT / 'tests/sha256-bench.py',
            ROOT / 'tests/sha256_support.py', ROOT / 'tests/sha256-test-native.c',
            *([ROOT / 'runtime/native/sha256.c'] if (ROOT / 'runtime/native/sha256.c').exists() else [])]},
        'portable_source_hashes': {str(path): sha(path) for path in portable_sources},
        'provider_hashes': {str(path): sha(path) for path in provider_files},
        'toolchain_hashes': {str(path): sha(path) for path in [compiler, runtime]},
        'binary_hashes': {name: sha(path) for name, path in binaries.items()},
        'preparation_commands': RECORDED_COMMANDS.copy(),
    }
    (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=int, default=5)
    parser.add_argument('--bytes', type=int, default=1048576)
    parser.add_argument('--iterations', type=int, default=64)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--build-dir', type=Path)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--run-prepared', action='store_true')
    args = parser.parse_args()
    if args.samples < 1 or args.bytes < 0 or args.iterations < 1:
        parser.error('samples/iterations must be positive and bytes nonnegative')
    if (args.prepare_only or args.run_prepared) and not args.build_dir:
        parser.error('--prepare-only/--run-prepared requires --build-dir')
    with tempfile.TemporaryDirectory(prefix='minyar-sha256-bench-') as temporary:
        directory = (args.build_dir or Path(temporary)).resolve()
        manifest = json.loads((directory / 'manifest.json').read_text()) if args.run_prepared else prepare(directory)
        if args.prepare_only:
            print('Prepared SHA benchmark binaries:', directory)
            return
        if 'portable_c' not in manifest['binaries']:
            parser.error('portable C reference required: set MINYAR_SHA256_PORTABLE_PREFIX during preparation')
        for name, path in manifest['binaries'].items():
            if sha(path) != manifest['binary_hashes'][name]:
                raise AssertionError(('prepared binary changed', name, path))
        records = []
        for mode in ('oneshot', 'lifecycle'):
            names = list(manifest['binaries'])
            # Rotate reference order; each binary gets the same warmed operation.
            for sample in range(-1, args.samples):
                order = names[sample % len(names):] + names[:sample % len(names)]
                sums = set()
                for name in order:
                    command = [manifest['binaries'][name], args.bytes, args.iterations, mode]
                    if name.startswith('openssl') or name == 'portable_c':
                        command.append('evp' if name == 'openssl_evp' else 'sha')
                    environment = os.environ.copy()
                    if name == 'openssl_no_hw':
                        environment['OPENSSL_ia32cap'] = '0'
                    result = run(command, env=environment)
                    elapsed, checksum = map(int, result.stdout.split())
                    sums.add(checksum)
                    if sample >= 0:
                        record = {'mode': mode, 'sample': sample, 'provider': name,
                                  'elapsed_ns': elapsed, 'checksum': checksum,
                                  'command': list(map(str, command)),
                                  'environment': {'OPENSSL_ia32cap': '0'} if name == 'openssl_no_hw' else {}}
                        records.append(record)
                        print(json.dumps(record), flush=True)
                if len(sums) != 1:
                    raise AssertionError(('mismatched complete-operation digests', mode, sample, sums))
        medians = {mode: {name: statistics.median(r['elapsed_ns'] for r in records
                    if r['mode'] == mode and r['provider'] == name) for name in names}
                   for mode in ('oneshot', 'lifecycle')}
        evidence = {**manifest, 'bytes': args.bytes, 'iterations': args.iterations,
                    'samples': args.samples, 'records': records, 'median_ns': medians,
                    'pure_vs_evp': {mode: medians[mode]['sha256pure'] / medians[mode]['openssl_evp'] for mode in medians}}
        if args.output:
            args.output.write_text(json.dumps(evidence, indent=2) + '\n')
        print(json.dumps({'median_ns': medians, 'pure_vs_evp': evidence['pure_vs_evp']}))


if __name__ == '__main__':
    main()
