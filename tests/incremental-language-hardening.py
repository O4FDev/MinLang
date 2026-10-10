#!/usr/bin/env python3
"""New language features preserve direct semantics through incremental builds."""
import os
from pathlib import Path
import subprocess
import unittest
from regressions import CLANG, COMPILER, RUNTIME, LINK_FLAGS, CompilerTestCase
from llvm_sanitizer import prepare_llvm_for_link
from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]
MODULE_COMPILER = Path(os.environ.get('MINYAR_TEST_MODULE_COMPILER', ROOT / 'build/minyarc-modules')).resolve()


class IncrementalLanguageHardening(CompilerTestCase):
    def setUp(self):
        super().setUp()
        self.entry = self.directory / 'main.min'
        self.prior = self.directory / 'prior.state'
        self.prior.write_text('')
        self.next = self.directory / 'next.state'
        self.stats = self.directory / 'stats.txt'
        self.llvm = self.directory / 'incremental.ll'

    def compare(self, expected, fallback=True, library=None, native=None):
        options = ['--library', str(library)] if library else []
        direct = self.directory / 'direct.ll'
        commands = (
            [COMPILER, self.entry, direct, *options],
            [MODULE_COMPILER, self.entry, self.llvm, '--module-state', self.prior, self.next, self.stats, *options],
        )
        for command in commands:
            result = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
        if fallback:
            stats = self.stats.read_text().split()
            self.assertEqual(stats[0], '0', 'fallback reused stale code')
            self.assertEqual(stats[6], 'false', 'fallback reused stale type tables')
            self.assertEqual(self.next.read_bytes(), b'', 'fallback published unsupported cache interfaces')
        elif self.next.read_bytes():
            self.prior.write_bytes(self.next.read_bytes())
        for llvm in (direct, self.llvm):
            prepare_llvm_for_link(llvm, LINK_FLAGS)
            for optimization in ('-O0', '-O2'):
                executable = llvm.with_suffix('.' + optimization[1:])
                command = [CLANG, optimization, *LINK_FLAGS, '-Wno-override-module', llvm, RUNTIME]
                if native:
                    command.append(native)
                command += ['-o', executable]
                link = subprocess.run(clang_command(list(map(str, command))), capture_output=True, text=True, timeout=30)
                self.assertEqual(link.returncode, 0, link.stderr)
                result = subprocess.run([executable], capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)

    def test_constants_and_import_edits_cannot_reuse_stale_code(self):
        library = self.directory / 'values.min'
        library.write_text('public function answer(): Integer { return 40 }\n')
        self.entry.write_text('use "./values.min" as values\nprint(values.answer() + 2)\n')
        self.compare('42\n', fallback=False)
        self.assertTrue(self.prior.read_bytes(), 'control did not publish a reusable cache')
        saved = self.prior.read_bytes()
        library.write_text('public constant ANSWER = 41\n')
        self.entry.write_text('use "./values.min" as values\nprint(values.ANSWER + 1)\n')
        self.compare('42\n')
        library.write_text('public constant ANSWER = 99\n')
        self.compare('100\n')
        other = self.directory / 'other.min'
        other.write_text('public constant ANSWER = 8\n')
        self.entry.write_text('use "./other.min" as values\nprint(values.ANSWER + 1)\n')
        self.compare('9\n')
        self.assertEqual(self.prior.read_bytes(), saved)
        library.write_text('public function answer(): Integer { return 6 }\n')
        self.entry.write_text('use "./values.min" as values\nprint(values.answer())\n')
        self.compare('6\n', fallback=False)

    def test_private_entry_constants(self):
        self.entry.write_text('constant VALUE = 2.5\nprint(VALUE)\n')
        self.compare('2.5\n')

    def test_newline_syntax_retains_normal_cache_reuse(self):
        self.entry.write_text('''function category(
value: Integer
): Integer {
if value < 0 { return 1 }
else if value == 0 { return 2 }
else { return 3 }
}
print(category(
0
))
''')
        self.compare('2\n', fallback=False)
        self.compare('2\n', fallback=False)
        self.assertEqual(self.stats.read_text().split()[0], '1')

    def test_native_linkage_survives_incremental_mode(self):
        library = self.directory / 'native.min'
        library.write_text('public function answer(): Integer { native "test" }\n')
        native = self.directory / 'native.c'
        native.write_text('#include <stdint.h>\nint64_t minyar_test_answer(void) { return 42; }\n')
        self.entry.write_text('use "./native.min" as native\nprint(native.answer())\n')
        self.compare('42\n', native=native)
        self.compare('42\n', native=native)

    def test_package_path_edits_use_the_selected_library(self):
        first = self.directory / 'library-one'
        second = self.directory / 'library-two'
        first.mkdir()
        second.mkdir()
        (first / 'numbers.min').write_text('public function answer(): Integer { return 42 }\n')
        (second / 'numbers.min').write_text('public function answer(): Integer { return 7 }\n')
        self.entry.write_text('use "numbers" as numbers\nprint(numbers.answer())\n')
        self.compare('42\n', library=first)
        self.compare('7\n', library=second)


if __name__ == '__main__':
    unittest.main()
