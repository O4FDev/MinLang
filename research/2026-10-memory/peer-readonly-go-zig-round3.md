# Read-only Go/Zig peer comparison — round 3

Completed **66 new authored comparison groups**: 48 remaining Zig named tests, 9 Go assignment blocks and 9 Go branch scenarios. **25 runtime subsets remain pending; 41 groups are incompatible as written.** 8 original-control proposals are recorded, with P4 explicitly reusing existing empty/bounds contracts unless a concrete Bytes gap is later found. **Zero ports and zero test executions.**

Every named test, assertion case and in-file helper in the selected remainder was read through EOF. This is semantic research, not test execution, a production defect finding or whole-directory coverage. The plain-language/shared-reference contract is preserved; no language or memory syntax changes are proposed.

| Selected immutable source | Actual new semantic extent | Grouping |
| --- | --- | --- |
| [test/behavior/array.zig](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig) | Physical raw-byte lines 310–1127 | 48 authored groups |
| [test/assign.go](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/assign.go) | Physical raw-byte lines 1–71 | 9 authored groups |
| [test/if.go](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/if.go) | Physical raw-byte lines 1–93 | 9 authored groups |

Combined with the exact matching [round 2 record](peer-readonly-go-zig-round2.json), Zig array.zig is now completely reviewed: 68 named tests across the prefix and remainder. The newly selected Go files are complete. The [handoff ledger](../../evidence/peer-readonly/go-zig-round3/handoff.json) derives the union over selected files; it does not measure the whole campaign. Neither inventory discovery nor full-byte support-file retrieval receives semantic-review credit.

Go assign.go has an errorcheck directive: successful analysis means matching its ERROR annotations while accepting the positive assignment cases. It is not a successful executable program. Go if.go expects silent successful execution; Zig expectations apply only when the recorded backend guards permit its body. All outcomes here are inferred from primary source, never observed by running programs.

Exact full-byte source/license hashes, review spans and continuation hash are in [provenance](../../evidence/peer-readonly/go-zig-round3/provenance.json). Immutable source snapshots and their license notices are retained beside it. Authoritative lines include blank lines; web display normalization is not used. [Structured records](peer-readonly-go-zig-round3.json) contain exact per-site expectations, helper spans, guards, contracts and coverage references.

## Findings that affect a Minyar adaptation

- **Copied rows differ from shared bindings.** Zig L862–873 explicitly checks a captured row element remains zero after the source changes to fifteen. Plain Minyar binding of the inner List would observe fifteen. P6 proposes an alias versus explicit fresh snapshot control using existing syntax; implicit copying is not added.
- **Sentinel checks include memory beyond logical length.** The imported expectEqualSentinel helper first compares contents and lengths, then reads the expected and actual sentinel slots. Numeric sentinel 999, empty sentinel zero and sentinel splat cases cannot become content-only ports. Minyar rejects access at length. The tuple-to-sentinel case L605–614 only reads element zero; no absent sentinel assertion is invented.
- **Effects need an independent oracle.** A discarded array initializer checks two helper calls; weighted initializers check values 1,2,4,8 and state fifteen. These counters do not prove order on their own. P5 separates unused-initializer count from an original decimal trace that checks order. Existing used List literal/record initializer tests are related source coverage.
- **Nested reads and structural comparisons do not prove copying.** Ragged nested lengths/leaves and scalar filling project cleanly. Zig record comparisons recurse through fields; Minyar has no record equality. P3/P7 use individual fields and deliberately distinguish fresh construction from repeated shared references.
- **Type, storage and diagnostic contracts stay excluded.** Zero-bit values, type-valued arrays, union padding, undefined storage, pointer casts, optional/error unions and comptime execution have no direct counterpart. The final optional/error-union splat test discards its payload and does not assert payload contents. Go sync.Mutex/Time and repeated short-declaration regexes are library/syntax-specific, not imported Minyar diagnostics.
- **Ordinary branches remain simple.** Complete Go if.go supplies exact count oracles; ordinary Minyar Boolean if/else supports the runtime values. Go initializer clauses are expressed with existing explicit locals/functions. Branch-local bindings must not leak into sibling branches.

## Complete authored comparison groups

Pending runtime subset identifies a bounded adaptation or value projection with unsupported contracts excluded; it does not mean the whole upstream test is compatible or ported. Incompatible as written means its core contract is absent or different. Helpers/assertion sites remain grouped, never extra tests or ports. Local coverage below means actual inspected fixture source only; gaps are relative to those fixtures, not an exhaustive repository claim.

**Z21 — [test/behavior/array.zig:311–329](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L311-L329) — read/write through global variable array of struct fields initialized via array mult. Pending runtime subset.**

Expected primary-source cases: L317: storage[0].term=1; L319: after element replacement storage[0].term=123.

A local initialized List of explicit scalar records preserves these reads/replacements. Container-level mutable storage and array repetition are omitted; replacement is not a record copy proof.

In-file helper bodies read: doTheTest L316–320.

Upstream skips: stage2_arm, stage2_sparc64. No backend executed.

Inspected local coverage: [tests/conformance/records/program.min:1–10](../../tests/conformance/records/program.min) — Explicit record and nested List construction; Ada,36,language projections. All fields supplied. [tests/recursive-data.py:173–184](../../tests/recursive-data.py) — Captured earlier record projection survives later List replacement; old!,new!,new!. Replacement lifetime, not deep copying.

See proposal(s) P1: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z22 — [test/behavior/array.zig:331–337](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L331-L337) — implicit cast single-item pointer. Incompatible as written.**

Expected primary-source cases: L343: scalar byte=101 after writable slice increments it.

Minyar scalar arguments/bindings are values, not addressable storage convertible to a one-element array/slice. A shared one-element List control is original, not this scalar aliasing contract.

In-file helper bodies read: testImplicitCastSingleItemPtr L339–344.

Upstream skips: stage2_spirv, stage2_sparc64. No backend executed.

Explicit comptime-related source lines: 336. Parameter/driver details remain in the pinned body.

Inspected local coverage: [tests/readonly-parameters.py:40–54](../../tests/readonly-parameters.py) — Shared List parameter update/append exposes length2 and values6,6. Scalars are not addressable arguments.

See proposal(s) P1: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z23 — [test/behavior/array.zig:350–358](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L350-L358) — comptime evaluating function that takes array by value. Incompatible as written.**

Expected primary-source cases: L356: first comptime by-value array call returns1; L357: second comptime by-value array call returns1.

No compile-time function evaluation or by-value fixed arrays. Ordinary repeated List reads preserve values only, with shared argument semantics.

In-file helper bodies read: testArrayByValAtComptime L346–348.

Upstream skips: stage2_sparc64. No backend executed.

Explicit comptime-related source lines: 350, 354, 355. Parameter/driver details remain in the pinned body.

Inspected local coverage: [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Ordered effectful List literal values 1,2,3; literal function arguments 7/seven; Boolean/Character and nested Text empty context. Different exact values/shape from selected peer cases.

No original port proposed: the selected core contract is absent, or related source coverage already illustrates its supported runtime portion.

**Z24 — [test/behavior/array.zig:360–368](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L360-L368) — runtime initialize array elem and then implicit cast to slice. Pending runtime subset.**

Expected primary-source cases: L367: runtime initialized one-element slice[0]=2.

A List literal [two] captures Integer2. Exclude pointer-to-array coercion, i32 and slice representation.

Upstream skips: stage2_spirv, stage2_sparc64. No backend executed.

Inspected local coverage: [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Ordered effectful List literal values 1,2,3; literal function arguments 7/seven; Boolean/Character and nested Text empty context. Different exact values/shape from selected peer cases.

See proposal(s) P2: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z25 — [test/behavior/array.zig:370–395](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L370-L395) — array literal as argument to function. Pending runtime subset.**

Expected primary-source cases: L382: foo element0=1; L383: foo element1=2; L384: foo element2=3; L387: foo2 Boolean trash=true; L388: foo2 element0=1; L389: foo2 element1=2; L390: foo2 element2=3.

Pass [1,2,3] and [1,two,3] to typed List parameters, separately with a true Boolean argument. Four helper calls per entry exercise both helper variants; each entry also runs comptime upstream, excluded here. No by-value or lifetime claim follows from scalar reads.

In-file helper bodies read: entry L375–380; foo L381–385; foo2 L386–391.

Upstream skips: stage2_spirv, stage2_sparc64. No backend executed.

Explicit comptime-related source lines: 394. Parameter/driver details remain in the pinned body.

Inspected local coverage: [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Ordered effectful List literal values 1,2,3; literal function arguments 7/seven; Boolean/Character and nested Text empty context. Different exact values/shape from selected peer cases. [tests/readonly-parameters.py:40–54](../../tests/readonly-parameters.py) — Shared List parameter update/append exposes length2 and values6,6. Scalars are not addressable arguments.

See proposal(s) P2: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z26 — [test/behavior/array.zig:397–456](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L397-L456) — double nested array to const slice cast in array literal. Pending runtime subset.**

Expected primary-source cases: L418: cases2 outer length2; L419: cases2 row0 length1; L420: cases2[0][0]=1; L421: cases2 row1 length2; L422: cases2[1][0]=2; L423: cases2[1][1]=3; L437: check outer length3; L438: check case0 length1; L439: check case0 row0 length1; L440: check[0][0][0]=1; L441: check case1 length1; L442: check case1 row0 length2; L443: check[1][0][0]=2; L444: check[1][0][1]=3; L445: check case2 length2; L446: check case2 row0 length1; L447: check[2][0][0]=4; L448: check case2 row1 length3; L449: check[2][1][0]=5; L450: check[2][1][1]=6; L451: check[2][1][2]=7.

Typed nested Integer Lists preserve every length and leaf read. check is called on cases and cases3 (latter includes runtime two=2); cases2 is separately checked. Entry runs runtime and comptime upstream. Nested read oracles establish no alias/copy behavior.

In-file helper bodies read: entry L403–434; check L436–452.

Upstream skips: stage2_spirv, stage2_arm, stage2_sparc64. No backend executed.

Explicit comptime-related source lines: 455. Parameter/driver details remain in the pinned body.

Inspected local coverage: [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Ordered effectful List literal values 1,2,3; literal function arguments 7/seven; Boolean/Character and nested Text empty context. Different exact values/shape from selected peer cases. [tests/conformance/loops-and-assignment/program.min:53–55](../../tests/conformance/loops-and-assignment/program.min) — Two nested literal rows with one scalar mutation/read. Does not check cross-row independence. [tests/peer-research-semantics.py:67–78](../../tests/peer-research-semantics.py) — Ten dynamically constructed independent rows; mutation yields -1,10,99. Does not cover capturing/copying a row.

See proposal(s) P3: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z27 — [test/behavior/array.zig:458–481](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L458-L481) — anonymous literal in array. Pending runtime subset.**

Expected primary-source cases: L473: array[0].a=3; L474: array[0].b=4; L475: array[1].a=2; L476: array[1].b=3.

Minyar requires explicit named constructors and all fields: Foo{a:3;b:4}, Foo{a:2;b:3}. Values project; field defaults/anonymous coercion/usize/fixed-size/comptime do not.

In-file helper bodies read: doTheTest L467–477.

Upstream skips: stage2_arm, stage2_sparc64. No backend executed.

Explicit comptime-related source lines: 480. Parameter/driver details remain in the pinned body.

Inspected local coverage: [tests/conformance/records/program.min:1–10](../../tests/conformance/records/program.min) — Explicit record and nested List construction; Ada,36,language projections. All fields supplied. [tests/bootstrap-records.py:43–56](../../tests/bootstrap-records.py) — Existing missing/duplicate/unknown-field and wrong-type diagnostics. Source only; no bootstrap invocation here.

See proposal(s) P1: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z28 — [test/behavior/array.zig:483–498](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L483-L498) — access the null element of a null terminated array. Incompatible as written.**

Expected primary-source cases: L490: constant index4 reads sentinel0; L493: runtime index len=4 reads sentinel0.

A length4 Minyar container rejects index4. Adding zero as a fifth ordinary element changes length and cannot reproduce sentinel access.

In-file helper bodies read: doTheTest L487–494.

Upstream skips: stage2_sparc64. No backend executed.

Explicit comptime-related source lines: 497. Parameter/driver details remain in the pinned body.

Inspected local coverage: [tests/list-access.py:47–66](../../tests/list-access.py) — Empty/nonempty List reads/writes at length and extreme indices expect existing bounds diagnostic. No sentinel slot.

See proposal(s) P4: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z29 — [test/behavior/array.zig:500–516](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L500-L516) — type deduction for array subscript expression. Pending runtime subset.**

Expected primary-source cases: L508: true index selection reads0xAA=170; L510: false index selection reads0x55=85.

Use an explicit Integer index assigned by an ordinary Boolean if/else, then index an Integer List. No conditional expression, u8 coercion or comptime typing claim.

In-file helper bodies read: doTheTest L505–512.

Upstream skips: stage2_arm, stage2_sparc64. No backend executed.

Explicit comptime-related source lines: 515. Parameter/driver details remain in the pinned body.

Inspected local coverage: [tests/regressions.py:191–194](../../tests/regressions.py) — Ordinary Boolean branches return42/7; terminal fail branch and bare return. Different exact count oracles. [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Ordered effectful List literal values 1,2,3; literal function arguments 7/seven; Boolean/Character and nested Text empty context. Different exact values/shape from selected peer cases.

See proposal(s) P2: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z30 — [test/behavior/array.zig:518–540](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L518-L540) — sentinel element count towards the ABI size calculation. Incompatible as written.**

Expected primary-source cases: L532: extern struct raw-byte length3 including zero-length array sentinel; L533: raw byte0=0x55; L534: raw byte2=0xAA.

Minyar has no extern struct ABI or exposed raw record storage/sentinel. Three Bytes values would erase the layout contract.

In-file helper bodies read: doTheTest L524–535.

Upstream skips: stage2_spirv, stage2_arm, stage2_sparc64. No backend executed.

Explicit comptime-related source lines: 539. Parameter/driver details remain in the pinned body.

Inspected local coverage: [tests/conformance/bytes/program.min:2–18](../../tests/conformance/bytes/program.min) — Bytes initialized/indexed and one copied slice read; no subsequent copy independence mutation.

No original port proposed: the selected core contract is absent, or related source coverage already illustrates its supported runtime portion.

**Z31 — [test/behavior/array.zig:542–562](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L542-L562) — zero-sized array with recursive type definition. Incompatible as written.**

Expected primary-source cases: L561: recursive zero-sized array container default x=0.

Recursive records/empty recursive Lists exist, but no type-valued generic factory, @This, zero-sized inline array, defaults or undefined initialization. An empty recursive construction is related coverage, not this layout/type-resolution contract.

In-file helper bodies read: foo L547–552.

Upstream skips: stage2_sparc64, stage2_spirv. No backend executed.

Inspected local coverage: [tests/recursive-data.py:199–210](../../tests/recursive-data.py) — Contextual empty return/reassignment length0; nested typed literal reads2. No comptime empty pointer coercion.

No original port proposed: the selected core contract is absent, or related source coverage already illustrates its supported runtime portion.

**Z32 — [test/behavior/array.zig:564–597](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L564-L597) — type coercion of anon struct literal to array. Incompatible as written.**

Expected primary-source cases: L582: scalar arr1[0]=42; L583: scalar arr1[1]=56; L584: scalar arr1[2]=54; L590: union arr2[0].a=42; L591: union arr2[1].b=true; L592: union arr2[2].c contents=hello.

Integer List [42,56,54] projects the scalar half only. Core anonymous heterogeneous tuple coercion and untagged union variants are absent; do not replace the union with unrelated record fields and claim compatibility.

In-file helper bodies read: doTheTest L577–593.

Upstream skips: stage2_aarch64, stage2_spirv, stage2_sparc64, stage2_arm. No backend executed.

Explicit comptime-related source lines: 596. Parameter/driver details remain in the pinned body.

Inspected local coverage: [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Ordered effectful List literal values 1,2,3; literal function arguments 7/seven; Boolean/Character and nested Text empty context. Different exact values/shape from selected peer cases. [tests/conformance/records/program.min:1–10](../../tests/conformance/records/program.min) — Explicit record and nested List construction; Ada,36,language projections. All fields supplied.

See proposal(s) P2: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z33 — [test/behavior/array.zig:599–603](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L599-L603) — array with comptime-only element type. Incompatible as written.**

Expected primary-source cases: L601: array element0 is type u32; L602: array element1 is type i32.

Minyar types are not stored values; no List<type>, reflection or comptime-only element type. Integer values cannot port this assertion.

Inspected local coverage: [tests/recursive-data.py:186–197](../../tests/recursive-data.py) — Homogeneous literal and Nothing/separator diagnostics; does not implement tuple coercion or zero-bit storage.

No original port proposed: the selected core contract is absent, or related source coverage already illustrates its supported runtime portion.

**Z34 — [test/behavior/array.zig:605–614](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L605-L614) — tuple to array handles sentinel. Incompatible as written.**

Expected primary-source cases: L613: tuple-coerced sentinel array element0=1; sentinel is not explicitly read.

Absent tuple coercion and sentinel array types. Content-only [1,2,3] is not a sentinel validation; no missing sentinel assertion is invented.

Upstream skips: stage2_arm, stage2_sparc64. No backend executed.

Inspected local coverage: [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Ordered effectful List literal values 1,2,3; literal function arguments 7/seven; Boolean/Character and nested Text empty context. Different exact values/shape from selected peer cases.

No original port proposed: the selected core contract is absent, or related source coverage already illustrates its supported runtime portion.

**Z35 — [test/behavior/array.zig:616–637](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L616-L637) — array init of container level array variable. Pending runtime subset.**

Expected primary-source cases: L632: pair initially exactly[1,2]; L634: direct initialized assignment yields exactly[3,4]; L636: temporary initialized assignment yields exactly[5,6].

Use a local owner record with a List<Integer> field and helper replacement, comparing length and each scalar explicitly. No List equality, mutable module globals, noinline promise or by-value copy. Save old alias as an original lifetime control.

In-file helper bodies read: foo L623–625; bar L626–630.

Upstream skips: stage2_spirv, stage2_arm, stage2_sparc64. No backend executed.

Inspected local coverage: [tests/conformance/records/program.min:1–10](../../tests/conformance/records/program.min) — Explicit record and nested List construction; Ada,36,language projections. All fields supplied. [tests/recursive-data.py:173–184](../../tests/recursive-data.py) — Captured earlier record projection survives later List replacement; old!,new!,new!. Replacement lifetime, not deep copying.

See proposal(s) P1: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z36 — [test/behavior/array.zig:639–648](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L639-L648) — runtime initialized sentinel-terminated array literal. Incompatible as written.**

Expected primary-source cases: L646: byte reinterpretation at2=0x99; L647: byte reinterpretation at3=0x99.

Sentinel0x9999 is stored after runtime u16 value300; both its bytes equal0x99 regardless byte order. Minyar exposes neither sentinel layout nor pointer reinterpretation. Explicit Bytes serialization would be original and unnecessary to this review.

Upstream skips: stage2_spirv. No backend executed.

Inspected local coverage: [tests/conformance/bytes/program.min:2–18](../../tests/conformance/bytes/program.min) — Bytes initialized/indexed and one copied slice read; no subsequent copy independence mutation.

No original port proposed: the selected core contract is absent, or related source coverage already illustrates its supported runtime portion.

**Z37 — [test/behavior/array.zig:650–658](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L650-L658) — array of array agregate init. Pending runtime subset.**

Expected primary-source cases: L657: second repeated inner array element1=11.

Initialize two length10 Integer Lists of11 and check selected cell. Upstream value read does not itself assert repetition copy independence. Deliberate shared versus separately constructed rows need independent controls.

Upstream skips: stage2_arm, stage2_sparc64. No backend executed.

Inspected local coverage: [tests/conformance/loops-and-assignment/program.min:53–55](../../tests/conformance/loops-and-assignment/program.min) — Two nested literal rows with one scalar mutation/read. Does not check cross-row independence. [tests/peer-research-semantics.py:67–78](../../tests/peer-research-semantics.py) — Ten dynamically constructed independent rows; mutation yields -1,10,99. Does not cover capturing/copying a row.

See proposal(s) P3: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z38 — [test/behavior/array.zig:660–668](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L660-L668) — pointer to array has ptr field. Incompatible as written.**

Expected primary-source cases: L662: array .ptr equals cast many-item pointer; L663: ptr[0]=10; L664: ptr[1]=20; L665: ptr[2]=30; L666: ptr[3]=40; L667: pointer-to-ptr dereference index4=50.

No pointer .ptr field, pointer equality, pointer cast or pointer-to-pointer access. List reads10..50 omit the central pointer contract.

Inspected local coverage: [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Ordered effectful List literal values 1,2,3; literal function arguments 7/seven; Boolean/Character and nested Text empty context. Different exact values/shape from selected peer cases.

No original port proposed: the selected core contract is absent, or related source coverage already illustrates its supported runtime portion.

**Z39 — [test/behavior/array.zig:670–686](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L670-L686) — discarded array init preserves result location. Pending runtime subset.**

Expected primary-source cases: L685: discarded literal still invokes helper twice; x=2.

Use a shared Integer state List, a helper increments it and returns0, and an unused let value=[helper(state),helper(state)]. Existing syntax preserves required effects, excluding scalar address, intCast/u16-to-u8 and result-location lowering. This assertion checks count, not call order; add distinct ordered effects as an original extension.

In-file helper bodies read: f L672–675.

Inspected local coverage: [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Ordered effectful List literal values 1,2,3; literal function arguments 7/seven; Boolean/Character and nested Text empty context. Different exact values/shape from selected peer cases. [tests/scalar-record-initialization.py:28–36](../../tests/scalar-record-initialization.py) — Effectful record field initializers in source order; x12,y11,state12. No discarded List initializer oracle.

See proposal(s) P5: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z40 — [test/behavior/array.zig:688–697](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L688-L697) — array init with no result location has result type. Pending runtime subset.**

Expected primary-source cases: L694: record-held array length2; L695: element0=10; L696: element1=20.

Explicit owner record field List<Integer>=[10,20] preserves values/length. No anonymous record, context-dependent intCast, u16 or no-result-location contract.

Inspected local coverage: [tests/conformance/records/program.min:1–10](../../tests/conformance/records/program.min) — Explicit record and nested List construction; Ada,36,language projections. All fields supplied. [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Ordered effectful List literal values 1,2,3; literal function arguments 7/seven; Boolean/Character and nested Text empty context. Different exact values/shape from selected peer cases.

See proposal(s) P2: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z41 — [test/behavior/array.zig:699–709](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L699-L709) — slicing array of zero-sized values. Incompatible as written.**

Expected primary-source cases: L708: each of32 zero-bit u0 elements equals0 after pointer iteration writes0.

Minyar has signed64 Integers and no zero-bit numeric storage or element pointers. A32-zero List uses real storage and validates a different contract.

Upstream skips: stage2_arm, stage2_sparc64, stage2_spirv. No backend executed.

Inspected local coverage: [tests/regressions.py:204–207](../../tests/regressions.py) — Nothing rejected as field, parameter and List element; source diagnostics only. [tests/recursive-data.py:186–197](../../tests/recursive-data.py) — Homogeneous literal and Nothing/separator diagnostics; does not implement tuple coercion or zero-bit storage.

No original port proposed: the selected core contract is absent, or related source coverage already illustrates its supported runtime portion.

**Z42 — [test/behavior/array.zig:711–723](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L711-L723) — array init with no result pointer sets field result types. Pending runtime subset.**

Expected primary-source cases: L722: helper result123 equals input x123.

Pass [x] to a List<Integer> helper returning element0. u64-to-u32 inferred cast and value-array calling convention excluded.

In-file helper bodies read: f L714–716.

Inspected local coverage: [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Ordered effectful List literal values 1,2,3; literal function arguments 7/seven; Boolean/Character and nested Text empty context. Different exact values/shape from selected peer cases.

See proposal(s) P2: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z43 — [test/behavior/array.zig:725–749](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L725-L749) — runtime side-effects in comptime-known array init. Pending runtime subset.**

Expected primary-source cases: L747: initialized array exactly[1,2,4,8]; L748: side_effects equals u4 maximum15.

Helpers update shared state by1,2,4,8 and return those values into an Integer List. Check all values and state15. Exclude block expressions, u4/comptime result knowledge and array equality. Count/sum alone does not prove order; a decimal trace is an original extension.

Upstream skips: stage2_spirv. No backend executed.

Inspected local coverage: [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Ordered effectful List literal values 1,2,3; literal function arguments 7/seven; Boolean/Character and nested Text empty context. Different exact values/shape from selected peer cases. [tests/scalar-record-initialization.py:28–36](../../tests/scalar-record-initialization.py) — Effectful record field initializers in source order; x12,y11,state12. No discarded List initializer oracle.

See proposal(s) P5: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z44 — [test/behavior/array.zig:751–764](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L751-L764) — slice initialized through reference to anonymous array init provides result types. Pending runtime subset.**

Expected primary-source cases: L763: slice length4 and elements exactly[123,456,123,456].

Typed Integer List preserves ordered values. intCast/truncate are identities on these chosen small values; the test supplies no truncation boundary oracle. Exclude u16 coercion and array-to-slice reference.

Upstream skips: stage2_spirv. No backend executed.

Inspected local coverage: [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Ordered effectful List literal values 1,2,3; literal function arguments 7/seven; Boolean/Character and nested Text empty context. Different exact values/shape from selected peer cases.

See proposal(s) P2: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z45 — [test/behavior/array.zig:766–779](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L766-L779) — sentinel-terminated slice initialized through reference to anonymous array init provides result types. Incompatible as written.**

Expected primary-source cases: L778: slice length4, values[123,456,123,456], expected and actual in-memory sentinel999.

expectEqualSentinel additionally reads index length via imported helper. Minyar lacks sentinel storage; contents-only port loses that assertion and width coercion.

Upstream skips: stage2_spirv. No backend executed.

Inspected local coverage: [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Ordered effectful List literal values 1,2,3; literal function arguments 7/seven; Boolean/Character and nested Text empty context. Different exact values/shape from selected peer cases. [tests/list-access.py:47–66](../../tests/list-access.py) — Empty/nonempty List reads/writes at length and extreme indices expect existing bounds diagnostic. No sentinel slot.

No original port proposed: the selected core contract is absent, or related source coverage already illustrates its supported runtime portion.

**Z46 — [test/behavior/array.zig:781–798](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L781-L798) — many-item pointer initialized through reference to anonymous array init provides result types. Incompatible as written.**

Expected primary-source cases: L794: many-pointer[0]=123; L795: many-pointer[1]=456; L796: many-pointer[2]=123; L797: many-pointer[3]=456.

Core many-item pointer result typing absent. Scalar List projection can share P2, but does not validate pointers or @truncate.

Upstream skips: stage2_spirv, stage2_riscv64. No backend executed.

Inspected local coverage: [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Ordered effectful List literal values 1,2,3; literal function arguments 7/seven; Boolean/Character and nested Text empty context. Different exact values/shape from selected peer cases.

See proposal(s) P2: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z47 — [test/behavior/array.zig:800–818](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L800-L818) — many-item sentinel-terminated pointer initialized through reference to anonymous array init provides result types. Incompatible as written.**

Expected primary-source cases: L813: sentinel many-pointer[0]=123; L814: sentinel many-pointer[1]=456; L815: sentinel many-pointer[2]=123; L816: sentinel many-pointer[3]=456; L817: sentinel many-pointer[4]=999.

Length4 Minyar List rejects index4; ordinary fifth element would change the shape. Many-item pointers and u16 result typing absent.

Upstream skips: stage2_spirv, stage2_riscv64. No backend executed.

Inspected local coverage: [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Ordered effectful List literal values 1,2,3; literal function arguments 7/seven; Boolean/Character and nested Text empty context. Different exact values/shape from selected peer cases. [tests/list-access.py:47–66](../../tests/list-access.py) — Empty/nonempty List reads/writes at length and extreme indices expect existing bounds diagnostic. No sentinel slot.

No original port proposed: the selected core contract is absent, or related source coverage already illustrates its supported runtime portion.

**Z48 — [test/behavior/array.zig:820–833](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L820-L833) — pointer to array initialized through reference to anonymous array init provides result types. Incompatible as written.**

Expected primary-source cases: L832: pointer-array length4 and values[123,456,123,456].

No pointer-to-array result type. Runtime content projection is P2, with pointer coercion/width inference explicitly excluded.

Upstream skips: stage2_spirv. No backend executed.

Inspected local coverage: [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Ordered effectful List literal values 1,2,3; literal function arguments 7/seven; Boolean/Character and nested Text empty context. Different exact values/shape from selected peer cases.

See proposal(s) P2: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z49 — [test/behavior/array.zig:835–848](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L835-L848) — pointer to sentinel-terminated array initialized through reference to anonymous array init provides result types. Incompatible as written.**

Expected primary-source cases: L847: pointer sentinel-array length4, values[123,456,123,456], in-memory sentinel999.

Sentinel helper checks both content and index4 storage; pointer array and sentinel ABI absent.

Upstream skips: stage2_spirv. No backend executed.

Inspected local coverage: [tests/list-access.py:47–66](../../tests/list-access.py) — Empty/nonempty List reads/writes at length and extreme indices expect existing bounds diagnostic. No sentinel slot. [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Ordered effectful List literal values 1,2,3; literal function arguments 7/seven; Boolean/Character and nested Text empty context. Different exact values/shape from selected peer cases.

No original port proposed: the selected core contract is absent, or related source coverage already illustrates its supported runtime portion.

**Z50 — [test/behavior/array.zig:850–860](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L850-L860) — tuple initialized through reference to anonymous array init provides result types. Incompatible as written.**

Expected primary-source cases: L858: tuple first item12345; L859: tuple second pointer converted to address0x1000.

Heterogeneous tuple, pointers, integer-address conversion and inferred cast unsupported. A two-Integer record would remove pointer semantics.

Upstream skips: stage2_spirv. No backend executed.

Inspected local coverage: [tests/conformance/records/program.min:1–10](../../tests/conformance/records/program.min) — Explicit record and nested List construction; Ada,36,language projections. All fields supplied.

No original port proposed: the selected core contract is absent, or related source coverage already illustrates its supported runtime portion.

**Z51 — [test/behavior/array.zig:862–873](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L862-L873) — copied array element doesn't alias source. Incompatible as written.**

Expected primary-source cases: L872: captured by-value row a[1] remains0 after source x[0][1] becomes15.

Plain Minyar let a=x[0] shares the row and would observe15. Explicit copying into a fresh List can preserve0, but is an original snapshot algorithm, not by-value assignment. Initialize every Minyar cell; upstream only observes initialized selected cell.

Upstream skips: stage2_arm, stage2_sparc64. No backend executed.

Inspected local coverage: [tests/ownership.py:88–98](../../tests/ownership.py) — List alias/self assignment plus immutable old Text survival after replacement. Does not assert deep List copying. [tests/peer-research-semantics.py:67–78](../../tests/peer-research-semantics.py) — Ten dynamically constructed independent rows; mutation yields -1,10,99. Does not cover capturing/copying a row. [tests/recursive-data.py:173–184](../../tests/recursive-data.py) — Captured earlier record projection survives later List replacement; old!,new!,new!. Replacement lifetime, not deep copying.

See proposal(s) P6: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z52 — [test/behavior/array.zig:875–894](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L875-L894) — array initialized with string literal. Incompatible as written.**

Expected primary-source cases: L893: union-held record array bytes spell12345.

No untagged union, inline string-to-array copying, or undefined scalar field. Explicit initialized owner record/Text preserves contents only, not this storage path.

Upstream skips: stage2_sparc64, stage2_spirv. No backend executed.

Inspected local coverage: [tests/conformance/records/program.min:1–10](../../tests/conformance/records/program.min) — Explicit record and nested List construction; Ada,36,language projections. All fields supplied.

No original port proposed: the selected core contract is absent, or related source coverage already illustrates its supported runtime portion.

**Z53 — [test/behavior/array.zig:896–915](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L896-L915) — array initialized with array with sentinel. Incompatible as written.**

Expected primary-source cases: L914: union-held non-sentinel destination array length5 and values[1,2,3,4,5].

Sentinel source coerces into plain array held inside union; no sentinel, union or inline copy counterpart. The destination expectation does not read the source sentinel.

Upstream skips: stage2_spirv, stage2_sparc64. No backend executed.

Inspected local coverage: [tests/conformance/records/program.min:1–10](../../tests/conformance/records/program.min) — Explicit record and nested List construction; Ada,36,language projections. All fields supplied. [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Ordered effectful List literal values 1,2,3; literal function arguments 7/seven; Boolean/Character and nested Text empty context. Different exact values/shape from selected peer cases.

No original port proposed: the selected core contract is absent, or related source coverage already illustrates its supported runtime portion.

**Z54 — [test/behavior/array.zig:917–939](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L917-L939) — store array of array of structs at comptime. Pending runtime subset.**

Expected primary-source cases: L937: runtime nested struct-array helper returns15; L938: comptime same helper returns15.

Nested List<List<Cell>> with explicit Cell{x:15} preserves runtime return15; compile-time storage, by-value arrays and u8 excluded. No aliasing assertion here.

In-file helper bodies read: storeArrayOfArrayOfStructs L922–934.

Upstream skips: stage2_arm, stage2_sparc64. No backend executed.

Explicit comptime-related source lines: 938. Parameter/driver details remain in the pinned body.

Inspected local coverage: [tests/conformance/records/program.min:1–10](../../tests/conformance/records/program.min) — Explicit record and nested List construction; Ada,36,language projections. All fields supplied. [tests/conformance/loops-and-assignment/program.min:53–55](../../tests/conformance/loops-and-assignment/program.min) — Two nested literal rows with one scalar mutation/read. Does not check cross-row independence.

See proposal(s) P3: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z55 — [test/behavior/array.zig:941–954](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L941-L954) — accessing multidimensional global array at comptime. Pending runtime subset.**

Expected primary-source cases: L952: global nested array first inner length1; L953: first nested string=hello.

Local List<List<Text>> [[hello],[world,hello]] preserves checked length/value. Despite test title, call sites shown are ordinary testing calls; global const construction/comptime storage excluded, not counted as explicit comptime assertions. Other leaves not asserted upstream can be original controls.

Upstream skips: stage2_arm, stage2_spirv. No backend executed.

Inspected local coverage: [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Ordered effectful List literal values 1,2,3; literal function arguments 7/seven; Boolean/Character and nested Text empty context. Different exact values/shape from selected peer cases.

See proposal(s) P3: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z56 — [test/behavior/array.zig:956–978](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L956-L978) — union that needs padding bytes inside an array. Incompatible as written.**

Expected primary-source cases: L977: copied nested union variant D=1.

Nested tagged unions, tags and padding layout are absent. Integer record fields would remove the core layout bug class.

Upstream skips: stage2_aarch64, stage2_spirv, stage2_arm, stage2_sparc64. No backend executed.

Inspected local coverage: [tests/conformance/records/program.min:1–10](../../tests/conformance/records/program.min) — Explicit record and nested List construction; Ada,36,language projections. All fields supplied.

No original port proposed: the selected core contract is absent, or related source coverage already illustrates its supported runtime portion.

**Z57 — [test/behavior/array.zig:980–991](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L980-L991) — runtime index of array of zero-bit values. Incompatible as written.**

Expected primary-source cases: L989: result index=0; L990: result stored void value equals empty void literal.

Nothing cannot be stored in a record or List; runtime indexing of zero-bit void and anonymous record unsupported. Index0 alone does not preserve second assertion.

Upstream skips: stage2_spirv. No backend executed.

Inspected local coverage: [tests/regressions.py:204–207](../../tests/regressions.py) — Nothing rejected as field, parameter and List element; source diagnostics only.

No original port proposed: the selected core contract is absent, or related source coverage already illustrates its supported runtime portion.

**Z58 — [test/behavior/array.zig:993–1012](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L993-L1012) — @splat array. Pending runtime subset.**

Expected primary-source cases: L1001: all10 u32 elements equal123; separately all10 Foo records compare field x=10.

Scalar Integer fill can preserve123. Explicit newly constructed Cell{x:10} values with field checks preserve record contents, excluding record equality, generic @splat, widths and comptime. Reusing one Cell shares in Minyar; independent mutation/sharing controls are original, because upstream equality alone proves no alias rule.

In-file helper bodies read: doTheTest L998–1003.

Upstream skips: stage2_arm, stage2_sparc64. No backend executed.

Explicit comptime-related source lines: 1007, 1011. Parameter/driver details remain in the pinned body.

Inspected local coverage: [tests/peer-research-semantics.py:67–78](../../tests/peer-research-semantics.py) — Ten dynamically constructed independent rows; mutation yields -1,10,99. Does not cover capturing/copying a row. [tests/conformance/records/program.min:1–10](../../tests/conformance/records/program.min) — Explicit record and nested List construction; Ada,36,language projections. All fields supplied.

See proposal(s) P7: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z59 — [test/behavior/array.zig:1014–1035](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L1014-L1035) — @splat array with sentinel. Incompatible as written.**

Expected primary-source cases: L1023: all10 numeric elements100; separately all10 optional opaque pointers address0x1000; L1026: numeric sentinel42; optional pointer sentinelnull at index10.

Sentinel, optional opaque pointers/address conversion, generic splat and comptime absent. Scalar fill is related P7 only, not this sentinel contract.

In-file helper bodies read: doTheTest L1020–1027.

Upstream skips: stage2_spirv, stage2_arm, stage2_sparc64. No backend executed.

Explicit comptime-related source lines: 1031, 1034. Parameter/driver details remain in the pinned body.

Inspected local coverage: [tests/list-access.py:47–66](../../tests/list-access.py) — Empty/nonempty List reads/writes at length and extreme indices expect existing bounds diagnostic. No sentinel slot.

See proposal(s) P7: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z60 — [test/behavior/array.zig:1037–1058](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L1037-L1058) — @splat zero-length array. Incompatible as written.**

Expected primary-source cases: L1049: zero-length array is comptime-known with sentinel42; pointer variant sentinelnull.

Zero-length array splat of runtime undefined value still supplies a compile-time sentinel. Minyar typed empty Lists have no slot0 and no runtime-undefined/comptime notion.

In-file helper bodies read: doTheTest L1043–1050.

Upstream skips: stage2_spirv, stage2_arm, stage2_sparc64. No backend executed.

Explicit comptime-related source lines: 1049, 1054, 1057. Parameter/driver details remain in the pinned body.

Inspected local coverage: [tests/recursive-data.py:199–210](../../tests/recursive-data.py) — Contextual empty return/reassignment length0; nested typed literal reads2. No comptime empty pointer coercion. [tests/list-access.py:47–66](../../tests/list-access.py) — Empty/nonempty List reads/writes at length and extreme indices expect existing bounds diagnostic. No sentinel slot.

See proposal(s) P4: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z61 — [test/behavior/array.zig:1060–1063](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L1060-L1063) — initialize slice with reference to empty array initializer. Incompatible as written.**

Expected primary-source cases: L1062: empty referenced array coerces to slice of comptime length0.

Runtime empty List length0 is related but cannot validate compile-time pointer/slice coercion.

Explicit comptime-related source lines: 1062. Parameter/driver details remain in the pinned body.

Inspected local coverage: [tests/recursive-data.py:199–210](../../tests/recursive-data.py) — Contextual empty return/reassignment length0; nested typed literal reads2. No comptime empty pointer coercion.

See proposal(s) P4: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z62 — [test/behavior/array.zig:1065–1068](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L1065-L1068) — initialize many-pointer with reference to empty array initializer. Incompatible as written.**

Expected primary-source cases: L1066: reference to empty array accepted as many-item pointer; L1067: pointer discarded; no value assertion.

No pointer type or empty anonymous array coercion. This is compile-acceptance only, not a hidden value test.

Inspected local coverage: [tests/recursive-data.py:199–210](../../tests/recursive-data.py) — Contextual empty return/reassignment length0; nested typed literal reads2. No comptime empty pointer coercion.

No original port proposed: the selected core contract is absent, or related source coverage already illustrates its supported runtime portion.

**Z63 — [test/behavior/array.zig:1070–1074](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L1070-L1074) — initialize sentinel-terminated slice with reference to empty array initializer. Incompatible as written.**

Expected primary-source cases: L1072: empty sentinel slice comptime length0; L1073: sentinel slice slot0=0 at comptime.

Minyar emptiness and bounds contrast must remain distinct; no sentinel slot0 or comptime.

Explicit comptime-related source lines: 1072, 1073. Parameter/driver details remain in the pinned body.

Inspected local coverage: [tests/recursive-data.py:199–210](../../tests/recursive-data.py) — Contextual empty return/reassignment length0; nested typed literal reads2. No comptime empty pointer coercion. [tests/list-access.py:47–66](../../tests/list-access.py) — Empty/nonempty List reads/writes at length and extreme indices expect existing bounds diagnostic. No sentinel slot.

See proposal(s) P4: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z64 — [test/behavior/array.zig:1076–1079](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L1076-L1079) — initialize sentinel-terminated many-pointer with reference to empty array initializer. Incompatible as written.**

Expected primary-source cases: L1078: empty sentinel many-pointer slot0=0 at comptime.

No many-pointer/sentinel/comptime. Ordinary empty container access stops; replacing with [0] changes length.

Explicit comptime-related source lines: 1078. Parameter/driver details remain in the pinned body.

Inspected local coverage: [tests/list-access.py:47–66](../../tests/list-access.py) — Empty/nonempty List reads/writes at length and extreme indices expect existing bounds diagnostic. No sentinel slot.

See proposal(s) P4: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z65 — [test/behavior/array.zig:1081–1088](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L1081-L1088) — pass pointer to empty array initializer to anytype parameter. Incompatible as written.**

Expected primary-source cases: L1087: anytype helper reports exact type of empty-array-reference initializer.

No generic anytype, type-valued result, type reflection or compile-time assertion. Typed empty List context is not equivalent.

In-file helper bodies read: TypeOf L1083–1085.

Explicit comptime-related source lines: 1087. Parameter/driver details remain in the pinned body.

Inspected local coverage: [tests/recursive-data.py:199–210](../../tests/recursive-data.py) — Contextual empty return/reassignment length0; nested typed literal reads2. No comptime empty pointer coercion.

No original port proposed: the selected core contract is absent, or related source coverage already illustrates its supported runtime portion.

**Z66 — [test/behavior/array.zig:1090–1101](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L1090-L1101) — initialize pointer to anyopaque with reference to empty array initializer. Incompatible as written.**

Expected primary-source cases: L1100: loaded opaque-pointer cast has exact empty tuple type at comptime; no value assertion.

No opaque pointer, alignment cast, pointer cast, empty tuple or type reflection. Empty runtime List has a different contract.

Upstream skips: stage2_spirv. No backend executed.

Explicit comptime-related source lines: 1100. Parameter/driver details remain in the pinned body.

Inspected local coverage: [tests/recursive-data.py:199–210](../../tests/recursive-data.py) — Contextual empty return/reassignment length0; nested typed literal reads2. No comptime empty pointer coercion.

No original port proposed: the selected core contract is absent, or related source coverage already illustrates its supported runtime portion.

**Z67 — [test/behavior/array.zig:1103–1114](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L1103-L1114) — sentinel of runtime-known array initialization is populated. Incompatible as written.**

Expected primary-source cases: L1112: runtime-known array data slot0=42; L1113: sentinel storage slot1=123.

No sentinel array or many-pointer access. A List of length1 reads42 but rejects index1; adding ordinary123 changes length.

Upstream skips: stage2_spirv. No backend executed.

Inspected local coverage: [tests/list-access.py:47–66](../../tests/list-access.py) — Empty/nonempty List reads/writes at length and extreme indices expect existing bounds diagnostic. No sentinel slot. [tests/recursive-data.py:148–171](../../tests/recursive-data.py) — Ordered effectful List literal values 1,2,3; literal function arguments 7/seven; Boolean/Character and nested Text empty context. Different exact values/shape from selected peer cases.

See proposal(s) P4: original existing-syntax control only; unsupported peer contracts remain excluded.

**Z68 — [test/behavior/array.zig:1116–1127](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig#L1116-L1127) — splat with an error union or optional result type. Incompatible as written.**

Expected primary-source cases: L1125: generic error-union/optional vector splat call succeeds and result discarded; L1126: generic error-union/optional fixed-array splat call succeeds and result discarded.

No error union, optional, vector, generic type-valued argument or @splat. No payload element/assertion is present; do not claim four ones were checked.

In-file helper bodies read: doTest L1120–1122.

Upstream skips: stage2_aarch64. No backend executed.

Inspected local coverage: [tests/recursive-data.py:186–197](../../tests/recursive-data.py) — Homogeneous literal and Nothing/separator diagnostics; does not implement tuple coercion or zero-bit storage.

No original port proposed: the selected core contract is absent, or related source coverage already illustrates its supported runtime portion.

**A1 — [test/assign.go:23–27](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/assign.go#L23-L27) — Mutex value assignment. Incompatible as written.**

Expected primary-source cases: L25: accepted assignment of sync.Mutex values; L26: blank discard accepted.

No sync.Mutex/native lock type. Minyar ordinary record assignment aliases, whereas Go struct assignment copies.

Inspected local coverage: [tests/conformance/records/program.min:1–10](../../tests/conformance/records/program.min) — Explicit record and nested List construction; Ada,36,language projections. All fields supplied.

No direct port: core Go syntax/library/type contract absent; related local fixtures are source-only coverage.

**A2 — [test/assign.go:28–32](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/assign.go#L28-L32) — embedded record assignment. Incompatible as written.**

Expected primary-source cases: L30: accepted assignment of T embedding int and sync.Mutex; L31: blank discard accepted.

No embedded fields or native lock; named record assignment shares rather than copies.

Inspected local coverage: [tests/conformance/records/program.min:1–10](../../tests/conformance/records/program.min) — Explicit record and nested List construction; Ada,36,language projections. All fields supplied.

No direct port: core Go syntax/library/type contract absent; related local fixtures are source-only coverage.

**A3 — [test/assign.go:33–37](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/assign.go#L33-L37) — Mutex array assignment. Incompatible as written.**

Expected primary-source cases: L35: accepted assignment of [2]sync.Mutex values; L36: blank discard accepted.

No fixed arrays of sync.Mutex; List assignment shares.

Inspected local coverage: [tests/ownership.py:88–98](../../tests/ownership.py) — List alias/self assignment plus immutable old Text survival after replacement. Does not assert deep List copying.

No direct port: core Go syntax/library/type contract absent; related local fixtures are source-only coverage.

**A4 — [test/assign.go:38–42](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/assign.go#L38-L42) — embedded record array assignment. Incompatible as written.**

Expected primary-source cases: L40: accepted assignment of [2]T values; L41: blank discard accepted.

No embedded/native lock fields or by-value array copying.

Inspected local coverage: [tests/conformance/records/program.min:1–10](../../tests/conformance/records/program.min) — Explicit record and nested List construction; Ada,36,language projections. All fields supplied. [tests/ownership.py:88–98](../../tests/ownership.py) — List alias/self assignment plus immutable old Text survival after replacement. Does not assert deep List copying.

No direct port: core Go syntax/library/type contract absent; related local fixtures are source-only coverage.

**A5 — [test/assign.go:43–46](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/assign.go#L43-L46) — unexported Time composite literal. Incompatible as written.**

Expected primary-source cases: L44: compiler diagnostic regex assignment.*Time.

Foreign library internals, positional struct literal and nil unsupported. Minyar missing named fields is a different diagnostic class.

Inspected local coverage: [tests/bootstrap-records.py:43–56](../../tests/bootstrap-records.py) — Existing missing/duplicate/unknown-field and wrong-type diagnostics. Source only; no bootstrap invocation here.

No direct port: core Go syntax/library/type contract absent; related local fixtures are source-only coverage.

**A6 — [test/assign.go:47–50](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/assign.go#L47-L50) — unknown/private Mutex field literal. Incompatible as written.**

Expected primary-source cases: L48: compiler diagnostic regex (unknown|assignment).*Mutex.

sync.Mutex internals are not Minyar records. Existing unknown-field diagnostics provide related original compiler coverage; do not import this library-specific regex.

Inspected local coverage: [tests/bootstrap-records.py:43–56](../../tests/bootstrap-records.py) — Existing missing/duplicate/unknown-field and wrong-type diagnostics. Source only; no bootstrap invocation here.

No direct port: core Go syntax/library/type contract absent; related local fixtures are source-only coverage.

**A7 — [test/assign.go:51–58](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/assign.go#L51-L58) — pointer dereference assignment. Incompatible as written.**

Expected primary-source cases: L52: empty Mutex constructor address accepted; L53: Mutex local declaration accepted; L54: dereference-to-value assignment accepted; L55: value-to-dereference assignment accepted; L56: x discard accepted; L57: y discard accepted.

No address-taking or dereference. A List-held explicit record replacement is an original shared-reference control, not by-value Mutex assignment.

Inspected local coverage: [tests/conformance/records/program.min:1–10](../../tests/conformance/records/program.min) — Explicit record and nested List construction; Ada,36,language projections. All fields supplied.

P1 only as explicit initialized Minyar shared-reference control.

**A8 — [test/assign.go:59–66](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/assign.go#L59-L66) — repeated short declaration with outer x. Incompatible as written.**

Expected primary-source cases: L62: compiler regex .*x.* repeated on left side of :=|x redeclared in this block.

No multi-target := declaration; replacing with two sequential let declarations changes the diagnostic question. Branch shadowing is separately supported.

Inspected local coverage: [tests/conformance/bindings-and-scope/program.min:1–7](../../tests/conformance/bindings-and-scope/program.min) — Branch-local shadow prints20, then outer11. Related lexical binding coverage.

No direct port: core Go syntax/library/type contract absent; related local fixtures are source-only coverage.

**A9 — [test/assign.go:67–70](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/assign.go#L67-L70) — repeated short declaration without outer a. Incompatible as written.**

Expected primary-source cases: L68: compiler regex .*a.* repeated on left side of :=|a redeclared in this block.

No multi-target := declaration. The Go duplicate target contract is not a request to change Minyar same-scope binding semantics.

Inspected local coverage: [tests/conformance/bindings-and-scope/program.min:1–7](../../tests/conformance/bindings-and-scope/program.min) — Branch-local shadow prints20, then outer11. Related lexical binding coverage.

No direct port: core Go syntax/library/type contract absent; related local fixtures are source-only coverage.

**I1 — [test/if.go:24–28](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/if.go#L24-L28) — main: literal true. Pending runtime subset.**

Expected primary-source cases: L28: count=1; assertequal succeeds silently.

Ordinary Boolean if plus Integer increment directly preserves1. No panic or Go diagnostic port.

In-file helper bodies read: assertequal L11–16.

Inspected local coverage: [tests/regressions.py:191–194](../../tests/regressions.py) — Ordinary Boolean branches return42/7; terminal fail branch and bare return. Different exact count oracles. [tests/conformance/bindings-and-scope/program.min:1–7](../../tests/conformance/bindings-and-scope/program.min) — Branch-local shadow prints20, then outer11. Related lexical binding coverage. [tests/peer-research-swift-statements.py:30–44](../../tests/peer-research-swift-statements.py) — Reject branch-local names in sibling branches and non-Boolean conditions. No Go initializer clause syntax.

P8 gives all exact count oracles; enclosing local/function scope replaces absent initializer clause without changing language semantics.

**I2 — [test/if.go:30–34](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/if.go#L30-L34) — main: literal false. Pending runtime subset.**

Expected primary-source cases: L34: count=0; assertequal succeeds silently.

Ordinary false branch remains skipped; preserves0. No panic or Go diagnostic port.

In-file helper bodies read: assertequal L11–16.

Inspected local coverage: [tests/regressions.py:191–194](../../tests/regressions.py) — Ordinary Boolean branches return42/7; terminal fail branch and bare return. Different exact count oracles. [tests/conformance/bindings-and-scope/program.min:1–7](../../tests/conformance/bindings-and-scope/program.min) — Branch-local shadow prints20, then outer11. Related lexical binding coverage. [tests/peer-research-swift-statements.py:30–44](../../tests/peer-research-swift-statements.py) — Reject branch-local names in sibling branches and non-Boolean conditions. No Go initializer clause syntax.

P8 gives all exact count oracles; enclosing local/function scope replaces absent initializer clause without changing language semantics.

**I3 — [test/if.go:36–40](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/if.go#L36-L40) — main: true with initializer. Pending runtime subset.**

Expected primary-source cases: L40: count=1; assertequal succeeds silently.

Use explicit enclosing function/local one=1 before if; exclude Go initializer scope syntax. No panic or Go diagnostic port.

In-file helper bodies read: assertequal L11–16.

Inspected local coverage: [tests/regressions.py:191–194](../../tests/regressions.py) — Ordinary Boolean branches return42/7; terminal fail branch and bare return. Different exact count oracles. [tests/conformance/bindings-and-scope/program.min:1–7](../../tests/conformance/bindings-and-scope/program.min) — Branch-local shadow prints20, then outer11. Related lexical binding coverage. [tests/peer-research-swift-statements.py:30–44](../../tests/peer-research-swift-statements.py) — Reject branch-local names in sibling branches and non-Boolean conditions. No Go initializer clause syntax.

P8 gives all exact count oracles; enclosing local/function scope replaces absent initializer clause without changing language semantics.

**I4 — [test/if.go:42–47](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/if.go#L42-L47) — main: false with initializer. Pending runtime subset.**

Expected primary-source cases: L47: count=0; assertequal succeeds silently.

Initialize local one before false branch; preserves0; initializer execution itself is not asserted upstream. No panic or Go diagnostic port.

In-file helper bodies read: assertequal L11–16.

Inspected local coverage: [tests/regressions.py:191–194](../../tests/regressions.py) — Ordinary Boolean branches return42/7; terminal fail branch and bare return. Different exact count oracles. [tests/conformance/bindings-and-scope/program.min:1–7](../../tests/conformance/bindings-and-scope/program.min) — Branch-local shadow prints20, then outer11. Related lexical binding coverage. [tests/peer-research-swift-statements.py:30–44](../../tests/peer-research-swift-statements.py) — Reject branch-local names in sibling branches and non-Boolean conditions. No Go initializer clause syntax.

P8 gives all exact count oracles; enclosing local/function scope replaces absent initializer clause without changing language semantics.

**I5 — [test/if.go:49–53](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/if.go#L49-L53) — main: comparison condition. Pending runtime subset.**

Expected primary-source cases: L53: count=1; assertequal succeeds silently.

Integer5<7 is Boolean true; preserves1. No panic or Go diagnostic port.

In-file helper bodies read: assertequal L11–16.

Inspected local coverage: [tests/regressions.py:191–194](../../tests/regressions.py) — Ordinary Boolean branches return42/7; terminal fail branch and bare return. Different exact count oracles. [tests/conformance/bindings-and-scope/program.min:1–7](../../tests/conformance/bindings-and-scope/program.min) — Branch-local shadow prints20, then outer11. Related lexical binding coverage. [tests/peer-research-swift-statements.py:30–44](../../tests/peer-research-swift-statements.py) — Reject branch-local names in sibling branches and non-Boolean conditions. No Go initializer clause syntax.

P8 gives all exact count oracles; enclosing local/function scope replaces absent initializer clause without changing language semantics.

**I6 — [test/if.go:55–61](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/if.go#L55-L61) — main: true else. Pending runtime subset.**

Expected primary-source cases: L61: count=1; assertequal succeeds silently.

Only true arm increments; preserves1. No panic or Go diagnostic port.

In-file helper bodies read: assertequal L11–16.

Inspected local coverage: [tests/regressions.py:191–194](../../tests/regressions.py) — Ordinary Boolean branches return42/7; terminal fail branch and bare return. Different exact count oracles. [tests/conformance/bindings-and-scope/program.min:1–7](../../tests/conformance/bindings-and-scope/program.min) — Branch-local shadow prints20, then outer11. Related lexical binding coverage. [tests/peer-research-swift-statements.py:30–44](../../tests/peer-research-swift-statements.py) — Reject branch-local names in sibling branches and non-Boolean conditions. No Go initializer clause syntax.

P8 gives all exact count oracles; enclosing local/function scope replaces absent initializer clause without changing language semantics.

**I7 — [test/if.go:63–69](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/if.go#L63-L69) — main: false else. Pending runtime subset.**

Expected primary-source cases: L69: count=-1; assertequal succeeds silently.

Only else arm decrements; preserves-1. No panic or Go diagnostic port.

In-file helper bodies read: assertequal L11–16.

Inspected local coverage: [tests/regressions.py:191–194](../../tests/regressions.py) — Ordinary Boolean branches return42/7; terminal fail branch and bare return. Different exact count oracles. [tests/conformance/bindings-and-scope/program.min:1–7](../../tests/conformance/bindings-and-scope/program.min) — Branch-local shadow prints20, then outer11. Related lexical binding coverage. [tests/peer-research-swift-statements.py:30–44](../../tests/peer-research-swift-statements.py) — Reject branch-local names in sibling branches and non-Boolean conditions. No Go initializer clause syntax.

P8 gives all exact count oracles; enclosing local/function scope replaces absent initializer clause without changing language semantics.

**I8 — [test/if.go:71–80](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/if.go#L71-L80) — main: initializer and body shadow. Pending runtime subset.**

Expected primary-source cases: L80: count=-1; assertequal succeeds silently.

Explicit local t=1 available to both branches; inner t=7 in skipped true arm. Exclude initializer clause extent; do not leak a true-arm binding into else. No panic or Go diagnostic port.

In-file helper bodies read: assertequal L11–16.

Inspected local coverage: [tests/regressions.py:191–194](../../tests/regressions.py) — Ordinary Boolean branches return42/7; terminal fail branch and bare return. Different exact count oracles. [tests/conformance/bindings-and-scope/program.min:1–7](../../tests/conformance/bindings-and-scope/program.min) — Branch-local shadow prints20, then outer11. Related lexical binding coverage. [tests/peer-research-swift-statements.py:30–44](../../tests/peer-research-swift-statements.py) — Reject branch-local names in sibling branches and non-Boolean conditions. No Go initializer clause syntax.

P8 gives all exact count oracles; enclosing local/function scope replaces absent initializer clause without changing language semantics.

**I9 — [test/if.go:82–92](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/if.go#L82-L92) — main: outer binding and body shadow. Pending runtime subset.**

Expected primary-source cases: L92: count=-1; assertequal succeeds silently.

Outer t=1 is used by else while skipped true arm declares distinct t=7. Existing lexical scopes preserve-1. No panic or Go diagnostic port.

In-file helper bodies read: assertequal L11–16.

Inspected local coverage: [tests/regressions.py:191–194](../../tests/regressions.py) — Ordinary Boolean branches return42/7; terminal fail branch and bare return. Different exact count oracles. [tests/conformance/bindings-and-scope/program.min:1–7](../../tests/conformance/bindings-and-scope/program.min) — Branch-local shadow prints20, then outer11. Related lexical binding coverage. [tests/peer-research-swift-statements.py:30–44](../../tests/peer-research-swift-statements.py) — Reject branch-local names in sibling branches and non-Boolean conditions. No Go initializer clause syntax.

P8 gives all exact count oracles; enclosing local/function scope replaces absent initializer clause without changing language semantics.

## Original existing-syntax controls

All controls are proposals only, with exact expected values rather than observations. None implements a missing peer feature. P4 identifies related already-covered contracts and requires a demonstrated gap before new cases.

**P1 — Shared explicit records and replacement.**

Use explicit initialized Cell records in local List and owner record; check1 then123 after replacement, and owner List values[1,2],[3,4],[5,6] across direct and helper replacement. Construct Foo values(3,4),(2,3) explicitly. Keep old element/List alias across replacement and observe its unchanged old value.

Expected: 1,123; ordered pairs1,2 then3,4 then5,6; Foo fields3,4,2,3; saved old element1 and old pair1,2 survive.

Related records/replacement lifetime fixtures exist; exact peer values and full/temporary replacement sequence are pending. No implicit copies, globals, defaults or pointers.

**P2 — Literal arguments, contextual indexing and ordered values.**

Use literal and runtime two=2 in List argument helpers, with and without Boolean true; check every1,2,3. Check scalar lists[42,56,54], one-element2, owner[10,20], helper123 and[123,456,123,456]. Select index via ordinary if from true/false and read170/85.

Expected: Exact lengths and every scalar as listed; helper reads123; selected values170,85.

Source literal/effect/parameter fixtures already cover related syntax. New values are original runtime projections; no width truncation boundary, tuple, pointer or compile-time inference claim.

**P3 — Ragged nested values and explicit sharing controls.**

Build typed nested cases [[[1]],[[2,3]],[[4],[5,6,7]]], plus cases2 [[1],[2,3]]. Check all peer lengths/leaves. Build two separately initialized rows of ten11s and a separate deliberately shared-row control; mutate one and distinguish independent from shared rows. Read nested Cell15 and Text rows[hello],[world,hello].

Expected: All ragged lengths/leaves in Z26; selected repeated value11; mutation affects only fresh row, both shared positions; Cell15 and first Text row length1/hello.

Existing dynamic row independence and nested read fixtures do not cover this exact ragged topology/shared contrast. Mutation controls are original additions, not inferred upstream copy assertions.

**P4 — Empty runtime containers and no sentinel.**

Reuse typed empty Integer List/Bytes length0 and negative index-at-length contracts; if future Bytes companion is needed inspect its diagnostic fixtures first. For runtime initialized length1 value42, index1 remains invalid.

Expected: Runtime empty lengths0; List index0/length stops with current bounds diagnostic; length1 value42 is valid only at0.

Existing empty/bounds source fixtures cover the List contract. No redundant port or new diagnostic proposed without a concrete gap; sentinel comparisons remain incompatible.

**P5 — Unused initializer effects and ordered trace.**

A helper on shared Integer state increments then returns0; bind an unused List containing two calls and check state2. Separately four helpers add1,2,4,8 and return each value; check exact list and state15. Add decimal trace for order1,2,3,4, so order is independently observed.

Expected: Unused literal state2; [1,2,4,8], state15, ordered trace1234.

Existing used literal and record effects cover left-to-right execution; unused literal effect preservation and exact weighted trace remain narrow original additions. Upstream state2/15 alone does not assert ordering.

**P6 — Shared row binding versus explicit snapshot.**

Start initialized nested rows with chosen slot0; bind alias=x[0]; create fresh copied row by explicit scalar iteration into a new Integer List before mutation; set source chosen slot15. Check alias15, explicit snapshot0. Replace the source outer position, drop local source references, and check retained alias15/snapshot0.

Expected: Plain alias15; fresh snapshot0; both retained values remain15/0 after source replacement.

Zig asserts0 from an implicit value copy; this Minyar contrast follows current shared ownership. Existing dynamic independent rows/managed projection capture are related, but do not assert this exact alias-versus-explicit-snapshot contrast.

**P7 — Scalar filling and record construction versus sharing.**

Fill ten Integer values123. Construct ten fresh Cell{x:10} records and check fields individually; separately add the same Cell ten times, mutate its x and observe all entries. Mutation of one fresh cell must preserve other fresh cells.

Expected: Ten123 values; ten initial fields10; one fresh mutation affects only its cell; one deliberately shared record mutation affects every shared position.

Upstream structural equality does not assert alias independence. Minyar record equality unsupported, so field checks and explicit construction/sharing are required; no splat operator, generics or comptime.

**P8 — Exact branch counts and scoped explicit initializer.**

Preserve all Go if.go count oracles in ordinary Minyar if/else. Put initializer values in an explicit helper/local scope; check outer t1 remains1 while branch-local t7 is available only in its own arm. An original effectful initializer can count one call before a false condition; no initializer-clause syntax is added.

Expected: Counts1,0,1,0,1,1,-1,-1,-1; outer t1; optional original initializer call count1.

Existing branch-return, shadow and sibling rejection fixtures cover related behavior; exact count sequence is pending. Effectful initializer is an original extension, not an upstream assertion.

## Provenance and review limits

| Immutable primary file | SHA256 | License |
| --- | --- | --- |
| [zig test/behavior/array.zig](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/array.zig) | `dab114e7be1a113cdd16b523c4a35825f7f95724aaa79dd08cd8d5e6499eebbd` | MIT |
| [go test/assign.go](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/assign.go) | `7e70e835c60a1d799f73ebb945ed4c7ef8b1dce91016c7278f451a7b864a758f` | BSD-3-Clause |
| [zig LICENSE](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/LICENSE) | `5c537d6853e005298a285d508cff9ac7192cea23576c840d485b2b586a7ff177` | MIT |
| [go LICENSE](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/LICENSE) | `911f8f5782931320f5b8d1160a76365b83aea6447ee6c04fa6d5591467db9dad` | BSD-3-Clause |
| [go test/if.go](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/if.go) | `4f0432541f84b9da481f7ddef108edea8704468cb45cead41f80a76a14c0b7d8` | BSD-3-Clause |
| [zig lib/std/testing.zig](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/lib/std/testing.zig) | `089ad53ec22c7d22b5707dbf2935ba2ee2cb256465ce654151507f53548a9236` | MIT |
| [zig lib/std/meta.zig](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/lib/std/meta.zig) | `3cf9b3eb6c6b6f9b101f06f0562a4071c81a5fbc6de63d8197e837e10cedfc40` | MIT |
| [zig lib/std/mem.zig](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/lib/std/mem.zig) | `eadbec0169898b15b1c066dec393b314f5c4bbc0a0ebbb3c940bd9f70a9e92c3` | MIT |
| [zig lib/std/debug.zig](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/lib/std/debug.zig) | `7eb5226c116028906ee3d87abcc20506fc3ac0fe71659b49e875cf980e8f1096` | MIT |

Imported oracle helpers are selectively read support bodies in testing.zig, meta.zig, mem.zig and debug.zig, including sentinel and structural equality behavior. Their remaining implementation, standard-library tests and transitive diagnostic/utility machinery are not exhaustive reviews and receive no peer group credit. See the exact helper spans in the structured record.

All selected upstream and supporting source/license fetches succeeded. No new upstream unavailability or content/service restriction occurred. The prior restricted Rust resource was neither retried nor routed around. Missing optional local booleans fixture was skipped; actual branch/scope fixtures supplied coverage. Stopped integration/literature execution lanes were not resumed.

[Record consistency checks](../../evidence/peer-readonly/go-zig-round3/document-checks.json) account for 112 Zig assertion call sites, 24 attached in-file helper bodies, 4 Go error annotations and 9 Go branch assertion calls. These are grouped source sites, not execution counts. Checks verify names, spans, guards, exact hashes and ledger consistency without running any test/compiler/peer program.

Only peer-readonly-go-zig-round3.md/.json and evidence/peer-readonly/go-zig-round3 were authored. Existing dirty workspace was preserved by this lane. No production/build/test files, central manifests, commits, installations, compilation, timings, soak or application cohorts were changed or run. Current campaign work in other lanes may change unrelated files concurrently.

No selected-file source review remains pending. All runtime projections and proposed original controls remain unimplemented/unexecuted; incompatible core contracts stay excluded. Unselected peer files remain unreviewed. Campaign completion remains the parent’s responsibility and retains its earliest authorized completion time in the campaign README.
