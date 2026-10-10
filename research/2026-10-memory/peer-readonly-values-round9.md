# Read-only numeric and value peer review — round 9

Reviewed **4 complete new pinned files**, **566 raw physical lines** and **94 heterogeneous groups**. Dispositions: **16 adopt pending, 39 adapt pending, 39 incompatible**; zero exact groups credited already covered. All selected lines through EOF, helpers, phase guards and dormant bodies were read.

Two original regression proposals remain unimplemented, uncompiled and unexecuted. No maintained source/test/build edits, compilation, execution, ports, installs, timings, commits, subagents or central-manifest edits occurred. GPT-6.1 Sol high documentary research only. Root/core owns active executable projections and soak. Campaign earliest completion remains **2026-10-04 06:54:29 UTC**; this report does not claim campaign completion.

## Complete selection and immutable evidence

| Pinned source | Kind | Complete raw extent | Groups | SHA256 |
| --- | --- | --- | ---: | --- |
| [libcxx/test/std/algorithms/alg.sorting/alg.min.max/minmax.pass.cpp](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/algorithms/alg.sorting/alg.min.max/minmax.pass.cpp) | C++_standard_library_test_not_compiler_IR_test | L1–66 | 8 | `d482dc28d0d28a6aa7665a92850183030a69a3730a9a83cfb22812726ae8bf12` |
| [test/ken/array.go](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/array.go) | compiler_language_run_test | L1–138 | 10 | `c32ee895426d5f2c063a7d31af03cd7742aa18a5773302a2e9a16c5d3de01c1b` |
| [test/ken/shift.go](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go) | compiler_language_run_test | L1–121 | 30 | `24b53120a610e883c2bc7a3e75ab5553007d888748070e881e97e74c88ae5a3a` |
| [libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp) | C++_standard_library_test_not_compiler_IR_test | L1–241 | 46 | `39c2d013caf946fbd634e14518e3c7149a875b401c71401a501de0d6402c3483` |

Pins: Go `56ebf80e57db9f61981fc0636fc6419dc6f68eda`; LLVM `b708aea0bc7127adf4ec643660699c8bcdde1273`. Swift pin from peers.json was checked (`1ff1cc1170617ab23ab74aa8b741c8daca1903f6`), with no Swift file selected. No central/prior selected source overlaps. These are compiler-language Go tests and C++ standard-library tests, not LLVM IR optimizer tests.

Raw bytes and notices are retained under [upstream evidence](../../evidence/peer-readonly/values-round9/upstream/). [Provenance](../../evidence/peer-readonly/values-round9/provenance.json) retains URLs, byte hashes, licenses and exact read extents. [Screening](../../evidence/peer-readonly/values-round9/screening.json) preserves three candidate404 paths and two optional output-sidecar404 paths; no retry followed a retained raw failure. minmax_comp.pass.cpp is retained as an unselected screening candidate, with no review-group credit. The web display normalized Go array blank lines (133 displayed versus138 raw physical lines); all attribution uses saved physical bytes.

| License | Identification | SHA256 |
| --- | --- | --- |
| [llvm/LICENSE.TXT](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/LICENSE.TXT) | Apache-2.0 WITH LLVM-exception; full legacy/third-party sections also retained | `8d85c1057d742e597985c7d4e6320b015a9139385cff4cbae06ffc0ebe89afee` |
| [llvm/libcxx/LICENSE.TXT](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/LICENSE.TXT) | Apache-2.0 WITH LLVM-exception; full legacy/third-party sections also retained | `539dd7aed86e8a4f12cbdd0e6c50c189c7d74847e4fecc64ce2c6ee3a01da38b` |
| [go/LICENSE](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/LICENSE) | BSD-3-Clause | `911f8f5782931320f5b8d1160a76365b83aea6447ee6c04fa6d5591467db9dad` |

All selected headers and retained full licenses were read. Evidence contains unchanged upstream bytes; no upstream implementation is imported into maintained tests.

## Findings and contract boundaries

The gcd table supplies12 independent expected magnitudes. Every row has18 signed/type-order/unsigned/mixed call forms. The17 paired drivers additionally require C++ common result types and compile-time execution; an Integer loop cannot prove those contracts. The random tests use a separate recursive Euclidean oracle but supply no fixed generated stream or per-pair expected values; no10000-check Minyar credit is claimed. Limit tests each retain27 input entries including duplicates and729 designed ordered pairs. Signed minimum is excluded by the source representability precondition; unsigned converted negatives remain unsigned magnitudes. The widened1234/INT32_MIN case fits signed64 and expects2. C++ assertions can be disabled with NDEBUG, including entire runtime do_test calls; no assertion-enabled configuration was run.

Runtime minmax asserts addresses. Its equal-zero cases distinguish input identity despite equal values. Minyar min/max return scalar values and expose no scalar address, so these six runtime units are incompatible as written. The guarded constexpr pairs check0/1 values; those values can be projected at runtime, while the phase remains excluded. No C++ reference lifetime or Minyar allocation-elimination claim follows.

Go array uses `len !=10 && cap !=100`; a pass alone does not separately assert both. It reslices beyond current length using retained capacity. The final nested reslice begins at original root index35, so its independent sum is4355. Minyar has neither public List.slice nor capacity: initialized Lists and explicit ranges can preserve sums and helper-visible mutation only. The two bounds-fault bodies are fully read but commented out in main; they are dormant source probes, not executed tests.

Go shift helpers print mismatches without panicking. The pinned harness merges stdout/stderr and compares output; missing optional .out means empty expected output. The optional sidecar URLs returned404, supporting that bounded inference rather than a directory-wide absence proof. Twelve constant and18 dynamic tuples retain explicit answer cells. Nonselected i/u variables also shift, but only the selected branch is checked. Counts0/5 and small signed/positive values fit Minyar; count1025 must stop in Minyar, rather than adopting Go oversized-shift saturation/sign extension. Existing local sources already model full-width valid shifts and invalid counts; no redundant shift proposal is included.

## Frozen local source coverage

| ID / exact saved span | Source evidence | Limit | SHA256 |
| --- | --- | --- | --- |
| number-contract / L14–61, L94–112, L134–174, L230–277 | [docs/language.md](../../evidence/peer-readonly/values-round9/references/docs/language.md) — Signed64 Integer, checked arithmetic, abs/min/max, shift count0..63, ordinary loops; shared List/records. | No unsigned Integer, templates, constexpr, capacity or List.slice API. | `8f7f6fe21d789082e19f473dc77dddfb7166cb14c501789993b6264088aface6` |
| finite-extrema / L24–32 | [tests/conformance/floats-and-bits/program.min](../../evidence/peer-readonly/values-round9/references/tests/conformance/floats-and-bits/program.min) — Small Integer min(3,-2), Float max(1.5,2.5), clamp/abs and elementary bitwise/shift controls. | No C++ reference identity, equal-input extrema snapshot or full signed endpoint ordering. | `edb48dc4a78ef8a5d150355b8c78b940f96ae63f3f5193c384dd783a012dd31c` |
| finite-extrema-output / L1–36 | [tests/conformance/floats-and-bits/expected.stdout](../../evidence/peer-readonly/values-round9/references/tests/conformance/floats-and-bits/expected.stdout) — Retained exact stdout for conformance values. | Expected output source only; no execution here. | `af1af3465fff6eafdad2328137c2a23739ea0c006d29addb4d2445caf4d1a0f8` |
| shift-model / L12–46 | [tests/checked-scalars.py](../../evidence/peer-readonly/values-round9/references/tests/checked-scalars.py) — 48 seeded full-width signed values/counts; left shift truncation and arithmetic right independent Python models; abs/clamp. | Source generation exists; exact 1234/-1234/5678 answer table and count1025 are not forced by inspected generation. | `34df3cd2f5b5a894c3fb7155251689a47b9d0dd0a176e57d3cf5a9501b307963` |
| shift-boundaries / L95–120 | [tests/checked-scalars.py](../../evidence/peer-readonly/values-round9/references/tests/checked-scalars.py) — Count63, signed minimum shifted by0, negative arithmetic right, scalar boundaries. | No Go unsigned contract or oversized-shift success. | `34df3cd2f5b5a894c3fb7155251689a47b9d0dd0a176e57d3cf5a9501b307963` |
| shift-failures / L57–93, L122–131 | [tests/checked-scalars.py](../../evidence/peer-readonly/values-round9/references/tests/checked-scalars.py) — Both shift operators reject minimum/-1/64/maximum counts with left-to-right prints11,22 and exact diagnostic. | Count1025 is not an explicit fixture in these spans; it is not proposed as a new high-value redundant test. | `34df3cd2f5b5a894c3fb7155251689a47b9d0dd0a176e57d3cf5a9501b307963` |
| checked-abs / L165–186 | [tests/checked-scalars.py](../../evidence/peer-readonly/values-round9/references/tests/checked-scalars.py) — Signed minimum abs failure and invalid clamp bounds have exact diagnostics. | Rejects signed minimum; does not cover a complete Euclidean composition or import C++ undefined behavior. | `34df3cd2f5b5a894c3fb7155251689a47b9d0dd0a176e57d3cf5a9501b307963` |
| division-model / L119–133, L161–190 | [tests/peer-research-semantics.py](../../evidence/peer-readonly/values-round9/references/tests/peer-research-semantics.py) — Signed quotient/remainder compared with a separate sparse-bit subtract model; signed remainder projection. | No gcd loop/test0/common_type or Euclidean fixed expected near-boundary composition in inspected spans. | `561a56339fd970b10b2f68e849a68039f06067856209b97a608b763fcaacd981` |
| list-alias / L1–12 | [tests/conformance/text-and-lists/program.min](../../evidence/peer-readonly/values-round9/references/tests/conformance/text-and-lists/program.min) — Aliases see additions/index replacements; nested homogeneous values. | No capacity/reslicing/fixed-array zero initialization or root-offset35 sum. | `ab2aa53fb9eb61b91f577b5275d48668a99471e99aa8e6126ca1b74ffa9b8dd0` |
| list-bounds / L47–100 | [tests/list-access.py](../../evidence/peer-readonly/values-round9/references/tests/list-access.py) — Length0/2 invalid getters/setters, growth during index/RHS, captured receiver replacement. | Different sizes and active standalone traps; does not run Go dormant bodies or assert pointer identity. | `cadc7dc2edddf284a4f7c7b6ea99ed8fdf986ffb068d5db2f295371cdfefb552` |
| existing-row-projection / L84–101 | [tests/memory-research-peer-projections.py](../../evidence/peer-readonly/values-round9/references/tests/memory-research-peer-projections.py) — Retained shared row versus explicit copy, outer replacement, length/values after dropping owners. | Managed row/reference control; no builtin min/max returned scalar snapshot or Euclidean arithmetic. | `c04f0700dd2afed431f86007b2b8b0e23f4e635590c81f23ba09660dcd69fbfa` |

Implementation reads are separate from test coverage:

- [compiler/compiler.min](../../evidence/peer-readonly/values-round9/references/compiler/compiler.min) [[1836, 1884]], SHA256 `994d457a3728806942541df5f567e332a6594ea508c3bc61cc2d4ac5c485eadc`: sdiv/srem share checked division; shift emits checked count then shl/ashr. Implementation reading only, not a generated-IR or executable observation.
- [compiler/compiler.min](../../evidence/peer-readonly/values-round9/references/compiler/compiler.min) [[3053, 3073], [3100, 3112]], SHA256 `994d457a3728806942541df5f567e332a6594ea508c3bc61cc2d4ac5c485eadc`: Integer extrema use signed compare/select and return scalar operands; Float uses minnum/maxnum. Integer equality selects right scalar but exposes no address; no Float tie-bit rule proposed.
- [runtime/minyar_numbers.h](../../evidence/peer-readonly/values-round9/references/runtime/minyar_numbers.h) [[1, 31], [201, 220]], SHA256 `ce8ac3a34ac9cf59035057d80aa9ac77ed738d9076922b11c9e888d59341620d`: Overflow/division failures, abs minimum failure and shift count check. Numeric helper ABI/source only; no runtime execution or platform representation claim.

All mappings bind to retained bytes. Source reading and expected.stdout files are documentary, not observed pass evidence. Searches for gcd/min/max were limited to inspected fixtures and prior proposals; no whole-repository coverage or exhaustive novelty is asserted.

## Complete per-group ledger

The [JSON ledger](peer-readonly-values-round9.json) records every group, exact oracle line/helper span, subcall/limit expansion, source hash and local coverage reference. The lexical oracle index attributes each source site once and attaches reusable helper sites to every relevant group; template/loop multiplicity is never a port count.

### G1 — Cases row (0, 0) -> 0

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L31–31](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L31-L31) — **adapt_pending**; phase: runtime_and_constexpr_in_upstream. 

Expected from source: Every signed/sign-reversed, unsigned, mixed-sign and type-order instantiation of this row expects gcd magnitude 0. Both result-type checks must succeed. 18 test0 call forms per row, across the separately recorded type/phase drivers.

Minyar: An original Integer Euclidean loop can preserve the bounded magnitudes and all four sign combinations. Minyar has no gcd builtin, generics, unsigned Integer or constexpr execution; this is an arithmetic value projection, not std::gcd parity.

Oracle source lines: [51]; complete helper spans: [[44, 70], [128, 169]]; related frozen coverage: number-contract, division-model, checked-abs.

### G2 — Cases row (1, 0) -> 1

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L32–32](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L32-L32) — **adapt_pending**; phase: runtime_and_constexpr_in_upstream. 

Expected from source: Every signed/sign-reversed, unsigned, mixed-sign and type-order instantiation of this row expects gcd magnitude 1. Both result-type checks must succeed. 18 test0 call forms per row, across the separately recorded type/phase drivers.

Minyar: An original Integer Euclidean loop can preserve the bounded magnitudes and all four sign combinations. Minyar has no gcd builtin, generics, unsigned Integer or constexpr execution; this is an arithmetic value projection, not std::gcd parity.

Oracle source lines: [51]; complete helper spans: [[44, 70], [128, 169]]; related frozen coverage: number-contract, division-model, checked-abs.

### G3 — Cases row (0, 1) -> 1

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L33–33](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L33-L33) — **adapt_pending**; phase: runtime_and_constexpr_in_upstream. 

Expected from source: Every signed/sign-reversed, unsigned, mixed-sign and type-order instantiation of this row expects gcd magnitude 1. Both result-type checks must succeed. 18 test0 call forms per row, across the separately recorded type/phase drivers.

Minyar: An original Integer Euclidean loop can preserve the bounded magnitudes and all four sign combinations. Minyar has no gcd builtin, generics, unsigned Integer or constexpr execution; this is an arithmetic value projection, not std::gcd parity.

Oracle source lines: [51]; complete helper spans: [[44, 70], [128, 169]]; related frozen coverage: number-contract, division-model, checked-abs.

### G4 — Cases row (1, 1) -> 1

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L34–34](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L34-L34) — **adapt_pending**; phase: runtime_and_constexpr_in_upstream. 

Expected from source: Every signed/sign-reversed, unsigned, mixed-sign and type-order instantiation of this row expects gcd magnitude 1. Both result-type checks must succeed. 18 test0 call forms per row, across the separately recorded type/phase drivers.

Minyar: An original Integer Euclidean loop can preserve the bounded magnitudes and all four sign combinations. Minyar has no gcd builtin, generics, unsigned Integer or constexpr execution; this is an arithmetic value projection, not std::gcd parity.

Oracle source lines: [51]; complete helper spans: [[44, 70], [128, 169]]; related frozen coverage: number-contract, division-model, checked-abs.

### G5 — Cases row (2, 3) -> 1

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L35–35](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L35-L35) — **adapt_pending**; phase: runtime_and_constexpr_in_upstream. 

Expected from source: Every signed/sign-reversed, unsigned, mixed-sign and type-order instantiation of this row expects gcd magnitude 1. Both result-type checks must succeed. 18 test0 call forms per row, across the separately recorded type/phase drivers.

Minyar: An original Integer Euclidean loop can preserve the bounded magnitudes and all four sign combinations. Minyar has no gcd builtin, generics, unsigned Integer or constexpr execution; this is an arithmetic value projection, not std::gcd parity.

Oracle source lines: [51]; complete helper spans: [[44, 70], [128, 169]]; related frozen coverage: number-contract, division-model, checked-abs.

### G6 — Cases row (2, 4) -> 2

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L36–36](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L36-L36) — **adapt_pending**; phase: runtime_and_constexpr_in_upstream. 

Expected from source: Every signed/sign-reversed, unsigned, mixed-sign and type-order instantiation of this row expects gcd magnitude 2. Both result-type checks must succeed. 18 test0 call forms per row, across the separately recorded type/phase drivers.

Minyar: An original Integer Euclidean loop can preserve the bounded magnitudes and all four sign combinations. Minyar has no gcd builtin, generics, unsigned Integer or constexpr execution; this is an arithmetic value projection, not std::gcd parity.

Oracle source lines: [51]; complete helper spans: [[44, 70], [128, 169]]; related frozen coverage: number-contract, division-model, checked-abs.

### G7 — Cases row (11, 9) -> 1

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L37–37](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L37-L37) — **adapt_pending**; phase: runtime_and_constexpr_in_upstream. 

Expected from source: Every signed/sign-reversed, unsigned, mixed-sign and type-order instantiation of this row expects gcd magnitude 1. Both result-type checks must succeed. 18 test0 call forms per row, across the separately recorded type/phase drivers.

Minyar: An original Integer Euclidean loop can preserve the bounded magnitudes and all four sign combinations. Minyar has no gcd builtin, generics, unsigned Integer or constexpr execution; this is an arithmetic value projection, not std::gcd parity.

Oracle source lines: [51]; complete helper spans: [[44, 70], [128, 169]]; related frozen coverage: number-contract, division-model, checked-abs.

### G8 — Cases row (36, 17) -> 1

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L38–38](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L38-L38) — **adapt_pending**; phase: runtime_and_constexpr_in_upstream. 

Expected from source: Every signed/sign-reversed, unsigned, mixed-sign and type-order instantiation of this row expects gcd magnitude 1. Both result-type checks must succeed. 18 test0 call forms per row, across the separately recorded type/phase drivers.

Minyar: An original Integer Euclidean loop can preserve the bounded magnitudes and all four sign combinations. Minyar has no gcd builtin, generics, unsigned Integer or constexpr execution; this is an arithmetic value projection, not std::gcd parity.

Oracle source lines: [51]; complete helper spans: [[44, 70], [128, 169]]; related frozen coverage: number-contract, division-model, checked-abs.

### G9 — Cases row (36, 18) -> 18

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L39–39](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L39-L39) — **adapt_pending**; phase: runtime_and_constexpr_in_upstream. 

Expected from source: Every signed/sign-reversed, unsigned, mixed-sign and type-order instantiation of this row expects gcd magnitude 18. Both result-type checks must succeed. 18 test0 call forms per row, across the separately recorded type/phase drivers.

Minyar: An original Integer Euclidean loop can preserve the bounded magnitudes and all four sign combinations. Minyar has no gcd builtin, generics, unsigned Integer or constexpr execution; this is an arithmetic value projection, not std::gcd parity.

Oracle source lines: [51]; complete helper spans: [[44, 70], [128, 169]]; related frozen coverage: number-contract, division-model, checked-abs.

### G10 — Cases row (25, 30) -> 5

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L40–40](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L40-L40) — **adapt_pending**; phase: runtime_and_constexpr_in_upstream. 

Expected from source: Every signed/sign-reversed, unsigned, mixed-sign and type-order instantiation of this row expects gcd magnitude 5. Both result-type checks must succeed. 18 test0 call forms per row, across the separately recorded type/phase drivers.

Minyar: An original Integer Euclidean loop can preserve the bounded magnitudes and all four sign combinations. Minyar has no gcd builtin, generics, unsigned Integer or constexpr execution; this is an arithmetic value projection, not std::gcd parity.

Oracle source lines: [51]; complete helper spans: [[44, 70], [128, 169]]; related frozen coverage: number-contract, division-model, checked-abs.

### G11 — Cases row (24, 16) -> 8

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L41–41](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L41-L41) — **adapt_pending**; phase: runtime_and_constexpr_in_upstream. 

Expected from source: Every signed/sign-reversed, unsigned, mixed-sign and type-order instantiation of this row expects gcd magnitude 8. Both result-type checks must succeed. 18 test0 call forms per row, across the separately recorded type/phase drivers.

Minyar: An original Integer Euclidean loop can preserve the bounded magnitudes and all four sign combinations. Minyar has no gcd builtin, generics, unsigned Integer or constexpr execution; this is an arithmetic value projection, not std::gcd parity.

Oracle source lines: [51]; complete helper spans: [[44, 70], [128, 169]]; related frozen coverage: number-contract, division-model, checked-abs.

### G12 — Cases row (124, 100) -> 4

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L42–42](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L42-L42) — **adapt_pending**; phase: runtime_and_constexpr_in_upstream. 

Expected from source: Every signed/sign-reversed, unsigned, mixed-sign and type-order instantiation of this row expects gcd magnitude 4. Both result-type checks must succeed. 18 test0 call forms per row, across the separately recorded type/phase drivers.

Minyar: An original Integer Euclidean loop can preserve the bounded magnitudes and all four sign combinations. Minyar has no gcd builtin, generics, unsigned Integer or constexpr execution; this is an arithmetic value projection, not std::gcd parity.

Oracle source lines: [51]; complete helper spans: [[44, 70], [128, 169]]; related frozen coverage: number-contract, division-model, checked-abs.

### T1 — do_test<signed char> type/phase driver

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L175–175, L181–181](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L175-L181) — **incompatible_as_written**; phase: paired_constexpr_and_runtime. 

Expected from source: Compile-time static_assert(do_test()) succeeds and runtime assert(do_test(non_cce)) succeeds. For all 12 rows, each of 18 call forms verifies the expected value and common result type in both operand-type orders. The unused do_test parameter receives argc in the runtime driver; it does not alter any expected value.

Minyar: Minyar has one signed Integer and no template/common_type/constexpr contract. G1–G12 separately retain the small mathematical values; a successful Integer loop cannot satisfy this driver type matrix or its compile-time phase.

Oracle source lines: [49, 50, 175, 181]; complete helper spans: [[44, 53], [128, 169]]; related frozen coverage: number-contract.

### T2 — do_test<short> type/phase driver

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L176–176, L182–182](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L176-L182) — **incompatible_as_written**; phase: paired_constexpr_and_runtime. 

Expected from source: Compile-time static_assert(do_test()) succeeds and runtime assert(do_test(non_cce)) succeeds. For all 12 rows, each of 18 call forms verifies the expected value and common result type in both operand-type orders. The unused do_test parameter receives argc in the runtime driver; it does not alter any expected value.

Minyar: Minyar has one signed Integer and no template/common_type/constexpr contract. G1–G12 separately retain the small mathematical values; a successful Integer loop cannot satisfy this driver type matrix or its compile-time phase.

Oracle source lines: [49, 50, 176, 182]; complete helper spans: [[44, 53], [128, 169]]; related frozen coverage: number-contract.

### T3 — do_test<int> type/phase driver

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L177–177, L183–183](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L177-L183) — **incompatible_as_written**; phase: paired_constexpr_and_runtime. 

Expected from source: Compile-time static_assert(do_test()) succeeds and runtime assert(do_test(non_cce)) succeeds. For all 12 rows, each of 18 call forms verifies the expected value and common result type in both operand-type orders. The unused do_test parameter receives argc in the runtime driver; it does not alter any expected value.

Minyar: Minyar has one signed Integer and no template/common_type/constexpr contract. G1–G12 separately retain the small mathematical values; a successful Integer loop cannot satisfy this driver type matrix or its compile-time phase.

Oracle source lines: [49, 50, 177, 183]; complete helper spans: [[44, 53], [128, 169]]; related frozen coverage: number-contract.

### T4 — do_test<long> type/phase driver

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L178–178, L184–184](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L178-L184) — **incompatible_as_written**; phase: paired_constexpr_and_runtime. 

Expected from source: Compile-time static_assert(do_test()) succeeds and runtime assert(do_test(non_cce)) succeeds. For all 12 rows, each of 18 call forms verifies the expected value and common result type in both operand-type orders. The unused do_test parameter receives argc in the runtime driver; it does not alter any expected value.

Minyar: Minyar has one signed Integer and no template/common_type/constexpr contract. G1–G12 separately retain the small mathematical values; a successful Integer loop cannot satisfy this driver type matrix or its compile-time phase.

Oracle source lines: [49, 50, 178, 184]; complete helper spans: [[44, 53], [128, 169]]; related frozen coverage: number-contract.

### T5 — do_test<long long> type/phase driver

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L179–179, L185–185](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L179-L185) — **incompatible_as_written**; phase: paired_constexpr_and_runtime. 

Expected from source: Compile-time static_assert(do_test()) succeeds and runtime assert(do_test(non_cce)) succeeds. For all 12 rows, each of 18 call forms verifies the expected value and common result type in both operand-type orders. The unused do_test parameter receives argc in the runtime driver; it does not alter any expected value.

Minyar: Minyar has one signed Integer and no template/common_type/constexpr contract. G1–G12 separately retain the small mathematical values; a successful Integer loop cannot satisfy this driver type matrix or its compile-time phase.

Oracle source lines: [49, 50, 179, 185]; complete helper spans: [[44, 53], [128, 169]]; related frozen coverage: number-contract.

### T6 — do_test<std::int8_t> type/phase driver

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L187–187, L192–192](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L187-L192) — **incompatible_as_written**; phase: paired_constexpr_and_runtime. 

Expected from source: Compile-time static_assert(do_test()) succeeds and runtime assert(do_test(non_cce)) succeeds. For all 12 rows, each of 18 call forms verifies the expected value and common result type in both operand-type orders. The unused do_test parameter receives argc in the runtime driver; it does not alter any expected value.

Minyar: Minyar has one signed Integer and no template/common_type/constexpr contract. G1–G12 separately retain the small mathematical values; a successful Integer loop cannot satisfy this driver type matrix or its compile-time phase.

Oracle source lines: [49, 50, 187, 192]; complete helper spans: [[44, 53], [128, 169]]; related frozen coverage: number-contract.

### T7 — do_test<std::int16_t> type/phase driver

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L188–188, L193–193](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L188-L193) — **incompatible_as_written**; phase: paired_constexpr_and_runtime. 

Expected from source: Compile-time static_assert(do_test()) succeeds and runtime assert(do_test(non_cce)) succeeds. For all 12 rows, each of 18 call forms verifies the expected value and common result type in both operand-type orders. The unused do_test parameter receives argc in the runtime driver; it does not alter any expected value.

Minyar: Minyar has one signed Integer and no template/common_type/constexpr contract. G1–G12 separately retain the small mathematical values; a successful Integer loop cannot satisfy this driver type matrix or its compile-time phase.

Oracle source lines: [49, 50, 188, 193]; complete helper spans: [[44, 53], [128, 169]]; related frozen coverage: number-contract.

### T8 — do_test<std::int32_t> type/phase driver

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L189–189, L194–194](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L189-L194) — **incompatible_as_written**; phase: paired_constexpr_and_runtime. 

Expected from source: Compile-time static_assert(do_test()) succeeds and runtime assert(do_test(non_cce)) succeeds. For all 12 rows, each of 18 call forms verifies the expected value and common result type in both operand-type orders. The unused do_test parameter receives argc in the runtime driver; it does not alter any expected value.

Minyar: Minyar has one signed Integer and no template/common_type/constexpr contract. G1–G12 separately retain the small mathematical values; a successful Integer loop cannot satisfy this driver type matrix or its compile-time phase.

Oracle source lines: [49, 50, 189, 194]; complete helper spans: [[44, 53], [128, 169]]; related frozen coverage: number-contract.

### T9 — do_test<std::int64_t> type/phase driver

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L190–190, L195–195](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L190-L195) — **incompatible_as_written**; phase: paired_constexpr_and_runtime. 

Expected from source: Compile-time static_assert(do_test()) succeeds and runtime assert(do_test(non_cce)) succeeds. For all 12 rows, each of 18 call forms verifies the expected value and common result type in both operand-type orders. The unused do_test parameter receives argc in the runtime driver; it does not alter any expected value.

Minyar: Minyar has one signed Integer and no template/common_type/constexpr contract. G1–G12 separately retain the small mathematical values; a successful Integer loop cannot satisfy this driver type matrix or its compile-time phase.

Oracle source lines: [49, 50, 190, 195]; complete helper spans: [[44, 53], [128, 169]]; related frozen coverage: number-contract.

### T10 — do_test<signed char, int> type/phase driver

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L197–197, L206–206](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L197-L206) — **incompatible_as_written**; phase: paired_constexpr_and_runtime. 

Expected from source: Compile-time static_assert(do_test()) succeeds and runtime assert(do_test(non_cce)) succeeds. For all 12 rows, each of 18 call forms verifies the expected value and common result type in both operand-type orders. The unused do_test parameter receives argc in the runtime driver; it does not alter any expected value.

Minyar: Minyar has one signed Integer and no template/common_type/constexpr contract. G1–G12 separately retain the small mathematical values; a successful Integer loop cannot satisfy this driver type matrix or its compile-time phase.

Oracle source lines: [49, 50, 197, 206]; complete helper spans: [[44, 53], [128, 169]]; related frozen coverage: number-contract.

### T11 — do_test<int, signed char> type/phase driver

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L198–198, L207–207](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L198-L207) — **incompatible_as_written**; phase: paired_constexpr_and_runtime. 

Expected from source: Compile-time static_assert(do_test()) succeeds and runtime assert(do_test(non_cce)) succeeds. For all 12 rows, each of 18 call forms verifies the expected value and common result type in both operand-type orders. The unused do_test parameter receives argc in the runtime driver; it does not alter any expected value.

Minyar: Minyar has one signed Integer and no template/common_type/constexpr contract. G1–G12 separately retain the small mathematical values; a successful Integer loop cannot satisfy this driver type matrix or its compile-time phase.

Oracle source lines: [49, 50, 198, 207]; complete helper spans: [[44, 53], [128, 169]]; related frozen coverage: number-contract.

### T12 — do_test<short, int> type/phase driver

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L199–199, L208–208](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L199-L208) — **incompatible_as_written**; phase: paired_constexpr_and_runtime. 

Expected from source: Compile-time static_assert(do_test()) succeeds and runtime assert(do_test(non_cce)) succeeds. For all 12 rows, each of 18 call forms verifies the expected value and common result type in both operand-type orders. The unused do_test parameter receives argc in the runtime driver; it does not alter any expected value.

Minyar: Minyar has one signed Integer and no template/common_type/constexpr contract. G1–G12 separately retain the small mathematical values; a successful Integer loop cannot satisfy this driver type matrix or its compile-time phase.

Oracle source lines: [49, 50, 199, 208]; complete helper spans: [[44, 53], [128, 169]]; related frozen coverage: number-contract.

### T13 — do_test<int, short> type/phase driver

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L200–200, L209–209](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L200-L209) — **incompatible_as_written**; phase: paired_constexpr_and_runtime. 

Expected from source: Compile-time static_assert(do_test()) succeeds and runtime assert(do_test(non_cce)) succeeds. For all 12 rows, each of 18 call forms verifies the expected value and common result type in both operand-type orders. The unused do_test parameter receives argc in the runtime driver; it does not alter any expected value.

Minyar: Minyar has one signed Integer and no template/common_type/constexpr contract. G1–G12 separately retain the small mathematical values; a successful Integer loop cannot satisfy this driver type matrix or its compile-time phase.

Oracle source lines: [49, 50, 200, 209]; complete helper spans: [[44, 53], [128, 169]]; related frozen coverage: number-contract.

### T14 — do_test<int, long> type/phase driver

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L201–201, L210–210](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L201-L210) — **incompatible_as_written**; phase: paired_constexpr_and_runtime. 

Expected from source: Compile-time static_assert(do_test()) succeeds and runtime assert(do_test(non_cce)) succeeds. For all 12 rows, each of 18 call forms verifies the expected value and common result type in both operand-type orders. The unused do_test parameter receives argc in the runtime driver; it does not alter any expected value.

Minyar: Minyar has one signed Integer and no template/common_type/constexpr contract. G1–G12 separately retain the small mathematical values; a successful Integer loop cannot satisfy this driver type matrix or its compile-time phase.

Oracle source lines: [49, 50, 201, 210]; complete helper spans: [[44, 53], [128, 169]]; related frozen coverage: number-contract.

### T15 — do_test<long, int> type/phase driver

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L202–202, L211–211](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L202-L211) — **incompatible_as_written**; phase: paired_constexpr_and_runtime. 

Expected from source: Compile-time static_assert(do_test()) succeeds and runtime assert(do_test(non_cce)) succeeds. For all 12 rows, each of 18 call forms verifies the expected value and common result type in both operand-type orders. The unused do_test parameter receives argc in the runtime driver; it does not alter any expected value.

Minyar: Minyar has one signed Integer and no template/common_type/constexpr contract. G1–G12 separately retain the small mathematical values; a successful Integer loop cannot satisfy this driver type matrix or its compile-time phase.

Oracle source lines: [49, 50, 202, 211]; complete helper spans: [[44, 53], [128, 169]]; related frozen coverage: number-contract.

### T16 — do_test<int, long long> type/phase driver

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L203–203, L212–212](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L203-L212) — **incompatible_as_written**; phase: paired_constexpr_and_runtime. 

Expected from source: Compile-time static_assert(do_test()) succeeds and runtime assert(do_test(non_cce)) succeeds. For all 12 rows, each of 18 call forms verifies the expected value and common result type in both operand-type orders. The unused do_test parameter receives argc in the runtime driver; it does not alter any expected value.

Minyar: Minyar has one signed Integer and no template/common_type/constexpr contract. G1–G12 separately retain the small mathematical values; a successful Integer loop cannot satisfy this driver type matrix or its compile-time phase.

Oracle source lines: [49, 50, 203, 212]; complete helper spans: [[44, 53], [128, 169]]; related frozen coverage: number-contract.

### T17 — do_test<long long, int> type/phase driver

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L204–204, L213–213](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L204-L213) — **incompatible_as_written**; phase: paired_constexpr_and_runtime. 

Expected from source: Compile-time static_assert(do_test()) succeeds and runtime assert(do_test(non_cce)) succeeds. For all 12 rows, each of 18 call forms verifies the expected value and common result type in both operand-type orders. The unused do_test parameter receives argc in the runtime driver; it does not alter any expected value.

Minyar: Minyar has one signed Integer and no template/common_type/constexpr contract. G1–G12 separately retain the small mathematical values; a successful Integer loop cannot satisfy this driver type matrix or its compile-time phase.

Oracle source lines: [49, 50, 204, 213]; complete helper spans: [[44, 53], [128, 169]]; related frozen coverage: number-contract.

### F1 — seeded fuzzy std::int8_t

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L222–222](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L222-L222) — **incompatible_as_written**; phase: runtime_loop; comparison_only_if_assert_enabled. 

Expected from source: 10000 generated pairs in [0, 127] compare std::gcd with basic_gcd. mt19937 is seeded 1938. One-byte types use int as distribution result type. The source supplies no explicit per-pair answer table; an identical seed alone does not establish an identical distribution sequence across implementations.

Minyar: No Minyar std::gcd, mt19937, distribution API or integral type instantiation exists. Use explicit independent operands/answers if deriving a new arithmetic regression; do not invent a copied seeded stream or credit 10000 Minyar checks.

Oracle source lines: [83]; complete helper spans: [[55, 85]]; related frozen coverage: division-model.

### F2 — seeded fuzzy std::int16_t

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L223–223](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L223-L223) — **incompatible_as_written**; phase: runtime_loop; comparison_only_if_assert_enabled. 

Expected from source: 10000 generated pairs in [0, 32767] compare std::gcd with basic_gcd. mt19937 is seeded 1938. One-byte types use int as distribution result type. The source supplies no explicit per-pair answer table; an identical seed alone does not establish an identical distribution sequence across implementations.

Minyar: No Minyar std::gcd, mt19937, distribution API or integral type instantiation exists. Use explicit independent operands/answers if deriving a new arithmetic regression; do not invent a copied seeded stream or credit 10000 Minyar checks.

Oracle source lines: [83]; complete helper spans: [[55, 85]]; related frozen coverage: division-model.

### F3 — seeded fuzzy std::int32_t

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L224–224](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L224-L224) — **incompatible_as_written**; phase: runtime_loop; comparison_only_if_assert_enabled. 

Expected from source: 10000 generated pairs in [0, 2147483647] compare std::gcd with basic_gcd. mt19937 is seeded 1938. One-byte types use int as distribution result type. The source supplies no explicit per-pair answer table; an identical seed alone does not establish an identical distribution sequence across implementations.

Minyar: No Minyar std::gcd, mt19937, distribution API or integral type instantiation exists. Use explicit independent operands/answers if deriving a new arithmetic regression; do not invent a copied seeded stream or credit 10000 Minyar checks.

Oracle source lines: [83]; complete helper spans: [[55, 85]]; related frozen coverage: division-model.

### F4 — seeded fuzzy std::int64_t

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L225–225](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L225-L225) — **incompatible_as_written**; phase: runtime_loop; comparison_only_if_assert_enabled. 

Expected from source: 10000 generated pairs in [0, 9223372036854775807] compare std::gcd with basic_gcd. mt19937 is seeded 1938. One-byte types use int as distribution result type. The source supplies no explicit per-pair answer table; an identical seed alone does not establish an identical distribution sequence across implementations.

Minyar: No Minyar std::gcd, mt19937, distribution API or integral type instantiation exists. Use explicit independent operands/answers if deriving a new arithmetic regression; do not invent a copied seeded stream or credit 10000 Minyar checks.

Oracle source lines: [83]; complete helper spans: [[55, 85]]; related frozen coverage: division-model.

### F5 — seeded fuzzy std::uint8_t

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L226–226](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L226-L226) — **incompatible_as_written**; phase: runtime_loop; comparison_only_if_assert_enabled. 

Expected from source: 10000 generated pairs in [0, 255] compare std::gcd with basic_gcd. mt19937 is seeded 1938. One-byte types use int as distribution result type. The source supplies no explicit per-pair answer table; an identical seed alone does not establish an identical distribution sequence across implementations.

Minyar: No Minyar std::gcd, mt19937, distribution API or integral type instantiation exists. Use explicit independent operands/answers if deriving a new arithmetic regression; do not invent a copied seeded stream or credit 10000 Minyar checks.

Oracle source lines: [83]; complete helper spans: [[55, 85]]; related frozen coverage: division-model.

### F6 — seeded fuzzy std::uint16_t

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L227–227](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L227-L227) — **incompatible_as_written**; phase: runtime_loop; comparison_only_if_assert_enabled. 

Expected from source: 10000 generated pairs in [0, 65535] compare std::gcd with basic_gcd. mt19937 is seeded 1938. One-byte types use int as distribution result type. The source supplies no explicit per-pair answer table; an identical seed alone does not establish an identical distribution sequence across implementations.

Minyar: No Minyar std::gcd, mt19937, distribution API or integral type instantiation exists. Use explicit independent operands/answers if deriving a new arithmetic regression; do not invent a copied seeded stream or credit 10000 Minyar checks.

Oracle source lines: [83]; complete helper spans: [[55, 85]]; related frozen coverage: division-model.

### F7 — seeded fuzzy std::uint32_t

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L228–228](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L228-L228) — **incompatible_as_written**; phase: runtime_loop; comparison_only_if_assert_enabled. 

Expected from source: 10000 generated pairs in [0, 4294967295] compare std::gcd with basic_gcd. mt19937 is seeded 1938. One-byte types use int as distribution result type. The source supplies no explicit per-pair answer table; an identical seed alone does not establish an identical distribution sequence across implementations.

Minyar: No Minyar std::gcd, mt19937, distribution API or integral type instantiation exists. Use explicit independent operands/answers if deriving a new arithmetic regression; do not invent a copied seeded stream or credit 10000 Minyar checks.

Oracle source lines: [83]; complete helper spans: [[55, 85]]; related frozen coverage: division-model.

### F8 — seeded fuzzy std::uint64_t

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L229–229](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L229-L229) — **incompatible_as_written**; phase: runtime_loop; comparison_only_if_assert_enabled. 

Expected from source: 10000 generated pairs in [0, 18446744073709551615] compare std::gcd with basic_gcd. mt19937 is seeded 1938. One-byte types use int as distribution result type. The source supplies no explicit per-pair answer table; an identical seed alone does not establish an identical distribution sequence across implementations.

Minyar: No Minyar std::gcd, mt19937, distribution API or integral type instantiation exists. Use explicit independent operands/answers if deriving a new arithmetic regression; do not invent a copied seeded stream or credit 10000 Minyar checks.

Oracle source lines: [83]; complete helper spans: [[55, 85]]; related frozen coverage: division-model.

### L1 — limit Cartesian table std::int8_t

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L231–231](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L231-L231) — **adapt_pending**; phase: runtime_only_if_assert_enabled. 

Expected from source: Each ordered pair in the 27-entry table must equal the independent basic_gcd helper. Duplicate entries remain present; design is 27×27=729 comparisons for this invocation. Signed minimum itself is deliberately excluded because its absolute value is unrepresentable. Unsigned negative spellings convert modulo the type width, rather than retaining a negative magnitude.

Minyar: The listed mathematical values fit Integer. Explicit Integer constants and a new loop may preserve their gcd values, but not C++ widths, unsigned casts, common types or the std::gcd implementation. No signed-minimum UB case is made into a Minyar success expectation.

Oracle source lines: [123]; complete helper spans: [[55, 70], [87, 126]]; related frozen coverage: number-contract, division-model, checked-abs.

### L2 — limit Cartesian table std::int16_t

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L232–232](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L232-L232) — **adapt_pending**; phase: runtime_only_if_assert_enabled. 

Expected from source: Each ordered pair in the 27-entry table must equal the independent basic_gcd helper. Duplicate entries remain present; design is 27×27=729 comparisons for this invocation. Signed minimum itself is deliberately excluded because its absolute value is unrepresentable. Unsigned negative spellings convert modulo the type width, rather than retaining a negative magnitude.

Minyar: The listed mathematical values fit Integer. Explicit Integer constants and a new loop may preserve their gcd values, but not C++ widths, unsigned casts, common types or the std::gcd implementation. No signed-minimum UB case is made into a Minyar success expectation.

Oracle source lines: [123]; complete helper spans: [[55, 70], [87, 126]]; related frozen coverage: number-contract, division-model, checked-abs.

### L3 — limit Cartesian table std::int32_t

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L233–233](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L233-L233) — **adapt_pending**; phase: runtime_only_if_assert_enabled. 

Expected from source: Each ordered pair in the 27-entry table must equal the independent basic_gcd helper. Duplicate entries remain present; design is 27×27=729 comparisons for this invocation. Signed minimum itself is deliberately excluded because its absolute value is unrepresentable. Unsigned negative spellings convert modulo the type width, rather than retaining a negative magnitude.

Minyar: The listed mathematical values fit Integer. Explicit Integer constants and a new loop may preserve their gcd values, but not C++ widths, unsigned casts, common types or the std::gcd implementation. No signed-minimum UB case is made into a Minyar success expectation.

Oracle source lines: [123]; complete helper spans: [[55, 70], [87, 126]]; related frozen coverage: number-contract, division-model, checked-abs.

### L4 — limit Cartesian table std::int64_t

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L234–234](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L234-L234) — **adapt_pending**; phase: runtime_only_if_assert_enabled. 

Expected from source: Each ordered pair in the 27-entry table must equal the independent basic_gcd helper. Duplicate entries remain present; design is 27×27=729 comparisons for this invocation. Signed minimum itself is deliberately excluded because its absolute value is unrepresentable. Unsigned negative spellings convert modulo the type width, rather than retaining a negative magnitude.

Minyar: The listed mathematical values fit Integer. Explicit Integer constants and a new loop may preserve their gcd values, but not C++ widths, unsigned casts, common types or the std::gcd implementation. No signed-minimum UB case is made into a Minyar success expectation.

Oracle source lines: [123]; complete helper spans: [[55, 70], [87, 126]]; related frozen coverage: number-contract, division-model, checked-abs.

### L5 — limit Cartesian table std::uint8_t

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L235–235](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L235-L235) — **adapt_pending**; phase: runtime_only_if_assert_enabled. 

Expected from source: Each ordered pair in the 27-entry table must equal the independent basic_gcd helper. Duplicate entries remain present; design is 27×27=729 comparisons for this invocation. Signed minimum itself is deliberately excluded because its absolute value is unrepresentable. Unsigned negative spellings convert modulo the type width, rather than retaining a negative magnitude.

Minyar: The listed mathematical values fit Integer. Explicit Integer constants and a new loop may preserve their gcd values, but not C++ widths, unsigned casts, common types or the std::gcd implementation. No signed-minimum UB case is made into a Minyar success expectation.

Oracle source lines: [123]; complete helper spans: [[55, 70], [87, 126]]; related frozen coverage: number-contract, division-model, checked-abs.

### L6 — limit Cartesian table std::uint16_t

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L236–236](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L236-L236) — **adapt_pending**; phase: runtime_only_if_assert_enabled. 

Expected from source: Each ordered pair in the 27-entry table must equal the independent basic_gcd helper. Duplicate entries remain present; design is 27×27=729 comparisons for this invocation. Signed minimum itself is deliberately excluded because its absolute value is unrepresentable. Unsigned negative spellings convert modulo the type width, rather than retaining a negative magnitude.

Minyar: The listed mathematical values fit Integer. Explicit Integer constants and a new loop may preserve their gcd values, but not C++ widths, unsigned casts, common types or the std::gcd implementation. No signed-minimum UB case is made into a Minyar success expectation.

Oracle source lines: [123]; complete helper spans: [[55, 70], [87, 126]]; related frozen coverage: number-contract, division-model, checked-abs.

### L7 — limit Cartesian table std::uint32_t

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L237–237](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L237-L237) — **adapt_pending**; phase: runtime_only_if_assert_enabled. 

Expected from source: Each ordered pair in the 27-entry table must equal the independent basic_gcd helper. Duplicate entries remain present; design is 27×27=729 comparisons for this invocation. Signed minimum itself is deliberately excluded because its absolute value is unrepresentable. Unsigned negative spellings convert modulo the type width, rather than retaining a negative magnitude.

Minyar: The listed mathematical values fit Integer. Explicit Integer constants and a new loop may preserve their gcd values, but not C++ widths, unsigned casts, common types or the std::gcd implementation. No signed-minimum UB case is made into a Minyar success expectation.

Oracle source lines: [123]; complete helper spans: [[55, 70], [87, 126]]; related frozen coverage: number-contract, division-model, checked-abs.

### L8 — limit Cartesian table std::uint64_t

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L238–238](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L238-L238) — **incompatible_as_written**; phase: runtime_only_if_assert_enabled. 

Expected from source: Each ordered pair in the 27-entry table must equal the independent basic_gcd helper. Duplicate entries remain present; design is 27×27=729 comparisons for this invocation. Signed minimum itself is deliberately excluded because its absolute value is unrepresentable. Unsigned negative spellings convert modulo the type width, rather than retaining a negative magnitude.

Minyar: uint64 maximum and converted negative values exceed Minyar Integer; no lossless whole-domain projection. No signed-minimum UB case is made into a Minyar success expectation.

Oracle source lines: [123]; complete helper spans: [[55, 70], [87, 126]]; related frozen coverage: number-contract, division-model, checked-abs.

### W1 — LWG2837 widened signed magnitude

[libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp L215–220](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp#L215-L220) — **adapt_pending**; phase: runtime. 

Expected from source: gcd(int64(1234), INT32_MIN) yields 2, and result type is int64_t.

Minyar: Explicit Integer 1234 and -2147483648 preserve result 2 in an original Euclidean loop. This is within signed 64-bit range and does not validate C++ common_type or a narrower-type abs implementation.

Oracle source lines: [218, 219]; complete helper spans: []; related frozen coverage: number-contract, division-model, checked-abs.

### M1 — runtime reference selection at L35

[libcxx/test/std/algorithms/alg.sorting/alg.min.max/minmax.pass.cpp L35–35](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/algorithms/alg.sorting/alg.min.max/minmax.pass.cpp#L35-L35) — **incompatible_as_written**; phase: runtime. 

Expected from source: In block x=0, y=0, returned first aliases x and second aliases y. Both pointer-address assertions must succeed. Equal values in M1/M2 specifically select first argument as minimum and second as maximum.

Minyar: Minyar min/max return scalar values; Integer bindings cannot expose C++ address/reference identity. 0/1 value checks alone would erase the equal-value tie discriminator. P2 deliberately tests scalar snapshots under List mutation, not reference parity.

Oracle source lines: [26, 27]; complete helper spans: [[21, 28]]; related frozen coverage: finite-extrema, list-alias.

### M2 — runtime reference selection at L36

[libcxx/test/std/algorithms/alg.sorting/alg.min.max/minmax.pass.cpp L36–36](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/algorithms/alg.sorting/alg.min.max/minmax.pass.cpp#L36-L36) — **incompatible_as_written**; phase: runtime. 

Expected from source: In block x=0, y=0, returned first aliases y and second aliases x. Both pointer-address assertions must succeed. Equal values in M1/M2 specifically select first argument as minimum and second as maximum.

Minyar: Minyar min/max return scalar values; Integer bindings cannot expose C++ address/reference identity. 0/1 value checks alone would erase the equal-value tie discriminator. P2 deliberately tests scalar snapshots under List mutation, not reference parity.

Oracle source lines: [26, 27]; complete helper spans: [[21, 28]]; related frozen coverage: finite-extrema, list-alias.

### M3 — runtime reference selection at L41

[libcxx/test/std/algorithms/alg.sorting/alg.min.max/minmax.pass.cpp L41–41](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/algorithms/alg.sorting/alg.min.max/minmax.pass.cpp#L41-L41) — **incompatible_as_written**; phase: runtime. 

Expected from source: In block x=0, y=1, returned first aliases x and second aliases y. Both pointer-address assertions must succeed. Equal values in M1/M2 specifically select first argument as minimum and second as maximum.

Minyar: Minyar min/max return scalar values; Integer bindings cannot expose C++ address/reference identity. 0/1 value checks alone would erase the equal-value tie discriminator. P2 deliberately tests scalar snapshots under List mutation, not reference parity.

Oracle source lines: [26, 27]; complete helper spans: [[21, 28]]; related frozen coverage: finite-extrema, list-alias.

### M4 — runtime reference selection at L42

[libcxx/test/std/algorithms/alg.sorting/alg.min.max/minmax.pass.cpp L42–42](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/algorithms/alg.sorting/alg.min.max/minmax.pass.cpp#L42-L42) — **incompatible_as_written**; phase: runtime. 

Expected from source: In block x=0, y=1, returned first aliases x and second aliases y. Both pointer-address assertions must succeed. Equal values in M1/M2 specifically select first argument as minimum and second as maximum.

Minyar: Minyar min/max return scalar values; Integer bindings cannot expose C++ address/reference identity. 0/1 value checks alone would erase the equal-value tie discriminator. P2 deliberately tests scalar snapshots under List mutation, not reference parity.

Oracle source lines: [26, 27]; complete helper spans: [[21, 28]]; related frozen coverage: finite-extrema, list-alias.

### M5 — runtime reference selection at L47

[libcxx/test/std/algorithms/alg.sorting/alg.min.max/minmax.pass.cpp L47–47](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/algorithms/alg.sorting/alg.min.max/minmax.pass.cpp#L47-L47) — **incompatible_as_written**; phase: runtime. 

Expected from source: In block x=1, y=0, returned first aliases y and second aliases x. Both pointer-address assertions must succeed. Equal values in M1/M2 specifically select first argument as minimum and second as maximum.

Minyar: Minyar min/max return scalar values; Integer bindings cannot expose C++ address/reference identity. 0/1 value checks alone would erase the equal-value tie discriminator. P2 deliberately tests scalar snapshots under List mutation, not reference parity.

Oracle source lines: [26, 27]; complete helper spans: [[21, 28]]; related frozen coverage: finite-extrema, list-alias.

### M6 — runtime reference selection at L48

[libcxx/test/std/algorithms/alg.sorting/alg.min.max/minmax.pass.cpp L48–48](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/algorithms/alg.sorting/alg.min.max/minmax.pass.cpp#L48-L48) — **incompatible_as_written**; phase: runtime. 

Expected from source: In block x=1, y=0, returned first aliases y and second aliases x. Both pointer-address assertions must succeed. Equal values in M1/M2 specifically select first argument as minimum and second as maximum.

Minyar: Minyar min/max return scalar values; Integer bindings cannot expose C++ address/reference identity. 0/1 value checks alone would erase the equal-value tie discriminator. P2 deliberately tests scalar snapshots under List mutation, not reference parity.

Oracle source lines: [26, 27]; complete helper spans: [[21, 28]]; related frozen coverage: finite-extrema, list-alias.

### M7 — C++14 constexpr value pair std::minmax(x,y)

[libcxx/test/std/algorithms/alg.sorting/alg.min.max/minmax.pass.cpp L56–58](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/algorithms/alg.sorting/alg.min.max/minmax.pass.cpp#L56-L58) — **adapt_pending**; phase: constexpr_only. 

Expected from source: With constexpr static x=1,y=0, p.first equals 0 and p.second equals 1 at compile time. This branch checks values, not addresses.

Minyar: Ordinary Integer min(1,0)/max(1,0), and reversed order, preserve 0/1 at runtime. No Minyar constexpr declaration or standard-library pair API is promised.

Oracle source lines: [57, 58]; complete helper spans: [[54, 55]]; related frozen coverage: finite-extrema.

### M8 — C++14 constexpr value pair std::minmax(y,x)

[libcxx/test/std/algorithms/alg.sorting/alg.min.max/minmax.pass.cpp L59–61](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/std/algorithms/alg.sorting/alg.min.max/minmax.pass.cpp#L59-L61) — **adapt_pending**; phase: constexpr_only. 

Expected from source: With constexpr static x=1,y=0, p.first equals 0 and p.second equals 1 at compile time. This branch checks values, not addresses.

Minyar: Ordinary Integer min(1,0)/max(1,0), and reversed order, preserve 0/1 at runtime. No Minyar constexpr declaration or standard-library pair API is promised.

Oracle source lines: [60, 61]; complete helper spans: [[54, 55]]; related frozen coverage: finite-extrema.

### A0 — length/capacity conjunction guard

[test/ken/array.go L59–63](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/array.go#L59-L63) — **incompatible_as_written**; phase: runtime. 

Expected from source: make([]int,10,100) has length10 and capacity100. Exact guard is len!=10 && cap!=100: it panics only if BOTH are wrong, so a silent pass alone does not independently assert both properties.

Minyar: Minyar List exposes length, not Go capacity or zero-initialized make/reslicing. Do not strengthen the peer guard while claiming its oracle is unchanged.

Oracle source lines: [60]; complete helper spans: [[58, 76]]; related frozen coverage: list-alias.

### A1 — after [0:100] initialization and [0:10]

[test/ken/array.go L69–69](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/array.go#L69-L69) — **adapt_pending**; phase: runtime. 

Expected from source: Helper res expects sum 45, from half-open original indices [0,10) via (hb-lb)*(hb+lb-1)/2. Failure prints operands/sum and panics. Mutation in setpd/setpf is visible to callers.

Minyar: An initialized List<Integer>, indexed helper mutation and an explicit range-sum loop can preserve this arithmetic result. No public List.slice, capacity extension, fixed-array pointer, Go slice-header/value ABI or implicit zero initialization is mapped. A3 needs explicit root offset35; replaying slice syntax against Minyar would be invalid.

Oracle source lines: [47]; complete helper spans: [[11, 55]]; related frozen coverage: list-alias, list-bounds, existing-row-projection.

### A2 — after reslice [5:25] from length10 but capacity100

[test/ken/array.go L72–72](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/array.go#L72-L72) — **adapt_pending**; phase: runtime. 

Expected from source: Helper res expects sum 290, from half-open original indices [5,25) via (hb-lb)*(hb+lb-1)/2. Failure prints operands/sum and panics. Mutation in setpd/setpf is visible to callers.

Minyar: An initialized List<Integer>, indexed helper mutation and an explicit range-sum loop can preserve this arithmetic result. No public List.slice, capacity extension, fixed-array pointer, Go slice-header/value ABI or implicit zero initialization is mapped. A3 needs explicit root offset35; replaying slice syntax against Minyar would be invalid.

Oracle source lines: [47]; complete helper spans: [[11, 55]]; related frozen coverage: list-alias, list-bounds, existing-row-projection.

### A3 — after nested [30:95] from root offset5

[test/ken/array.go L75–75](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/array.go#L75-L75) — **adapt_pending**; phase: runtime. 

Expected from source: Helper res expects sum 4355, from half-open original indices [35,100) via (hb-lb)*(hb+lb-1)/2. Failure prints operands/sum and panics. Mutation in setpd/setpf is visible to callers.

Minyar: An initialized List<Integer>, indexed helper mutation and an explicit range-sum loop can preserve this arithmetic result. No public List.slice, capacity extension, fixed-array pointer, Go slice-header/value ABI or implicit zero initialization is mapped. A3 needs explicit root offset35; replaying slice syntax against Minyar would be invalid.

Oracle source lines: [47]; complete helper spans: [[11, 55]]; related frozen coverage: list-alias, list-bounds, existing-row-projection.

### A4 — pointer to fixed [20]int

[test/ken/array.go L83–83](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/array.go#L83-L83) — **adapt_pending**; phase: runtime. 

Expected from source: Helper res expects sum 190, from half-open original indices [0,20) via (hb-lb)*(hb+lb-1)/2. Failure prints operands/sum and panics. Mutation in setpd/setpf is visible to callers.

Minyar: An initialized List<Integer>, indexed helper mutation and an explicit range-sum loop can preserve this arithmetic result. No public List.slice, capacity extension, fixed-array pointer, Go slice-header/value ABI or implicit zero initialization is mapped. A3 needs explicit root offset35; replaying slice syntax against Minyar would be invalid.

Oracle source lines: [47]; complete helper spans: [[11, 55]]; related frozen coverage: list-alias, list-bounds, existing-row-projection.

### A5 — new fixed [40]int exposed as a slice

[test/ken/array.go L90–90](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/array.go#L90-L90) — **adapt_pending**; phase: runtime. 

Expected from source: Helper res expects sum 780, from half-open original indices [0,40) via (hb-lb)*(hb+lb-1)/2. Failure prints operands/sum and panics. Mutation in setpd/setpf is visible to callers.

Minyar: An initialized List<Integer>, indexed helper mutation and an explicit range-sum loop can preserve this arithmetic result. No public List.slice, capacity extension, fixed-array pointer, Go slice-header/value ABI or implicit zero initialization is mapped. A3 needs explicit root offset35; replaying slice syntax against Minyar would be invalid.

Oracle source lines: [47]; complete helper spans: [[11, 55]]; related frozen coverage: list-alias, list-bounds, existing-row-projection.

### A6 — slice [5:30] of the initialized 40-element array

[test/ken/array.go L93–93](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/array.go#L93-L93) — **adapt_pending**; phase: runtime. 

Expected from source: Helper res expects sum 425, from half-open original indices [5,30) via (hb-lb)*(hb+lb-1)/2. Failure prints operands/sum and panics. Mutation in setpd/setpf is visible to callers.

Minyar: An initialized List<Integer>, indexed helper mutation and an explicit range-sum loop can preserve this arithmetic result. No public List.slice, capacity extension, fixed-array pointer, Go slice-header/value ABI or implicit zero initialization is mapped. A3 needs explicit root offset35; replaying slice syntax against Minyar would be invalid.

Oracle source lines: [47]; complete helper spans: [[11, 55]]; related frozen coverage: list-alias, list-bounds, existing-row-projection.

### A7 — stack fixed [80]int exposed as a slice

[test/ken/array.go L101–101](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/array.go#L101-L101) — **adapt_pending**; phase: runtime. 

Expected from source: Helper res expects sum 3160, from half-open original indices [0,80) via (hb-lb)*(hb+lb-1)/2. Failure prints operands/sum and panics. Mutation in setpd/setpf is visible to callers.

Minyar: An initialized List<Integer>, indexed helper mutation and an explicit range-sum loop can preserve this arithmetic result. No public List.slice, capacity extension, fixed-array pointer, Go slice-header/value ABI or implicit zero initialization is mapped. A3 needs explicit root offset35; replaying slice syntax against Minyar would be invalid.

Oracle source lines: [47]; complete helper spans: [[11, 55]]; related frozen coverage: list-alias, list-bounds, existing-row-projection.

### A8 — dormant index-at-length fault size100

[test/ken/array.go L105–115](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/array.go#L105-L115) — **adapt_pending**; phase: dormant_not_called. 

Expected from source: If called: good and should fault observations precede an index-at-length write (100); bounds failure should prevent bad. The main call is commented out, so these bodies do NOT execute in this selected //run test.

Minyar: Current List index-at-length failure is related and already has source fixtures for lengths0/2. An original length80/100 setup could preserve only the invalid-index relation; it would add little beyond those controls. No new redundant regression proposed.

Oracle source lines: [113]; complete helper spans: []; related frozen coverage: list-bounds.

### A9 — dormant index-at-length fault size80

[test/ken/array.go L118–129](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/array.go#L118-L129) — **adapt_pending**; phase: dormant_not_called. 

Expected from source: If called: good and should fault observations precede an index-at-length write (80); bounds failure should prevent bad. The main call is commented out, so these bodies do NOT execute in this selected //run test.

Minyar: Current List index-at-length failure is related and already has source fixtures for lengths0/2. An original length80/100 setup could preserve only the invalid-index relation; it would add little beyond those controls. No new redundant regression proposed.

Oracle source lines: [127]; complete helper spans: []; related frozen coverage: list-bounds.

### C1 — constant shift tuple (0, 0, 0)

[test/ken/shift.go L48–48, L101–101](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L48-L101) — **adopt_pending**; phase: upstream_constant_expression_in_runtime_call. 

Expected from source: Expected 1234 from explicit ians answer cell. A mismatch prints a diagnostic; helper does not panic or change exit status. The //run harness compares merged stdout/stderr with expected output, so a diagnostic is observable failure under its empty-output expectation.

Minyar: These signed small values and counts0/5 fit the existing Integer shift contract. Minyar uses x = x << count rather than unsupported <<= syntax. No compile-time evaluator equivalence is inferred.

Oracle source lines: [18]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries.

### C2 — constant shift tuple (0, 0, 1)

[test/ken/shift.go L49–49, L102–102](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L49-L102) — **adopt_pending**; phase: upstream_constant_expression_in_runtime_call. 

Expected from source: Expected 1234 from explicit ians answer cell. A mismatch prints a diagnostic; helper does not panic or change exit status. The //run harness compares merged stdout/stderr with expected output, so a diagnostic is observable failure under its empty-output expectation.

Minyar: These signed small values and counts0/5 fit the existing Integer shift contract. Minyar uses x = x << count rather than unsupported <<= syntax. No compile-time evaluator equivalence is inferred.

Oracle source lines: [18]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries.

### C3 — constant shift tuple (0, 1, 0)

[test/ken/shift.go L50–50, L103–103](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L50-L103) — **adopt_pending**; phase: upstream_constant_expression_in_runtime_call. 

Expected from source: Expected 39488 from explicit ians answer cell. A mismatch prints a diagnostic; helper does not panic or change exit status. The //run harness compares merged stdout/stderr with expected output, so a diagnostic is observable failure under its empty-output expectation.

Minyar: These signed small values and counts0/5 fit the existing Integer shift contract. Minyar uses x = x << count rather than unsupported <<= syntax. No compile-time evaluator equivalence is inferred.

Oracle source lines: [18]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries.

### C4 — constant shift tuple (0, 1, 1)

[test/ken/shift.go L51–51, L104–104](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L51-L104) — **adopt_pending**; phase: upstream_constant_expression_in_runtime_call. 

Expected from source: Expected 38 from explicit ians answer cell. A mismatch prints a diagnostic; helper does not panic or change exit status. The //run harness compares merged stdout/stderr with expected output, so a diagnostic is observable failure under its empty-output expectation.

Minyar: These signed small values and counts0/5 fit the existing Integer shift contract. Minyar uses x = x << count rather than unsupported <<= syntax. No compile-time evaluator equivalence is inferred.

Oracle source lines: [18]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries.

### C5 — constant shift tuple (1, 0, 0)

[test/ken/shift.go L53–53, L108–108](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L53-L108) — **adopt_pending**; phase: upstream_constant_expression_in_runtime_call. 

Expected from source: Expected -1234 from explicit ians answer cell. A mismatch prints a diagnostic; helper does not panic or change exit status. The //run harness compares merged stdout/stderr with expected output, so a diagnostic is observable failure under its empty-output expectation.

Minyar: These signed small values and counts0/5 fit the existing Integer shift contract. Minyar uses x = x << count rather than unsupported <<= syntax. No compile-time evaluator equivalence is inferred.

Oracle source lines: [18]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries.

### C6 — constant shift tuple (1, 0, 1)

[test/ken/shift.go L54–54, L109–109](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L54-L109) — **adopt_pending**; phase: upstream_constant_expression_in_runtime_call. 

Expected from source: Expected -1234 from explicit ians answer cell. A mismatch prints a diagnostic; helper does not panic or change exit status. The //run harness compares merged stdout/stderr with expected output, so a diagnostic is observable failure under its empty-output expectation.

Minyar: These signed small values and counts0/5 fit the existing Integer shift contract. Minyar uses x = x << count rather than unsupported <<= syntax. No compile-time evaluator equivalence is inferred.

Oracle source lines: [18]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries.

### C7 — constant shift tuple (1, 1, 0)

[test/ken/shift.go L55–55, L110–110](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L55-L110) — **adopt_pending**; phase: upstream_constant_expression_in_runtime_call. 

Expected from source: Expected -39488 from explicit ians answer cell. A mismatch prints a diagnostic; helper does not panic or change exit status. The //run harness compares merged stdout/stderr with expected output, so a diagnostic is observable failure under its empty-output expectation.

Minyar: These signed small values and counts0/5 fit the existing Integer shift contract. Minyar uses x = x << count rather than unsupported <<= syntax. No compile-time evaluator equivalence is inferred.

Oracle source lines: [18]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries.

### C8 — constant shift tuple (1, 1, 1)

[test/ken/shift.go L56–56, L111–111](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L56-L111) — **adopt_pending**; phase: upstream_constant_expression_in_runtime_call. 

Expected from source: Expected -39 from explicit ians answer cell. A mismatch prints a diagnostic; helper does not panic or change exit status. The //run harness compares merged stdout/stderr with expected output, so a diagnostic is observable failure under its empty-output expectation.

Minyar: These signed small values and counts0/5 fit the existing Integer shift contract. Minyar uses x = x << count rather than unsupported <<= syntax. No compile-time evaluator equivalence is inferred.

Oracle source lines: [18]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries.

### C9 — constant shift tuple (2, 0, 0)

[test/ken/shift.go L58–58, L115–115](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L58-L115) — **adapt_pending**; phase: upstream_constant_expression_in_runtime_call. 

Expected from source: Expected 5678 from explicit uans answer cell. A mismatch prints a diagnostic; helper does not panic or change exit status. The //run harness compares merged stdout/stderr with expected output, so a diagnostic is observable failure under its empty-output expectation.

Minyar: 5678 and the results fit Integer, so only positive numeric values transfer; Go uint and unsigned shift semantics are omitted. Minyar uses x = x << count rather than unsupported <<= syntax. No compile-time evaluator equivalence is inferred.

Oracle source lines: [32]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries.

### C10 — constant shift tuple (2, 0, 1)

[test/ken/shift.go L59–59, L116–116](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L59-L116) — **adapt_pending**; phase: upstream_constant_expression_in_runtime_call. 

Expected from source: Expected 5678 from explicit uans answer cell. A mismatch prints a diagnostic; helper does not panic or change exit status. The //run harness compares merged stdout/stderr with expected output, so a diagnostic is observable failure under its empty-output expectation.

Minyar: 5678 and the results fit Integer, so only positive numeric values transfer; Go uint and unsigned shift semantics are omitted. Minyar uses x = x << count rather than unsupported <<= syntax. No compile-time evaluator equivalence is inferred.

Oracle source lines: [32]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries.

### C11 — constant shift tuple (2, 1, 0)

[test/ken/shift.go L60–60, L117–117](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L60-L117) — **adapt_pending**; phase: upstream_constant_expression_in_runtime_call. 

Expected from source: Expected 181696 from explicit uans answer cell. A mismatch prints a diagnostic; helper does not panic or change exit status. The //run harness compares merged stdout/stderr with expected output, so a diagnostic is observable failure under its empty-output expectation.

Minyar: 5678 and the results fit Integer, so only positive numeric values transfer; Go uint and unsigned shift semantics are omitted. Minyar uses x = x << count rather than unsupported <<= syntax. No compile-time evaluator equivalence is inferred.

Oracle source lines: [32]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries.

### C12 — constant shift tuple (2, 1, 1)

[test/ken/shift.go L61–61, L118–118](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L61-L118) — **adapt_pending**; phase: upstream_constant_expression_in_runtime_call. 

Expected from source: Expected 177 from explicit uans answer cell. A mismatch prints a diagnostic; helper does not panic or change exit status. The //run harness compares merged stdout/stderr with expected output, so a diagnostic is observable failure under its empty-output expectation.

Minyar: 5678 and the results fit Integer, so only positive numeric values transfer; Go uint and unsigned shift semantics are omitted. Minyar uses x = x << count rather than unsupported <<= syntax. No compile-time evaluator equivalence is inferred.

Oracle source lines: [32]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries.

### D1 — dynamic shift tuple (0, 0, 0)

[test/ken/shift.go L68–92, L101–101](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L68-L101) — **adopt_pending**; phase: runtime_variable. 

Expected from source: Fresh selected operand 1234, count0, operator <<, expected 1234 from ians. Nonselected i/u variables also shift each iteration, but only the selected type branch is checked. Mismatch prints without panic; output harness supplies failure detection.

Minyar: Count0/5 and the explicit value are representable by existing Integer shifts; rewrite switch/compound shifts as ordinary branches/assignments. No width-dependent overflow is needed for these values.

Oracle source lines: [18]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries, shift-failures.

### D2 — dynamic shift tuple (0, 0, 1)

[test/ken/shift.go L68–92, L102–102](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L68-L102) — **adopt_pending**; phase: runtime_variable. 

Expected from source: Fresh selected operand 1234, count0, operator >>, expected 1234 from ians. Nonselected i/u variables also shift each iteration, but only the selected type branch is checked. Mismatch prints without panic; output harness supplies failure detection.

Minyar: Count0/5 and the explicit value are representable by existing Integer shifts; rewrite switch/compound shifts as ordinary branches/assignments. No width-dependent overflow is needed for these values.

Oracle source lines: [18]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries, shift-failures.

### D3 — dynamic shift tuple (0, 1, 0)

[test/ken/shift.go L68–92, L103–103](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L68-L103) — **adopt_pending**; phase: runtime_variable. 

Expected from source: Fresh selected operand 1234, count5, operator <<, expected 39488 from ians. Nonselected i/u variables also shift each iteration, but only the selected type branch is checked. Mismatch prints without panic; output harness supplies failure detection.

Minyar: Count0/5 and the explicit value are representable by existing Integer shifts; rewrite switch/compound shifts as ordinary branches/assignments. No width-dependent overflow is needed for these values.

Oracle source lines: [18]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries, shift-failures.

### D4 — dynamic shift tuple (0, 1, 1)

[test/ken/shift.go L68–92, L104–104](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L68-L104) — **adopt_pending**; phase: runtime_variable. 

Expected from source: Fresh selected operand 1234, count5, operator >>, expected 38 from ians. Nonselected i/u variables also shift each iteration, but only the selected type branch is checked. Mismatch prints without panic; output harness supplies failure detection.

Minyar: Count0/5 and the explicit value are representable by existing Integer shifts; rewrite switch/compound shifts as ordinary branches/assignments. No width-dependent overflow is needed for these values.

Oracle source lines: [18]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries, shift-failures.

### D5 — dynamic shift tuple (0, 2, 0)

[test/ken/shift.go L68–92, L105–105](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L68-L105) — **incompatible_as_written**; phase: runtime_variable. 

Expected from source: Fresh selected operand 1234, count1025, operator <<, expected 0 from ians. Nonselected i/u variables also shift each iteration, but only the selected type branch is checked. Mismatch prints without panic; output harness supplies failure detection.

Minyar: Count1025 stops in Minyar; it must not succeed with Go saturation/sign-extension values or be masked to1.

Oracle source lines: [18]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries, shift-failures.

### D6 — dynamic shift tuple (0, 2, 1)

[test/ken/shift.go L68–92, L106–106](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L68-L106) — **incompatible_as_written**; phase: runtime_variable. 

Expected from source: Fresh selected operand 1234, count1025, operator >>, expected 0 from ians. Nonselected i/u variables also shift each iteration, but only the selected type branch is checked. Mismatch prints without panic; output harness supplies failure detection.

Minyar: Count1025 stops in Minyar; it must not succeed with Go saturation/sign-extension values or be masked to1.

Oracle source lines: [18]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries, shift-failures.

### D7 — dynamic shift tuple (1, 0, 0)

[test/ken/shift.go L68–92, L108–108](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L68-L108) — **adopt_pending**; phase: runtime_variable. 

Expected from source: Fresh selected operand -1234, count0, operator <<, expected -1234 from ians. Nonselected i/u variables also shift each iteration, but only the selected type branch is checked. Mismatch prints without panic; output harness supplies failure detection.

Minyar: Count0/5 and the explicit value are representable by existing Integer shifts; rewrite switch/compound shifts as ordinary branches/assignments. No width-dependent overflow is needed for these values.

Oracle source lines: [18]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries, shift-failures.

### D8 — dynamic shift tuple (1, 0, 1)

[test/ken/shift.go L68–92, L109–109](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L68-L109) — **adopt_pending**; phase: runtime_variable. 

Expected from source: Fresh selected operand -1234, count0, operator >>, expected -1234 from ians. Nonselected i/u variables also shift each iteration, but only the selected type branch is checked. Mismatch prints without panic; output harness supplies failure detection.

Minyar: Count0/5 and the explicit value are representable by existing Integer shifts; rewrite switch/compound shifts as ordinary branches/assignments. No width-dependent overflow is needed for these values.

Oracle source lines: [18]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries, shift-failures.

### D9 — dynamic shift tuple (1, 1, 0)

[test/ken/shift.go L68–92, L110–110](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L68-L110) — **adopt_pending**; phase: runtime_variable. 

Expected from source: Fresh selected operand -1234, count5, operator <<, expected -39488 from ians. Nonselected i/u variables also shift each iteration, but only the selected type branch is checked. Mismatch prints without panic; output harness supplies failure detection.

Minyar: Count0/5 and the explicit value are representable by existing Integer shifts; rewrite switch/compound shifts as ordinary branches/assignments. No width-dependent overflow is needed for these values.

Oracle source lines: [18]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries, shift-failures.

### D10 — dynamic shift tuple (1, 1, 1)

[test/ken/shift.go L68–92, L111–111](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L68-L111) — **adopt_pending**; phase: runtime_variable. 

Expected from source: Fresh selected operand -1234, count5, operator >>, expected -39 from ians. Nonselected i/u variables also shift each iteration, but only the selected type branch is checked. Mismatch prints without panic; output harness supplies failure detection.

Minyar: Count0/5 and the explicit value are representable by existing Integer shifts; rewrite switch/compound shifts as ordinary branches/assignments. No width-dependent overflow is needed for these values.

Oracle source lines: [18]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries, shift-failures.

### D11 — dynamic shift tuple (1, 2, 0)

[test/ken/shift.go L68–92, L112–112](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L68-L112) — **incompatible_as_written**; phase: runtime_variable. 

Expected from source: Fresh selected operand -1234, count1025, operator <<, expected 0 from ians. Nonselected i/u variables also shift each iteration, but only the selected type branch is checked. Mismatch prints without panic; output harness supplies failure detection.

Minyar: Count1025 stops in Minyar; it must not succeed with Go saturation/sign-extension values or be masked to1.

Oracle source lines: [18]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries, shift-failures.

### D12 — dynamic shift tuple (1, 2, 1)

[test/ken/shift.go L68–92, L113–113](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L68-L113) — **incompatible_as_written**; phase: runtime_variable. 

Expected from source: Fresh selected operand -1234, count1025, operator >>, expected -1 from ians. Nonselected i/u variables also shift each iteration, but only the selected type branch is checked. Mismatch prints without panic; output harness supplies failure detection.

Minyar: Count1025 stops in Minyar; it must not succeed with Go saturation/sign-extension values or be masked to1.

Oracle source lines: [18]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries, shift-failures.

### D13 — dynamic shift tuple (2, 0, 0)

[test/ken/shift.go L68–92, L115–115](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L68-L115) — **adapt_pending**; phase: runtime_variable. 

Expected from source: Fresh selected operand 5678, count0, operator <<, expected 5678 from uans. Nonselected i/u variables also shift each iteration, but only the selected type branch is checked. Mismatch prints without panic; output harness supplies failure detection.

Minyar: Count0/5 and the explicit value are representable by existing Integer shifts; rewrite switch/compound shifts as ordinary branches/assignments. Go unsigned width/type remains excluded.

Oracle source lines: [32]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries, shift-failures.

### D14 — dynamic shift tuple (2, 0, 1)

[test/ken/shift.go L68–92, L116–116](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L68-L116) — **adapt_pending**; phase: runtime_variable. 

Expected from source: Fresh selected operand 5678, count0, operator >>, expected 5678 from uans. Nonselected i/u variables also shift each iteration, but only the selected type branch is checked. Mismatch prints without panic; output harness supplies failure detection.

Minyar: Count0/5 and the explicit value are representable by existing Integer shifts; rewrite switch/compound shifts as ordinary branches/assignments. Go unsigned width/type remains excluded.

Oracle source lines: [32]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries, shift-failures.

### D15 — dynamic shift tuple (2, 1, 0)

[test/ken/shift.go L68–92, L117–117](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L68-L117) — **adapt_pending**; phase: runtime_variable. 

Expected from source: Fresh selected operand 5678, count5, operator <<, expected 181696 from uans. Nonselected i/u variables also shift each iteration, but only the selected type branch is checked. Mismatch prints without panic; output harness supplies failure detection.

Minyar: Count0/5 and the explicit value are representable by existing Integer shifts; rewrite switch/compound shifts as ordinary branches/assignments. Go unsigned width/type remains excluded.

Oracle source lines: [32]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries, shift-failures.

### D16 — dynamic shift tuple (2, 1, 1)

[test/ken/shift.go L68–92, L118–118](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L68-L118) — **adapt_pending**; phase: runtime_variable. 

Expected from source: Fresh selected operand 5678, count5, operator >>, expected 177 from uans. Nonselected i/u variables also shift each iteration, but only the selected type branch is checked. Mismatch prints without panic; output harness supplies failure detection.

Minyar: Count0/5 and the explicit value are representable by existing Integer shifts; rewrite switch/compound shifts as ordinary branches/assignments. Go unsigned width/type remains excluded.

Oracle source lines: [32]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries, shift-failures.

### D17 — dynamic shift tuple (2, 2, 0)

[test/ken/shift.go L68–92, L119–119](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L68-L119) — **incompatible_as_written**; phase: runtime_variable. 

Expected from source: Fresh selected operand 5678, count1025, operator <<, expected 0 from uans. Nonselected i/u variables also shift each iteration, but only the selected type branch is checked. Mismatch prints without panic; output harness supplies failure detection.

Minyar: Count1025 stops in Minyar; it must not succeed with Go saturation/sign-extension values or be masked to1.

Oracle source lines: [32]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries, shift-failures.

### D18 — dynamic shift tuple (2, 2, 1)

[test/ken/shift.go L68–92, L120–120](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/test/ken/shift.go#L68-L120) — **incompatible_as_written**; phase: runtime_variable. 

Expected from source: Fresh selected operand 5678, count1025, operator >>, expected 0 from uans. Nonselected i/u variables also shift each iteration, but only the selected type branch is checked. Mismatch prints without panic; output harness supplies failure detection.

Minyar: Count1025 stops in Minyar; it must not succeed with Go saturation/sign-extension values or be masked to1.

Oracle source lines: [32]; complete helper spans: [[15, 36], [95, 121]]; related frozen coverage: shift-model, shift-boundaries, shift-failures.

## Helpers, guards and remaining support extents

Machine-indexed lexical sites: **53**, by kind `{"assert": 23, "dormant_bounds_fault_site": 2, "failure_predicate": 2, "print_mismatch_predicate": 2, "static_assert": 24}`. There are18 gcd test0 subcall source forms, two selected C++ phase guard sites and zero selected backend skips. No dynamic assertion total or configured backend execution is inferred.

| In-file helper/driver | Complete read spans | Meaning |
| --- | --- | --- |
| libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp::test0 | [[44, 53]] | Converts operands, two result-type static assertions, value assertion, returns true; assertion-disabled builds can remove value comparison. |
| libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp::basic_gcd_ and basic_gcd | [[55, 70]] | Recursive n==0 base else m%n; signed negatives normalized except minimum, then convert to unsigned. Selected signed-limit inputs avoid minimum. Unsigned converted negatives remain large positive values. |
| libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp::do_fuzzy_tests | [[72, 85]] | Seed1938, distribution0..type max, one-byte distribution uses int, 10000 model comparisons; no saved stream/answers or actual executions. |
| libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp::do_limit_tests | [[87, 126]] | 27 ordered entries, duplicates kept; all729 ordered pairs compared to Euclidean helper; magnitude representability precondition explicitly documented. |
| libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp::do_test | [[128, 169]] | 12 table rows,18 call forms each, signed/type-order/unsigned/mixed forms; accumulate &= evaluates each test0 call, does not short-circuit. Dummy int parameter unused. |
| libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp::main | [[171, 241]] | 17 paired constexpr/runtime drivers; widened result example; eight fuzzy/eight limit calls; returns0. Runtime drivers wrapped in assert can disappear with NDEBUG; direct fuzzy/limit loops remain but their comparison assert can disappear. |
| libcxx/test/std/algorithms/alg.sorting/alg.min.max/minmax.pass.cpp::test | [[21, 28]] | Two reference-address assertions; equal scalar values cannot discriminate alias selection. |
| libcxx/test/std/algorithms/alg.sorting/alg.min.max/minmax.pass.cpp::main | [[30, 66]] | Six runtime calls, four constexpr value assertions under TEST_STD_VER>=14, returns0; no mutation/lifetime assertion. |
| test/ken/array.go::setpd/sumpd/setpf/sumpf/res | [[11, 55]] | Each helper complete: shared backing stores set index values, sums selected lengths; res compares against arithmetic progression formula and prints/panics on mismatch. Debug print comments inactive. |
| test/ken/array.go::scenario bodies and main | [[58, 138]] | All four active functions and two dormant fault functions fully read; main calls only active functions. Capacity conjunction not strengthened; nested slice root offsets tracked. |
| test/ken/shift.go::testi/index/testu | [[15, 36]] | Exact index ((t1*3)+t2)*2+t3; scalar mismatch prints only; no panic/fail/exit. |
| test/ken/shift.go::main/init | [[38, 121]] | 12 constant calls;18 dynamic selected cases. Nonselected variables also shifted. Initialization writes18 exact answer cells before main; semicolons/formatting retained. |

| Imported support | Exact reviewed spans | Contract and unreviewed remainder |
| --- | --- | --- |
| [libcxx/test/support/test_macros.h](https://github.com/llvm/llvm-project/blob/b708aea0bc7127adf4ec643660699c8bcdde1273/libcxx/test/support/test_macros.h) | [[88, 105]] | TEST_STD_VER derived from __cplusplus unless already defined; C++14 minmax branch guard. No cassert/NDEBUG configuration or library ABI inspected. Unreviewed complement: [[1, 87], [106, 551]]. |
| [src/cmd/internal/testdir/testdir_test.go](https://github.com/golang/go/blob/56ebf80e57db9f61981fc0636fc6419dc6f68eda/src/cmd/internal/testdir/testdir_test.go) | [[608, 615], [657, 668], [1016, 1054], [1133, 1157]] | Command stdout/stderr share one buffer; //run verifies exit and output; missing optional .out means expected empty output, CRLF normalized. Timeout/build mechanisms and transitive tools remain outside review. Unreviewed complement: [[1, 607], [616, 656], [669, 1015], [1055, 1132], [1158, 1997]]. |

Platform cassert expansion, actual NDEBUG configuration, <algorithm>/<numeric> implementations, random distribution internals, integral ABI widths, transitive Go tool invocation and other harness sections are outside this semantic audit. Full-byte support retrieval is not whole-support review. The complete selected nonassertion extents remain explicit in JSON.

## Original regressions — proposals only

### P1 — Signed Euclidean remainder composition with explicit boundary answers

Inspected division-model/checked-abs sources cover primitives and traps but not repeated Euclidean remainder with explicit large signed operands and fixed answers. No gcd proposal occurs in retained round2–8 proposal lists. This is a selective gap, not repository-wide absence or exhaustive novelty.

Independent expectation: gcd(0,0)=0; zero with ±17 gives17; gcd(±25,±30)=5; consecutive maximum/maximum-1 are coprime; 9223372036854775806 is twice4611686018427387903; -2147483648 and1234 share exactly factor2. All abs inputs are representable; divisor-zero is avoided by the loop guard.

```minyar
function euclid(left: Integer, right: Integer): Integer {
    let a = abs(left)
    let b = abs(right)
    while b != 0 {
        let next = a % b
        a = b
        b = next
    }
    return a
}
print(euclid(0, 0))
print(euclid(0, -17))
print(euclid(-17, 0))
print(euclid(25, 30))
print(euclid(-25, 30))
print(euclid(25, -30))
print(euclid(-25, -30))
print(euclid(9223372036854775807, 9223372036854775806))
print(euclid(9223372036854775806, 4611686018427387903))
print(euclid(1234, -2147483648))
print(euclid(-2147483648, 1234))
```

Exact expected stdout:

```text
0
17
17
5
5
5
5
1
4611686018427387903
2
2
```

Excluded peer contracts: std::gcd API, unsigned arithmetic, templates/common_type, constexpr, signed minimum absolute-value success.

Core owner may first add exact-output regression, preserve any red, then choose its existing source-frozen optimization/profile checks. No defect, speed gain or peer API parity inferred. Status: original_proposal; unimplemented_uncompiled_unexecuted.

### P2 — Integer extrema return scalar snapshots across shared List mutation

Inspected conformance checks one small min and one Float max; row projection retains managed rows. No cited fixture returns both Integer extrema then mutates both source slots through an alias and checks the saved scalars across equal/reversed/signed-endpoint inputs. Prior swap/row/wide-record proposals do not perform this extrema composition.

Independent expectation: Equal0 yields0/0; both orders of0/1 yield0/1; either order of signed endpoints yields minimum/maximum. Returned Integer fields retain captured numbers while the shared source and its alias become100/200. Fresh Limits records are explicit; no record equality is used.

```minyar
record Limits { low: Integer; high: Integer }
function limits(values: List<Integer>): Limits {
    return Limits { low: min(values[0], values[1]); high: max(values[0], values[1]) }
}
function inspect(first: Integer, second: Integer) {
    let values = [first, second]
    let alias = values
    let saved = limits(values)
    alias[0] = 100
    alias[1] = 200
    print(saved.low)
    print(saved.high)
    print(values[0])
    print(values[1])
}
inspect(0, 0)
inspect(0, 1)
inspect(1, 0)
inspect(-9223372036854775808, 9223372036854775807)
inspect(9223372036854775807, -9223372036854775808)
```

Exact expected stdout:

```text
0
0
100
200
0
1
100
200
0
1
100
200
-9223372036854775808
9223372036854775807
100
200
-9223372036854775808
9223372036854775807
100
200
```

Excluded peer contracts: C++ pair/reference identity, scalar addresses, constexpr, Float NaN/signed-zero tie policy, implicit copies.

Core owner may add exact-output red-first fixture and apply its existing final-source checks. Values do not prove address identity, unique ownership, allocation elimination or speed. Status: original_proposal; unimplemented_uncompiled_unexecuted.

## Prior evidence and bounded handoff

Saved original runtime projections remain separate: run-l5_218bk has eight methods and48 generated executions with24 final O0/24 O2 link flags; run-1a2ft1yr separately has one wide-record method and6 executions with3 O0/3 O2. These pre-existing saved results were read, not rerun. A [concurrent source observation](../../evidence/peer-readonly/values-round9/concurrent-runtime-source-observation.json) separately records two newly added round8-inspired methods; method implementation alone is not execution evidence. No full nine-method final-source matrix or literal peer ports are claimed. The historical sanitizer optimization correction remains authoritative. [Saved documentary evidence](../../evidence/peer-readonly/values-round9/prior-runtime-document-checks.json).

Prior selected rounds2–8 derive **552 groups / 26 complete files**. This round gives the selected-report union **646 groups / 30 complete files**. The central ledger is a separate earlier manifest and was inspected for overlap, not rewritten. Quantities remain heterogeneous source-review selections, not global/all-peer coverage, ports or passing tests.

**55 adopt/adapt groups** and P1/P2 await root/core executable decisions; **39 incompatible groups** stay excluded. Zero selected lines remain unread. Other peer files, the unselected comparator candidate and exact support complements remain outside credited review. All new failures are retained; restricted Rust/university-allocator/Joisha sources and stopped compiler/native-model/AFL lanes were not retried, bypassed or resumed. Only the two round9 reports and values-round9 evidence tree were authored. [Handoff](../../evidence/peer-readonly/values-round9/handoff.json).

Documentary hashes/spans/counts/attributions are checked by the retained [document checks](../../evidence/peer-readonly/values-round9/document-checks.json); no test or compilation is run by those checks. The [evidence index](../../evidence/peer-readonly/values-round9/evidence-index.json) is machine-derived and excludes itself to avoid recursive hashing.

Documentary final result: **1424 consistent checks**, 0 failed. The retained [initial check](../../evidence/peer-readonly/values-round9/document-checks-initial.json) exposed two documentary extent/accounting errors, corrected above; no executable regression failure is inferred. Concurrent live reference changes are recorded without rebinding frozen coverage:

- research/2026-10-memory/README.md: frozen `6dd77e7c13164b10a35237855605c7646c29e222507774448bdce0031cc86e24`, observed `b6b52ce2abcdf9424c1023eb24687151731be0e4f42e833377ce49f2f81f0ea0`.
- tests/memory-research-peer-projections.py: frozen `c04f0700dd2afed431f86007b2b8b0e23f4e635590c81f23ba09660dcd69fbfa`, observed `817b5949ac6733afc143154a15adab8a6e3527a783543882dcfb1f82f0c9de58`.
