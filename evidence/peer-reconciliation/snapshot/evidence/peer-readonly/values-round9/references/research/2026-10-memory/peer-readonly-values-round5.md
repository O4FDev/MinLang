# Read-only peer value semantics — round 5

Five complete new files, **587 raw physical lines**, **118 heterogeneous comparison groups**: 4 Swift, 54 Go NaN rows, 45 Go literal calls, and 15 Zig subcases across six named tests. **60 pending adoptions, 3 pending adaptations, 53 incompatible units, 2 already-covered properties**. Three original proposals; zero ports or test executions.

This is a distinct documentary review, using GPT-6.1 Sol high. Only the two round5 research files and `evidence/peer-readonly/values-round5/` were authored. Core/native sources, dirty work, central ledgers, frozen soaks and stopped execution lanes were left alone. Earliest campaign completion remains 2026-10-04 06:54:29 UTC; this bounded round makes no campaign-completion claim.

## Complete source selection

| Source | Commit | Raw extent | SHA256 |
| --- | --- | --- | --- |
| [swift test/Interpreter/array_of_optional.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/array_of_optional.swift) | `1ff1cc1170617ab23ab74aa8b741c8daca1903f6` | 1–27 | `a68f033e0e5436b9f009fb956b20082dfd5dc75f2d8825f0f942730a710456e7` |
| [swift test/Interpreter/conversions.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/conversions.swift) | `1ff1cc1170617ab23ab74aa8b741c8daca1903f6` | 1–17 | `054a4c6b52c60bb59a1b38e216a3cb5124b2cdd9f5f8fe4b3511b851a8f81491` |
| [go test/floatcmp.go](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go) | `56ebf80e57db9f61981fc0636fc6419dc6f68eda` | 1–93 | `e1a59f4248ac702bff8c8c90f566ecfa327c244a99e6d8d0e0d903f2b37b5c88` |
| [go test/float_lit.go](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go) | `56ebf80e57db9f61981fc0636fc6419dc6f68eda` | 1–203 | `b9f9cbb151e55b2dec656625c48ff9110050a7e8e174b881fa06b440feae62eb` |
| [zig test/behavior/cast_int.zig](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/cast_int.zig) | `3db960767d12b6214bcf43f1966a037c7a586a12` | 1–247 | `7162e9752946b30ecdbfb221167ea087cc7dbad8eb5041ddc37c563a82130f30` |

Sources and pinned licenses are retained unchanged under the evidence directory (Swift Apache-2.0 with Runtime Library Exception, Go BSD-3-Clause, Zig MIT). Physical lines come from raw bytes, including blanks; web line normalization differs. [Structured ledger](peer-readonly-values-round5.json) retains each exact assertion/helper/guard span. [Source manifest](../../evidence/peer-readonly/values-round5/source-manifest.json) and [document checks](../../evidence/peer-readonly/values-round5/document-checks.json) contain retrieval provenance and independent counts/hashes.

The existing deduplicated ledger and rounds2/3/4 were read before selection. None of these five paths appears in their authored reviews. Prior rounds2–4 retain 218 groups/10 complete files. Adding this round yields 336 groups/15 files across those selected read-only rounds only; grouping differs, so this is not a whole-campaign denominator or a port count. Before selection, the earlier three-projection run-ki_43p1a evidence was read. The final handoff also reads the latest [run-crettoqb results](evidence/runtime-peer-projections/run-crettoqb/results.json) and provenance: four original projections from rounds2–4 passed 24 generated executions across three configurations in the separate runtime lane. These cover Bytes sharing/copied slices, row aliases/scalar snapshots, literal effects/order, and effectful nonempty/empty List/Bytes/Text producers with body storage retention. They are not proposed again or counted as round5 executions. Exact latest bytes are retained in the round5 supplementary manifest.

## Findings and interpretation

- **NaN ordering is a Boolean contract.** Existing conformance asserts direct == false and != true. The other 52 exact operand/negation combinations are adoptable with existing Float/Boolean syntax; no special NaN syntax is needed. The current emitter declares ordered comparisons and unordered !=, but implementation reading does not replace an executable regression.
- **Literal grammar and numeric value are separate.** Eight of 45 checked Go lexemes fit current Minyar grammar; 37 test unsupported leading/trailing-point forms, exponent-only forms or unary plus. They remain incompatible as written. Rewriting to an ordinary decimal value does not cover Go grammar or require a Minyar syntax addition.
- **Go close is approximate.** For nonzero values it accepts relative error below 1e-14; zero mismatches return false without setting global bad. Callers print failures; only nonzero error sets the final panic flag. L173 checks +10.e+23, while L174 prints +10.e+234 on failure. No exact decimal-bit, signed-zero or underflow result is inferred from that diagnostic.
- **Zig casts cannot be erased.** Unsigned 21/10/7-bit truncation has a useful original mask projection; mixed signed widths and checked casts remain incompatible. A plain Integer assignment of -5 performs no narrowing. u128 max shifted 120 cannot become signed64 -1 shifted 120.
- **Optional/class/packed results supply no lifetime proof.** Swift optional iteration and inherited/forced generic class casts are incompatible. Zig packed enum/optional/union loads exercise layout, direct == and raw byte writes; Integer record fields would erase the tested bug. Source notes explicitly warn expectEqual hides it. No destructor or retained-owner assertion occurs.
- **Source and oracle execution stay distinct.** Swift CHECK accepts ordered textual matches, not necessarily exact stdout. Both Swift files require executable_test. Zig has 19 skip-guard sites, including a little-endian guard in the packed-struct test; none was run. Go main expectations and all numeric results here are inferred.

## Local coverage mapping

**nan-equality — `tests/conformance/floats-and-bits/program.min` L22–23.** Direct generated Float NaN equality false and inequality true. No relational, negated or helper-returned Boolean matrix. Source inspected only; no run/pass claim.

**finite-floats — `tests/conformance/floats-and-bits/program.min` L7–23.** Finite decimal arithmetic, exponent extremes, Float conversion, negative zero formatting and one finite ordering. Different literal values from selected Go file. Source inspected only; no run/pass claim.

**literal-normalization — `tests/compiler-hardening.py` L118–149.** 64 model-derived decimal normalization comparisons, negative zero, enormous zero exponent, huge mantissa and exact overflow boundary. No explicit half-minimum-subnormal source literals or named Go cases. Source inspected only; no run/pass claim.

**float-bits-formatter — `tests/runtime-numeric.py` L34–62, L123–161.** Native formatter receives binary64 bits, including minimum subnormal and maximum finite; generated lane uses separate numeric-formatting.min. Native inputs bypass source literal parser. Source inspected only; no run/pass claim.

**formatter-native-driver — `tests/runtime-numeric.c` L34–38, L119–134.** Reads hexadecimal bit patterns, reconstructs native double with memcpy, then formats. Does not parse Minyar source. Source inspected only; no run/pass claim.

**scalar-boundaries — `tests/checked-scalars.py` L12–46, L95–163.** Signed64 bit shifts, Character bounds, truncating Float-to-Integer and exact conversion traps. Does not introduce small-width Integer types or casts. Source inspected only; no run/pass claim.

**nan-clamp — `tests/checked-scalars.py` L48–62.** Bytes-backed NaN payload and negative-zero clamp behavior. Clamp selects negative zero in this case; it is not a direct NaN comparison matrix. Source inspected only; no run/pass claim.

**small-mask — `tests/conformance/floats-and-bits/program.min` L29–38.** Small 0xFF & 0x0F, shifts, OR/XOR, complement and wrapping. No 21/10/7-bit projection of a 64-bit input spanning its 32-bit boundary. Source inspected only; no run/pass claim.

**bytes-endian — `tests/conformance/bytes/program.min` L2–16.** Unaligned Int32 -2, UInt16 65535 and Float storage. Does not implement Zig arbitrary-width integer casts or packed enum layout. Source inspected only; no run/pass claim.

**list-and-record-literals — `tests/recursive-data.py` L148–184.** Homogeneous ordinary Lists and named records; managed captured projection survives replacement. No Optional, enum, inheritance, dynamic class casts or packed layout. Source inspected only; no run/pass claim.

**existing-projections — `tests/memory-research-peer-projections.py` L41–100.** Previously implemented original Bytes independent-copy, row-alias versus explicit snapshot and unused-literal effect/order controls. Not new round5 coverage; do not propose duplicates. Source inspected only; no run/pass claim.

**local-oracle — `tests/regressions.py` L49–62.** CompilerTestCase.executes checks process status and exact stdout at O0/O2 when actually invoked. This research round invokes none of it. Source inspected only; no run/pass claim.


## Per-unit comparisons

The following tables cover every selected semantic unit without a within-file cap. JSON preserves attached driver/helpers and all 51 Zig assertion calls; helpers and repeated guards are not extra comparisons. `adopt_pending` preserves the supported expression contract; `adapt_pending` is an explicitly weaker original algorithm. Incompatible rows can document a value analogue while retaining their incompatible disposition.

### Swift complete units

**S1 — [optional-array present/absent iteration and final progress](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/array_of_optional.swift#L12-L25), incompatible_as_written.** Printed sequence 10, none, 20, none, 30, hello world. Six ordered CHECK directives L6-11; normal main call. No mutation, destructor or ownership-count assertion. Minyar has initialized homogeneous Lists but no Optional or sum/enum payload. A Boolean-tagged record algorithm would implement another protocol; no such substitute proposed. Excluded: Int?, .none/.some payload pattern and switch are absent; no optional lifetime or allocation proof from value output.

**S2 — [derived-to-base inherited method call](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/conversions.swift#L8-L9), incompatible_as_written.** Ordered output CHECK foo; associated call at L15. No failing cast is asserted. Named Minyar records have no subtyping or inherited methods. Excluded: class inheritance and derived-to-base conversion

**S3 — [forced base-to-derived cast](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/conversions.swift#L10-L11), incompatible_as_written.** Ordered output CHECK bar; associated call at L16. No failing cast is asserted. There is no dynamic class identity or forced downcast; ordinary helper print is not cast coverage. Excluded: as! and runtime class casting

**S4 — [forced cast to generic subclass](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/conversions.swift#L12-L13), incompatible_as_written.** Ordered output CHECK bas; associated call at L17. No failing cast is asserted. No generic class factory, runtime specialization identity or forced downcast. Excluded: G<T>, G<Int>, inheritance and as!

### Go NaN matrix

Every row uses Float operands with nan/one; directly preserve comparison and ! nesting. Local references: nan-equality, finite-floats, nan-clamp. N1/N2 have existing direct-property assertions; P1 adds the missing operand/operator/negation/helper combinations. All rows share the table initializer L19–77 and driver L79–93, plus pinned math.NaN/Float64frombits support. No globals/tuple-loop or payload-identity port.

| Unit / exact source | Expression | Expected Boolean | Disposition |
| --- | --- | --- | --- |
| [N1 L23](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L23-L23) | `nan == nan` | `false` | already_covered |
| [N2 L24](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L24-L24) | `nan != nan` | `true` | already_covered |
| [N3 L25](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L25-L25) | `nan < nan` | `false` | adopt_pending |
| [N4 L26](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L26-L26) | `nan > nan` | `false` | adopt_pending |
| [N5 L27](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L27-L27) | `nan <= nan` | `false` | adopt_pending |
| [N6 L28](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L28-L28) | `nan >= nan` | `false` | adopt_pending |
| [N7 L29](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L29-L29) | `f == nan` | `false` | adopt_pending |
| [N8 L30](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L30-L30) | `f != nan` | `true` | adopt_pending |
| [N9 L31](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L31-L31) | `f < nan` | `false` | adopt_pending |
| [N10 L32](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L32-L32) | `f > nan` | `false` | adopt_pending |
| [N11 L33](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L33-L33) | `f <= nan` | `false` | adopt_pending |
| [N12 L34](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L34-L34) | `f >= nan` | `false` | adopt_pending |
| [N13 L35](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L35-L35) | `nan == f` | `false` | adopt_pending |
| [N14 L36](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L36-L36) | `nan != f` | `true` | adopt_pending |
| [N15 L37](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L37-L37) | `nan < f` | `false` | adopt_pending |
| [N16 L38](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L38-L38) | `nan > f` | `false` | adopt_pending |
| [N17 L39](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L39-L39) | `nan <= f` | `false` | adopt_pending |
| [N18 L40](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L40-L40) | `nan >= f` | `false` | adopt_pending |
| [N19 L41](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L41-L41) | `!(nan == nan)` | `true` | adopt_pending |
| [N20 L42](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L42-L42) | `!(nan != nan)` | `false` | adopt_pending |
| [N21 L43](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L43-L43) | `!(nan < nan)` | `true` | adopt_pending |
| [N22 L44](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L44-L44) | `!(nan > nan)` | `true` | adopt_pending |
| [N23 L45](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L45-L45) | `!(nan <= nan)` | `true` | adopt_pending |
| [N24 L46](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L46-L46) | `!(nan >= nan)` | `true` | adopt_pending |
| [N25 L47](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L47-L47) | `!(f == nan)` | `true` | adopt_pending |
| [N26 L48](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L48-L48) | `!(f != nan)` | `false` | adopt_pending |
| [N27 L49](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L49-L49) | `!(f < nan)` | `true` | adopt_pending |
| [N28 L50](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L50-L50) | `!(f > nan)` | `true` | adopt_pending |
| [N29 L51](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L51-L51) | `!(f <= nan)` | `true` | adopt_pending |
| [N30 L52](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L52-L52) | `!(f >= nan)` | `true` | adopt_pending |
| [N31 L53](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L53-L53) | `!(nan == f)` | `true` | adopt_pending |
| [N32 L54](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L54-L54) | `!(nan != f)` | `false` | adopt_pending |
| [N33 L55](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L55-L55) | `!(nan < f)` | `true` | adopt_pending |
| [N34 L56](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L56-L56) | `!(nan > f)` | `true` | adopt_pending |
| [N35 L57](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L57-L57) | `!(nan <= f)` | `true` | adopt_pending |
| [N36 L58](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L58-L58) | `!(nan >= f)` | `true` | adopt_pending |
| [N37 L59](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L59-L59) | `!!(nan == nan)` | `false` | adopt_pending |
| [N38 L60](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L60-L60) | `!!(nan != nan)` | `true` | adopt_pending |
| [N39 L61](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L61-L61) | `!!(nan < nan)` | `false` | adopt_pending |
| [N40 L62](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L62-L62) | `!!(nan > nan)` | `false` | adopt_pending |
| [N41 L63](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L63-L63) | `!!(nan <= nan)` | `false` | adopt_pending |
| [N42 L64](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L64-L64) | `!!(nan >= nan)` | `false` | adopt_pending |
| [N43 L65](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L65-L65) | `!!(f == nan)` | `false` | adopt_pending |
| [N44 L66](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L66-L66) | `!!(f != nan)` | `true` | adopt_pending |
| [N45 L67](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L67-L67) | `!!(f < nan)` | `false` | adopt_pending |
| [N46 L68](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L68-L68) | `!!(f > nan)` | `false` | adopt_pending |
| [N47 L69](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L69-L69) | `!!(f <= nan)` | `false` | adopt_pending |
| [N48 L70](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L70-L70) | `!!(f >= nan)` | `false` | adopt_pending |
| [N49 L71](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L71-L71) | `!!(nan == f)` | `false` | adopt_pending |
| [N50 L72](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L72-L72) | `!!(nan != f)` | `true` | adopt_pending |
| [N51 L73](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L73-L73) | `!!(nan < f)` | `false` | adopt_pending |
| [N52 L74](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L74-L74) | `!!(nan > f)` | `false` | adopt_pending |
| [N53 L75](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L75-L75) | `!!(nan <= f)` | `false` | adopt_pending |
| [N54 L76](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/floatcmp.go#L76-L76) | `!!(nan >= f)` | `false` | adopt_pending |

### Go complete literal call matrix

All calls use pow10 L13–21 and close L23–47. Reference is (Float(ia)/Float(ib))*10^power; expected close=true, with the tolerance and zero limitation above. Local normalization/exponent/formatter tests are related but not exact peer-case or grammar coverage. The ordinary value column is a documentary analogue only for incompatible rows; no such ports were written. P2 is an original source-parser boundary discriminator rather than a Go assertion.

| Unit / physical source | Checked lexeme | Reference ia/ib ×10^power | Existing-syntax value analogue | Disposition |
| --- | --- | --- | --- | --- |
| [L1 L50–52](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L50-L52) | `0.` | 0/1 ×10^0 | `0.0` | incompatible_as_written |
| [L2 L53–55](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L53-L55) | `+10.` | 10/1 ×10^0 | `10.0` | incompatible_as_written |
| [L3 L56–58](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L56-L58) | `-210.` | -210/1 ×10^0 | `-210.0` | incompatible_as_written |
| [L4 L60–62](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L60-L62) | `.0` | 0/1 ×10^0 | `0.0` | incompatible_as_written |
| [L5 L63–65](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L63-L65) | `+.01` | 1/100 ×10^0 | `0.01` | incompatible_as_written |
| [L6 L66–68](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L66-L68) | `-.012` | -12/1000 ×10^0 | `-0.012` | incompatible_as_written |
| [L7 L70–72](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L70-L72) | `0.0` | 0/1 ×10^0 | `0.0` | adopt_pending |
| [L8 L73–75](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L73-L75) | `+10.01` | 1001/100 ×10^0 | `10.01` | incompatible_as_written |
| [L9 L76–78](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L76-L78) | `-210.012` | -210012/1000 ×10^0 | `-210.012` | adopt_pending |
| [L10 L80–82](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L80-L82) | `0E+1` | 0/1 ×10^0 | `0.0E+1` | incompatible_as_written |
| [L11 L83–85](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L83-L85) | `+10e2` | 10/1 ×10^2 | `10.0e2` | incompatible_as_written |
| [L12 L86–88](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L86-L88) | `-210e3` | -210/1 ×10^3 | `-210.0e3` | incompatible_as_written |
| [L13 L90–92](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L90-L92) | `0E-1` | 0/1 ×10^0 | `0.0E-1` | incompatible_as_written |
| [L14 L93–95](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L93-L95) | `+0e23` | 0/1 ×10^1 | `0.0e23` | incompatible_as_written |
| [L15 L96–98](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L96-L98) | `-0e345` | 0/1 ×10^1 | `-0.0e345` | incompatible_as_written |
| [L16 L100–102](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L100-L102) | `0E1` | 0/1 ×10^1 | `0.0E1` | incompatible_as_written |
| [L17 L103–105](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L103-L105) | `+10e23` | 10/1 ×10^23 | `10.0e23` | incompatible_as_written |
| [L18 L106–108](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L106-L108) | `-210e34` | -210/1 ×10^34 | `-210.0e34` | incompatible_as_written |
| [L19 L110–112](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L110-L112) | `0.E1` | 0/1 ×10^1 | `0.0E1` | incompatible_as_written |
| [L20 L113–115](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L113-L115) | `+10.e+2` | 10/1 ×10^2 | `10.0e+2` | incompatible_as_written |
| [L21 L116–118](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L116-L118) | `-210.e-3` | -210/1 ×10^-3 | `-210.0e-3` | incompatible_as_written |
| [L22 L120–122](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L120-L122) | `.0E1` | 0/1 ×10^1 | `0.0E1` | incompatible_as_written |
| [L23 L123–125](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L123-L125) | `+.01e2` | 1/100 ×10^2 | `0.01e2` | incompatible_as_written |
| [L24 L126–128](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L126-L128) | `-.012e3` | -12/1000 ×10^3 | `-0.012e3` | incompatible_as_written |
| [L25 L130–132](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L130-L132) | `0.0E1` | 0/1 ×10^0 | `0.0E1` | adopt_pending |
| [L26 L133–135](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L133-L135) | `+10.01e2` | 1001/100 ×10^2 | `10.01e2` | incompatible_as_written |
| [L27 L136–138](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L136-L138) | `-210.012e3` | -210012/1000 ×10^3 | `-210.012e3` | adopt_pending |
| [L28 L140–142](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L140-L142) | `0.E+12` | 0/1 ×10^0 | `0.0E+12` | incompatible_as_written |
| [L29 L143–145](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L143-L145) | `+10.e23` | 10/1 ×10^23 | `10.0e23` | incompatible_as_written |
| [L30 L146–148](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L146-L148) | `-210.e33` | -210/1 ×10^33 | `-210.0e33` | incompatible_as_written |
| [L31 L150–152](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L150-L152) | `.0E-12` | 0/1 ×10^0 | `0.0E-12` | incompatible_as_written |
| [L32 L153–155](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L153-L155) | `+.01e23` | 1/100 ×10^23 | `0.01e23` | incompatible_as_written |
| [L33 L156–158](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L156-L158) | `-.012e34` | -12/1000 ×10^34 | `-0.012e34` | incompatible_as_written |
| [L34 L160–162](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L160-L162) | `0.0E12` | 0/1 ×10^12 | `0.0E12` | adopt_pending |
| [L35 L163–165](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L163-L165) | `+10.01e23` | 1001/100 ×10^23 | `10.01e23` | incompatible_as_written |
| [L36 L166–168](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L166-L168) | `-210.012e33` | -210012/1000 ×10^33 | `-210.012e33` | adopt_pending |
| [L37 L170–172](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L170-L172) | `0.E123` | 0/1 ×10^123 | `0.0E123` | incompatible_as_written |
| [L38 L173–175](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L173-L175) | `+10.e+23` | 10/1 ×10^23 | `10.0e+23` | incompatible_as_written |
| [L39 L176–178](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L176-L178) | `-210.e-35` | -210/1 ×10^-35 | `-210.0e-35` | incompatible_as_written |
| [L40 L180–182](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L180-L182) | `.0E123` | 0/1 ×10^123 | `0.0E123` | incompatible_as_written |
| [L41 L183–185](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L183-L185) | `+.01e29` | 1/100 ×10^29 | `0.01e29` | incompatible_as_written |
| [L42 L186–188](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L186-L188) | `-.012e29` | -12/1000 ×10^29 | `-0.012e29` | incompatible_as_written |
| [L43 L190–192](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L190-L192) | `0.0E123` | 0/1 ×10^123 | `0.0E123` | adopt_pending |
| [L44 L193–195](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L193-L195) | `+10.01e31` | 1001/100 ×10^31 | `10.01e31` | incompatible_as_written |
| [L45 L196–198](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/float_lit.go#L196-L198) | `-210.012e19` | -210012/1000 ×10^19 | `-210.012e19` | adopt_pending |

### Zig complete subcase comparison

**Z1 — [u128 max shifted by checked u7 count120](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/cast_int.zig#L7-L18), incompatible_as_written.** maxInt(u128)=2^128-1; >>120 yields255. Expect call L17.

Minyar: Integer is signed64; maxInt(u128) and count120 cannot be represented as this operation. A shift120 must stop. Excluded: u128, u7 result typing, @intCast and unsigned logical shifting; -1 >>120 is not a substitute.

Inspected local references: scalar-boundaries. Source only, no execution or ownership/copy proof.

Guards for owning named test: L8: `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L9: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L10: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`; L11: `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest;`.

**Z2 — [signed -5 widen and checked narrow](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/cast_int.zig#L20-L33), incompatible_as_written.** L27 i32 y equals i8 x, both -5; L32 checked i32 x2 to i8 equals i8 y2 -5. Both assertions true.

Minyar: Ordinary Integer -5 copies preserve value, but do not perform widening/narrowing; an existing Bytes Int16 check is a separate storage conversion. Excluded: Minyar has one Integer type; implicit cross-width equality/coercion and i8 checked cast are absent.

Inspected local references: scalar-boundaries, bytes-endian. Source only, no execution or ownership/copy proof.

Guards for owning named test: L21: `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L22: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.

**Z3 — [u21 widen then truncate u64 to u21](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/cast_int.zig#L38-L53), adapt_pending.** All five expectEqual calls: a,b,c=6417; d,e=0x145678 (1332856). w=0x1234567812345678; truncation discards all high bits above u21.

Minyar: Use Integer w & 0x1FFFFF for the explicit low-bit algorithm and compare 1332856; ordinary Integer aliases preserve 6417. This tests bitwise extraction, not a typed cast. Excluded: u21/u10/u7/u32/u64/u60, implicit widening, @truncate and result typing absent. Replacing only widths with Integer would omit truncation.

Inspected local references: small-mask, scalar-boundaries. Original proposal P3. Source only, no execution or ownership/copy proof.

Guards for owning named test: L36: `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest; // TODO`.

**Z4 — [u10 widen then truncate u64 to u10](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/cast_int.zig#L55-L70), adapt_pending.** All five expectEqual calls: a,b,c=234; d,e=0x278 (632). w=0x1234567812345678; truncation discards all high bits above u10.

Minyar: Use Integer w & 0x3FF for the explicit low-bit algorithm and compare 632; ordinary Integer aliases preserve 234. This tests bitwise extraction, not a typed cast. Excluded: u21/u10/u7/u32/u64/u60, implicit widening, @truncate and result typing absent. Replacing only widths with Integer would omit truncation.

Inspected local references: small-mask, scalar-boundaries. Original proposal P3. Source only, no execution or ownership/copy proof.

Guards for owning named test: L36: `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest; // TODO`.

**Z5 — [u7 widen then truncate u64 to u7](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/cast_int.zig#L71-L86), adapt_pending.** All five expectEqual calls: a,b,c=11; d,e=0x78 (120). w=0x1234567812345678; truncation discards all high bits above u7.

Minyar: Use Integer w & 0x7F for the explicit low-bit algorithm and compare 120; ordinary Integer aliases preserve 11. This tests bitwise extraction, not a typed cast. Excluded: u21/u10/u7/u32/u64/u60, implicit widening, @truncate and result typing absent. Replacing only widths with Integer would omit truncation.

Inspected local references: small-mask, scalar-boundaries. Original proposal P3. Source only, no execution or ownership/copy proof.

Guards for owning named test: L36: `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest; // TODO`.

**Z6 — [i21 sign-preserving widening and checked narrowing](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/cast_int.zig#L88-L103), incompatible_as_written.** All five expectEqual calls: a,b,c=-6417; d,e=-12345. Negative narrow input fits i21; no overflow/rejection case in this source block.

Minyar: Integer scalar assignment preserves both bounded negatives. Signed64 shift/mask controls may separately test sign extraction; assignment alone is not this cross-width contract. Excluded: i21/i32/i64/i60 signed width coercion and checked @intCast absent. The test does not assert invalid casts.

Inspected local references: scalar-boundaries. Source only, no execution or ownership/copy proof.

Guards for owning named test: L36: `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest; // TODO`.

**Z7 — [i10 sign-preserving widening and checked narrowing](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/cast_int.zig#L105-L120), incompatible_as_written.** All five expectEqual calls: a,b,c=-234; d,e=-456. Negative narrow input fits i10; no overflow/rejection case in this source block.

Minyar: Integer scalar assignment preserves both bounded negatives. Signed64 shift/mask controls may separately test sign extraction; assignment alone is not this cross-width contract. Excluded: i10/i32/i64/i60 signed width coercion and checked @intCast absent. The test does not assert invalid casts.

Inspected local references: scalar-boundaries. Source only, no execution or ownership/copy proof.

Guards for owning named test: L36: `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest; // TODO`.

**Z8 — [i7 sign-preserving widening and checked narrowing](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/cast_int.zig#L121-L136), incompatible_as_written.** All five expectEqual calls: a,b,c=-11; d,e=-42. Negative narrow input fits i7; no overflow/rejection case in this source block.

Minyar: Integer scalar assignment preserves both bounded negatives. Signed64 shift/mask controls may separately test sign extraction; assignment alone is not this cross-width contract. Excluded: i7/i32/i64/i60 signed width coercion and checked @intCast absent. The test does not assert invalid casts.

Inspected local references: scalar-boundaries. Source only, no execution or ownership/copy proof.

Guards for owning named test: L36: `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest; // TODO`.

**Z9 — [optional Piece payload](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/cast_int.zig#L173-L175), incompatible_as_written.** L174-175 optional unwrapped type PAWN and color BLACK after charToPiece(p).

Minyar: Named Minyar records can contain explicit Integer fields, but have no enum/packed bit layout, optional payload or pointer overwrite. An arithmetic 251 &1 / (251 >>1)&7 discriminator is an original bit algorithm only. Excluded: optional payload, non-byte enum load, error-union return; direct == is significant upstream: comments say expectEqual would hide the reported bug. No destructor, alias, reference-count or retained-result assertion.

Inspected local references: list-and-record-literals, small-mask. Source only, no execution or ownership/copy proof.

Guards for owning named test: L168: `if (builtin.zig_backend == .stage2_aarch64) return error.SkipZigTest;`; L169: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`; L170: `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest; // TODO`.

**Z10 — [raw-byte Piece payload](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/cast_int.zig#L177-L180), incompatible_as_written.** L179-180 raw byte 251 loaded into Piece has type PAWN, color BLACK.

Minyar: Named Minyar records can contain explicit Integer fields, but have no enum/packed bit layout, optional payload or pointer overwrite. An arithmetic 251 &1 / (251 >>1)&7 discriminator is an original bit algorithm only. Excluded: packed layout, pointer cast/write and undefined initial object; direct == is significant upstream: comments say expectEqual would hide the reported bug. No destructor, alias, reference-count or retained-result assertion.

Inspected local references: list-and-record-literals, small-mask. Source only, no execution or ownership/copy proof.

Guards for owning named test: L168: `if (builtin.zig_backend == .stage2_aarch64) return error.SkipZigTest;`; L169: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`; L170: `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest; // TODO`.

**Z11 — [Piece field inside ordinary struct](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/cast_int.zig#L192-L198), incompatible_as_written.** L197-198 raw byte 251 into struct0.p gives PAWN, BLACK; struct0.int is unobserved.

Minyar: Named Minyar records can contain explicit Integer fields, but have no enum/packed bit layout, optional payload or pointer overwrite. An arithmetic 251 &1 / (251 >>1)&7 discriminator is an original bit algorithm only. Excluded: packed Piece load within ordinary struct and pointer cast; direct == is significant upstream: comments say expectEqual would hide the reported bug. No destructor, alias, reference-count or retained-result assertion.

Inspected local references: list-and-record-literals, small-mask. Source only, no execution or ownership/copy proof.

Guards for owning named test: L184: `if (builtin.zig_backend == .stage2_aarch64) return error.SkipZigTest;`; L185: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`; L186: `if (builtin.cpu.arch.endian() != .little) return error.SkipZigTest; // packed struct TODO`; L187: `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest; // TODO`.

**Z12 — [three Piece fields inside packed struct](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/cast_int.zig#L200-L214), incompatible_as_written.** L209-214 every p0,p1,p2 gives PAWN, BLACK; p0 byte-written, p1/p2 helper-written. pad is unobserved.

Minyar: Named Minyar records can contain explicit Integer fields, but have no enum/packed bit layout, optional payload or pointer overwrite. An arithmetic 251 &1 / (251 >>1)&7 discriminator is an original bit algorithm only. Excluded: non-byte-aligned packed fields, byte overwrite and little-endian guard; direct == is significant upstream: comments say expectEqual would hide the reported bug. No destructor, alias, reference-count or retained-result assertion.

Inspected local references: list-and-record-literals, small-mask. Source only, no execution or ownership/copy proof.

Guards for owning named test: L184: `if (builtin.zig_backend == .stage2_aarch64) return error.SkipZigTest;`; L185: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`; L186: `if (builtin.cpu.arch.endian() != .little) return error.SkipZigTest; // packed struct TODO`; L187: `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest; // TODO`.

**Z13 — [packed union interpretation](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/cast_int.zig#L227-L233), incompatible_as_written.** L232-233 union0 int=251 interpreted as Piece gives PAWN, BLACK.

Minyar: Named Minyar records can contain explicit Integer fields, but have no enum/packed bit layout, optional payload or pointer overwrite. An arithmetic 251 &1 / (251 >>1)&7 discriminator is an original bit algorithm only. Excluded: packed union type punning; direct == is significant upstream: comments say expectEqual would hide the reported bug. No destructor, alias, reference-count or retained-result assertion.

Inspected local references: list-and-record-literals, small-mask. Source only, no execution or ownership/copy proof.

Guards for owning named test: L218: `if (builtin.zig_backend == .stage2_aarch64) return error.SkipZigTest;`; L219: `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest;`; L220: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`; L221: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest;`; L222: `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest;`.

**Z14 — [ordinary union overwritten Piece](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/cast_int.zig#L235-L241), incompatible_as_written.** L240-241 initial WHITE/KING Piece overwritten with byte 251 gives PAWN, BLACK.

Minyar: Named Minyar records can contain explicit Integer fields, but have no enum/packed bit layout, optional payload or pointer overwrite. An arithmetic 251 &1 / (251 >>1)&7 discriminator is an original bit algorithm only. Excluded: untagged union and raw partial-storage write; direct == is significant upstream: comments say expectEqual would hide the reported bug. No destructor, alias, reference-count or retained-result assertion.

Inspected local references: list-and-record-literals, small-mask. Source only, no execution or ownership/copy proof.

Guards for owning named test: L218: `if (builtin.zig_backend == .stage2_aarch64) return error.SkipZigTest;`; L219: `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest;`; L220: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`; L221: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest;`; L222: `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest;`.

**Z15 — [middle packed Piece array element](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/cast_int.zig#L243-L246), incompatible_as_written.** L245-246 pieces[1] byte 251 gives PAWN, BLACK; other elements unobserved.

Minyar: Named Minyar records can contain explicit Integer fields, but have no enum/packed bit layout, optional payload or pointer overwrite. An arithmetic 251 &1 / (251 >>1)&7 discriminator is an original bit algorithm only. Excluded: array layout, packed enum load, pointer cast and undefined siblings; direct == is significant upstream: comments say expectEqual would hide the reported bug. No destructor, alias, reference-count or retained-result assertion.

Inspected local references: list-and-record-literals, small-mask. Source only, no execution or ownership/copy proof.

Guards for owning named test: L218: `if (builtin.zig_backend == .stage2_aarch64) return error.SkipZigTest;`; L219: `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest;`; L220: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`; L221: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest;`; L222: `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest;`.

## Original missing-test proposals

All three are original, precise, existing-syntax **proposals**, unimplemented and unexecuted in round5. No code was ported, compiled or executed. The latest separately executed four-projection run-crettoqb was checked for overlap: none asserts the NaN relational/negation matrix, neighboring half-minimum source literals, or cross-32-bit masks proposed here. Recheck cited snapshot gaps against concurrent fixture changes before implementation.

**P1 — NaN ordered and negated comparisons through direct values and helper returns.** Use Float nan=0.0/0.0 and Float one=1.0. Check all 18 operand/operator combinations (nan,nan; one,nan; nan,one; ==,!=,<,>,<=,>=) directly, negated, and double-negated, with explicit expected Boolean rows. Also return each comparison from a typed Boolean helper before negation, and include finite-order controls (1.0<2.0 true, !(1.0<2.0) false). A small original two-call control compares effectful Float helpers returning nan/one and records trace12 regardless of comparison result.

Expected independently: For each of the three operand pairs, base row [false,true,false,false,false,false]; ! row [true,false,true,true,true,true]; !! row repeats base. Helper-return rows identical; finite controls true,false; effectful ordered comparison false and decimal trace12.

Gap: Conformance L22-23 only exercises ==/!=; finite < is not unordered <; nan-clamp and NaN-to-Integer failure never observe Boolean ordering/negation. The emitter currently declares correct fcmp predicates but reading implementation is not regression evidence. No repetition of the separately executed Bytes-copy/row-snapshot/literal-effects/iterable-retention projections; direct ==/!= are controls, not new coverage claims.

**P2 — Source literal underflow and signed-zero bit discriminators.** In a generated Minyar program use 2.4703282292062327e-324, 2.4703282292062328e-324, and their negatives, plus 0.0e123 and -0.0e123. Append each Float to Bytes with addFloat64; print getInt64 at each offset. Repeat through a function returning Float. These decimal values straddle half the least positive binary64 subnormal; read signed64 bits rather than using a relative-error helper or formatting as the sole oracle.

Expected independently: Bits in order: 0,1,-9223372036854775808,-9223372036854775807,0,-9223372036854775808. Function-return version identical. The two nearby decimal magnitudes are respectively below and above 2^-1075; positive zero and minimum subnormal compare differently at the bit level.

Gap: The Go file selected here tests normal nonzero values and tolerant decimal agreement, never half-minimum subnormal. Existing random source normalization has no guaranteed exact neighboring half-minimum values. Runtime formatter minimum-subnormal input is already binary bits and bypasses the source parser; existing overflow threshold tests concern the opposite end. Generated source normalization boundary, not another native formatter or negative-zero-formatting test. No leading/trailing-point forms, unary plus or exponent-only syntax.

**P3 — Explicit low-bit extraction across the 32-bit boundary.** Use Integer w=0x1234567812345678. Compare w &0x1FFFFF, w &0x3FF, w &0x7F with independently listed expected Integers. Pass the same value through typed Integer helpers and a List<Integer> slot, then repeat the masks. Add signed control -5 &0xFF=251 and (-5 &0xFF)<<56>>56=-5 using explicit grouping. Optional value-only packed-byte contrast checks 251 &1=1 and (251>>1)&7=5; do not construct an enum or packed record.

Expected independently: All three paths yield 1332856,632,120. Signed controls 251,-5; optional scalar extraction 1,5. No @truncate, small-width implicit conversion or packed-storage claim.

Gap: Conformance checks only 0xFF &0x0F and small bitwise values. Random full-width shift fixtures do not independently assert these cross-boundary low-bit masks or stored/helper projections. Typed Bytes tests have fixed native widths and are not arbitrary-width casts. Original bitwise algorithm, not Zig cast implementation. Scalar equality on masks does not count as ownership proof.

## Availability, scope and handoff

One Swift directory API request returned a web-tool Internal Error / URL not accessible; that API was neither retried nor routed around. The already retained inventory supplied candidate discovery. The distinct selected raw files and licenses were accessible. The prior restricted Rust resource remains excluded, with zero new review credit; stopped integration/literature/tooling execution lanes were not revived.

Zig eval.zig and Go convert.go were discovery candidates only and remain unselected/review-pending. The retained unselected extents are Go convert.go L1–46 and Zig eval.zig L1–1759, entirely semantic-review pending. Full supporting raw files are retained but only the six listed oracle contracts receive selective-body review. Their exact pending complements are in JSON. Other peer files/directories are unreviewed by this round. No broad all-tests or all-papers claim is made.

Selected-file review is complete: zero selected pending lines. All 63 round5 adopt/adapt comparison units remain pending, and all 3 original round5 proposals remain unimplemented/unexecuted in this lane; 53 incompatible groups remain excluded; 2 existing direct NaN properties are documented. No runtime correctness result is inferred. Central ledgers remain untouched. The handoff derives counts from the saved record and independent documentary checks.

Independent documentary verification completed 848 checks: all 54 Go matrix rows, 45 Go literal calls, 51 Zig assertion sites, 19 Zig guard sites and 9 Swift CHECKs are attributed; 15 raw peer source/license/support/candidate hashes and 43 local snapshot hashes match. Exact integer/rational derivation independently checks the low-bit and underflow proposal oracles. The campaign README and runtime projection report changed concurrently; their original and observed hashes are retained. This lane did not write them.

A further 23 documentary checks validate seven retained latest runtime evidence snapshots, four external method/provenance mappings, three configurations, both O0/O2 records and 24 externally recorded generated executions. Those executions belong to the separate runtime lane. This round executed zero tests. Generated ASan and runtime C ASan/UBSan are documented there; no generated UBSan, LSan or timing claim is added.
