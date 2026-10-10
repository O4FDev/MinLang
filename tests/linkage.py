#!/usr/bin/env python3
"""Language names cannot interpose the runtime, libc, or native package ABI."""
import os
from pathlib import Path
import re
import subprocess
import unittest

from clang_helpers import clang_command
from llvm_sanitizer import prepare_llvm_for_link
from regressions import CLANG, COMPILER, LINK_FLAGS, ROOT, RUNTIME, CompilerTestCase

STAGE0 = Path(os.environ.get('MINYAR_TEST_STAGE0', ROOT / 'build/stage0'))
MODULE_COMPILER = Path(os.environ.get('MINYAR_TEST_MODULE_COMPILER', ROOT / 'build/minyarc-modules'))
NAMES = ('malloc', 'free', 'calloc', 'realloc', 'printf', 'fprintf', 'memcpy',
         'strlen', 'stdout', 'stderr', 'environ', 'minyar_stack_enter',
         'minyar_rc_enter', 'minyar_fail_integer_overflow', 'minyar_fail_integer_division')


def declarations(public=False):
    return ''.join(('public ' if public else '') +
                   f'function {name}(value: Integer): Integer {{ return value + {index + 1} }}\n'
                   for index, name in enumerate(NAMES))


def calls(namespace=''):
    return ''.join(f'print({namespace}{name}({index * 7}))\n' for index, name in enumerate(NAMES))


EXPECTED = ''.join(f'{index * 8 + 1}\n' for index in range(len(NAMES)))


def fields(text):
    result = []
    position = 0
    while position < len(text):
        newline = text.index('\n', position)
        size = int(text[position:newline])
        position = newline + 1
        assert 0 <= size <= len(text) - position
        result.append(text[position:position + size])
        position += size
    return result


def pack(values):
    return ''.join(f'{len(value)}\n{value}' for value in values)


def module_symbols(filename, names):
    # Fixtures live beside the entry, so their stable identity is the reversed
    # root-relative local path used by the module ABI.
    identity = ('local:' + filename)[::-1]
    return {f'.minyar.fn.minyar.module|{name}|{identity}' for name in names}


class LanguageLinkage(CompilerTestCase):
    def assert_namespace(self, llvm, expected_symbols=None):
        # Check the actual emitted ABI before linking/running: the old compiler
        # can otherwise replace malloc/free and corrupt its own runtime process.
        definitions = re.findall(r'^define ([^\n]*?)@("[^"\n]+"|[^\s(]+)\(', llvm.read_text(), re.M)
        self.assertTrue(definitions)
        self.assertEqual(len(definitions), len({name for _, name in definitions}))
        if expected_symbols is None:
            expected_symbols = {'.minyar.fn.' + name for name in NAMES}
        user_names = []
        entries = 0
        for attributes, quoted_name in definitions:
            name = quoted_name.strip('"')
            if attributes.startswith('internal '):
                self.assertTrue(name.startswith('.minyar.'), name)
            else:
                self.assertTrue(name == 'main' or name.startswith('.minyar.fn.'), name)
                if name != 'main':
                    self.assertEqual(name.count('.minyar.fn.'), 1, name)
                    user_names.append(name)
                else:
                    entries += 1
        self.assertEqual(entries, 1, 'exactly one C entry main must be emitted')
        self.assertEqual(set(user_names), set(expected_symbols))
        self.assertEqual(len(user_names), len(expected_symbols))

    def execute_ir(self, llvm, expected=EXPECTED, expected_symbols=None, native_sources=()):
        self.assert_namespace(llvm, expected_symbols)
        prepare_llvm_for_link(llvm, LINK_FLAGS)
        for optimization in ('-O0', '-O2'):
            executable = self.directory / ('linked-' + optimization[1:])
            link = subprocess.run(clang_command([CLANG, optimization, *LINK_FLAGS,
                                  '-Wno-override-module', llvm, RUNTIME, *native_sources,
                                  '-o', executable]),
                                  capture_output=True, text=True, timeout=60)
            self.assertEqual(link.returncode, 0, link.stderr)
            result = subprocess.run([executable], capture_output=True, text=True, timeout=30)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected, ''))

    def assert_native_callee(self, llvm):
        text = llvm.read_text()
        declarations = re.findall(r'^declare i64 @minyar_probe_sample\(i64\)\s*$', text, re.M)
        self.assertEqual(len(declarations), 1)
        self.assertEqual(text.count('call i64 @minyar_probe_sample(i64 %argument.0)'), 1)

    def native_stub(self):
        native = self.directory / 'probe.c'
        native.write_text('long long minyar_probe_sample(long long value) { return value + 100; }\n')
        return native

    def test_ordinary_names_do_not_interpose_c_dependencies(self):
        result, llvm = self.compile(declarations() + calls())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.execute_ir(llvm)

    def test_bootstrap_uses_the_same_language_namespace(self):
        source = self.directory / 'bootstrap.min'
        source.write_text(declarations() + 'function main() {\n' + calls() + '}\n')
        llvm = source.with_suffix('.ll')
        result = subprocess.run([STAGE0, source, '-o', llvm], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.execute_ir(llvm)

    def test_local_modules_and_cached_fragments_keep_names_separate(self):
        library = self.directory / 'lib.min'
        library.write_text(declarations(public=True))
        entry = self.directory / 'main.min'
        entry.write_text('use "./lib.min" as lib\n' + calls('lib.'))
        llvm = self.directory / 'program.ll'
        direct = subprocess.run([COMPILER, entry, llvm], capture_output=True, text=True, timeout=30)
        self.assertEqual(direct.returncode, 0, direct.stderr)
        self.execute_ir(llvm, expected_symbols={f'.minyar.fn.minyar_module_1_{name}' for name in NAMES})
        prior = self.directory / 'prior.state'
        prior.write_text('')
        following = self.directory / 'following.state'
        stats = self.directory / 'stats'
        for phase in ('cold', 'warm', 'changed'):
            with self.subTest(phase=phase):
                if phase == 'changed':
                    # A semantically neutral dependency edit forces a mixed
                    # reused/recompiled graph while preserving the value oracle.
                    library.write_text('// changed dependency\n' + declarations(public=True))
                result = subprocess.run([MODULE_COMPILER, entry, llvm, '--module-state', prior,
                                         following, stats], capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                counts = {'cold': ['0', '2'], 'warm': ['2', '0'], 'changed': ['1', '1']}
                self.assertEqual(stats.read_text().split()[:2], counts[phase])
                self.execute_ir(llvm, expected_symbols=module_symbols('lib.min', NAMES))
                # An empty publication means unchanged state, not an empty cache.
                if following.stat().st_size:
                    prior.write_bytes(following.read_bytes())

        # An otherwise intact cache from the previous linkage ABI must rebuild.
        # Keeping every payload valid makes accidental reuse observable; corrupt
        # data could fall back for an unrelated reason and hide a version-check bug.
        legacy = fields(following.read_text())
        self.assertEqual(legacy[0], 'minyar-module-interface-v5')
        legacy[0] = 'minyar-module-interface-v4'
        prior.write_text(pack(legacy))
        result = subprocess.run([MODULE_COMPILER, entry, llvm, '--module-state', prior,
                                 following, stats], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(stats.read_text().split()[:2], ['0', '2'], 'old ABI cache was reused')
        self.execute_ir(llvm, expected_symbols=module_symbols('lib.min', NAMES))

    def test_native_callee_keeps_its_c_symbol(self):
        result, llvm = self.compile('''function sample(value: Integer): Integer { native "probe" }
function minyar_probe_sample(value: Integer): Integer { return value + 200 }
print(sample(7))
print(minyar_probe_sample(7))
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_native_callee(llvm)
        self.execute_ir(llvm, '107\n207\n',
                        {'.minyar.fn.sample', '.minyar.fn.minyar_probe_sample'},
                        (self.native_stub(),))

    def test_native_module_fallback_keeps_c_and_language_symbols_separate(self):
        library = self.directory / 'probe.min'
        library_source = 'public function sample(value: Integer): Integer { native "probe" }\n'
        library.write_text(library_source)
        entry = self.directory / 'main.min'
        entry.write_text('''use "./probe.min" as probe
function minyar_probe_sample(value: Integer): Integer { return value + 200 }
print(probe.sample(7))
print(minyar_probe_sample(7))
''')
        llvm = self.directory / 'program.ll'
        symbols = {'.minyar.fn.minyar_module_0_minyar_probe_sample',
                   '.minyar.fn.minyar_module_1_sample'}
        native = self.native_stub()
        direct = subprocess.run([COMPILER, entry, llvm], capture_output=True, text=True, timeout=30)
        self.assertEqual(direct.returncode, 0, direct.stderr)
        self.assert_native_callee(llvm)
        self.execute_ir(llvm, '107\n207\n', symbols, (native,))
        prior = self.directory / 'prior.state'
        prior.write_text('')
        following = self.directory / 'following.state'
        stats = self.directory / 'stats'
        for phase in ('cold', 'warm', 'changed'):
            with self.subTest(phase=phase):
                if phase == 'changed':
                    library.write_text('// changed native dependency\n' + library_source)
                result = subprocess.run([MODULE_COMPILER, entry, llvm, '--module-state', prior,
                                         following, stats], capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                # Native declarations are not cache interfaces yet: the whole
                # graph must compile again and publish no incremental state.
                self.assertEqual(stats.read_text().split(), ['0', '2', '2', '0', '0', '0', 'false'])
                self.assertEqual(following.read_text(), '')
                self.assert_native_callee(llvm)
                self.execute_ir(llvm, '107\n207\n', symbols, (native,))
                # An empty publication means unchanged state, not an empty cache.
                if following.stat().st_size:
                    prior.write_bytes(following.read_bytes())

    def test_same_name_in_two_modules_and_entry_stays_distinct(self):
        left = self.directory / 'left.min'
        right = self.directory / 'right.min'
        left_source = 'public function malloc(value: Integer): Integer { return value + 1 }\n'
        left.write_text(left_source)
        right.write_text('public function malloc(value: Integer): Integer { return value + 2 }\n')
        entry = self.directory / 'main.min'
        entry.write_text('''use "./left.min" as left
use "./right.min" as right
function malloc(value: Integer): Integer { return value + 3 }
print(left.malloc(10))
print(right.malloc(10))
print(malloc(10))
''')
        llvm = self.directory / 'program.ll'
        direct = subprocess.run([COMPILER, entry, llvm], capture_output=True, text=True, timeout=30)
        self.assertEqual(direct.returncode, 0, direct.stderr)
        self.execute_ir(llvm, '11\n12\n13\n',
                        {f'.minyar.fn.minyar_module_{module}_malloc' for module in range(3)})
        symbols = set().union(*(module_symbols(filename, ('malloc',))
                                for filename in ('main.min', 'left.min', 'right.min')))
        prior = self.directory / 'prior.state'
        prior.write_text('')
        following = self.directory / 'following.state'
        stats = self.directory / 'stats'
        for phase in ('cold', 'warm', 'changed'):
            with self.subTest(phase=phase):
                expected = '11\n12\n13\n'
                if phase == 'changed':
                    left.write_text(left_source.replace('value + 1', 'value + 4'))
                    expected = '14\n12\n13\n'
                result = subprocess.run([MODULE_COMPILER, entry, llvm, '--module-state', prior,
                                         following, stats], capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                counts = {'cold': ['0', '3'], 'warm': ['3', '0'], 'changed': ['2', '1']}
                self.assertEqual(stats.read_text().split()[:2], counts[phase])
                self.execute_ir(llvm, expected, symbols)
                # An empty publication means unchanged state, not an empty cache.
                if following.stat().st_size:
                    prior.write_bytes(following.read_bytes())


if __name__ == '__main__':
    unittest.main()
