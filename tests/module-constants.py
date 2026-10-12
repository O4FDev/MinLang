#!/usr/bin/env python3
"""neo-db G11: tables initialized once, shared imports, dependencies and roots."""
import unittest
from regressions import CompilerTestCase


class ModuleConstants(CompilerTestCase):
    def test_crc32c_slicing_by_eight_table_matches_independent_model(self):
        polynomial = 0x82F63B78
        expected = []
        for index in range(256):
            value = index
            for _ in range(8): value = (value >> 1) ^ (polynomial if value & 1 else 0)
            expected.append(value)
        for group in range(1, 8):
            for index in range(256):
                value = expected[(group - 1) * 256 + index]
                expected.append((value >> 8) ^ expected[value & 255])
        oracle = ','.join(map(str, expected))
        self.executes('''constant POLYNOMIAL = 0x82F63B78
constant TABLE: List<Integer> = makeTable()
function makeTable(): List<Integer> {
    print("crc init")
    let table: List<Integer> = []
    for i in 0..256 {
        let value = i
        for bit in 0..8 {
            if value & 1 == 1 { value = (value >> 1) ^ POLYNOMIAL } else { value = value >> 1 }
        }
        table.add(value)
    }
    for group in 1..8 {
        for i in 0..256 {
            let value = table[(group - 1) * 256 + i]
            table.add((value >> 8) ^ table[value & 255])
        }
    }
    return table
}
function cell(i: Integer): Integer { return TABLE[i] }
let oracle = [''' + oracle + ''']
for i in 0..2048 { if cell(i) != oracle[i] { fail("CRC32C table") } }
print(TABLE.length)
print(cell(1))
''', 'crc init\n2048\n4067132163\n')

    def test_annotated_table_initializes_once_before_main(self):
        self.executes('''constant TABLE: List<Integer> = makeTable()
function makeTable(): List<Integer> {
    print("init")
    let table: List<Integer> = []
    for i in 0..2048 { table.add(i * 7) }
    return table
}
function item(i: Integer): Integer { return TABLE[i] }
function main(): Integer {
    print("main")
    print(item(2047))
    print(item(1))
    print(TABLE.length)
    return 0
}
''', 'init\nmain\n14329\n7\n2048\n')

    def test_diamond_imports_share_one_table_and_cleanup(self):
        (self.directory / 'table.min').write_text('''public constant TABLE: List<Text> = make()
function make(): List<Text> { print("table init"); return ["a" + "!", "b" + "!"] }
public function first(): Text { return TABLE[0] }
''')
        for name in ('left', 'right'):
            (self.directory / f'{name}.min').write_text('''use "./table.min" as table
public function value(): Text { return table.first() }
''')
        self.executes('''use "./left.min" as left
use "./right.min" as right
print(left.value())
print(right.value())
''', 'table init\na!\na!\n')

    def test_literal_tables_records_bytes_and_scalar_dependencies(self):
        self.executes('''record Table { values: List<Integer>; title: Text }
constant ROW: Table = Table { values: [1, 2, 3]; title: "row" + "!" }
constant DATA: Bytes = Bytes("abc")
constant ANSWER: Integer = BASE + ROW.values[1]
constant BASE: Integer = 40 + 0
constant FLAGS: List<Boolean> = [true, false]
constant EMPTY: List<Integer> = []
let first = ROW
let second = ROW
print(first.title)
print(second.values[2])
print(DATA.length)
print(ANSWER)
print(FLAGS[0])
print(EMPTY.length)
''', 'row!\n3\n3\n42\ntrue\n0\n')

    def test_imported_record_annotation_and_constant_shadowing(self):
        (self.directory / 'config.min').write_text('''public record Table { values: List<Integer> }
public constant DATA: Table = Table { values: [7, 9] }
public function local(DATA: Integer): Integer { return DATA }
''')
        self.executes('''use "./config.min" as config
constant LOCAL: Integer = 40 + 2
function shadow(LOCAL: Integer): Integer { return LOCAL }
print(config.DATA.values[1])
print(config.local(3))
print(shadow(4))
print(LOCAL)
''', '9\n3\n4\n42\n')

    def test_recursive_initializer_reports_cycle(self):
        self.executes('''constant FIRST: Integer = second()
constant SECOND: Integer = first()
function first(): Integer { return FIRST }
function second(): Integer { return SECOND }
print(FIRST)
''', '', status=1, stderr='Minyar stopped: module constant initialization is recursive.\n')

    def test_unused_annotated_initializer_and_main_return_paths(self):
        for body in ('return 0', 'if argumentCount() == 0 { return 0 }; return 1'):
            with self.subTest(body=body):
                self.executes('''constant TABLE: List<Text> = make()
function make(): List<Text> { print("unused init"); return ["value" + "!"] }
function main(): Integer { ''' + body + ''' }
''', 'unused init\n')

    def test_managed_constant_marks_parallel_effect(self):
        self.rejects('''constant TABLE: List<Integer> = [1, 2]
parallel function read(index: Integer): Integer { return TABLE[index] }
''', "parallel function 'read' may use only Integer, Float, Boolean and Character values")

    def test_complex_initializer_needs_annotation_and_correct_type(self):
        self.rejects('constant TABLE = [1, 2]\n', 'a nonliteral constant needs a type annotation')
        self.rejects('constant TABLE: List<Integer> = ["wrong"]\n', 'all values in a List literal must have the same type')
        self.rejects('constant TABLE: List<Integer> = 1\n', "the value for constant 'TABLE' is Integer, not List<Integer>")
        self.rejects('constant TABLE: List<Integer> = value()\nfunction value(): Integer { return 1 }\n', "the initializer for constant 'TABLE' has the wrong type")
        self.rejects('constant EMPTY: Nothing = 1\n', 'Nothing cannot be used as a value type')


if __name__ == '__main__': unittest.main(verbosity=2)
