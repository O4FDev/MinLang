#!/usr/bin/env python3
"""Release correctness regressions: diagnostics, native execution and Unicode properties.

Run against either compiler with MINYAR_TEST_COMPILER; native cases run at O0 and
O2 so backend optimization cannot conceal a frontend/runtime disagreement.
"""
import os
import hashlib
import inspect
import shlex
from pathlib import Path
import subprocess
import unittest
from llvm_sanitizer import prepare_llvm_for_link
from clang_helpers import clang_command
from test_evidence import Evidence

ROOT = Path(__file__).resolve().parents[1]
COMPILER = Path(os.environ.get('MINYAR_TEST_COMPILER', ROOT / 'build/minyarc')).resolve()
CLANG = os.environ.get('MINYAR_TEST_CLANG', 'clang')
RUNTIME = Path(os.environ.get('MINYAR_TEST_RUNTIME', ROOT / 'build/minyar-runtime.o')).resolve()

LINK_FLAGS = shlex.split(os.environ.get("MINYAR_TEST_LINK_FLAGS", ""))
# ASan/UBSan compiler processes run at background priority in the full gate.
# Keep the ordinary hang detector tight, but allow instrumentation and shared
# host scheduling the same ceiling already used for sanitized linking.
COMPILE_TIMEOUT = 30 if LINK_FLAGS else 10
RUN_TIMEOUT = 30 if LINK_FLAGS else 10

class CompilerTestCase(unittest.TestCase):
    def setUp(self):
        self.evidence = Evidence('regression', inputs=(COMPILER, RUNTIME, __file__, inspect.getsourcefile(type(self)) or __file__),
                                 controls={'test': self.id(), 'link_flags': LINK_FLAGS})
        self.directory = self.evidence.path
        self.addCleanup(self.close_evidence)
        self.serial = 0

    def close_evidence(self):
        result = self._outcome.result
        failed = any(test.id() == self.id() or test.id().startswith(self.id() + ' ')
                     for test, _ in result.failures + result.errors)
        self.evidence.close(failed=failed)

    def compile(self, source):
        self.serial += 1
        path = self.directory / f'case{self.serial}.min'
        path.write_text(source, encoding='utf-8')
        llvm = path.with_suffix('.ll')
        result = self.evidence.run([str(COMPILER), str(path), str(llvm),
                                 *getattr(self, 'compiler_arguments', ())],
                                capture_output=True, text=True, timeout=COMPILE_TIMEOUT, phase='compile')
        if result.returncode == 0:
            prepare_llvm_for_link(llvm, LINK_FLAGS)
        return result, llvm

    def rejects(self, source, diagnostic):
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(result.stdout, 'rejected source unexpectedly wrote standard output')
        self.assertIn(diagnostic, result.stderr)
        self.assertFalse(llvm.exists(), 'invalid source left LLVM output behind')
        self.assertNotIn('List position', result.stderr)

    def link_program(self, llvm, optimization, exe):
        return self.evidence.run(clang_command([CLANG, optimization, *LINK_FLAGS, '-Wno-override-module',
                                               str(llvm), str(RUNTIME), '-o', str(exe)]),
                                 capture_output=True, text=True, timeout=30, phase='link')

    def executes(self, source, expected, status=0, stderr='', optimizations=('-O0', '-O2'), arguments=(), file_outputs=()):
        file_outputs = tuple(file_outputs)
        self.evidence.controls.setdefault('execution_oracles', []).append({
            'source': f'case{self.serial + 1}.min', 'stdout': expected,
            'stderr': stderr, 'status': status, 'optimizations': list(optimizations), 'arguments': list(arguments),
            'file_outputs': [{'path': str(path), 'bytes': len(contents), 'sha256': hashlib.sha256(contents).hexdigest()} for path, contents in file_outputs],
        })
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        for optimization in optimizations:
            with self.subTest(optimization=optimization):
                exe = llvm.with_suffix('.' + optimization[1:])
                link = self.link_program(llvm, optimization, exe)
                self.assertEqual(link.returncode, 0, link.stderr)
                for path, _ in file_outputs:
                    Path(path).unlink(missing_ok=True)
                run = self.evidence.run([str(exe), *arguments], capture_output=True, timeout=RUN_TIMEOUT, phase='execute')
                self.assertEqual(run.returncode, status, run.stderr)
                self.assertEqual(run.stdout, expected.encode('utf-8'))
                self.assertEqual(run.stderr, stderr.encode('utf-8'))
                for path, contents in file_outputs:
                    self.assertTrue(Path(path).is_file(), f'program did not create {path}')
                    self.assertEqual(Path(path).read_bytes(), contents)
        return llvm

class Regressions(CompilerTestCase):
    def test_calls_before_a_binding_do_not_shift_ownership_slots(self):
        # A per-body call count once shared a slot with the ownership map:
        # one call in the first binding gave it slot -1, an out-of-bounds store.
        source = ('record Box {\n    label: Text\n}\n'
                  'function make(label: Text): Box { return Box { label: label } }\n'
                  'let box = make("box")\nlet other = make("other")\nprint(box.label + " " + other.label)\n')
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('@minyar_rc_local_take(i64 -', llvm.read_text())
        self.executes(source, 'box other\n')

    def test_utf8_byte_order_mark_is_accepted(self):
        self.executes('\ufeffprint(42)\n', '42\n')

    def test_non_ascii_identifier_has_actionable_diagnostic(self):
        self.rejects(
            'let café = 42\nprint(café)\n',
            "line 1, column 8: names must use ASCII letters, digits, and '_'; found non-ASCII character 'é'",
        )

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

    def test_methods_reject_the_wrong_receiver_kind(self):
        self.rejects('let text = "value"\ntext.add(1)\n', "2, column 6: this value has no method named 'add'")
        self.rejects('let values = [1]\nvalues.slice(0)\n', "2, column 8: this value has no method named 'slice'")

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
        self.evidence.run(clang_command([CLANG, '-O2', *LINK_FLAGS, '-Wno-override-module', str(llvm), str(RUNTIME), '-o', str(exe)]), check=True, capture_output=True, timeout=30)
        for encoded in (b'\xc0\xaf', b'\xed\xa0\x80', b'\xf4\x90\x80\x80', b'\xe2\x82'):
            with self.subTest(encoded=encoded):
                path = self.directory / 'invalid-utf8.txt'
                path.write_bytes(encoded)
                run = self.evidence.run([str(exe), str(path)], capture_output=True, timeout=RUN_TIMEOUT)
                self.assertEqual(run.returncode, 1)
                self.assertIn(b'invalid UTF-8', run.stderr)

    def test_ascii_index_and_slice_validate_invalid_utf8_tail_first(self):
        # The requested ASCII block is valid; malformed bytes are later in
        # the same Text. Lazy indexing must validate the entire value first.
        prefixes = ('a' * 128, '\ufeff' + 'a' * 128, 'é' + 'a' * 127)
        tails = (b'\xff', b'\xe2\x82', b'\xed\xa0\x80', b'\xc0\xaf')
        operations = (('text[0]', lambda value: value[0]),
                      ('text[65]', lambda value: value[65]),
                      ('text.slice(64, 128)', lambda value: value[64:128]))
        path = self.directory / 'indexed-tail.txt'
        for expression, oracle in operations:
            source = 'let text = readTextFile(argument(0))\nprint(' + expression + ')\nprint("after")\n'
            result, llvm = self.compile(source)
            self.assertEqual(result.returncode, 0, result.stderr)
            for optimization in ('-O0', '-O2'):
                exe = llvm.with_suffix('.' + optimization[1:])
                self.evidence.run(clang_command([CLANG, optimization, *LINK_FLAGS, '-Wno-override-module',
                                   llvm, RUNTIME, '-o', exe]), check=True, timeout=30, phase='link')
                for prefix in prefixes:
                    valid = prefix + '🙂'
                    path.write_bytes(valid.encode('utf-8'))
                    observed = self.evidence.run([exe, path], timeout=RUN_TIMEOUT, phase='execute-valid-tail')
                    self.assertEqual((observed.returncode, observed.stdout, observed.stderr),
                                     (0, (oracle(valid) + '\nafter\n').encode('utf-8'), b''))
                    for tail in tails:
                        with self.subTest(expression=expression, optimization=optimization,
                                          prefix=prefix[:2], tail=tail):
                            path.write_bytes(prefix.encode('utf-8') + tail)
                            observed = self.evidence.run([exe, path], timeout=RUN_TIMEOUT,
                                                         phase='execute-invalid-tail')
                            self.assertEqual((observed.returncode, observed.stdout, observed.stderr),
                                             (1, b'', b'Minyar stopped: Text contained invalid UTF-8.\n'))

    def test_file_io_failures_stop_cleanly(self):
        read_result, read_llvm = self.compile('print(readTextFile(argument(0)))\n')
        self.assertEqual(read_result.returncode, 0, read_result.stderr)
        read_exe = read_llvm.with_suffix('.read')
        self.evidence.run(clang_command([CLANG, '-O2', *LINK_FLAGS, '-Wno-override-module', str(read_llvm), str(RUNTIME), '-o', str(read_exe)]), check=True, capture_output=True, timeout=30)
        read_directory = self.evidence.run([str(read_exe), str(self.directory)], capture_output=True, timeout=RUN_TIMEOUT)
        self.assertEqual(read_directory.returncode, 1)
        self.assertTrue(
            b'could not be read' in read_directory.stderr or b'could not be opened' in read_directory.stderr,
            read_directory.stderr,
        )

        write_result, write_llvm = self.compile('writeTextFile(argument(0), "contents")\n')
        self.assertEqual(write_result.returncode, 0, write_result.stderr)
        write_exe = write_llvm.with_suffix('.write')
        self.evidence.run(clang_command([CLANG, '-O2', *LINK_FLAGS, '-Wno-override-module', str(write_llvm), str(RUNTIME), '-o', str(write_exe)]), check=True, capture_output=True, timeout=30)
        write_directory = self.evidence.run([str(write_exe), str(self.directory)], capture_output=True, timeout=RUN_TIMEOUT)
        self.assertEqual(write_directory.returncode, 1)
        self.assertIn(b'could not be created', write_directory.stderr)
        missing_parent = self.directory / 'missing' / 'output.txt'
        write_missing = self.evidence.run([str(write_exe), str(missing_parent)], capture_output=True, timeout=RUN_TIMEOUT)
        self.assertEqual(write_missing.returncode, 1)
        self.assertIn(b'could not be created', write_missing.stderr)

    def test_file_read_preserves_first_byte_and_empty_files(self):
        result, llvm = self.compile('print(readTextFile(argument(0)))\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        exe = llvm.with_suffix('.exe')
        self.evidence.run(clang_command([CLANG, '-O2', *LINK_FLAGS, '-Wno-override-module', str(llvm), str(RUNTIME), '-o', str(exe)]), check=True, capture_output=True, timeout=30)
        path = self.directory / 'contents.txt'
        for contents in (b'', b'A', 'é🙂'.encode('utf-8'), b'first\r\nsecond\n'):
            with self.subTest(contents=contents):
                path.write_bytes(contents)
                run = self.evidence.run([str(exe), str(path)], capture_output=True, timeout=RUN_TIMEOUT)
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(run.stdout, contents + b'\n')

    @unittest.skipIf(os.name == 'nt', 'closing a child descriptor uses POSIX preexec_fn')
    def test_closed_standard_output_is_reported(self):
        result, llvm = self.compile('print("unwritten")\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        exe = llvm.with_suffix('.closed-output')
        self.evidence.run(clang_command([CLANG, '-O2', *LINK_FLAGS, '-Wno-override-module', str(llvm), str(RUNTIME), '-o', str(exe)]), check=True, capture_output=True, timeout=30)
        executed = self.evidence.run(
            [str(exe)],
            capture_output=False,
            stdout=None,
            stderr=subprocess.PIPE,
            preexec_fn=lambda: os.close(1),
            timeout=RUN_TIMEOUT,
        )
        self.assertEqual(executed.returncode, 1)
        self.assertEqual(executed.stderr, b'Minyar stopped: standard output could not be written.\n')

    def test_integer_boundaries(self):
        self.executes('print(9223372036854775807)\nprint(-9223372036854775808)\nprint(0000042)\n', '9223372036854775807\n-9223372036854775808\n42\n')
        for literal in ('9223372036854775808', '18446744073709551616', '-9223372036854775809', '0009223372036854775808'):
            with self.subTest(literal=literal):
                self.rejects(f'print({literal})\n', 'Integer literal is outside the supported range')

    def test_missing_return(self):
        self.rejects('function value(): Integer { return }\n', 'a returned value has the wrong type')
        for body in ('', 'if flag { return 42 }', 'while flag { return 42 }',
                     'while false { return 42 }'):
            with self.subTest(body=body):
                self.rejects(f'function value(flag: Boolean): Integer {{\n{body}\n}}\n', 'must return a value on every path')

    def test_return_paths(self):
        self.executes('function value(flag: Boolean): Integer {\nif flag { return 42 } else { return 7 }\n}\nprint(value(true))\nprint(value(false))\n', '42\n7\n')
        self.executes('function value(flag: Boolean): Integer {\nif flag { return 42 } else { fail("no value") }\n}\nprint(value(true))\n', '42\n')
        self.executes('function stop() {\nreturn\n}\nstop()\nprint("done")\n', 'done\n')

    def test_unreachable_code_preserves_return(self):
        self.executes('function value(): Integer {\nreturn 42\nprint(true || false)\n}\nprint(value())\n', '42\n')
        self.executes('exit(7)\nprint(true && false)\n', '', status=7)

    def test_literal_true_loop_is_terminal(self):
        self.executes('''function scalar(): Integer {
while true { return 1 }
print("unreachable")
}
function owned(flag: Boolean): Text {
let prefix = "retained"
while (true) {
if flag { return prefix + " yes" } else { return prefix + " no" }
}
}
function nested(): List<Integer> { while true { while true { return [4, 2] } } }
function never(): Integer { while true { } }
print(scalar()); print(owned(true)); print(owned(false))
let values = nested(); print(values[0]); print(values[1])
''', '1\nretained yes\nretained no\n4\n2\n')
        self.executes('function stop(): Integer { while true { exit(7) } }\nprint(stop())\n',
                      '', status=7)
        self.executes('function stop(): Integer { while true { fail("loop stopped") } }\nprint(stop())\n',
                      '', status=1, stderr='Minyar stopped: loop stopped\n')
        self.rejects('function value(): Integer { while true { return 1 }; print(missing) }\n',
                     "I can't find a value named 'missing'")

    def test_main_signature(self):
        self.rejects('function main(value: Integer) {\nreturn value\n}\n', 'main expects no parameters')
        self.rejects('function main(): Text {\nreturn "x"\n}\n', 'main must return Integer')

    def test_nothing_is_only_a_return_type(self):
        for source in ('record R { value: Nothing }\n', 'function f(value: Nothing) {}\n', 'let values: List<Nothing> = []\n'):
            with self.subTest(source=source):
                self.rejects(source, 'Nothing cannot be used as a value type')

    def test_unicode_files_and_arguments(self):
        path = self.directory / 'unicode é🙂.txt'
        path.write_text('é🙂', encoding='utf-8')
        source = 'let argumentText = argument(0)\nlet fileText = readTextFile(argument(1))\nprint(argumentText)\nprint(argumentText[0])\nprint(fileText[1])\n'
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        exe = llvm.with_suffix('.exe')
        self.evidence.run(clang_command([CLANG, '-O2', *LINK_FLAGS, '-Wno-override-module', str(llvm), str(RUNTIME), '-o', str(exe)]), check=True, capture_output=True, timeout=30)
        for argument in ('é🙂', 'é🙂 with spaces', 'é🙂 "quoted" \\end\\'):
            with self.subTest(argument=argument):
                run = self.evidence.run([str(exe), argument, str(path)], capture_output=True, timeout=RUN_TIMEOUT)
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(run.stdout, f'{argument}\né\n🙂\n'.encode('utf-8'))

    def test_unicode_paths_support_text_and_binary_file_operations(self):
        text_path = self.directory / 'text é🙂.txt'
        bytes_path = self.directory / 'bytes é🙂.bin'
        self.executes('''let textPath = argument(0)
let bytesPath = argument(1)
print(fileExists(textPath))
writeTextFile(textPath, "é🙂")
print(fileExists(textPath))
print(readTextFile(textPath))
let bytes = Bytes(3)
bytes[0] = 0
bytes[1] = 255
bytes[2] = 42
writeBytesFile(bytesPath, bytes)
print(fileExists(bytesPath))
let read = readBytesFile(bytesPath)
print(read[0])
print(read[1])
print(read[2])
''', 'false\ntrue\né🙂\ntrue\n0\n255\n42\n',
            arguments=(str(text_path), str(bytes_path)),
            file_outputs=((text_path, 'é🙂'.encode('utf-8')), (bytes_path, bytes([0, 255, 42]))))

    def test_write_text_file_writes_list_pieces_without_joining(self):
        # writeTextFile(path, List<Text>) must write exactly what joinText would
        # build: pieces crossing the runtime's write buffer, one piece larger
        # than the buffer, Unicode, and an empty piece.
        path = self.directory / 'pieces é.txt'
        lines = ''.join(f'line {index}\n' for index in range(40000))
        expected = 'é🙂\n' + lines + 'abcde' * 70000 + 'end'
        self.executes('''let pieces: List<Text> = []
pieces.add("")
pieces.add("é🙂\\n")
let index = 0
while index < 40000 {
    pieces.add("line ")
    pieces.add(Text(index))
    pieces.add("\\n")
    index = index + 1
}
let filler: List<Text> = []
index = 0
while index < 70000 {
    filler.add("abcde")
    index = index + 1
}
pieces.add(joinText(filler))
pieces.add("end")
writeTextFile(argument(0), pieces)
let written = readTextFile(argument(0))
print(written == joinText(pieces))
print(written.byteLength)
''', f'true\n{len(expected.encode("utf-8"))}\n', arguments=(str(path),),
            file_outputs=((path, expected.encode('utf-8')),))
        result, llvm = self.compile('let pieces: List<Text> = []\npieces.add("x")\nwriteTextFile(argument(0), pieces)\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('call void @minyar_write_text_parts(', llvm.read_text())
        exe = llvm.with_suffix('.exe')
        self.evidence.run(clang_command([CLANG, '-O2', *LINK_FLAGS, '-Wno-override-module', str(llvm), str(RUNTIME), '-o', str(exe)]), check=True, capture_output=True, timeout=30)
        run = self.evidence.run([str(exe), str(self.directory)], capture_output=True, timeout=RUN_TIMEOUT)
        self.assertEqual(run.returncode, 1)
        self.assertIn(b'could not be created', run.stderr)

    def test_consuming_self_assignment_respects_parameters_and_later_reads(self):
        # x = x + e and x = x.appended(e) move x's owner into the join or
        # append, which may then grow in place. A parameter before its first
        # assignment owns nothing (its caller's count must stay intact), and
        # a later read of x in the same statement must see the old value.
        self.executes('''function growText(t: Text): Integer {
    t = t + "zz"
    return t.length
}
function growList(xs: List<Integer>): Integer {
    xs = xs.appended(99)
    return xs.length
}
function growInLoop(xs: List<Integer>): Integer {
    let count = 0
    while count < 3 {
        xs = xs.appended(count)
        count = count + 1
    }
    return xs.length
}
// Joined, not literal: literals are immortal and never grow in place.
let text = "ab" + "cd"
print(growText(text))
print(text)
let numbers = [1, 2, 3]
print(growList(numbers))
print(numbers.length)
print(numbers[0])
print(growInLoop(numbers))
print(numbers.length)
print(growList([4, 5]))
let repeated = "a" + "b"
repeated = repeated + "!" + repeated
print(repeated)
let values = [10, 20]
values = values.appended(1).appended(values.length)
print(values[3])
''', '6\nabcd\n4\n3\n1\n6\n3\n3\nab!ab\n2\n')

    def test_invalid_arithmetic_and_ordering(self):
        for operator in ('+', '-', '*', '/', '%'):
            for value in ('true', "'a'", '"text"'):
                if operator == '+' and value == '"text"':
                    continue
                with self.subTest(operator=operator, value=value):
                    self.rejects(f'print({value} {operator} {value})\n', 'needs Integer or Float operands')
        for value in ('true', '"text"'):
            with self.subTest(value=value):
                self.rejects(f'print({value} < {value})\n', 'ordered comparison needs Integer, Float, or Character operands')

    def test_valid_operators(self):
        self.executes('print(7 + 5)\nprint(7 - 5)\nprint(7 * 5)\nprint(7 / 5)\nprint(7 % 5)\nprint(true == false)\nprint("x" == "x")\nprint(\'a\' < \'b\')\nprint("a" + "b")\n', '12\n2\n35\n1\n2\nfalse\ntrue\ntrue\nab\n')

    def test_builtin_arity(self):
        for name, args in {'print':['', '1, 2'], 'Text':['', '1, 2'], 'fail':['', '"x", "y"'], 'exit':['', '0, 1'], 'joinText':['', '[], []'], 'argumentCount':['0'], 'argument':['', '0, 1'], 'readTextFile':['', '"a", "b"'], 'writeTextFile':['', '"a"', '"a", "b", "c"']}.items():
            for arguments in args:
                with self.subTest(name=name, arguments=arguments):
                    self.rejects(f'{name}({arguments})\n', f'{name} expects')

    def test_builtin_types(self):
        for expression in ('fail(1)', 'exit("x")', 'argument(true)', 'readTextFile(42)', 'writeTextFile("x", 1)', 'writeTextFile(1, "x")', 'writeTextFile("x", [1, 2])', 'joinText("x")', 'Text([])', 'print([])'):
            with self.subTest(expression=expression):
                self.rejects(expression + '\n', 'expects')

    def test_nonvalues_and_index_types(self):
        self.rejects('let value = print(42)\n', 'Nothing cannot be stored')
        self.rejects('let values: List<Integer> = []\nvalues.add(1)\nvalues[true] = 2\n', 'a position must be an Integer')
        self.rejects('let value = 42\nprint(value[0])\n', 'indexing needs Text, a List, or Bytes')

if __name__ == '__main__':
    unittest.main(verbosity=2)
