import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import unittest

from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]
CLANG = os.environ.get('MINYAR_TEST_CLANG', 'clang')


class PackageNativeInputs(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native package with spaces ')
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.package = self.work / 'packages'
        self.package.mkdir()
        (self.package / 'linux.min').write_text(
            'public function number(): Integer { native "linux" }\n'
            'public function other(): Integer { native "linux" }\n')
        (self.work / 'child.min').write_text('use "linux" as linux\n'
            'public function answer(): Integer { return linux.number() + linux.other() }\n')
        self.source = self.work / 'main.min'
        self.source.write_text('use "./child.min" as child\nprint(child.answer())\n')
        self.native = self.work / 'native source $literal.c'
        self.header = self.work / 'value.h'
        self.header.write_text('#define VALUE 40\n')
        self.native.write_text('#include "value.h"\nlong long minyar_linux_number(void) { return VALUE; }\n')
        self.other = self.work / 'other.c'
        self.other.write_text('long long minyar_linux_other(void) { return 2; }\n')
        self.output = self.work / 'program'
        self.env = dict(os.environ, MINYAR_CLANG=CLANG, MAKEFLAGS='--jobs 8')
        self.env.pop('MINYAR_LINK_ARTIFACTS', None)

    def command(self, options, success=True):
        result = subprocess.run([str(ROOT / 'minyar'), '--library', str(self.package),
            *options, str(self.source), '-o', str(self.output)], cwd=self.work,
            env=self.env, capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def inputs(self):
        return ['--native-source', f'linux={self.native}', '--native-source', f'linux={self.other}']

    def execute(self, expected='42\n'):
        self.assertEqual(subprocess.check_output([str(self.output)], text=True), expected)

    def test_transitive_package_sources_follow_header_changes(self):
        self.command(self.inputs())
        self.execute()
        self.header.write_text('#define VALUE 50\n')
        self.command(self.inputs())
        self.execute('52\n')

    def test_object_and_archive_inputs(self):
        obj = self.work / 'native object.o'
        other = self.work / 'other.o'
        archive = self.work / 'native archive.a'
        for source, output in ((self.native, obj), (self.other, other)):
            subprocess.run(clang_command([CLANG, '-O2', '-c', str(source), '-o', str(output)]), check=True)
        subprocess.run([shutil.which('llvm-ar') or 'ar', 'rcs', str(archive), str(other)], check=True)
        self.command(['--native-object', f'linux={archive}', '--native-object', f'linux={obj}'])
        self.execute()

    def test_unbound_library_still_fails(self):
        result = self.command(['--native-source', f'unused={self.native}'], success=False)
        self.assertIn('unknown native library: linux', result.stderr)

    def test_unused_source_is_not_compiled(self):
        unused = self.work / 'unused.c'
        unused.write_text('invalid C must never compile\n')
        self.command([*self.inputs(), '--native-source', f'unused={unused}'])
        self.execute()

    def test_source_compile_failure_preserves_executable(self):
        self.command(self.inputs())
        self.native.write_text('invalid C\n')
        self.command(self.inputs(), success=False)
        self.execute()

    def test_unknown_and_missing_symbols_preserve_executable(self):
        self.command(self.inputs())
        self.command(['--native-source', f'linux={self.other}'], success=False)
        self.execute()
        self.command([], success=False)
        self.execute()

    def test_release_and_debug(self):
        for mode in ('--release', '--debug'):
            if platform.system() == 'Linux':
                if mode == '--release':
                    self.env['MINYAR_CLANG_FLAGS'] = '-O2 -Wno-override-module -Wl,--threads=1'
                else:
                    self.env.pop('MINYAR_CLANG_FLAGS', None)
            self.command([mode, *self.inputs()])
            self.execute()

    def test_native_flags_apply_to_package_source(self):
        self.env['MINYAR_NATIVE_FLAGS'] = '-O2 -DEXTRA=2'
        self.other.write_text('long long minyar_linux_other(void) { return EXTRA; }\n')
        self.command(self.inputs())
        self.execute()

    def test_builtin_provider_links_with_package_inputs(self):
        self.source.write_text('use "./child.min" as child\nuse "net" as net\n'
                              'use "sha256" as hash\nprint(child.answer())\n'
                              'print(net.ipVersion("127.0.0.1"))\nprint(hash.digest(Bytes()).length)\n')
        self.command(self.inputs())
        self.execute('42\n4\n32\n')

    def test_runtime_native_header_is_available(self):
        self.native.write_text('#include "minyar_native.h"\n'
            'long long minyar_linux_number(void) { return 40; }\n')
        self.command(self.inputs())
        self.execute()

    def test_native_input_cannot_be_output(self):
        original = self.native.read_bytes()
        self.output = self.native
        result = self.command(self.inputs(), success=False)
        self.assertIn('refusing to replace a native input', result.stderr)
        self.assertEqual(self.native.read_bytes(), original)

    def test_check_rejects_native_output_options(self):
        result = subprocess.run([str(ROOT / 'minyar'), '--check', *self.inputs(), str(self.source)],
            cwd=self.work, env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_input_validation(self):
        for options in (['--native-source', str(self.native)],
                        ['--native-source', f'bad-name={self.native}'],
                        ['--native-object', f'linux={self.work / "missing.o"}'],
                        ['--native-object', f'linux={self.native}']):
            self.command(options, success=False)


if __name__ == '__main__':
    unittest.main()
