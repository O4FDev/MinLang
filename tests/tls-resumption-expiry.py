#!/usr/bin/env python3
"""Authenticate while valid, let a real certificate expire, reject PSK reuse."""
import argparse
from datetime import datetime, timedelta, timezone
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tls_tests', ROOT / 'tests/tls-local.py')
fixtures = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixtures)
def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--sanitize', action='store_true'); options = parser.parse_args()
    if options.sanitize:
        for name in ('MINYAR_CLANG_FLAGS', 'MINYAR_NATIVE_FLAGS', 'MINYAR_RUNTIME_FLAGS'):
            os.environ[name] = '-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
    with tempfile.TemporaryDirectory(prefix='minyar-resumption-expiry-') as directory:
        binary = Path(directory) / 'expiry.exe'; fixtures.compile_program(ROOT / 'tests/tls-resumption-expiry.min', binary)
        for mode in ('server', 'client'):
            case = Path(directory) / mode; case.mkdir(); ca = fixtures.Certificates(case); ca.root('root')
            expires = (datetime.now(timezone.utc) + timedelta(seconds=5)).replace(microsecond=0)
            for name, usage in [('server', 'serverAuth'), ('client', 'clientAuth')]:
                validity = (expires - timedelta(hours=1), expires) if name == mode else 'valid'
                ca.leaf(name, 'root', usage=usage, ec=True, validity=validity)
            result = subprocess.run([str(binary), str(ca.path('root', 'der')), str(ca.path('server', 'der')), str(ca.path('server', 'pk8')),
                                     str(ca.path('client', 'der')), str(ca.path('client', 'pk8')), mode, str(int(expires.timestamp() * 1000))],
                                    capture_output=True, text=True, timeout=12)
            assert result.returncode == 0, (mode, result.returncode, result.stdout, result.stderr)
            print(result.stdout, end='')
if __name__ == '__main__': main()
