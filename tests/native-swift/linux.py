#!/usr/bin/env python3
"""Linux acceptance tests. Every Minyar fixture is original compiler input."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--compiler', required=True, type=Path)
ARGS, extra = parser.parse_known_args()
COMPILER = ARGS.compiler.absolute()
if sys.platform != 'linux' or not COMPILER.is_file():
    parser.error('run on Linux with a built native Minyar compiler')


def run(*command, ok=True):
    result = subprocess.run(list(map(str, command)), cwd=ROOT, text=True,
                            env=dict(os.environ, MINYAR_PYTHON=sys.executable),
                            capture_output=True, timeout=240)
    if (result.returncode == 0) != ok:
        raise AssertionError(f'{command}\n{result.stdout}\n{result.stderr}')
    return result


class LinuxNativeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='minyar-linux-check-')
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name)
        self.launcher = [ROOT / 'minyar', '--backend', 'native', '--compiler', COMPILER]

    def test_platform_selection_and_atomic_failure(self):
        project = self.path / 'app'
        project.mkdir()
        (project / 'app.min').write_text('@main record App { static function main() { print(platformName()) } }')
        (project / 'Platform.min').write_text('function platformName(): String { "fallback" }')
        override = project / 'Platform.linux.min'
        override.write_text('function platformName(): String { "linux" }')
        (project / 'Platform.mac.min').write_text('THIS MUST NOT REACH THE LINUX COMPILER')
        nested = project / 'another'
        nested.mkdir()
        (nested / 'app.min').write_text('THIS IS A DIFFERENT APP')
        output = self.path / 'program'
        for entry in [project, project / 'app.min']:
            run(*self.launcher, entry, '-o', output)
            self.assertEqual(run(output).stdout, 'linux\n')
            self.assertEqual(output.read_bytes()[:4], b'\x7fELF')
        previous = output.read_bytes()
        override.write_text('function platformName(): String { 42 }')
        failure = run(*self.launcher, project, '-o', output, ok=False)
        self.assertIn(str(override) + ':1:', failure.stderr)
        self.assertEqual(output.read_bytes(), previous)
        failure = run(*self.launcher, project, '--target-platform', 'mac', ok=False)
        self.assertIn('this host builds linux', failure.stderr)
        failure = run(*self.launcher, project, '--emit-swift', self.path / 'swift', ok=False)
        self.assertIn('does not generate Swift source', failure.stderr)
        self.assertFalse((self.path / 'swift').exists())

    def test_c_sdk_layout_and_signal_callback(self):
        source = self.path / 'main.min'
        source.write_text('''use "LinuxDesktop"
let total: Int32 = 0
constant action = g_simple_action_new("test", nil)!
constant callback: @convention(c) (OpaquePointer?, OpaquePointer?, UnsafeMutableRawPointer?) -> Void = { _, _, data in
    data!.assumingMemoryBound(to: Int32.self).pointee += 1
}
withUnsafeMutablePointer(to: &total) { counter in
    g_signal_connect_data(UnsafeMutableRawPointer(action), "activate", unsafeBitCast(callback, to: GCallback.self), counter, nil, GConnectFlags(rawValue: 0))
    g_action_activate(action, nil)
}
precondition(total == 1)
g_object_unref(UnsafeMutableRawPointer(action))
print("\\(gtk_get_major_version()) \\(MemoryLayout<GtkTextIter>.size) \\(MemoryLayout<GtkTextIter>.alignment)")
''')
        output = self.path / 'abi'
        run(*self.launcher, '--pkg-config', 'libadwaita-1', source, '-o', output)
        c = self.path / 'abi.c'
        c.write_text('#include <gtk/gtk.h>\n#include <stdio.h>\nint main(void) { printf("%u %zu %zu\\n", gtk_get_major_version(), sizeof(GtkTextIter), _Alignof(GtkTextIter)); }\n')
        import shlex
        flags = shlex.split(run('pkg-config', '--cflags', '--libs', 'libadwaita-1').stdout)
        control = self.path / 'c-control'
        run('clang', c, *flags, '-o', control)
        self.assertEqual(run(output).stdout, run(control).stdout)
        dependencies = run('ldd', output).stdout
        self.assertIn('libgtk-4.so', dependencies)
        self.assertNotIn('libminyar', dependencies)

    def test_shared_document_example(self):
        binary = self.path / 'editor'
        run(*self.launcher, '--release', '--pkg-config', 'libadwaita-1',
            ROOT / 'examples/native-editor', '-o', binary)
        self.assertEqual(run(binary, '--model-test').stdout, 'shared document model passed\n')

    def test_language_features_and_macros(self):
        for optimization in ['-Onone', '-O']:
            binary = self.path / optimization[1:]
            run(COMPILER, '-swift-version', '6', '-whole-module-optimization',
                '-parse-as-library', optimization, ROOT / 'tests/swiftui-features.min', '-o', binary)
            self.assertIn('actors passed', run(binary).stdout)

    def test_conditional_binding_mutability(self):
        binary = self.path / 'bindings'
        run(COMPILER, '-swift-version', '6', ROOT / 'tests/native-swift/conditional-bindings.min', '-o', binary)
        self.assertEqual(run(binary).stdout, '42\n42\n42\n')
        errors = run(COMPILER, '-swift-version', '6', '-typecheck',
                     ROOT / 'tests/native-swift/conditional-constant-failure.min', ok=False).stderr
        self.assertGreaterEqual(errors.count('error: cannot assign to value:'), 3)

    def test_native_library_c_client(self):
        source = self.path / 'Library.min'
        source.write_text('@_cdecl("minyar_answer") public function answer(value: Int32): Int32 { value * 2 }\n')
        products = self.path / 'library'
        run(*self.launcher, '--release', '--library', '--module-name', 'MinyarLinux', source, '-o', products)
        self.assertTrue((products / 'libMinyarLinux.so').is_file())
        interface = (products / 'MinyarLinux.swiftinterface').read_text()
        self.assertIn('func answer', interface)
        self.assertNotIn('function answer', interface)
        c = self.path / 'client.c'
        c.write_text('#include <stdint.h>\nextern int32_t minyar_answer(int32_t);\nint main(void) { return minyar_answer(21) == 42 ? 0 : 1; }\n')
        output = self.path / 'client'
        run('clang', c, '-L', products, '-lMinyarLinux', f'-Wl,-rpath,{products}', '-o', output)
        run(output)


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0], *extra])
