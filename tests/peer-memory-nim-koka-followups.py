#!/usr/bin/env python3
"""Original focused ownership adaptations, validated at O0/O2.

These are semantic subsets of pinned upstream cases, not upstream suite ports.
Exact peer layout/IR and sanitizer validation are separate obligations.
"""
import unittest
from regressions import CompilerTestCase


class PeerMemoryFollowups(CompilerTestCase):
    def test_nim_early_return_after_duplicate_owner_insertion(self):
        # topt_wasmoved_destroy_pairs:tfor. Return containers to observe owners;
        # do not assert Nim's wasMoved/destroy IR or seq copy-on-write semantics.
        self.executes('''record Transfer { left: List<List<Text>>; right: List<List<Text>> }
function build(stop: Integer, chooseLeft: Boolean): Transfer {
    let left: List<List<Text>> = []
    let right: List<List<Text>> = []
    let value = ["owned" + "!"]
    let index = 0
    while index < 4 {
        if index == stop { return Transfer { left: left; right: right } }
        left.add(value)
        index = index + 1
    }
    if chooseLeft { left.add(value) } else { right.add(value) }
    return Transfer { left: left; right: right }
}
let early = build(2, false)
print(early.left.length)
print(early.right.length)
print(early.left[0][0])
print(early.left[1][0])
let left = build(-1, true)
print(left.left.length)
print(left.right.length)
print(left.left[4][0])
let right = build(-1, false)
print(right.left.length)
print(right.right.length)
print(right.right[0][0])
let saved = early.left[0]
early = Transfer { left: []; right: [] }
left = Transfer { left: []; right: [] }
right = Transfer { left: []; right: [] }
print(saved[0])
''', '2\n0\nowned!\nowned!\n5\n0\nowned!\n4\n1\nowned!\nowned!\n')

    def test_koka_projected_child_and_whole_parent_survive_transfer(self):
        # parc20 Cons(head,xs). A Result holds a projected managed child and
        # original parent; does not claim integer boxing/native Cons reuse.
        self.executes('''record Payload { text: Text }
record Result { selected: List<Payload>; original: List<Payload> }
function prepend(values: List<Payload>): Result {
    if values.length == 0 { return Result { selected: []; original: [] } }
    return Result { selected: [values[0]]; original: values }
}
let result = prepend([Payload { text: "first" + "!" }, Payload { text: "second" + "!" }])
print(result.selected[0].text)
print(result.original[0].text)
let saved = result.selected[0]
let parent = result.original
result = prepend([])
parent[0] = Payload { text: "changed" + "!" }
print(saved.text)
print(parent[0].text)
print(parent[1].text)
print(result.selected.length)
print(result.original.length)
''', 'first!\nfirst!\nfirst!\nchanged!\nsecond!\n0\n0\n')

    def test_koka_managed_separator_and_join_accumulator(self):
        # inline4 joinsepx/join-acc. Explicit loop replaces Cons recursion and
        # captured separator; retain same empty/singleton/multi value contract.
        self.executes('''function join(values: List<Text>, separator: Text): Text {
    if values.length == 0 { return "" }
    let result = values[0]
    let index = 1
    while index < values.length {
        result = result + separator + values[index]
        index = index + 1
    }
    return result
}
print("[" + join([], "empty" + "!") + "]")
print(join(["solo" + "!"], "unused" + "!"))
let separator = "<" + ">"
let values = ["alpha" + "!", "beta" + "!", "gamma" + "!"]
let result = join(values, separator)
print(separator)
print(values[0])
values = []
separator = "replacement" + "!"
print(result)
let index = 0
while index < 40 {
    result = join(["left" + Text(index), "right" + Text(index)], ":" + "!")
    index = index + 1
}
print(result)
''', '[]\nsolo!\n<>\nalpha!\nalpha!<>beta!<>gamma!\nleft39:!right39\n')


if __name__ == '__main__':
    unittest.main()
