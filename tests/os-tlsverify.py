#!/usr/bin/env python3
"""Keep both freestanding trust adapters compatible and fail closed."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = '''use "tls" as tls
use "tlsverify" as trust
use "aes" as aes

for certificates in [Bytes(), Bytes(128)] {
    if trust.chain("localhost", certificates, Bytes()) == "" { fail("server trust accepted") }
    if trust.clientChain(certificates, Bytes()) == "" { fail("client trust accepted") }
    if trust.currentCertificateExpiry(certificates) != 0 { fail("positive certificate expiry") }
    if trust.currentCertificateExpiry(certificates) > trust.currentTimeMilliseconds() { fail("current peer identity") }
    if trust.signature(certificates, 0x0403, Bytes(), Bytes()) { fail("signature accepted") }
    if trust.sign(certificates, 0x0403, Bytes()).length != 0 { fail("signature produced") }
    if trust.p256Public(certificates).length != 0 { fail("public key produced") }
    if trust.p256(certificates, Bytes(65)).length != 0 { fail("shared secret produced") }
}
if trust.p256Key().length != 0 { fail("private key produced") }
if trust.currentTimeMilliseconds() != 0 { fail("clock fabricated") }
if aes.encrypt(Bytes(16), Bytes(12), Bytes(), Bytes()).length != 0 { fail("ciphertext produced") }
if aes.decrypt(Bytes(16), Bytes(12), Bytes(), Bytes(16)).length != 0 { fail("plaintext accepted") }
if aes.block(Bytes(16), Bytes(16)).length != 0 { fail("block produced") }
print("os-tlsverify: unavailable")
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--source', type=Path, default=ROOT)
    options = parser.parse_args()
    source = options.source.resolve()
    sys.path.insert(0, str(source / 'tests'))
    from clang_helpers import asan_leak_options, launcher_command

    environment = dict(os.environ, ASAN_OPTIONS=asan_leak_options() + ':halt_on_error=1',
                       UBSAN_OPTIONS='halt_on_error=1')
    if options.sanitize:
        flags = '-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
        for name in ('MINYAR_CLANG_FLAGS', 'MINYAR_NATIVE_FLAGS', 'MINYAR_RUNTIME_FLAGS'):
            environment[name] = flags
    with tempfile.TemporaryDirectory(prefix='minyar-os-tlsverify-') as temporary:
        directory = Path(temporary)
        fixture = directory / 'trust.min'
        fixture.write_text(PROGRAM)
        for architecture in ('x86_64', 'arm64'):
            for mode in ('--debug', '--release'):
                binary = directory / (architecture + mode + '.exe')
                command = [*launcher_command(source), mode, '--library',
                           str(source / 'os/arch' / architecture), str(fixture), '-o', str(binary)]
                print(shlex.join(command), flush=True)
                result = subprocess.run(command, cwd=source, env=environment,
                                        capture_output=True, text=True, timeout=180)
                assert result.returncode == 0, (command, result.returncode, result.stdout, result.stderr)
                result = subprocess.run([str(binary)], cwd=source, env=environment,
                                        capture_output=True, text=True, timeout=10)
                assert (result.returncode, result.stdout, result.stderr) == (
                    0, 'os-tlsverify: unavailable\n', ''), (architecture, mode, result)
                print(architecture + ' ' + mode + ': compatibility and rejection passed', flush=True)


if __name__ == '__main__':
    main()
