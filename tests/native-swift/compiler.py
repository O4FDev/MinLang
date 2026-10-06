#!/usr/bin/env python3
"""Acceptance tests for the pinned compiler, then its native Minyar frontend.

--baseline uses the existing source prototype to establish an upstream control.
Without that flag, original .min source is passed directly to the compiler.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
args_parser = argparse.ArgumentParser(description=__doc__)
args_parser.add_argument('--compiler', required=True, type=Path)
args_parser.add_argument('--baseline', action='store_true')
ARGS, test_args = args_parser.parse_known_args()
# Preserve argv[0]: Swift selects driver versus frontend mode by executable name.
COMPILER = ARGS.compiler.absolute()
if not COMPILER.is_file():
    args_parser.error(f'compiler does not exist: {COMPILER}')


def run(*command, ok=True, timeout=240):
    result = subprocess.run(list(map(str, command)), cwd=ROOT, text=True,
                            env=dict(os.environ, MINYAR_PYTHON=sys.executable),
                            capture_output=True, timeout=timeout)
    if (result.returncode == 0) != ok:
        raise AssertionError(f'{command}\n{result.stdout}\n{result.stderr}')
    return result


TARGET = json.loads(run('xcrun', 'swiftc', '-print-target-info').stdout)
SDK = run('xcrun', '--sdk', 'macosx', '--show-sdk-path').stdout.strip()
FLAGS = ['-swift-version', '6', '-resource-dir', TARGET['paths']['runtimeResourcePath'],
         '-sdk', SDK, '-target', TARGET['target']['triple'], '-whole-module-optimization']
if ARGS.baseline:
    spec = importlib.util.spec_from_file_location('native_swift_control', ROOT / 'scripts/native-swift.py')
    CONTROL = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = CONTROL
    spec.loader.exec_module(CONTROL)


class NativeCompilerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='minyar-compiler-check-')
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name)

    def source(self, text, name='main', logical_name=None):
        suffix = '.swift' if ARGS.baseline else '.min'
        path = self.path / (name + suffix)
        if ARGS.baseline:
            text = CONTROL.lower(text)
        if logical_name:
            text = f'#sourceLocation(file: {json.dumps(logical_name)}, line: 1)\n' + text
        path.write_text(text)
        return path

    def compile(self, *arguments, ok=True):
        return run(COMPILER, *FLAGS, *arguments, ok=ok)

    def test_native_features_and_observation(self):
        source = self.source((ROOT / 'tests/swiftui-features.min').read_text())
        for optimization in ['-Onone', '-O']:
            binary = self.path / optimization[1:]
            self.compile('-parse-as-library', optimization, source, '-o', binary)
            self.assertIn('actors passed', run(binary).stdout)

    def test_conditional_binding_mutability(self):
        good = self.source((ROOT / 'tests/native-swift/conditional-bindings.min').read_text())
        binary = self.path / 'bindings'
        self.compile(good, '-o', binary)
        self.assertEqual(run(binary).stdout, '42\n42\n42\n')
        bad = self.source((ROOT / 'tests/native-swift/conditional-constant-failure.min').read_text(), 'bad')
        errors = self.compile('-typecheck', bad, ok=False).stderr
        self.assertGreaterEqual(errors.count('error: cannot assign to value:'), 3)

    def test_multifile_and_original_diagnostics(self):
        main = self.source('print(twice(21))\n')
        helper = self.source('function twice(value: Int): Int { value * 2 }\n', 'helper')
        binary = self.path / 'program'
        self.compile(main, helper, '-o', binary)
        self.assertEqual(run(binary).stdout, '42\n')
        bad = self.source('// original source position\nconstant value: Int = "wrong"\n', 'bad')
        diagnostic = self.compile('-typecheck', bad, ok=False)
        self.assertIn(f'{bad}:2:', diagnostic.stderr)

    def test_swift_dialect_isolation(self):
        swift = self.path / 'immutable.swift'
        swift.write_text('let value = 1\nvalue = 2\n')
        diagnostic = self.compile('-typecheck', swift, ok=False)
        self.assertIn("'let' constant", diagnostic.stderr)
        mutable = self.source('let value = 1\nvalue = 2\nprint(value)\n')
        binary = self.path / 'mutable'
        self.compile(mutable, '-o', binary)
        self.assertEqual(run(binary).stdout, '2\n')

    def test_mixed_swift_and_minyar_sources(self):
        helper = self.source('''function twice(value: Int): Int {
    let total = value
    total += value
    return total
}
''', 'helper')
        main = self.path / 'main.swift'
        main.write_text('let input = 21\nprint(twice(input))\n')
        binary = self.path / 'mixed'
        self.compile(main, helper, '-o', binary)
        self.assertEqual(run(binary).stdout, '42\n')
        main.write_text(main.read_text() + 'input = 22\n')
        diagnostic = self.compile('-typecheck', main, helper, ok=False)
        self.assertIn("'let' constant", diagnostic.stderr)

    def test_swiftui_differential_ir_and_execution(self):
        logical = '/MinyarParity/Probe.swift'
        ours = self.source((ROOT / 'tests/swiftui-equivalent.min').read_text(), logical_name=logical)
        reference = self.path / 'reference.swift'
        reference.write_text(f'#sourceLocation(file: {json.dumps(logical)}, line: 1)\n' +
                             (ROOT / 'tests/swiftui-equivalent.swift').read_text())
        products = []
        for source, name in [(ours, 'minyar'), (reference, 'swift')]:
            ir = self.path / (name + '.ll')
            binary = self.path / name
            flags = ['-parse-as-library', '-O', '-module-name', 'Parity']
            self.compile(*flags, '-emit-ir', source, '-o', ir)
            self.compile(*flags, source, '-o', binary)
            products.append((ir.read_text(), run(binary).stdout))
        def normalize(ir):
            return '\n'.join(line for line in ir.splitlines()
                             if not line.startswith(("; ModuleID =", 'source_filename =')))
        self.assertEqual(normalize(products[0][0]), normalize(products[1][0]))
        self.assertEqual(products[0][1], products[1][1])
        self.assertTrue(products[0][1].startswith('10\n'))
        self.assertNotIn('minyar_', products[0][0])

    def test_swiftui_scene(self):
        source = self.source((ROOT / 'examples/swiftui/main.min').read_text())
        binary = self.path / 'native-scene'
        self.compile('-parse-as-library', '-O', source, '-o', binary)
        result = run(binary, '--smoke', timeout=30)
        self.assertIn('swiftui scene mounted', result.stdout)

    def test_native_library_and_swift_client(self):
        source = self.source((ROOT / 'examples/swiftui-library/widgets.min').read_text())
        library = self.path / 'libMinyarWidgets.dylib'
        interface = self.path / 'MinyarWidgets.swiftinterface'
        self.compile('-parse-as-library', '-O', '-module-name', 'MinyarWidgets',
                     '-enable-library-evolution', '-emit-library', '-emit-module',
                     '-emit-module-path', self.path / 'MinyarWidgets.swiftmodule',
                     '-emit-module-interface-path', interface,
                     '-Xlinker', '-install_name', '-Xlinker', '@rpath/libMinyarWidgets.dylib',
                     source, '-o', library)
        text_only = self.path / 'text-interface'
        text_only.mkdir()
        (text_only / interface.name).write_bytes(interface.read_bytes())
        for headers in [self.path, text_only]:
            binary = self.path / ('client-' + headers.name)
            run('xcrun', 'swiftc', '-swift-version', '6', '-parse-as-library', '-O',
                '-I', headers, '-L', self.path, '-lMinyarWidgets',
                '-module-cache-path', self.path / ('cache-' + headers.name),
                '-Xlinker', '-rpath', '-Xlinker', self.path,
                ROOT / 'tests/swiftui-library-client.swift', '-o', binary)
            self.assertIn('Swift imported native Minyar', run(binary).stdout)

    def test_macro_diagnostic_positions(self):
        source = self.source('use "Observation"\nconstant n = 1; @Observable record Bad { let value = 0 }\n')
        result = self.compile('-typecheck', source, ok=False)
        # Both frontends must report coordinates in the actual compiler input.
        line = source.read_text().splitlines()[1]
        column = line.index('@Observable') + 1
        self.assertIn(f'{source}:2:{column}:', result.stderr)
        self.assertIn(line, result.stderr)

    def test_swiftui_entry_macro(self):
        text = '''use "SwiftUI"
extension EnvironmentValues {
    @Entry let minyarProbe: Int = 42
}
@main record Probe {
    static function main() {
        let values = EnvironmentValues()
        precondition(values.minyarProbe == 42)
        values.minyarProbe = 7
        precondition(values.minyarProbe == 7)
        constant fixed = Binding.BINDING_FACTORY(42)
        precondition(fixed.wrappedValue == 42)
        print("SwiftUI Entry macro passed")
    }
}
'''
        # SDK member names must survive native keyword classification. The
        # older prototype needs explicit escaping for this API name.
        source = self.source(text.replace('BINDING_FACTORY', '`constant`' if ARGS.baseline else 'constant'))
        binary = self.path / 'entry'
        self.compile('-parse-as-library', '-O', source, '-o', binary)
        self.assertEqual(run(binary).stdout, 'SwiftUI Entry macro passed\n')

    def test_native_regex_literal(self):
        # The prototype requires extended delimiters. The native parser must
        # also support Swift's context-sensitive bare regex syntax.
        literal = '#/[0-9]+/#' if ARGS.baseline else '/[0-9]+/'
        source = self.source(f'''constant regex = {literal}
precondition("abc12".firstMatch(of: regex)?.output == "12")
print("native regex passed")
''')
        binary = self.path / 'regex'
        self.compile('-O', source, '-o', binary)
        self.assertEqual(run(binary).stdout, 'native regex passed\n')

    @unittest.skipIf(ARGS.baseline, 'requires the direct native launcher')
    def test_native_project_selection(self):
        project = self.path / 'project'
        feature = project / 'counter'
        feature.mkdir(parents=True)
        (project / 'app.min').write_text('@main record App { static function main() { print(platformName()) } }\n')
        (feature / 'Platform.min').write_text('function platformName(): String { "shared" }\n')
        override = feature / 'Platform.mac.min'
        override.write_text('function platformName(): String { "mac" }\n')
        (feature / 'Platform.windows.min').write_text('THIS MUST NEVER REACH THE MAC COMPILER\n')
        nested = project / 'tools/child'
        nested.mkdir(parents=True)
        (nested / 'app.min').write_text('@main record App { static function main() { print("child app") } }\n')
        app = self.path / 'Project.app'
        command = [ROOT / 'minyar', '--backend', 'native', '--compiler', COMPILER,
                   '--target-platform', 'mac', '--bundle-id', 'org.minyar.project-test', '-o', app]
        for entry in [project, project / 'app.min']:
            run(*command, entry)
            self.assertEqual(run(app / 'Contents/MacOS/application').stdout, 'mac\n')
        child_app = self.path / 'Child.app'
        run(*command, nested, '-o', child_app)
        self.assertEqual(run(child_app / 'Contents/MacOS/application').stdout, 'child app\n')
        previous = (app / 'Contents/MacOS/application').read_bytes()
        override.write_text('function platformName(): String { 42 }\n')
        failure = run(*command, project, ok=False)
        self.assertIn(str(override) + ':1:', failure.stderr)
        self.assertEqual((app / 'Contents/MacOS/application').read_bytes(), previous)
        unsupported = run(*command, project, '--target-platform', 'windows', ok=False)
        self.assertIn('this host builds mac', unsupported.stderr)

    @unittest.skipIf(ARGS.baseline, 'requires the direct native launcher')
    def test_native_app_launcher_and_failed_replacement(self):
        app = self.path / 'Native Minyar Test.app'
        command = [ROOT / 'minyar', '--backend', 'native', '--compiler', COMPILER,
                   '--release', '--app', '--bundle-id', 'org.minyar.native-acceptance',
                   '-o', app]
        run(*command, ROOT / 'examples/swiftui/main.min')
        info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
        self.assertEqual(info['CFBundleIdentifier'], 'org.minyar.native-acceptance')
        binary = app / 'Contents/MacOS' / info['CFBundleExecutable']
        run('codesign', '--verify', '--strict', app)
        self.assertIn('swiftui scene mounted', run(binary, '--smoke', timeout=30).stdout)
        previous = binary.read_bytes()
        bad = self.source('constant value: Int = "wrong"\n')
        failure = run(*command, bad, ok=False)
        self.assertIn(str(bad) + ':1:', failure.stderr)
        self.assertEqual(binary.read_bytes(), previous)
        rejected = run(*command, bad, '--emit-swift', self.path / 'lowered', ok=False)
        self.assertIn('does not generate Swift source', rejected.stderr)
        self.assertFalse((self.path / 'lowered').exists())


if __name__ == '__main__':
    print('Testing upstream control' if ARGS.baseline else 'Testing direct Minyar compiler input', flush=True)
    unittest.main(argv=[sys.argv[0], *test_args])
