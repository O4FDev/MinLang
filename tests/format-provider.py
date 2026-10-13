#!/usr/bin/env python3
"""Exercise actual provider resolution, ABI probes and quoted prefix handling."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from format_provider import provider_info, _probe_source, _windows


class Providers(unittest.TestCase):
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    kinds = ('sha256', 'tararchive')

    def copy_sha_prefix(self, name, *, shared=False):
        original = provider_info('sha256', self.clang)
        prefix = (Path(name) / "provider space's").resolve()
        include, lib = prefix / 'include', prefix / 'lib'
        include.mkdir(parents=True)
        lib.mkdir()
        shutil.copytree(Path(original['include']) / 'openssl', include / 'openssl')
        for item in original['inputs']:
            path = Path(item['path'])
            if path.name in ('opensslconf.h', 'configuration.h'):
                shutil.copy2(path, include / 'openssl' / path.name)
        library = Path(original['library'])
        if shared:
            suffix = '.dylib' if sys.platform == 'darwin' else '.so'
        else:
            library = library.parent / 'libcrypto.a'
            if not library.is_file():
                self.skipTest('OpenSSL development static archive is absent')
            suffix = '.a'
        shutil.copy2(library, lib / ('libcrypto' + suffix))
        return prefix

    def test_actual_provider_receipts(self):
        for kind in self.kinds:
            with self.subTest(kind=kind):
                info = provider_info(kind, self.clang)
                library = Path(info['library'])
                self.assertTrue(library.is_absolute() and library.is_file())
                self.assertIn(str(library), info['libraries'])
                self.assertEqual(len(info['sha256']), 64)
                runtime = info['runtime_library']
                if runtime:
                    self.assertIn(runtime, [item['path'] for item in info['inputs']])
                    self.assertIn(Path(info['prefix']), Path(runtime).parents)
                    if not _windows():
                        self.assertEqual(runtime, info['library'])
                else:
                    self.assertTrue(library.name.endswith('.a'))
                for item in info['inputs']:
                    self.assertEqual(item['sha256'], hashlib.sha256(
                        Path(item['path']).read_bytes()).hexdigest())
                self.assertTrue(any(item['path'].endswith(
                    'openssl/sha.h' if kind == 'sha256' else 'archive.h')
                    for item in info['inputs']))
                self.assertFalse(any('libssl' in value for value in info['libraries']))

    def test_bad_prefix_reports_missing_provider(self):
        with tempfile.TemporaryDirectory(prefix='minyar-missing-provider-') as name:
            for kind in self.kinds:
                with self.subTest(kind=kind), patch.dict(
                        os.environ, {'MINYAR_' + kind.upper() + '_PREFIX': name}):
                    with self.assertRaisesRegex(ValueError, 'headers.*provider prefix'):
                        provider_info(kind, self.clang)

    @unittest.skipIf(_windows(), 'MSYS2 requires the active compiler/CRT prefix')
    def test_real_prefix_with_space_apostrophe_and_header_refresh(self):
        # Real cc -M output contains Make escaping, not shell quoting. Exercise
        # the whole resolver/probe with actual headers and a selected library.
        with tempfile.TemporaryDirectory(prefix='minyar-provider-') as name:
            prefix = self.copy_sha_prefix(name)
            include, lib = prefix / 'include', prefix / 'lib'
            with patch.dict(os.environ, {'MINYAR_SHA256_PREFIX': str(prefix)}):
                first = provider_info('sha256', self.clang)
                self.assertEqual(Path(first['include']), include)
                self.assertEqual(Path(first['library']).parent, lib)
                self.assertTrue(first['library'].endswith('.a'))
                self.assertIsNone(first['runtime_library'])
                header = include / 'openssl' / 'sha.h'
                with header.open('a') as stream:
                    stream.write('\n/* provider cache input changed */\n')
                second = provider_info('sha256', self.clang)
                self.assertNotEqual(first['sha256'], second['sha256'])
                self.assertNotEqual(first['cflags'], second['cflags'])
                self.assertEqual(first['libraries'], second['libraries'])
                # Generated secondary configuration must also affect the cache.
                with (include / 'openssl/opensslconf.h').open('a') as stream:
                    stream.write('\n/* secondary provider input changed */\n')
                third = provider_info('sha256', self.clang)
                self.assertNotEqual(second['sha256'], third['sha256'])

    @unittest.skipIf(_windows(), 'copied prefixes cannot use the active MSYS2 CRT')
    def test_copied_shared_provider_wrong_loaded_image_is_rejected(self):
        # Keep the real install name/SONAME. The normal consumer loads the
        # original image even though the copied file was given to the linker.
        with tempfile.TemporaryDirectory(prefix='minyar-loaded-provider-') as name:
            prefix = self.copy_sha_prefix(name, shared=True)
            with patch.dict(os.environ, {'MINYAR_SHA256_PREFIX': str(prefix)}):
                with self.assertRaisesRegex(ValueError, 'loaded provider image.*selected library'):
                    provider_info('sha256', self.clang)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'ELF loader regression')
    def test_normal_loader_environment_can_override_rpath(self):
        original = provider_info('sha256', self.clang)
        with tempfile.TemporaryDirectory(prefix='minyar-loader-override-') as name:
            foreign = Path(name).resolve() / 'foreign'
            foreign.mkdir()
            # The real SONAME has to exist for LD_LIBRARY_PATH to win.
            shutil.copy2(original['library'], foreign / Path(original['library']).name)
            with patch.dict(os.environ, {'LD_LIBRARY_PATH': str(foreign)}):
                with self.assertRaisesRegex(ValueError, 'loaded provider image.*selected library'):
                    provider_info('sha256', self.clang)

    @unittest.skipIf(_windows(), 'copied prefixes cannot use the active MSYS2 CRT')
    def test_foreign_openssl_secondary_header_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='minyar-secondary-header-') as name:
            prefix = self.copy_sha_prefix(name)
            foreign = prefix.parent / 'foreign' / 'openssl'
            foreign.mkdir(parents=True)
            shutil.copy2(prefix / 'include/openssl/opensslconf.h', foreign / 'opensslconf.h')
            shutil.copy2(foreign / 'opensslconf.h', foreign.parent / 'opensslconf.h')
            with patch.dict(os.environ, {'MINYAR_SHA256_PREFIX': str(prefix)}):
                for flags in (['-I' + str(foreign.parent)],
                              ['-include', str(foreign / 'opensslconf.h')],
                              ['-include', str(foreign.parent / 'opensslconf.h')]):
                    with self.subTest(flags=flags), self.assertRaisesRegex(
                            ValueError, 'provider-owned header.*provider prefix'):
                        provider_info('sha256', self.clang, flags)

    def test_foreign_archive_secondary_header_is_rejected(self):
        if 'tararchive' not in self.kinds:
            self.skipTest('libarchive development headers excluded from this host run')
        original = provider_info('tararchive', self.clang)
        with tempfile.TemporaryDirectory(prefix='minyar-archive-header-') as name:
            foreign = Path(name).resolve()
            shutil.copy2(Path(original['include']) / 'archive_entry.h', foreign / 'archive_entry.h')
            for flags in (['-I' + str(foreign)], ['-include', str(foreign / 'archive_entry.h')]):
                with self.subTest(flags=flags), self.assertRaisesRegex(
                        ValueError, 'provider-owned header.*provider prefix'):
                    provider_info('tararchive', self.clang, flags)

    @unittest.skipIf(_windows(), 'literal POSIX path spelling regression')
    def test_literal_backslash_prefix_has_explicit_diagnostic(self):
        with tempfile.TemporaryDirectory(prefix='minyar-backslash-provider-') as name:
            old = self.copy_sha_prefix(name)
            prefix = old.with_name('provider back\\slash')
            old.rename(prefix)
            # Establish valid native compiler argv before checking the explicit
            # diagnostic for Clang dependency output path normalization.
            source, binary = prefix.parent / 'probe.c', prefix.parent / 'probe'
            source.write_text(_probe_source('sha256'))
            subprocess.run([self.clang, '-I' + str(prefix / 'include'), str(source),
                            str(prefix / 'lib/libcrypto.a'), '-o', str(binary)],
                           check=True, capture_output=True, timeout=30)
            subprocess.run([str(binary)], check=True, capture_output=True, timeout=30)
            with patch.dict(os.environ, {'MINYAR_SHA256_PREFIX': str(prefix)}):
                with self.assertRaisesRegex(ValueError, 'literal backslash.*unsupported'):
                    provider_info('sha256', self.clang)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'ELF PLT address regression')
    def test_non_pie_consumer_flags_identify_shared_image(self):
        info = provider_info('sha256', self.clang, ['-fno-pie'], ['-no-pie'])
        self.assertEqual(info['runtime_library'], info['library'])

    def test_effective_link_flags_are_used_and_fingerprinted(self):
        base = provider_info('sha256', self.clang)
        valid = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-Wl,--as-needed']
        changed = provider_info('sha256', self.clang, link_flags=valid)
        self.assertEqual(changed['link_flags'], valid)
        self.assertNotEqual(base['sha256'], changed['sha256'])
        native = ['-DMINYAR_PROVIDER_FLAG_TEST=1']
        changed = provider_info('sha256', self.clang, compile_flags=native)
        self.assertEqual(changed['compile_flags'], native)
        self.assertNotEqual(base['sha256'], changed['sha256'])
        with tempfile.TemporaryDirectory(prefix='minyar-link-flags-') as name:
            with self.assertRaisesRegex(ValueError, 'compile/link probe failed'):
                provider_info('sha256', self.clang,
                              link_flags=[str(Path(name) / 'nonexistent-input.a')])

    @unittest.skipIf(_windows(), 'tiny POSIX shared-library fixture')
    def test_effective_link_flags_cannot_interpose_secondary_api_image(self):
        # SHA256_Init still comes from the selected real provider. Only Final
        # resolves to the extra image; every provider API image must be checked.
        with tempfile.TemporaryDirectory(prefix='minyar-link-image-') as name:
            directory = Path(name).resolve()
            source = directory / 'shadow.c'
            source.write_text('int SHA256_Final(unsigned char *out, void *state) { return 0; }\n')
            if sys.platform == 'darwin':
                library = directory / 'libshadow.dylib'
                flags = ['-dynamiclib', '-Wl,-install_name,' + str(library)]
            else:
                library = directory / 'libshadow.so'
                flags = ['-shared', '-fPIC']
            subprocess.run([self.clang, *flags, str(source), '-o', str(library)],
                           check=True, capture_output=True, timeout=30)
            with self.assertRaisesRegex(ValueError, 'loaded provider image.*selected library'):
                provider_info('sha256', self.clang, link_flags=[str(library)])

    def test_disabled_sha_compatibility_api_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'compile/link probe failed'):
            provider_info('sha256', self.clang, ['-DOPENSSL_NO_DEPRECATED'])

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux static provider contract')
    def test_full_static_providers_preserve_archives_and_input_identity(self):
        flags = ['-O2', '-pthread', '-static', '-Wno-override-module']
        for kind in ('sha256', 'tararchive', 'lz4'):
            with self.subTest(kind=kind):
                info = provider_info(kind, self.clang, flags)
                again = provider_info(kind, self.clang, flags)
                self.assertTrue(info['library'].endswith('.a'))
                self.assertIsNone(info['runtime_library'])
                self.assertEqual(info['sha256'], again['sha256'])
                self.assertEqual(info['compile_flags'], flags)
                archives = [row for row in info['inputs'] if row['path'].endswith('.a')]
                self.assertTrue(any(Path(row['path']).name == 'libc.a' for row in archives))
                self.assertIn(info['library'], [row['path'] for row in archives])
                for row in info['inputs']:
                    self.assertEqual(row['sha256'], hashlib.sha256(Path(row['path']).read_bytes()).hexdigest())

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux static provider contract')
    def test_static_provider_rejects_shared_object_disguised_as_archive(self):
        with tempfile.TemporaryDirectory(prefix='minyar-static-provider-') as name:
            prefix = self.copy_sha_prefix(name, shared=True)
            library = prefix / 'lib/libcrypto.so'
            library.rename(prefix / 'lib/libcrypto.a')
            with patch.dict(os.environ, {'MINYAR_SHA256_PREFIX': str(prefix)}):
                with self.assertRaisesRegex(ValueError, 'real static archive'):
                    provider_info('sha256', self.clang, ['-static'])

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux static provider contract')
    def test_static_link_cannot_interpose_matching_version_api(self):
        with tempfile.TemporaryDirectory(prefix='minyar-static-interposition-') as name:
            work = Path(name)
            source, object_file = work / 'shadow.c', work / 'shadow.o'
            source.write_text('#include <archive.h>\nint archive_version_number(void) { return ARCHIVE_VERSION_NUMBER; }\n')
            subprocess.run([self.clang, '-O2', '-c', str(source), '-o', str(object_file)],
                           check=True, capture_output=True, timeout=30)
            selected = provider_info('tararchive', self.clang, ['-static'])
            probe, binary = work / 'probe.c', work / 'probe'
            probe.write_text(_probe_source('tararchive'))
            flags = [str(object_file), '-Wl,--allow-multiple-definition']
            subprocess.run([self.clang, '-static', str(probe), *flags,
                            *selected['libraries'], '-o', str(binary)],
                           check=True, capture_output=True, timeout=30)
            subprocess.run([str(binary)], check=True, capture_output=True, timeout=30)
            with self.assertRaisesRegex(ValueError, 'static provider API.*selected archive'):
                provider_info('tararchive', self.clang, ['-static'], flags)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux static provider contract')
    def test_static_provider_still_rejects_header_library_version_mismatch(self):
        source = _probe_source('lz4', identify=True, static=True)
        source = source.replace('LZ4_versionNumber() != LZ4_VERSION_NUMBER',
                                'LZ4_versionNumber() != LZ4_VERSION_NUMBER + 1')
        with patch('format_provider._probe_source', return_value=source):
            with self.assertRaisesRegex(ValueError, 'version/64-bit API probe failed'):
                provider_info('lz4', self.clang, ['-static'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clang', default=os.environ.get('MINYAR_TEST_CLANG', 'clang'))
    parser.add_argument('--kind', action='append', choices=('sha256', 'tararchive'))
    arguments, remaining = parser.parse_known_args()
    Providers.clang = arguments.clang
    if arguments.kind:
        Providers.kinds = tuple(arguments.kind)
    unittest.main(argv=[sys.argv[0], *remaining])
