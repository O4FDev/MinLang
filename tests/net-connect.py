#!/usr/bin/env python3
"""Real nonblocking TCP connect/refusal and address validation at O0/O2."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--sanitize', action='store_true'); options = parser.parse_args()
    if options.sanitize:
        for name in ('MINYAR_CLANG_FLAGS', 'MINYAR_NATIVE_FLAGS', 'MINYAR_RUNTIME_FLAGS'):
            os.environ[name] = '-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
        os.environ['ASAN_OPTIONS'] = 'detect_leaks=1'
        os.environ['UBSAN_OPTIONS'] = 'halt_on_error=1'
    with tempfile.TemporaryDirectory(prefix='minyar-net-connect-') as temporary:
        for mode in ('--debug', '--release'):
            output = Path(temporary) / ('connect' + ('.exe' if os.name == 'nt' else ''))
            command = [str(ROOT / 'minyar'), mode, str(ROOT / 'tests/net-connect.min'), '-o', str(output)]
            if os.name == 'nt': command.insert(0, 'bash')
            result = subprocess.run(command, capture_output=True, timeout=120)
            assert result.returncode == 0, result.stderr
            result = subprocess.run([str(output)], capture_output=True, timeout=10)
            assert result.returncode == 0 and result.stdout == b'nonblocking connect and recoverable refusal verified\n', result
        print('Nonblocking connect API: numeric addresses, refusal, real I/O and EOF passed')

if __name__ == '__main__': main()
