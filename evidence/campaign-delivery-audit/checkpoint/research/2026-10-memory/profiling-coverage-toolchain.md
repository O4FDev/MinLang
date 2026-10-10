# Coverage portability repair and measured scope

The real coverage pipeline initially failed before corpus execution in two
separate infrastructure paths. Both failures and frozen source hashes remain in
`profiling-coverage-run.json` and `profiling-coverage-final.json`.

The first path used an Apple Clang 17 precheck despite an explicitly selected
LLVM 22 compiler. Targetless pre-inlining IR also let opt create ELF-style COMDAT
coverage helpers which Mach-O could not lower. The precheck now honors the
selected compiler, and opt receives the actual selected Clang target triple.
Tests exercise both Mach-O and ELF triples and reject missing/invalid metadata.

The second path linked an Apple Clang 17 prebuilt compiler-runtime IR carrying
vendor stack-probe attributes into LLVM 22. Coverage now compiles the same arena
runtime C source into a disposable object with the selected compiler. It does
not strip stack protection attributes or reuse the shared production runtime.
A regression asserts the selected compiler, arena configuration and fresh-source
input. The real link and self-compilation produce exactly the shared fixed-point
LLVM bytes; an initial stdin smoke invocation only printed compiler help and was
corrected to the compiler's file-input interface before that comparison.

Nine accounting/portability harness tests and the real shared-branch inlining
fixture pass. All four LLVM tool identities are recorded and mismatched major
versions fail before instrumentation. The global Apple toolchain is unchanged.
This run establishes LLVM 22.1.5 on arm64-apple-darwin25; mocked ELF argument
coverage is not an actual Linux backend execution claim.

The complete frozen run passed in 270.4 seconds with no measured source changes.
That wall time is host-dependent correctness evidence, not a clean latency
measurement. It includes all four maintained peer suites in both compiler
instrumentation orders, numeric oracles and the existing seeded fuzz corpus.

| Metric | Covered / denominator | Percentage | Interpretation |
| --- | --- | --- | --- |
| Compiler distinct edges before inlining | 1,937 / 2,245 | 86.28% | IDs assigned to the original CFG; no helpers or guards excluded |
| Compiler sites after inlining | 2,638 / 4,369 | 60.38% | Copied helper sites have separate IDs; not the acceptance denominator |
| Eager runtime mapped lines | 1,118 / 1,403 | 79.69% | All mapped runtime C and inline headers included |
| Eager runtime mapped branches | 474 / 710 | 66.76% | Uncovered branches remain in denominator |

The acceptance floors remain 79% distinct compiler edges, 72% runtime lines and
55% runtime branches. Toolchain changes can alter lowered CFGs and source
mapping denominators; percentages must be compared using recorded tool/source
identities, not treated as directly interchangeable with historical totals.
Compiler-arena, bounded/pool and optional native backends are separate runtime
configurations, outside this eager runtime mapping. Their focused evidence is
retained elsewhere, rather than folded into this percentage.

Exact evidence: `profiling-coverage-matched.json`, `.log`, and
`profiling-coverage-result.json`; raw profiles and instrumented IR remain in
`build/coverage/run-8ggqot60`. Both instrumented compiler self outputs match the
current fixed point byte for byte.
