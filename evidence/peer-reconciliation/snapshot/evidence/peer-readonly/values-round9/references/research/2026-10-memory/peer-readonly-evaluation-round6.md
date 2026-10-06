# Read-only evaluation and type-identity peer review, round6

Source review is complete for Go `test/convert.go` L1–46 and Zig `test/behavior/eval.zig` L1–1759. The retained raw bytes were hashed against immutable source provenance before review; no refetch. All selected lines, helpers, backend skips, comptime cases and dormant bodies were read. Zero selected lines remain unread. These round5 retrieval-only candidates receive semantic-review status here.

**114 heterogeneous groups**: 110 Zig test blocks, 1 Zig module comptime block, 3 Go reflected-type predicates. Dispositions: **25 adapt pending, 1 adopt pending, 88 incompatible**. Zero exact peer units are credited already covered; related local fixtures have explicit limits. **203 Zig oracle-call source sites, 9 compile-error sites, 98 guards, 3 Go failure predicates** are attributed once. Wrapper/helper call sites are separate source sites, not extra dynamic assertion executions/ports.

Two original narrow proposals remain unimplemented/unexecuted: ordered effects before a decisive Boolean literal/helper, and binary64 arithmetic rounding at 2^53. No tests, compiles, installations, commits, timings, subagents, production/test/build edits or central-manifest edits occurred. The campaign earliest completion remains **2026-10-04 06:54:29 UTC**; bounded-round completion does not complete the campaign.

## Primary sources, attribution and immutable hashes

The [source manifest](../../evidence/peer-readonly/evaluation-round6/source-manifest.json) retains raw bytes, immutable URLs and original retrieval provenance. Go source Copyright 2009 The Go Authors and BSD notice are preserved with the BSD-3-Clause repository license; Zig retains MIT/Expat with Copyright Zig contributors. Full licenses/conditions remain intact. Support snapshots are selective helper reviews, not whole-file test review.

| Primary pinned source | SHA-256 | Bytes / physical lines |
| --- | --- | --- |
| [Go test/convert.go](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/convert.go) | `434f08deff4429782504c04d85c71fdee659eb59c1c135a2b2da0f056bd5f1a6` | 833 / 46 |
| [Zig test/behavior/eval.zig](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig) | `0177fbf3b6439bfcbd8b4a8615395d244e89461d3cb78e7a408ba7ff76d31bfe` | 46475 / 1759 |
| [Go LICENSE](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/LICENSE) | `911f8f5782931320f5b8d1160a76365b83aea6447ee6c04fa6d5591467db9dad` | 1453 / 27 |
| [Zig LICENSE](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/LICENSE) | `5c537d6853e005298a285d508cff9ac7192cea23576c840d485b2b586a7ff177` | 1080 / 21 |
| [Zig lib/std/testing.zig](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/lib/std/testing.zig) | `089ad53ec22c7d22b5707dbf2935ba2ee2cb256465ce654151507f53548a9236` | 48207 / 1251 |
| [Zig lib/std/debug.zig](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/lib/std/debug.zig) | `7eb5226c116028906ee3d87abcc20506fc3ac0fe71659b49e875cf980e8f1096` | 69500 / 1782 |
| [Zig lib/std/mem.zig](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/lib/std/mem.zig) | `eadbec0169898b15b1c066dec393b314f5c4bbc0a0ebbb3c940bd9f70a9e92c3` | 184945 / 4840 |
| [Zig lib/std/meta.zig](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/lib/std/meta.zig) | `3cf9b3eb6c6b6f9b101f06f0562a4071c81a5fbc6de63d8197e837e10cedfc40` | 39789 / 1251 |

Go commit: `56ebf80e57db9f61981fc0636fc6419dc6f68eda`. Zig commit: `3db960767d12b6214bcf43f1966a037c7a586a12`.

## Findings and limits

- Go’s filename/comment does not make this numeric conversion coverage: all checks compare reflected type names. f/g are never invoked and arithmetic values are unasserted. Minyar has no reflected named-derived-type contract.
- Type/layout/comptime contracts remain excluded: no generic type factory, type-valued field, optional, arbitrary-width Integer, raw/aligned pointer, sentinel or comptime evaluator is assumed. Constants are single literals.
- Runtime projections preserve specified values using current syntax, excluding peer phase/lowering semantics. Binary64 +1 at 2^53 transfers with explicit Float operands. f32 +1 at 2^24 and f128 at 2^113 do not.
- Identical effects or commutative sums prove counts/values, not order. P1 uses independent ordered IDs. Existing literal-order, row-snapshot and producer-once controls are excluded from new proposals.
- Repeated Zig rows are recursively initialized by-value arrays, compared structurally over all 16 cells. Minyar rows share mutable references, Bytes.slice copies, Text views share immutable backing. Matching values do not prove copy/lifetime equivalence.
- `container level const and var have unique addresses` checks p.x==S.c.x before/after S.v.x=2, without independently asserting post-mutation c.x==1 or v.x==2. The explicit equality oracle alone does not establish the title’s full independence claim.
- Runtimefalse L1407–1417 never reaches its assertion. L1448–1463 andL1465–1482 are unconditionally skipped. Bodies remain source-reviewed, with zero execution/pass credit.
- Pointer identity, discarded allocations and global memoization have no retained-owner/destructor oracle. The string memoization commentL615–626 says the specification guarantee is unsettled.

## Correction to prior runtime evidence

Immutable [run-crettoqb results](evidence/runtime-peer-projections/run-crettoqb/results.json) have 24 real executions: 16 native links at O0/O2 and 8 sanitized generated links effectively O1. The appended sanitizer-O1 overrode requested flags. Earlier O0/O2 sanitizer wording was too broad. Historical individual argv were absent; effective modes derive from archived runner/helper ordering. The [correction record](runtime-peer-optimization-correction.json) is separately retained; old snapshots/ledgers remain unchanged.

Durable [run-7m86apqr results](evidence/runtime-peer-projections/run-7m86apqr/results.json) have status passed: 6 methods × 3 configurations × 2 generated link levels =36 executions. Documentary checks verify 18 last-O0 and 18 last-O2 actual link flags, saved successful outputs/status and sanitizer ASan definition counts. Native runtime C objects remain O2; sanitized runtime C objects O1. The [current runtime report](runtime-peer-projections.md) disclaims generated UBSan/LSan/full-suite validation. Added NaN relation/negation and source-subnormal methods concern round5; no low-mask implementation inferred. These are separate runtime-lane originals, not literal peer ports or round6 executions.

Initial four-method fixture bytes remain frozen; correction/latest result/report have a separate [manifest](../../evidence/peer-readonly/evaluation-round6/corrected-runtime-manifest.json). Concurrent reference changes are recorded in JSON. No unrelated runtime audit/measurement is reinterpreted here.

## Frozen local source coverage

See [local manifest](../../evidence/peer-readonly/evaluation-round6/local-manifest.json). Spans establish inspected source assertions/expected bytes only, not a new pass or exact peer phase/type/copy coverage.

| ID | Source/test spans | Property and limitation |
| --- | --- | --- |
| numbers | `tests/conformance/numbers-and-comparisons/program.min` L1–9; expected tests/conformance/numbers-and-comparisons/expected.stdout L1–9 | Signed64 arithmetic/comparisons, not named/reflected/narrow types. |
| loops | `tests/conformance/loops-and-assignment/program.min` L9–15, L45–64; expected tests/conformance/loops-and-assignment/expected.stdout L1–1, L14–16 | Runtime for/while break/continue, nested innermost break; no labeled exits/comptime quotas. |
| records | `tests/conformance/loops-and-assignment/program.min` L1–7, L26–43; expected tests/conformance/loops-and-assignment/expected.stdout L8–13 | Shared record scalar/Text mutation via functions/outer records, health15/99, blocks42; no identical read helper on same record across mutation. |
| literal | `tests/recursive-data.py` L148–184 | Left-to-right List values1/2/3; earlier projected record retains old! during replacement. No fixed-array operators/static copies. |
| row | `tests/memory-research-peer-projections.py` L63–80 | Shared row vs explicit scalar snapshot survives replacement, exact15,0,5,15,0,3,3. No implicit by-value record/array copy. |
| short | `tests/peer-research-semantics.py` L80–97 | Basic \|\|/&& skip traps and ordered IDs1,2,3,4; decisive literal examples place literal FIRST, not after mandatory effects. |
| short-temp | `tests/adversarial.py` L145–161 | Boolean producer temporary Text, precedence and IDs3,4,5,6,8; no middle decisive literal after two mandatory effects. |
| floats | `tests/conformance/floats-and-bits/program.min` L1–28; expected tests/conformance/floats-and-bits/expected.stdout L1–21 | Binary64 ordinary arithmetic/NaN equality/Float List; no2^53 addition tie or f32/f128 phase evaluation. |
| bits | `tests/conformance/floats-and-bits/program.min` L29–38; expected tests/conformance/floats-and-bits/expected.stdout L22–29 | Small &,\|,^,~0=-1,1<<10,-16>>2,wrapping; no wide or type-dependent contract. |
| bytes | `tests/conformance/bytes/program.min` L1–38; expected tests/conformance/bytes/expected.stdout L1–16 | Zero-filled/shared Bytes, endian storage, iteration and slice values; this fixture does not assert slice independence. No writable view/sentinel/layout. |
| text | `tests/conformance/text-and-lists/program.min` L1–12; expected tests/conformance/text-and-lists/expected.stdout L1–6 | Content equality,indexing,slicing,Lists; no pointer identity/type reflection/factory. |
| existing-projections | `tests/memory-research-peer-projections.py` L41–153 | Four prior originals in initial frozen fixture; execution records separate. Duplicates excluded. |
| list-targets | `tests/list-access.py` L68–111 | Index/RHS growth,receiver capture,Text compound RHS lifetime; not raw-pointer/phase equivalence. |
| target-order | `tests/compiler-hardening.py` L292–320 | Field/Bytes receiver captured before effects; not type memoization/global purity. |
| local-oracle | `tests/regressions.py` L54–65 | When invoked, asserts status/exact UTF8 stdout at O0/O2; read only this round. Prior sanitizer flags correction separately disclosed. |
| near2^53-format | `tests/runtime-numeric.py` L25–26, L36–61, L64–75 | Goldens at 2^53 and neighbor bit patterns feed formatter; no language +1/+2 boundary arithmetic. |
| near2^53-label | `tests/numeric-formatting.min` L1–19 | Record/Text formatting includes2^53-1, not2^53+1/+2 addition rounding. |

## Complete semantic ledger

Every selected unit below has manually authored outcomes and compatibility reasoning. The [JSON ledger](peer-readonly-evaluation-round6.json) retains exact source expressions, per-site dispositions, guard text/line, comptime lines, helper spans, failure alternatives and direct local coverage spans. A pending group projection does not hide excluded comptime/compileError/typed-width sites. No arbitrary prefixes are selected.

### Z1 — compile time recursion

[test/behavior/eval.zig L7–9](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L7-L9). **adapt_pending**.

Expected: fibonacci base x<=1 returns1; fibonacci(7)=21 gives global array length21.

Minyar: Ordinary recursive Integer function preserves21; excludes comptime array sizing.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L8 | adapt_pending | `try expect(some_data.len == 21);` |

Related local source: loops: tests/conformance/loops-and-assignment/program.min L9–15, L45–64.

Additional in-file helper/declaration extents: L10–14.

### Z2 — static add one

[test/behavior/eval.zig L20–25](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L20-L25). **incompatible_as_written**.

Expected: force-unwrap ?i32 input1234 then+1 gives1235 as global value.

Minyar: Optional/global computed initialization absent.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L24 | incompatible_as_written | `try expect(should_be_1235 == 1235);` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

Additional in-file helper/declaration extents: L16–19.

Skip guards: L21 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L22 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.

### Z3 — inlined loop

[test/behavior/eval.zig L27–33](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L27-L33). **adapt_pending**.

Expected: inline comptime while i0..5 inclusive yields sum15.

Minyar: Ordinary while i<=5,sum15; no inline/comptime lowering or order inference.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L32 | adapt_pending | `try expect(sum == 15);` |

Related local source: loops: tests/conformance/loops-and-assignment/program.min L9–15, L45–64.

### Z4 — inline variable gets result of const if

[test/behavior/eval.zig L42–45](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L42-L45). **adapt_pending**.

Expected: gimme1or2 comptime Boolean selects x1/y2 into comptime z; true1,false2.

Minyar: Ordinary if with explicit return preserves values; no comptime parameter/address.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L43 | adapt_pending | `try expect(gimme1or2(true) == 1);` |
| L44 | adapt_pending | `try expect(gimme1or2(false) == 2);` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

Additional in-file helper/declaration extents: L35–41.

### Z5 — static function evaluation

[test/behavior/eval.zig L47–49](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L47-L49). **adapt_pending**.

Expected: staticAdd(1,2) globally evaluated yields3.

Minyar: Ordinary function call yields3; literal-only constants cannot store call result.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L48 | adapt_pending | `try expect(statically_added_number == 3);` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

Additional in-file helper/declaration extents: L50–53.

### Z6 — const expr eval on single expr blocks

[test/behavior/eval.zig L55–58](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L55-L58). **adapt_pending**.

Expected: true conditional labeled blocks return3 at runtime and comptime; false x branch unasserted.

Minyar: Function if/return3 value projection; no block/conditional expression or comptime.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L56 | adapt_pending | `try expect(constExprEvalOnSingleExprBlocksFn(1, true) == 3);` |
| L57 | incompatible_as_written | `comptime assert(constExprEvalOnSingleExprBlocksFn(1, true) == 3);` |

Related local source: loops: tests/conformance/loops-and-assignment/program.min L9–15, L45–64.

Additional in-file helper/declaration extents: L60–70.

### Z7 — constant expressions

[test/behavior/eval.zig L72–78](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L72-L78). **incompatible_as_written**.

Expected: [array_size20]u8 has sizeof(TYPE)=20; contents undefined/unread.

Minyar: List length20 does not prove type layout.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L77 | incompatible_as_written | `try expect(@sizeOf(@TypeOf(array)) == 20);` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

Additional in-file helper/declaration extents: L79–79.

Skip guards: L73 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.

### Z8 — inlined block and runtime block phi

[test/behavior/eval.zig L93–107](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L93-L107). **adapt_pending**.

Expected: max(bool,a,b) uses or; TT/TF/FT true, FF false at runtime and comptime.

Minyar: Boolean || function preserves four runtime values; generic specialization/comptime excluded per-site.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L96 | adapt_pending | `try expect(letsTryToCompareBools(true, true));` |
| L97 | adapt_pending | `try expect(letsTryToCompareBools(true, false));` |
| L98 | adapt_pending | `try expect(letsTryToCompareBools(false, true));` |
| L99 | adapt_pending | `try expect(!letsTryToCompareBools(false, false));` |
| L102 | incompatible_as_written | `try expect(letsTryToCompareBools(true, true));` |
| L103 | incompatible_as_written | `try expect(letsTryToCompareBools(true, false));` |
| L104 | incompatible_as_written | `try expect(letsTryToCompareBools(false, true));` |
| L105 | incompatible_as_written | `try expect(!letsTryToCompareBools(false, false));` |

Related local source: short: tests/peer-research-semantics.py L80–97.

Additional in-file helper/declaration extents: L81–92.

Skip guards: L94 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.

### Z9 — eval @setRuntimeSafety at compile-time

[test/behavior/eval.zig L109–112](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L109-L112). **incompatible_as_written**.

Expected: comptime fnWithSetRuntimeSafety enables safety then returns1234.

Minyar: Runtime1234 would erase runtime-safety builtin phase contract.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L111 | incompatible_as_written | `try expect(result == 1234);` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

Additional in-file helper/declaration extents: L114–117.

### Z10 — compile-time downcast when the bits fit

[test/behavior/eval.zig L119–125](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L119-L125). **incompatible_as_written**.

Expected: comptime u16 255 intCast to u8 stays255.

Minyar: No narrow checked casts or comptime.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L123 | incompatible_as_written | `try expect(byte == 255);` |

Related local source: bits: tests/conformance/floats-and-bits/program.min L29–38.

### Z11 — pointer to type

[test/behavior/eval.zig L127–137](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L127-L137). **incompatible_as_written**.

Expected: type T i32; ptr type *type; indirect write f32 changes T and *T.

Minyar: Types/type pointers are not local values.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L130 | incompatible_as_written | `try expect(T == i32);` |
| L132 | incompatible_as_written | `try expect(@TypeOf(ptr) == *type);` |
| L134 | incompatible_as_written | `try expect(T == f32);` |
| L135 | incompatible_as_written | `try expect(*T == *f32);` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

### Z12 — a type constructed in a global expression

[test/behavior/eval.zig L139–152](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L139-L152). **incompatible_as_written**.

Expected: global type factory creates struct [10]u8; writes10,11,12; ptrCast reads same.

Minyar: List field reads erase global type construction and raw pointer cast.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L149 | incompatible_as_written | `try expect(ptr[0] == 10);` |
| L150 | incompatible_as_written | `try expect(ptr[1] == 11);` |
| L151 | incompatible_as_written | `try expect(ptr[2] == 12);` |

Related local source: records: tests/conformance/loops-and-assignment/program.min L1–7, L26–43.

Additional in-file helper/declaration extents: L154–159.

Skip guards: L140 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L141 `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest;`; L142 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z13 — comptime function with the same args is memoized

[test/behavior/eval.zig L161–166](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L161-L166). **incompatible_as_written**.

Expected: MakeType(i32) type identity equals itself, differs MakeType(f64).

Minyar: No anonymous generic type factory/memoization identity.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L163 | incompatible_as_written | `try expect(MakeType(i32) == MakeType(i32));` |
| L164 | incompatible_as_written | `try expect(MakeType(i32) != MakeType(f64));` |

Related local source: records: tests/conformance/loops-and-assignment/program.min L1–7, L26–43.

Additional in-file helper/declaration extents: L168–172.

### Z14 — try to trick eval with runtime if

[test/behavior/eval.zig L174–176](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L174-L176). **incompatible_as_written**.

Expected: inline10 iterations with runtime conditional discarded; returns comptime counter10.

Minyar: Runtime count would not prove mixed-phase evaluation.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L175 | incompatible_as_written | `try expect(testTryToTrickEvalWithRuntimeIf(true) == 10);` |

Related local source: loops: tests/conformance/loops-and-assignment/program.min L9–15, L45–64.

Additional in-file helper/declaration extents: L178–185.

### Z15 — @setEvalBranchQuota

[test/behavior/eval.zig L187–198](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L187-L198). **incompatible_as_written**.

Expected: quota1002 allows1001 iterations plus expect; sum500500.

Minyar: No comptime branch quota; runtime triangular sum changes target.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L196 | incompatible_as_written | `try expect(sum == 500500);` |

Related local source: loops: tests/conformance/loops-and-assignment/program.min L9–15, L45–64.

### Z16 — constant struct with negation

[test/behavior/eval.zig L200–202](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L200-L202). **incompatible_as_written**.

Expected: first Vertex.x equals f32 rounding of-0.6; remaining fields/vertices unasserted.

Minyar: Float is binary64; cannot claim binary32 evaluation by substituting same decimal.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L201 | incompatible_as_written | `try expect(vertices[0].x == @as(f32, -0.6));` |

Related local source: floats: tests/conformance/floats-and-bits/program.min L1–28.

Additional in-file helper/declaration extents: L203–232.

### Z17 — statically initialized list

[test/behavior/eval.zig L234–241](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L234-L241). **adapt_pending**.

Expected: makePoint globals have fields(1,2),(3,4), all four checked.

Minyar: Local named records/List preserve four fields; no static evaluation/value-array copy proof.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L237 | adapt_pending | `try expect(static_point_list[0].x == 1);` |
| L238 | adapt_pending | `try expect(static_point_list[0].y == 2);` |
| L239 | adapt_pending | `try expect(static_point_list[1].x == 3);` |
| L240 | adapt_pending | `try expect(static_point_list[1].y == 4);` |

Related local source: records: tests/conformance/loops-and-assignment/program.min L1–7, L26–43.

Additional in-file helper/declaration extents: L242–255.

Skip guards: L235 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.

### Z18 — statically initialized array literal

[test/behavior/eval.zig L257–260](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L257-L260). **adapt_pending**.

Expected: global[1,2,3,4] assigned to y by value, only y[3]==4.

Minyar: Local List last4 value projection; no later mutation, so no copy-independence proof.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L259 | adapt_pending | `try expect(y[3] == 4);` |

Related local source: literal: tests/recursive-data.py L148–184.

Additional in-file helper/declaration extents: L261–261.

### Z19 — comptime iterate over fn ptr list

[test/behavior/eval.zig L303–307](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L303-L307). **incompatible_as_written**.

Expected: comptime filter names first byte then function list calls: t start1->6,o start0->1,w start99->99.

Minyar: No function-valued fields/inline pointer list; commutative additions do not prove order.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L304 | incompatible_as_written | `try expect(performFn('t', 1) == 6);` |
| L305 | incompatible_as_written | `try expect(performFn('o', 0) == 1);` |
| L306 | incompatible_as_written | `try expect(performFn('w', 99) == 99);` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

Additional in-file helper/declaration extents: L263–301.

### Z20 — create global array with for loop

[test/behavior/eval.zig L309–312](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L309-L312). **adapt_pending**.

Expected: global builder assigns index squared; only index5=25,index9=81 checked.

Minyar: Local Integer List builder with for/add preserves values; compile-time global excluded.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L310 | adapt_pending | `try expect(global_array[5] == 5 * 5);` |
| L311 | adapt_pending | `try expect(global_array[9] == 9 * 9);` |

Related local source: loops: tests/conformance/loops-and-assignment/program.min L9–15, L45–64.

Additional in-file helper/declaration extents: L314–320.

### Z21 — @setEvalBranchQuota at same scope as generic function call

[test/behavior/eval.zig L339–343](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L339-L343). **incompatible_as_written**.

Expected: generateTable1010 entries index cast; scoped quota5000, comptime table; slot2==2.

Minyar: No generic quota/phase table generation.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L342 | incompatible_as_written | `try expect(doesAlotT(u32, 2) == 2);` |

Related local source: loops: tests/conformance/loops-and-assignment/program.min L9–15, L45–64.

Additional in-file helper/declaration extents: L322–337.

Skip guards: L340 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.

### Z22 — comptime modification of const struct field

[test/behavior/eval.zig L351–358](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L351-L358). **incompatible_as_written**.

Expected: comptime res copies diamond_info.version0; mutate res1; original0/copy1 independently asserted.

Minyar: Minyar record assignment aliases, so same spelling changes original; explicit reconstruction different contract.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L355 | incompatible_as_written | `try expect(diamond_info.version == 0);` |
| L356 | incompatible_as_written | `try expect(res.version == 1);` |

Related local source: row: tests/memory-research-peer-projections.py L63–80.

Additional in-file helper/declaration extents: L345–349.

### Z23 — refer to the type of a generic function

[test/behavior/eval.zig L360–364](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L360-L364). **incompatible_as_written**.

Expected: Func generic function value assigned doNothingWithType and called i32; no value assertion.

Minyar: Successful type-value/function-value analysis only, unavailable locally.

No value assertion: successful analysis/driver completion is the selected oracle.

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

Additional in-file helper/declaration extents: L366–368.

### Z24 — zero extend from u0 to u1

[test/behavior/eval.zig L370–375](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L370-L375). **incompatible_as_written**.

Expected: u0 zero widens u1, equals0.

Minyar: No zero/one-bit Integer types; ordinary0 not equivalent.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L374 | incompatible_as_written | `try expect(zero_u1 == 0);` |

Related local source: bits: tests/conformance/floats-and-bits/program.min L29–38.

### Z25 — return 0 from function that has u0 return type

[test/behavior/eval.zig L377–388](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L377-L388). **incompatible_as_written**.

Expected: foo_zero()->u0 zero; comptime conditional compileError if nonzero.

Minyar: No zero-bit return type or phase rejection oracle.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L385 | incompatible_as_written | `@compileError("test failed");` |

Related local source: bits: tests/conformance/floats-and-bits/program.min L29–38.

### Z26 — statically initialized struct

[test/behavior/eval.zig L390–395](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L390-L395). **adapt_pending**.

Expected: static record starts x13,ytrue; x+=1 ->14; y not checked.

Minyar: Ordinary named record mutation14; static initialization excluded.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L394 | adapt_pending | `try expect(st_init_str_foo.x == 14);` |

Related local source: records: tests/conformance/loops-and-assignment/program.min L1–7, L26–43.

Additional in-file helper/declaration extents: L396–403.

Skip guards: L391 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.

### Z27 — inline for with same type but different values

[test/behavior/eval.zig L405–413](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L405-L413). **incompatible_as_written**.

Expected: inline type list[2]u8,[1]u8,[2]u8 sums array lengths5; undefined data unread.

Minyar: No heterogeneous type iteration/fixed-array metadata.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L412 | incompatible_as_written | `try expect(res == 5);` |

Related local source: loops: tests/conformance/loops-and-assignment/program.min L9–15, L45–64.

### Z28 — f32 at compile time is lossy

[test/behavior/eval.zig L415–417](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L415-L417). **incompatible_as_written**.

Expected: f32 at2^24 plus1 rounds back2^24.

Minyar: Binary64 would give16777217, so incompatible direct Float port.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L416 | incompatible_as_written | `try expect(@as(f32, 1 << 24) + 1 == 1 << 24);` |

Related local source: floats: tests/conformance/floats-and-bits/program.min L1–28.

### Z29 — f64 at compile time is lossy

[test/behavior/eval.zig L419–421](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L419-L421). **adopt_pending**.

Expected: f64 at2^53 plus1 rounds back2^53, equality true.

Minyar: Explicit Float9007199254740992.0+1.0 equality preserves binary64 property; source arithmetic coverage pending.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L420 | adopt_pending | `try expect(@as(f64, 1 << 53) + 1 == 1 << 53);` |

Related local source: floats: tests/conformance/floats-and-bits/program.min L1–28.

### Z30 — anonymous f128 equality

[test/behavior/eval.zig L423–425](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L423-L425). **incompatible_as_written**.

Expected: comptime f128 exactly represents2^113=10384593717069655257060992658440192.

Minyar: No Float128/113-bit shift.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L424 | incompatible_as_written | `comptime assert(@as(f128, 1 << 113) == 10384593717069655257060992658440192);` |

Related local source: floats: tests/conformance/floats-and-bits/program.min L1–28.

### Z31 — binary math operator in partially inlined function

[test/behavior/eval.zig L438–454](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L438-L454). **adapt_pending**.

Expected: copyWithPartialInline assembles bytes1..16 big-endian ->0x01020304,0x05060708,0x090a0b0c,0x0d0e0f10.

Minyar: Integer/Bytes indexed reads and shifts24/16/8/0 preserve four fitting values; no writable slices/u32/inline or overlap proof.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L450 | adapt_pending | `try expect(s[0] == 0x1020304);` |
| L451 | adapt_pending | `try expect(s[1] == 0x5060708);` |
| L452 | adapt_pending | `try expect(s[2] == 0x90a0b0c);` |
| L453 | adapt_pending | `try expect(s[3] == 0xd0e0f10);` |

Related local source: bits: tests/conformance/floats-and-bits/program.min L29–38; bytes: tests/conformance/bytes/program.min L1–38.

Additional in-file helper/declaration extents: L427–436.

Skip guards: L439 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L440 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L441 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z32 — comptime shl

[test/behavior/eval.zig L456–465](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L456-L465). **incompatible_as_written**.

Expected: u1283<<63 equals27670116110564327424.

Minyar: Result outside signed64; no u128.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L464 | incompatible_as_written | `try expect((a << b) == c);` |

Related local source: bits: tests/conformance/floats-and-bits/program.min L29–38.

Skip guards: L457 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L458 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L459 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z33 — comptime bitwise operators

[test/behavior/eval.zig L467–482](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L467-L482). **adapt_pending**.

Expected: twelve bitwise equalities yield1,3,-3,-1,-1,-4,2,0,0,18446744073709551611,-18446744073709551615,all128ones.

Minyar: First seven fitting signed operands transferable; typed i8/i128 complements and out-of-range values excluded per-site.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L469 | adapt_pending | `try expect(3 & 1 == 1);` |
| L470 | adapt_pending | `try expect(3 & -1 == 3);` |
| L471 | adapt_pending | `try expect(-3 & -1 == -3);` |
| L472 | adapt_pending | `try expect(3 \| -1 == -1);` |
| L473 | adapt_pending | `try expect(-3 \| -1 == -1);` |
| L474 | adapt_pending | `try expect(3 ^ -1 == -4);` |
| L475 | adapt_pending | `try expect(-3 ^ -1 == 2);` |
| L476 | incompatible_as_written | `try expect(~@as(i8, -1) == 0);` |
| L477 | incompatible_as_written | `try expect(~@as(i128, -1) == 0);` |
| L478 | incompatible_as_written | `try expect(18446744073709551615 & 18446744073709551611 == 18446744073709551611);` |
| L479 | incompatible_as_written | `try expect(-18446744073709551615 & -18446744073709551611 == -18446744073709551615);` |
| L480 | incompatible_as_written | `try expect(~@as(u128, 0) == 0xffffffffffffffffffffffffffffffff);` |

Related local source: bits: tests/conformance/floats-and-bits/program.min L29–38.

### Z34 — comptime shlWithOverflow

[test/behavior/eval.zig L484–495](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L484-L495). **incompatible_as_written**.

Expected: ct and rt shlWithOverflow u64allones by16 compare result component0; overflow flag not asserted.

Minyar: No overflow tuple/u64; equality has no independent value oracle, no ordinary-shift substitution.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L494 | incompatible_as_written | `try expect(ct_shifted == rt_shifted);` |

Related local source: bits: tests/conformance/floats-and-bits/program.min L29–38.

Skip guards: L485 `if (builtin.zig_backend == .stage2_aarch64) return error.SkipZigTest;`; L486 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L487 `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest;`.

### Z35 — const ptr to variable data changes at runtime

[test/behavior/eval.zig L497–504](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L497-L504). **adapt_pending**.

Expected: const pointer to mutable Foo.name reads a97 then b98 after replacement.

Minyar: Shared named record alias with Text field preserves reads; raw const pointer/global excluded; no retained-old-backing oracle.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L501 | adapt_pending | `try expect(foo_ref.name[0] == 'a');` |
| L503 | adapt_pending | `try expect(foo_ref.name[0] == 'b');` |

Related local source: records: tests/conformance/loops-and-assignment/program.min L1–7, L26–43.

Additional in-file helper/declaration extents: L506–511.

Skip guards: L498 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L499 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z36 — runtime 128 bit integer division

[test/behavior/eval.zig L513–526](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L513-L526). **incompatible_as_written**.

Expected: u128152313999999999991610955792383 /10000000000000000000 ->15231399999.

Minyar: Operands outside Integer, no wide divide equivalence.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L525 | incompatible_as_written | `try expect(c == 15231399999);` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

Skip guards: L514 `if (builtin.zig_backend == .stage2_wasm) return error.SkipZigTest; // TODO`; L515 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L516 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L517 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`; L518 `if (builtin.zig_backend == .stage2_c and builtin.cpu.arch.isArm()) return error.SkipZigTest;`; L519 `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest;`.

### Z37 — @tagName of @typeInfo

[test/behavior/eval.zig L528–534](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L528-L534). **incompatible_as_written**.

Expected: tagName(typeInfo(u8)) mem.eql string int.

Minyar: No type reflection/tagName.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L533 | incompatible_as_written | `try expect(std.mem.eql(u8, str, "int"));` |

Related local source: text: tests/conformance/text-and-lists/program.min L1–12.

Skip guards: L529 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L530 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z38 — static eval list init

[test/behavior/eval.zig L536–542](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L536-L542). **adapt_pending**.

Expected: vec3 stores data[x,y,z]; global z1.0/runtime z3.0 checked.

Minyar: Named record List<Float> value projection for exactly representable1/3; static/f32/value-array contracts excluded.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L540 | adapt_pending | `try expect(static_vec3.data[2] == 1.0);` |
| L541 | adapt_pending | `try expect(vec3(0.0, 0.0, 3.0).data[2] == 3.0);` |

Related local source: records: tests/conformance/loops-and-assignment/program.min L1–7, L26–43; floats: tests/conformance/floats-and-bits/program.min L1–28.

Additional in-file helper/declaration extents: L543–551.

Skip guards: L537 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L538 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.

### Z39 — inlined loop has array literal with elided runtime scope on first iteration but not second iteration

[test/behavior/eval.zig L553–566](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L553-L566). **incompatible_as_written**.

Expected: inline first selection comptime[2], second runtime[3], discarded; comptime counter2 asserted.

Minyar: Runtime counter does not prove scope-elision phase handling.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L564 | incompatible_as_written | `try expect(i == 2);` |

Related local source: loops: tests/conformance/loops-and-assignment/program.min L9–15, L45–64.

Skip guards: L554 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.

### Z40 — ptr to local array argument at comptime

[test/behavior/eval.zig L568–577](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L568-L577). **adapt_pending**.

Expected: modifySomeBytes writes positions0=a97,9=b98 of undefined10-byte array at comptime; endpoints checked.

Minyar: Bytes(10) direct shared parameter writes97/98; exclude writable slice, undefined contents/comptime.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L574 | adapt_pending | `try expect(bytes[0] == 'a');` |
| L575 | adapt_pending | `try expect(bytes[9] == 'b');` |

Related local source: bytes: tests/conformance/bytes/program.min L1–38.

Additional in-file helper/declaration extents: L579–582.

Skip guards: L569 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.

### Z41 — comparisons 0 <= uint and 0 > uint should be comptime

[test/behavior/eval.zig L584–586](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L584-L586). **incompatible_as_written**.

Expected: unsigned runtime input1234 makes four sign-bound conditions comptime-known; compileError traps unreachable.

Minyar: Signed Integer admits negatives; no unsigned range proof/compileError phase contract.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L589 | incompatible_as_written | `@compileError("this condition should be comptime-known");` |
| L592 | incompatible_as_written | `@compileError("this condition should be comptime-known");` |
| L595 | incompatible_as_written | `@compileError("this condition should be comptime-known");` |
| L598 | incompatible_as_written | `@compileError("this condition should be comptime-known");` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

Additional in-file helper/declaration extents: L587–600.

### Z42 — const global shares pointer with other same one

[test/behavior/eval.zig L604–610](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L604-L610). **incompatible_as_written**.

Expected: hi2=hi1 same first-byte pointer via helper at runtime and comptime.

Minyar: Text value equality exposes no addresses/lifetime; raw-pointer identity excluded.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L608 | incompatible_as_written | `try assertEqualPtrs(&hi1[0], &hi2[0]);` |
| L609 | incompatible_as_written | `comptime assert(&hi1[0] == &hi2[0]);` |
| L612 | incompatible_as_written | `try expect(ptr1 == ptr2);` |

Related local source: text: tests/conformance/text-and-lists/program.min L1–12.

Additional in-file helper/declaration extents: L602–603, L611–613.

Skip guards: L605 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L606 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z43 — string literal used as comptime slice is memoized

[test/behavior/eval.zig L627–632](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L627-L632). **incompatible_as_written**.

Expected: equal link literal slices produce identical nested Node types; source615-626 says guarantee unsettled.

Minyar: No factory type identity; peer comment is not settled language law.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L630 | incompatible_as_written | `comptime assert(TypeWithCompTimeSlice(a).Node == TypeWithCompTimeSlice(b).Node);` |
| L631 | incompatible_as_written | `comptime assert(TypeWithCompTimeSlice("link").Node == TypeWithCompTimeSlice("link").Node);` |

Related local source: text: tests/conformance/text-and-lists/program.min L1–12.

Additional in-file helper/declaration extents: L615–626, L634–639.

### Z44 — comptime function with mutable pointer is not memoized

[test/behavior/eval.zig L641–649](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L641-L649). **adapt_pending**.

Expected: comptime x1 same mutable pointer increment twice ->3, calls not memoized.

Minyar: Shared List[1] helper+=1 twice gives3; no comptime/pointer memoization proof, identical effects prove count not order.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L647 | adapt_pending | `try expect(x == 3);` |

Related local source: literal: tests/recursive-data.py L148–184.

Additional in-file helper/declaration extents: L651–653.

### Z45 — const ptr to comptime mutable data is not memoized

[test/behavior/eval.zig L655–662](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L655-L662). **adapt_pending**.

Expected: read_x const pointer sees1, then field mutation2 and read2 at comptime.

Minyar: Named record read helper on same shared alias before/after mutation; runtime1,2 projection, no pointer/comptime.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L658 | adapt_pending | `try expect(foo.read_x() == 1);` |
| L660 | adapt_pending | `try expect(foo.read_x() == 2);` |

Related local source: records: tests/conformance/loops-and-assignment/program.min L1–7, L26–43.

Additional in-file helper/declaration extents: L664–670.

### Z46 — function which returns struct with type field causes implicit comptime

[test/behavior/eval.zig L672–675](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L672-L675). **incompatible_as_written**.

Expected: wrap(i32).T is i32, record type field forces implicit comptime.

Minyar: No type-valued fields/type factories.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L674 | incompatible_as_written | `try expect(ty == i32);` |

Related local source: records: tests/conformance/loops-and-assignment/program.min L1–7, L26–43.

Additional in-file helper/declaration extents: L677–683.

### Z47 — call method with comptime pass-by-non-copying-value self parameter

[test/behavior/eval.zig L685–697](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L685-L697). **incompatible_as_written**.

Expected: comptime self-value method b returns field a2.

Minyar: Runtime read erases comptime pass-by-non-copying-value receiver contract.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L696 | incompatible_as_written | `try expect(b == 2);` |

Related local source: records: tests/conformance/loops-and-assignment/program.min L1–7, L26–43.

### Z48 — setting backward branch quota just before a generic fn call

[test/behavior/eval.zig L699–702](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L699-L702). **incompatible_as_written**.

Expected: quota1001 immediately before loopNTimes(1001); empty inline loop succeeds without value assertion.

Minyar: Successful comptime quota analysis only; runtime loop not substitute.

No value assertion: successful analysis/driver completion is the selected oracle.

Related local source: loops: tests/conformance/loops-and-assignment/program.min L9–15, L45–64.

Additional in-file helper/declaration extents: L704–707.

### Z49 — variable inside inline loop that has different types on different iterations

[test/behavior/eval.zig L709–711](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L709-L711). **incompatible_as_written**.

Expected: heterogeneous tuple true,u32(42) inline checks first Booleantrue,second Integer42.

Minyar: Homogeneous Lists cannot preserve per-iteration types.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L717 | incompatible_as_written | `if (i == 0) try expect(x);` |
| L718 | incompatible_as_written | `if (i == 1) try expect(x == 42);` |

Related local source: literal: tests/recursive-data.py L148–184.

Additional in-file helper/declaration extents: L713–720.

### Z50 — *align(1) u16 is the same as *align(1:0:2) u16

[test/behavior/eval.zig L722–727](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L722-L727). **incompatible_as_written**.

Expected: *align(1:0:2)u16 equals *align(1)u16; *align(2:0:2)u16 equals *u16.

Minyar: No aligned pointer type values.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L724 | incompatible_as_written | `try expect(*align(1:0:2) u16 == *align(1) u16);` |
| L725 | incompatible_as_written | `try expect(*align(2:0:2) u16 == *u16);` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

### Z51 — array concatenation of function calls

[test/behavior/eval.zig L729–736](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L729-L736). **incompatible_as_written**.

Expected: oneItem(3)++oneItem(4) array equals[3,4] via mem.eql.

Minyar: No array/List concat operator; manual add is different algorithm; pure calls no effect/order oracle.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L735 | incompatible_as_written | `try expect(std.mem.eql(i32, &a, &[_]i32{ 3, 4 }));` |

Related local source: literal: tests/recursive-data.py L148–184.

Additional in-file helper/declaration extents: L747–753.

Skip guards: L730 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest;`; L731 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L732 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z52 — array multiplication of function calls

[test/behavior/eval.zig L738–745](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L738-L745). **incompatible_as_written**.

Expected: oneItem(3)**scalar(2) array equals[3,3].

Minyar: No repetition operator; no call-count/order assertion.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L744 | incompatible_as_written | `try expect(std.mem.eql(i32, &a, &[_]i32{ 3, 3 }));` |

Related local source: literal: tests/recursive-data.py L148–184.

Additional in-file helper/declaration extents: L747–753.

Skip guards: L739 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest;`; L740 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L741 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z53 — array concatenation peer resolves element types - value

[test/behavior/eval.zig L755–769](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L755-L769). **incompatible_as_written**.

Expected: value concat u3[1,7],u8[200,225,255] ->TYPE[5]u8 and all five values.

Minyar: No narrow peer type resolution/concat; matching numbers erase core joining.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L763 | incompatible_as_written | `comptime assert(@TypeOf(c) == [5]u8);` |
| L764 | incompatible_as_written | `try expect(c[0] == 1);` |
| L765 | incompatible_as_written | `try expect(c[1] == 7);` |
| L766 | incompatible_as_written | `try expect(c[2] == 200);` |
| L767 | incompatible_as_written | `try expect(c[3] == 225);` |
| L768 | incompatible_as_written | `try expect(c[4] == 255);` |

Related local source: literal: tests/recursive-data.py L148–184.

Skip guards: L756 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest;`; L757 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.

### Z54 — array concatenation peer resolves element types - pointer

[test/behavior/eval.zig L771–785](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L771-L785). **incompatible_as_written**.

Expected: pointer concat same values ->TYPE*const[5]u8 plus five reads.

Minyar: No pointer concat/type joining.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L779 | incompatible_as_written | `comptime assert(@TypeOf(c) == *const [5]u8);` |
| L780 | incompatible_as_written | `try expect(c[0] == 1);` |
| L781 | incompatible_as_written | `try expect(c[1] == 7);` |
| L782 | incompatible_as_written | `try expect(c[2] == 200);` |
| L783 | incompatible_as_written | `try expect(c[3] == 225);` |
| L784 | incompatible_as_written | `try expect(c[4] == 255);` |

Related local source: literal: tests/recursive-data.py L148–184.

Skip guards: L772 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest;`; L773 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L774 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z55 — array concatenation sets the sentinel - value

[test/behavior/eval.zig L787–805](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L787-L805). **incompatible_as_written**.

Expected: value concat ->TYPE[5:69]u8, five payload1,7,200,225,255, ptr[5]sentinel69.

Minyar: No sentinel, Byte length5 indexing5 traps; concat narrow join absent.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L797 | incompatible_as_written | `comptime assert(@TypeOf(c) == [5:69]u8);` |
| L798 | incompatible_as_written | `try expect(c[0] == 1);` |
| L799 | incompatible_as_written | `try expect(c[1] == 7);` |
| L800 | incompatible_as_written | `try expect(c[2] == 200);` |
| L801 | incompatible_as_written | `try expect(c[3] == 225);` |
| L802 | incompatible_as_written | `try expect(c[4] == 255);` |
| L804 | incompatible_as_written | `try expect(ptr[5] == 69);` |

Related local source: bytes: tests/conformance/bytes/program.min L1–38.

Skip guards: L788 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest;`; L789 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L790 `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest;`; L791 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z56 — array concatenation sets the sentinel - pointer

[test/behavior/eval.zig L807–823](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L807-L823). **incompatible_as_written**.

Expected: pointer concat ->TYPE*const[5:69]u8, same five values and trailing69.

Minyar: No pointer/sentinel concat.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L815 | incompatible_as_written | `comptime assert(@TypeOf(c) == *const [5:69]u8);` |
| L816 | incompatible_as_written | `try expect(c[0] == 1);` |
| L817 | incompatible_as_written | `try expect(c[1] == 7);` |
| L818 | incompatible_as_written | `try expect(c[2] == 200);` |
| L819 | incompatible_as_written | `try expect(c[3] == 225);` |
| L820 | incompatible_as_written | `try expect(c[4] == 255);` |
| L822 | incompatible_as_written | `try expect(ptr[5] == 69);` |

Related local source: bytes: tests/conformance/bytes/program.min L1–38.

Skip guards: L808 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L809 `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest;`; L810 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z57 — array multiplication sets the sentinel - value

[test/behavior/eval.zig L825–841](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L825-L841). **incompatible_as_written**.

Expected: repeated u3[1,6] twice ->TYPE[4:7]u3, values1,6,1,6,sentinel7 at4.

Minyar: No repeat/u3/sentinel; payload match insufficient.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L834 | incompatible_as_written | `comptime assert(@TypeOf(b) == [4:7]u3);` |
| L835 | incompatible_as_written | `try expect(b[0] == 1);` |
| L836 | incompatible_as_written | `try expect(b[1] == 6);` |
| L837 | incompatible_as_written | `try expect(b[2] == 1);` |
| L838 | incompatible_as_written | `try expect(b[3] == 6);` |
| L840 | incompatible_as_written | `try expect(ptr[4] == 7);` |

Related local source: bytes: tests/conformance/bytes/program.min L1–38.

Skip guards: L826 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest;`; L827 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L828 `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest;`; L829 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z58 — array multiplication sets the sentinel - pointer

[test/behavior/eval.zig L843–858](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L843-L858). **incompatible_as_written**.

Expected: pointer repeat ->TYPE*const[4:7]u3 plus1,6,1,6,sentinel7.

Minyar: No pointer repetition/sentinel.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L851 | incompatible_as_written | `comptime assert(@TypeOf(b) == *const [4:7]u3);` |
| L852 | incompatible_as_written | `try expect(b[0] == 1);` |
| L853 | incompatible_as_written | `try expect(b[1] == 6);` |
| L854 | incompatible_as_written | `try expect(b[2] == 1);` |
| L855 | incompatible_as_written | `try expect(b[3] == 6);` |
| L857 | incompatible_as_written | `try expect(ptr[4] == 7);` |

Related local source: bytes: tests/conformance/bytes/program.min L1–38.

Skip guards: L844 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest;`; L845 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L846 `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest;`; L847 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z59 — comptime assign int to optional int

[test/behavior/eval.zig L860–867](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L860-L867). **incompatible_as_written**.

Expected: comptime optional?i32 null then2, unwrapped*=10; expectEqual20.

Minyar: No optional absence/payload lvalue.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L865 | incompatible_as_written | `try expectEqual(20, x.?);` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

### Z60 — two comptime calls with array default initialized to undefined

[test/behavior/eval.zig L869–896](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L869-L896). **incompatible_as_written**.

Expected: two comptime A.d calls default construct B.undefined[255]u8 then discard through A.e; no value check.

Minyar: Successful undefined/default phase analysis only; no allocation/lifetime assertion.

No value assertion: successful analysis/driver completion is the selected oracle.

Related local source: records: tests/conformance/loops-and-assignment/program.min L1–7, L26–43.

Skip guards: L870 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L871 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.

### Z61 — const type-annotated local initialized with function call has correct type

[test/behavior/eval.zig L898–907](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L898-L907). **incompatible_as_written**.

Expected: foo comptime_int1234 assigned explicit u64; TYPEu64 and VALUE1234 checked.

Minyar: No comptime_int/u64 coercion; same number alone not type preservation.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L905 | incompatible_as_written | `try expect(@TypeOf(x) == u64);` |
| L906 | incompatible_as_written | `try expect(x == 1234);` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

### Z62 — comptime pointer load through elem_ptr

[test/behavior/eval.zig L909–927](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L909-L927). **incompatible_as_written**.

Expected: comptime array S.x=index; ptr starts0 reads0, ptr+=1 then ptr[1].x2.

Minyar: No elem_ptr/many-pointer arithmetic; direct List[2] is different contract.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L923 | incompatible_as_written | `assert(x == 0);` |
| L925 | incompatible_as_written | `assert(ptr[1].x == 2);` |

Related local source: records: tests/conformance/loops-and-assignment/program.min L1–7, L26–43.

### Z63 — debug variable type resolved through indirect zero-bit types

[test/behavior/eval.zig L929–935](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L929-L935). **incompatible_as_written**.

Expected: empty slice of struct with []void compiles debug type resolution, no expect.

Minyar: No zero-bit element/debug type-resolution contract.

No value assertion: successful analysis/driver completion is the selected oracle.

Related local source: literal: tests/recursive-data.py L148–184.

Skip guards: L930 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z64 — const local with comptime init through array init

[test/behavior/eval.zig L937–954](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L937-L954). **incompatible_as_written**.

Expected: enum declaration function a reflected into decls; first name byte a asserted at comptime.

Minyar: No enum declaration reflection/comptime initializer.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L953 | incompatible_as_written | `comptime assert(decls[0][0].name[0] == 'a');` |

Related local source: text: tests/conformance/text-and-lists/program.min L1–12.

### Z65 — closure capture type of runtime-known parameter

[test/behavior/eval.zig L956–969](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L956-L969). **incompatible_as_written**.

Expected: generic c1234 type captured using @TypeOf(c) in local D, field1234 checked.

Minyar: Named record1234 erases runtime parameter TYPE capture.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L963 | incompatible_as_written | `try expect(d.c == 1234);` |

Related local source: records: tests/conformance/loops-and-assignment/program.min L1–7, L26–43.

Skip guards: L957 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.

### Z66 — closure capture type of runtime-known var

[test/behavior/eval.zig L971–979](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L971-L979). **incompatible_as_written**.

Expected: x:u32 1234 gives field type @TypeOf(x+100), s.val1234.

Minyar: No local structural type/expr reflection.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L978 | incompatible_as_written | `try expect(s.val == 1234);` |

Related local source: records: tests/conformance/loops-and-assignment/program.min L1–7, L26–43.

Skip guards: L972 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.

### Z67 — comptime break passing through runtime condition converted to runtime break

[test/behavior/eval.zig L981–1011](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L981-L1011). **adapt_pending**.

Expected: inline abc visits bar then match; b sets oktrue and breaks; count2.

Minyar: Ordinary Character List loop/state helper and break preserves true,2; no inline/phase lowering; count not order.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L995 | adapt_pending | `try expect(ok);` |
| L996 | adapt_pending | `try expect(count == 2);` |

Related local source: loops: tests/conformance/loops-and-assignment/program.min L9–15, L45–64.

Skip guards: L982 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.

### Z68 — comptime break to outer loop passing through runtime condition converted to runtime break

[test/behavior/eval.zig L1013–1047](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1013-L1047). **incompatible_as_written**.

Expected: labeled outer ABC innerabc breaks OUTER on b; oktrue,count2, outer_byte discarded.

Minyar: break local is innermost only; flag/function-return rewrite different original control.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1030 | incompatible_as_written | `try expect(ok);` |
| L1031 | incompatible_as_written | `try expect(count == 2);` |

Related local source: loops: tests/conformance/loops-and-assignment/program.min L9–15, L45–64.

Skip guards: L1014 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L1015 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.

### Z69 — comptime break operand passing through runtime condition converted to runtime break

[test/behavior/eval.zig L1049–1063](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1049-L1063). **adapt_pending**.

Expected: inline for expression scansabc with elsez, break operand runtimeb; helper runtime+comptime givesb.

Minyar: Ordinary function loop returns matched Characterb orz; no loop expression/break operand/comptime.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1057 | adapt_pending | `try expect(result == 'b');` |

Related local source: loops: tests/conformance/loops-and-assignment/program.min L9–15, L45–64.

### Z70 — comptime break operand passing through runtime switch converted to runtime break

[test/behavior/eval.zig L1065–1082](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1065-L1082). **incompatible_as_written**.

Expected: runtime switch match in inline loop expression breaks operandb elsez; helper runtime+comptime b.

Minyar: No switch/loop expression; if rewrite removes target switch lowering.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1076 | incompatible_as_written | `try expect(result == 'b');` |

Related local source: loops: tests/conformance/loops-and-assignment/program.min L9–15, L45–64.

Skip guards: L1066 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.

### Z71 — no dependency loop for alignment of self struct

[test/behavior/eval.zig L1084–1120](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1084-L1120). **incompatible_as_written**.

Expected: recursive struct generic C(B),D(F) aligned raw pointerbuf; nested write42+=1 ->43.

Minyar: No alignOf/generic recursive layout/many-pointer; List43 erases failure mode.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1095 | incompatible_as_written | `try expect(a.d.g[3] == 43);` |

Related local source: records: tests/conformance/loops-and-assignment/program.min L1–7, L26–43.

Skip guards: L1085 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L1086 `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest;`; L1087 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z72 — no dependency loop for alignment of self bare union

[test/behavior/eval.zig L1122–1158](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1122-L1158). **incompatible_as_written**.

Expected: same alignment construction with bare unionB; buf43.

Minyar: No bare union/layout/generic aligned pointers.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1133 | incompatible_as_written | `try expect(a.d.g[3] == 43);` |

Related local source: records: tests/conformance/loops-and-assignment/program.min L1–7, L26–43.

Skip guards: L1123 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L1124 `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest;`; L1125 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z73 — no dependency loop for alignment of self tagged union

[test/behavior/eval.zig L1160–1196](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1160-L1196). **incompatible_as_written**.

Expected: same alignment construction tagged unionB; buf43.

Minyar: No tagged union/layout/generic aligned pointers.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1171 | incompatible_as_written | `try expect(a.d.g[3] == 43);` |

Related local source: records: tests/conformance/loops-and-assignment/program.min L1–7, L26–43.

Skip guards: L1161 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L1162 `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest;`; L1163 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z74 — equality of pointers to comptime const

[test/behavior/eval.zig L1198–1201](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1198-L1201). **incompatible_as_written**.

Expected: undefined consti32 same address equals itself at comptime; payload unread.

Minyar: No raw address; value equality different entity.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1200 | incompatible_as_written | `comptime assert(&a == &a);` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

### Z75 — storing an array of type in a field

[test/behavior/eval.zig L1203–1230](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1203-L1230). **incompatible_as_written**.

Expected: Foobar128 type fields and1024-byte array; comptime foo fillsa, runtime slice0..10 passed then discarded; no value check.

Minyar: Successful mixed-phase type-field extraction only; no a-content/lifetime proof.

No value assertion: successful analysis/driver completion is the selected oracle.

Related local source: literal: tests/recursive-data.py L148–184.

Skip guards: L1204 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L1205 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L1206 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z76 — pass pointer to field of comptime-only type as a runtime parameter

[test/behavior/eval.zig L1232–1258](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1232-L1258). **incompatible_as_written**.

Expected: mixed record T:typebool,x1234; runtime foo(&bag.x) setsok if dereference1234.

Minyar: No type-valued mixed fields/raw field pointers.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1250 | incompatible_as_written | `try expect(ok);` |

Related local source: records: tests/conformance/loops-and-assignment/program.min L1–7, L26–43.

Skip guards: L1233 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L1234 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z77 — comptime write through extern struct reinterpreted as array

[test/behavior/eval.zig L1260–1275](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1260-L1275). **incompatible_as_written**.

Expected: comptime extern structu8 fields reinterpreted as *[3]u8; writes1,2,3 then field asserts.

Minyar: No raw reinterpretation/record ABI layout; Bytes decoding different target.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1271 | incompatible_as_written | `assert(s.a == 1);` |
| L1272 | incompatible_as_written | `assert(s.b == 2);` |
| L1273 | incompatible_as_written | `assert(s.c == 3);` |

Related local source: bytes: tests/conformance/bytes/program.min L1–38.

### Z78 — continue nested in a conditional in an inline for

[test/behavior/eval.zig L1277–1286](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1277-L1286). **adapt_pending**.

Expected: inline1,2,3 each always sets x0 then continue; final0; tail/visits unasserted.

Minyar: Ordinary for/if/continue yields0; final0 alone weak continue oracle.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1285 | adapt_pending | `try expect(x == 0);` |

Related local source: loops: tests/conformance/loops-and-assignment/program.min L9–15, L45–64.

### Z79 — optional pointer represented as a pointer value

[test/behavior/eval.zig L1288–1296](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1288-L1296). **incompatible_as_written**.

Expected: optional pointer&val15; pointer to unwrapped payload double dereference15.

Minyar: No optional/raw pointer representation.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1294 | incompatible_as_written | `try expect(payload_ptr.*.* == 15);` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

### Z80 — mutate through pointer-like optional at comptime

[test/behavior/eval.zig L1298–1307](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1298-L1307). **incompatible_as_written**.

Expected: optional pointer payload overwritten to address const16; double dereference16.

Minyar: No optional pointer payload mutation.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1305 | incompatible_as_written | `try expect(payload_ptr.*.* == 16);` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

### Z81 — repeated value is correctly expanded

[test/behavior/eval.zig L1309–1324](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1309-L1324). **incompatible_as_written**.

Expected: zeroes recursively splats by-VALUE four S rows of four i8zero; diagonal1..3=1,2,3; structural equality checks all16.

Minyar: Implicit value copies differ from shared Minyar rows; explicit fresh rows distinct contract already covered by prior projections.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1317–1322 | incompatible_as_written | `        try expectEqual(M{ .x = .{             .{ .x = .{ 0, 0, 0, 0 } },             .{ .x = .{ 0, 1, 0, 0 } },             .{ .x = .{ 0, 0, 2, 0 } },             .{ .x = .{ 0, 0, 0, 3 } },         } }, res);` |

Related local source: row: tests/memory-research-peer-projections.py L63–80.

### Z82 — value in if block is comptime-known

[test/behavior/eval.zig L1326–1337](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1326-L1337). **incompatible_as_written**.

Expected: conditionalfalse chooses b direct/record.str; foo concat both ->foob; only equal-to-each-other asserted.

Minyar: No compile-time concat; equality alone not independent foob oracle.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1336 | incompatible_as_written | `comptime assert(std.mem.eql(u8, first, second));` |

Related local source: text: tests/conformance/text-and-lists/program.min L1–12.

### Z83 — lazy sizeof is resolved in division

[test/behavior/eval.zig L1339–1346](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1339-L1346). **incompatible_as_written**.

Expected: sizeof singleu32 struct /2==2 and -2==2.

Minyar: Arithmetic2 cannot prove lazy layout resolution.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1344 | incompatible_as_written | `try expect(@sizeOf(A) / a == 2);` |
| L1345 | incompatible_as_written | `try expect(@sizeOf(A) - a == 2);` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

### Z84 — lazy sizeof union tag size in compare

[test/behavior/eval.zig L1348–1356](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1348-L1356). **incompatible_as_written**.

Expected: tagged union two void variants sizeof1.

Minyar: No tagged union tag layout.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1355 | incompatible_as_written | `try expect(@sizeOf(A) == 1);` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

Skip guards: L1349 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z85 — lazy value is resolved as slice operand

[test/behavior/eval.zig L1358–1371](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1358-L1371). **incompatible_as_written**.

Expected: u64 slice and castu8 slice same address and sizeof(A)=4 length; underlying byte extents32 vs4; unread undefined contents.

Minyar: No pointer/layout exposure; equal lengths do not prove equal byte spans.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1369 | incompatible_as_written | `try expect(@intFromPtr(ptr1) == @intFromPtr(ptr2));` |
| L1370 | incompatible_as_written | `try expect(ptr1.len == ptr2.len);` |

Related local source: bytes: tests/conformance/bytes/program.min L1–38.

Skip guards: L1359 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L1360 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L1361 `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest;`; L1362 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z86 — break from inline loop depends on runtime condition

[test/behavior/eval.zig L1373–1405](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1373-L1405). **adapt_pending**.

Expected: inline for and inline while use foo(a==4), labeled block result4; unmatched TestFailed; both4 checked.

Minyar: Ordinary function loop early return4 with fail fallback preserves value; no labeled block/inline/comptime index.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1389 | adapt_pending | `try expect(blk == 4);` |
| L1403 | adapt_pending | `try expect(blk == 4);` |

Related local source: loops: tests/conformance/loops-and-assignment/program.min L9–15, L45–64.

Failure alternatives: L1387 `return error.TestFailed;`; L1401 `return error.TestFailed;`.

### Z87 — inline for inside a runtime condition

[test/behavior/eval.zig L1407–1417](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1407-L1417). **incompatible_as_written**.

Expected: if runtimeafalse prevents inline loop: assertion val3 never reached.

Minyar: Successful compilation only; dormant assertion is not executed evidence.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1414 | incompatible_as_written | `try expect(val == 3);` |

Related local source: loops: tests/conformance/loops-and-assignment/program.min L9–15, L45–64.

### Z88 — continue in inline for inside a comptime switch

[test/behavior/eval.zig L1419–1435](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1419-L1435). **adapt_pending**.

Expected: comptime switcharr[1]=2 chooses inline loop, skip2 sum1+3=4.

Minyar: Ordinary if/List for continue preserves4; sum not order proof, switch/phase excluded.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1434 | adapt_pending | `try expect(count == 4);` |

Related local source: loops: tests/conformance/loops-and-assignment/program.min L9–15, L45–64.

Skip guards: L1420 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.

### Z89 — length of global array is determinable at comptime

[test/behavior/eval.zig L1437–1446](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1437-L1446). **incompatible_as_written**.

Expected: comptime helper asserts global undefined[1024]u8 length1024.

Minyar: Runtime Bytes allocation length not compile-time metadata proof.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1442 | incompatible_as_written | `try std.testing.expect(bytes.len == 1024);` |

Related local source: bytes: tests/conformance/bytes/program.min L1–38.

### Z90 — continue nested inline for loop

[test/behavior/eval.zig L1448–1463](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1448-L1463). **incompatible_as_written**.

Expected: unconditional SkipZigTest; dormant labeled outer continue intended x2 and finala2.

Minyar: No labeled continue/inline; no reached peer evidence.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1460 | incompatible_as_written | `try expect(x == 2);` |
| L1462 | incompatible_as_written | `try expect(a == 2);` |

Related local source: loops: tests/conformance/loops-and-assignment/program.min L9–15, L45–64.

Skip guards: L1450 `if (true) return error.SkipZigTest;`.

### Z91 — continue nested inline for loop in named block expr

[test/behavior/eval.zig L1465–1482](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1465-L1482). **incompatible_as_written**.

Expected: unconditional skip; dormant labeled outer continue inside named block assignment intended x2,a2.

Minyar: No labeled continue/block expression; no pass evidence.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1479 | incompatible_as_written | `try expect(x == 2);` |
| L1481 | incompatible_as_written | `try expect(a == 2);` |

Related local source: loops: tests/conformance/loops-and-assignment/program.min L9–15, L45–64.

Skip guards: L1467 `if (true) return error.SkipZigTest;`.

### Z92 — x and false is comptime-known false

[test/behavior/eval.zig L1484–1509](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1484-L1509). **adapt_pending**.

Expected: foo incrementsx returnstrue; and middlefalse executes2; blockreturnfalse adds third ->3; compileError branches must eliminated.

Minyar: && effectfultrue producers before decisivefalse; helper third false producer; independent trace proposal. Phase compileError excluded per-site.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1497 | incompatible_as_written | `@compileError("Condition should be comptime-known false");` |
| L1499 | adapt_pending | `try expect(T.x == 2);` |
| L1506 | incompatible_as_written | `@compileError("Condition should be comptime-known false");` |
| L1508 | adapt_pending | `try expect(T.x == 3);` |

Related local source: short: tests/peer-research-semantics.py L80–97.

Skip guards: L1485 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.

### Z93 — x or true is comptime-known true

[test/behavior/eval.zig L1511–1536](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1511-L1536). **adapt_pending**.

Expected: foo incrementsx returnsfalse; or middletrue executes2; blockreturntrue adds third ->3; negated compileError branches eliminated.

Minyar: || false producers before decisivetrue; helper third true producer; trace proposal. Phase compileError excluded per-site.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1524 | incompatible_as_written | `@compileError("Condition should be comptime-known false");` |
| L1526 | adapt_pending | `try expect(T.x == 2);` |
| L1533 | incompatible_as_written | `@compileError("Condition should be comptime-known false");` |
| L1535 | adapt_pending | `try expect(T.x == 3);` |

Related local source: short: tests/peer-research-semantics.py L80–97.

Skip guards: L1512 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.

### Z94 — non-optional and optional array elements concatenated

[test/behavior/eval.zig L1538–1547](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1538-L1547). **incompatible_as_written**.

Expected: concat u8A and optional?u8null joins optional elements; runtime index0 unwrapA.

Minyar: No optional type joining/unwrap; null element not asserted.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1546 | incompatible_as_written | `try expect(array[index].? == 'A');` |

Related local source: literal: tests/recursive-data.py L148–184.

Skip guards: L1539 `if (builtin.zig_backend == .stage2_aarch64) return error.SkipZigTest;`; L1540 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L1541 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.

### Z95 — inline call in @TypeOf inherits is_inline property

[test/behavior/eval.zig L1549–1555](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1549-L1555). **incompatible_as_written**.

Expected: inline doNothing()->void in TypeOf retains inline property; resulting TYPEvoid.

Minyar: No TypeOf/void value; Nothing cannot be stored.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1554 | incompatible_as_written | `try expect(S.T == void);` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

### Z96 — comptime function turns function value to function pointer

[test/behavior/eval.zig L1557–1570](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1557-L1570). **incompatible_as_written**.

Expected: fnPtr returns function value address; foo array pointer equals&Nil at comptime; Nil not invoked.

Minyar: No first-class function values/pointers/comptime address identity.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1569 | incompatible_as_written | `comptime assert(S.foo[0] == &S.Nil);` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

### Z97 — container level const and var have unique addresses

[test/behavior/eval.zig L1572–1584](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1572-L1584). **incompatible_as_written**.

Expected: p=&S.c; p.x==S.c.x before/after S.v.x=2; no independent post c.x==1/v.x==2 assertions.

Minyar: Container constant/copy semantics absent; equality referencing same c does not independently prove title unique addresses.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1581 | incompatible_as_written | `try std.testing.expect(p.x == S.c.x);` |
| L1583 | incompatible_as_written | `try std.testing.expect(p.x == S.c.x);` |

Related local source: row: tests/memory-research-peer-projections.py L63–80.

### Z98 — break from block results in type

[test/behavior/eval.zig L1586–1599](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1586-L1599). **incompatible_as_written**.

Expected: NewType(usize) uses sizeof labeledblock selecting void; TYPEvoid.

Minyar: No type-return function/layout block value.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1598 | incompatible_as_written | `try expect(T == void);` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

### Z99 — struct in comptime false branch is not evaluated

[test/behavior/eval.zig L1601–1613](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1601-L1613). **incompatible_as_written**.

Expected: comptime switch2 selects V=u32; unselected branch invalid V.foo not evaluated; TYPEu32.

Minyar: No type factory/switch pruning invalid type fields; runtime false branch different proof.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1612 | incompatible_as_written | `try expect(S.some(u32) == u32);` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

### Z100 — result of nested switch assigned to variable

[test/behavior/eval.zig L1615–1629](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1615-L1629). **incompatible_as_written**.

Expected: nested switch reads zds0 yields1234 then assignment; alternative early return unselected.

Minyar: No switch/branch expressions; if rewrite changes lowering.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1628 | incompatible_as_written | `try expect(zds == 1234);` |

Related local source: loops: tests/conformance/loops-and-assignment/program.min L9–15, L45–64.

Skip guards: L1616 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest; // TODO`.

### Z101 — inline for loop of functions returning error unions

[test/behavior/eval.zig L1631–1647](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1631-L1647). **incompatible_as_written**.

Expected: inline TYPE loop T1/T2 calls differing error-union functions1/2, sum3.

Minyar: No error unions/try/type iteration; commutative3 not order proof.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1646 | incompatible_as_written | `try expect(a == 3);` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

### Z102 — if inside a switch

[test/behavior/eval.zig L1649–1661](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1649-L1661). **incompatible_as_written**.

Expected: switch wave_type0 nested ifconditiontrue yields2;100/200/300 alternatives unasserted.

Minyar: No switch/if expression type merge.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1660 | incompatible_as_written | `try expect(sample == 2);` |

Related local source: loops: tests/conformance/loops-and-assignment/program.min L9–15, L45–64.

### Z103 — function has correct return type when previous return is casted to smaller type

[test/behavior/eval.zig L1663–1671](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1663-L1671). **incompatible_as_written**.

Expected: foo()->u16 true returns castu8FF widened255; falseFFFF not invoked; only255 checked.

Minyar: No narrow return type coercion; Integer255 not equivalent.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1670 | incompatible_as_written | `try expect(S.foo(true) == 0xFF);` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

### Z104 — early exit in container level const

[test/behavior/eval.zig L1673–1683](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1673-L1683). **incompatible_as_written**.

Expected: container const labeledblock earlytrue breaku32 gives1; unreachable0 not asserted.

Minyar: No computed container constants/value-bearing break.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1682 | incompatible_as_written | `try expect(S.value == 1);` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

### Z105 — @inComptime

[test/behavior/eval.zig L1685–1694](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1685-L1694). **incompatible_as_written**.

Expected: inComptime directruntimefalse,functionruntimefalse,functioncomptimetrue via equal helper.

Minyar: No phase query; Boolean literal substitutions not equivalent.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1691 | incompatible_as_written | `try expectEqual(false, @inComptime());` |
| L1692 | incompatible_as_written | `try expectEqual(false, S.inComptime());` |
| L1693 | incompatible_as_written | `try expectEqual(true, comptime S.inComptime());` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

### Z106 — module comptime partial array assignment

[test/behavior/eval.zig L1697–1705](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1697-L1705). **adapt_pending**.

Expected: module comptime prefix assignment foo[0..2].*=bar[1,2], preserves suffix0x55=85, final1,2,85.

Minyar: Explicit Bytes indexed prefix writes from distinct source preserve values; no writable slice/phase/overlap/lifetime proof.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1702 | adapt_pending | `assert(foo[0] == 1);` |
| L1703 | adapt_pending | `assert(foo[1] == 2);` |
| L1704 | adapt_pending | `assert(foo[2] == 0x55);` |

Related local source: bytes: tests/conformance/bytes/program.min L1–38.

### Z107 — const with allocation before result is comptime-known

[test/behavior/eval.zig L1707–1715](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1707-L1715). **incompatible_as_written**.

Expected: computed const block makes pure unused[2] then result[42]; comptime TYPE[1]u32 and first42.

Minyar: No comptime allocation/result inference; no observable effect/lifetime asserted.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1713 | incompatible_as_written | `comptime assert(@TypeOf(x) == [1]u32);` |
| L1714 | incompatible_as_written | `comptime assert(x[0] == 42);` |

Related local source: literal: tests/recursive-data.py L148–184.

### Z108 — const with specified type initialized with typed array is comptime-known

[test/behavior/eval.zig L1717–1723](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1717-L1723). **incompatible_as_written**.

Expected: explicit[3]u16 initialized1,2,3; comptime TYPE and all three values.

Minyar: No fixed narrow array/comptime-known typing; List values alone insufficient.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1719 | incompatible_as_written | `comptime assert(@TypeOf(x) == [3]u16);` |
| L1720 | incompatible_as_written | `comptime assert(x[0] == 1);` |
| L1721 | incompatible_as_written | `comptime assert(x[1] == 2);` |
| L1722 | incompatible_as_written | `comptime assert(x[2] == 3);` |

Related local source: literal: tests/recursive-data.py L148–184.

### Z109 — block with comptime-known result but possible runtime exit is comptime-known

[test/behavior/eval.zig L1725–1741](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1725-L1741). **incompatible_as_written**.

Expected: runtime ttrue guards TestFailed paths; comptime_int block values123/456 and asserts.

Minyar: No comptime_int/block break values/phase split.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1739 | incompatible_as_written | `comptime assert(a == 123);` |
| L1740 | incompatible_as_written | `comptime assert(b == 456);` |

Related local source: loops: tests/conformance/loops-and-assignment/program.min L9–15, L45–64.

Failure alternatives: L1730 `if (!t) return error.TestFailed;`; L1736 `return error.TestFailed;`.

### Z110 — comptime labeled block implicit exit

[test/behavior/eval.zig L1743–1748](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1743-L1748). **incompatible_as_written**.

Expected: comptime labeledblock falsebreak123 implicit exit void{} equals{}.

Minyar: Nothing not stored; no void-valued block expression.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L1747 | incompatible_as_written | `comptime assert(result == {});` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

### Z111 — comptime block has intermediate runtime-known values

[test/behavior/eval.zig L1750–1759](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/eval.zig#L1750-L1759). **incompatible_as_written**.

Expected: arr[1,2], runtime-typed idxundefined assigned0 then comptime arr[idx] discarded; successful phase handling only.

Minyar: No comptime interpreter/undefined local; no value or retention assertion.

No value assertion: successful analysis/driver completion is the selected oracle.

Related local source: literal: tests/recursive-data.py L148–184.

### G1 — typeof(f)==typeof(g), both func() int. Neither function is executed.

[test/convert.go L31–35](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/convert.go#L31-L35). **incompatible_as_written**.

Expected: typeof(f)==typeof(g), both func() int. Neither function is executed.

Minyar: No first-class function values/interface boxing/type reflection; return0 replacement changes assertion.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L32 | incompatible_as_written | `if t := typeof(f); t != want {` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

Additional in-file helper/declaration extents: L13–13, L15–19, L21–28, L30–46.

### G2 — typeof(+a)==typeof(a), named main.A preserved under unary plus; value unasserted.

[test/convert.go L37–41](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/convert.go#L37-L41). **incompatible_as_written**.

Expected: typeof(+a)==typeof(a), named main.A preserved under unary plus; value unasserted.

Minyar: No named Integer-derived types/unary-plus reflected type preservation.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L38 | incompatible_as_written | `if t := typeof(+a); t != want {` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

Additional in-file helper/declaration extents: L13–13, L15–19, L21–28, L30–46.

### G3 — typeof(a+0)==typeof(a), named main.A plus untyped constant0 preserves type; value unasserted.

[test/convert.go L42–45](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/convert.go#L42-L45). **incompatible_as_written**.

Expected: typeof(a+0)==typeof(a), named main.A plus untyped constant0 preserves type; value unasserted.

Minyar: No Go named-type/untyped-constant/reflection semantics.

| Exact source site | Disposition | Oracle |
| --- | --- | --- |
| L42 | incompatible_as_written | `if t := typeof(a + 0); t != want {` |

Related local source: numbers: tests/conformance/numbers-and-comparisons/program.min L1–9.

Additional in-file helper/declaration extents: L13–13, L15–19, L21–28, L30–46.

## Required helper contracts and remaining support extents

- [lib/std/testing.zig](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/lib/std/testing.zig), reviewed L69–218, L363–377, L604–608: expect false returns TestUnexpectedResult. expectEqual peer-resolves commonT; scalar != fails; ordinary struct fields recurse, array routes expectEqualSlices. Slice helper tests every element via meta.eql and equal length, errors otherwise. Needed branches for bool,int and repeated M/S arrays; diagnostic formatting outside extent unreviewed. Pending complement: L1–68, L219–362, L378–603, L609–1251.
- [lib/std/debug.zig](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/lib/std/debug.zig), reviewed L545–560: assert false invokes unreachable. Comptime failures invalid; ReleaseFast/Small runtime assert can disappear, unlike expect. Do not infer always-active runtime oracle. Pending complement: L1–544, L561–1782.
- [lib/std/mem.zig](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/lib/std/mem.zig), reviewed L257–345, L675–689, L693–707, L729–787, L4344–4357: zeroes recurses integers0/ordinary fields and arrays via by-value splat, so repeated S rows are independent Zig values. eql validates lengths/value equality; optional unique-representation byte path. Selected byte runtime equality tiny strings, or comptime; no SIMD result claim. sliceAsBytes representation cast, zero-bit branch and checked size multiplication. No ownership oracle. Pending complement: L1–256, L346–674, L690–692, L708–728, L788–4343, L4358–4840.
- [lib/std/meta.zig](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/lib/std/meta.zig), reviewed L707–765, L1108–1151: eql recursively checks ordinary structs/arrays/scalars, enabling all16 repeated-matrix cells. Pointers compare identity, slices address+length. hasUniqueRepresentation integer gate size*8==bits. No pointee/lifetime evidence. Pending complement: L1–706, L766–1107, L1152–1251.

External/nested selected-file functions all have explicit helper contracts in JSON, independently reconciled against every fn definition. Go typeof L13 calls reflect.TypeOf(x).String(); f/gL15–17 return0 but are never invoked; typeT/mapmL19–21 and B/b/xL24–28 are unasserted support. Go reflect implementation was not retained/read; no reflect internals review claimed. Zig needed structural-equality/zeroes/byte-equality contracts are explicit. Diagnostic formatting/transitive utility internals outside needed extents remain unreviewed.

## Original proposals, implementation pending

### P1 — Ordered mandatory effects before decisive Boolean literal/helper

Existing literal decisiveness examples put literal FIRST; producer/precedence tests decide on effectful returns. No inspected fixture has two mandatory effects then a middle false/true literal and forbidden trailing effect. Peer identical increments prove count, not order.

Current-syntax program authored only in report/ledger, not compiled/executed:

```minyar
function observe(events: List<Integer>, id: Integer, result: Boolean): Boolean {
    events.add(id)
    return result
}
function decisive(events: List<Integer>, result: Boolean): Boolean {
    let temporary = Text(3) + "!"
    events.add(3)
    return result
}
let events: List<Integer> = []
print(observe(events, 1, true) && observe(events, 2, true) && false && observe(events, 9, true))
print(events.length)
for id in events { print(id) }
events = []
print(observe(events, 1, true) && observe(events, 2, true) && decisive(events, false) && observe(events, 9, true))
print(events.length)
for id in events { print(id) }
events = []
print(observe(events, 1, false) || observe(events, 2, false) || true || observe(events, 9, false))
print(events.length)
for id in events { print(id) }
events = []
print(observe(events, 1, false) || observe(events, 2, false) || decisive(events, true) || observe(events, 9, false))
print(events.length)
for id in events { print(id) }
```

Exact independent expected stdout:

```text
false
2
1
2
false
3
1
2
3
true
2
1
2
true
3
1
2
3
```

Ordered ID list and Boolean result, trailing9 absent; explicit reset; no commutative-order inference.

Excluded peer contracts: comptime known-condition, compileError, Zig block expression.

### P2 — Binary64 unit-spacing tie arithmetic at2^53

Ordinary Float/NaN fixtures and parse/formatting near2^53 do not perform +1/+2 arithmetic. Round5 subnormal literal and NaN relations are distinct.

Current-syntax program authored only in report/ledger, not compiled/executed:

```minyar
function add(left: Float, right: Float): Float {
    return left + right
}
let x = 9007199254740992.0
print(x + 1.0 == x)
print(x + 2.0 == 9007199254740994.0)
print((x + 2.0) - x)
print(add(x, 1.0) == x)
print(add(x, 2.0) == 9007199254740994.0)
print(add(x, 2.0) - x)
```

Exact independent expected stdout:

```text
true
true
2.0
true
true
2.0
```

Binary64 spacing2 at2^53; halfway+1 rounds even, next representable+2 differs2. Explicit decimal constants/expected Booleans, not solely variant equality.

Excluded peer contracts: f32/f128, comptime, implicit Integer/Float mixing.

## Documentary checks and handoff

The independent audit has **955 consistent documentary checks**: retained hashes/sizes/lines, complete selected extents, all oracle sites/guards, all fn helper contracts, support partitions, local spans, deduplicated prior paths, central bytes and saved corrected runtime argv/outputs. [Checks](../../evidence/peer-readonly/evaluation-round6/document-checks.json) are not test executions or correctness validation.

Prior groups 32+66+120+118=336 span 15 distinct selected files; array.zig is deduplicated across rounds2/3. Adding 114/two gives **450 selected heterogeneous comparisons across17 distinct files**. This selected-report union is not campaign coverage, suite denominator, ports or passing validation.

All 26 adopt/adapt groups and both proposals remain pending executable adaptation; 88 incompatible groups excluded. Zero selected review-pending lines; exact support complements and all other peer files/directories remain outside this round. No extra file selected: complete eval supplies distinct relevant contracts within the bounded selection.

Restricted Rust remains excluded, not retried/bypassed. Round5 directory API failure preserved without retry. Stopped compiler-integration/literature lanes not revived. No new resource restriction and zero network calls this round. Active core/native experiments and dirty work were left to their owners.

Only `research/2026-10-memory/peer-readonly-evaluation-round6.md/.json` and `evidence/peer-readonly/evaluation-round6/` authored. Central manifests unchanged. [Handoff](../../evidence/peer-readonly/evaluation-round6/handoff.json) retains IDs/counts/pending gaps and campaign boundary. Completion applies only to this bounded source round.
