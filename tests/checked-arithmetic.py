#!/usr/bin/env python3
"""Checked numeric guards stay visible without changing traps or evaluation order."""

import subprocess
import random
import unittest
from regressions import CompilerTestCase, CLANG, RUNTIME, LINK_FLAGS, RUN_TIMEOUT
from clang_helpers import clang_command


class CheckedArithmetic(CompilerTestCase):
    def test_native_functions_cannot_replace_integer_failure_abi(self):
        for name in ("overflow", "division"):
            with self.subTest(name=name):
                self.rejects(
                    f'function {name}() {{ native "fail_integer" }}\n',
                    "native symbol conflicts with a runtime function",
                )

    def test_checks_are_visible_without_lto(self):
        llvm = self.executes(
            """function sum(left: Integer, right: Integer): Integer {
return left + right
}
function quotient(left: Integer, right: Integer): Integer {
return left / right
}
print(sum(20, 22))
print(quotient(84, 2))
""",
            "42\n42\n",
        )
        ir = llvm.read_text()
        self.assertIn("define internal void @.minyar.integer.overflow.checked", ir)
        self.assertIn("define internal void @.minyar.integer.division.checked", ir)
        self.assertNotIn("noalias", ir)
        self.assertNotIn(" fast ", ir)

    def test_operations_match_independent_signed_integer_model(self):
        rng = random.Random(2102026)
        source = []
        expected = []
        operations = {
            "+": lambda a, b: a + b,
            "-": lambda a, b: a - b,
            "*": lambda a, b: a * b,
            "/": lambda a, b: (abs(a) // abs(b)) * (-1 if (a < 0) != (b < 0) else 1),
        }
        operations["%"] = lambda a, b: a - operations["/"](a, b) * b
        for index, (operator, model) in enumerate(operations.items()):
            name = f"operation{index}"
            source.append(
                f"function {name}(a: Integer, b: Integer): Integer {{ return a {operator} b }}"
            )
            pairs = [
                (
                    rng.randrange(-1000000, 1000001),
                    rng.randrange(1, 1000001) * rng.choice((-1, 1)),
                )
                for _ in range(32)
            ]
            for left, right in pairs:
                source.append(f"print({name}({left}, {right}))")
                expected.append(str(model(left, right)))
        self.executes("\n".join(source) + "\n", "\n".join(expected) + "\n")

    def test_boundary_values_and_signed_remainders(self):
        self.executes(
            """function add(a: Integer, b: Integer): Integer { return a + b }
function subtract(a: Integer, b: Integer): Integer { return a - b }
function multiply(a: Integer, b: Integer): Integer { return a * b }
function divide(a: Integer, b: Integer): Integer { return a / b }
function remainder(a: Integer, b: Integer): Integer { return a % b }
print(add(9223372036854775806, 1))
print(subtract(-9223372036854775807, 1))
print(multiply(-9223372036854775808, 1))
print(multiply(-4611686018427387904, 2))
print(divide(-9223372036854775808, 1))
print(remainder(-9223372036854775808, 1))
print(divide(-7, 3))
print(remainder(-7, 3))
print(divide(7, -3))
print(remainder(7, -3))
""",
            "9223372036854775807\n-9223372036854775808\n-9223372036854775808\n-9223372036854775808\n-9223372036854775808\n0\n-2\n-1\n-2\n1\n",
        )

    def test_failure_diagnostics_and_evaluation_order(self):
        cases = [
            (
                "+",
                "9223372036854775807",
                "1",
                "this Integer calculation is outside the supported range.",
            ),
            (
                "-",
                "-9223372036854775808",
                "1",
                "this Integer calculation is outside the supported range.",
            ),
            (
                "*",
                "-9223372036854775808",
                "-1",
                "this Integer calculation is outside the supported range.",
            ),
            (
                "*",
                "3037000500",
                "3037000500",
                "this Integer calculation is outside the supported range.",
            ),
        ]
        for operator in ("/", "%"):
            cases += [
                (operator, "17", "0", "an Integer cannot be divided by zero."),
                (
                    operator,
                    "-9223372036854775808",
                    "-1",
                    "this Integer division is outside the supported range.",
                ),
            ]
        for operator, left, right, message in cases:
            source = f"""function left(): Integer {{ print(11); return {left} }}
function right(): Integer {{ print(22); return {right} }}
function operation(a: Integer, b: Integer): Integer {{ return a {operator} b }}
print(operation(left(), right()))
print(33)
"""
            result, llvm = self.compile(source)
            self.assertEqual(result.returncode, 0, result.stderr)
            for optimization in ("-O0", "-O2"):
                executable = llvm.with_suffix("." + optimization[1:])
                linked = subprocess.run(
                    clang_command(
                        [
                            CLANG,
                            optimization,
                            *LINK_FLAGS,
                            "-Wno-override-module",
                            str(llvm),
                            str(RUNTIME),
                            "-o",
                            str(executable),
                        ]
                    ),
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertEqual(linked.returncode, 0, linked.stderr)
                run = subprocess.run(
                    [str(executable)],
                    capture_output=True,
                    text=True,
                    timeout=RUN_TIMEOUT,
                )
                self.assertEqual(run.returncode, 1, run.stderr)
                self.assertEqual(run.stdout, "11\n22\n")
                self.assertEqual(run.stderr, f"Minyar stopped: {message}\n")

    def test_unary_negation_keeps_overflow_check(self):
        source = """function negate(value: Integer): Integer { return -value }
print(negate(-9223372036854775808))
"""
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        for optimization in ("-O0", "-O2"):
            executable = llvm.with_suffix("." + optimization[1:])
            linked = subprocess.run(
                clang_command(
                    [
                        CLANG,
                        optimization,
                        *LINK_FLAGS,
                        "-Wno-override-module",
                        str(llvm),
                        str(RUNTIME),
                        "-o",
                        str(executable),
                    ]
                ),
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(linked.returncode, 0, linked.stderr)
            run = subprocess.run(
                [str(executable)], capture_output=True, text=True, timeout=RUN_TIMEOUT
            )
            self.assertEqual(run.returncode, 1, run.stderr)
            self.assertEqual(run.stdout, "")
            self.assertEqual(
                run.stderr,
                "Minyar stopped: this Integer calculation is outside the supported range.\n",
            )


if __name__ == "__main__":
    unittest.main()
