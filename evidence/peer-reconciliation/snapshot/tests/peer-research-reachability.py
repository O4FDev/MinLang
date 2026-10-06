#!/usr/bin/env python3
"""Literal-true loop reachability: a candidate from Zig's ordinary while test.

This follows Minyar's existing every-reachable-path return contract. It adds no
loop expressions, constant-folding language feature, labeled breaks or syntax.
"""

import unittest
from regressions import CompilerTestCase


class LiteralTrueLoopReachability(CompilerTestCase):
    def test_value_return_inside_literal_true_loop(self):
        self.executes("""function value(): Integer {
    while true { return 41 }
}
print(value())
""", "41\n")

    def test_conditional_return_with_continue_has_no_fallthrough(self):
        self.executes("""function value(): Integer {
    let count = 0
    while true {
        count += 1
        if count == 4 { return count }
        continue
    }
}
print(value())
""", "4\n")

    def test_inner_loop_break_does_not_exit_outer_loop(self):
        for loop in ("while true { break }", "for item in 0..1 { break }"):
            with self.subTest(loop=loop):
                self.executes(f"function value(): Integer {{\n"
                              f"while true {{\n{loop}\nreturn 42\n}}\n}}\nprint(value())\n",
                              "42\n")

    def test_unreachable_break_after_return_does_not_create_fallthrough(self):
        self.executes("""function value(): Integer {
    while true {
        return 43
        break
    }
}
print(value())
""", "43\n")

    def test_diverging_value_functions_need_no_unreachable_return(self):
        for body in ("", "continue", "continue\nbreak"):
            with self.subTest(body=body):
                # These functions are deliberately unused; every LLVM block
                # must still verify at both optimization levels.
                self.executes(f"function never(): Integer {{ while true {{\n{body}\n}} }}\n"
                              "print(44)\n", "44\n")

    def test_owned_return_from_literal_true_loop_keeps_its_value(self):
        self.executes("""record Result { text: Text }
function value(): Result {
    while true {
        let text = "retained" + "!"
        return Result { text: text }
    }
}
print(value().text)
""", "retained!\n")

    def test_reachable_break_still_requires_return_after_the_loop(self):
        for body in ("break", "if flag { break } else { return 1 }",
                     "while true { break }\nif flag { break }\nreturn 1"):
            with self.subTest(body=body):
                self.rejects(f"function value(flag: Boolean): Integer {{\n"
                             f"while true {{\n{body}\n}}\n}}\n",
                             "must return a value on every path")

    def test_reachable_break_can_reach_a_following_return(self):
        self.executes("""function value(flag: Boolean): Integer {
    while true {
        if flag { break }
        return 45
    }
    return 46
}
print(value(false))
print(value(true))
""", "45\n46\n")

    def test_while_marker_keeps_continue_after_a_reachable_break(self):
        self.executes("""function value(takeBreak: Boolean, skipOnce: Boolean): Integer {
    let visits = 0
    while true {
        visits += 1
        if takeBreak { break }
        if skipOnce && visits == 1 { continue }
        return 7
    }
    return 8
}
print(value(true, true))
print(value(false, true))
print(value(false, false))
""", "8\n7\n7\n")

    def test_dead_nested_branches_and_loops_do_not_add_an_outer_exit(self):
        self.executes("""function value(flag: Boolean): Integer {
    while true {
        if flag { return 47 } else { return 48 }
        if flag { break } else if !flag { break } else { continue }
        while true { break }
        for item in 0..1 { break }
        break
    }
}
print(value(true))
print(value(false))
""", "47\n48\n")

    def test_nonconstant_condition_still_requires_return(self):
        self.rejects("function value(flag: Boolean): Integer {\n"
                     "while flag { return 1 }\n}\n",
                     "must return a value on every path")

    def test_compound_true_condition_keeps_existing_conservative_behavior(self):
        self.rejects("function value(): Integer {\n"
                     "while true || false { return 1 }\n}\n",
                     "must return a value on every path")

    def test_compound_condition_starting_with_true_can_still_fall_through(self):
        for condition in ("true && flag", "true == flag"):
            with self.subTest(condition=condition):
                self.rejects("function value(flag: Boolean): Integer {\n"
                             f"while {condition} {{ return 1 }}\n}}\n",
                             "must return a value on every path")

    def test_unreachable_source_still_resolves_names_and_checks_types(self):
        for statement, diagnostic in (
            ("print(missingName)", "can't find a value"),
            ("print(1 + true)", "the two sides of '+' have different types (Integer and Boolean)"),
            ("while 1 { break }", "a while condition must be Boolean"),
        ):
            with self.subTest(statement=statement):
                self.rejects("function value(): Integer {\n"
                             "    while true {\n"
                             "        return 49\n"
                             f"        {statement}\n"
                             "    }\n}\n", diagnostic)

    def test_unreachable_source_keeps_its_diagnostic_location(self):
        self.rejects("function value(): Integer {\n"
                     "    while true {\n"
                     "        return 49\n"
                     "        print(missingName)\n"
                     "    }\n}\n",
                     "line 4, column 15: I can't find a value named 'missingName'")

    def test_observable_effects_before_return_or_break_are_preserved(self):
        self.executes("""function value(effects: List<Integer>, takeBreak: Boolean): Integer {
    while true {
        effects.add(1)
        if takeBreak { effects.add(2); break }
        effects.add(3)
        return 4
    }
    effects.add(5)
    return 6
}
let effects: List<Integer> = []
print(value(effects, false))
print(effects.length)
print(value(effects, true))
print(effects.length)
for effect in effects { print(effect) }
""", "4\n2\n6\n5\n1\n3\n1\n2\n5\n")

    def test_loop_condition_still_requires_boolean(self):
        for value in ("1", "1.0", '"true"', "'t'"):
            with self.subTest(value=value):
                self.rejects(f"function value(): Integer {{\n"
                             f"while {value} {{ return 1 }}\n}}\n",
                             "a while condition must be Boolean")


if __name__ == "__main__":
    unittest.main()
