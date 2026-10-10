#!/usr/bin/env python3
"""Original Minyar adaptations of pinned Swift statement-test subsets.

Provenance/dispositions: peer-swift-statement-directory.json. Swift Optional,
let immutability, exceptions, labels, switch and accessor coroutines are excluded.
The maintained tests do not require that research manifest or downloaded corpus.
"""
import unittest
from regressions import CompilerTestCase


class SwiftStatementSemantics(CompilerTestCase):
    def test_nested_integer_iterations_preserve_running_sum(self):
        # foreach.swift::slices: only ordinary nested iteration, no COW claim.
        self.executes('''let rows: List<List<Integer>> = []
rows.add([2, 3, 5])
rows.add([])
rows.add([7, 11])
let sum = 0
for row in rows { for item in row { sum += item } }
print(sum)
''', '28\n')

    def test_loop_body_binding_does_not_escape_its_scope(self):
        # if_while_var.swift::testWhileScoping: use ordinary body binding.
        self.rejects('''while false { let inner = 1 }
print(inner)
''', "can't find a value named 'inner'")

    def test_branch_binding_does_not_leak_to_siblings(self):
        # if_while_var.swift::binding-else-scope: exclude Optional binding.
        for branch in ('else { print(inner) }',
                       'else if false { print(inner) }',
                       'else if false { let another = 2 } else { print(inner) }'):
            with self.subTest(branch=branch):
                self.rejects('if true { let inner = 1 } ' + branch + '\n',
                             "can't find a value named 'inner'")

    def test_ordinary_if_requires_boolean(self):
        # statements.swift::bad_if and funcdecl5 Boolean conditions.
        for value in ('1', '1.0', '"false"', "'t'"):
            with self.subTest(value=value):
                self.rejects('if ' + value + ' { print(1) }\n',
                             'an if condition must be Boolean')

    def test_jumps_outside_loops_reject_even_in_ordinary_if(self):
        # statements.swift::top-level break/continue, excluding labeled if.
        for jump in ('break', 'continue'):
            for source in (jump + '\n', 'if true { ' + jump + ' }\n'):
                with self.subTest(source=source):
                    self.rejects(source, "'" + jump + "' can only be used inside a loop")

    def test_value_return_requires_a_value(self):
        # statements.swift::NonVoidReturn1.
        self.rejects('function value(): Integer { return }\n',
                     'a returned value has the wrong type')

    def test_void_return_call_preserves_effect_order(self):
        # statements.swift::VoidReturn1/VoidReturn3 ordinary semantic subset.
        self.executes('''function effect(values: List<Integer>) { values.add(2) }
function stop(values: List<Integer>, early: Boolean) {
    values.add(1)
    if early { return; }
    return effect(values)
}
let values: List<Integer> = []
stop(values, true)
stop(values, false)
for value in values { print(value) }
''', '1\n1\n2\n')

    def test_missing_if_else_while_braces_reject_without_output(self):
        # statements.swift::IfStmt1/IfStmt2/IfStmt3/WhileStmt1.
        for source in ('if true\nprint(1)\n',
                       'if true {} else\nprint(1)\n',
                       'if true {} else false {}\n',
                       'while true\nprint(1)\n',
                       'if true else {}\n'):
            with self.subTest(source=source):
                self.rejects(source, "expected '{'")

    def test_contextual_swift_spellings_remain_ordinary_names(self):
        # yield.swift::call_yield / then_stmt.swift ordinary-name subsets.
        self.executes('''function yield(value: Integer): Integer { return value + 1 }
function then(value: Integer): Integer { return yield(value) }
record Words { then: Integer, yield: Integer }
let then = [4, 6]
let words = Words { then: then[0], yield: then[1] }
print(words.then)
print(words.yield)
print(then(words.then))
''', '4\n6\n5\n')

    def test_dead_call_after_break_remains_a_statement(self):
        # statements.swift::breakContinue's named call after a dead break.
        self.executes('''function effect(values: List<Integer>) { values.add(99) }
let values: List<Integer> = []
while true {
    values.add(3)
    break
    effect(values)
}
print(values.length)
print(values[0])
''', '1\n3\n')


if __name__ == '__main__':
    unittest.main()
