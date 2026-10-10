#!/usr/bin/env python3
"""Actual independent Quinn/rustls UDP+mTLS interop (not a self round-trip)."""
import importlib.util
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tls_tests', ROOT / 'tests/tls-local.py')
fixtures = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixtures)

def main():
    parser = argparse.ArgumentParser(); modes = parser.add_mutually_exclusive_group(); modes.add_argument('--migration', action='store_true'); modes.add_argument('--resumption', action='store_true'); modes.add_argument('--early', action='store_true'); options = parser.parse_args()
    if options.migration: os.environ['MINYAR_QUINN_REBIND'] = '1'
    if options.early: options.resumption = True; os.environ['MINYAR_QUINN_EARLY'] = '1'
    if options.resumption: os.environ['MINYAR_QUINN_RESUME'] = '1'
    subprocess.run(['cargo', 'build', '--locked', '--manifest-path', str(ROOT / 'tests/interop/quinn/Cargo.toml'), '--target-dir', str(ROOT / 'build/interop-quinn')], check=True, timeout=300)
    with tempfile.TemporaryDirectory(prefix='minyar-quinn-') as directory:
        ca = fixtures.Certificates(directory); ca.root('root'); ca.leaf('server', 'root'); ca.leaf('client', 'root', usage='clientAuth')
        binary = Path(directory) / 'udp-server.exe'; fixtures.compile_program(ROOT / ('tests/quic-soak-server.min' if options.resumption else 'tests/quic-udp-server.min'), binary)
        command = [str(binary), str(ca.path('server', 'der')), str(ca.path('server', 'pk8')), str(ca.path('root', 'der'))]
        if options.resumption: command += ['5000', '16', 'early' if options.early else 'tickets']
        server = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            ready = server.stdout.readline().strip(); assert ready.startswith('READY '), ready
            client = subprocess.run([str(ROOT / 'build/interop-quinn/debug/minyar-quinn-interop'), ready.split()[1], str(ca.path('root', 'der')), str(ca.path('client', 'der')), str(ca.path('client', 'pk8'))], capture_output=True, text=True, timeout=20)
            out, err = server.communicate(timeout=20)
            assert client.returncode == 0 and server.returncode == 0, (client.returncode, client.stdout, client.stderr, server.returncode, out, err)
            if options.resumption: assert 'RESUMED 1' in out, out
            print(client.stdout, end=''); print(out, end='')
        finally:
            if server.poll() is None: server.kill(); server.communicate()
        client_binary = Path(directory) / 'udp-client.exe'; fixtures.compile_program(ROOT / ('tests/quic-udp-resumption.min' if options.resumption else 'tests/quic-udp-client.min'), client_binary)
        server = subprocess.Popen([str(ROOT / 'build/interop-quinn/debug/minyar-quinn-interop'), 'server', str(ca.path('root', 'der')), str(ca.path('server', 'der')), str(ca.path('server', 'pk8'))], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            ready = server.stdout.readline().strip(); assert ready.startswith('READY '), ready
            command = [str(client_binary), ready.split()[1], str(ca.path('root', 'der')), str(ca.path('client', 'der')), str(ca.path('client', 'pk8'))]
            if options.migration: command.append('migration')
            if options.early: command.append('early')
            client = subprocess.run(command, capture_output=True, text=True, timeout=20)
            out, err = server.communicate(timeout=20)
            assert client.returncode == 0 and server.returncode == 0, (client.returncode, client.stdout, client.stderr, server.returncode, out, err)
            print(client.stdout, end=''); print(out, end='')
        finally:
            if server.poll() is None: server.kill(); server.communicate()

if __name__ == '__main__': main()
