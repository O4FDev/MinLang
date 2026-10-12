#!/usr/bin/env python3
"""Exercise actual provider resolution, ABI probes and quoted prefix handling."""
import argparse
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from format_provider import provider_info, _windows


class Providers(unittest.TestCase):
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')

    def test_actual_provider_receipts(self):
        for kind in ('sha256', 'tararchive'):
            with self.subTest(kind=kind):
                info = provider_info(kind, self.clang)
                library = Path(info['library'])
                self.assertTrue(library.is_absolute() and library.is_file())
                self.assertIn(str(library), info['libraries'])
                self.assertEqual(len(info['sha256']), 64)
                self.assertTrue(any(item['path'].endswith(
                    'openssl/sha.h' if kind == 'sha256' else 'archive.h')
                    for item in info['inputs']))
                self.assertFalse(any('libssl' in value for value in info['libraries']))

    def test_bad_prefix_reports_missing_provider(self):
        with tempfile.TemporaryDirectory(prefix='minyar-missing-provider-') as name:
            for kind in ('sha256', 'tararchive'):
                with self.subTest(kind=kind), patch.dict(
                        os.environ, {'MINYAR_' + kind.upper() + '_PREFIX': name}):
                    with self.assertRaisesRegex(ValueError, 'headers.*provider prefix'):
                        provider_info(kind, self.clang)

    @unittest.skipIf(_windows(), 'MSYS2 requires the active compiler/CRT prefix')
    def test_real_prefix_with_space_apostrophe_and_header_refresh(self):
        # Real cc -M output contains Make escaping, not shell quoting. Exercise
        # the whole resolver/probe with actual headers and a selected library.
        original = provider_info('sha256', self.clang)
        with tempfile.TemporaryDirectory(prefix='minyar-provider-') as name:
            prefix = Path(name) / "provider space's"
            include, lib = prefix / 'include', prefix / 'lib'
            include.mkdir(parents=True)
            lib.mkdir()
            shutil.copytree(Path(original['include']) / 'openssl', include / 'openssl')
            # Debian's generated OpenSSL configuration is in a multiarch
            # directory; use exactly the files selected by the compiler.
            for item in original['inputs']:
                path = Path(item['path'])
                if path.name in ('opensslconf.h', 'configuration.h'):
                    shutil.copy2(path, include / 'openssl' / path.name)
            suffix = '.dylib' if sys.platform == 'darwin' else '.so'
            shutil.copy2(original['library'], lib / ('libcrypto' + suffix))
            with patch.dict(os.environ, {'MINYAR_SHA256_PREFIX': str(prefix)}):
                first = provider_info('sha256', self.clang)
                self.assertEqual(Path(first['include']), include)
                self.assertEqual(Path(first['library']).parent, lib)
                header = include / 'openssl' / 'sha.h'
                with header.open('a') as stream:
                    stream.write('\n/* provider cache input changed */\n')
                second = provider_info('sha256', self.clang)
                self.assertNotEqual(first['sha256'], second['sha256'])
                self.assertNotEqual(first['cflags'], second['cflags'])
                self.assertEqual(first['libraries'], second['libraries'])

    def test_disabled_sha_compatibility_api_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'compile/link probe failed'):
            provider_info('sha256', self.clang, ['-DOPENSSL_NO_DEPRECATED'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clang', default=os.environ.get('MINYAR_TEST_CLANG', 'clang'))
    arguments, remaining = parser.parse_known_args()
    Providers.clang = arguments.clang
    unittest.main(argv=[sys.argv[0], *remaining])
