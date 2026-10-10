#!/usr/bin/env python3
"""Numeric source positions, lazy diagnostics, and cached module origin parity."""
import os
from pathlib import Path
import re
import subprocess
import unittest
from clang_helpers import clang_command
from llvm_sanitizer import prepare_llvm_for_link
from regressions import CompilerTestCase, COMPILER, CLANG, RUNTIME, ROOT, LINK_FLAGS

CORE = Path(os.environ.get('MINYAR_TEST_SOURCE', ROOT / 'compiler/compiler.min'))
MODULE_COMPILER = Path(os.environ.get('MINYAR_TEST_MODULE_COMPILER', ROOT / 'build/minyarc-modules'))


class SourceMaps(CompilerTestCase):
    def test_default_source_uses_two_coordinates_per_token_at_large_sizes(self):
        core = CORE.read_text().split('\nfunction main(')[0]
        self.executes(core + '''
function main() {
    let pieces: List<Text> = []
    let count = 0
    while count < 50000 { pieces.add("value "); count = count + 1 }
    let kinds: List<Integer> = []
    let texts: List<Text> = []
    let locations = newSourceMap()
    tokenize(joinText(pieces), kinds, texts, locations)
    print(kinds.length)
    print(locations.coordinates.length)
}
''', '50001\n100002\n')

    def test_path_indices_are_sparse_and_preserve_gaps_resets_and_named_eof(self):
        core = CORE.read_text().split('\nfunction main(')[0]
        self.executes(core + '''
function main() {
    let kinds: List<Integer> = []
    let texts: List<Text> = []
    let source = newSourceMap()
    let position = 0
    while position < 50000 {
        addToken(kinds, texts, source.coordinates, 1, "value", 4294967297, 9223372036854775807)
        position = position + 1
    }
    print(source.pathIndices.length)
    print(tokenLocation(source, 49999))
    let path = sourcePath(source, "folder/é🙂.min")
    setTokenPath(source, 3, path)
    print(source.pathIndices.length)
    print(tokenLocation(source, 2))
    print(tokenLocation(source, 3))
    print(tokenLocation(source, 49999))
    setTokenPath(source, 3, 0)
    print(tokenLocation(source, 3))
    setTokenOrigin(source, 49999, "8, column 13")
    setTokenPath(source, 49999, path)
    print(tokenLocation(source, 49999))
    addEndToken(kinds, texts, source, "end of interfaces")
    print(tokenLocation(source, 50000))
}
''', '0\n4294967297, column 9223372036854775807\n4\n'
             '4294967297, column 9223372036854775807\n'
             'folder/é🙂.min:4294967297, column 9223372036854775807\n'
             '4294967297, column 9223372036854775807\n'
             '4294967297, column 9223372036854775807\n'
             'folder/é🙂.min:8, column 13\nend of interfaces\n')

    def test_full_integer_positions_shared_paths_and_sparse_legacy_origins(self):
        core = CORE.read_text().split('\nfunction main(')[0]
        self.executes(core + '''
function main() {
    let kinds: List<Integer> = []
    let texts: List<Text> = []
    let source = newSourceMap()
    print(source.paths.length)
    print(sourcePath(source, "") == 0)
    print(sourcePath(source, "") == 0)
    print(source.paths.length)
    addToken(kinds, texts, source.coordinates, 1, "first", 4294967297, 9223372036854775807)
    addToken(kinds, texts, source.coordinates, 1, "second", 2, 7)
    addToken(kinds, texts, source.coordinates, 1, "third", 3, 11)
    print(tokenLocation(source, 0))
    print(source.origins.length)
    setTokenOrigin(source, 2, "8, column 13")
    print(tokenLocation(source, 1))
    print(tokenLocation(source, 2))
    print(source.origins.length)
    print(source.origins[0] == "" && source.origins[1] == "")
    let copiedKinds: List<Integer> = []
    let copiedTexts: List<Text> = []
    let copied = newSourceMap()
    let path = sourcePath(copied, "folder/é🙂.min")
    print(path == sourcePath(copied, "folder/é🙂.min"))
    copyModuleToken(copiedKinds, copiedTexts, copied, 1, "second", source, 1, path)
    copyModuleToken(copiedKinds, copiedTexts, copied, 1, "third", source, 2, path)
    print(path == 1)
    print(sourcePath(copied, "") == 0)
    print(copied.paths.length)
    print(tokenLocation(copied, 0))
    print(tokenLocation(copied, 1))
    addEndToken(copiedKinds, copiedTexts, copied, "end of interfaces")
    print(tokenLocation(copied, 2))
}
''', '1\ntrue\ntrue\n1\n4294967297, column 9223372036854775807\n0\n2, column 7\n8, column 13\n3\ntrue\ntrue\ntrue\ntrue\n2\nfolder/é🙂.min:2, column 7\nfolder/é🙂.min:8, column 13\nend of interfaces\n')

    def test_successful_parser_does_not_format_per_expression_locations(self):
        llvm = self.directory / 'compiler.ll'
        result = subprocess.run([COMPILER, CORE, llvm], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        ir = llvm.read_text()
        ir, count = re.subn(r'(?m)^(define ptr )@\.minyar\.fn\.sourceLocation\(', r'\1@original_source_location(', ir)
        self.assertEqual(count, 1)
        ir = re.sub(r'(?m)^(  .*call ptr )@\.minyar\.fn\.sourceLocation\(', r'\1@probe_source_location(', ir)
        ir += '\ndeclare ptr @probe_source_location(i64, i64)\n'
        llvm.write_text(ir)
        prepare_llvm_for_link(llvm, LINK_FLAGS)
        probe = self.directory / 'probe.c'
        probe.write_text('''#include <stdio.h>
static unsigned long long formats;
extern void *original_source_location(long long, long long);
void *probe_source_location(long long line, long long column) {
    ++formats; return original_source_location(line, column);
}
__attribute__((destructor)) static void report(void) {
    fprintf(stderr, "LOCATION_FORMATS=%llu\\n", formats);
}
''')
        executable = self.directory / 'compiler-probe'
        result = subprocess.run(clang_command([CLANG, '-O2', *LINK_FLAGS, '-Wno-override-module', llvm, probe, RUNTIME, '-o', executable]), capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        source = self.directory / 'expressions.min'
        source.write_text('function identity(value: Integer): Integer { return value }\n' + '\n'.join(f'print(identity({i}) + {i})' for i in range(1000)) + '\n')
        result = subprocess.run([executable, source, self.directory / 'expressions.ll'], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        formats = re.search(r'LOCATION_FORMATS=(\d+)', result.stderr)
        self.assertIsNotNone(formats, result.stderr)
        self.assertLessEqual(int(formats[1]), 4, 'successful expressions eagerly formatted source locations')

    def test_imported_unicode_diagnostic_retains_exact_original_coordinates(self):
        library = self.directory / 'unicode é🙂.min'
        library.write_text('\ufeffpublic function answer(): Integer {\n    let text = "é🙂"\n    return text + 2\n}\n')
        self.rejects('use "./unicode é🙂.min" as lib\nprint(lib.answer())\n',
                     f'{library}:3, column 17: the two sides of')

    def test_cold_warm_and_changed_import_diagnostics_match_direct_compilation(self):
        library = self.directory / 'library.min'
        entry = self.directory / 'main.min'
        library.write_text('public function answer(): Integer { return 42 }\n')
        entry.write_text('use "./library.min" as lib\nprint(lib.answer())\n')
        prior = self.directory / 'prior.state'; prior.write_text('')
        following = self.directory / 'next.state'
        stats = self.directory / 'stats'
        output = self.directory / 'output.ll'
        def incremental():
            return subprocess.run([MODULE_COMPILER, entry, output, '--module-state', prior, following, stats], capture_output=True, text=True, timeout=30)
        for _ in range(2):
            result = incremental(); self.assertEqual(result.returncode, 0, result.stderr)
            if following.stat().st_size:
                prior.write_bytes(following.read_bytes())
        self.assertEqual(stats.read_text().split()[0], '2', 'control failed to reuse both cached modules')
        self.assertGreater(prior.stat().st_size, 0, 'warm no-change marker discarded cached origins')
        # An unchanged import uses sparse persisted origins during interface
        # reconstruction, while a changed body gets original source positions.
        cases = [
            ('public function answer(): Integer { return 42 }\n', 'use "./library.min" as lib\nprint(lib.missing())\n', f'{entry}:2, column 7'),
            ('public function answer(): Integer {\n    return "é🙂" + 2\n}\n', 'use "./library.min" as lib\nprint(lib.answer())\n', f'{library}:2, column 17'),
        ]
        for body, main, location in cases:
            library.write_text(body); entry.write_text(main)
            direct = subprocess.run([COMPILER, entry, self.directory / 'direct.ll'], capture_output=True, text=True, timeout=30)
            cached = incremental()
            self.assertEqual(direct.returncode, 1, direct.stderr)
            self.assertEqual(cached.returncode, 1, cached.stderr)
            self.assertEqual(cached.stderr, direct.stderr)
            self.assertIn(location, direct.stderr)
            self.assertEqual(direct.stderr.count(str(library)), int(location.startswith(str(library))))


if __name__ == '__main__':
    unittest.main()
