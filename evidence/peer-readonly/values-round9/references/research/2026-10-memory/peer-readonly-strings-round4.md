# Read-only Text/Bytes/List peer comparison — round 4

Five complete previously unreviewed files, 2099 raw physical lines, 120 explicitly grouped comparisons: 65 Go groups and54 named Zig tests plus one module comptime group. 53 pending runtime projections, 67 incompatible-as-written groups. Seven original proposals; zero ports, executions, compilations, installations, code/test edits, commits, subagents or timing measurements. Quantities are derived from the saved JSON ledger, not estimates.

This is a new independent read-only lane. The prior restricted Rust resource was not retried or bypassed; stopped integration/literature/tooling lanes were not resumed. No content/service restriction or upstream unavailability occurred on these accessible official Go/Zig reads. Parent campaign completion remains its responsibility, with earliest completion06:54:29UTC; this record makes no elapsed-time or campaign-completion claim.

## Scope and immutable provenance

| File | Commit | Whole-file raw lines | SHA256 | License |
| --- | --- | --- | --- | --- |
| [test/copy.go](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/copy.go) | `56ebf80e57db9f61981fc0636fc6419dc6f68eda` | 1–351 | `e6ec5740b54c62d21e244e9a85b69e76b7e873c5e6c75d3ab630f05f43a5d1a6` | BSD-3-Clause |
| [test/string_lit.go](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go) | `56ebf80e57db9f61981fc0636fc6419dc6f68eda` | 1–150 | `02b55dc6e18a6768a7bb38408c02cdde4facc00efff64c6925f2a8d10107d232` | BSD-3-Clause |
| [test/range.go](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go) | `56ebf80e57db9f61981fc0636fc6419dc6f68eda` | 1–494 | `ab3d1479aa0d07a3ed28c10642a172820ed2be4a008df547af215867bd772c25` | BSD-3-Clause |
| [test/strcopy.go](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/strcopy.go) | `56ebf80e57db9f61981fc0636fc6419dc6f68eda` | 1–29 | `1104deacf844be15188fbcf8fd137a53cd9b5bd0f7c0a2c1f23c3723017ddcef` | BSD-3-Clause |
| [test/behavior/slice.zig](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig) | `3db960767d12b6214bcf43f1966a037c7a586a12` | 1–1075 | `3f1c58837a03e180b71fbe9e0e838a083509110caff11973e24d3022ac322c57` | MIT |

Complete raw bytes and pinned licenses are retained under `evidence/peer-readonly/strings-round4`. Use one-based physical raw-source line numbers; web rendering collapses blank lines and has different line totals. Supporting std assertions have selective body review only, no library-test credit. Exact source/helper spans, guards, local snapshots, prior record hashes, ownership boundary and documentary checks are in the structured provenance.

The pre-existing peer inventories mark all five selected files unreviewed. Existing utf.go/stringrange.go/append.go/divmod.go and string_literals.zig are excluded, together with rounds2/3 files. Prior rounds2+3 retain98 grouped comparisons across five files; this round adds no duplicate file credit. Inventories/central campaign records were not edited.

## Findings and limits

- Go copy.go swaps two separate input/output arrays. Its copy-up/copy-down comment does not establish same-buffer overlap; no overlap oracle is asserted. Count and prefix/copied/suffix checks span a grouped matrix, not individually executed ports.
- Go range.go abcd☺ byte positions0,1,2,3,4 sum10, which also matches scalar ordinals because the multi-byte scalar is last. P3 places multibyte scalars inside aé🙂b, distinguishing conceptual byte offsets0,1,3,7 from scalar ordinals0,1,2,3.
- Go string_lit.go accepts arbitrary invalid-byte strings, replaces invalid runes/surrogates with U+FFFD and preserves invalid byte roundtrips. Minyar Text rejects invalid UTF-8 and Character accepts only scalars. Binary preservation belongs to Bytes; no Text/Bytes conversion API is invented.
- Go strcopy.go asserts raw address inequality after a substring conversion. Minyar immutable Text may share its backing legitimately; Bytes copied-slice mutation independence is a separate contract. Minyar tiny-view copy guard applies only to sources larger than4KiB, not this2048-byte input.
- Zig writable slice views, descriptor len/ptr mutation, hidden sentinels readable at length, pointer/type/generic/comptime/ABI alignment contracts remain excluded. Ordinary Text/Bytes content projections do not cover them. In particular, Zig zero-length sentinel index0 reads2; Minyar empty index0 must stop.
- Selected Go loops assert once-evaluation for unchanged inputs. They do not establish fixed-versus-live length behavior during growth. Minyar List iteration rereads length; P4 adds an original bounded growth control without claiming peer equivalence.
- Existing native Bytes self-append and Text immutable-view lifetime/consuming-join fixtures are related source coverage. This lane ran none of them and makes no final-source or whole-campaign validation claim.

## Local fixture references

**unicode — `tests/regressions.py` L96–112.** Scalar indexing, slice(ordinal,ordinal+1), Text(Character), length/byteLength; inputs A,é,界,🙂,Aé界🙂 and combining é. Different exact literals from this round. Source only; not run.

**invalid-utf8 — `tests/regressions.py` L114–125.** File bytes C0 AF, ED A0 80, F4 90 80 80, E2 82 require exit1 and invalid UTF-8 diagnostic; no permissive replacement decoding. Source only; not run.

**scalar-boundary — `tests/runtime-unit.c` L359–367.** Native scalar roundtrip table includes zero and U+10FFFF; length1. Native ABI fixture, not compiler literal syntax or invalid Character traps. Source only; not run.

**byte-model — `tests/runtime-bytes.c` L33–99.** Native deterministic Bytes model: count/value oracle for mutation, clear/resize, self-append and sampled slice contents. Slice released before later source mutation, so copied-slice independence is not asserted. Source only; not run.

**byte-self — `tests/runtime-bytes.c` L61–65.** Native self-append doubles original bytes in the independent model. Does not establish in-place overlapping subrange copy or generated addBytes self-call. Source only; not run.

**byte-slice — `tests/conformance/bytes/program.min` L2–21.** Generated-syntax Bytes operations, slice(4,5) reads153 (expected.stdout L8), then byte iteration sum2759. No copy/source mutation contrast. Source only; not run.

**byte-empty — `tests/conformance/bytes/program.min` L32–38.** Clear length0, resize(3) zero at2, empty addBytes(loaded) length15. No explicit slice(length,length). Source only; not run.

**list-text — `tests/conformance/text-and-lists/program.min` L1–12.** Shared List additions/replacement, joinText Myar🙂, scalar length5 versus byteLength8, slice(1,4)=yar, typed nested empty List. Expected.stdout L1–6. Source only; not run.

**loops — `tests/conformance/loops-and-assignment/program.min` L9–24.** Range sum18 with break/continue; ordered Text List visits alpha,beta,gamma; Text héllo Character iteration skipping l. No effectful collection helper or loop growth assertion. Source only; not run.

**utf-loop — `tests/peer-research-semantics.py` L99–106.** abc日本語 scalar sequence/reconstruction and length6/byteLength12. Different literal; no once-evaluation counter. Source only; not run.

**empty-loop — `tests/peer-research-semantics.py` L108–117.** Empty Text loop visits0, leaves outer β code946; fresh binding, not Go assignment-form range semantics. Source only; not run.

**view-lifetime — `tests/runtime-unit.c` L162–192.** Native full slice identity, flattened nested immutable Text view root and surviving cd; retention guard copies one byte from8192-byte source. Public Text does not expose pointer identity. Source only; not run.

**text-self — `tests/memory-research-text-join-index.min` L31–47, 55–72.** Generated-syntax indexed Text self-join, empty join, retained immutable alias and view + suffix while root remains intact. Source expectations only. Source only; not run.

**receiver-order — `tests/adversarial.py` L83–103, 124–143.** Captured Text receiver survives effectful start/end helper replacement; output old!,new,last!. Indexed assignment events1 then2 and original!!. Different operation from Go parallel range assignment. Source only; not run.

**unicode-model — `tests/adversarial.py` L233–253.** Model-derived scalar lengths, byte lengths, every index and sampled slices, with alphabet containing zero, combining mark, Unicode maximum, quote/backslash. Not exact peer-case coverage or guaranteed sample at every endpoint. Source only; not run.

**text-abc — `tests/regressions.py` L77–90, 234–235.** Ordinary abc.slice(0,2)=ab and Text a+b=ab. Different exact nested ASCII substring sequence. Source only; not run.

**empty-list — `tests/recursive-data.py` L199–210.** Contextually typed empty List return/reassignment length0; no slice-pointer coercion/type machinery. Source only; not run.

**no-list-slice — `tests/regressions.py` L92–94.** Explicit diagnostic: List has no slice method; Text has no add method. No proposed writable List views. Source only; not run.

## One-to-one grouped comparisons

Each row below is an explicit grouped semantic unit with every attached assertion/helper retained in JSON. Upstream outcomes mean expected values inferred from pinned source, never observations. A pending runtime projection preserves only stated ordinary value behavior; listed exclusions remain unsupported. Pure incompatibilities can reference original contrast proposals without changing their disposition.

**C1 — [test/copy.go:L109–110](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/copy.go#L109-L110) — uint8 slice. Pending runtime projection.**

Upstream: For length0..39, in0..32, out0..32: n=min(length,40-in,40-out); returned count n, destination prefix/suffix unchanged, copied destination[out+j]=input[in+j] for0<=j<n. reset swaps two DISTINCT allocations; input/output do not overlap. Silent successful main. u8(i)=97+i%26; byte values97..122

Minyar: Bytes values fit directly; indexed writes into a destination using a separately copied source range.

Excluded/incompatible: No copy intrinsic, writable slice/view, capacity, named slice types, parallel swap or unsigned element-width semantics. A helper implemented with ordinary indexing would test its own algorithm, not Go copy lowering.

Inspected local references: byte-model. Exact bounded prefix/copied/suffix/count matrix absent from inspected fixtures; propose a small independent matrix rather than claiming the full upstream driver. Original proposal: P2.

**C2 — [test/copy.go:L111–112](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/copy.go#L111-L112) — string to uint8 slice. Pending runtime projection.**

Upstream: For length0..39, in0..32, out0..32: n=min(length,40-in,40-out); returned count n, destination prefix/suffix unchanged, copied destination[out+j]=input[in+j] for0<=j<n. reset swaps two DISTINCT allocations; input/output do not overlap. Silent successful main. ASCII inputS constructed from input8; same byte values

Minyar: Use Text indexing plus Integer(Character) only for these ASCII scalars, or initialize matching Bytes; no Text-to-Bytes conversion API is claimed.

Excluded/incompatible: No copy intrinsic, writable slice/view, capacity, named slice types, parallel swap or unsigned element-width semantics. A helper implemented with ordinary indexing would test its own algorithm, not Go copy lowering.

Inspected local references: byte-slice. Exact bounded prefix/copied/suffix/count matrix absent from inspected fixtures; propose a small independent matrix rather than claiming the full upstream driver. Original proposal: P2.

**C3 — [test/copy.go:L113–114](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/copy.go#L113-L114) — uint16 slice. Pending runtime projection.**

Upstream: For length0..39, in0..32, out0..32: n=min(length,40-in,40-out); returned count n, destination prefix/suffix unchanged, copied destination[out+j]=input[in+j] for0<=j<n. reset swaps two DISTINCT allocations; input/output do not overlap. Silent successful main. u16(i)=u8(i)*0x0101; values24929..31354

Minyar: A List<Integer> can hold these bounded values; explicit indexed destination writes preserve the value/count oracle.

Excluded/incompatible: No copy intrinsic, writable slice/view, capacity, named slice types, parallel swap or unsigned element-width semantics. A helper implemented with ordinary indexing would test its own algorithm, not Go copy lowering.

Inspected local references: loops. Exact bounded prefix/copied/suffix/count matrix absent from inspected fixtures; propose a small independent matrix rather than claiming the full upstream driver. Original proposal: P2.

**C4 — [test/copy.go:L115–116](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/copy.go#L115-L116) — distinct named uint32 slices. Pending runtime projection.**

Upstream: For length0..39, in0..32, out0..32: n=min(length,40-in,40-out); returned count n, destination prefix/suffix unchanged, copied destination[out+j]=input[in+j] for0<=j<n. reset swaps two DISTINCT allocations; input/output do not overlap. Silent successful main. u32(i)=u8(i)*0x01010101; values1633771873..2054847098

Minyar: A List<Integer> can hold these bounded values; named Go slice types have no Minyar counterpart.

Excluded/incompatible: No copy intrinsic, writable slice/view, capacity, named slice types, parallel swap or unsigned element-width semantics. A helper implemented with ordinary indexing would test its own algorithm, not Go copy lowering.

Inspected local references: loops. Exact bounded prefix/copied/suffix/count matrix absent from inspected fixtures; propose a small independent matrix rather than claiming the full upstream driver. Original proposal: P2.

**C5 — [test/copy.go:L117–118](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/copy.go#L117-L118) — uint64 slice. Pending runtime projection.**

Upstream: For length0..39, in0..32, out0..32: n=min(length,40-in,40-out); returned count n, destination prefix/suffix unchanged, copied destination[out+j]=input[in+j] for0<=j<n. reset swaps two DISTINCT allocations; input/output do not overlap. Silent successful main. u64(i)=u8(i)*0x0101010101010101, all top bytes<=0x7A and within signed64

Minyar: A List<Integer> can hold this particular value domain; full uint64 arithmetic/width is excluded.

Excluded/incompatible: No copy intrinsic, writable slice/view, capacity, named slice types, parallel swap or unsigned element-width semantics. A helper implemented with ordinary indexing would test its own algorithm, not Go copy lowering.

Inspected local references: loops. Exact bounded prefix/copied/suffix/count matrix absent from inspected fixtures; propose a small independent matrix rather than claiming the full upstream driver. Original proposal: P2.

**C6 — [test/copy.go:L336–346](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/copy.go#L336-L346) — array [0:] roundtrip. Pending runtime projection.**

Upstream: Forty byte values u8(i) survive input->array[0:]->zeroed output; verify8(40,0,0,40) checks count40 and every value.

Minyar: Fresh Bytes initialized explicitly, full-range Bytes.slice followed by explicit destination writes can check content and copy independence.

Excluded/incompatible: Go array-to-slice conversion, array storage and copy intrinsic excluded.

Inspected local references: byte-model, byte-slice. Full-range snapshot followed by destination/source mutation remains a narrow original control relative to sampled native slices. Original proposal: P1.

**L0 — [test/string_lit.go:L55–73](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L55-L73) — unasserted mixed interpreted/raw concatenation. Incompatible as written.**

Upstream: All literal syntax/concatenation must be accepted; s is later overwritten. No assertion checks the value of this initial concatenation.

Minyar: Ordinary Text + accepts valid UTF-8 scalars; accepted syntax here is largely Go-specific.

Excluded/incompatible: Raw backquoted strings, octal/hex/Unicode escape spellings, invalid-byte literals and Go constant concatenation are not inferred as Minyar support.

Inspected local references: unicode, text-abc. No value oracle to preserve; do not invent one or count this as a passing runtime regression.

**L1 — [test/string_lit.go:L75–75](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L75-L75) — empty interpreted/raw equality. Pending runtime projection.**

Upstream: Empty byte sequence. Equality assert succeeds; main exits0.

Minyar: An ordinary empty Text has length0 and byteLength0.

Excluded/incompatible: Raw backquote syntax excluded.

Inspected local references: empty-loop. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P6.

**L2 — [test/string_lit.go:L76–76](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L76-L76) — blank equality. Pending runtime projection.**

Upstream: One ASCII space (32). Equality assert succeeds; main exits0.

Minyar: Ordinary single-space Text content equality.

Excluded/incompatible: Go assertion/diagnostic infrastructure excluded.

Inspected local references: unicode-model. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P5.

**L3 — [test/string_lit.go:L77–77](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L77-L77) — hex a equality. Pending runtime projection.**

Upstream: Byte61 hex equals ASCII a (97). Equality assert succeeds; main exits0.

Minyar: Use literal a or Text(Character(97)); hex escape parser contract excluded.

Excluded/incompatible: No Go hex-escape syntax claim.

Inspected local references: unicode. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P5.

**L4 — [test/string_lit.go:L78–78](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L78-L78) — hex a versus raw a. Pending runtime projection.**

Upstream: Same byte61 hex. Equality assert succeeds; main exits0.

Minyar: Same runtime content projection with ordinary Text.

Excluded/incompatible: Raw and hex escape spellings excluded.

Inspected local references: unicode. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P5.

**L5 — [test/string_lit.go:L79–79](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L79-L79) — Unicode ä escape. Pending runtime projection.**

Upstream: U+00E4 encoded C3 A4. Equality assert succeeds; main exits0.

Minyar: Literal ä equals Text(Character(228)); scalar length1, bytes2.

Excluded/incompatible: No Go Unicode-escape parser claim.

Inspected local references: unicode, scalar-boundary. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P5.

**L6 — [test/string_lit.go:L80–80](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L80-L80) — Unicode ä versus raw ä. Pending runtime projection.**

Upstream: U+00E4 encoded C3 A4. Equality assert succeeds; main exits0.

Minyar: Same scalar projection using ordinary UTF-8 literal.

Excluded/incompatible: Raw backquote and Unicode-escape spellings excluded.

Inspected local references: unicode. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P5.

**L7 — [test/string_lit.go:L81–81](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L81-L81) — Unicode 本 escape. Pending runtime projection.**

Upstream: U+672C encoded E6 9C AC. Equality assert succeeds; main exits0.

Minyar: Literal 本 equals Text(Character(26412)); scalar length1, bytes3.

Excluded/incompatible: No Go escape parser claim.

Inspected local references: utf-loop. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P5.

**L8 — [test/string_lit.go:L82–82](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L82-L82) — Unicode 本 versus raw 本. Pending runtime projection.**

Upstream: Same U+672C bytes. Equality assert succeeds; main exits0.

Minyar: Same runtime scalar/content projection.

Excluded/incompatible: Raw backquote and Unicode-escape spellings excluded.

Inspected local references: utf-loop. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P5.

**L9 — [test/string_lit.go:L83–85](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L83-L85) — control escape equality. Pending runtime projection.**

Upstream: Bytes07,08,0C,0A,0D,09,0B,5C,22 on both sides. Equality assert succeeds; main exits0.

Minyar: Build Text from valid Character values7,8,12,10,13,9,11,92,34 and observe every scalar; no unsupported escape required.

Excluded/incompatible: Escape spellings/diagnostic byte indexing excluded.

Inspected local references: unicode-model. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P5.

**L10 — [test/string_lit.go:L86–88](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L86-L88) — raw escape-looking text. Pending runtime projection.**

Upstream: Literal backslash-letter text, not controls; both sides have identical bytes. Equality assert succeeds; main exits0.

Minyar: Build literal backslash Character92 plus ordinary letters/quotes, assert exact scalar sequence.

Excluded/incompatible: Raw string grammar excluded.

Inspected local references: unicode-model. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P5.

**L11 — [test/string_lit.go:L89–91](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L89-L91) — octal/hex arbitrary byte escape equality. Incompatible as written.**

Upstream: Bytes00,53,00,CA,FE,53 then two U+BABE scalars (몾); CA FE are invalid UTF-8. Equality assert succeeds; main exits0.

Minyar: Keep binary bytes in Bytes. Minyar Text must reject invalid UTF-8 rather than preserve this string.

Excluded/incompatible: Invalid UTF-8 Text, octal escapes and permissive byte-string contract incompatible.

Inspected local references: invalid-utf8, byte-model. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement.

**L12 — [test/string_lit.go:L92–94](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L92-L94) — raw octal/Unicode escape-looking text. Pending runtime projection.**

Upstream: Ordinary ASCII backslashes and digits compare equal; no escape decoding on raw side. Equality assert succeeds; main exits0.

Minyar: Reconstruct ordinary Text through existing backslash Character and ASCII pieces.

Excluded/incompatible: Raw backquote parser and Go octal/Unicode escape syntax excluded.

Inspected local references: unicode-model. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P5.

**L13 — [test/string_lit.go:L95–95](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L95-L95) — raw trailing backslash. Pending runtime projection.**

Upstream: ASCII sequence backslash x, backslash u, backslash U, backslash. Equality assert succeeds; main exits0.

Minyar: Construct via Character92 and letters; content equality/length7.

Excluded/incompatible: Raw literal ending in backslash excluded.

Inspected local references: unicode-model. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P5.

**L14 — [test/string_lit.go:L101–101](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L101-L101) — maximum variable rune. Pending runtime projection.**

Upstream: U+10FFFF encoded F4 8F BF BF. Equality assert succeeds; main exits0.

Minyar: Text(Character(1114111)) has length1/byteLength4 and indexing returns1114111.

Excluded/incompatible: Go rune int32/string conversion syntax excluded.

Inspected local references: scalar-boundary, unicode-model. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P5.

**L15 — [test/string_lit.go:L104–104](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L104-L104) — variable too-large rune. Incompatible as written.**

Upstream: U+110000 converts to replacement U+FFFD EF BF BD. Equality assert succeeds; main exits0.

Minyar: Character(1114112) must stop; no replacement value.

Excluded/incompatible: Scalar validation versus replacement is incompatible.

Inspected local references: scalar-boundary. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P5.

**L16 — [test/string_lit.go:L107–107](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L107-L107) — variable minimum surrogate. Incompatible as written.**

Upstream: U+D800 converts to U+FFFD. Equality assert succeeds; main exits0.

Minyar: Character(55296) must stop.

Excluded/incompatible: Surrogate replacement differs from scalar-only Character.

Inspected local references: invalid-utf8. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P5.

**L17 — [test/string_lit.go:L110–110](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L110-L110) — variable maximum surrogate. Incompatible as written.**

Upstream: U+DFFF converts to U+FFFD. Equality assert succeeds; main exits0.

Minyar: Character(57343) must stop.

Excluded/incompatible: Surrogate replacement differs from scalar-only Character.

Inspected local references: invalid-utf8. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P5.

**L18 — [test/string_lit.go:L113–113](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L113-L113) — negative variable rune. Incompatible as written.**

Upstream: -1 converts to U+FFFD. Equality assert succeeds; main exits0.

Minyar: Character(-1) must stop.

Excluded/incompatible: Negative replacement differs from scalar validation.

Inspected local references: scalar-boundary. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P5.

**L19 — [test/string_lit.go:L118–118](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L118-L118) — maximum constant rune. Pending runtime projection.**

Upstream: U+10FFFF encoded F4 8F BF BF via Go compile-time conversion. Equality assert succeeds; main exits0.

Minyar: Same runtime Text(Character(1114111)) projection as L14; no compile-time conversion coverage.

Excluded/incompatible: Go compile-time constant conversion excluded.

Inspected local references: scalar-boundary. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P5.

**L20 — [test/string_lit.go:L120–120](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L120-L120) — too-large constant rune. Incompatible as written.**

Upstream: U+110000 constant converts to U+FFFD. Equality assert succeeds; main exits0.

Minyar: Runtime Character(1114112) rejection control only.

Excluded/incompatible: Go compile-time acceptance/replacement unsupported.

Inspected local references: scalar-boundary. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P5.

**L21 — [test/string_lit.go:L122–122](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L122-L122) — minimum surrogate constant. Incompatible as written.**

Upstream: U+D800 constant converts to U+FFFD. Equality assert succeeds; main exits0.

Minyar: Character(55296) rejection only.

Excluded/incompatible: Go constant acceptance/replacement unsupported.

Inspected local references: invalid-utf8. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P5.

**L22 — [test/string_lit.go:L124–124](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L124-L124) — maximum surrogate constant. Incompatible as written.**

Upstream: U+DFFF constant converts to U+FFFD. Equality assert succeeds; main exits0.

Minyar: Character(57343) rejection only.

Excluded/incompatible: Go constant acceptance/replacement unsupported.

Inspected local references: invalid-utf8. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P5.

**L23 — [test/string_lit.go:L126–126](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L126-L126) — negative constant rune. Incompatible as written.**

Upstream: -1 constant converts to U+FFFD. Equality assert succeeds; main exits0.

Minyar: Character(-1) rejection only.

Excluded/incompatible: Go constant acceptance/replacement unsupported.

Inspected local references: scalar-boundary. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P5.

**L24 — [test/string_lit.go:L131–131](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L131-L131) — mixed valid/invalid rune slice. Incompatible as written.**

Upstream: One U+10FFFF followed by four U+FFFD;16 UTF-8 bytes total. Equality assert succeeds; main exits0.

Minyar: A List<Character> cannot contain invalid scalars; explicit Character construction stops at first invalid value.

Excluded/incompatible: No permissive rune-list to Text conversion; no full conversion API.

Inspected local references: scalar-boundary, invalid-utf8. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement.

**L25 — [test/string_lit.go:L133–133](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L133-L133) — global valid rune roundtrip. Pending runtime projection.**

Upstream: gr1 -> string equals aä本☺; scalars97,228,26412,9786;9 UTF-8 bytes. Equality assert succeeds; main exits0.

Minyar: Iterate valid Text, reconstruct with Text(Character); scalar length4/byteLength9.

Excluded/incompatible: Go globals and []rune conversion APIs excluded.

Inspected local references: utf-loop. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P3.

**L26 — [test/string_lit.go:L134–134](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L134-L134) — global invalid rune roundtrip. Incompatible as written.**

Upstream: gr2 replaces each FF with U+FFFD, equals aä��本☺;15 UTF-8 bytes. Equality assert succeeds; main exits0.

Minyar: Reject invalid input before a Text iteration can begin.

Excluded/incompatible: Go invalid-byte replacement decode incompatible.

Inspected local references: invalid-utf8. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement.

**L27 — [test/string_lit.go:L135–135](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L135-L135) — global valid byte roundtrip. Incompatible as written.**

Upstream: gb1 -> string equals original aä本☺ bytes. Equality assert succeeds; main exits0.

Minyar: Known byte sequence can be modeled in Bytes; valid Text content can be asserted separately.

Excluded/incompatible: No Text<->Bytes conversion API in inspected language contract; Byte indexing must not be replaced with Character indexing on Unicode.

Inspected local references: unicode, byte-model. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement.

**L28 — [test/string_lit.go:L136–136](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L136-L136) — global invalid byte roundtrip. Incompatible as written.**

Upstream: gb2 -> string preserves FF FF unchanged. Equality assert succeeds; main exits0.

Minyar: Bytes may preserve FF; Text rejects invalid UTF-8.

Excluded/incompatible: Permissive binary string and conversion API incompatible.

Inspected local references: invalid-utf8, byte-model. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement.

**L29 — [test/string_lit.go:L144–144](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L144-L144) — local valid rune roundtrip. Pending runtime projection.**

Upstream: r1 -> string equals aä本☺. Equality assert succeeds; main exits0.

Minyar: Scalar iteration/reconstruction projection; length4/bytes9.

Excluded/incompatible: Go rune-slice conversion and globals are not implemented.

Inspected local references: utf-loop. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement. Original proposal: P3.

**L30 — [test/string_lit.go:L145–145](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L145-L145) — local invalid rune roundtrip. Incompatible as written.**

Upstream: r2 conversion replaces each FF; aä��本☺. Equality assert succeeds; main exits0.

Minyar: Reject invalid Text.

Excluded/incompatible: Permissive replacement decode incompatible.

Inspected local references: invalid-utf8. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement.

**L31 — [test/string_lit.go:L146–146](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L146-L146) — local valid byte roundtrip. Incompatible as written.**

Upstream: b1 -> string preserves valid UTF-8 bytes. Equality assert succeeds; main exits0.

Minyar: Bytes and Text controls separately; no conversion port.

Excluded/incompatible: Missing Text<->Bytes conversion API; do not claim byte indexing through Text.

Inspected local references: unicode, byte-model. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement.

**L32 — [test/string_lit.go:L147–147](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/string_lit.go#L147-L147) — local invalid byte roundtrip. Incompatible as written.**

Upstream: b2 -> string preserves FF FF unchanged. Equality assert succeeds; main exits0.

Minyar: Binary preservation belongs in Bytes, invalid Text stops.

Excluded/incompatible: Permissive string conversion incompatible.

Inspected local references: invalid-utf8, byte-model. Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement.

**R1 — [test/range.go:L28–52](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L28-L52) — blank ASCII Text visits. Pending runtime projection.**

Upstream: Three loop forms each visit26. All failure checks stay false; main silent success.

Minyar: Use ordinary for character in alphabet and a counter; fresh unused name.

Excluded/incompatible: No blank identifiers, index/value tuple binding or assignment-form range.

Inspected local references: loops, empty-loop. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream. Original proposal: P4.

**R2 — [test/range.go:L53–60](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L53-L60) — ASCII byte-position sum. Pending runtime projection.**

Upstream: Index sum325 (0..25). All failure checks stay false; main silent success.

Minyar: Explicit range0..text.length or counter yields325 for ASCII.

Excluded/incompatible: Minyar Text loop yields Characters, not byte offsets; equivalence only for ASCII.

Inspected local references: loops. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream. Original proposal: P3.

**R3 — [test/range.go:L61–69](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L61-L69) — ASCII rune sum. Pending runtime projection.**

Upstream: Rune sum2847. All failure checks stay false; main silent success.

Minyar: Sum Integer(character) in ordinary Text loop.

Excluded/incompatible: Go rune arithmetic/type width excluded.

Inspected local references: utf-loop. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream. Original proposal: P4.

**R4 — [test/range.go:L71–88](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L71-L88) — channels. Incompatible as written.**

Upstream: Channel sequence reconstructs alphabet; separate channel count26. All failure checks stay false; main silent success.

Minyar: No channel or goroutine API. A List sum would not cover this test.

Excluded/incompatible: Channel close/receive and concurrent generator incompatible.

Inspected local references: loops. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream.

**R5 — [test/range.go:L100–113](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L100-L113) — slice expression evaluated once. Pending runtime projection.**

Upstream: nmake1, value sum15. All failure checks stay false; main silent success.

Minyar: Helper with shared Integer state returns List<Integer>[1,2,3,4,5]; for visits its values once.

Excluded/incompatible: Go global state, index/value tuple syntax and fixed slice header length excluded.

Inspected local references: loops. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream. Original proposal: P4.

**R6 — [test/range.go:L115–125](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L115-L125) — slice range parallel target assignment. Incompatible as written.**

Upstream: i0,x[0]10,x[1]99. All failure checks stay false; main silent success.

Minyar: Minyar has fresh loop binding and single-target assignment; explicit sequential code changes the contract.

Excluded/incompatible: Parallel target capture including x[old i] incompatible.

Inspected local references: receiver-order. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream.

**R7 — [test/range.go:L127–141](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L127-L141) — slice index expression once. Pending runtime projection.**

Upstream: nmake1,index sum10. All failure checks stay false; main silent success.

Minyar: Evaluate helper once into local List, explicit ordinal range/counter over values.

Excluded/incompatible: No index-yielding List loop; a range over stored length is a weaker runtime projection, not intrinsic range coverage.

Inspected local references: loops. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream. Original proposal: P4.

**R8 — [test/range.go:L143–157](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L143-L157) — slice no bindings expression once. Pending runtime projection.**

Upstream: nmake1,count5. All failure checks stay false; main silent success.

Minyar: Ordinary unused element binding and helper side-effect counter.

Excluded/incompatible: Go no-binding range syntax excluded; no growth case upstream.

Inspected local references: loops. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream. Original proposal: P4.

**R9 — [test/range.go:L167–181](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L167-L181) — byte conversion expression once. Pending runtime projection.**

Upstream: makenumstring called1; byte sum15 for01..05. All failure checks stay false; main silent success.

Minyar: Helper returns initialized Bytes01..05 and increments shared state once, then Bytes loop Integer sum15.

Excluded/incompatible: []byte(Text) conversion and byte overflow width excluded; this changes helper representation and is explicitly a projection.

Inspected local references: byte-slice, byte-model. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream. Original proposal: P4.

**R10 — [test/range.go:L191–205](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L191-L205) — array values once. Pending runtime projection.**

Upstream: nmake1,sum15. All failure checks stay false; main silent success.

Minyar: Fresh List helper once with same values.

Excluded/incompatible: Array value copying/fixed size excluded; List shared semantics not an array implementation.

Inspected local references: loops. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream. Original proposal: P4.

**R11 — [test/range.go:L207–221](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L207-L221) — array indices once. Pending runtime projection.**

Upstream: nmake1,sum10. All failure checks stay false; main silent success.

Minyar: Fresh List helper evaluated once plus ordinary ordinal range.

Excluded/incompatible: Go index range, array value and length evaluation rules excluded.

Inspected local references: loops. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream. Original proposal: P4.

**R12 — [test/range.go:L223–237](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L223-L237) — array no bindings once. Pending runtime projection.**

Upstream: nmake1,count5. All failure checks stay false; main silent success.

Minyar: Fresh List helper and unused element binding.

Excluded/incompatible: Go fixed-array/no-binding semantics excluded.

Inspected local references: loops. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream. Original proposal: P4.

**R13 — [test/range.go:L244–270](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L244-L270) — array pointer len/cap and values. Incompatible as written.**

Upstream: Each len/cap call invokes helper once and yields5; range invokes once and sums15. All failure checks stay false; main silent success.

Minyar: No pointer-to-array or capacity property.

Excluded/incompatible: Pointer len/cap evaluation and range contract incompatible; List helper similarity does not cover it.

Inspected local references: loops. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream.

**R14 — [test/range.go:L272–287](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L272-L287) — array pointer indices. Incompatible as written.**

Upstream: nmake1,index sum10. All failure checks stay false; main silent success.

Minyar: No pointer-to-array range.

Excluded/incompatible: Pointer representation/evaluation incompatible; no duplicate List projection credit.

Inspected local references: loops. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream.

**R15 — [test/range.go:L288–302](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L288-L302) — array pointer no bindings. Incompatible as written.**

Upstream: nmake1,count5. All failure checks stay false; main silent success.

Minyar: No pointer-to-array range.

Excluded/incompatible: Pointer/no-binding contract incompatible.

Inspected local references: loops. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream.

**R16 — [test/range.go:L312–325](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L312-L325) — Unicode Text values expression once. Pending runtime projection.**

Upstream: nmake1, scalar sum10180 for abcd☺ (97+98+99+100+9786). All failure checks stay false; main silent success.

Minyar: Effectful Text helper once; Integer(Character) sum10180/count5 and byteLength7.

Excluded/incompatible: No global mutable state; no rune32 width arithmetic. Minyar valid UTF-8 domain preserved.

Inspected local references: utf-loop. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream. Original proposal: P4.

**R17 — [test/range.go:L327–336](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L327-L336) — Text range parallel indexed target. Incompatible as written.**

Upstream: i0,x[0]a,x[1]c. All failure checks stay false; main silent success.

Minyar: No parallel range assignment.

Excluded/incompatible: Old-index lvalue capture and outer assignment incompatible.

Inspected local references: receiver-order. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream.

**R18 — [test/range.go:L337–346](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L337-L346) — Text range parallel target depending on rune. Incompatible as written.**

Upstream: r2,y[0]1,y[1]0,y[2]3. All failure checks stay false; main silent success.

Minyar: No parallel range assignment.

Excluded/incompatible: Value/index assignment order and old-rune target capture incompatible.

Inspected local references: receiver-order. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream.

**R19 — [test/range.go:L348–362](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L348-L362) — Unicode Text byte-position sum. Pending runtime projection.**

Upstream: nmake1, byte offsets0,1,2,3,4 sum10. All failure checks stay false; main silent success.

Minyar: An explicit scalar ordinal counter also sums10 ONLY for this literal, whose sole multibyte scalar is last.

Excluded/incompatible: Minyar for Text produces Character, not byte positions. Original interior-multibyte discriminator required; same sum is not general byte-index coverage.

Inspected local references: unicode, utf-loop. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream. Original proposal: P3.

**R20 — [test/range.go:L364–378](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L364-L378) — Unicode Text no bindings count. Pending runtime projection.**

Upstream: nmake1,count5, despite UTF-8 byteLength7. All failure checks stay false; main silent success.

Minyar: Ordinary Text loop helper once yields five Characters.

Excluded/incompatible: Go no-binding syntax excluded.

Inspected local references: utf-loop. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream. Original proposal: P4.

**R21 — [test/range.go:L388–402](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L388-L402) — map values expression once. Incompatible as written.**

Upstream: nmake1,sum10180. All failure checks stay false; main silent success.

Minyar: No Map type in inspected Minyar language.

Excluded/incompatible: Map range/construction and unspecified iteration order incompatible; equivalent List sum not coverage.

Inspected local references: loops. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream.

**R22 — [test/range.go:L404–418](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L404-L418) — map indices expression once. Incompatible as written.**

Upstream: nmake1,key sum10. All failure checks stay false; main silent success.

Minyar: No Map/key iteration.

Excluded/incompatible: Map key contract incompatible.

Inspected local references: loops. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream.

**R23 — [test/range.go:L420–434](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L420-L434) — map no bindings once. Incompatible as written.**

Upstream: nmake1,count5. All failure checks stay false; main silent success.

Minyar: No Map range.

Excluded/incompatible: Map/no-binding contract incompatible.

Inspected local references: loops. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream.

**R24 — [test/range.go:L446–461](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L446-L461) — effectful pointer range lvalues. Incompatible as written.**

Upstream: getvar calls4; index sum1,value sum3. All failure checks stay false; main silent success.

Minyar: Ordinary helper effects have related tests, but no pointer lvalues or parallel range targets.

Excluded/incompatible: Pointer dereference, range-assignment evaluation contract incompatible.

Inspected local references: receiver-order. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream.

**R25 — [test/range.go:L463–472](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/range.go#L463-L472) — empty array skips lvalue evaluation. Incompatible as written.**

Upstream: No iteration and ncalls0. All failure checks stay false; main silent success.

Minyar: An empty Text/List/Bytes skips body effects as an original control, not pointer-target evaluation.

Excluded/incompatible: No effectful pointer range targets, no zero-sized Go array typing.

Inspected local references: empty-loop, empty-list. Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream.

**S1 — [test/strcopy.go:L17–29](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/strcopy.go#L17-L29) — substring conversion address inequality. Incompatible as written.**

Upstream: 2048 zero bytes -> string -> sub[10:12] -> string([]byte(sub)); subh.Data != subcopyh.Data or panic. No distinct content oracle is asserted.

Minyar: Public immutable Text sharing is legal. Bytes.slice copies, but proving its mutation independence is a different original contract.

Excluded/incompatible: reflect.StringHeader, unsafe.Pointer and forced string-byte-string allocation/address identity are incompatible. The2048-byte source is below Minyar documented >4KiB tiny-slice copy guard; do not claim it must copy.

Inspected local references: view-lifetime, byte-slice. Only copied Bytes mutation independence and retained Text value/lifetime can be proposed. Never assert distinct public Text addresses. Original proposal: P1.

**Z0 — [test/behavior/slice.zig:L11–29](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L11-L29) — module comptime type search. Incompatible as written.**

Upstream: indexOfScalar(type,[c_uint,c_ulong,c_ulonglong],c_ulong) unwraps optional index1; otherwise compileError. Legal module-level comptime execution.

Minyar: An ordinary Integer List search is not type/generic/comptime coverage.

Excluded/incompatible: First-class type values, optional result, generic slice parameters, comptime execution and compileError incompatible.

Inspected local references: No relevant fixture reference for this unsupported contract. No runtime port proposed; preserve unsupported type contract.

**Z1 — [test/behavior/slice.zig:L31–49](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L31-L49) — slicing. Pending runtime projection.**

Upstream: Lengths5/10 and first selected i32 value1234. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Initialize a List<Integer> of20 values; explicitly collect positions5..10 and10..20 into fresh Lists, or use bounded byte values in Bytes. No public List.slice.

Excluded/incompatible: Undefined array storage, pointer dereference, writable view and pointer-to-array type excluded.

Inspected local references: loops, no-list-slice. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

Backend guard source: L32: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L33: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z2 — [test/behavior/slice.zig:L51–59](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L51-L59) — const slice. Pending runtime projection.**

Upstream: Comptime ASCII source length10, slice length1, element2. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Runtime Text1234567890.slice(1,2) has length1 and Character2.

Excluded/incompatible: No compile-time slice execution/type coverage.

Inspected local references: text-abc. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

**Z3 — [test/behavior/slice.zig:L61–66](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L61-L66) — comptime slice of undefined pointer of length 0. Incompatible as written.**

Upstream: Undefined many-pointer slices[0..0] and[100..100] each length0. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Initialized empty Bytes/Text boundaries only; cannot slice beyond an empty object.

Excluded/incompatible: Undefined/unbounded pointer has no Minyar counterpart; slice(100,100) on empty Bytes/Text must fail.

Inspected local references: byte-empty, empty-loop. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

**Z4 — [test/behavior/slice.zig:L68–73](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L68-L73) — implicitly cast array of size 0 to slice. Pending runtime projection.**

Upstream: Zero-element u8 array coerced to slice; helper length0. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Bytes() or contextually typed empty Integer List length0.

Excluded/incompatible: Implicit array-to-slice pointer coercion excluded.

Inspected local references: byte-empty, empty-list. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

Backend guard source: L69: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO` No backend was run.

**Z5 — [test/behavior/slice.zig:L79–93](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L79-L93) — access len index of sentinel-terminated slice. Incompatible as written.**

Upstream: hello sentinel slice length5, slice[5]0; runtime and comptime helper calls. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Text hello length5; index5 must stop, not yield zero.

Excluded/incompatible: Sentinel access at length and comptime execution incompatible.

Inspected local references: unicode. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

Backend guard source: L80: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L81: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z6 — [test/behavior/slice.zig:L95–101](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L95-L101) — comptime slice of slice preserves comptime var. Incompatible as written.**

Upstream: Nested open slices of comptime buffer share mutation; nested indexed value1. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Plain Bytes alias observes writes; each Bytes.slice makes an independent copy instead.

Excluded/incompatible: Writable nested view and comptime variable identity incompatible.

Inspected local references: byte-slice, list-text. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P1.

**Z7 — [test/behavior/slice.zig:L103–119](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L103-L119) — open slice of open slice with sentinel. Incompatible as written.**

Upstream: Nested sentinel slices preserve [:0]const u8; lengths5/4, first h/e, sentinel0 at5/4. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Ordinary Text nested slices can assert content/length; endpoint reads must stop.

Excluded/incompatible: Sentinel propagation, pointer typing and endpoint zero access incompatible.

Inspected local references: view-lifetime. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

Backend guard source: L104: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L105: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z8 — [test/behavior/slice.zig:L121–137](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L121-L137) — open slice with sentinel of slice with end index. Incompatible as written.**

Upstream: End-index slices types *const[5]u8 and *const[5:0]u8; both length5, h/o values, sentinel0 for sentinel variant. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Runtime hello slice contents only; no sentinel/type claim.

Excluded/incompatible: Type-level sentinel and endpoint access incompatible.

Inspected local references: text-abc. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

Backend guard source: L122: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L123: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z9 — [test/behavior/slice.zig:L139–159](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L139-L159) — slice of type. Incompatible as written.**

Upstream: Both array and slice loops yield type values i32,f64,type in that order. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Minyar has no first-class type values or compile-time generic loop.

Excluded/incompatible: List<type>, reflection, comptime and inline type iteration incompatible.

Inspected local references: loops. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity.

**Z10 — [test/behavior/slice.zig:L161–166](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L161-L166) — generic malloc free. Incompatible as written.**

Upstream: Generic memAlloc(u8,10) returns view into static100-byte buffer; memFree deliberately no-op; test has no value assertion. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Automatic Bytes ownership is not this allocator/free API.

Excluded/incompatible: Generic pointer cast, static storage and manual free protocol incompatible; no allocator leak/success claims.

Inspected local references: byte-empty. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity.

Backend guard source: L162: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO` No backend was run.

**Z11 — [test/behavior/slice.zig:L175–189](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L175-L189) — slice of hardcoded address to pointer. Incompatible as written.**

Upstream: Hardcoded pointer4 slice length2; type*[2]u8 and slice.ptr address4. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: No public hardcoded-address/pointer conversion.

Excluded/incompatible: Address identity and pointer typing incompatible.

Inspected local references: No relevant fixture reference for this unsupported contract. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity.

Backend guard source: L176: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z12 — [test/behavior/slice.zig:L191–198](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L191-L198) — comptime slice of pointer preserves comptime var. Incompatible as written.**

Upstream: Comptime pointer view assignment changes nested original buffer read to1. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Plain Bytes aliases observe1 but copied slice does not mutate source.

Excluded/incompatible: Pointer cast/comptime mutable view incompatible.

Inspected local references: byte-slice. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P1.

**Z13 — [test/behavior/slice.zig:L200–211](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L200-L211) — comptime pointer cast array and then slice. Pending runtime projection.**

Upstream: Both pointer-cast variants slice[1]2 from array1..8. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Runtime Bytes slice(0,2) returns second byte2 with original input initialized.

Excluded/incompatible: Pointer casts, const-pointer typing and comptime pointer provenance excluded.

Inspected local references: byte-slice. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

**Z14 — [test/behavior/slice.zig:L213–223](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L213-L223) — slicing zero length array. Pending runtime projection.**

Upstream: Empty string and empty u32 array slices have length0 and content equality to empty. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Text empty.slice(0,0) and Bytes().slice(0,0) length0; typed empty List cannot call slice.

Excluded/incompatible: Array-to-slice/storage/type conversion excluded; Text counts scalars generally.

Inspected local references: byte-empty, empty-list. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

Backend guard source: L214: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L215: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z15 — [test/behavior/slice.zig:L225–236](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L225-L236) — slicing pointer by length. Pending runtime projection.**

Upstream: Pointer shift by1 then first5 values gives length5 and elements2,3,4,5,6. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Bytes1..8.slice(1,6), check every selected byte.

Excluded/incompatible: Unbounded pointer arithmetic and missing-end syntax excluded.

Inspected local references: byte-model. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

Backend guard source: L226: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z16 — [test/behavior/slice.zig:L240–248](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L240-L248) — compile time slice of pointer to hard coded address. Incompatible as written.**

Upstream: Hardcoded x address0x1000,len0x500; y shifted0x100 i32 items address0x1400,len0x400. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: No pointer address or element-size layout property.

Excluded/incompatible: Raw address arithmetic and compile-time pointer construction incompatible.

Inspected local references: No relevant fixture reference for this unsupported contract. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity.

Backend guard source: L241: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z17 — [test/behavior/slice.zig:L250–263](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L250-L263) — slice string literal has correct type. Incompatible as written.**

Upstream: Literal full slice *const[4:0]u8; array full slice *const[4]i32; runtime-zero slices [:0]const u8 and []const i32. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Ordinary Text/Bytes content does not cover these exact static types.

Excluded/incompatible: Sentinel and runtime/comptime-dependent pointer types incompatible.

Inspected local references: text-abc. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity.

Backend guard source: L251: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z18 — [test/behavior/slice.zig:L265–274](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L265-L274) — result location zero sized array inside struct field implicit cast to slice. Pending runtime projection.**

Upstream: Struct entries []u32 field initialized through empty array coercion length0. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Record with explicitly typed empty List<Integer> field length0.

Excluded/incompatible: Zero-sized array/slice implicit result-location coercion excluded.

Inspected local references: empty-list. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

Backend guard source: L266: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO` No backend was run.

**Z19 — [test/behavior/slice.zig:L276–283](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L276-L283) — runtime safety lets us slice from len..len. Pending runtime projection.**

Upstream: Helper runtime slice[3..3] of three bytes equals empty. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Bytes1,2,3.slice(3,3) length0; empty at end is legal.

Excluded/incompatible: Writable view, usize width and Zig safety-mode behavior excluded.

Inspected local references: byte-model, byte-empty. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

Backend guard source: L277: `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest;`; L278: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L279: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z20 — [test/behavior/slice.zig:L289–298](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L289-L298) — C pointer. Incompatible as written.**

Upstream: C-pointer[0..10] equals kjdhfkjdhf. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Known Text literal slice(0,10) projects ASCII contents.

Excluded/incompatible: Core test exercises C pointer range/conversion; remains incompatible, no pointer coverage.

Inspected local references: text-abc. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

Backend guard source: L290: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L291: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z21 — [test/behavior/slice.zig:L300–316](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L300-L316) — C pointer slice access. Incompatible as written.**

Upstream: C pointer runtime-zero slice type[]const u32 versus compile-time zero *const[1]u32; five pointed values42. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Initialize Integer List with42 values only as optional content control.

Excluded/incompatible: C pointer element addresses, type resolution, dereference iteration incompatible.

Inspected local references: loops. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity.

Backend guard source: L301: `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest;`; L302: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L303: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z22 — [test/behavior/slice.zig:L318–321](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L318-L321) — comptime slices are disambiguated. Pending runtime projection.**

Upstream: Comptime helper sliceSum([1,2])3 and sliceSum([3,4])7. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Two ordinary Integer List sums3 and7 can be compared separately.

Excluded/incompatible: No comptime specialization identity, inline loop or generic helper coverage.

Inspected local references: loops. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P4.

**Z23 — [test/behavior/slice.zig:L331–343](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L331-L343) — slice type with custom alignment. Incompatible as written.**

Upstream: Aligned32 record slice write of field anything42 is observed in array[1]. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Shared List<Record> plain alias can observe scalar field42.

Excluded/incompatible: Alignment32 and array view aliasing not covered by List alias; no implicit copied-record semantics.

Inspected local references: list-text. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity.

Backend guard source: L332: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L333: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z24 — [test/behavior/slice.zig:L345–370](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L345-L370) — obtaining a null terminated slice. Incompatible as written.**

Upstream: buf abc followed by zero; sentinel slices resolve [:0]u8 then *[2]u8 or []u8 depending on bound. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Ordinary Bytes abc0 can preserve zero, but no sentinel type.

Excluded/incompatible: Null-termination validation, pointer-to-array and runtime-bound type distinctions incompatible.

Inspected local references: byte-model. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity.

Backend guard source: L346: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L347: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z25 — [test/behavior/slice.zig:L372–387](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L372-L387) — empty array to slice. Incompatible as written.**

Upstream: Empty slice permits align1,align4,align16 coercions and asserts each reflected alignment. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: No public alignment or pointer attributes.

Excluded/incompatible: Alignment coercion/type reflection incompatible; empty length alone would not cover assertions.

Inspected local references: empty-list. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity.

**Z26 — [test/behavior/slice.zig:L389–404](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L389-L404) — @ptrCast slice to pointer. Incompatible as written.**

Upstream: Five FF bytes cast from aligned slice to *u16 dereference65535; runtime/comptime. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Bytes FF FF getUInt16(0)=65535 is an optional explicit little-endian scalar control.

Excluded/incompatible: Core alignment/pointer cast/native layout and comptime dereference incompatible.

Inspected local references: byte-slice. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity.

Backend guard source: L390: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L391: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z27 — [test/behavior/slice.zig:L406–441](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L406-L441) — slice multi-pointer without end. Incompatible as written.**

Upstream: Many-pointer open slices keep [*]u8 or [*:0]u8 types and first values2,3, runtime/comptime. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Ordinary initialized Bytes.slice(1,5) could read2,3; bounded owned copy differs.

Excluded/incompatible: Unbounded pointer/no-end/sentinel propagation/type assertions incompatible.

Inspected local references: byte-slice. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

Backend guard source: L407: `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest;`; L408: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z28 — [test/behavior/slice.zig:L443–657](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L443-L657) — slice syntax resulting in pointer-to-array. Incompatible as written.**

Upstream: Twenty helper subcases assert pointer-to-array types, sentinels, alignments, optional coercion, runtime/comptime distinctions; content subcases read2,3,5,0,1 and concatenateab. All exact sites/helper spans retained in JSON. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Only initialized bounded Bytes slices and ordinary Text+ can project selected values. Main test remains incompatible; no20-helper port credit.

Excluded/incompatible: Pointer-to-array typing, sentinel propagation/access, u0, explicit alignment, optional slice coercion and comptime/runtime type differences incompatible.

Inspected local references: byte-slice, text-abc, view-lifetime. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

Backend guard source: L444: `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L445: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L446: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z29 — [test/behavior/slice.zig:L659–676](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L659-L676) — slice pointer-to-array null terminated. Incompatible as written.**

Upstream: Comptime sentinel source slices type*[2]u8,*[2:4]u8,*[4:0]u8; runtime open tail[:0]u8. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: No public sentinel-dependent type.

Excluded/incompatible: Pointer-array/sentinel and phase-dependent typing incompatible.

Inspected local references: No relevant fixture reference for this unsupported contract. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity.

Backend guard source: L660: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L661: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z30 — [test/behavior/slice.zig:L678–709](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L678-L709) — slice pointer-to-array zero length. Incompatible as written.**

Upstream: Zero ordinary/sentinel slice variants resolve different *[0] or *[0:0] types across phases; no content assertion. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: No pointer-array type reflection; empty length not the tested oracle.

Excluded/incompatible: Zero-size/sentinel phase-dependent typing incompatible.

Inspected local references: empty-list. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity.

Backend guard source: L679: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L680: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z31 — [test/behavior/slice.zig:L711–746](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L711-L746) — type coercion of pointer to anon struct literal to pointer to slice. Pending runtime projection.**

Upstream: Two coerced slice literals: length3 values42,56,54; length3 strings hello, comma-space,world!; runtime/comptime. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Explicit homogeneous List<Integer> and List<Text>, check lengths/every element.

Excluded/incompatible: Anonymous tuple pointer-to-slice coercion, unused union definition and comptime execution excluded; no tuple/generic support inferred.

Inspected local references: list-text. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P7.

Backend guard source: L712: `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L713: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L714: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z32 — [test/behavior/slice.zig:L748–757](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L748-L757) — array concat of slices gives ptr to array. Pending runtime projection.**

Upstream: Comptime array concat aoeu+asdf yields aoeuasdf and *const[8]u8. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Ordinary Text+ preserves aoeuasdf.

Excluded/incompatible: Compile-time concat/slice constant folding and pointer type excluded.

Inspected local references: text-abc. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P7.

**Z33 — [test/behavior/slice.zig:L759–767](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L759-L767) — array mult of slice gives ptr to array. Pending runtime projection.**

Upstream: Comptime slice multiplication aoeu**2 yields aoeuaoeu and *const[8]u8. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Ordinary Text aoeu+aoeu preserves content without a repeat operator.

Excluded/incompatible: Slice multiplication syntax, compile-time evaluation and pointer type excluded.

Inspected local references: text-self. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P7.

**Z34 — [test/behavior/slice.zig:L769–784](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L769-L784) — slice bounds in comptime concatenation. Pending runtime projection.**

Upstream: Comptime bs of dotted literal[8..9] is1; both empty++bs and bs++empty have length1 and contents1. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Runtime Text.slice(8,9), then both orders of +empty.

Excluded/incompatible: Compile-time block/concat/type behavior excluded.

Inspected local references: text-self, text-abc. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P7.

Backend guard source: L770: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L771: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z35 — [test/behavior/slice.zig:L786–802](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L786-L802) — slice sentinel access at comptime. Incompatible as written.**

Upstream: Both explicit sentinel array and123 literal slices length3,slice[length]0. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Text123 index3 must stop.

Excluded/incompatible: Sentinel length-index access incompatible.

Inspected local references: unicode. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

**Z36 — [test/behavior/slice.zig:L804–820](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L804-L820) — slicing array with sentinel as end index. Incompatible as written.**

Upstream: Sentinel array1..4 slice[4..5] includes zero with length1,*[1]u8. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Bytes four elements slice(4,5) must stop; explicit appended zero is an ordinary fifth element.

Excluded/incompatible: Implicit sentinel participates beyond public length; incompatible.

Inspected local references: byte-model. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

Backend guard source: L805: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L806: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z37 — [test/behavior/slice.zig:L822–839](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L822-L839) — slicing slice with sentinel as end index. Incompatible as written.**

Upstream: Sentinel slice1..4[4..5] includes zero length1,*[1]u8. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Bytes slice(4,5) on length4 must stop.

Excluded/incompatible: Sentinel end-index access incompatible.

Inspected local references: byte-model. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

Backend guard source: L823: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L824: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z38 — [test/behavior/slice.zig:L841–850](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L841-L850) — slice len modification at comptime. Incompatible as written.**

Upstream: Comptime writable slice descriptor length0 +=2 exposes original0,1 and length2. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Bytes.resize(2) zero-initializes exposed bytes instead of reviving old contents; separate alias shares container length.

Excluded/incompatible: Direct slice.len descriptor mutation/comptime view metadata incompatible.

Inspected local references: byte-empty. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity.

**Z39 — [test/behavior/slice.zig:L852–862](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L852-L862) — slice field ptr const. Incompatible as written.**

Upstream: All four equality assertions compare exact const pointer/slice-field-pointer types. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: No address-of or pointer attributes.

Excluded/incompatible: Const pointer type reflection incompatible.

Inspected local references: No relevant fixture reference for this unsupported contract. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity.

**Z40 — [test/behavior/slice.zig:L864–876](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L864-L876) — slice field ptr var. Incompatible as written.**

Upstream: All four equality assertions compare mutable pointer-to-slice and pointer-to-ptr-field types. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: No address-of/mutable pointer metadata.

Excluded/incompatible: Pointer/field mutability type reflection incompatible.

Inspected local references: No relevant fixture reference for this unsupported contract. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity.

Backend guard source: L865: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO` No backend was run.

**Z41 — [test/behavior/slice.zig:L878–891](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L878-L891) — global slice field access. Incompatible as written.**

Upstream: Global slice ptr+=1,len-=2 transforms string totrin. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Text string.slice(1,5) yields trin as an optional content control.

Excluded/incompatible: Direct global writable descriptor/pointer arithmetic incompatible; resulting contents alone do not cover it.

Inspected local references: text-abc. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

Backend guard source: L879: `if (builtin.zig_backend == .stage2_aarch64) return error.SkipZigTest;`; L880: `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L881: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest; // TODO`; L882: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z42 — [test/behavior/slice.zig:L893–901](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L893-L901) — slice of void. Incompatible as written.**

Upstream: Slice of12 void items with runtime bound10 has length10. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Nothing cannot be stored in List; no zero-bit element type.

Excluded/incompatible: Slice<void>, zero-sized value storage and undefined array incompatible.

Inspected local references: no-list-slice. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity.

Backend guard source: L894: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z43 — [test/behavior/slice.zig:L903–917](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L903-L917) — slice with dereferenced value. Pending runtime projection.**

Upstream: Two block expressions use dereferenced runtime index0 on empty array; retained result length0. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Bytes().slice(ordinary Integer0,0) length0.

Excluded/incompatible: Pointer dereference and block-value break syntax excluded.

Inspected local references: byte-empty. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

Backend guard source: L904: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z44 — [test/behavior/slice.zig:L919–934](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L919-L934) — empty slice ptr is non null. Incompatible as written.**

Upstream: Two empty-slice pointer casts retain the same integer address after adding zero. Name says non-null; actual assertions only compare addresses. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: No public pointer identity/null contract; length0 is not this oracle.

Excluded/incompatible: Pointer identity, cast and undefined storage assumptions incompatible; do not invent a non-null assertion.

Inspected local references: empty-list. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity.

Backend guard source: L920: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest; // Test assumes `undefined` is non-zero` No backend was run.

**Z45 — [test/behavior/slice.zig:L936–943](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L936-L943) — slice decays to many pointer. Incompatible as written.**

Upstream: Sentinel many-pointer from abcdefg-zero scans via mem.span; equals seven-byte ordinary slice. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Text containing explicit zero preserves it as a scalar; public Text never implicitly scans to zero.

Excluded/incompatible: Sentinel decay, scanning pointer and pointer-length discovery incompatible.

Inspected local references: unicode-model. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity.

Backend guard source: L937: `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest;`; L938: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z46 — [test/behavior/slice.zig:L945–962](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L945-L962) — write through pointer to optional slice arg. Incompatible as written.**

Upstream: Pointer to optional slice updated via bar/baz from null to text ok; string equalityok. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: A return Text helper can yieldok; this alone does not cover pointer/optional mutation.

Excluded/incompatible: Optional types, pointer writes, error-union propagation incompatible.

Inspected local references: text-abc. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity.

Backend guard source: L946: `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest;`; L947: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest;`; L948: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z47 — [test/behavior/slice.zig:L964–978](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L964-L978) — modify slice length at comptime. Incompatible as written.**

Upstream: Comptime slice descriptor snapshots: a values[10],b[10,20] after separate len increments. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Explicit Bytes.slice copies of sizes1,2 or separate initialized Lists can retain those values.

Excluded/incompatible: Direct length modification, copied descriptor state and comptime semantics incompatible; mutable Minyar container alias has shared length.

Inspected local references: byte-slice. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P1.

Backend guard source: L965: `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest;`; L966: `if (builtin.zig_backend == .stage2_sparc64) return error.SkipZigTest;`; L967: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z48 — [test/behavior/slice.zig:L980–993](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L980-L993) — slicing zero length array field of struct. Pending runtime projection.**

Upstream: Zero-size struct array field helper foo(0,0).len0. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Explicit record with Bytes() field; field.slice(0,0).length0.

Excluded/incompatible: Undefined struct, [0]usize fixed storage and self pointer excluded.

Inspected local references: empty-list, byte-empty. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

Backend guard source: L981: `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L982: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;`; L983: `if (builtin.zig_backend == .stage2_riscv64) return error.SkipZigTest;` No backend was run.

**Z49 — [test/behavior/slice.zig:L995–1006](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L995-L1006) — slicing slices gives correct result. Pending runtime projection.**

Upstream: Nested1234 slices equal1234,2,3,4,34. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Exactly the same ordinary Text slices with explicit bounds; held view remains valid after reassigning source.

Excluded/incompatible: Zig byte offsets coincide with scalar ordinals for ASCII only; no mutable view/type coverage.

Inspected local references: text-abc, view-lifetime. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

Backend guard source: L996: `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L997: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z50 — [test/behavior/slice.zig:L1008–1018](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L1008-L1018) — get address of element of zero-sized slice. Incompatible as written.**

Upstream: Undefined []void slice index0 address passed to no-op destroy; no value assertion. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: No Nothing List or address-of operation.

Excluded/incompatible: Zero-bit element pointer and undefined storage contract incompatible; no empty-bound safety coverage.

Inspected local references: No relevant fixture reference for this unsupported contract. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity.

Backend guard source: L1009: `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L1010: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z51 — [test/behavior/slice.zig:L1020–1038](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L1020-L1038) — sentinel-terminated 0-length slices. Incompatible as written.**

Upstream: Four sentinel zero-length slice/array variants index0 value2 despite length0. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Empty Bytes/Text/List index0 must stop.

Excluded/incompatible: Sentinel storage readable at zero-length endpoint incompatible.

Inspected local references: byte-empty, empty-list. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

Backend guard source: L1021: `if (builtin.zig_backend == .stage2_arm) return error.SkipZigTest; // TODO`; L1022: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z52 — [test/behavior/slice.zig:L1040–1048](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L1040-L1048) — peer slices keep abi alignment with empty struct. Pending runtime projection.**

Upstream: Runtime false peer choice between &[42]u32 and empty struct coerces to[]const u32,length0. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Ordinary if assigning an explicitly typed empty Integer List length0.

Excluded/incompatible: ABI alignment, peer-type inference, empty struct coercion excluded.

Inspected local references: empty-list. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P6.

Backend guard source: L1041: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

**Z53 — [test/behavior/slice.zig:L1050–1061](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L1050-L1061) — sentinel expression in slice operation has result type. Incompatible as written.**

Upstream: Sentinel u16 max65535 inferred via @intCast; *const[2:sentinel]u16, endpoint65535,len2,values1,2. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Explicit Bytes UInt16 or Integer List can store65535, but no hidden endpoint.

Excluded/incompatible: Sentinel result-type inference and endpoint access incompatible.

Inspected local references: byte-slice. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity.

**Z54 — [test/behavior/slice.zig:L1063–1075](https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/test/behavior/slice.zig#L1063-L1075) — conditionally return second argument slice. Pending runtime projection.**

Upstream: foo(false,false-text) returns empty; foo(true,true-text) returns true-text. Every source expectation holds when backend guards permit; phase assertions retained separately.

Minyar: Function(Boolean,Text):Text returning empty or borrowed argument keeps exact content; retain returned Text across caller reassignment.

Excluded/incompatible: Zig slice ABI, empty-array coercion excluded; Minyar automatic lifetime adds original control.

Inspected local references: text-abc, view-lifetime. Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity. Original proposal: P7.

Backend guard source: L1064: `if (builtin.zig_backend == .stage2_spirv) return error.SkipZigTest;` No backend was run.

## Original regression proposals — all pending

**P1 — Copied Bytes versus shared alias and immutable Text retention.**

Initialize Bytes11,22,33,44,55; keep plain alias and snapshot=slice(1,4). Mutate source[1]=99: alias sees99, snapshot[0]22. Mutate snapshot[1]=77: source[2]33. Clear source via alias; snapshot remains22,77,44. Independently retain Text substring of a2048-scalar root, reassign root, verify substring value; do not inspect or assert distinct addresses.

Expected independently: Alias99; snapshot22,77,44; source length0 after clear, snapshot length3. Retained Text equals its original content.

Coverage/gap: Native source reads sampled slice then releases it; exact generated copied-slice mutation independence missing from inspected fixtures. Text retention already covered natively; use public generated control only if it adds a demonstrated gap. Related source references: byte-model, byte-slice, view-lifetime.

**P2 — Bounded copy oracle using explicit snapshots.**

Original helper accepts destination/source Bytes and offsets/count, clamps count explicitly to each remaining length, snapshots selected source with Bytes.slice before writes, returns count. Independent expected arrays check untouched prefix/suffix. Cover count0, unequal remaining lengths, exact end, forward/backward shared-input overlap and full self-copy. Explicit original algorithm; no copy intrinsic or view feature added.

Expected independently: For11,22,33,44,55: src[0..4] -> dst[1..5] gives11,11,22,33,44; src[1..5] -> dst[0..4] gives22,33,44,55,55; full self-copy unchanged; count0 preserves all values; clamped count=min(requested,source remaining,destination remaining).

Coverage/gap: Go copy.go covers distinct allocations only. Original overlap helper tests snapshot semantics, not upstream Go copy lowering or unsupported public memmove. Related source references: byte-model, byte-self.

**P3 — Interior Unicode scalars distinguish byte positions.**

For aé🙂b assert every Character, length4,byteLength8, slice(1,3)=é🙂 and reconstructed Text equality. Explicit ordinal counter yields0,1,2,3; document Go byte offsets0,1,3,7 without pretending Minyar Text exposes bytes. Also reconstruct aä本☺ from Characters using current Text conversion.

Expected independently: Codes97,233,128578,98; ordinal sum6 versus conceptual byte-offset sum11. For aä本☺:97,228,26412,9786,length4,byteLength9.

Coverage/gap: Go range abcd☺ sum10 does not discriminate offset semantics; current fixtures have Unicode length/index controls but different exact discriminator sequence. Related source references: unicode, utf-loop, unicode-model.

**P4 — Once-evaluated loop collection and original growth contrast.**

Three helpers mutate shared Integer state[0] then return List1..5, Bytes1..5 or Textabcd☺; each for evaluates helper once. Independent visit/value counters. Empty variants still invoke helper once then no body effects. Optional List control starts1,2 and appends3 on first element, with bounded guard; doc requires rereading List.length. No Go tuple or blank syntax.

Expected independently: Each helper calls1; List/Bytes sum15,count5; Text sum10180,count5,byteLength7; empty call1/body0. Original growing List visits1,2,3,sum6.

Coverage/gap: Inspected local loops have no effectful collection helper count. Upstream does not mutate/grow ranged collections; growth contrast is Minyar-only original control, not a peer match. Related source references: loops, utf-loop, empty-loop.

**P5 — Valid literal content and invalid Character boundaries.**

Use ordinary Text literals and Text(Character) for ä,本,U+10FFFF and controls7,8,12,10,13,9,11,92,34. Construct escape-looking text through backslash Character, not raw/backquoted syntax. Independently reject Character1114112,55296,57343,-1 in isolated original programs; no replacement character success expectation or copied Go diagnostics.

Expected independently: ä length1/bytes2/code228; 本 length1/bytes3/code26412; max length1/bytes4/code1114111. Controls preserve every code in order; trailing-backslash text length7. Invalid scalar construction stops.

Coverage/gap: Native max/zero scalar roundtrip already exists. Compiler scalar-boundary rejection cases and exact content sequences are not present in inspected fixtures; do not add redundant native tests or unsupported escape spellings. Related source references: scalar-boundary, unicode, unicode-model, invalid-utf8.

**P6 — Nested and empty slice endpoints with lifetime.**

Runtime Text1234 full slice then nested[1,2],[2,3],[3,4],[2,4] by slice(start,end); preserve nested34 across parent/root rebinding. Test Text empty and Bytes empty slice(0,0); three-byte Bytes.slice(3,3). Separate original failures: Text/Bytes indexlength, empty index0, slice(length,length+1), negative/reversed bounds. No sentinel, writable view or List.slice.

Expected independently: 1234,2,3,4,34; retained34. Every legal empty range length0. Endpoint/invalid-range accesses stop; no sentinel zero exposed.

Coverage/gap: Exact generated nested ASCII and Bytes end-to-end empty slices pending; existing native view lifetime and model slices are related. Reuse existing bounds fixtures if they already assert each proposed negative case. Related source references: text-abc, view-lifetime, byte-empty, byte-model, unicode-model.

**P7 — Ordinary Text concatenation and conditional borrowed return.**

Join aoeu+asdf, aoeu+aoeu, and both empty orders around slice8..9 of dotted Text. Function(Boolean,Text):Text returns empty or argument; caller reassigns argument after true return, retained result staystrue. Explicit Lists42,56,54 and hello,comma-space,world! assert every element. Runtime only.

Expected independently: aoeuasdf; aoeuaoeu; each empty join result1,length1; false branch empty; true branchtrue surviving caller reassignment; both Lists length3 with exact values.

Coverage/gap: Related empty/self joins and return/lifetime fixtures exist. Exact peer content inputs and conditional borrowed-return sequence are pending in inspected fixtures; no comptime concat/repeat or pointer coercion claim. Related source references: text-self, text-abc, list-text, view-lifetime.

## Remaining scope and handoff

All selected-file source review is complete. No selected assertion/helper is knowingly left pending; retained support implementations outside the listed helper spans remain unreviewed and uncounted. Go copy1.go, other range/slice files and other unselected Zig behavior/std text files remain outside this round. Accessible sources were independently read; no unavailable resource needed alternate access.

All runtime projections and original regressions remain unimplemented/unexecuted. Full upstream compile-time/generic/pointer/capacity/conversion contracts are not covered. Exact local gaps are relative to the inspected snapshots; an implementer should deduplicate against other existing fixtures before adding tests. Parent retains prior98 comparisons plus this ledger’s new group count, with unlike group sizes and no new ports.

Only `research/2026-10-memory/peer-readonly-strings-round4.md/.json` and `evidence/peer-readonly/strings-round4` were authored. Existing dirty work and concurrent soak/application work were preserved. Parent scope/progress messages were sent using stable round4 request IDs; final handoff uses counts from this saved ledger.

Documentary verification found consistent attribution for all 32 Go literal equality calls, 47 Go range failure predicates, 223 Zig assertion/compile-error sites, all 76 backend skip-guard sites and all 20 nested helper subcases in Z28. Eleven pinned source/license/support hashes and fifteen local snapshot hashes matched. These are documentary checks only. See [document checks](../../evidence/peer-readonly/strings-round4/document-checks.json) and [final handoff](../../evidence/peer-readonly/strings-round4/handoff.json).
