#!/usr/bin/env python3
"""Real Windows providers and compiled Minyar APIs; no OS trust-root changes.

The certificate fixture creates and removes its own nonexportable CNG test key.
Login writes are redirected to a test-only per-process registry key. GUI widgets
stay hidden; the tray is tested when this Windows session has Explorer.
"""
import os
from pathlib import Path
import subprocess
import tempfile
from clang_helpers import windows_host

ROOT = Path(__file__).resolve().parents[1]


def main():
    if not windows_host():
        raise SystemExit('this correctness gate requires native Windows APIs')
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    ROOT.joinpath('build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='windows-bridge-', dir=ROOT/'build') as directory:
        temp = Path(directory)
        fixtures = [
            ('windows-certificate', [], ['wincert.c', 'tlsverify.c'],
             ['crypt32', 'ncrypt', 'bcrypt', 'ws2_32']),
            ('windows-desktop', ['-DMINYAR_DESKTOP_TEST=1'], ['desktop.c'],
             ['user32', 'shell32', 'advapi32', 'ole32', 'oleaut32', 'iphlpapi', 'uuid', 'ws2_32', 'bcrypt']),
            ('windows-native', ['-DMINYAR_WINDOWS_TEST=1'], ['windows.c'],
             ['user32', 'gdi32', 'shell32']),
        ]
        for name, defines, providers, libraries in fixtures:
            executable = temp/(name+'.exe')
            subprocess.run([clang, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                '-DMINYAR_SYSTEM_HEAP=1', *defines, ROOT/'tests'/f'{name}.c',
                ROOT/'runtime/minyar_runtime.c',
                *(ROOT/'runtime/native'/provider for provider in providers),
                *('-l'+library for library in libraries), '-lm', '-o', executable],
                check=True, timeout=60)
            subprocess.run([executable], check=True, timeout=30)
            if name == 'windows-native':
                result = subprocess.run([executable, 'stale'], capture_output=True, text=True, timeout=30)
                assert result.returncode == 1 and 'invalid or destroyed handle' in result.stderr, result
        for mode in ['--debug', '--release']:
            executable = temp/('contract-'+mode[2:]+'.exe')
            subprocess.run([ROOT/'minyar', mode, ROOT/'tests/windows-bridge.min', '-o', executable],
                           check=True, timeout=120)
            result = subprocess.run([executable], check=True, capture_output=True, text=True, timeout=30)
            assert result.stdout == 'Windows native package contracts verified\n', result


if __name__ == '__main__':
    main()
