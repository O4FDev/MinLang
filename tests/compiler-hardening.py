#!/usr/bin/env python3
"""Compiler contracts for constants, native bodies, and module shadowing.

Uses the shared compiler/runtime environment overrides; execution oracles run
at O0 and O2. Invalid declarations must fail before LLVM is published.
"""
import os
from pathlib import Path
import random
import subprocess
import unittest
from regressions import CompilerTestCase, LINK_FLAGS, ROOT, COMPILER
from llvm_sanitizer import prepare_llvm_for_link


class CompilerHardening(CompilerTestCase):
    def test_executable_entry_is_not_an_ordinary_callable_function(self):
        for source in ('function main(): Integer { return main() }\n',
                       'function main(): Integer { return 0 }\n'
                       'function invoke(): Integer { return main() }\n'):
            self.rejects(source,
                         'the executable entry main cannot be called')

    def test_imported_main_uses_the_language_calling_convention(self):
        (self.directory / 'entry-name.min').write_text(
            'public function main(): Integer { return 42 }\n')
        self.executes('use "./entry-name.min" as lib\nprint(lib.main())\n', '42\n')

    def test_runtime_names_have_distinct_language_symbols(self):
        names = ('minyar_fail_integer_overflow', 'minyar_fail_integer_division',
                 'minyar_print_integer', 'minyar_list_get', 'minyar_stack_enter',
                 'minyar_rc_enter_stack_v1', 'minyar_future_helper', 'minyar_')
        source = ''.join(f'function {name}(): Integer {{ return 42 }}\n' for name in names)
        source += ''.join(f'print({name}())\n' for name in names)
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in names:
            self.assertIn(f'define i64 @.minyar.fn.{name}(', llvm.read_text())
            self.assertNotIn(f'define i64 @{name}(', llvm.read_text())
        self.executes(source, '42\n' * len(names))

    def test_imported_runtime_named_functions_are_safe(self):
        (self.directory / 'reserved.min').write_text(
            'public function minyar_fail_integer_overflow(): Integer { return 42 }\n')
        self.executes('use "./reserved.min" as lib\nprint(lib.minyar_fail_integer_overflow())\n', '42\n')

    def test_package_names_keep_hyphens_and_underscores(self):
        library = self.directory / 'library with spaces'
        library.mkdir()
        self.compiler_arguments = ['--library', str(library)]
        for name in ('valid-name', 'under_score', 'a1'):
            (library / (name + '.min')).write_text(
                'public function answer(): Integer { return 42 }\n')
            self.executes(f'use "{name}" as package\nprint(package.answer())\n', '42\n')
        for name in ('bad.name', 'bad/name', 'bad name'):
            self.rejects(f'use "{name}" as package\n',
                         "package names use letters, digits, '-', and '_'")

    def test_module_declarations_may_precede_imports(self):
        (self.directory / 'empty.min').write_text('public function value(): Integer { return 1 }\n')
        declaration = 'function answer(): Integer { return 42 }\n'
        imported = 'use "./empty.min" as empty\n'
        for source in (declaration + imported, imported + declaration):
            self.executes(source + 'print(answer() + empty.value())\n', '43\n')

    def test_parent_imports_remain_relative_when_a_library_is_selected(self):
        project = self.directory / 'project with spaces'
        nested = project / 'nested'
        library = self.directory / 'library with spaces'
        nested.mkdir(parents=True)
        library.mkdir()
        (project / 'shared.min').write_text(
            'public function value(): Integer { return 42 }\n')
        (nested / 'local.min').write_text(
            'public function value(): Integer { return 7 }\n')
        (library / 'shared.min').write_text(
            'public function value(): Integer { return 13 }\n')
        self.directory = nested
        self.compiler_arguments = ['--library', str(library)]
        self.executes('use "../shared.min" as parent\n'
                      'use "./local.min" as local\n'
                      'use "shared" as package\n'
                      'print(parent.value())\nprint(local.value())\n'
                      'print(package.value())\n', '42\n7\n13\n')
        self.rejects('use ".shared" as invalid\n',
                     "package names use letters, digits, '-', and '_'")

    def test_character_literals_emit_scalar_constants(self):
        llvm = self.executes("constant LETTER = 'é'\n"
                             "print(Integer('a'))\nprint(Integer(LETTER))\n"
                             "print(Integer('中'))\nprint(Integer('🙂'))\n"
                             "print(Integer('\\n'))\nprint(Integer('\\t'))\n"
                             "print(Integer('\\\\'))\n",
                             '97\n233\n20013\n128578\n10\n9\n92\n')
        self.assertNotIn('call i32 @minyar_text_character_at', llvm.read_text(),
                         'validated Character literals still perform runtime Text reads')

    def test_hex_integer_boundaries_match_decimal_literals(self):
        self.executes('''constant LOW = -0x000000008000000000000000
print(0x7FFFFFFFFFFFFFFF)
print(-0x7FFFFFFFFFFFFFFF)
print(-0x8000000000000000)
print(LOW)
''', '9223372036854775807\n-9223372036854775807\n-9223372036854775808\n-9223372036854775808\n')
        for expression in ('0x8000000000000000', '-0x8000000000000001',
                           '-0xFFFFFFFFFFFFFFFF', '-0x80000000000000000',
                           '1 - 0x8000000000000000'):
            with self.subTest(expression=expression):
                self.rejects(f'print({expression})\n',
                             'Integer literal is outside the supported range')
        self.rejects('constant UNUSED = 0x8000000000000000\n',
                     'Integer literal is outside the supported range')

    def test_hex_literals_cannot_enter_the_decimal_float_parser(self):
        self.rejects('print(0x1.5)\n',
                     'hexadecimal literals are Integers and cannot have a decimal point')

    def test_float_normalization_matches_independent_decimal_conversion(self):
        rng = random.Random(7314)
        lines = []
        for _ in range(64):
            digits = str(rng.randrange(1, 10 ** rng.randrange(1, 31)))
            point = rng.randrange(1, len(digits) + 1)
            value = ('0' * rng.randrange(9) + digits[:point] + '.' +
                     (digits[point:] or '0') + '0' * rng.randrange(9) +
                     'e' + str(rng.randrange(-330, 271)))
            expected = format(float(value), '.17e')
            lines.append(f'print({value} == {expected})')
        self.executes('\n'.join(lines) + '\n', 'true\n' * len(lines))
        self.executes('print(-0.0)\nprint(0.0e999999999999999999999)\n', '-0.0\n0.0\n')

    def test_large_float_mantissas_keep_their_exponent(self):
        value = '0.' + '0' * 100010 + '1e100011'
        self.executes(f'print({value})\n', '1.0\n')
        self.rejects('print(0.' + '0' * 100010 + '1e100400)\n',
                     'Float literal is larger than the largest Float')

    def test_float_literals_reject_the_exact_overflow_boundary(self):
        boundary = 2 ** 1024 - 2 ** 970
        for value in ('1.8e308', '-1.8e308', '1.7976931348623159e308',
                      str(boundary) + '.0'):
            with self.subTest(value=value):
                self.rejects(f'print({value})\n',
                             'Float literal is larger than the largest Float')
        self.executes('print(1.7976931348623158e308 == 1.7976931348623157e308)\n', 'true\n')
        # Decimal digits immediately below the exact midpoint still round to
        # the finite maximum; exponent spelling must not affect the decision.
        finite = str(boundary - 1) + '.0'
        self.executes(f'print({finite} == 1.7976931348623157e308)\n', 'true\n')

    def test_wrapped_calls_and_lists_need_no_trailing_comma(self):
        self.executes('''function add(
left: Integer,
right: Integer
): Integer { return left + right }
let values = [
add(
20,
22
),
(
3 +
4
)
]
print(values[
0
])
print(values[1])
''', '42\n7\n')

    def test_else_if_can_follow_a_newline(self):
        self.executes('''function category(value: Integer): Integer {
if value < 0 { return 1 }
// A branch may continue after whitespace and comments.
else if value == 0 { return 2 }
else { return 3 }
}
if false { print(0) }
print(category(-1))
print(category(0))
print(category(1))
''', '1\n2\n3\n')

    def test_unused_constants_validate_their_literals(self):
        for value, diagnostic in (
            ('9223372036854775808', 'Integer literal is outside the supported range'),
            ('-9223372036854775809', 'Integer literal is outside the supported range'),
            ('1.0e309', 'Float literal is larger than the largest Float'),
        ):
            with self.subTest(value=value):
                self.rejects(f'constant UNUSED = {value}\nprint(42)\n', diagnostic)

    def test_native_library_names_cannot_inject_llvm(self):
        for library in ('', '../graphics', 'bad-name', 'bad|name', 'bad\\nname', 'bad\x00name', 'é'):
            with self.subTest(library=library):
                self.rejects(f'function draw() {{ native "{library}" }}\n',
                             'native library names must use ASCII letters, digits, and')

    def test_native_must_be_the_entire_function_body(self):
        for body in (
            'print(1); native "graphics"',
            'native "graphics"; print(1)',
            'if true { native "graphics" }',
            'if true {} else { native "graphics" }',
            'while true { native "graphics" }',
        ):
            with self.subTest(body=body):
                self.rejects(f'function draw() {{ {body} }}\n',
                             'native must be the only statement in its function')

    def test_valid_native_signature(self):
        result, llvm = self.compile('''function draw(value: Float, ready: Boolean): Boolean {
native "graphics"
}
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        output = llvm.read_text()
        self.assertIn('declare zeroext i1 @minyar_graphics_draw(double, i1 zeroext)', output)
        self.assertIn('; minyar-native-library: graphics', output)

    def test_native_bindings_cannot_redeclare_any_emitted_runtime_symbol(self):
        declarations = (
            'function enter(): Integer { native "rc" }',
            'function enter(value: Integer) { native "rc" }',
            'function enter() { native "stack" }',
            'function integer(value: Integer) { native "print" }',
            'function length(value: Bytes): Integer { native "bytes" }',
            'function division(value: Integer) { native "fail_integer" }',
            'function overflow() { native "fail_integer" }',
        )
        for declaration in declarations:
            with self.subTest(declaration=declaration):
                self.rejects(declaration + '\n',
                             'native symbol conflicts with a runtime function')
        self.compiler_arguments = ['--bounded-owners', '2048']
        self.rejects('function enter_stack_v1(slots: Text, frame: Text, count: Integer) '
                     '{ native "rc" }\n',
                     'native symbol conflicts with a runtime function')

    def test_imported_runtime_native_bindings_fail_direct_and_module_fallback(self):
        module_compiler = Path(os.environ.get('MINYAR_TEST_MODULE_COMPILER', ROOT / 'build/minyarc-modules'))
        for declaration in ('function enter(): Integer { native "rc" }',
                            'function enter(value: Integer) { native "rc" }',
                            'function division(value: Integer) { native "fail_integer" }'):
            (self.directory / 'collision.min').write_text('public ' + declaration + '\n')
            entry = self.directory / 'entry.min'
            entry.write_text('use "./collision.min" as collision\n')
            for compiler in (COMPILER, module_compiler):
                with self.subTest(declaration=declaration, compiler=compiler):
                    llvm = self.directory / 'collision.ll'
                    prior = self.directory / 'prior.state'
                    prior.write_text('')
                    options = [] if compiler == COMPILER else [
                        '--module-state', str(prior), str(self.directory / 'next.state'),
                        str(self.directory / 'stats')]
                    result = subprocess.run([str(compiler), str(entry), str(llvm), *options],
                                            capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertIn('native symbol conflicts with a runtime function', result.stderr)
                    self.assertFalse(llvm.exists(), 'invalid native ABI left LLVM output behind')

    def test_conflicting_native_signatures_are_rejected_before_llvm(self):
        (self.directory / 'integer.min').write_text(
            'public function sample(value: Integer): Integer { native "graphics" }\n')
        (self.directory / 'float.min').write_text(
            'public function sample(value: Float): Float { native "graphics" }\n')
        self.rejects('use "./integer.min" as integer\nuse "./float.min" as float\n',
                     'native symbol has conflicting function signatures')

    def test_native_symbols_are_distinct_from_language_names(self):
        result, llvm = self.compile('''function sample(): Integer { native "graphics" }
function minyar_graphics_sample(): Integer { return 42 }
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        generated = llvm.read_text()
        self.assertIn('declare i64 @minyar_graphics_sample()', generated)
        self.assertIn('define i64 @.minyar.fn.sample()', generated)
        self.assertIn('define i64 @.minyar.fn.minyar_graphics_sample()', generated)

    def test_module_constant_shadowing_matches_single_module(self):
        (self.directory / 'empty.min').write_text('public constant SENTINEL = 0\n')
        source = '''constant VALUE = 99
function typed(VALUE: Integer): Integer { return VALUE }
let VALUE: Integer = 7
print(VALUE)
print(typed(12))
'''
        self.executes(source, '7\n12\n')
        self.executes('use "./empty.min" as empty\n' + source, '7\n12\n')

    def test_compound_assignment_captures_targets_before_side_effects(self):
        self.executes('''record Cell { number: Float; label: Text; bytes: Bytes }
record Holder { cell: Cell }
function replacement(holder: Holder): Float {
holder.cell = Cell { number: 99.0; label: "new"; bytes: Bytes(1) }
return 2.5
}
function replacementText(holder: Holder): Text {
holder.cell = Cell { number: 88.0; label: "latest"; bytes: Bytes(1) }
return "!"
}
function position(holder: Holder, visits: List<Integer>): Integer {
visits[0] += 1
holder.cell = Cell { number: 77.0; label: "bytes"; bytes: Bytes(1) }
return 0
}
let holder = Holder { cell: Cell { number: 1.5; label: "old"; bytes: Bytes(1) } }
holder.cell.number += replacement(holder)
print(holder.cell.number)
holder.cell.label += replacementText(holder)
print(holder.cell.label)
let visits = [0]
holder.cell.bytes[position(holder, visits)] += 1
print(holder.cell.bytes[0])
print(visits[0])
let values = [1.25]
values[0] *= 4.0
print(values[0])
''', '99.0\nlatest\n0\n1\n5.0\n')

    def test_constant_boundaries_and_else_if(self):
        self.executes('''constant LOW = -9223372036854775808
constant HIGH = 9223372036854775807
constant SMALL: Float = -0.25
constant WORD = "é"
function category(value: Integer): Text {
if value < 0 { return "negative" } else if value == 0 { return WORD } else { return "positive" }
}
print(LOW)
print(HIGH)
print(SMALL)
print(category(-1))
print(category(0))
print(category(1))
''', '-9223372036854775808\n9223372036854775807\n-0.25\nnegative\né\npositive\n')


class BootstrapHardening(CompilerTestCase):
    def compile(self, source):
        self.serial += 1
        path = self.directory / f'bootstrap{self.serial}.min'
        path.write_text(source)
        llvm = path.with_suffix('.ll')
        compiler = Path(os.environ.get('MINYAR_TEST_BOOTSTRAP', ROOT / 'build/stage0'))
        result = subprocess.run([compiler, path, '-o', llvm], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            prepare_llvm_for_link(llvm, LINK_FLAGS)
        return result, llvm

    def test_bootstrap_wrapping_and_else_if_match_the_language(self):
        self.executes('''function category(
value: Integer
): Integer {
if value < 0 { return 1 }
else if value == 0 { return 2 }
else { return 3 }
}
function main() {
print(category(
0
))
return 0
}
''', '2\n')

    def test_bootstrap_entry_is_not_an_ordinary_callable_function(self):
        for source in ('function main(): Integer { return main() }\n',
                       'function main(): Integer { return 0 }\n'
                       'function invoke(): Integer { return main() }\n'):
            self.rejects(source,
                         'the executable entry main cannot be called')

    def test_bootstrap_checked_character_conversion(self):
        self.executes('function main() {\nprint(Character(128578))\nreturn 0\n}\n', '🙂\n')
        self.rejects('function main() {\nprint(Character())\nreturn 0\n}\n',
                     'Character expects exactly one Integer code point')
        self.rejects('function main() {\nprint(Character("text"))\nreturn 0\n}\n',
                     'a Character code point needs Integer')

    def test_bootstrap_integer_accepts_character_code_points(self):
        self.executes("function main() {\nprint(Integer('a'))\nprint(Integer(Character(128578)))\nprint(Integer(42))\nreturn 0\n}\n",
                      '97\n128578\n42\n')
        self.rejects('function main() {\nprint(Integer())\nreturn 0\n}\n',
                     'Integer expects exactly one Integer or Character value')
        self.rejects('function main() {\nprint(Integer("text"))\nreturn 0\n}\n',
                     'Integer expects an Integer or Character value')


if __name__ == '__main__':
    unittest.main()
