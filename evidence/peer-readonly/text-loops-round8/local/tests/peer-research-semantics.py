#!/usr/bin/env python3
"""Original Minyar regressions for individually reviewed peer-test properties.

Provenance and incompatible portions are in research/2026-10-memory/peers.json.
These are semantic adaptations, not copied source or claims that upstream
language behavior is completely implemented. Shared CompilerTestCase checks O0/O2.
"""

import unittest
import subprocess
from regressions import CompilerTestCase, CLANG, RUNTIME, LINK_FLAGS, RUN_TIMEOUT
from clang_helpers import clang_command


class PeerSemanticTests(CompilerTestCase):
    def test_swift_unicode_value_survives_indexing_then_consuming_join(self):
        # Preserve the reviewed Swift scalar-literal property after a
        # Minyar-specific consuming assignment; this is an additional stress
        # sequence, not a claim about Swift's String ownership implementation.
        self.executes("""let text = "é🙂" + "!"
print(text.length)
print(Integer(text[0]))
print(Integer(text[1]))
text = text + "ABC"
print(text.length)
print(text.byteLength)
for character in text { print(Integer(character)) }
print(text.slice(0, 2))
""", "3\n233\n128578\n6\n10\n233\n128578\n33\n65\n66\n67\né🙂\n")

    def test_rust_scope_void_call_can_finish_a_void_function(self):
        self.executes("""function finish() { print(23) }
function run() { return finish() }
run()
""", "23\n")

    def test_swift_single_scalar_literals_keep_the_scalar_value(self):
        characters = "bβ𝔹"
        source = []
        expected = []
        for character in characters:
            source += [f"print(Integer('{character}'))",
                       f"print(Character({ord(character)}) == '{character}')",
                       f'print(Text(Character({ord(character)})) == "{character}")']
            expected += [str(ord(character)), "true", "true"]
        self.executes("\n".join(source) + "\n", "\n".join(expected) + "\n")

    def test_swift_string_literals_preserve_multiple_scalars(self):
        source = """let text = "🇦🇺" + ""
print(text.length)
print(text.byteLength)
print(Integer(text[0]))
print(Integer(text[1]))
print(text.slice(0, 1) + text.slice(1, 2) == text)
"""
        self.executes(source, "2\n8\n127462\n127482\ntrue\n")

    def test_swift_float_array_literal_keeps_order_and_values(self):
        values = [((i * 17) % 11 - 5) / 2 for i in range(192)]
        literal = ", ".join(f"{value:.1f}" for value in values)
        source = f"let values: List<Float> = [{literal}]\n"
        source += "print(values.length)\n"
        source += "for value in values { print(Integer(value * 2.0)) }\n"
        expected = ["192", *(str(int(value * 2)) for value in values)]
        self.executes(source, "\n".join(expected) + "\n")

    def test_swift_nested_array_construction_uses_distinct_rows(self):
        self.executes("""let rows: List<List<Integer>> = []
for row in 0..10 {
    let values: List<Integer> = []
    for column in 0..10 { values.add(row * 10 + column) }
    rows.add(values)
}
rows[0][0] = -1
print(rows[0][0])
print(rows[1][0])
print(rows[9][9])
""", "-1\n10\n99\n")

    def test_zig_short_circuit_skips_traps_and_keeps_all_live_effects(self):
        self.executes("""function trap(): Boolean {
    let zero = 0
    return 1 / zero == 0
}
function observe(events: List<Integer>, id: Integer, result: Boolean): Boolean {
    events.add(id)
    return result
}
let events: List<Integer> = []
print(true || trap())
print(false && trap())
print(observe(events, 1, false) || observe(events, 2, true))
print(observe(events, 3, true) && observe(events, 4, false))
print(true || observe(events, 5, false))
print(false && observe(events, 6, true))
for event in events { print(event) }
""", "true\nfalse\ntrue\nfalse\ntrue\nfalse\n1\n2\n3\n4\n")

    def test_go_utf8_scalar_iteration_and_text_construction_agree(self):
        text = "abc日本語"
        source = f'let text = "{text}" + ""\n'
        source += "let rebuilt = \"\"\nfor character in text {\n"
        source += "print(Integer(character))\nrebuilt = rebuilt + Text(character)\n}\n"
        source += "print(rebuilt == text)\nprint(rebuilt.length)\nprint(rebuilt.byteLength)\n"
        expected = [*(str(ord(character)) for character in text), "true", "6", "12"]
        self.executes(source, "\n".join(expected) + "\n")

    def test_go_empty_text_iteration_does_not_touch_outer_binding(self):
        self.executes("""let character = 'β'
let visits = 0
for character in "" {
    visits += 1
    print(character)
}
print(visits)
print(Integer(character))
""", "0\n946\n")

    def test_llvm_divide_shift_wrapping_add_matches_signed_remainder(self):
        values = [-(1 << 63), -(1 << 63) + 1, -(1 << 62), -65537,
                  -65, -64, -63, -5, -4, -3, -1, 0, 1, 3, 4, 5,
                  63, 64, 65, 65537, (1 << 62), (1 << 63) - 2, (1 << 63) - 1]
        source = []
        expected = []
        for power in (2, 4, 6, 30, 61):
            divisor = 1 << power
            source.append(f"function remainder{power}(x: Integer): Integer {{\n"
                          f"return wrappingAdd((x / -{divisor}) << {power}, x)\n}}\n")
            for value in values:
                quotient = (abs(value) // divisor) * (-1 if value < 0 else 1)
                expected.append(str(value - quotient * divisor))
                source.append(f"print(remainder{power}({value}))\n")
        self.executes("".join(source), "\n".join(expected) + "\n")

    def test_nim_discarded_overflowing_result_still_traps(self):
        source = """function calculate(a: Integer, b: Integer) {
    let discarded = a - b
}
function left(): Integer { print(11); return -2 }
function right(): Integer { print(22); return 9223372036854775807 }
calculate(left(), right())
print(33)
"""
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        for optimization in ("-O0", "-O2"):
            with self.subTest(optimization=optimization):
                executable = llvm.with_suffix("." + optimization[1:])
                linked = subprocess.run(clang_command(
                    [CLANG, optimization, *LINK_FLAGS, "-Wno-override-module",
                     str(llvm), str(RUNTIME), "-o", str(executable)]),
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(linked.returncode, 0, linked.stderr)
                run = subprocess.run([str(executable)], capture_output=True,
                                     text=True, timeout=RUN_TIMEOUT)
                self.assertEqual(run.returncode, 1, run.stderr)
                self.assertEqual(run.stdout, "11\n22\n")
                self.assertEqual(run.stderr,
                    "Minyar stopped: this Integer calculation is outside the supported range.\n")

    def test_go_sparse_bit_signed_division_matches_shift_subtract_model(self):
        def divide_model(left, right):
            remainder, divisor, quotient = abs(left), abs(right), 0
            for bit in range(max(0, remainder.bit_length() - divisor.bit_length()), -1, -1):
                if remainder >= divisor << bit:
                    remainder -= divisor << bit
                    quotient |= 1 << bit
            if (left < 0) != (right < 0):
                quotient = -quotient
            return quotient, -remainder if left < 0 else remainder

        values = {0, -1, -(1 << 63), (1 << 63) - 1}
        for bit in (0, 1, 7, 15, 31, 32, 61, 62):
            for offset in (-1, 0, 1):
                values.add((1 << bit) + offset)
                values.add(-((1 << bit) + offset))
        divisors = [-((1 << 63)), -(1 << 32) - 1, -257, -3, -1, 1, 3, 257,
                    (1 << 32) + 1, (1 << 62), (1 << 63) - 1]
        source = ["function quotient(a: Integer, b: Integer): Integer { return a / b }\n",
                  "function remainder(a: Integer, b: Integer): Integer { return a % b }\n"]
        expected = []
        for left in sorted(values):
            for right in divisors:
                if left == -(1 << 63) and right == -1:
                    continue  # Go wraps this pair; Minyar deliberately traps.
                quotient, remainder = divide_model(left, right)
                source += [f"print(quotient({left}, {right}))\n",
                           f"print(remainder({left}, {right}))\n"]
                expected += [str(quotient), str(remainder)]
        self.executes("".join(source), "\n".join(expected) + "\n")

    def test_go_append_value_order_preserves_the_original_input(self):
        patterns = [(0, [0]), (0, [0, 1, 2, 0]), (3, [1]), (3, [1, 2, 0]),
                    (0, [2]), (0, [0, 1, 2, 1]), (3, [0]), (3, [0, 0, 2])]
        kinds = {"Boolean": ["true", "false", "true"],
                 "Integer": ["-17", "0", "9223372036854775807"],
                 "Float": ["-0.5", "0.0", "2.5"],
                 "Text": ['"β"', '"𝔹"', '"abc"']}
        for kind, values in kinds.items():
            with self.subTest(kind=kind):
                source, expected = [], []
                for index, (length, added) in enumerate(patterns):
                    original = values[:length]
                    source.append(f"let before{index}: List<{kind}> = [{', '.join(original)}]\n")
                    source.append(f"let after{index} = before{index}\n")
                    for item in added:
                        source.append(f"after{index} = after{index}.appended({values[item]})\n")
                    source += [f"print(before{index}.length)\n", f"print(after{index}.length)\n",
                               f"for value in before{index} {{ print(value) }}\n",
                               f"for value in after{index} {{ print(value) }}\n"]
                    result = original + [values[item] for item in added]
                    expected += [str(length), str(len(result))]
                    expected += [value.strip('"') for value in original + result]
                self.executes("".join(source), "\n".join(expected) + "\n")


if __name__ == "__main__":
    unittest.main()
