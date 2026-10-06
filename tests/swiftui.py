#!/usr/bin/env python3
"""Native frontend, differential code generation, and real SwiftUI scene tests."""
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_swift', ROOT / 'scripts/native-swift.py')
frontend = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = frontend
spec.loader.exec_module(frontend)


def run(*args, ok=True, timeout=180):
    result = subprocess.run([str(arg) for arg in args], cwd=ROOT,
                            env=dict(os.environ, MINYAR_PYTHON=sys.executable),
                            text=True, capture_output=True, timeout=timeout)
    if ok and result.returncode:
        raise AssertionError(f'{args}\n{result.stdout}\n{result.stderr}')
    if not ok and result.returncode == 0:
        raise AssertionError(f'expected failure: {args}')
    return result


class FrontendTests(unittest.TestCase):
    def test_syntax_and_generic_closure_parameters(self):
        source = 'function map<T, U>(xs: [T], f: (T, T) -> U): [U] { let n = 0; constant x = n }'
        self.assertEqual(frontend.lower(source),
                         'func map<T, U>(_ xs: [T], _ f: (T, T) -> U)-> [U] { var n = 0; let x = n }')

    def test_explicit_labels_and_native_declarations(self):
        self.assertEqual(frontend.lower('function f(_ x: Int, to y: Int) async throws: Int { x + y }'),
                         'func f(_ x: Int, to y: Int) async throws-> Int { x + y }')
        self.assertEqual(frontend.lower('record Box<T>: P { constant x: T }'),
                         'struct Box<T>: P { let x: T }')

    def test_literals_comments_interpolation(self):
        literals = [
            '"function let record constant"',
            '#"function \\#(String("let"))"#',
            '"outer \\(String("inner \\(2)"))!"',
            '"""\nlet record \\(2)\n"""',
            '/* let /* function */ record */',
            '// function\n',
            '`let`',
            '#/let|constant|record/#',
        ]
        for literal in literals:
            self.assertEqual(frontend.lower(literal), literal)
        self.assertEqual(frontend.lower('"\\({ constant x = 2; return x }())"'),
                         '"\\({ let x = 2; return x }())"')

    def test_invalid_input_and_imports(self):
        for source in ['"unfinished', '/* unfinished', '`unfinished',
                       'use "./local.min"', 'use "SwiftUI" as ui', 'function missing',
                       'constant r = /let/']:
            with self.assertRaises(ValueError, msg=source):
                frontend.lower(source)
        self.assertEqual(frontend.lower('use "SwiftUI"\nuse "Observation"'),
                         'import SwiftUI\nimport Observation')


class LibraryInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='minyar-library-install-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.source = self.path / 'products'
        self.source.mkdir()
        (self.source / 'library').write_text('old binary')
        (self.source / 'module').write_text('old metadata')
        self.output = self.path / 'installed'
        frontend.install_library(self.source, self.output)

    def test_replacement_and_unrelated_directory(self):
        (self.source / 'library').write_text('new binary')
        (self.source / 'module').write_text('new metadata')
        frontend.install_library(self.source, self.output)
        self.assertEqual((self.output / 'module').read_text(), 'new metadata')
        unrelated = self.path / 'unrelated'
        unrelated.mkdir()
        (unrelated / 'precious').write_text('retain')
        with self.assertRaises(ValueError):
            frontend.install_library(self.source, unrelated)
        self.assertEqual((unrelated / 'precious').read_text(), 'retain')
        link = self.path / 'link'
        link.symlink_to(self.output)
        with self.assertRaises(ValueError):
            frontend.install_library(self.source, link)

    def test_lock_is_not_removed_by_losing_writer(self):
        lock = self.path / 'installed.minyar-lock'
        lock.write_text('active owner')
        with self.assertRaises(FileExistsError):
            frontend.install_library(self.source, self.output)
        self.assertEqual(lock.read_text(), 'active owner')

    def test_rollback_retains_matching_binary_and_metadata(self):
        replace = os.replace
        def fail_install(src, dst):
            if Path(src).name == 'next':
                raise OSError('injected installation failure')
            return replace(src, dst)
        with mock.patch.object(frontend.os, 'replace', side_effect=fail_install):
            with self.assertRaisesRegex(OSError, 'injected'):
                frontend.install_library(self.source, self.output)
        self.assertEqual((self.output / 'library').read_text(), 'old binary')
        self.assertEqual((self.output / 'module').read_text(), 'old metadata')
        self.assertFalse(list(self.path.glob('.minyar-library-*')))
        self.assertFalse((self.path / 'installed.minyar-lock').exists())

    def test_failed_rollback_preserves_backup(self):
        replace = os.replace
        def fail_install_and_rollback(src, dst):
            if Path(src).name in ('next', 'previous'):
                raise OSError('injected rename failure')
            return replace(src, dst)
        with mock.patch.object(frontend.os, 'replace', side_effect=fail_install_and_rollback):
            with self.assertRaisesRegex(OSError, 'previous library preserved'):
                frontend.install_library(self.source, self.output)
        backups = list(self.path.glob('.minyar-library-*/previous'))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / 'library').read_text(), 'old binary')
        self.assertEqual((backups[0] / 'module').read_text(), 'old metadata')


@unittest.skipUnless(sys.platform == 'darwin', 'requires macOS/Xcode and a GUI session')
class NativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='minyar-swiftui-tests-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)

    def native(self, *args, **kwargs):
        return run(ROOT / 'minyar', '--backend', 'swift', *args, **kwargs)

    def test_exact_optimized_ir_equivalence(self):
        ours, reference = self.path / 'minyar.ll', self.path / 'swift.ll'
        binary = self.path / 'program'
        sil = self.path / 'program.sil'
        self.native('--release', '--module-name', 'ParityProbe', '--emit-ir', ours,
                    '--emit-sil', sil, ROOT / 'tests/swiftui-equivalent.min', '-o', binary)
        flags = ['xcrun', 'swiftc', '-swift-version', '6', '-module-name', 'ParityProbe',
                 '-whole-module-optimization', '-O', '-parse-as-library']
        source = self.path / 'reference.swift'
        # Runtime diagnostics contain #fileID. Give both independent sources
        # the same logical filename so that data, too, can match exactly.
        logical = json.dumps(str(ROOT / 'tests/swiftui-equivalent.min'))
        source.write_text(f'#sourceLocation(file: {logical}, line: 1)\n' +
                          (ROOT / 'tests/swiftui-equivalent.swift').read_text())
        run(*flags, '-emit-ir', source, '-o', reference)
        # Only the two output filenames differ. Compare every instruction,
        # metadata record, calling convention and declaration that remains.
        normalize = lambda p: '\n'.join(line for line in p.read_text().splitlines()
                                       if not line.startswith(('; ModuleID = ', 'source_filename = ')))
        self.assertEqual(normalize(ours), normalize(reference))
        run(*flags, source, '-o', self.path / 'reference')
        self.assertEqual(run(binary).stdout, run(self.path / 'reference').stdout)
        self.assertTrue(run(binary).stdout.startswith('10\n'))
        ir = ours.read_text()
        self.assertIn('CounterViewV4body', ir)
        self.assertIn('NSHostingView', ir)
        self.assertNotIn('minyar_', ir)
        self.assertNotIn('AnyView', sil.read_text())
        self.assertIn('CounterView', sil.read_text())

    def test_native_ownership_generics_errors_concurrency(self):
        for release in (False, True):
            binary = self.path / ('release' if release else 'debug')
            self.native(*(['--release'] if release else []),
                        ROOT / 'tests/swiftui-features.min', '-o', binary)
            self.assertEqual(run(binary).stdout,
                             'native generics, typed errors, ARC, closures and actors passed\n')

    def test_native_library_imports_binary_and_resilient_interface(self):
        library = self.path / 'MinyarWidgets'
        self.native('--library', '--release', '--module-name', 'MinyarWidgets',
                    ROOT / 'examples/swiftui-library/widgets.min', '-o', library)
        interface = library / 'MinyarWidgets.swiftinterface'
        self.assertRegex(interface.read_text(), r'some SwiftUI(?:Core)?\.View')
        self.assertIn('public struct NativeBadge', interface.read_text())
        dylib = library / 'libMinyarWidgets.dylib'
        self.assertIn('@rpath/libMinyarWidgets.dylib', run('otool', '-D', dylib).stdout)
        self.assertNotIn('_minyar_', run('nm', dylib).stdout)
        # A separate Swift compilation imports and runs our module. Also test
        # rebuilding the module from its public interface without its binary
        # .swiftmodule or a populated module cache.
        interface_only = self.path / 'interfaces'
        interface_only.mkdir()
        shutil.copyfile(interface, interface_only / interface.name)
        for headers in (library, interface_only):
            client = self.path / ('client-' + headers.name)
            run('xcrun', 'swiftc', '-swift-version', '6', '-parse-as-library', '-O',
                '-module-cache-path', self.path / ('cache-' + headers.name),
                '-I', headers, '-L', library, '-lMinyarWidgets',
                '-Xlinker', '-rpath', '-Xlinker', library,
                ROOT / 'tests/swiftui-library-client.swift', '-o', client)
            self.assertEqual(run(client).stdout,
                             'Swift imported native Minyar generics, conformances, views and bindings\n')
        # A second native Minyar compilation imports the same native module.
        source = self.path / 'client.min'
        source.write_text('use "MinyarWidgets"\nprint(nativeSum([1, 2, 3]))\n')
        self.native('--swift-flag=-I', f'--swift-flag={library}',
                    '--swift-flag=-L', f'--swift-flag={library}',
                    '--swift-flag=-lMinyarWidgets', '--swift-flag=-Xlinker',
                    '--swift-flag=-rpath', '--swift-flag=-Xlinker', f'--swift-flag={library}',
                    source, '-o', self.path / 'minyar-client')
        self.assertEqual(run(self.path / 'minyar-client').stdout, '6\n')

        # Rejected configurations must not damage the installed library.
        before = dylib.read_bytes()
        self.native('--library', '--app', source, '-o', library, ok=False)
        self.native('--library', ROOT / 'examples/swiftui/main.min', '-o', library, ok=False)
        self.native('--library', '--emit-sil', library / 'inside.sil', source, '-o', library, ok=False)
        source.write_text('not valid Minyar\n')
        self.native('--library', source, '-o', library, ok=False)
        self.assertEqual(dylib.read_bytes(), before)

    def test_multiple_files_diagnostics_and_failed_build_preservation(self):
        main, helper, binary = [self.path / s for s in ['main.min', 'helper.min', 'program']]
        main.write_text('print(twice(21))\n')
        helper.write_text('function twice(value: Int): Int { value * 2 }\n')
        self.native(main, helper, '-o', binary)
        self.assertEqual(run(binary).stdout, '42\n')
        previous = binary.read_bytes()
        main.write_text('// diagnostic should refer to this file\nlet x: Int = "wrong"\n')
        error = self.native(main, '-o', binary, ok=False)
        self.assertIn(f'{main}:2:', error.stderr)
        self.assertEqual(binary.read_bytes(), previous)
        self.native('--memory-profile', 'lazy', main, '-o', binary, ok=False)
        self.native(main, '-o', main, ok=False)

    def test_native_app_scene_and_bundle(self):
        app = self.path / 'Minyar Native é.app'
        lowered = self.path / 'lowered'
        self.native('--release', '--app', '--bundle-id', 'org.minyar.swiftui-test',
                    '--emit-swift', lowered, ROOT / 'examples/swiftui/main.min', '-o', app)
        info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
        self.assertEqual(info['CFBundleIdentifier'], 'org.minyar.swiftui-test')
        run('codesign', '--verify', '--strict', app)
        binary = app / 'Contents/MacOS/application'
        self.assertEqual(run(binary, '--smoke', timeout=30).stdout,
                         'swiftui scene mounted; native state updated\n')
        deps = run('otool', '-L', binary).stdout
        self.assertIn('SwiftUI.framework', deps)
        self.assertIn('libswiftCore', deps)
        symbols = run('nm', '-u', binary).stdout
        self.assertNotIn('_minyar_', symbols)
        self.assertNotIn('AnyView(', (lowered / 'main.swift').read_text())


if __name__ == '__main__':
    unittest.main(verbosity=2)
