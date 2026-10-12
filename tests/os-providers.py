#!/usr/bin/env python3
"""Freestanding provider symbols, real crypto vectors and IP literal parity."""
import argparse
import os
from pathlib import Path
import random
import shlex
import socket
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {'minyar_net_ipVersion', *('minyar_securecrypto_' + name for name in
            ('x25519', 'chacha20', 'poly1305', 'seal', 'open', 'equal'))}
DRIVER = r'''#include <stdio.h>
#include <string.h>
#include "minyar_native.h"
extern long long minyar_net_ipVersion(const MinyarText *address);
static int hex(int c) { return c <= '9' ? c - '0' : c - 'a' + 10; }
int main(void) {
    unsigned char bytes[1024]; char line[2048];
    MinyarText invalid = {NULL, -1, 0, NULL, NULL};
    if (minyar_net_ipVersion(&invalid) != 0) return 1;
    invalid.byte_length = 0;
    if (minyar_net_ipVersion(&invalid) != 0) return 2;
    invalid.byte_length = 256;
    if (minyar_net_ipVersion(&invalid) != 0) return 3;
    while (fgets(line, sizeof(line), stdin)) {
        size_t count = strcspn(line, "\n");
        if (count % 2 || count > sizeof(bytes) * 2) return 4;
        for (size_t i = 0; i < count / 2; i++) bytes[i] = (unsigned char)(hex(line[i * 2]) * 16 + hex(line[i * 2 + 1]));
        MinyarText text = {bytes, (long long)count / 2, 0, NULL, NULL};
        printf("%lld\n", minyar_net_ipVersion(&text));
    }
    return 0;
}
'''


def run(argv, environment, expected=None, data=None):
    print(shlex.join(map(str, argv)), flush=True)
    result = subprocess.run(list(map(str, argv)), env=environment,
                            capture_output=True, input=data, timeout=180)
    assert result.returncode == 0, (argv, result.returncode, result.stdout, result.stderr)
    assert not result.stderr if expected is not None else True, result.stderr
    if expected is not None:
        assert result.stdout == expected, (argv, result.stdout, expected)
    return result.stdout


def oracle(value):
    if not 0 < len(value) < 256 or b'\0' in value:
        return 0
    try:
        text = value.decode('ascii')
    except UnicodeDecodeError:
        return 0
    for family, version in ((socket.AF_INET, 4), (socket.AF_INET6, 6)):
        try:
            socket.inet_pton(family, text)
            return version
        except OSError:
            pass
    return 0


def cases():
    values = [b'', b'localhost', b'example.com', b'127.0.0.1', b'0.0.0.0', b'255.255.255.255',
              b'01.2.3.4', b'1.02.3.4', b'1.2.3.004', b'256.0.0.1', b'1.2.3', b'1.2.3.4.',
              b'1.2.3.4\0x', b'::', b'::1', b'2001:db8::1', b'::ffff:192.0.2.1', b'::192.0.2.1',
              b'1:2:3:4:5:6:192.0.2.1', b'1:2:3:4:5:192.0.2.1', b'::ffff:192.00.2.1',
              b'1:2:3:4:5:6:7:8', b'1:2:3:4:5:6:7:8::', b'1:2:3:4:5:6:7', b'1:2:3:4:5:6:7:8:9',
              b'1::2::3', b':::', b':1', b'1:', b'::fffff', b'[::1]', b'fe80::1%eth0', b' ::1',
              b'::1 ', b'\xc3\xa9', b'a' * 255, b'a' * 256, b'0' * 300]
    rng = random.Random(20261012)
    for _ in range(1000):
        values.append(socket.inet_ntop(socket.AF_INET, rng.randbytes(4)).encode())
        values.append(socket.inet_ntop(socket.AF_INET6, rng.randbytes(16)).encode())
    for omitted in range(1, 9):
        for start in range(9 - omitted):
            left = ':'.join(['abcd'] * start)
            right = ':'.join(['1234'] * (8 - start - omitted))
            values.append((left + '::' + right).encode())
    originals = values[:]
    alphabet = b'0123456789abcdefABCDEF:.%[]xyz -+\x00'
    for _ in range(12000):
        value = rng.choice(originals)
        at = rng.randrange(len(value) + 1)
        operation = rng.randrange(3)
        ch = bytes([rng.choice(alphabet)])
        values.append(value[:at] + (ch if operation != 1 else b'') + value[at + (operation != 0):])
    return sorted(set(values))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT)
    parser.add_argument('--sanitize', action='store_true')
    options = parser.parse_args()
    source = options.source.resolve()
    clang = os.environ.get('MINYAR_TEST_CLANG', os.environ.get('MINYAR_CLANG', 'clang'))
    resource = subprocess.check_output([clang, '-print-resource-dir'], text=True).strip()
    environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')
    with tempfile.TemporaryDirectory(prefix='minyar-os-providers-') as temporary:
        directory = Path(temporary)
        common = ['-O2', '-flto', '-ffreestanding', '-fno-builtin', '-nostdinc',
                  '-isystem', resource + '/include', '-isystem', source / 'runtime/freestanding/include',
                  '-fno-stack-protector', '-fno-pic', '-Wall', '-Wno-unused-function']
        for arch, target, extra in [('x86_64', 'x86_64-unknown-none-elf', ['-march=x86-64-v2', '-mno-red-zone']),
                                     ('arm64', 'aarch64-unknown-none-elf', [])]:
            obj = directory / (arch + '.o')
            run([clang, '--target=' + target, *extra, *common, '-c',
                 source / 'runtime/freestanding/freestanding.c', '-o', obj], environment)
            symbols = run(['llvm-nm', '--defined-only', obj], environment).decode()
            names = {line.split()[-1] for line in symbols.splitlines()}
            assert REQUIRED <= names, (arch, 'missing freestanding providers', sorted(REQUIRED - names))
        flags = (['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
                 if options.sanitize else ['-O2'])
        provider = directory / 'providers.o'
        run([clang, *common, *flags, '-c', source / 'runtime/freestanding/providers.c', '-o', provider], environment)
        runtime = directory / 'runtime.o'
        run([clang, *flags, '-c', source / 'runtime/minyar_default_runtime.c', '-o', runtime], environment)
        ir = directory / 'crypto.ll'
        run([source / 'build/minyarc', source / 'tests/securecrypto.min', ir,
             '--bounded-owners', '32', '--library', source / 'library'], environment)
        if options.sanitize:
            instrumented = directory / 'crypto-sanitize.ll'
            run(['python3', source / 'tests/llvm_sanitizer.py', ir, instrumented], environment)
            ir = instrumented
        binary = directory / 'vectors'
        run([clang, *flags, '-Wno-override-module', '-fuse-ld=lld', '-no-pie', ir, runtime, provider, '-lm', '-o', binary], environment)
        output = run([binary], environment,
                     expected=b'Native crypto: RFC 7748/8439, low-order X25519 rejection, tag tampering, empty messages, invalid lengths and counter bounds passed\n')
        print(output.decode(), end='')
        driver = directory / 'ip.c'
        driver.write_text(DRIVER)
        binary = directory / 'ip'
        run([clang, *flags, '-fuse-ld=lld', '-no-pie', '-I', source / 'runtime', driver, runtime, provider, '-lm', '-o', binary], environment)
        selected = cases()
        expected = ''.join(str(oracle(value)) + '\n' for value in selected).encode()
        run([binary], environment, expected=expected,
            data=b''.join(value.hex().encode() + b'\n' for value in selected))
        print(f'IP literal contract: {len(selected)} canonical/malformed/NUL/hostname controls match inet_pton')


if __name__ == '__main__':
    main()
