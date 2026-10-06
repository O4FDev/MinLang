# Read-only Text, literal and loop peer review — round 8

Reviewed **4 complete new pinned files**, **744 raw physical lines**, and **64 heterogeneous authored groups**. Dispositions: **5 adopt pending, 26 adapt pending, 33 incompatible, zero already-covered exact groups**. All selected lines, assertions, helpers, backend skips, phase bodies and diagnostic branches were read. No arbitrary prefix selected.

Two original precise regressions are proposed below; neither was implemented, compiled or executed. No maintained source/test/build edits, installs, commits, timings, subagents or central-manifest changes occurred. This finishes only this bounded source review. Campaign earliest completion remains **2026-10-04 06:54:29 UTC**; no campaign completion is claimed.

## Selection and immutable provenance

[Source manifest](../../evidence/peer-readonly/text-loops-round8/source-manifest.json) retains exact raw sources/licenses, primary URLs, hashes, support partitions and unavailable candidates. [Overlap check](../../evidence/peer-readonly/text-loops-round8/overlap-check.json) checks the broad deduplicated ledger, initial peer inventories, Rust/Swift directory and Nim/Koka/Lean ledgers plus rounds2–7. Go char_lit and Zig for were listed pending; neither had authored review. Go ken/string and libc++ comparison had no matching review entry. Zig bool/while were excluded because already reviewed.

| Selected source | Complete raw extent | SHA-256 | Groups |
| --- | --- | --- | --- |
| [test/char_lit.go](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/char_lit.go) | L1–45; 657 bytes | `a564a0a6031ae143fafa3b03b85214d69354cc5b7bb63baff20335a981dde053` | 2 |
| [test/behavior/for.zig](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig) | L1–526; 14222 bytes | `5fcc5f2bf662a84facfc2c5a16188e94e3c64f57a6061ebf711380c9bec75e99` | 27 |
| [libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp) | L1–59; 1942 bytes | `042ef8f04a17332646026b1b17e2032a28bf0c9be8e774b7177cd3669ef35f71` | 18 |
| [test/ken/string.go](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/string.go) | L1–114; 1837 bytes | `307c1b00298b86d2ce3bb50db40021de7dd548e31afa95f585418efcf46ec8f9` | 17 |

| Preserved license | SHA-256 |
| --- | --- |
| [llvm LICENSE.TXT](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/LICENSE.TXT) | `8d85c1057d742e597985c7d4e6320b015a9139385cff4cbae06ffc0ebe89afee` |
| [zig LICENSE](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/LICENSE) | `5c537d6853e005298a285d508cff9ac7192cea23576c840d485b2b586a7ff177` |
| [go LICENSE](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/LICENSE) | `911f8f5782931320f5b8d1160a76365b83aea6447ee6c04fa6d5591467db9dad` |

Go retains its 2009 Go Authors BSD-3-Clause notice; Zig the contributors’ MIT/Expat license; LLVM Apache-2.0 WITH LLVM-exception. License bytes match the peers.json pins. Full notices and conditions are retained. No upstream code was copied into maintained tests.

## Findings and contract boundaries

- **Text equality compares content; Text ordering is unavailable.** Go ken/string mixed ==/!=/> predicates must be split: == and != transfer, > does not. libc++ compare tests are **C++ standard-library behavior**, never compiler IR equivalence. Only four zero-result ASCII equality properties receive pending value-projection credit. Ordered-sign, unsigned-byte and null-pointer cases remain incompatible.
- **Go literal spelling and value projection differ.** char_lit adds22 untyped rune constants into uint64 and checks2155027. Nine literal values can retain their spellings using explicit Integer(Character) conversions. Minyar n/r/t escapes have their familiar values; other one-letter escapes fall through to that following character. Go a/b/f/v control escapes therefore differ, and numeric octal/hex/Unicode escape spellings are unavailable. Character(code) is a distinct value control, never proof that the original source syntax works.
- **Scalar loop capture transfers without array-copy semantics.** Zig for copies a scalar into its payload before the body mutates the source slot; it asserts only the captured values1,2,3. It does not assert the final source100,101,102. Minyar scalar List elements can preserve that capture property while the List remains shared. A nested record/List capture remains a shared reference unless a scalar is explicitly saved.
- **Counts and control ordering remain separate.** The initial Zig sum6 checks continue before the threshold break. Ordinary range0..6 checks sum15. No effects appear in those range bounds; earlier round2R2 already proposes effectful bound controls, so this round does not repeat them. Labels, zipped inputs, loop-expression results/else and mixed comptime/runtime specialization are excluded or explicitly reduced to a different value algorithm.
- **The C++ test has no embedded-NUL mismatch oracle.** Its count limits1/2/3 compare ASCII digits; the all-bits-one case checks unsigned byte ordering. P1’s NUL-after-content mismatch, every-position short-length matrix and Unicode tail are original Minyar extensions. Invalid UTF8 is not normalized or converted to a peer byte-order Text contract.
- **Prints are observations, not invented assertions.** Go ken/string prints have no in-file output golden/check annotation. Their predicted content and different Minyar newline framing are documented separately from its nine failure predicates. Indexed recomputation compares two variants and is weaker than independent expected code points. No pointer, lifetime or ownership inference follows merely from matching output.

## Local source coverage

[Local manifest](../../evidence/peer-readonly/text-loops-round8/local-manifest.json) freezes every cited file. Source inspection and known expected stdout are separate from a new pass. Exact spans below establish related behavior only; zero selected upstream groups receive already-covered credit.

| ID / local file | Inspected spans | Coverage and limits |
| --- | --- | --- |
| loops: `tests/conformance/loops-and-assignment/program.min` | L9–24, L45–64 | Range skip/break sum18; Text héllo skips l; while exits11; nested innermost break count3. No List source mutation after scalar capture. |
| loops-output: `tests/conformance/loops-and-assignment/expected.stdout` | L1–17 | Exact expected stdout accompanies loop fixture; documentary only. |
| text-list: `tests/conformance/text-and-lists/program.min` | L1–12 | Shared Text List join/index/slice; no negative equality pair. |
| text-list-output: `tests/conformance/text-and-lists/expected.stdout` | L1–6 | Exact expected stdout; documentary only. |
| text-index: `tests/runtime/text-indexing.min` | L1–8 | Aé🙂 counts3/7, index and slice; no equality matrix. |
| unicode-properties: `tests/regressions.py` | L96–113 | Six Unicode values compare scalar slices to constructed Character Text. No guaranteed all mismatch positions or embedded NUL comparison. |
| operators: `tests/regressions.py` | L223–236 | Text order is rejected; x==x true and a+b outputab. No supported Text ordering. |
| literal: `tests/compiler-hardening.py` | L89–96 | Exact a/é/中/🙂/newline/tab/backslash values and absence of runtime literal reads; different supplementary Go scalar and aggregate sum absent. |
| peer-unicode: `tests/peer-research-semantics.py` | L37–56, L99–116 | bβ𝔹 values, flag reconstruction, abc日本語 reconstruction and empty Text fresh-binding control. |
| peer-runtime: `tests/memory-research-peer-projections.py` | L62–175, L176–275, L277–317 | Nine original methods; copy/alias/literal/producer/NaN/subnormal/effect/arithmetic/wide-record properties. Scalar loop binding after in-body source mutation not checked here. |
| native-text: `tests/runtime-unit.c` | L86–180, L360–367 | Unicode mixed/backward indices, nested view equals cd, scalar0..U+10FFFF roundtrips. These are local native observations, not peer literal syntax. |
| native-nul: `tests/compiler-slice-cache.c` | L30–36 | a,NUL,b full slice exact bytes; no public equality mismatch after NUL. |
| native-ascii: `tests/memory-research-ascii-join.c` | L55–93 | ASCII inputs insert NUL every17 bytes; join uses byte lengths and memcmp. No all-position public equality matrix. |
| fuzz-text: `tests/fuzz.py` | L180–235 | Five labels and split join equality success; no guaranteed NUL/negative comparator boundary matrix. |
| number-equality: `tests/conformance/numbers-and-comparisons/program.min` | L1–9 | same==same only for Text. |

Selective implementation reads are frozen too: compiler/compiler.min L278–383 (escape handling), L3681–3797 (for capture/private counter), L4130–4139 (jump syntax); runtime/minyar_runtime.c L407–444 (length/content equality). Those bodies suggest where a regression is useful; reading them does not validate execution. Other implementation extents are unreviewed in this lane.

## Complete per-unit dispositions

Grouping is one Go character failure predicate, Go string semantic observation/predicate, Zig named test with all in-file helpers, or libc++ assert site. The [JSON ledger](peer-readonly-text-loops-round8.json) retains exact source strings, every guard/site/phase driver, lexical sub-dispositions and local spans. Helpers/assertion sites are not extra groups, executions or ports.

### C1 — Supplementary scalar escape value

[test/char_lit.go L37–40](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/char_lit.go#L37-L40) — **incompatible_as_written**.

Expected from source: U+EBABE equals 0xEBABE (965310); mismatch exits1.

Minyar assessment: Minyar has no Go eight-digit Unicode escape contract. Character(965310) numeric control is possible but does not test this source spelling. Do not add an escape feature.

Related local IDs: literal, native-text.
Oracle/failure source sites: L37.

### C2 — All 22 literal contributions and exact sum

[test/char_lit.go L14–36, L41–44](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/char_lit.go#L14-L36) — **adapt_pending**.

Expected from source: All22 contributions sum to0x20E213=2155027; L41 failure exits1.

Minyar assessment: Explicit Integer(Character) contributions, numeric Character values for unsupported escapes, preserve fitting scalar sum. This is a value projection only: Go uint64/untyped rune arithmetic and unsupported escape spellings are excluded. Round4P5 already proposes related scalar controls; no new standalone literal proposal.

Related local IDs: literal, native-text, peer-unicode.
Oracle/failure source sites: L41.

### K1 — literal print

[test/ken/string.go L17–18](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/string.go#L17-L18) — **adapt_pending**.

Expected from source: abc

Minyar assessment: Ordinary quoted Text abc prints abc plus Minyar newline; Go raw quotes and no-newline print are excluded.

Related local IDs: text-list, unicode-properties, operators, peer-unicode.

### K2 — variable print

[test/ken/string.go L20–21](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/string.go#L20-L21) — **adapt_pending**.

Expected from source: xyz-

Minyar assessment: Print one concatenated Text xyz-; multiargument/no-newline print differs.

Related local IDs: text-list, unicode-properties, operators, peer-unicode.

### K3 — literal concatenation

[test/ken/string.go L23–24](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/string.go#L23-L24) — **adapt_pending**.

Expected from source: abcxyz-

Minyar assessment: Ordinary Text+ preserves content; Go raw syntax and print framing excluded.

Related local IDs: text-list, unicode-properties, operators, peer-unicode.

### K4 — variable concatenation

[test/ken/string.go L26–27](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/string.go#L26-L27) — **adapt_pending**.

Expected from source: abcxyz-

Minyar assessment: Text variables with + preserve content; no lifetime/copy claim.

Related local IDs: text-list, unicode-properties, operators, peer-unicode.

### K5 — literal relations

[test/ken/string.go L29–32](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/string.go#L29-L32) — **adapt_pending**.

Expected from source: abc==xyz false; abc!=abc false; abc>xyz false

Minyar assessment: First two relations map to quoted Text ==/!=. Text > is incompatible; no order API added.

Related local IDs: text-list, unicode-properties, operators, peer-unicode.
Oracle/failure source sites: L30.

### K6 — variable relations

[test/ken/string.go L34–37](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/string.go#L34-L37) — **adapt_pending**.

Expected from source: a==b false; a!=a false; a>b false

Minyar assessment: First two Text relations transfer; Text > excluded. Independent exact operands required.

Related local IDs: text-list, unicode-properties, operators, peer-unicode.
Oracle/failure source sites: L35.

### K7 — assigned concatenation

[test/ken/string.go L39–41](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/string.go#L39-L41) — **adapt_pending**.

Expected from source: c becomes abcxyz

Minyar assessment: Ordinary assignment and Text+ preserve value; pointer distinctness unasserted.

Related local IDs: text-list, unicode-properties, operators, peer-unicode.

### K8 — compound concatenation

[test/ken/string.go L43–46](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/string.go#L43-L46) — **adapt_pending**.

Expected from source: c becomes abcxyz

Minyar assessment: Existing Text += applies in order; print framing differs.

Related local IDs: text-list, unicode-properties, operators, peer-unicode.

### K9 — right operand receiver assignment

[test/ken/string.go L48–51](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/string.go#L48-L51) — **adapt_pending**.

Expected from source: c=b then c=a+c gives abcxyz

Minyar assessment: Use existing assignment and concatenation; old right receiver must supply xyz. No pointer identity/lifetime claim from same printed value.

Related local IDs: text-list, unicode-properties, operators, peer-unicode.

### K10 — ASCII length

[test/ken/string.go L53–57](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/string.go#L53-L57) — **adopt_pending**.

Expected from source: len(c)=6

Minyar assessment: c.length6 agrees for ASCII; Go byte length and Minyar scalar length are not equated for general Unicode.

Related local IDs: text-list, unicode-properties, operators, peer-unicode.
Oracle/failure source sites: L54.

### K11 — ASCII indexed recomputation

[test/ken/string.go L59–65](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/string.go#L59-L65) — **adapt_pending**.

Expected from source: All six c[i] equal (a+b)[i]

Minyar assessment: Scalar Character equality for ASCII with for i in0..6; Go byte indices excluded for Unicode. This is variant equality, not independent all-six code oracle.

Related local IDs: text-list, unicode-properties, operators, peer-unicode.
Oracle/failure source sites: L61.

### K12 — two slices and newline

[test/ken/string.go L67–70](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/string.go#L67-L70) — **adapt_pending**.

Expected from source: abc then xyz then newline printed

Minyar assessment: slice(0,3),slice(3,6) contents transfer for ASCII; public print framing differs. No asserted output golden in selected file.

Related local IDs: text-list, unicode-properties, operators, peer-unicode.

### K13 — constant scalar to string

[test/ken/string.go L72–76](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/string.go#L72-L76) — **adopt_pending**.

Expected from source: string(x rune)=x Text

Minyar assessment: Text('x') preserves the scalar value; Text(Integer120) would be decimal120 and is not the mapping.

Related local IDs: text-list, unicode-properties, operators, peer-unicode.
Oracle/failure source sites: L74.

### K14 — variable scalar to string

[test/ken/string.go L78–83](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/string.go#L78-L83) — **adopt_pending**.

Expected from source: v=x rune; string(v)=x

Minyar assessment: Bind Character x and use Text(v). Do not substitute Integer-to-Text formatting.

Related local IDs: text-list, unicode-properties, operators, peer-unicode.
Oracle/failure source sites: L81.

### K15 — byte array conversion

[test/ken/string.go L85–93](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/string.go#L85-L93) — **incompatible_as_written**.

Expected from source: Byte array a,b,c converts to abc

Minyar assessment: Minyar has no public Bytes-to-Text reinterpretation constructor. Rebuilding Characters would erase raw-byte conversion/copy and invalid-UTF8 semantics.

Related local IDs: text-list, unicode-properties, operators, peer-unicode.
Oracle/failure source sites: L91.

### K16 — rune array conversion

[test/ken/string.go L95–103](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/string.go#L95-L103) — **adapt_pending**.

Expected from source: a,U+1234,c converts to aሴc

Minyar assessment: Explicit List<Character> construction and loop Text(character) joins preserve exact three scalars; no Go array conversion, rune width, source escape or implicit copy equivalence.

Related local IDs: text-list, unicode-properties, operators, peer-unicode.
Oracle/failure source sites: L101.

### K17 — byte array pointer conversion

[test/ken/string.go L105–113](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/string.go#L105-L113) — **incompatible_as_written**.

Expected from source: new byte array pointer converts to abc

Minyar assessment: Raw pointer allocation and byte-array string conversion absent. ASCII equality does not justify pointer/encoding features.

Related local IDs: text-list, unicode-properties, operators, peer-unicode.
Oracle/failure source sites: L111.

### Z1 — continue in for loop

[test/behavior/for.zig L7–20](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L7-L20) — **adopt_pending**.

Expected from source: Continue before break visits1,2,3, sum6.

Minyar assessment: Ordinary List<Integer> for, +=,continue,break preserve exact sum. Related conformance has different order/threshold.

Related local IDs: loops.
Oracle/failure source sites: L19.
Backend skip guards: L8 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.

### Z2 — break from outer for loop

[test/behavior/for.zig L22–25](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L22-L25) — **incompatible_as_written**.

Expected from source: Outer labeled break leaves after inner visit1.

Minyar assessment: Minyar break targets innermost loop only; flag/function-return rewrites change control contract. Comptime excluded.

Related local IDs: loops.
Oracle/failure source sites: L36.
Additional complete in-file helper/declaration extents: L27–37.
Excluded comptime/inline phase sites: L24.

### Z3 — continue outer for loop

[test/behavior/for.zig L39–42](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L39-L42) — **incompatible_as_written**.

Expected from source: Labeled outer continue leaves inner each time, counter4.

Minyar assessment: No labeled continue or comptime. Four values alone do not prove same jump lowering.

Related local IDs: loops.
Oracle/failure source sites: L53.
Additional complete in-file helper/declaration extents: L44–54.
Excluded comptime/inline phase sites: L41.

### Z4 — ignore lval with underscore (for loop)

[test/behavior/for.zig L56–65](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L56-L65) — **incompatible_as_written**.

Expected from source: Empty void-array loop analysis succeeds; body never entered.

Minyar assessment: No stored Nothing/void-array or underscore zip payload. No value assertions.

Related local IDs: loops.

### Z5 — basic for loop

[test/behavior/for.zig L67–108](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L67-L108) — **adapt_pending**.

Expected from source: 24 output bytes repeat9,8,7,6,0,1,2,3 three times; full mem.eql.

Minyar assessment: Explicit Integer List loops and index counter can build this full vector; excludes fixed-array repeat, pointers, writable descriptors and width casts.

Related local IDs: loops, peer-runtime.
Oracle/failure source sites: L107.
Backend skip guards: L68 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest;`; L69 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L70 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z6 — for with null and T peer types and inferred result location type

[test/behavior/for.zig L110–129](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L110-L129) — **incompatible_as_written**.

Expected from source: Inputs1,2 contain no10, loop yields null; panic branch unentered at runtime and comptime.

Minyar assessment: No optional/loop expression/peer result-location type. Numeric values alone erase contract.

Related local IDs: loops.
Oracle/failure source sites: L123.
Backend skip guards: L111 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest;`; L112 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L113 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.
Excluded comptime/inline phase sites: L128.

### Z7 — 2 break statements and an else

[test/behavior/for.zig L131–148](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L131-L148) — **incompatible_as_written**.

Expected from source: entry(true,false) yields loop true on first element; both phases.

Minyar assessment: Break operands and loop else expressions absent. Undefined buffer contents are never read; no initialization oracle.

Related local IDs: loops.
Oracle/failure source sites: L143.
Backend skip guards: L132 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.
Excluded comptime/inline phase sites: L147.

### Z8 — for loop with pointer elem var

[test/behavior/for.zig L150–169](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L150-L169) — **adapt_pending**.

Expected from source: abcdefg bytes increment to bcdefgh; capture pointer types constu8 and mutableu8.

Minyar assessment: Explicit initialized Bytes and indexed increments project transformed ASCII values only. Pointer capture and TypeOf assertions incompatible.

Related local IDs: peer-runtime.
Oracle/failure source sites: L159, L163, L167.
Additional complete in-file helper/declaration extents: L171–175.
Backend skip guards: L151 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L152 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L153 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z9 — for copies its payload

[test/behavior/for.zig L177–192](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L177-L192) — **adapt_pending**.

Expected from source: Captured scalar remains1,2,3 while corresponding source grows by99.

Minyar assessment: Use List<Integer> scalar capture and explicit index; captured scalar is snapshot, List itself shared. No implicit array/row copying or comptime. Source post-state is unasserted upstream.

Related local IDs: loops, peer-runtime.
Oracle/failure source sites: L186.
Backend skip guards: L178 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.
Excluded comptime/inline phase sites: L191.

### Z10 — for on slice with allowzero ptr

[test/behavior/for.zig L194–208](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L194-L208) — **incompatible_as_written**.

Expected from source: allowzero pointer/slice captures each1..4 both byvalue/byref in both phases.

Minyar assessment: No allowzero raw pointers, byref payloads or comptime; ordinary values do not test representation.

Related local IDs: loops.
Oracle/failure source sites: L202, L203.
Backend skip guards: L195 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L196 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L197 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.
Excluded comptime/inline phase sites: L207.

### Z11 — else continue outer for

[test/behavior/for.zig L210–222](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L210-L222) — **incompatible_as_written**.

Expected from source: First empty slice leads else continue; next one-element slice leads return.

Minyar assessment: Minyar no loop else or writable buffer slice. Discarded undefined item gives no content oracle.

Related local IDs: loops.
Backend skip guards: L211 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L212 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z12 — for loop with else branch

[test/behavior/for.zig L224–243](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L224-L243) — **incompatible_as_written**.

Expected from source: Odd1 continues then even2 breaks with4; both else fallback1 and panic unentered.

Minyar assessment: Loop expressions and break values absent. Explicit function returns would be a different control algorithm.

Related local IDs: loops.
Oracle/failure source sites: L232, L240, L241.

### Z13 — count over fixed range

[test/behavior/for.zig L245–255](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L245-L255) — **adopt_pending**.

Expected from source: Exclusive0..6 sum15.

Minyar assessment: Integer for0..6 and += project exact bounded runtime sum, no unsigned-width proof.

Related local IDs: loops.
Oracle/failure source sites: L254.
Backend skip guards: L246 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L247 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`.

### Z14 — two counters

[test/behavior/for.zig L257–268](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L257-L268) — **adapt_pending**.

Expected from source: Ten zipped indices satisfy j=i+10, sum10.

Minyar assessment: Explicit j=i+10 in ordinary0..10 loop projects values, excludes multi-range zip evaluation/length contract.

Related local IDs: loops.
Oracle/failure source sites: L264, L267.
Backend skip guards: L258 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L259 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`.

### Z15 — 1-based counter and ptr to array

[test/behavior/for.zig L270–300](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L270-L300) — **adapt_pending**.

Expected from source: Positions1..5 have h,e,l,l,o; ok5.

Minyar assessment: Text hello scalar iteration with explicit1-based counter preserves six oracles for ASCII; zip/pointer input excluded.

Related local IDs: loops, peer-unicode.
Oracle/failure source sites: L278, L282, L286, L290, L294, L299.
Backend skip guards: L271 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L272 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`.

### Z16 — slice and two counters, one is offset and one is runtime

[test/behavior/for.zig L302–329](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L302-L329) — **adapt_pending**.

Expected from source: blah indices b0/c1,l1/c2,a2/c3,h3/c4.

Minyar assessment: Ordinary Text iteration with explicit0/1-based counters preserves eight exact mappings. No triple zip or runtime-range pairing semantics; count is not separately asserted.

Related local IDs: loops.
Oracle/failure source sites: L313, L314, L317, L318, L321, L322, L325, L326.
Backend skip guards: L303 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L304 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L305 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z17 — two slices, one captured by-ref

[test/behavior/for.zig L331–348](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L331-L348) — **adapt_pending**.

Expected from source: Writable slice receives b,l,a,h at all four positions.

Minyar assessment: Initialized Bytes plus explicit indexed copy preserves four values; no writable slice view, pointer payload or zip equivalence.

Related local IDs: peer-runtime.
Oracle/failure source sites: L344, L345, L346, L347.
Backend skip guards: L332 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L333 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L334 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z18 — raw pointer and slice

[test/behavior/for.zig L350–367](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L350-L367) — **incompatible_as_written**.

Expected from source: Raw pointer plus slice writes blah into first4buf bytes.

Minyar assessment: No raw pointer captures or mixed pointer/slice zip. Distinct buffers do not establish overlap correctness.

Related local IDs: peer-runtime.
Oracle/failure source sites: L363, L364, L365, L366.
Backend skip guards: L351 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L352 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L353 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z19 — raw pointer and counter

[test/behavior/for.zig L369–385](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L369-L385) — **incompatible_as_written**.

Expected from source: Raw pointer plus bounded counter writes ABCD first4positions.

Minyar assessment: No raw-pointer iteration/typed cast; ordinary Bytes algorithm is not this contract.

Related local IDs: peer-runtime.
Oracle/failure source sites: L381, L382, L383, L384.
Backend skip guards: L370 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L371 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L372 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.

### Z20 — inline for with slice as the comptime-known

[test/behavior/for.zig L387–415](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L387-L415) — **incompatible_as_written**.

Expected from source: Comptime lo characters pair with runtime3,4; ok2; other char compileError.

Minyar assessment: Mixed compile-time argument and runtime counter specialization is core; ordinary loop erases it.

Related local IDs: loops.
Oracle/failure source sites: L399, L402, L405, L414.
Backend skip guards: L388 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L389 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`.
Excluded comptime/inline phase sites: L387, L397, L410.

### Z21 — inline for with counter as the comptime-known

[test/behavior/for.zig L417–446](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L417-L446) — **incompatible_as_written**.

Expected from source: Runtime lo characters pair with comptime3,4; ok2; other counter compileError.

Minyar assessment: No comptime parameter/type-specialized inline loop. Literal/runtime value equality insufficient.

Related local IDs: loops.
Oracle/failure source sites: L430, L433, L436, L445.
Backend skip guards: L418 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L419 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L420 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.
Excluded comptime/inline phase sites: L417, L428, L441.

### Z22 — inline for on tuple pointer

[test/behavior/for.zig L448–461](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L448-L461) — **incompatible_as_written**.

Expected from source: Inline tuple-pointer writes all fields to0,1,2; structural expectEqual.

Minyar assessment: No positional tuple, raw field pointer or inline loop; List field reads not library/type equivalence.

Related local IDs: loops.
Oracle/failure source sites: L460.
Backend skip guards: L449 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L450 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L451 `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`.
Excluded comptime/inline phase sites: L448, L456.

### Z23 — ref counter that starts at zero

[test/behavior/for.zig L463–475](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L463-L475) — **adapt_pending**.

Expected from source: Values and counters0,1,2 equal; dereferenced addresses also equal, runtime array and inline tuple.

Minyar assessment: Runtime Integer List plus explicit counter value projection only. Address-taking and tuple inline sites excluded.

Related local IDs: loops.
Oracle/failure source sites: L468, L469, L472, L473.
Backend skip guards: L464 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L465 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`.
Excluded comptime/inline phase sites: L471.

### Z24 — inferred alloc ptr of for loop

[test/behavior/for.zig L477–497](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L477-L497) — **incompatible_as_written**.

Expected from source: Optional result null for condfalse; true payload for condtrue.

Minyar assessment: Optional and inferred loop-result allocation location absent.

Related local IDs: loops.
Oracle/failure source sites: L487, L495.
Backend skip guards: L478 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L479 `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`.

### Z25 — for loop results in a bool

[test/behavior/for.zig L499–505](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L499-L505) — **incompatible_as_written**.

Expected from source: Loop-expression breaks true for sole zero; expect true.

Minyar assessment: Boolean loop-expression/break operands absent; rewriting to mutable flag changes target.

Related local IDs: loops.
Oracle/failure source sites: L502.
Backend skip guards: L500 `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`.

### Z26 — return from inline for

[test/behavior/for.zig L507–517](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L507-L517) — **adapt_pending**.

Expected from source: S.do returnsfalse inside first inline iteration; finaltrue bypassed.

Minyar assessment: Ordinary function over one-element Text List can returnfalse; excludes tuple inline phase and generated pruning guarantees.

Related local IDs: loops.
Oracle/failure source sites: L516.
Excluded comptime/inline phase sites: L507, L510.

### Z27 — for loop 0 length range

[test/behavior/for.zig L519–526](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/for.zig#L519-L526) — **incompatible_as_written**.

Expected from source: Empty zipped range never instantiates comptime unreachable.

Minyar assessment: Runtime empty-loop nonentry is covered by original producer tests, but does not prove no comptime body instantiation.

Related local IDs: loops, peer-runtime.
Oracle/failure source sites: L524.
Excluded comptime/inline phase sites: L524.

### L1 — char_traits comparison source line22

[libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp L22–22](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp#L22-L22) — **adapt_pending**.

Expected from source: Result0

Minyar assessment: Quoted ASCII Text equality preserves this bounded value relation; no char_traits API, explicit-length pointer input, C++17 constexpr or IR equivalence.

Related local IDs: operators, number-equality, native-text.
Oracle/failure source sites: L22.
Classification: C++ standard-library behavior; not compiler IR equivalence. C++17+ static_assert(test()) L54–56 remains an incompatible phase guarantee.

### L2 — char_traits comparison source line23

[libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp L23–23](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp#L23-L23) — **incompatible_as_written**.

Expected from source: No dereference at n0, result0

Minyar assessment: Raw null-pointer/zero-count library guarantee absent in Minyar.

Related local IDs: operators, number-equality, native-text.
Oracle/failure source sites: L23.
Classification: C++ standard-library behavior; not compiler IR equivalence. C++17+ static_assert(test()) L54–56 remains an incompatible phase guarantee.

### L3 — char_traits comparison source line25

[libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp L25–25](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp#L25-L25) — **adapt_pending**.

Expected from source: Result0

Minyar assessment: Quoted ASCII Text equality preserves this bounded value relation; no char_traits API, explicit-length pointer input, C++17 constexpr or IR equivalence.

Related local IDs: operators, number-equality, native-text.
Oracle/failure source sites: L25.
Classification: C++ standard-library behavior; not compiler IR equivalence. C++17+ static_assert(test()) L54–56 remains an incompatible phase guarantee.

### L4 — char_traits comparison source line26

[libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp L26–26](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp#L26-L26) — **incompatible_as_written**.

Expected from source: Negative comparison sign

Minyar assessment: Minyar Text supports ==/!= only. Character ordering or an original lexicographic algorithm would not implement this Text/library comparison API.

Related local IDs: operators, number-equality, native-text.
Oracle/failure source sites: L26.
Classification: C++ standard-library behavior; not compiler IR equivalence. C++17+ static_assert(test()) L54–56 remains an incompatible phase guarantee.

### L5 — char_traits comparison source line27

[libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp L27–27](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp#L27-L27) — **incompatible_as_written**.

Expected from source: Positive comparison sign

Minyar assessment: Minyar Text supports ==/!= only. Character ordering or an original lexicographic algorithm would not implement this Text/library comparison API.

Related local IDs: operators, number-equality, native-text.
Oracle/failure source sites: L27.
Classification: C++ standard-library behavior; not compiler IR equivalence. C++17+ static_assert(test()) L54–56 remains an incompatible phase guarantee.

### L6 — char_traits comparison source line29

[libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp L29–29](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp#L29-L29) — **adapt_pending**.

Expected from source: Result0

Minyar assessment: Quoted ASCII Text equality preserves this bounded value relation; no char_traits API, explicit-length pointer input, C++17 constexpr or IR equivalence.

Related local IDs: operators, number-equality, native-text.
Oracle/failure source sites: L29.
Classification: C++ standard-library behavior; not compiler IR equivalence. C++17+ static_assert(test()) L54–56 remains an incompatible phase guarantee.

### L7 — char_traits comparison source line30

[libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp L30–30](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp#L30-L30) — **incompatible_as_written**.

Expected from source: Negative comparison sign

Minyar assessment: Minyar Text supports ==/!= only. Character ordering or an original lexicographic algorithm would not implement this Text/library comparison API.

Related local IDs: operators, number-equality, native-text.
Oracle/failure source sites: L30.
Classification: C++ standard-library behavior; not compiler IR equivalence. C++17+ static_assert(test()) L54–56 remains an incompatible phase guarantee.

### L8 — char_traits comparison source line31

[libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp L31–31](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp#L31-L31) — **incompatible_as_written**.

Expected from source: Negative comparison sign

Minyar assessment: Minyar Text supports ==/!= only. Character ordering or an original lexicographic algorithm would not implement this Text/library comparison API.

Related local IDs: operators, number-equality, native-text.
Oracle/failure source sites: L31.
Classification: C++ standard-library behavior; not compiler IR equivalence. C++17+ static_assert(test()) L54–56 remains an incompatible phase guarantee.

### L9 — char_traits comparison source line32

[libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp L32–32](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp#L32-L32) — **incompatible_as_written**.

Expected from source: Positive comparison sign

Minyar assessment: Minyar Text supports ==/!= only. Character ordering or an original lexicographic algorithm would not implement this Text/library comparison API.

Related local IDs: operators, number-equality, native-text.
Oracle/failure source sites: L32.
Classification: C++ standard-library behavior; not compiler IR equivalence. C++17+ static_assert(test()) L54–56 remains an incompatible phase guarantee.

### L10 — char_traits comparison source line33

[libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp L33–33](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp#L33-L33) — **incompatible_as_written**.

Expected from source: Positive comparison sign

Minyar assessment: Minyar Text supports ==/!= only. Character ordering or an original lexicographic algorithm would not implement this Text/library comparison API.

Related local IDs: operators, number-equality, native-text.
Oracle/failure source sites: L33.
Classification: C++ standard-library behavior; not compiler IR equivalence. C++17+ static_assert(test()) L54–56 remains an incompatible phase guarantee.

### L11 — char_traits comparison source line35

[libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp L35–35](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp#L35-L35) — **adapt_pending**.

Expected from source: Result0

Minyar assessment: Quoted ASCII Text equality preserves this bounded value relation; no char_traits API, explicit-length pointer input, C++17 constexpr or IR equivalence.

Related local IDs: operators, number-equality, native-text.
Oracle/failure source sites: L35.
Classification: C++ standard-library behavior; not compiler IR equivalence. C++17+ static_assert(test()) L54–56 remains an incompatible phase guarantee.

### L12 — char_traits comparison source line36

[libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp L36–36](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp#L36-L36) — **incompatible_as_written**.

Expected from source: Negative comparison sign

Minyar assessment: Minyar Text supports ==/!= only. Character ordering or an original lexicographic algorithm would not implement this Text/library comparison API.

Related local IDs: operators, number-equality, native-text.
Oracle/failure source sites: L36.
Classification: C++ standard-library behavior; not compiler IR equivalence. C++17+ static_assert(test()) L54–56 remains an incompatible phase guarantee.

### L13 — char_traits comparison source line37

[libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp L37–37](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp#L37-L37) — **incompatible_as_written**.

Expected from source: Negative comparison sign

Minyar assessment: Minyar Text supports ==/!= only. Character ordering or an original lexicographic algorithm would not implement this Text/library comparison API.

Related local IDs: operators, number-equality, native-text.
Oracle/failure source sites: L37.
Classification: C++ standard-library behavior; not compiler IR equivalence. C++17+ static_assert(test()) L54–56 remains an incompatible phase guarantee.

### L14 — char_traits comparison source line38

[libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp L38–38](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp#L38-L38) — **incompatible_as_written**.

Expected from source: Negative comparison sign

Minyar assessment: Minyar Text supports ==/!= only. Character ordering or an original lexicographic algorithm would not implement this Text/library comparison API.

Related local IDs: operators, number-equality, native-text.
Oracle/failure source sites: L38.
Classification: C++ standard-library behavior; not compiler IR equivalence. C++17+ static_assert(test()) L54–56 remains an incompatible phase guarantee.

### L15 — char_traits comparison source line39

[libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp L39–39](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp#L39-L39) — **incompatible_as_written**.

Expected from source: Positive comparison sign

Minyar assessment: Minyar Text supports ==/!= only. Character ordering or an original lexicographic algorithm would not implement this Text/library comparison API.

Related local IDs: operators, number-equality, native-text.
Oracle/failure source sites: L39.
Classification: C++ standard-library behavior; not compiler IR equivalence. C++17+ static_assert(test()) L54–56 remains an incompatible phase guarantee.

### L16 — char_traits comparison source line40

[libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp L40–40](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp#L40-L40) — **incompatible_as_written**.

Expected from source: Positive comparison sign

Minyar assessment: Minyar Text supports ==/!= only. Character ordering or an original lexicographic algorithm would not implement this Text/library comparison API.

Related local IDs: operators, number-equality, native-text.
Oracle/failure source sites: L40.
Classification: C++ standard-library behavior; not compiler IR equivalence. C++17+ static_assert(test()) L54–56 remains an incompatible phase guarantee.

### L17 — char_traits comparison source line41

[libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp L41–41](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp#L41-L41) — **incompatible_as_written**.

Expected from source: Positive comparison sign

Minyar assessment: Minyar Text supports ==/!= only. Character ordering or an original lexicographic algorithm would not implement this Text/library comparison API.

Related local IDs: operators, number-equality, native-text.
Oracle/failure source sites: L41.
Classification: C++ standard-library behavior; not compiler IR equivalence. C++17+ static_assert(test()) L54–56 remains an incompatible phase guarantee.

### L18 — char_traits comparison source line46

[libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp L46–46](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/strings/char.traits/char.traits.specializations/char.traits.specializations.char/compare.pass.cpp#L46-L46) — **incompatible_as_written**.

Expected from source: Unsigned char ordering: all-bits-one compares greater than1

Minyar assessment: Unsigned byte comparison is a C++ library behavior. Invalid UTF8 byte255 must not be turned into a Minyar Character-equivalent Text contract.

Related local IDs: operators, number-equality, native-text.
Oracle/failure source sites: L46.
Additional complete in-file helper/declaration extents: L44–45.
Classification: C++ standard-library behavior; not compiler IR equivalence. C++17+ static_assert(test()) L54–56 remains an incompatible phase guarantee.

## Assertion helpers, drivers and unreviewed complements

| Pinned support file | Exact reviewed spans | Meaning |
| --- | --- | --- |
| [lib/std/testing.zig](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/lib/std/testing.zig) | L69–218, L604–608 | expect false errors; expectEqual resolves common type and compares scalars, tuple struct fields recursively, optional presence/payload. Formatting internals not audited. |
| [lib/std/mem.zig](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/lib/std/mem.zig) | L675–689, L693–707, L729–787, L4344–4357 | Length/content equality; tiny and vector/word byte paths; zero-size sliceAsBytes. SIMD choice/transitive implementations remain outside selective review. Vector comparison disabled on aarch64/powerpc/riscv64/spirv and under builtin.fuzz (L677–689); tests retain separate backend skips. |
| [lib/std/meta.zig](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/lib/std/meta.zig) | L1108–1151 | u8 unique representation permits byte path; recursive representation checks are not ownership proof. |
| [libcxx/test/support/test_macros.h](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/support/test_macros.h) | L88–105, L175–179 | TEST_STD_VER derives from language mode unless overridden; TEST_CONSTEXPR_CXX17 enables constexpr only>=17. Platform assert macro expansion/NDEBUG configuration not inspected or run. |
| [lib/std/debug.zig](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/lib/std/debug.zig) | L545–560 | debug.assert false is unreachable; detects runtime failure only in safe modes. Needed eqlBytes compile-time precondition, not an always-active standalone test oracle. |

Full helper bytes are retained, but only those spans are reviewed. Every complement is explicit in JSON. SIMD choice internals, transitive standard utilities, platform cassert/NDEBUG configuration and library ABI implementations are not exhaustively audited.

In-file Zig helper bodies testBreakOuter L27–37, testContinueOuter L44–54 and mangleString L171–175 are complete. Nested doTheTest/entry/check/do definitions are wholly within each listed named-test extent. Go main bodies are complete; they have no extra in-file assertion helper. libc++ test L21–50 and main L52–59 are read wholly. main invokes test at runtime and static_assert for TEST_STD_VER>=17. Assertions require enabled cassert; no configured C++ mode or actual execution is claimed. Zig 48 backend skips and62 oracle/failure source sites are attributed once; compileError/panic branches are forbidden paths, not expected diagnostics or observed failures.

## Original precise pending regressions

### P1 — Exact Text equality through embedded NUL and every mismatch position

Inspected local fixtures establish NUL byte preservation and positive Text equality but not every unequal position across all short-comparison byte lengths0..17 plus31/32/33, unequal prefix length or equal-length difference after a NUL followed by a multibyte scalar. Claim is bounded to cited spans/search; no repository-wide absence proof.

Round4P3/P5 concern scalar positions/literal controls; P6 slices/endpoints. Round5/6/7 and current nine runtime methods do not propose this public negative-comparison discriminator matrix. C++ test itself has no embedded-NUL mismatch; that is an original extension. Construction does not guarantee distinct addresses; no address/ownership claim.

```minyar
function build(size: Integer, changed: Integer): Text {
    let result = ""
    for position in 0..size {
        let code = 97
        if position == size / 2 { code = 0 }
        if position == changed { code = 98 }
        result = result + Text(Character(code))
    }
    return result
}
let sizes = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 31, 32, 33]
for size in sizes {
    let left = build(size, -1)
    let right = build(size, -1)
    print(left == right)
    print(left != right)
    print(left.length)
    print(left.byteLength)
    print(left == right + "c")
    for position in 0..size {
        print(left == build(size, position))
        print(left != build(size, position))
    }
}
let zero = Text(Character(0))
let left = "é" + zero + "🙂"
let equal = Text(Character(233)) + zero + Text(Character(128578))
let different = "é" + zero + "🙃"
print(left == equal)
print(left != equal)
print(left == different)
print(left != different)
print(left.length)
print(left.byteLength)
print(Integer(left[1]))
print(left.slice(1, 3) == zero + "🙂")
```

Independent expected result: For each explicit size n: true,false,n,n,false, then n pairs false,true. Unicode tail: true,false,false,true,3,7,0,true. All contents valid UTF8; no ordering/normalization expectation.

Status: original proposal only, unimplemented/uncompiled/unexecuted. Use current syntax and contract. Core owner may choose existing candidate-aware O0/O2/sanitizer/ownership validation; record any actual red rather than inventing a production defect.

### P2 — Scalar payload captured before source mutation across continue and break

Conformance controls jump targets with ranges/Text; runtime producer test sums captured values without mutation; row projection controls aliases versus an explicit whole-row copy. None of those cited spans mutates the current Integer List position after for scalar capture, reassigns the loop binding, continues once then breaks before the third position.

Round2R2 already proposes reassignment of a range loop binding and once-only bounds; retain it rather than repeat it here. This adds in-body collection mutation against captured scalar and explicit untouched-third-slot/tail oracles. No copied row, pointer payload, label, zip or comptime behavior.

```minyar
let source = [1, 2, 3]
let position = 0
let visits = 0
let tail = 0
let captured = 0
for value in source {
    let index = position
    position += 1
    visits += 1
    source[index] += 99
    captured = captured * 10 + value
    value = 900
    if index == 0 { continue }
    if index == 1 { break }
    tail += 1
}
print(captured)
print(visits)
print(position)
print(tail)
for value in source { print(value) }
```

Independent expected result: Exact stdout:

```text
12
2
2
0
100
101
3
```

Status: original proposal only, unimplemented/uncompiled/unexecuted. Use current syntax and contract. Core owner may choose existing candidate-aware O0/O2/sanitizer/ownership validation; record any actual red rather than inventing a production defect.

## Prior executable evidence and final handoff

The current runtime report and archived results were inspected without running anything. Saved run-l5_218bk has eight original methods, three configurations and 48 executions; the final actual generated-link flags count24 O0/24 O2. run-1a2ft1yr separately has one wide-record method and 6 executions, with3 O0/3 O2. Native runtime C uses O2; sanitized C uses O1. No complete nine-method54-execution final-source matrix is claimed. These are original Minyar tests, not literal upstream ports. Earlier18/24 sanitizer executions were effectivelyO1; runtime-peer-optimization-correction.json remains authoritative and historical ledgers are unchanged. [Documentary check of saved results](../../evidence/peer-readonly/text-loops-round8/prior-runtime-document-checks.json).

Prior selected rounds2–7 have 488 heterogeneous groups across 22 deduplicated complete files. With this round the **selected-report union is552 groups across26 files**. These numbers come from saved authored ledgers, with array.zig deduplicated across2/3 and convert/eval retrieval promoted only at round6. They are not total campaign coverage, a language-suite denominator, ports, or passing tests.

31 adopt/adapt groups and both original proposals await executable work; 33 incompatible groups remain excluded. Zero selected lines remain unread. Other peer files, exact support complements and unselected screening candidates remain outside this round’s credited review. Failed raw discovery candidates returned404 (or web fetch error); no content/service restriction arose. Prior restricted Rust and recorded directory/university restrictions were not retried or bypassed. All sources used for dispositions are pinned.

Only peer-readonly-text-loops-round8.md/.json and evidence/peer-readonly/text-loops-round8/ were authored. Central manifests were left unchanged; core soak, aggregate review, demand-certificate research and stopped execution lanes were untouched. [Handoff](../../evidence/peer-readonly/text-loops-round8/handoff.json) retains IDs/counts/boundaries. Campaign earliest completion remains 2026-10-04 06:54:29 UTC and campaign completion is not claimed.

Documentary final check: **532 consistent hash/span/count/attribution checks**, with no test execution. The initial erroneous local expected.stdout extent L1–18 was corrected to its actual 17 physical lines before handoff. [Checks](../../evidence/peer-readonly/text-loops-round8/document-checks.json) also record the campaign README changing concurrently: frozen `b669179308f0f40f304eca9f5abfde8cdf51890ee27e893459509b5ee2d508e2`, observed `6dd77e7c13164b10a35237855605c7646c29e222507774448bdce0031cc86e24`. This lane did not author that change; mappings bind to retained snapshots.
