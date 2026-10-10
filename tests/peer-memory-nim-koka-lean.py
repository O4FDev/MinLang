#!/usr/bin/env python3
"""Original ownership-shape adaptations of pinned Nim/Koka/Lean regressions.

Source-unit dispositions and semantic differences are recorded in
research/2026-10-memory/peer-nim-koka-lean.json. No upstream source is vendored
here. Run before any implementation change; initially passing cases are coverage
additions, not fabricated red-green fixes. CompilerTestCase checks O0 and O2.
"""
import unittest
from regressions import CompilerTestCase


class PeerMemorySemantics(CompilerTestCase):
    def test_nim_effectful_assignment_indices_keep_order_and_old_alias(self):
        # tmovebug caseNotAConstant; no custom copy/destructor timing mapped.
        self.executes('''record Item { text: Text }
function next(state: List<Integer>): Integer {
    let result = state[0]
    print(result)
    state[0] = result + 1
    return result
}
let items = [Item { text: "a" + "!" }, Item { text: "b" + "!" }, Item { text: "c" + "!" }]
let old = items[0]
let state = [0]
items[next(state)] = items[next(state)]
print(items[0].text)
print(items[1].text)
print(items[2].text)
print(old.text)
''', '0\n1\nb!\nb!\nc!\na!\n')

    def test_nim_saved_scope_survives_owner_replacement(self):
        # topt_no_cursor mergeShadowScope: saved old owner must survive close.
        self.executes('''record Scope { parents: List<Scope>; symbols: List<Text> }
record Context { current: Scope }
function merge(context: Context) {
    let saved = context.current
    context.current = context.current.parents[0]
    for symbol in saved.symbols { context.current.symbols.add(symbol) }
}
function make(): Context {
    let parent = Scope { parents: []; symbols: ["parent" + "!"] }
    let child = Scope { parents: [parent]; symbols: ["a" + "!", "b" + "!"] }
    return Context { current: child }
}
let context = make()
merge(context)
print(context.current.symbols.length)
print(context.current.symbols[0])
print(context.current.symbols[1])
print(context.current.symbols[2])
''', '3\nparent!\na!\nb!\n')

    def test_nim_record_constructor_keeps_an_earlier_projection(self):
        # tmovebug parse/parseOD: one local supplies multiple constructor fields.
        # Extend the later read with mutation to expose lifetime protection.
        self.executes('''record Box { text: Text }
record Snapshot { text: Text; words: List<Text> }
function later(boxes: List<Box>): List<Text> {
    let saved = boxes[0].text
    boxes[0] = Box { text: "changed" + "!" }
    return [saved, boxes[0].text]
}
function capture(): Snapshot {
    let boxes = [Box { text: "original" + "!" }]
    return Snapshot { text: boxes[0].text; words: later(boxes) }
}
let snapshot = capture()
print(snapshot.text)
print(snapshot.words[0])
print(snapshot.words[1])
''', 'original!\noriginal!\nchanged!\n')

    def test_nim_conditional_saved_projection_survives_later_rows(self):
        # topt_no_cursor extractConfig: conditional borrow spans loop iterations.
        self.executes('''let saved = "initial" + "!"
let rows: List<Text> = []
let index = 0
while index < 300 {
    rows = ["row" + Text(index), "payload" + Text(index)]
    if index % 7 == 0 { saved = rows[1] }
    let observed = rows[1]
    rows = []
    if index == 299 { print(saved); print(observed) }
    index = index + 1
}
print(saved)
''', 'payload294\npayload299\npayload294\n')

    def test_nim_returned_member_survives_same_slot_overwrite(self):
        # tarc_orc #21974 pop: result protected before assignment to source slot.
        self.executes('''record Item { text: Text }
function removeFirst(items: List<Item>, position: Integer): Item {
    let result = items[0]
    items[0] = items[position]
    return result
}
let items = [Item { text: "first" + "!" }, Item { text: "last" + "!" }]
let original = removeFirst(items, 1)
let same = removeFirst(items, 0)
items = []
print(original.text)
print(same.text)
''', 'first!\nlast!\n')

    def test_nim_part_to_whole_assignment_uses_one_dynamic_index(self):
        # tmovebug partToWholeSeqRTIndex; custom hook timing is not mapped.
        self.executes('''record Tree { text: Text; children: List<Tree> }
function position(state: List<Integer>): Integer {
    state[0] = state[0] + 1
    return 0
}
let root = Tree { text: "leaf" + "!"; children: [] }
let index = 0
while index < 150 {
    root = Tree { text: "parent" + Text(index); children: [root] }
    index = index + 1
}
let oldRoot = root
let state = [0]
index = 0
while index < 150 {
    root = root.children[position(state)]
    index = index + 1
}
print(root.text)
print(oldRoot.text)
print(state[0])
''', 'leaf!\nparent149\n150\n')

    def test_koka_nested_selection_keeps_only_the_selected_child(self):
        # parc18: both nonempty selects right head, other arms return an input.
        self.executes('''record Payload { text: Text }
function select(left: List<Payload>, right: List<Payload>): List<Payload> {
    if left.length > 0 {
        if right.length > 0 { return [right[0]] }
        return left
    }
    return right
}
let left = [Payload { text: "left" + "!" }]
let right = [Payload { text: "right" + "!" }]
let both = select(left, right)
let onlyLeft = select(left, [])
let onlyRight = select([], right)
left = []
right = []
print(both[0].text)
print(onlyLeft[0].text)
print(onlyRight[0].text)
print(select([], []).length)
''', 'right!\nleft!\nright!\n0\n')

    def test_koka_record_rotation_preserves_shared_input_lists(self):
        # parc23 rotate: explicit fresh tails replace immutable Cons decomposition.
        self.executes('''record Pair { remaining: List<Text>; accumulated: List<Text> }
function rotate(pair: Pair): Pair {
    if pair.remaining.length == 0 { return Pair { remaining: []; accumulated: [] } }
    let tail: List<Text> = []
    let index = 1
    while index < pair.remaining.length {
        tail.add(pair.remaining[index])
        index = index + 1
    }
    let accumulated: List<Text> = [pair.remaining[0]]
    index = 0
    while index < pair.accumulated.length {
        accumulated.add(pair.accumulated[index])
        index = index + 1
    }
    return Pair { remaining: accumulated; accumulated: tail }
}
let remaining = ["a" + "!", "b" + "!", "c" + "!"]
let accumulated = ["saved" + "!"]
let original = Pair { remaining: remaining; accumulated: accumulated }
let rotated = rotate(original)
let empty = rotate(Pair { remaining: []; accumulated: accumulated })
remaining = []
accumulated = []
print(rotated.remaining[0])
print(rotated.remaining[1])
print(rotated.accumulated[0])
print(rotated.accumulated[1])
print(original.remaining.length)
print(original.accumulated[0])
print(empty.remaining.length)
print(empty.accumulated.length)
''', 'a!\nsaved!\nb!\nc!\n3\nsaved!\n0\n0\n')

    def test_lean_join_argument_survives_returned_pair_and_short_circuit(self):
        # borrowBug: Nat is immediate/tagged in some cases, so use managed Payload
        # for the ownership shape; no claim about Lean's exact RC golden output.
        self.executes('''record Payload { value: Integer; text: Text }
record Pair { first: Payload; second: Payload }
function pair(value: Payload): Pair { return Pair { first: value; second: value } }
function predicate(value: Payload): Boolean {
    print(value.text)
    return value.value > 10
}
function joined(value: Payload): Boolean {
    return predicate(value) || predicate(value)
}
function choose(flag: Boolean, left: Payload, right: Payload): Boolean {
    if flag { let temporary = pair(right); return joined(temporary.first) }
    let temporary = pair(left)
    return joined(temporary.first)
}
let left = Payload { value: 1; text: "left" + "!" }
let right = Payload { value: 11; text: "right" + "!" }
print(choose(true, left, right))
print(choose(false, left, right))
print(left.text)
print(right.text)
''', 'right!\ntrue\nleft!\nleft!\nfalse\nleft!\nright!\n')

    def test_lean_reuse_regression_shared_recursive_operands(self):
        # reusebug: tagged records encode the tested Expr constructors. This
        # checks output/sharing, without claiming identical ADT layout or reuse.
        self.executes('''record Expr { tag: Integer; number: Integer; text: Text; children: List<Expr> }
function value(number: Integer): Expr {
    return Expr { tag: 0; number: number; text: ""; children: [] }
}
function variable(text: Text): Expr {
    return Expr { tag: 1; number: 0; text: text; children: [] }
}
function add(left: Expr, right: Expr): Expr {
    if right.tag == 2 {
        if right.children[0].tag == 0 {
            return add(right.children[0], add(left, right.children[1]))
        }
    }
    return Expr { tag: 2; number: 0; text: ""; children: [left, right] }
}
function multiply(left: Expr, right: Expr): Expr {
    return Expr { tag: 3; number: 0; text: ""; children: [left, right] }
}
function show(expression: Expr): Text {
    if expression.tag == 0 { return Text(expression.number) }
    if expression.tag == 1 { return expression.text }
    if expression.tag == 2 {
        return "(" + show(expression.children[0]) + " + " + show(expression.children[1]) + ")"
    }
    return "(" + show(expression.children[0]) + " * " + show(expression.children[1]) + ")"
}
let x = variable("x" + "")
let original = add(multiply(value(2), x), x)
let expression = add(value(1), original)
print(show(expression))
print(show(original))
let reassociated = add(multiply(value(2), x), add(value(3), x))
print(show(reassociated))
print(show(x))
''', '(1 + ((2 * x) + x))\n((2 * x) + x)\n(3 + ((2 * x) + x))\nx\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
