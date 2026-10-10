#!/usr/bin/env python3
"""Checked scalar primitives preserve boundaries, traps, and operand evaluation."""

import subprocess
import random
import unittest
from regressions import CompilerTestCase, CLANG, RUNTIME, LINK_FLAGS, RUN_TIMEOUT
from clang_helpers import clang_command


class CheckedScalars(CompilerTestCase):
    def test_scalar_operations_match_independent_models(self):
        rng = random.Random(2102026)
        source = [
            "function shift(a: Integer, b: Integer): Integer { return a << b }",
            "function right(a: Integer, b: Integer): Integer { return a >> b }",
            "function character(a: Integer): Integer { return Integer(Character(a)) }",
            "function integer(a: Float): Integer { return Integer(a) }",
            "function amplitude(a: Integer): Integer { return abs(a) }",
            "function clipped(a: Integer, lo: Integer, hi: Integer): Integer { return clamp(a, lo, hi) }",
        ]
        expected = []
        for _ in range(48):
            value = rng.randrange(-(1 << 63) + 1, 1 << 63)
            count = rng.randrange(64)
            shifted = (value << count) & ((1 << 64) - 1)
            if shifted >= 1 << 63:
                shifted -= 1 << 64
            scalar = rng.randrange(0x110000)
            if 0xD800 <= scalar <= 0xDFFF:
                scalar += 0x800
            coordinate = rng.randrange(-10000000, 10000000) / 8.0
            lower = rng.randrange(-10000000, 10000000)
            upper = lower + rng.randrange(10000000)
            expressions = [
                (f"shift({value}, {count})", shifted),
                (f"right({value}, {count})", value >> count),
                (f"character({scalar})", scalar),
                (f"integer({coordinate})", int(coordinate)),
                (f"amplitude({value})", abs(value)),
                (f"clipped({value}, {lower}, {upper})", min(max(value, lower), upper)),
            ]
            for expression, answer in expressions:
                source.append(f"print({expression})")
                expected.append(str(answer))
        self.executes("\n".join(source) + "\n", "\n".join(expected) + "\n")

    def test_nan_payload_and_negative_zero_survive_clamp(self):
        self.executes(
            """let payload = Bytes(0)
payload.addInt64(9221120237041090626)
let nan = payload.getFloat64(0)
let output = Bytes(0)
output.addFloat64(clamp(nan, -0.0, -0.0))
output.addFloat64(clamp(-0.0, -0.0, -0.0))
print(output.getInt64(0))
print(output.getInt64(8))
print(payload.getInt64(0))
print(Integer(output.getFloat64(0)))
""",
            "-9223372036854775808\n-9223372036854775808\n9221120237041090626\n0\n",
        )

    def traps(self, source, message):
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        for optimization in ("-O0", "-O2"):
            with self.subTest(optimization=optimization, source=source):
                exe = llvm.with_suffix("." + optimization[1:])
                p = subprocess.run(
                    clang_command(
                        [
                            CLANG,
                            optimization,
                            *LINK_FLAGS,
                            "-Wno-override-module",
                            str(llvm),
                            str(RUNTIME),
                            "-o",
                            str(exe),
                        ]
                    ),
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertEqual(p.returncode, 0, p.stderr)
                p = subprocess.run(
                    [str(exe)], capture_output=True, text=True, timeout=RUN_TIMEOUT
                )
                self.assertEqual(p.returncode, 1, p.stderr)
                self.assertEqual(p.stdout, "11\n22\n")
                self.assertEqual(p.stderr, "Minyar stopped: " + message + "\n")

    def test_good_shift_unicode_float_abs_clamp_boundaries(self):
        self.executes(
            """function shift(a: Integer,b: Integer): Integer { return a << b }
function right(a: Integer,b: Integer): Integer { return a >> b }
function character(a: Integer): Integer { return Integer(Character(a)) }
function integer(a: Float): Integer { return Integer(a) }
function amplitude(a: Integer): Integer { return abs(a) }
print(shift(1,63))
print(shift(-1,63))
print(right(-9223372036854775808,63))
print(shift(-9223372036854775808,0))
print(character(0))
print(character(55295))
print(character(57344))
print(character(1114111))
print(integer(-9223372036854775808.0))
print(integer(9223372036854774784.0))
print(integer(-0.0))
print(integer(-1.75))
print(amplitude(-9223372036854775807))
print(clamp(42,7,7))
print(clamp(-1.0,0.0,2.0))
print(clamp(0.0/0.0,0.0,2.0))
""",
            "-9223372036854775808\n-9223372036854775808\n-1\n-9223372036854775808\n0\n55295\n57344\n1114111\n-9223372036854775808\n9223372036854774784\n0\n-1\n9223372036854775807\n7\n0.0\n0.0\n",
        )

    def test_shift_failure_counts_and_evaluation_order(self):
        for operator in ("<<", ">>"):
            for count in (-9223372036854775808, -1, 64, 9223372036854775807):
                self.traps(
                    f"""function left(): Integer {{ print(11); return -1 }}
function right(): Integer {{ print(22); return {count} }}
print(left() {operator} right())
""",
                    "a shift count must be between 0 and 63.",
                )

    def test_character_surrogates_and_range_failures(self):
        for value in (
            -9223372036854775808,
            -1,
            55296,
            57343,
            1114112,
            9223372036854775807,
        ):
            self.traps(
                f"""function value(): Integer {{ print(11); print(22); return {value} }}
print(Character(value()))
""",
                "this Integer is not a Unicode scalar value.",
            )

    def test_float_nan_infinities_and_exact_bounds(self):
        cases = [
            ("0.0/0.0", "NaN cannot be converted to an Integer."),
            ("9223372036854775808.0", "this Float is outside the Integer range."),
            ("-9223372036854777856.0", "this Float is outside the Integer range."),
            ("1.0/0.0", "this Float is outside the Integer range."),
            ("-1.0/0.0", "this Float is outside the Integer range."),
        ]
        for value, message in cases:
            self.traps(
                f"""function value(): Float {{ print(11); print(22); return {value} }}
print(Integer(value()))
""",
                message,
            )

    def test_abs_and_clamp_exact_failure_diagnostics(self):
        self.traps(
            """function value(): Integer { print(11); print(22); return -9223372036854775808 }
print(abs(value()))
""",
            "the absolute value of this Integer is outside the supported range.",
        )
        for lower, upper in (
            ("7", "6"),
            ("7.0", "6.0"),
            ("0.0/0.0", "1.0"),
            ("0.0", "0.0/0.0"),
        ):
            scalar = "Float" if "." in lower else "Integer"
            value = "0.0" if scalar == "Float" else "0"
            self.traps(
                f"""function lower(): {scalar} {{ print(11); return {lower} }}
function upper(): {scalar} {{ print(22); return {upper} }}
print(clamp({value}, lower(), upper()))
""",
                "clamp needs a lower bound that is not above its upper bound.",
            )

    def test_optimization_guard_visibility_without_lto(self):
        result, llvm = self.compile(
            "print(Character(65))\nprint(Integer(1.5))\nprint(abs(-42))\nprint(clamp(7,0,1))\nprint(1<<7)\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        ir = llvm.read_text()
        for helper in (
            "shift.checked",
            "character.checked",
            "float.integer.checked",
            "integer.absolute.checked",
            "clamp.integer.checked",
            "clamp.float.checked",
        ):
            self.assertIn("@.minyar." + helper, ir)
        self.assertIn("fcmp oge double %value, -9.223372036854775808e18", ir)
        self.assertIn("fcmp olt double %value, 9.223372036854775808e18", ir)
        self.assertNotIn("0xC3E0000000000000", ir)
        self.assertNotIn("0x43E0000000000000", ir)


if __name__ == "__main__":
    unittest.main()
