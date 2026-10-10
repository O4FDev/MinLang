#!/usr/bin/env python3
"""Virtual-clock authenticated peers under loss, duplication and reordering."""
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tls_tests', ROOT / 'tests/tls-local.py')
fixtures = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixtures)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--sanitize', action='store_true'); modes = parser.add_mutually_exclusive_group(); modes.add_argument('--key-update', action='store_true'); modes.add_argument('--migration', action='store_true'); modes.add_argument('--server-protocol', action='store_true'); modes.add_argument('--resumption', action='store_true'); modes.add_argument('--quic-resumption', action='store_true'); modes.add_argument('--early', action='store_true'); modes.add_argument('--fallback', action='store_true'); modes.add_argument('--congestion',action='store_true'); modes.add_argument('--stream-control',action='store_true'); modes.add_argument('--stream-churn',action='store_true'); options = parser.parse_args()
    if options.sanitize:
        for name in ('MINYAR_CLANG_FLAGS', 'MINYAR_NATIVE_FLAGS', 'MINYAR_RUNTIME_FLAGS'):
            os.environ[name] = '-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
    with tempfile.TemporaryDirectory(prefix='minyar-quic-pair-') as directory:
        ca = fixtures.Certificates(directory); ca.root('root'); ca.leaf('server', 'root'); ca.leaf('client', 'root', usage='clientAuth')
        name = 'tests/quic-migration.min' if options.migration else ('tests/quic-key-update.min' if options.key_update else 'tests/quic-transport.min')
        if options.server_protocol: name = 'tests/tls-server-protocol.min'
        if options.resumption: name = 'tests/tls-resumption.min'
        if options.quic_resumption: name = 'tests/quic-resumption.min'
        if options.early: name = 'tests/quic-early.min'
        if options.fallback: name = 'tests/transport.min'
        if options.congestion: name = 'tests/quic-congestion.min'
        if options.stream_control: name='tests/quic-stream-control.min'
        if options.stream_churn: name='tests/quic-stream-churn.min'
        binary = Path(directory) / 'transport.exe'; fixtures.compile_program(ROOT / name, binary)
        result = subprocess.run([str(binary), str(ca.path('root', 'der')), str(ca.path('server', 'der')), str(ca.path('server', 'pk8')),
                                 str(ca.path('client', 'der')), str(ca.path('client', 'pk8'))], capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
        print(result.stdout, end='')


if __name__ == '__main__': main()
