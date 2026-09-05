#!/usr/bin/env python3
"""Dense ownership slots preserve LLVM locals, aliases, and borrowed parameters."""
import os
import re
import subprocess
import sys
import unittest
from regressions import CLANG, COMPILER, ROOT, CompilerTestCase


class CompactOwnership(CompilerTestCase):
    def frame(self, source, name):
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        match = re.search(r'define [^\n]*@' + re.escape(name) + r'\([^\n]*\)[^\n{]*\{\n(.*?)\n\}', llvm.read_text(), re.S)
        self.assertIsNotNone(match, name)
        body = match[1]
        entry = re.search(r'call void @minyar_rc_enter\(i64 (\d+)\)', body)
        self.assertIsNotNone(entry, body)
        indices = set(map(int, re.findall(r'call void @minyar_rc_local(?:_take)?\(i64 (\d+)', body)))
        return int(entry[1]), indices, body

    def test_scalars_do_not_reserve_ownership_slots(self):
        source = 'function mixed(seed: Integer): Integer {\n' + '\n'.join(
            f'let number{i} = seed + {i}' for i in range(200))
        source += '\nlet text = Text(number199) + "!"\nreturn text.length\n}\nprint(mixed(1))\n'
        count, indices, body = self.frame(source, 'mixed')
        self.assertEqual(count, 1)
        self.assertEqual(indices, {0})
        self.assertIn('%local.201', body, 'LLVM local identifiers must stay independent of owner slots')
        self.executes(source, '4\n')

    def test_readonly_borrowed_parameters_need_no_local_owners(self):
        source = '''function decorate(a: Text, b: Text, c: List<Integer>, n: Integer): Text {
let length = c.length + n
return a + b + Text(length)
}
print(decorate("a", "b", [1], 2))
'''
        count, indices, _ = self.frame(source, 'decorate')
        self.assertEqual((count, indices), (0, set()))
        self.executes(source, 'ab3\n')

    def test_assigned_parameter_gets_one_stable_slot_across_branches(self):
        source = '''function select(a: Text, b: Text, flag: Boolean): Text {
let number = 1
if flag { a = b } else { a = a }
let i = 0
while i < 3 {
if flag { a = a + "!" }
i = i + 1
}
return a
}
let original = "old" + ""
let replacement = "new" + ""
print(select(original, replacement, false))
print(select(original, replacement, true))
print(original)
'''
        count, indices, _ = self.frame(source, 'select')
        self.assertEqual((count, indices), (1, {0}))
        self.executes(source, 'old\nnew!!!\nold\n')

    def test_shadowing_scope_cleanup_and_escaping_alias(self):
        self.executes('''function preserve(original: Text, flag: Boolean): Text {
let saved = original
let number = 3
if flag {
let saved = original + " inner"
print(saved)
original = "replacement" + "!"
} else {
let saved = original + " other"
print(saved)
}
let result = saved + original
return result
}
let original = "root" + "!"
print(preserve(original, true))
print(preserve(original, false))
print(original)
''', 'root! inner\nroot!replacement!\nroot! other\nroot!root!\nroot!\n')

    def test_generation_reset_between_functions(self):
        pieces = []
        for i in range(12):
            pieces.append(f'function f{i}(text: Text): Text {{')
            pieces.extend(f'let n{j} = {j}' for j in range(i % 4))
            pieces.append(f'let value = text + "{i}"')
            if i % 2:
                pieces.append('text = value')
            pieces.append('return value\n}')
        pieces.extend(f'print(f{i}("x"))' for i in range(12))
        source = '\n'.join(pieces) + '\n'
        for i in range(12):
            count, indices, _ = self.frame(source, f'f{i}')
            self.assertEqual(count, 1 + i % 2)
            self.assertEqual(indices, set(range(count)))
        self.executes(source, ''.join(f'x{i}\n' for i in range(12)))

    def test_early_returns_and_recursive_parameter_reassignment(self):
        self.executes('''record Box { text: Text }
function walk(box: Box, depth: Integer, replace: Boolean): Box {
let scalar = depth + 1
if depth == 0 { return box }
let saved = box
if replace { box = Box { text: box.text + "!" } }
let child = walk(box, depth - 1, replace)
if replace { return child }
return saved
}
let root = Box { text: "a" + "" }
let same = walk(root, 12, false)
let changed = walk(root, 3, true)
print(same.text)
print(changed.text)
print(root.text)
''', 'a\na!!!\na\n')

    def test_distinct_owners_cannot_share_one_slot(self):
        # This is also the oracle for a seeded ownership-slot collision mutant.
        self.executes('''function pair(): Text {
let a = "first" + "!"
let scalar = 42
let b = "second" + "!"
return a + b
}
print(pair())
''', 'first!second!\n')


    def test_collision_mutant_fails_with_real_use_after_free(self):
        source_root = COMPILER.parent.parent
        source = (source_root / 'src/compiler.min').read_text()
        site = 'return state[entry + 1]'
        self.assertEqual(source.count(site), 1, 'ownership mapper mutation site changed')
        source = source.replace(site, 'return 0', 1)
        path = self.directory / 'collision.min'
        path.write_text(source)
        llvm = path.with_suffix('.ll')
        mutant = self.directory / 'collision-compiler'
        generated = subprocess.run([str(COMPILER), str(path), str(llvm)],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(generated.returncode, 0, generated.stderr)
        linked = subprocess.run([CLANG, '-O1', '-Wno-override-module', str(llvm),
            str(source_root / 'build/minyar-compiler-runtime.ll'), '-o', str(mutant)],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(linked.returncode, 0, linked.stderr)
        environment = os.environ.copy()
        environment['MINYAR_TEST_COMPILER'] = str(mutant)
        environment['MINYAR_TEST_RUNTIME'] = str(ROOT / 'build/ownership-runtime.o')
        environment['MINYAR_TEST_LINK_FLAGS'] = '-fsanitize=address,undefined'
        environment['ASAN_OPTIONS'] = 'detect_leaks=0:halt_on_error=1'
        checked = subprocess.run([sys.executable, str(ROOT / 'tests/compact-ownership.py'),
            'CompactOwnership.test_distinct_owners_cannot_share_one_slot'],
            env=environment, capture_output=True, text=True, timeout=30)
        self.assertEqual(checked.returncode, 1, checked.stderr)
        self.assertIn('AddressSanitizer: heap-use-after-free', checked.stderr)
        for optimization in ('-O0', '-O2'):
            self.assertIn(f"optimization='{optimization}'", checked.stderr)


if __name__ == '__main__':
    unittest.main()
