#!/usr/bin/env python3
"""Actual codec provider contracts, including static linking and header identity."""
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.environ.get('MINYAR_COMPRESSION_PROVIDER_TOOLS', str(ROOT / 'tools')))
from compression_provider import codec_provider, _static_archive

WINDOWS = platform.system() == 'Windows' or platform.system().startswith(('MSYS', 'MINGW', 'CYGWIN'))


class Providers(unittest.TestCase):
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')

    @classmethod
    def setUpClass(cls):
        cls.flags, cls.libraries = codec_provider('zstd', cls.clang)
        cls.include = Path(cls.flags[cls.flags.index('-isystem') + 1])
        cls.archive = Path(cls.libraries[0])

    def prefix(self, directory):
        prefix = (Path(directory) / "provider space's").resolve()
        (prefix / 'include').mkdir(parents=True)
        (prefix / 'lib').mkdir()
        for name in ('zstd.h', 'zstd_errors.h'):
            shutil.copyfile(self.include / name, prefix / 'include' / name)
        return prefix

    def reject_archive(self, prefix, reason):
        with self.assertRaisesRegex(ValueError, reason):
            if WINDOWS:
                # Temp prefixes cannot satisfy the MSYS compiler/CRT rule.
                _static_archive(prefix / 'lib/libzstd.a', self.clang,
                                ('ZSTD_createCDict_advanced', 'ZSTD_createDDict_advanced'))
            else:
                with patch.dict(os.environ, {'MINYAR_ZSTD_PREFIX': str(prefix)}):
                    codec_provider('zstd', self.clang)

    def test_matched_real_archive_and_effective_flags(self):
        if WINDOWS:
            flags, libraries = codec_provider('zstd', self.clang, ['-O1'], ['-O1'])
            self.assertEqual(Path(libraries[0]), self.archive)
            self.assertTrue(flags)
            return
        with tempfile.TemporaryDirectory() as directory:
            prefix = self.prefix(directory)
            shutil.copyfile(self.archive, prefix / 'lib/libzstd.a')
            with patch.dict(os.environ, {'MINYAR_ZSTD_PREFIX': str(prefix)}):
                flags, libraries = codec_provider('zstd', self.clang, ['-O1'], ['-O1'])
                self.assertEqual(Path(libraries[0]), prefix / 'lib/libzstd.a')
                before = flags
                with (prefix / 'include/zstd_errors.h').open('a') as stream:
                    stream.write('\n/* cache input */\n')
                self.assertNotEqual(before, codec_provider('zstd', self.clang)[0])

    def test_renamed_real_shared_library_rejected(self):
        candidates = [self.archive.parent / name for name in ('libzstd.dylib', 'libzstd.so')]
        shared = next((path for path in candidates if path.is_file()), None)
        if shared is None:
            self.skipTest('provider has no shared-library fixture')
        with tempfile.TemporaryDirectory() as directory:
            prefix = self.prefix(directory)
            shutil.copyfile(shared, prefix / 'lib/libzstd.a')
            self.reject_archive(prefix, 'real static archive')

    def test_link_script_and_thin_archive_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = self.prefix(directory)
            for payload in (b'INPUT(-lzstd)\n', b'!<thin>\n'):
                (prefix / 'lib/libzstd.a').write_bytes(payload)
                self.reject_archive(prefix, 'real static archive')

    def test_short_coff_import_archive_rejected(self):
        # The COFF short import header is also accepted by archive tools on Unix.
        # It describes an import thunk, never embedded static implementation code.
        with tempfile.TemporaryDirectory() as directory:
            prefix = self.prefix(directory)
            member = Path(directory) / 'import.o'
            member.write_bytes(b'\0\0\xff\xff' + b'\0' * 16 + b'ZSTD_createDDict_advanced\0zstd.dll\0')
            subprocess.run(['ar', 'rcs', str(prefix / 'lib/libzstd.a'), str(member)], check=True,
                           capture_output=True)
            self.reject_archive(prefix, 'real static archive')

    def test_archive_without_advanced_definitions_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = self.prefix(directory)
            source, obj = Path(directory) / 'other.c', Path(directory) / 'other.o'
            source.write_text('int unrelated(void) { return 1; }\n')
            subprocess.run([self.clang, '-c', str(source), '-o', str(obj)], check=True,
                           capture_output=True)
            subprocess.run(['ar', 'rcs', str(prefix / 'lib/libzstd.a'), str(obj)], check=True,
                           capture_output=True)
            self.reject_archive(prefix, 'missing static definitions')

    def test_foreign_primary_and_secondary_headers_rejected(self):
        for codec, names in (('zstd', ('zstd.h', 'zstd_errors.h')),
                             ('deflate', ('zlib.h', 'zconf.h'))):
            flags, _ = codec_provider(codec, self.clang)
            include = Path(flags[flags.index('-isystem') + 1])
            with tempfile.TemporaryDirectory() as directory:
                for name in names:
                    with self.subTest(codec=codec, header=name):
                        foreign = Path(directory) / name
                        shutil.copyfile(include / name, foreign)
                        # zlib's quoted secondary include is relative to zlib.h;
                        # forced inclusion can still inject a foreign zconf.
                        options = ['-include', str(foreign)] if name == 'zconf.h' else ['-I', directory]
                        with self.assertRaisesRegex(ValueError, 'headers must belong to provider prefix'):
                            codec_provider(codec, self.clang, options)
                        foreign.unlink()

    @unittest.skipIf(WINDOWS, 'Windows backslash is a path separator')
    def test_literal_backslash_prefix_has_explicit_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = self.prefix(directory)
            target = prefix.with_name('provider back\\slash')
            prefix.rename(target)
            shutil.copyfile(self.archive, target / 'lib/libzstd.a')
            with patch.dict(os.environ, {'MINYAR_ZSTD_PREFIX': str(target)}):
                with self.assertRaisesRegex(ValueError, 'literal backslash provider paths are unsupported'):
                    codec_provider('zstd', self.clang)


if __name__ == '__main__':
    unittest.main()
