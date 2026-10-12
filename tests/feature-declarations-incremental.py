#!/usr/bin/env python3
"""Program-wide feature declarations survive multi-module cache replay."""
import os
from pathlib import Path
import re
import unittest

from clang_helpers import clang_command, windows_host
from llvm_sanitizer import prepare_llvm_for_link
from regressions import CompilerTestCase, ROOT, CLANG, RUNTIME, LINK_FLAGS


@unittest.skipIf(windows_host(), 'incremental module caching is a POSIX frontend')
class FeatureDeclarations(CompilerTestCase):
    def probe(self, family):
        leaf = self.directory / 'leaf.min'
        helper = self.directory / 'helper.min'
        entry = self.directory / 'main.min'
        source = 'record Hidden { value: Integer; label: Text }\npublic function make(): Hidden { return Hidden { value: 40; label: " 1:x " } }\n'
        if family == 'text':
            helper.write_text('''use "./leaf.min" as leaf
public function answer(): Integer {
    let item = leaf.make()
    let text = item.label.trim()
    let pieces = text.split(":")
    let value = Integer(pieces[0]) + text.find("x")
    let numbers = [1, 2]
    numbers.clear()
    if text.startsWith("1") && text.endsWith("x") { value += item.value }
    return value
}
''')
            entry.write_text('''use "./helper.min" as helper
let text = " 1:x ".trim()
let pieces = text.split(":")
let value = Integer(pieces[0]) + text.find("x")
let numbers = [1, 2]
numbers.clear()
if text.startsWith("1") && text.endsWith("x") { value += helper.answer() }
print(value)
''')
            names = ['minyar_text_' + n for n in ('find', 'split', 'starts_with', 'ends_with', 'trim', 'integer')] + ['minyar_list_clear']
            expected = b'46\n'
        else:
            helper.write_text('''use "./leaf.min" as leaf
public function answer(): Integer {
    let values = [3, 1, 2]
    values.sort()
    let copy = values.sorted()
    return leaf.make().value + values[0] + copy[1]
}
''')
            entry.write_text('''use "./helper.min" as helper
print(helper.answer())
let values = [3, 2, 1]
values.sort()
print(values.sorted()[1])
''')
            names = ['minyar_list_' + n for n in ('sort', 'sorted', 'sort_by', 'sorted_by')]
            expected = b'43\n2\n'
        sanitized = bool(LINK_FLAGS)
        frontend = Path(os.environ.get('MINYAR_MODULE_COMPILER', ROOT / 'build' / ('minyarc-modules-sanitize' if sanitized else 'minyarc-modules'))).resolve()
        driver = ROOT / 'build' / ('minyar-module-build-sanitize' if sanitized else 'minyar-module-build')
        for mode in ('state', 'driver'):
            leaf.write_text(source)
            prior = self.directory / (mode + '.state')
            prior.write_text('')
            next_state = self.directory / (mode + '.next.state')
            stats = self.directory / (mode + '.stats')
            for phase in ('cold', 'warm', 'private-field-edit', 'post-edit-warm'):
                with self.subTest(mode=mode, phase=phase):
                    if phase == 'private-field-edit':
                        leaf.write_text(source.replace('value: Integer; label: Text', 'label: Text; value: Integer'))
                    llvm = self.directory / (mode + '-' + phase + '.ll')
                    if mode == 'state':
                        command = [frontend, entry, llvm, '--module-state', prior, next_state, stats]
                    else:
                        command = [driver, frontend, entry, llvm, self.directory / 'cache', stats]
                    result = self.evidence.run(list(map(str, command)), timeout=60, phase='incremental-' + phase)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    if mode == 'state':
                        if next_state.stat().st_size:
                            prior.write_bytes(next_state.read_bytes())
                        else:
                            self.assertIn(phase, ('warm', 'post-edit-warm'), 'cold/edited build omitted its cache update')
                    if phase in ('warm', 'post-edit-warm'):
                        self.assertEqual(int(stats.read_text().split()[1]), 0, 'warm body cache was not exercised')
                    for name in names:
                        self.assertEqual(len(re.findall(r'^declare .*@' + name + r'\(', llvm.read_text(), re.M)), 1, name)
                    prepare_llvm_for_link(llvm, LINK_FLAGS)
                    for optimization in ('-O0', '-O2'):
                        executable = llvm.with_suffix('.' + optimization[1:])
                        linked = self.evidence.run(clang_command([CLANG, optimization, *LINK_FLAGS, '-Wno-override-module', str(llvm), str(RUNTIME), '-lm', '-o', str(executable)]), timeout=60, phase='link-incremental-feature')
                        self.assertEqual(linked.returncode, 0, linked.stderr)
                        run = self.evidence.run([str(executable)], timeout=30, phase='execute-incremental-feature')
                        self.assertEqual((run.returncode, run.stdout, run.stderr), (0, expected, b''))

    def test_text_clear_and_integer_declarations(self):
        self.probe('text')

    def test_stable_sort_declarations(self):
        self.probe('sort')


if __name__ == '__main__':
    unittest.main(verbosity=2)
