#!/usr/bin/env python3
"""Exercise collections together across constant getters and callback thunks."""
import unittest
from regressions import CompilerTestCase, ROOT
import callbacks


class CollectionConstants(CompilerTestCase):
    def test_constant_map_nested_lists_and_text_operations(self):
        self.executes('''constant TABLE: Map<Text, List<Integer>> = makeTable()
function makeTable(): Map<Text, List<Integer>> {
    print("init")
    let table = Map<Text, List<Integer>>()
    table["é"] = [3, 1, 2]
    return table
}
let alias = TABLE
let copy = TABLE["é"].sorted()
TABLE["é"].sort()
TABLE["é"][0] += 6
print(alias["é"][0])
print(copy[0])
let fields = "　é: +42 :🍊 ".trim().split(":")
let names = Map<Text, Integer>()
names[fields[0]] = Integer(fields[1])
print(names["é"])
print(fields[2].find("🍊"))
print(fields[0].startsWith("é"))
print(fields[2].endsWith("🍊"))
TABLE["é"].clear()
print(alias["é"].length)
TABLE.clear()
print(alias.length)
''', 'init\n7\n1\n42\n0\ntrue\ntrue\n0\n0\n')

    def test_imported_constant_map_receiver_writes(self):
        (self.directory / 'table.min').write_text('''public constant TABLE: Map<Integer, List<Text>> = make()
function make(): Map<Integer, List<Text>> {
    let table = Map<Integer, List<Text>>()
    table[1] = ["b" + "!", "a" + "!"]
    return table
}
''')
        self.executes('''use "./table.min" as first
use "./table.min" as second
first.TABLE[1].sort()
first.TABLE[1][0] = "changed" + "!"
print(second.TABLE[1][0])
let saved = second.TABLE[1]
first.TABLE.clear()
print(saved[1])
print(second.TABLE.length)
''', 'changed!\nb!\n0\n')


class MapComparator(CompilerTestCase):
    compiler_arguments = ('--library', str(ROOT / 'library'))
    compile = callbacks.Callbacks.compile
    executes = callbacks.Callbacks.executes

    def test_stable_comparator_over_negative_structural_slots(self):
        self.executes('''function make(rank: Integer, serial: Integer): Map<Integer, Integer> {
    let row = Map<Integer, Integer>()
    row[0] = rank
    row[1] = serial
    return row
}
let rows = [make(2, 0), make(1, 1), make(2, 2), make(1, 3)]
let compare = function(a: Map<Integer, Integer>, b: Map<Integer, Integer>): Integer {
    if a[0] < b[0] { return -1 }
    if a[0] > b[0] { return 1 }
    return 0
}
let copy = rows.sortedBy(compare)
rows.sortBy(compare)
for i in 0..rows.length {
    print(rows[i][1])
    print(copy[i][1])
}
copy.clear()
print(rows[0][1])
''', '1\n1\n3\n3\n0\n0\n2\n2\n1\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
