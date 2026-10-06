# Read-only Go/Zig peer semantics — round 2

Completed **32 authored comparison groups**: 12 Go scenarios across two complete selected files and 20 named Zig tests in one contiguous prefix. **18 runtime adaptations/projections are pending; 14 groups are incompatible as written.** Eight narrow original regressions are proposed. **Zero ports implemented; zero peer/local test executions.**

This is source-based semantic assessment, not inventory discovery, execution evidence, exhaustive peer coverage or a production defect finding. Every selected expectation and helper body was read. Upstream outcomes are inferred from the pinned assertions. Go expects silent successful main completion; Zig expectations apply only when its recorded backend skip guards permit execution. No upstream backend was run.

| Primary source | Actual semantic read extent | Groups |
| --- | --- | --- |
| [Go test/for.go](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/for.go) | Complete physical lines 1–76; assertequal and main | 8 |
| [Go test/simassign.go](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/simassign.go) | Complete physical lines 1–79; printit, testit, swap, main | 4 |
| [Zig test/behavior/array.zig](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig) | Physical lines 1–309; all 20 named tests and seven helper bodies in prefix | 20 |

Go is pinned to `56ebf80e57db9f61981fc0636fc6419dc6f68eda`; Zig to `3db960767d12b6214bcf43f1966a037c7a586a12`, from existing campaign manifests. The inspected ledger has no authored review for these three paths. Completed Rust expression/Swift statement selections were excluded. Central manifests and ledger are unchanged.

**Zig lines 310–1127 remain unreviewed.** Full-file retrieval into a temporary byte cache is distinct from semantic reading. Groups are one Go main scenario or one named Zig test including its helpers; assertions/helpers are not counted as extra groups or ports.

Exact source/license hashes and reviewed-prefix hashes are in [provenance](../../evidence/peer-readonly/go-zig-round2/provenance.json). The [structured review](peer-readonly-go-zig-round2.json) records every expectation line, helper range, backend skip guard, local reference and proposal. Physical raw-byte lines are authoritative; browser display normalization removed blank lines. Existing local coverage means inspected source fixtures only, not tests executed or validated.

The pinned [Go license](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/LICENSE) is BSD-3-Clause, SHA256 `911f8f5782931320f5b8d1160a76365b83aea6447ee6c04fa6d5591467db9dad`. The pinned [Zig license](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/LICENSE) is MIT, SHA256 `5c537d6853e005298a285d508cff9ac7192cea23576c840d485b2b586a7ff177`. Source bytes were hashed in a temporary cache; no upstream implementation code is embedded in these repository records.

## Findings

- **Loop bindings differ.** Go range assignment updates an existing outer index to 4. Minyar introduces a fresh binding, so an outer zero stays zero. Track the last index explicitly when desired. A Go continue/post-clause case maps safely to a Minyar range; a while translation must advance before its continue path.
- **Writable slices differ.** Zig writes through a slice into the backing array. Minyar Bytes.slice copies; List has no slice method. A proposed control expects source azaa after a slice-only write, then azya after a direct source write.
- **Parallel assignment and multi-result calls differ.** Minyar has one return value and single-target assignments. The Go permutation has a 4-cycle and a 5-cycle, so exact-order period 20; checksum 45 alone is insufficient. Explicit snapshots and one Pair record provide original controls without adding syntax.
- **Value checks do not establish representation compatibility.** Nested literal reads and ASCII order project to Lists/Bytes/Text. Fixed array copies, widths, comptime sizing, alignment and sentinels remain unsupported. Test fresh rows and intentionally shared rows separately. Nothing cannot be a stored void element.

## Authored dispositions

Pending runtime subset means a compatible runtime adaptation/projection is identified, with unsupported contracts excluded. It does not assert that the entire test is compatible or ported. Incompatible as written means a core contract differs or is absent; related proposals are original controls.

### Go

**G1 — [test/for.go:21–28](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/for.go#L21-L28) — main: unconditioned loop break. Pending runtime subset.**

Expected upstream: L28: i=6 after incrementing before testing the break threshold.

while true plus ordinary Integer assignment and break preserves this outcome. The failure helper panics only if comparison fails; panic reporting is not mapped.

Helpers read: assertequal L11–16, main L18–76.

Existing local source coverage: [tests/conformance/loops-and-assignment/program.min:45–51](../../tests/conformance/loops-and-assignment/program.min) — Increment before continue/break in while true; final 11, different threshold.

Original port/control: R1 proposed; none implemented/executed.

**G2 — [test/for.go:30–34](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/for.go#L30-L34) — main: init-condition-post. Pending runtime subset.**

Expected upstream: L34: sum=55 over inclusive values 0 through 10.

Use half-open range 0..11. Go initializer/post clauses and i++ lack exact syntax counterparts; here those clauses have no user-code effects.

Helpers read: assertequal L11–16, main L18–76.

Existing local source coverage: [tests/conformance/loops-and-assignment/program.min:9–15](../../tests/conformance/loops-and-assignment/program.min) — Related range sum with continue and break; total 18, different inputs.

Original port/control: R1 proposed; none implemented/executed.

**G3 — [test/for.go:36–41](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/for.go#L36-L41) — main: explicit body increment. Pending runtime subset.**

Expected upstream: L41: sum=55 over inclusive values 0 through 10.

Initialize an Integer and use while counter <= 10, accumulating then updating with += 1 exactly once each iteration.

Helpers read: assertequal L11–16, main L18–76.

Existing local source coverage: [tests/runtime/lists.min:1–17](../../tests/runtime/lists.min) — List indexed writes and explicit while counter/sum; different input and length.

Original port/control: R1 proposed; none implemented/executed.

**G4 — [test/for.go:43–47](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/for.go#L43-L47) — main: condition-only loop. Pending runtime subset.**

Expected upstream: L47: sum=108, the first multiple of 9 at least 100.

while sum < 100 maps the Boolean condition directly. The exact overshoot 108 is the oracle; sum >= 100 alone is weaker.

Helpers read: assertequal L11–16, main L18–76.

Existing local source coverage: [tests/conformance/loops-and-assignment/program.min:45–51](../../tests/conformance/loops-and-assignment/program.min) — Increment before continue/break in while true; final 11, different threshold.

Original port/control: R1 proposed; none implemented/executed.

**G5 — [test/for.go:49–56](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/for.go#L49-L56) — main: continue executes Go post update. Pending runtime subset.**

Expected upstream: L56: sum=25 from odd values 1,3,5,7,9.

Minyar range 0..11 preserves progress on continue. A while translation must increment before its continue path; putting the update only at body end hangs at zero.

Helpers read: assertequal L11–16, main L18–76.

Existing local source coverage: [tests/conformance/loops-and-assignment/program.min:9–15](../../tests/conformance/loops-and-assignment/program.min) — Related range sum with continue and break; total 18, different inputs. [tests/conformance/loops-and-assignment/program.min:45–51](../../tests/conformance/loops-and-assignment/program.min) — Increment before continue/break in while true; final 11, different threshold.

Original port/control: R1 proposed; none implemented/executed.

**G6 — [test/for.go:58–61](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/for.go#L58-L61) — main: range assignment updates outer index. Incompatible as written.**

Expected upstream: L61: outer i=4 after traversing five zero-size elements.

Go assigns a pre-existing i in this form. Minyar for i in 0..5 introduces a fresh binding, so outer i=0 stays zero. The Go zero-size inline struct and fixed-array representation has no documented Minyar counterpart.

Helpers read: assertequal L11–16, main L18–76.

Existing local source coverage: [tests/peer-research-swift-statements.py:24–28](../../tests/peer-research-swift-statements.py) — Loop-body name cannot escape; no outer-shadow assignment oracle. [tests/conformance/bindings-and-scope/program.min:1–7](../../tests/conformance/bindings-and-scope/program.min) — Scalar assignment and lexical shadowing; two separate outer/inner outputs.

Original port/control: R2 proposed; none implemented/executed.

**G7 — [test/for.go:63–68](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/for.go#L63-L68) — main: zero-size array clear retains outer index. Incompatible as written.**

Expected upstream: L68: outer i=4 despite assigning each zero-size array element.

Minyar has neither the fixed array of empty structs nor the existing-binding range form. A shadow/last-index control is useful but does not validate Go zero-size clear lowering.

Helpers read: assertequal L11–16, main L18–76.

Existing local source coverage: [tests/conformance/loops-and-assignment/program.min:37–43](../../tests/conformance/loops-and-assignment/program.min) — Construct zero-filled Integer List and mutate through nested record; original aliases observe it. [tests/peer-research-swift-statements.py:24–28](../../tests/peer-research-swift-statements.py) — Loop-body name cannot escape; no outer-shadow assignment oracle.

Original port/control: R2 proposed; none implemented/executed.

**G8 — [test/for.go:70–75](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/for.go#L70-L75) — main: integer array clear retains outer index. Incompatible as written.**

Expected upstream: L75: outer i=4 after clearing five integer elements.

Explicit indexed List clearing is supported; a fresh Minyar loop binding cannot preserve this outer assignment. A last variable must be assigned explicitly. Check all cleared elements separately in the original proposal.

Helpers read: assertequal L11–16, main L18–76.

Existing local source coverage: [tests/conformance/loops-and-assignment/program.min:37–43](../../tests/conformance/loops-and-assignment/program.min) — Construct zero-filled Integer List and mutate through nested record; original aliases observe it.

Original port/control: R2 proposed; none implemented/executed.

**S1 — [test/simassign.go:40–52](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/simassign.go#L40-L52) — main: initialization and testit(false). Pending runtime subset.**

Expected upstream: L18–32: testit requires sum=45; when permuteok=false it also requires exact ordered values 1 through 9; L50–51: initial testit(false) is true; no panic.

Sequential scalar initialization and the Boolean sum/order predicate can use local Integers or explicit record fields. Mutable package globals are excluded; this scenario itself performs no simultaneous assignment.

Helpers read: printit L13–15, testit L17–33, swap L35–37, main L39–79.

printit emits all nine scalars only on failure paths. testit returns false on wrong sum; otherwise permuteok may skip exact field comparisons. swap reverses two scalar results. No helper executes in this review.

Existing local source coverage: [tests/conformance/bindings-and-scope/program.min:1–7](../../tests/conformance/bindings-and-scope/program.min) — Scalar assignment and lexical shadowing; two separate outer/inner outputs. [tests/adversarial.py:145–161](../../tests/adversarial.py) — Short-circuit Boolean effects and temporary lifetimes; no nine-value checksum fixture.

Original port/control: R3 proposed; none implemented/executed.

**S2 — [test/simassign.go:54–68](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/simassign.go#L54-L68) — main: 100 permutation steps and exact-order checkpoints. Incompatible as written.**

Expected upstream: L55: new slots 1..9 receive old slots [2,3,4,1,9,5,6,7,8] simultaneously; L18–32: every step preserves checksum 45; false permuteok also demands exact original order; L57: zero-based iterations 19,39,59,79,99 require original order; other iterations require only checksum; L64–67: after 100 steps, final testit(false) succeeds with values 1 through 9.

Minyar lacks simultaneous multi-target assignment. This permutation has a 4-cycle and a 5-cycle: order period 20. Checksum alone misses wrong permutations. Explicit scalar snapshot locals before nine writes are a proposed original algorithm fixture, not Go assignment-lowering coverage.

Helpers read: printit L13–15, testit L17–33, swap L35–37, main L39–79.

Existing local source coverage: [tests/ownership.py:88–98](../../tests/ownership.py) — List/Text alias and self assignment; saved old Text survives element replacement. [tests/recursive-data.py:173–184](../../tests/recursive-data.py) — Earlier projected record captured in literal survives later source replacement.

Original port/control: R3 proposed; none implemented/executed.

**S3 — [test/simassign.go:70–73](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/simassign.go#L70-L73) — main: two-result swap. Incompatible as written.**

Expected upstream: L35–37: swap returns y then x; L71–72: swap(1,2) assigns a=2,b=1.

Minyar functions return one value and lack tuple destructuring. An explicit Pair record can preserve the ordered values with ordinary ownership; it does not validate multi-result return lowering.

Helpers read: printit L13–15, testit L17–33, swap L35–37, main L39–79.

Existing local source coverage: [tests/scalar-record-initialization.py:28–36](../../tests/scalar-record-initialization.py) — Effectful two-field record result initializes y then x; expected 12,11,12. [tests/conformance/records/program.min:1–10](../../tests/conformance/records/program.min) — Explicit nested record construction and projections.

Original port/control: R3 proposed; none implemented/executed.

**S4 — [test/simassign.go:75–78](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/simassign.go#L75-L78) — main: nested swap argument expansion. Incompatible as written.**

Expected upstream: L35–37: each helper call reverses its inputs; L76–77: two nested swaps leave a=2,b=1.

Minyar has no multi-result expansion into function arguments. A Pair input/result helper applied twice tests value composition and reference lifetimes using existing record syntax.

Helpers read: printit L13–15, testit L17–33, swap L35–37, main L39–79.

Existing local source coverage: [tests/conformance/records/program.min:1–10](../../tests/conformance/records/program.min) — Explicit nested record construction and projections.

Original port/control: R3 proposed; none implemented/executed.

### Zig

**Z1 — [test/behavior/array.zig:9–19](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L9-L19) — array to slice. Incompatible as written.**

Expected upstream: L14: one-element slices containing 3 and 4 sum to 7; L18: selected constant-slice elements sum to 10.

Alignment qualifiers, scalar-address reinterpretation as array pointer, and array-to-slice coercion lack Minyar equivalents. Integer List indexing can preserve only the sums, omitting the core pointer/alignment contract.

Existing local source coverage: [tests/conformance/floats-and-bits/program.min:17–20](../../tests/conformance/floats-and-bits/program.min) — Typed Float List indexing and addition; only related scalar operations.

Original port/control: None proposed for this unsupported core contract.

**Z2 — [test/behavior/array.zig:21–46](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L21-L46) — arrays. Pending runtime subset.**

Expected upstream: L41: filled values 1 through 5 sum to 15; L42–45: getArrayLen returns 5.

An initialized five-element Integer List supports the same sequential writes, read-driven counter advance, sum and length helper. Undefined initialization, fixed size and unsigned widths are excluded. Every Minyar element must be initialized before access.

Helpers read: getArrayLen L44–46.

Existing local source coverage: [tests/runtime/lists.min:1–17](../../tests/runtime/lists.min) — List indexed writes and explicit while counter/sum; different input and length. [tests/conformance/loops-and-assignment/program.min:37–43](../../tests/conformance/loops-and-assignment/program.min) — Construct zero-filled Integer List and mutate through nested record; original aliases observe it.

Original port/control: R5 proposed; none implemented/executed.

**Z3 — [test/behavior/array.zig:48–69](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L48-L69) — array concat with undefined. Incompatible as written.**

Expected upstream: L57: writing uninitialized suffix yields helloworld; L62: writing uninitialized prefix yields helloworld; L67–68: both helper cases run at runtime and comptime.

Bytes are initialized; Minyar has no undefined array slots, array ++, lvalue slice writes or comptime. Explicit indexed writes into zero-filled Bytes check final contents only, not the undefined-concat contract.

Helpers read: S.doTheTest L53–64.

Existing local source coverage: [tests/conformance/bytes/program.min:2–6](../../tests/conformance/bytes/program.min) — Bytes(4) initializes zero then supports indexed writes. [tests/conformance/bytes/program.min:32–35](../../tests/conformance/bytes/program.min) — Clear reports zero length; resize initializes newly exposed bytes.

Original port/control: R4 proposed; none implemented/executed.

**Z4 — [test/behavior/array.zig:71–85](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L71-L85) — array concat with tuple. Pending runtime subset.**

Expected upstream: L79: sequence=[1,2,3,4]; L83: reverse operand order gives [3,4,1,2].

Explicit homogeneous fresh Lists/appended construction can preserve both ordered results. There is no Zig tuple coercion or array concat; the original proposal separately checks unchanged inputs.

Existing local source coverage: [tests/peer-research-semantics.py:192–214](../../tests/peer-research-semantics.py) — Original fresh appended List value-order checks preserve the original input.

Original port/control: R5 proposed; none implemented/executed.

**Z5 — [test/behavior/array.zig:87–93](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L87-L93) — array init with concat. Pending runtime subset.**

Expected upstream: L92: four bytes spell abcd.

Constructed Bytes or List<Character> preserves this ASCII order. Text + can preserve this value but does not test array concat or its type inference.

Existing local source coverage: [tests/conformance/loops-and-assignment/program.min:66–69](../../tests/conformance/loops-and-assignment/program.min) — Scalar Text compound joins produce abc; does not test arrays.

Original port/control: R5 proposed; none implemented/executed.

**Z6 — [test/behavior/array.zig:95–105](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L95-L105) — array init with mult. Pending runtime subset.**

Expected upstream: L101: two-byte pattern repeated four times spells abababab; L104: single byte repeated four times spells aaaa.

Explicit scalar-byte appends check contents and lengths 8 and 4. No array ** operator exists. Scalar repetition gives no evidence that reference-valued rows would be independently copied.

Existing local source coverage: [tests/peer-research-semantics.py:67–78](../../tests/peer-research-semantics.py) — Dynamically built rows are distinct; one-row mutation preserves another row.

Original port/control: R5, R6 proposed; none implemented/executed.

**Z7 — [test/behavior/array.zig:107–114](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L107-L114) — array literal with explicit type. Pending runtime subset.**

Expected upstream: L112: length=4; L113: index 1=256.

Annotated List<Integer> = [4096,256,16,1] preserves both values. Zig u16 and fixed size are excluded; Minyar length is a mutable-container runtime property.

Existing local source coverage: [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Literal inference, left-to-right effects, contextual empties, scalar elements, and literal arguments.

Original port/control: R5 proposed; none implemented/executed.

**Z8 — [test/behavior/array.zig:116–121](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L116-L121) — array literal with inferred length. Pending runtime subset.**

Expected upstream: L119: length=4; L120: index 1=256.

A nonempty unannotated Integer List preserves both values; its element type is inferred. That is distinct from inferring a static array-size type.

Existing local source coverage: [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Literal inference, left-to-right effects, contextual empties, scalar elements, and literal arguments.

Original port/control: R5 proposed; none implemented/executed.

**Z9 — [test/behavior/array.zig:123–132](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L123-L132) — array dot len const expr. Incompatible as written.**

Expected upstream: L124–126: comptime length=4; L129–132: field array size uses some_array.len.

Minyar runtime Lists have no comptime mode or length-dependent array types. Ordinary length==4 would omit the whole compile-time contract.

Existing local source coverage: [tests/conformance/text-and-lists/program.min:1–5](../../tests/conformance/text-and-lists/program.min) — Shared Text List alias sees append/replacement; no separate alias length assertion.

Original port/control: None proposed for this unsupported core contract.

**Z10 — [test/behavior/array.zig:134–142](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L134-L142) — array literal with specified size. Pending runtime subset.**

Expected upstream: L140: element0=1; L141: element1=2.

A two-element Integer List preserves observed values. Fixed [2]u8 shape, address-taking and fixed-size diagnostics are excluded.

Existing local source coverage: [tests/conformance/text-and-lists/program.min:11–12](../../tests/conformance/text-and-lists/program.min) — Contextual empty/nested Integer List and one element read. [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Literal inference, left-to-right effects, contextual empties, scalar elements, and literal arguments.

Original port/control: R5 proposed; none implemented/executed.

**Z11 — [test/behavior/array.zig:144–154](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L144-L154) — array len field. Pending runtime subset.**

Expected upstream: L149: runtime array length=4; L150: comptime array length=4; L151: runtime pointer length=4; L152: comptime pointer length=4; L153: length type is usize.

A List and plain alias both have runtime length 4: this is the runtime projection only. Minyar length is Integer. Array pointers, usize, type reflection and both comptime assertions remain incompatible.

Existing local source coverage: [tests/conformance/text-and-lists/program.min:1–5](../../tests/conformance/text-and-lists/program.min) — Shared Text List alias sees append/replacement; no separate alias length assertion. [tests/readonly-parameters.py:40–54](../../tests/readonly-parameters.py) — Borrowed List parameter retains shared mutations and reports length/values 2,6,6.

Original port/control: R5 proposed; none implemented/executed.

**Z12 — [test/behavior/array.zig:156–183](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L156-L183) — array with sentinels. Incompatible as written.**

Expected upstream: L164: zero-length array exposes sentinel 0xde at index 0; L167: one-element pointer reinterpretation also reads 0xde; L174: sentinel address minus last-element address is 1 byte at runtime; L177: sentinel slot is writable; L181–182: runtime and comptime calls; pointer-address check skipped in comptime.

Empty Minyar Bytes/List have no sentinel accessible at index length; such access traps. Pointers, address arithmetic and sentinel ABI do not exist. Adding an ordinary terminator changes logical length and is not a sentinel port.

Helpers read: S.doTheTest L161–178.

Existing local source coverage: [tests/list-access.py:48–65](../../tests/list-access.py) — Separate read/write bounds cases include zero-length List.

Original port/control: R7 proposed; none implemented/executed.

**Z13 — [test/behavior/array.zig:185–191](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L185-L191) — void arrays. Incompatible as written.**

Expected upstream: L187–188: void element read/write is well typed; L189: four void elements occupy 0 bytes; L190: logical length=4.

Nothing is restricted to return positions and cannot be a List element. Minyar has no zero-sized stored values or size reflection. Replacing void with Integer would change the type and layout property.

Existing local source coverage: [tests/regressions.py:204–207](../../tests/regressions.py) — Nothing cannot be a parameter, field or List element. [tests/recursive-data.py:186–197](../../tests/recursive-data.py) — Rejects invalid homogeneous elements, Nothing elements, and separators.

Original port/control: None proposed for this unsupported core contract.

**Z14 — [test/behavior/array.zig:193–206](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L193-L206) — nested arrays of strings. Pending runtime subset.**

Expected upstream: L200: element0=hello; L201: element1=this; L202: element2=is; L203: element3=my; L204: element4=thing.

For these ASCII literals, List<Text> iteration/content equality preserves every expectation. Zig byte-slice representation and paired index enumeration are excluded; use an explicit index counter or range lookups.

Existing local source coverage: [tests/conformance/loops-and-assignment/program.min:17–24](../../tests/conformance/loops-and-assignment/program.min) — Ordered Text List and Unicode Text iteration, different literals. [tests/conformance/text-and-lists/program.min:1–5](../../tests/conformance/text-and-lists/program.min) — Shared Text List alias sees append/replacement; no separate alias length assertion.

Original port/control: R5 proposed; none implemented/executed.

**Z15 — [test/behavior/array.zig:208–220](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L208-L220) — nested arrays of integers. Pending runtime subset.**

Expected upstream: L216: row0,column0=1; L217: row0,column1=2; L218: row1,column0=3; L219: row1,column1=4.

Nested Integer List literals preserve all four reads. Zig arrays are inline values; Minyar nested Lists share references. These reads alone establish no copy/alias rule. Add fresh-literal and deliberately-shared-row controls.

Existing local source coverage: [tests/conformance/loops-and-assignment/program.min:53–55](../../tests/conformance/loops-and-assignment/program.min) — Nested Integer literal indexed mutation; only one cell checked. [tests/peer-research-semantics.py:67–78](../../tests/peer-research-semantics.py) — Dynamically built rows are distinct; one-row mutation preserves another row.

Original port/control: R6 proposed; none implemented/executed.

**Z16 — [test/behavior/array.zig:222–232](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L222-L232) — implicit comptime in array type size. Incompatible as written.**

Expected upstream: L227: length=11; L230–232: plusOne(10)=11 in type-size expression.

Minyar cannot execute functions to form a static array-size type. Runtime construction of eleven elements would miss the upstream contract.

Helpers read: plusOne L230–232.

Existing local source coverage: [tests/conformance/loops-and-assignment/program.min:37–43](../../tests/conformance/loops-and-assignment/program.min) — Construct zero-filled Integer List and mutate through nested record; original aliases observe it.

Original port/control: None proposed for this unsupported core contract.

**Z17 — [test/behavior/array.zig:234–258](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L234-L258) — single-item pointer to array indexing and slicing. Incompatible as written.**

Expected upstream: L246: explicit-size initialized array becomes azya; L251: inferred-size initialized array becomes azya; L256–257: helper writes z by index and y through one-element writable slice; L238–239: runtime and comptime calls.

Shared Bytes parameters preserve direct indexed writes, but Bytes.slice(2,3) copies. A write at copied position0 cannot change source index 2. List has no slice method. Translating as a copying slice and expecting azya would be wrong.

Helpers read: testSingleItemPtrArrayIndexSlice L242–253, doSomeMangling L255–258.

Existing local source coverage: [tests/readonly-parameters.py:40–54](../../tests/readonly-parameters.py) — Borrowed List parameter retains shared mutations and reports length/values 2,6,6. [tests/conformance/bytes/program.min:17–18](../../tests/conformance/bytes/program.min) — Reads one copied Bytes slice value; no copy independence mutation oracle. [tests/runtime-bytes.c:79–85](../../tests/runtime-bytes.c) — Native slice length/content oracle; no post-slice mutation independence check in this branch. [tests/regressions.py:92–94](../../tests/regressions.py) — Rejects List.slice; no writable List view API.

Original port/control: R4 proposed; none implemented/executed.

**Z18 — [test/behavior/array.zig:260–273](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L260-L273) — implicit cast zero sized array ptr to slice. Incompatible as written.**

Expected upstream: L266: slice of inferred empty array has length 0; L271: slice of explicit zero-sized array has length 0.

Typed empty List/Bytes values can report zero length but have no array-pointer coercion. Emptiness is only a projected property, not a test of the selected cast.

Existing local source coverage: [tests/recursive-data.py:199–210](../../tests/recursive-data.py) — Contextual empty return/reassignment reports length zero. [tests/conformance/bytes/program.min:32–35](../../tests/conformance/bytes/program.min) — Clear reports zero length; resize initializes newly exposed bytes.

Original port/control: R7 proposed; none implemented/executed.

**Z19 — [test/behavior/array.zig:275–291](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L275-L291) — anonymous list literal syntax. Pending runtime subset.**

Expected upstream: L283: element0=1; L284: element1=2; L285: element2=3; L286: element3=4; L289–290: runtime and comptime helper calls.

An annotated Integer List literal preserves all four runtime elements. Zig anonymous literal coercion, fixed size and comptime invocation remain outside the adaptation.

Helpers read: S.doTheTest L280–287.

Existing local source coverage: [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Literal inference, left-to-right effects, contextual empties, scalar elements, and literal arguments.

Original port/control: R5 proposed; none implemented/executed.

**Z20 — [test/behavior/array.zig:293–309](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L293-L309) — set global var array via slice embedded in struct. Pending runtime subset.**

Expected upstream: L302–304: write fields 1,2,3 through embedded slice; L306: original element0 field=1; L307: original element1 field=2; L308: original element2 field=3.

An initialized local List<Sub> held in an owner record preserves these shared scalar-field mutations. Exclude package globals, undefined trailing elements and sliced subranges. Sub contains only Integer, so cycle prevention permits this mutation.

Existing local source coverage: [tests/conformance/loops-and-assignment/program.min:37–43](../../tests/conformance/loops-and-assignment/program.min) — Construct zero-filled Integer List and mutate through nested record; original aliases observe it. [tests/conformance/bytes/program.min:22–27](../../tests/conformance/bytes/program.min) — Record-held shared Bytes mutation observed through original record.

Original port/control: R8 proposed; none implemented/executed.

## Proposed narrow regressions

All proposals use existing Minyar syntax and automatic ownership. No new memory, pointer, sentinel, writable-view or tuple features are proposed. Expected values are independent oracles, not observed results.

**R1 (medium) — Exact loop progress and thresholds.**

One bounded program checks increment-before-break=6, inclusive range sum=55, explicit while sum=55, condition overshoot=108 and odd-sum after continue=25. Use a range for continue or put explicit while update before the continue path.

Expected: 6,55,55,108,25.

Existing related control fixtures have different thresholds; no exact Go ordinary-control adaptation exists here.

**R2 (high) — Fresh loop binding and explicit last-index tracking.**

Keep outer i=0; for i in 0..5 assign an unrelated value to its fresh loop binding, count visits, then check outer i unchanged. Separately clear a five-element List by explicit range index and update last. Use effectful range-bound functions and check exactly one call to each.

Expected: outer=0,visits=5; last=4 and five zeros; two bound calls total.

Existing lexical scope coverage lacks this exact outer-binding contrast. Effectful bounds are an original extension, not an assertion in Go for.go.

**R3 (medium) — Explicit snapshots and one-record swap composition.**

Perform 100 steps where new slots 1..9 receive old slots [2,3,4,1,9,5,6,7,8], explicitly capturing all nine scalar snapshots before writes. Check checksum every step and exact order every twentieth step. Return one explicit Pair record from a swap helper and apply it twice. Add a separate managed Text Pair capture-before-replacement control.

Expected: sum 45 every step; ordered 1..9 at steps 20,40,60,80,100; two swaps preserve ordered input; old captured Text survives replacement.

Existing self assignment/literal capture does not cover this composition. This is an original staged algorithm regression, not missing multi-target/tuple syntax support. Managed Text is an original extension.

**R4 (high) — Shared Bytes owner versus copied slice.**

Start Bytes spelling aaaa and keep an ordinary alias. A function writes z at source index 1, then copies slice 2..3 and writes y at copy index 0. Check source and alias separately. Write y directly to source index 2. Reassign both source and alias to fresh empty Bytes and verify the copied slice still reads y.

Expected: source/alias=azaa,copy=y; direct source write yields azya through both aliases; copy survives source replacement.

Inspected slice fixtures only check values/length, not mutation independence. Use existing Bytes/local/function syntax; no writable view feature. Source-replacement lifetime is an original extension.

**R5 (medium) — Bounded homogeneous construction and order.**

Compare annotated/inferred [4096,256,16,1] using length and all four elements. Fill initialized five-element List to1..5 and check sum/helper length. Construct both scalar concat orders and ASCII repetition using ordinary writes/appends. Check ordered five Text values.

Expected: length4,index 1=256 and all other values; sum15,length5; [1,2,3,4] versus[3,4,1,2]; abcd,abababab length8,aaaa length4; ordered hello,this,is,my,thing.

Inference/effect/append-order fixtures exist. New fixture preserves bounded values only; no Zig operators/width/pointer/comptime claim.

**R6 (high) — Nested literal independence and deliberate sharing.**

Construct [[1,2],[3,4]], check all four cells, mutate one row and check the other. In a separate control construct [row,row] and show both entries see the same mutation. Retain a row while replacing one outer element and check the saved row.

Expected: initial 1,2,3,4; distinct literal rows independent; deliberate shared rows both change; saved row survives replacement.

Dynamically built independent rows exist; literal-versus-shared controls and replacement lifetime are pending narrow additions.

**R7 (medium) — Empty containers have no sentinel.**

Check empty annotated Integer List and Bytes() lengths zero. Consider separate future negative cases for reading/writing index 0, retaining existing bounds diagnostics. Add no terminator as a sentinel substitute.

Expected: lengths0; each index 0 access stops with existing bounds error.

Zero-length List bounds/contextual empties already exist. Inspect all Bytes diagnostic fixtures before adding a companion; no new coverage claim.

**R8 (medium) — Shared scalar records in an owner-held List.**

Construct three initialized Sub records, keep backing List alias, put that List in an owner record, mutate three element fields through the owner and check the backing alias. Keep a saved element, replace one List position, and check the saved record.

Expected: backing fields 1,2,3; saved element remains accessible after replacement.

Related nested List/record and Bytes aliases exist; this precise three-field observation plus lifetime control remains proposed.

## Availability and boundaries

- The prior restricted Rust resource was not retried or routed around. Its exact failed URL was not supplied and was not guessed. The existing 336-entry UI inventory remains discovery only; prior round had zero semantic reviews/comparison units.
- All five selected source/license fetches succeeded. No new unavailable upstream resource or content/service restriction occurred.
- Go test/assign.go was accessible but remained an unselected discovery candidate. It receives no semantic-review/hash credit here.
- Optional local candidate tests/bytes.py was absent and skipped; runtime-bytes.c and conformance/bytes supplied actual inspected source references.
- Flagged mixed integration/literature lanes were not resumed. No native robustness work, soak, compilation, test execution, tool installation, production edits, commits or subagents occurred.

Only new peer-readonly-go-zig-round2 research files and evidence/peer-readonly/go-zig-round2 records were authored. Existing dirty work is preserved. Documentation consistency checks verified hashes, spans, all eight Go assertion call sites and all 20 selected Zig tests; they execute no compiler, test or peer program.

Ledger handoff: **three distinct source entries, two complete files, one partial prefix, 32 grouped units, zero ports, zero execution validations**. Retain the partial extent and all exclusions; other peer paths remain unreviewed.

Final provenance check observed a concurrent change to the campaign README after its initial read/hash. Both observed hashes and timestamps are retained in evidence; selected semantic documents and cited test fixtures still match their recorded hashes. This review did not modify the campaign README.
