#!/usr/bin/env python3
"""Release correctness regressions: diagnostics, native execution and Unicode properties.

Run against either compiler with MINYAR_TEST_COMPILER; native cases run at O0 and
O2 so backend optimization cannot conceal a frontend/runtime disagreement.
"""
import os
import shlex
from pathlib import Path
import subprocess
import tempfile
import unittest
from llvm_sanitizer import prepare_llvm_for_link

ROOT = Path(__file__).resolve().parents[1]
COMPILER = Path(os.environ.get('MINYAR_TEST_COMPILER', ROOT / 'build/minyarc')).resolve()
CLANG = os.environ.get('MINYAR_TEST_CLANG', 'clang')
RUNTIME = Path(os.environ.get('MINYAR_TEST_RUNTIME', ROOT / 'build/minyar-runtime.o')).resolve()

LINK_FLAGS = shlex.split(os.environ.get("MINYAR_TEST_LINK_FLAGS", ""))

class CompilerTestCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='minyar-regression-')
        self.addCleanup(self.directory.cleanup)
        self.directory = Path(self.directory.name)
        self.serial = 0

    def compile(self, source):
        self.serial += 1
        path = self.directory / f'case{self.serial}.min'
        path.write_text(source, encoding='utf-8')
        llvm = path.with_suffix('.ll')
        result = subprocess.run([str(COMPILER), str(path), str(llvm)], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            prepare_llvm_for_link(llvm, LINK_FLAGS)
        return result, llvm

    def rejects(self, source, diagnostic):
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(diagnostic, result.stderr)
        self.assertFalse(llvm.exists(), 'invalid source left LLVM output behind')
        self.assertNotIn('List position', result.stderr)

    def executes(self, source, expected, status=0):
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        for optimization in ('-O0', '-O2'):
            with self.subTest(optimization=optimization):
                exe = llvm.with_suffix('.' + optimization[1:])
                link = subprocess.run([CLANG, optimization, *LINK_FLAGS, '-Wno-override-module', str(llvm), str(RUNTIME), '-o', str(exe)], capture_output=True, text=True, timeout=30)
                self.assertEqual(link.returncode, 0, link.stderr)
                run = subprocess.run([str(exe)], capture_output=True, timeout=10)
                self.assertEqual(run.returncode, status, run.stderr)
                self.assertEqual(run.stdout, expected.encode('utf-8'))
        return llvm

class Regressions(CompilerTestCase):
    def test_field_and_method_selectors_keep_their_receiver_namespace(self):
        (self.directory / 'tree.min').write_text('''public record Node { text: Text }
public function leaf(): Node { return Node { text: "alive" } }
''')
        self.executes('''use "./tree.min" as tree
record Wrapper { tree: tree.Node }
function slice(n: Integer): Integer { return n + 1 }
let boxes: List<Wrapper> = []
boxes.add(Wrapper { tree: tree.leaf() })
print(boxes[0].tree.text)
let text = "abc"
print(text.slice(0, 2))
print(slice(1))
''', 'alive\nab\n2\n')

    def test_unicode_index_does_not_depend_on_length(self):
        self.executes('let text = "é🙂"\nprint(Text(text[0]))\nprint(text.length)\nprint(Text(text[0]))\n', 'é\n2\né\n')

    def test_unicode_character_output(self):
        self.executes('let text = "é🙂"\nprint(text.length)\nprint(text[0])\nprint(text[1])\n', '2\né\n🙂\n')

    def test_unicode_properties(self):
        for value in ('A', 'é', '界', '🙂', 'Aé界🙂', 'é'):
            with self.subTest(value=value):
                lines = [f'let text = "{value}" + ""']
                expected = []
                for index, character in enumerate(value):
                    lines += [f'print(text[{index}])', f'print(Text(text[{index}])[0])', f'print(text.slice({index}, {index + 1}) == Text(text[{index}]))']
                    expected += [character, character, 'true']
                lines += ['print(text.length)', 'print(text.byteLength)']
                expected += [str(len(value)), str(len(value.encode('utf-8')))]
                self.executes('\n'.join(lines) + '\n', '\n'.join(expected) + '\n')

    def test_invalid_utf8_files(self):
        result, llvm = self.compile('let text = readTextFile(argument(0))\nprint(text.length)\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        exe = llvm.with_suffix('.exe')
        subprocess.run([CLANG, '-O2', *LINK_FLAGS, '-Wno-override-module', str(llvm), str(RUNTIME), '-o', str(exe)], check=True, capture_output=True, timeout=30)
        for encoded in (b'\xc0\xaf', b'\xed\xa0\x80', b'\xf4\x90\x80\x80', b'\xe2\x82'):
            with self.subTest(encoded=encoded):
                path = self.directory / 'invalid-utf8.txt'
                path.write_bytes(encoded)
                run = subprocess.run([str(exe), str(path)], capture_output=True, timeout=10)
                self.assertEqual(run.returncode, 1)
                self.assertIn(b'invalid UTF-8', run.stderr)

    def test_integer_boundaries(self):
        self.executes('print(9223372036854775807)\nprint(-9223372036854775808)\nprint(0000042)\n', '9223372036854775807\n-9223372036854775808\n42\n')
        for literal in ('9223372036854775808', '18446744073709551616', '-9223372036854775809', '0009223372036854775808'):
            with self.subTest(literal=literal):
                self.rejects(f'print({literal})\n', 'Integer literal is outside the supported range')

    def test_missing_return(self):
        for body in ('', 'if flag { return 42 }', 'while flag { return 42 }'):
            with self.subTest(body=body):
                self.rejects(f'function value(flag: Boolean): Integer {{\n{body}\n}}\n', 'must return a value on every path')

    def test_return_paths(self):
        self.executes('function value(flag: Boolean): Integer {\nif flag { return 42 } else { return 7 }\n}\nprint(value(true))\nprint(value(false))\n', '42\n7\n')
        self.executes('function value(flag: Boolean): Integer {\nif flag { return 42 } else { fail("no value") }\n}\nprint(value(true))\n', '42\n')
        self.executes('function stop() {\nreturn\n}\nstop()\nprint("done")\n', 'done\n')

    def test_unreachable_code_preserves_return(self):
        self.executes('function value(): Integer {\nreturn 42\nprint(true || false)\n}\nprint(value())\n', '42\n')
        self.executes('exit(7)\nprint(true && false)\n', '', status=7)

    def test_main_signature(self):
        self.rejects('function main(value: Integer) {\nreturn value\n}\n', 'main expects no parameters')
        self.rejects('function main(): Text {\nreturn "x"\n}\n', 'main must return Integer')

    def test_nothing_is_only_a_return_type(self):
        for source in ('record R { value: Nothing }\n', 'function f(value: Nothing) {}\n', 'let values: List<Nothing> = []\n'):
            with self.subTest(source=source):
                self.rejects(source, 'Nothing cannot be used as a value type')

    def test_unicode_files_and_arguments(self):
        path = self.directory / 'unicode.txt'
        path.write_text('é🙂', encoding='utf-8')
        source = 'let argumentText = argument(0)\nlet fileText = readTextFile(argument(1))\nprint(argumentText[0])\nprint(fileText[1])\n'
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        exe = llvm.with_suffix('.exe')
        subprocess.run([CLANG, '-O2', *LINK_FLAGS, '-Wno-override-module', str(llvm), str(RUNTIME), '-o', str(exe)], check=True, capture_output=True, timeout=30)
        run = subprocess.run([str(exe), 'é🙂', str(path)], capture_output=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout, 'é\n🙂\n'.encode('utf-8'))

    def test_invalid_arithmetic_and_ordering(self):
        for operator in ('+', '-', '*', '/', '%'):
            for value in ('true', "'a'", '"text"'):
                if operator == '+' and value == '"text"':
                    continue
                with self.subTest(operator=operator, value=value):
                    self.rejects(f'print({value} {operator} {value})\n', 'needs Integer operands')
        for value in ('true', '"text"'):
            with self.subTest(value=value):
                self.rejects(f'print({value} < {value})\n', 'ordered comparison needs Integer or Character operands')

    def test_valid_operators(self):
        self.executes('print(7 + 5)\nprint(7 - 5)\nprint(7 * 5)\nprint(7 / 5)\nprint(7 % 5)\nprint(true == false)\nprint("x" == "x")\nprint(\'a\' < \'b\')\nprint("a" + "b")\n', '12\n2\n35\n1\n2\nfalse\ntrue\ntrue\nab\n')

    def test_builtin_arity(self):
        for name, args in {'print':['', '1, 2'], 'Text':['', '1, 2'], 'fail':['', '"x", "y"'], 'exit':['', '0, 1'], 'joinText':['', '[], []'], 'argumentCount':['0'], 'argument':['', '0, 1'], 'readTextFile':['', '"a", "b"'], 'writeTextFile':['', '"a"', '"a", "b", "c"']}.items():
            for arguments in args:
                with self.subTest(name=name, arguments=arguments):
                    self.rejects(f'{name}({arguments})\n', f'{name} expects')

    def test_builtin_types(self):
        for expression in ('fail(1)', 'exit("x")', 'argument(true)', 'readTextFile(42)', 'writeTextFile("x", 1)', 'writeTextFile(1, "x")', 'joinText("x")', 'Text([])', 'print([])'):
            with self.subTest(expression=expression):
                self.rejects(expression + '\n', 'expects')

    def test_nonvalues_and_index_types(self):
        self.rejects('let value = print(42)\n', 'Nothing cannot be stored')
        self.rejects('let values: List<Integer> = []\nvalues.add(1)\nvalues[true] = 2\n', 'a position must be an Integer')
        self.rejects('let value = 42\nprint(value[0])\n', 'indexing needs Text or a List')

if __name__ == '__main__':
    unittest.main(verbosity=2)
