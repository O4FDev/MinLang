#!/usr/bin/env python3
"""Independent composed semantic contracts from retained Go/Zig/Swift reviews.

Each method is one case. O0/O2 are validation dimensions, never extra cases.
The peer mapping describes only an ordinary runtime subset; Minyar sharing,
explicit construction and original compositions do not assert peer copy rules.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import unittest

from regressions import CLANG, COMPILER, LINK_FLAGS, RUNTIME, CompilerTestCase


def contract(category, peer, extent, closest, difference):
    def decorate(method):
        method.contract = dict(category=category, peer=peer, compatibility=extent,
                               closest_existing=closest, new_contract=difference)
        return method
    return decorate


class PeerBreadthSemantics(CompilerTestCase):
    @contract('control_scope', 'go-zig-round3:I1-I9/P8',
              'Ordinary if/else; initializer clauses become explicit helper scope.',
              'scalar-record-storage:test_shadowing_and_conditional_scopes',
              'One nine-branch count sequence and explicit initializer/body/outer shadow levels.')
    def test_go_branch_counts_and_three_binding_levels(self):
        self.executes('''function counts(): Integer {
let count = 0
if true { count += 1 }; print(count)
count = 0; if false { count += 1 }; print(count)
count = 0; let t = 1; if true { count += t }; print(count)
count = 0; if false { count += t }; print(count)
count = 0; if t == 1 { count += 1 }; print(count)
count = 0; if true { count += 1 } else { count -= 1 }; print(count)
count = 0; if false { count += 1 } else { count -= 1 }; print(count)
count = 0
if true { let t = 7; if false { count += t } else { let t = -1; count += t } }
print(count)
count = 0
if false { let t = 7; count += t } else { let t = -1; count += t }
print(count)
return t
}
print(counts())
''', '1\n0\n1\n0\n1\n1\n-1\n-1\n-1\n1\n')

    @contract('control_scope', 'go-zig-round3:I5-I9/P8',
              'Original effectful extension of ordinary Go if chain, no initializer syntax.',
              'peer-research-semantics:test_zig_short_circuit_skips_traps_and_keeps_all_live_effects',
              'Else-if condition effects stop at the selected arm and restart on the next call.')
    def test_else_if_conditions_stop_after_selected_arm(self):
        self.executes('''function probe(trace: List<Integer>, digit: Integer, selected: Integer): Boolean {
trace[0] = trace[0] * 10 + digit
return digit == selected
}
function choose(trace: List<Integer>, selected: Integer): Integer {
if probe(trace, 1, selected) { return 10 }
else if probe(trace, 2, selected) { return 20 }
else if probe(trace, 3, selected) { return 30 }
else { return 40 }
}
let trace = [0]
print(choose(trace, 2)); print(trace[0])
trace[0] = 0; print(choose(trace, 0)); print(trace[0])
trace[0] = 0; print(choose(trace, 1)); print(trace[0])
''', '20\n12\n40\n123\n10\n1\n')

    @contract('control_scope', 'go-zig-round3:P8;swift-round7:X2',
              'Original loop-condition/record-return composition using ordinary Boolean conditions.',
              'peer-research-reachability:test_observable_effects_before_return_or_break_are_preserved',
              'Returned condition records distinguish condition reevaluation after continue from break.')
    def test_condition_record_rechecks_after_continue_but_not_break(self):
        self.executes('''record Gate { open: Boolean; visit: Integer }
function gate(state: List<Integer>): Gate {
state[0] += 1
return Gate { visit: state[0]; open: state[0] < 5 }
}
let state = [0]
let trace = 0
while gate(state).open {
if state[0] == 1 { continue }
trace = trace * 10 + state[0]
if state[0] == 3 { break }
}
print(state[0]); print(trace)
while gate(state).open { trace = trace * 10 + state[0] }
print(state[0]); print(trace)
''', '3\n23\n5\n234\n')

    @contract('control_scope', 'swift-round7:X1-X2;go-zig-round3:P5',
              'Ordinary range iteration; original endpoint-call scheduling, no Swift slice representation.',
              'memory-research-peer-projections:test_effectful_iterables_evaluate_once_and_retain_body_storage',
              'Nested range bounds run left-to-right once per loop entry, including an empty range.')
    def test_nested_range_endpoint_effects_are_per_entry(self):
        self.executes('''function bound(trace: List<Integer>, digit: Integer, value: Integer): Integer {
trace[0] = trace[0] * 10 + digit
return value
}
let trace = [0]
let visits = 0
for outer in bound(trace, 1, 0)..bound(trace, 2, 2) {
for inner in bound(trace, 3, outer)..bound(trace, 4, 2) { visits += 1 }
}
for empty in bound(trace, 5, 3)..bound(trace, 6, 3) { visits += 100 }
print(trace[0]); print(visits)
''', '12343456\n3\n')

    @contract('control_scope', 'go-zig-round3:I8-I9/P8;Z58/P7',
              'Explicit managed shadow and construction; Go short declarations and Zig splat excluded.',
              'compact-ownership:test_shadowing_scope_cleanup_and_escaping_alias',
              'Per-iteration same-name initializer reads outer record and escapes before continue.')
    def test_loop_shadow_initializer_escapes_before_continue(self):
        self.executes('''record Cell { value: Integer }
function collect(): List<Cell> {
let cell = Cell { value: 10 }
let saved: List<Cell> = []
for index in 0..3 {
let cell = Cell { value: cell.value + index }
saved.add(cell)
if index == 1 { continue }
cell.value += 100
}
print(cell.value)
return saved
}
let saved = collect()
for cell in saved { print(cell.value) }
''', '10\n110\n11\n112\n')

    @contract('evaluation_effects', 'go-zig-round3:Z39,Z43/P5',
              'Unused nested Lists and Boolean effects; no Zig result-location or comptime claim.',
              'memory-research-peer-projections:test_unused_literal_effects_and_ordered_shared_state',
              'Unused nested Boolean literal keeps depth-first effects and skips short-circuited elements.')
    def test_unused_nested_boolean_literals_keep_effect_schedule(self):
        self.executes('''function mark(trace: List<Integer>, digit: Integer, answer: Boolean): Boolean {
trace[0] = trace[0] * 10 + digit
return answer
}
let trace = [0]
let unused = [[mark(trace, 1, true), false && mark(trace, 9, true)],
[mark(trace, 2, false) || mark(trace, 3, true)],
[true || mark(trace, 8, false), mark(trace, 4, false)]]
print(trace[0])
''', '1234\n')

    @contract('evaluation_effects', 'go-zig-round3:Z43/P5;swift-round7:S4',
              'Original nested constructor effects; explicit named fields, no Swift value-copy rule.',
              'scalar-record-storage:test_field_initializer_order_and_side_effects',
              'Reordered outer fields interleave nested literal and record initialization depth-first.')
    def test_nested_constructor_effects_follow_source_depth(self):
        self.executes('''record Inner { first: Integer; second: Integer }
record Outer { inner: Inner; numbers: List<Integer>; tail: Integer }
function mark(trace: List<Integer>, digit: Integer): Integer {
trace[0] = trace[0] * 10 + digit
return digit * 10
}
let trace = [0]
let value = Outer { tail: mark(trace, 1);
numbers: [mark(trace, 2), mark(trace, 3)];
inner: Inner { second: mark(trace, 4); first: mark(trace, 5) } }
print(trace[0]); print(value.inner.first); print(value.inner.second)
print(value.numbers[0]); print(value.numbers[1]); print(value.tail)
''', '12345\n50\n40\n20\n30\n10\n')

    @contract('evaluation_effects', 'go-zig-round3:Z21,Z35/P1',
              'Shared initialized records; original three-argument replacement schedule.',
              'readonly-parameters:test_caller_protection_survives_later_argument_mutation',
              'Same call sees old record argument, replacement result, then new field scalar in that order.')
    def test_three_arguments_capture_old_replacement_and_new_scalar(self):
        self.executes('''record Cell { value: Integer; label: Text }
function replace(cells: List<Cell>): Cell {
cells[0] = Cell { label: "new" + "!"; value: 9 }
return Cell { value: 5; label: "middle" + "!" }
}
function inspect(before: Cell, middle: Cell, after: Integer) {
print(before.value); print(before.label); print(middle.value)
print(middle.label); print(after)
}
let cells = [Cell { value: 3; label: "old" + "!" }]
inspect(cells[0], replace(cells), cells[0].value)
print(cells[0].label)
''', '3\nold!\n5\nmiddle!\n9\nnew!\n')

    @contract('evaluation_effects', 'go-zig-round3:Z43/P5',
              'Original compound scalar write; no pointer result-location equivalence.',
              'adversarial:test_index_and_rhs_evaluation_order',
              'Compound indexed update captures value after index effects and before RHS mutation.')
    def test_compound_index_update_captures_between_effects(self):
        self.executes('''function index(values: List<Integer>, trace: List<Integer>): Integer {
trace[0] = trace[0] * 10 + 1
values[0] = 20
return 0
}
function right(values: List<Integer>, trace: List<Integer>): Integer {
trace[0] = trace[0] * 10 + 2
values[0] = 100
return 3
}
let values = [10]
let trace = [0]
values[index(values, trace)] += right(values, trace)
print(trace[0]); print(values[0])
''', '12\n23\n')

    @contract('evaluation_effects', 'swift-round7:X1-X2;go-zig-round3:P1',
              'Ordinary iteration of a shared List projected from a record.',
              'memory-research-peer-projections:test_effectful_iterables_evaluate_once_and_retain_body_storage',
              'Replacing iterable record field keeps original loop storage while later element mutation stays visible.')
    def test_loop_field_replacement_keeps_storage_and_live_element_updates(self):
        self.executes('''record Rows { values: List<Integer> }
let owner = Rows { values: [1, 2, 3] }
let original = owner.values
let trace = 0
for value in owner.values {
trace = trace * 10 + value
if value == 1 { owner.values = [8, 9]; original[1] = 7 }
}
print(trace); print(owner.values[0]); print(original[1])
''', '173\n8\n7\n')

    @contract('record_return_layout', 'swift-round7:S4/P1',
              'Original mixed wide record; explicit fields/ordinary recursion, no Swift struct ABI/copy claim.',
              'memory-research-peer-projections:test_wide_returned_record_preserves_fields_effect_order_and_retained_alias',
              'Eight mixed-kind slots survive recursive return and reference-field overwrite with old alias retained.')
    def test_mixed_wide_record_survives_recursive_return_and_field_write(self):
        self.executes('''record Mixed { count: Integer; flag: Boolean; letter: Character; ratio: Float;
text: Text; numbers: List<Integer>; bytes: Bytes; tail: Integer }
function make(depth: Integer): Mixed {
if depth > 0 { return make(depth - 1) }
let bytes = Bytes(1); bytes[0] = 42
return Mixed { tail: -7; bytes: bytes; numbers: [13, 17]; text: "wide" + "!";
ratio: 1.5; letter: 'β'; flag: true; count: 9 }
}
let value = make(4)
let numbers = value.numbers
value.numbers = [99]
print(value.count); print(value.flag); print(Integer(value.letter)); print(value.ratio)
print(value.text); print(numbers[1]); print(value.numbers[0]); print(value.bytes[0]); print(value.tail)
''', '9\ntrue\n946\n1.5\nwide!\n17\n99\n42\n-7\n')

    @contract('record_return_layout', 'swift-round7:S1-S3,T1-T4',
              'Named interval helpers replace operators/tuples; mutation uses Minyar shared record semantics.',
              'memory-research-peer-projections:test_integer_extrema_are_scalar_results_across_shared_mutation',
              'Interval negate/add/subtract composition creates independent endpoint records before input mutation.')
    def test_interval_algebra_returns_independent_endpoint_records(self):
        self.executes('''record Interval { low: Integer; high: Integer }
function negative(value: Interval): Interval { return Interval { high: -value.low; low: -value.high } }
function sum(a: Interval, b: Interval): Interval { return Interval { high: a.high + b.high; low: a.low + b.low } }
function difference(a: Interval, b: Interval): Interval { return Interval { low: a.low - b.high; high: a.high - b.low } }
let a = Interval { high: 2; low: 1 }
let b = Interval { low: 3; high: 4 }
let negated = negative(a)
let added = sum(a, b)
let subtracted = difference(b, a)
let composed = sum(added, negative(b))
a.low = 100; b.high = 200
print(negated.low); print(negated.high); print(added.low); print(added.high)
print(subtracted.low); print(subtracted.high); print(composed.low); print(composed.high)
''', '-2\n-1\n4\n6\n1\n3\n0\n3\n')

    @contract('record_return_layout', 'swift-round7:S4;go-zig-round3:P8',
              'Original mixed record selected through early and fallthrough return paths.',
              'adversarial:test_shadowing_and_early_returns_through_nested_scopes',
              'Distinct mixed scalar/reference field kinds retain named mapping on both return paths.')
    def test_mixed_record_branch_returns_preserve_all_field_kinds(self):
        self.executes('''record Result { number: Integer; flag: Boolean; character: Character; fraction: Float; values: List<Integer> }
function choose(early: Boolean): Result {
if early { return Result { values: [7]; fraction: 0.5; character: 'A'; flag: true; number: -3 } }
let values = [11, 13]
return Result { flag: false; number: 9; values: values; character: 'β'; fraction: -1.5 }
}
function show(value: Result) {
print(value.number); print(value.flag); print(Integer(value.character)); print(value.fraction)
print(value.values.length); print(value.values[0])
}
show(choose(true)); show(choose(false))
''', '-3\ntrue\n65\n0.5\n1\n7\n9\nfalse\n946\n-1.5\n2\n11\n')

    @contract('record_return_layout', 'go-zig-round3:Z26,Z54/P3',
              'Ragged Lists of explicit records; fixed-array layout, default fields and comptime excluded.',
              'peer-research-semantics:test_swift_nested_array_construction_uses_distinct_rows',
              'Returned three-level ragged record topology includes an empty middle row and named field mapping.')
    def test_returned_ragged_record_topology_keeps_empty_rows(self):
        self.executes('''record Cell { number: Integer; tag: Boolean }
function tree(): List<List<List<Cell>>> {
return [[[Cell { tag: true; number: 1 }]],
[[], [Cell { number: 2; tag: false }, Cell { tag: true; number: 3 }]],
[[Cell { number: 4; tag: false }]]]
}
let tree = tree()
print(tree.length)
for group in tree {
print(group.length)
for row in group {
print(row.length)
for cell in row { print(cell.number); print(cell.tag) }
}
}
''', '3\n1\n1\n1\ntrue\n2\n0\n2\n2\nfalse\n3\ntrue\n1\n1\n4\nfalse\n')

    @contract('record_return_layout', 'go-zig-round3:Z58/P7',
              'Fresh explicit constructors versus repeated same record; no splat/copy or record equality.',
              'peer-research-semantics:test_swift_nested_array_construction_uses_distinct_rows',
              'Record filling distinguishes each fresh cell from deliberately shared cells after field mutation.')
    def test_fresh_and_shared_record_fill_have_distinct_mutation_results(self):
        self.executes('''record Cell { value: Integer }
let fresh: List<Cell> = []
let shared: List<Cell> = []
let cell = Cell { value: 10 }
for index in 0..4 { fresh.add(Cell { value: 10 }); shared.add(cell) }
fresh[1].value = 20
shared[1].value = 30
for item in fresh { print(item.value) }
for item in shared { print(item.value) }
print(cell.value)
''', '10\n20\n10\n10\n30\n30\n30\n30\n30\n')

    @contract('alias_lifetime', 'go-zig-round3:Z35/P1;Z51/P6',
              'Original record field rebinding; sharing intentionally differs from Zig implicit copy.',
              'memory-research-peer-projections:test_shared_row_and_explicit_snapshot_survive_outer_replacement',
              'Two record fields initially share one List then diverge through one field replacement and helper identity.')
    def test_shared_record_fields_diverge_on_one_field_replacement(self):
        self.executes('''record Pair { left: List<Integer>; right: List<Integer> }
function echo(value: Pair): Pair { return value }
let row = [1, 2]
let owner = Pair { left: row; right: row }
let alias = echo(owner)
let old = owner.left
owner.left = [7, 8]
alias.right[0] = 3
row = []; owner = Pair { left: []; right: [] }
print(alias.left[0]); print(alias.right[0]); print(old[0])
alias.left[1] = 9
print(old[1]); print(alias.left[1])
''', '7\n3\n3\n2\n9\n')

    @contract('alias_lifetime', 'go-zig-round3:Z21,Z35/P1;swift-round7:S4',
              'Original borrowed nested record return after last parent replacement inside the helper.',
              'adversarial:test_borrowed_parameters_can_be_reassigned_and_escape',
              'A loop-selected nested record survives parent replacement before return, preserving a mutable nested List.')
    def test_borrowed_nested_record_returns_after_parent_is_replaced(self):
        self.executes('''record Leaf { numbers: List<Integer>; tag: Integer }
record Parent { leaf: Leaf }
function detach(parents: List<Parent>, wanted: Integer): Leaf {
for index in 0..parents.length {
if index == wanted {
let kept = parents[index].leaf
parents[index] = Parent { leaf: Leaf { tag: 9; numbers: [90] } }
return kept
}
}
return Leaf { tag: -1; numbers: [] }
}
let parents = [Parent { leaf: Leaf { numbers: [4, 5]; tag: 2 } }]
let kept = detach(parents, 0)
parents = []
kept.numbers[1] += 10
print(kept.tag); print(kept.numbers[0]); print(kept.numbers[1])
''', '2\n4\n15\n')

    @contract('alias_lifetime', 'swift-round7:X1;go-zig-round3:Z21/P1',
              'Managed iteration binding differs from scalar snapshots; original overwrite/continue/break composition.',
              'memory-research-peer-projections:test_scalar_loop_capture_survives_mutation_continue_and_break',
              'Managed record iteration retains old element across overwrite, parent rebinding and loop transfers.')
    def test_managed_loop_binding_survives_slot_overwrite_and_transfers(self):
        self.executes('''record Cell { value: Integer }
let source = [Cell { value: 1 }, Cell { value: 2 }, Cell { value: 3 }]
let original = source
let kept: List<Cell> = []
let position = 0
for cell in source {
kept.add(cell)
original[position] = Cell { value: 90 + position }
cell.value += 10
source = []
position += 1
if position == 1 { continue }
if position == 2 { break }
}
original = []
print(position); print(kept.length)
for cell in kept { print(cell.value) }
''', '2\n2\n11\n12\n')

    @contract('alias_lifetime', 'go-zig-round3:Z26/P3;Z51/P6',
              'Explicit two-level scalar snapshot versus shared nested List aliases, no implicit deep copy.',
              'memory-research-peer-projections:test_shared_row_and_explicit_snapshot_survive_outer_replacement',
              'Deep row snapshot remains independent while sibling shared paths split on inner replacement.')
    def test_deep_snapshot_and_sibling_aliases_split_at_inner_replacement(self):
        self.executes('''let row = [1, 2]
let branch = [row, row]
let root = [branch, branch]
let kept = root[1]
let snapshot: List<List<Integer>> = []
for source in kept {
let copied: List<Integer> = []
for value in source { copied.add(value) }
snapshot.add(copied)
}
root[0][0] = [7, 8]
row[1] = 9
root = []; branch = []; row = []
print(kept[0][0]); print(kept[1][1])
print(snapshot[0][0]); print(snapshot[0][1]); print(snapshot[1][1])
snapshot[0][0] = 50
print(snapshot[1][0])
''', '7\n9\n1\n2\n2\n1\n')

    @contract('alias_lifetime', 'go-zig-round3:P1,P6',
              'Original Bytes field/slice extension of record replacement and explicit-copy controls; no upstream binary format claim.',
              'memory-research-peer-projections:test_shared_bytes_and_independent_slice_survive_replacement',
              'Returned Bytes slice is independent of a shared record field after typed numeric writes and parent rebinding.')
    def test_record_bytes_slice_keeps_numeric_snapshot_after_field_rebind(self):
        self.executes('''record Packet { bytes: Bytes; version: Integer }
function snapshot(packet: Packet): Bytes { return packet.bytes.slice(0, 8) }
let bytes = Bytes(); bytes.addInt64(72623859790382856)
let packet = Packet { version: 1; bytes: bytes }
let alias = packet
let copied = snapshot(packet)
bytes.setInt64(0, -2)
alias.bytes = Bytes(); alias.bytes.addInt64(99)
packet = Packet { bytes: Bytes(); version: 2 }; bytes = Bytes()
print(copied.getInt64(0)); print(alias.bytes.getInt64(0)); print(alias.version)
print(copied[0]); print(copied[7])
''', '72623859790382856\n99\n1\n8\n1\n')

    @contract('numeric_composition', 'values-round9:P1/G1-G3,L4,W1',
              'Original rational normalization with representable abs inputs; no std::gcd API/constexpr/unsigned behavior.',
              'memory-research-peer-projections:test_euclidean_remainder_composes_at_signed_boundaries',
              'Euclid feeds returned numerator/denominator normalization, sign movement and zero canonicalization.')
    def test_rational_normalization_moves_sign_and_canonicalizes_zero(self):
        self.executes('''record Rational { numerator: Integer; denominator: Integer }
function gcd(a: Integer, b: Integer): Integer {
a = abs(a); b = abs(b)
while b != 0 { let next = a % b; a = b; b = next }
return a
}
function normalize(n: Integer, d: Integer): Rational {
let factor = gcd(n, d)
n = n / factor; d = d / factor
if d < 0 { n = -n; d = -d }
return Rational { denominator: d; numerator: n }
}
function show(value: Rational) { print(value.numerator); print(value.denominator) }
show(normalize(42, -56)); show(normalize(-42, -56)); show(normalize(0, -17))
show(normalize(9223372036854775806, 4611686018427387903))
''', '-3\n4\n3\n4\n0\n1\n2\n1\n')

    @contract('numeric_composition', 'values-round9:P1;go-zig-round3:Z26/P3',
              'Original Euclidean fold over ordinary ragged Lists; peer gcd API excluded.',
              'memory-research-peer-projections:test_euclidean_remainder_composes_at_signed_boundaries',
              'Repeated gcd composition across empty, zero and signed rows yields independent returned records after source mutation.')
    def test_ragged_gcd_fold_returns_scalars_independent_of_rows(self):
        self.executes('''record Fold { value: Integer; count: Integer }
function gcd(a: Integer, b: Integer): Integer {
a = abs(a); b = abs(b)
while b != 0 { let next = a % b; a = b; b = next }
return a
}
function fold(values: List<Integer>): Fold {
let value = 0
for next in values { value = gcd(value, next) }
return Fold { count: values.length; value: value }
}
let rows: List<List<Integer>> = [[], [0, -18, 30, 42], [0, 0], [35, 64]]
let results: List<Fold> = []
for row in rows { results.add(fold(row)) }
rows[1][1] = 999; rows = []
for result in results { print(result.value); print(result.count) }
''', '0\n0\n6\n4\n0\n2\n1\n2\n')

    @contract('numeric_composition', 'values-round9:P2;go-zig-round3:Z43/P5',
              'Original extrema record initializer with intervening shared mutation; no C++ reference identity.',
              'memory-research-peer-projections:test_integer_extrema_are_scalar_results_across_shared_mutation',
              'Min snapshot precedes mutation helper while max uses changed source in the same returned constructor.')
    def test_extrema_initializer_captures_before_and_after_mutation(self):
        self.executes('''record Limits { low: Integer; marker: Integer; high: Integer }
function change(values: List<Integer>): Integer { values[0] = 40; values[1] = 60; return 7 }
function inspect(values: List<Integer>): Limits {
return Limits { low: min(values[0], values[1]); marker: change(values); high: max(values[0], values[1]) }
}
let values = [-9, 2]
let result = inspect(values)
values = []
print(result.low); print(result.marker); print(result.high)
''', '-9\n7\n60\n')

    @contract('numeric_composition', 'values-round9:P1;go-zig-round3:P1',
              'Original quotient/remainder record snapshot and recomposition; no Go overflow-wrap minimum/-1 behavior.',
              'checked-arithmetic:test_boundary_values_and_signed_remainders',
              'Signed divmod returns a scalar record that recomposes the original operands after shared input overwrite.')
    def test_divmod_record_recomposes_saved_operands_after_input_overwrite(self):
        self.executes('''record Division { quotient: Integer; remainder: Integer; dividend: Integer; divisor: Integer }
function divide(values: List<Integer>): Division {
return Division { divisor: values[1]; remainder: values[0] % values[1];
dividend: values[0]; quotient: values[0] / values[1] }
}
let values = [-1234, 37]
let result = divide(values)
values[0] = 100; values[1] = 2; values = []
print(result.quotient); print(result.remainder)
print(result.quotient * result.divisor + result.remainder)
print(result.dividend)
''', '-33\n-13\n-1234\n-1234\n')

    @contract('numeric_composition', 'values-round9:D9-D10',
              'Representable Integer shifts followed by original binary packing; no Go unsigned width or overshift parity.',
              'checked-scalars:test_scalar_operations_match_independent_models',
              'Arithmetic right shift and checked left shift feed an eight-byte little-endian roundtrip across record return.')
    def test_signed_shift_results_pack_in_order_across_returned_bytes(self):
        self.executes('''record Encoded { bytes: Bytes; total: Integer }
function encode(value: Integer, count: Integer): Encoded {
let left = value << count
let right = value >> count
let bytes = Bytes(); bytes.addInt64(left); bytes.addInt64(right)
return Encoded { total: left + right; bytes: bytes }
}
let result = encode(-1234, 5)
print(result.bytes.length); print(result.bytes.getInt64(0)); print(result.bytes.getInt64(8))
print(result.total); print(result.bytes[0]); print(result.bytes[7]); print(result.bytes[8]); print(result.bytes[15])
''', '16\n-39488\n-39\n-39527\n192\n255\n217\n255\n')


PILOT = (
    'test_else_if_conditions_stop_after_selected_arm',
    'test_unused_nested_boolean_literals_keep_effect_schedule',
    'test_mixed_wide_record_survives_recursive_return_and_field_write',
    'test_managed_loop_binding_survives_slot_overwrite_and_transfers',
    'test_rational_normalization_moves_sign_and_canonicalizes_zero',
)


def inventory():
    return {name: dict(method.contract) for name, method in vars(PeerBreadthSemantics).items()
            if name.startswith('test_')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot', action='store_true', help='Five representative cases, O0/O2 each.')
    parser.add_argument('--list-cases', action='store_true', help='Static inventory; runs no compiler.')
    parser.add_argument('--run-record', type=Path, help='Concise case ledger with observed status and tool identities.')
    parser.add_argument('tests', nargs='*', help='Optional method names.')
    args = parser.parse_args()
    cases = inventory()
    if args.list_cases:
        print(json.dumps(cases, indent=2))
        sys.exit(0)
    names = list(PILOT) if args.pilot else args.tests or list(cases)
    for name in names:
        if name not in cases:
            parser.error('Unknown case: ' + name)
    optimization_overrides = [flag for flag in LINK_FLAGS
                              if re.fullmatch(r'-O(?:[0123szg]|fast)', flag)]
    if optimization_overrides:
        parser.error('O0/O2 coverage requires link flags without optimization overrides.')
    started = time.monotonic()
    suite = unittest.TestSuite(PeerBreadthSemantics(name) for name in names)
    class LedgerResult(unittest.TextTestResult):
        def addSuccess(self, test):
            super().addSuccess(test)
            cases[test._testMethodName]['observed_status'] = 'passed_O0_O2'
        def addFailure(self, test, error):
            super().addFailure(test, error)
            cases[test._testMethodName]['observed_status'] = 'failed'
        def addError(self, test, error):
            super().addError(test, error)
            cases[test._testMethodName]['observed_status'] = 'error'
        def addSubTest(self, test, subtest, error):
            super().addSubTest(test, subtest, error)
            if error is not None:
                cases[test._testMethodName]['observed_status'] = 'failed'
    result = unittest.TextTestRunner(verbosity=2, resultclass=LedgerResult).run(suite)
    if args.run_record:
        record = {
            'schema': 'minyar-breadth-semantic-progress-v1',
            'status': 'passed' if result.wasSuccessful() else 'failed',
            'command': [sys.executable, *sys.argv],
            'authored_cases': len(cases), 'selected_cases': len(names),
            'attempted_cases': result.testsRun,
            'executed_cases': sum(case.get('observed_status') == 'passed_O0_O2'
                                  for case in cases.values()),
            'elapsed_seconds': time.monotonic() - started,
            'passed_cases': sum(case.get('observed_status') == 'passed_O0_O2' for case in cases.values()),
            'categories': sorted({case['category'] for case in cases.values()}),
            'peers': ['Go', 'Zig', 'Swift', 'LLVM/libc++'],
            'validation_dimensions': ['O0', 'O2'],
            'clang': CLANG, 'link_flags': LINK_FLAGS,
            'retained_manifests': [
                'research/2026-10-memory/peer-readonly-go-zig-round3.json',
                'research/2026-10-memory/peer-readonly-swift-round7.json',
                'research/2026-10-memory/peer-readonly-values-round9.json',
            ],
            'coverage_only_unless_observed_contract_failure': True,
            'identities': {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                           for path in [Path(__file__), COMPILER, RUNTIME]},
            'cases': {name: {'observed_status': 'authored_unexecuted', **case}
                      for name, case in cases.items()},
        }
        args.run_record.write_text(json.dumps(record, indent=2) + '\n')
    sys.exit(not result.wasSuccessful())
