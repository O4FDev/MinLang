#!/usr/bin/env python3
"""Binary expression metadata reuse preserves operand lifetimes and type context."""
import unittest
from regressions import CompilerTestCase

VALID = [
('left_alias_replacement', '''function replace(values: List<Text>, result: Text): Text {
 values[0] = "changed" + "!"
 return result + "!"
}
let values: List<Text> = ["left" + "!"]
let joined = values[0] + replace(values, "right")
print(joined)
print(values[0])
values[0] = "same" + "!"
print(values[0] == replace(values, "same"))
print(values[0])
''', 'left!right!\nchanged!\ntrue\nchanged!\n'),
('projected_field_replacement', '''record Holder { text: Text }
function replace(values: List<Holder>): Text {
 values[0] = Holder { text: "changed" + "!" }
 return "right" + "!"
}
let values: List<Holder> = [Holder { text: "left" + "!" }]
print(values[0].text + ("/" + replace(values)))
print(values[0].text)
''', 'left!/right!\nchanged!\n'),
('owned_result_transfers', '''record Saved { text: Text }
function make(tag: Text): Text { return tag + "!" }
let values: List<Text> = []
values.add(make("A") + (make("B") + "tail"))
let saved = Saved { text: make("C") + (make("D") + "tail") }
print(values[0])
print(saved.text)
print((make("X") + make("Y")) == (make("X") + make("Y")))
''', 'A!B!tail\nC!D!tail\ntrue\n'),
('precedence_and_short_circuit', '''function unexpected(): Boolean { fail("a short-circuited operand ran") }
print(1 + 2 * 3 == 7)
print((1 < 2) == true)
print(10 - 6 / 2)
print(20 / 2 / 2)
print(2 * 3 + 4 < 11 == true)
print(("a" + "b" == "ab") && !(2 * 3 == 7) || false)
print(false && unexpected() || true)
print(true || unexpected())
''', 'true\ntrue\n7\n5\ntrue\ntrue\ntrue\ntrue\n'),
]
INVALID = [
 ('neutral_rhs_literal', 'print([1] == [])\n', "the two sides of '==' have different types"),
 ('text_integer_mismatch', 'print("x" + 1)\n', "the two sides of '+' have different types"),
 ('list_equality_unsupported', 'print([1] == [2])\n', 'records, Lists, and Bytes do not yet support equality'),
 ('neutral_rhs_binding', 'let values: List<Integer> = []\nprint(values == [])\n', "the two sides of '==' have different types"),
 ('comparison_changes_type', "print(('a' < 'b') == 1)\n", "the two sides of '==' have different types"),
 ('nested_operand_mismatch', 'print((1 + 2) * true)\n', "the two sides of '*' have different types"),
]


class BinaryExpressionOwnership(CompilerTestCase):
    def test_operand_lifetimes_and_evaluation_order(self):
        for name, source, expected in VALID:
            with self.subTest(case=name):
                self.executes(source, expected)

    def test_right_operand_context_and_diagnostics(self):
        for name, source, diagnostic in INVALID:
            with self.subTest(case=name):
                self.rejects(source, diagnostic)

    def test_owned_text_chain_uses_consuming_join(self):
        result, llvm = self.compile('''function piece(value: Text): Text {
 return value + "!"
}
print((piece("a") + piece("b")) + piece("c"))
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        generated = llvm.read_text()
        self.assertGreaterEqual(
            generated.count('call ptr @minyar_join_text_take_left('), 2,
            'fresh intermediate Text results should be consumed by the next join',
        )
        self.executes('''function piece(value: Text): Text { return value + "!" }
print((piece("a") + piece("b")) + piece("c"))
''', 'a!b!c!\n')

    def test_text_self_reassignment_moves_the_local_owner(self):
        result, llvm = self.compile('''let text = Text(0)
let position = 0
while position < 4096 {
 text = text + "abcdefgh"
 position = position + 1
}
let alias = text
text = text + "!"
print(alias.length)
print(text.length)
let doubled = "ab"
doubled = doubled + doubled
print(doubled)
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        generated = llvm.read_text()
        # The two joins with a literal RHS move the exact local owner. Reading
        # the same local on the RHS (doubled + doubled) keeps both operands live
        # and deliberately uses the ordinary join instead.
        self.assertEqual(generated.count('call void @minyar_rc_local_move_owner('), 2)
        self.assertEqual(generated.count('call ptr @minyar_join_text_take_left('), 2)
        self.assertEqual(generated.count('call ptr @minyar_join_text('), 1)
        self.executes('''let text = Text(0)
let position = 0
while position < 4096 {
 text = text + "abcdefgh"
 position = position + 1
}
let alias = text
text = text + "!"
print(alias.length)
print(text.length)
let doubled = "ab"
doubled = doubled + doubled
print(doubled)
''', '32769\n32770\nabab\n')

    def test_owned_list_replacement_transfers_only_fresh_results(self):
        result, llvm = self.compile('''function make(value: Text): Text { return value + "!" }
let values: List<Text> = ["old"]
values[0] = make("fresh")
let borrowed = make("borrowed")
values[0] = borrowed
print(values[0])
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        generated = llvm.read_text().split('define i32 @main(', 1)[1]
        self.assertEqual(generated.count('call void @minyar_list_set_take('), 1)
        self.assertEqual(generated.count('call void @minyar_list_set('), 1)
        self.executes('''function make(value: Text): Text { return value + "!" }
let values: List<Text> = ["old"]
values[0] = make("fresh")
let borrowed = make("borrowed")
values[0] = borrowed
print(values[0])
''', 'borrowed!\n')

    def test_aliases_survive_replacement_and_self_reads_at_varied_text_sizes(self):
        # Exercise immutable aliases at growth boundaries while the RHS
        # replaces the collection's owner.
        sources = ['''function overwrite(values: List<Text>, replacement: Text): Text {
 let prior = values[0]
 values[0] = replacement
 return prior
}
''']
        expected = []
        for size in (1, 15, 16, 31, 32, 63, 64, 127, 128, 255, 256, 1024):
            prior = 'x' * size + '!'
            replacement = 'new' + str(size)
            sources.append(f'''if true {{
 let values: List<Text> = ["{'x' * size}" + "!"]
 let alias = values[0]
 let joined = values[0] + overwrite(values, "new" + Text({size}))
 print(joined)
 print(alias)
 values[0] = values[0] + values[0]
 print(values[0])
 print(alias)
}}
''')
            expected.extend((prior + prior, prior, replacement + replacement, prior))
        self.executes(''.join(sources), '\n'.join(expected) + '\n')


if __name__ == '__main__':
    unittest.main()
