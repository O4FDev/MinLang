#!/usr/bin/env python3
"""Immutable incoming bindings use SSA values while mutable bindings keep slots."""
import re
import unittest
from regressions import CompilerTestCase


class ReadonlyParameters(CompilerTestCase):
    def function_body(self, source, name):
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        match = re.search(r'^define [^\n]*@' + name + r'\([^\n]*\)[^\n{]*\{\n(.*?)^}', llvm.read_text(), re.M | re.S)
        self.assertIsNotNone(match, name)
        return match[1]

    def test_scalar_parameters_need_no_local_storage(self):
        source = '''function values(number: Integer, flag: Boolean, letter: Character): Integer {
if flag { print(letter) }
return number + number
}
print(values(7, true, 'é'))
'''
        body = self.function_body(source, 'values')
        for index in range(3):
            self.assertNotIn(f'%local.{index}', body)
        self.executes(source, 'é\n14\n')

    def test_writable_parameter_retains_its_original_slot(self):
        source = '''function advance(counter: Integer, step: Integer): Integer {
while counter < 5 { counter = counter + step }
return counter
}
print(advance(1, 2))
'''
        body = self.function_body(source, 'advance')
        self.assertIn('%local.0', body)
        self.assertNotIn('%local.1', body)
        self.executes(source, '5\n')

    def test_shared_list_contents_remain_mutable_through_ssa_parameter(self):
        source = '''function update(values: List<Integer>, delta: Integer): Integer {
values[0] = values[0] + delta
values.add(values[0])
return values.length
}
let values = [2]
print(update(values, 4))
print(values[0])
print(values[1])
'''
        body = self.function_body(source, 'update')
        self.assertNotIn('%local.0', body)
        self.assertNotIn('%local.1', body)
        self.executes(source, '2\n6\n6\n')

    def test_typed_shadow_initializer_reads_incoming_value(self):
        source = '''function shadow(value: Text): Text {
if true {
let value: Text = value + "inner"
print(value)
}
return value
}
print(shadow("outer"))
'''
        body = self.function_body(source, 'shadow')
        self.assertNotIn('%local.0', body)
        self.executes(source, 'outerinner\nouter\n')

    def test_untyped_shadow_and_self_assignment_remain_safe(self):
        source = '''function shadow(value: Text): Text {
if true {
let value = value + "inner"
value = value
print(value)
}
return value
}
print(shadow("outer"))
'''
        self.executes(source, 'outerinner\nouter\n')

    def test_late_nested_write_is_not_hidden_by_braces_or_strings(self):
        source = '''record Label { text: Text }
function choose(value: Text, flag: Boolean): Text {
if flag {
let label = Label { text: "}" }
print(label.text)
if true { value = value + "!" }
}
return value
}
print(choose("first", true))
print(choose("second", false))
'''
        body = self.function_body(source, 'choose')
        self.assertIn('%local.0', body)
        self.assertNotIn('%local.1', body)
        self.executes(source, '}\nfirst!\nsecond\n')

    def test_record_parameter_ids_cannot_alias_scalar_replacement_metadata(self):
        source = '''record Pair { x: Integer; y: Integer }
function inspect(pair: Pair): Integer {
let local = Pair { x: pair.x; y: pair.y }
return local.x + local.y
}
print(inspect(Pair { x: 3; y: 4 }))
'''
        body = self.function_body(source, 'inspect')
        self.assertNotIn('%local.0', body)
        self.assertNotIn('@minyar_record_new', body)
        self.assertEqual(body.count('@minyar_record_get'), 2)
        self.executes(source, '7\n')

    def test_recursion_and_forward_calls_keep_returned_borrows_alive(self):
        self.executes('''function echo(value: Text, depth: Integer): Text {
if depth == 0 { return value }
return later(value, depth - 1)
}
function later(value: Text, depth: Integer): Text { return echo(value, depth) }
print(echo("alive" + "!", 30))
''', 'alive!\n')

    def test_imported_function_parameters_use_the_same_rules(self):
        (self.directory / 'helper.min').write_text('public function decorate(value: Text): Text { return value + "!" }\n')
        self.executes('''use "./helper.min" as helper
print(helper.decorate("module"))
''', 'module!\n')

    def test_large_parameter_lists_keep_bounded_analysis_fallback(self):
        parameters = ', '.join(f'a{i}: Integer' for i in range(65))
        source = f'function many({parameters}): Integer {{ return a0 + a64 }}\n'
        source += 'print(many(' + ', '.join(str(i) for i in range(65)) + '))\n'
        body = self.function_body(source, 'many')
        self.assertIn('%local.0', body)
        self.assertIn('%local.64', body)
        self.executes(source, '64\n')

    def test_caller_protection_survives_later_argument_mutation(self):
        self.executes('''function replace(values: List<Text>): Integer { values[0] = "after"; return 0 }
function keep(value: Text, ignored: Integer): Text { return value }
let values = ["before" + ""]
print(keep(values[0], replace(values)))
print(values[0])
''', 'before\nafter\n')


if __name__ == '__main__':
    unittest.main()
