# C++ ecosystem test audit for Minyar

Research date: 2026-10-04. Recommendation: **adapt selected regression shapes and GCC's optimization-matrix discipline; pilot FileCheck for frontend IR contracts; do not import whole compiler suites or replace Minyar's Python harness with DejaGNU.** This is a source audit and proposed backlog, not a claim that new tests were implemented or run.

## Scope and reproducibility

Upstream HEADs resolved through the GitHub commit API on the research date:

| Repository | Inspected revision | Commit date UTC |
| --- | --- | --- |
| llvm/llvm-project | `d30940d9dc3690bc8433411ce9b1e9eca45f9e62` | 2026-10-04 06:57:41 |
| gcc-mirror/gcc | `3526c3b792cc55d00a0585639baa5a6810899df1` | 2026-10-04 05:57:42 |
| llvm/llvm-test-suite | `57fbfe58ed5b1363083ad8d3515a2aae4108ae84` | 2026-10-02 12:27:38 |

The source links below are immutable. Reviewed the listed representative fixtures, portions of runner/configuration implementations, licenses, and official testing documentation. This is an inventory of major families with targeted close reading, **not an exhaustive reading of every upstream test**. No upstream compiler builds were attempted. GCC GitHub directory listing hit the 1,000-entry API limit for `gcc.dg/torture`; no total fixture count is inferred from that listing.

Local grounding: `README.md`, `docs/language.md`, `docs/testing.md`, `Makefile`, `tests/conformance/README.md`, `tests/regressions.py`, `tests/adversarial.py`, `tests/fuzz.py`, relevant `tests/runtime-unit.c` cases and `tests/readonly-parameters.py`; searched tests/scripts for LTO, reduction and optimization coverage. Repository-wide absence claims would require further inventory. A proposed gap below means absent from these inspected paths, or an explicit extension to existing coverage.

## Where their tests live

| Project | Main roots / families | Mechanism and relevance |
| --- | --- | --- |
| LLVM | `llvm/test/{Transforms,Analysis,CodeGen,Verifier,Assembler,Linker,DebugInfo,tools}`; `llvm/unittests` | lit/FileCheck regression files; compiled unit tests. Most backend target tests belong to LLVM, but verifier and frontend IR-contract styles are directly useful. |
| Clang | `clang/test/{Lexer,Parser,Sema,SemaCXX,CodeGen,CodeGenCXX,Driver,Modules,AST,Analysis}`; `clang/unittests` | Driver and frontend invocations plus diagnostic or IR assertions. Borrow small reproducer structure; C++ language conformance is largely inapplicable. |
| libc++ | `libcxx/test/std`, `libcxx/test/libcxx`, `libcxx/test/support`; `libcxx/benchmarks` | Standard behavior versus implementation invariants, support allocators/iterators, success/failure phase conventions. Growth, aliasing and allocator edge shapes transfer. |
| Adjacent LLVM projects | `compiler-rt/test`, `compiler-rt/lib/*/tests`, `libcxxabi/test`, `libunwind/test`, `lld/test`, `cross-project-tests` | Sanitizers, ABI/unwinding, linking and cross-project integration. Mapped for follow-up; fixtures not audited exhaustively. |
| LLVM whole programs | separate `llvm-test-suite`: `SingleSource`, `MultiSource`, `External` | Build/run/reference output and performance. Useful program-shaped workloads, but external suites and C/C++ semantics prevent blanket import. |
| GCC frontends | `gcc/testsuite/gcc.dg`, `gcc.c-torture`, `g++.dg`, `g++.old-deja`, `c-c++-common`, `gcc.target` | DejaGNU/Tcl directives select compile/run, diagnostics, target capabilities, optimization variants and assembly/tree-dump checks. |
| GCC libraries | `libstdc++-v3/testsuite`, plus `libgcc`, `libgomp`, `libatomic`, `libsanitizer` test roots | C++ library requirements, runtime helper behavior and parallelism. Root inventory only for these libraries; no claim of detailed libstdc++ audit. |

LLVM's official [testing guide](https://llvm.org/docs/TestingGuide.html) distinguishes unit, regression and whole-program suites. Its [test-suite guide](https://llvm.org/docs/TestSuiteGuide.html) describes reference execution and metrics. Source-level configurations inspected: [LLVM lit config][llvm-config], [Clang lit config][clang-config], [libc++ test format][libcxx-format], [whole-program config][suite-config], [GCC dg runner][gcc-dg], [GCC torture options][torture], and relevant capability-probe portions of [target-supports.exp][targets].

## Existing Minyar strengths to preserve

Minyar already has spec-indexed O0/O2 conformance, exact diagnostic bytes and locations, deterministic typed fuzzing with independent arithmetic expectations, AFL++ coverage campaigns, mutation scoring, compiler fixed points, Linux/macOS/Windows gates, ownership graph oracles, allocator-profile/budget matrices, sanitizer instrumentation and runner failure injection. Recommending those as new methodology would misrepresent the codebase.

`CompilerTestCase.executes` currently checks return status and stdout at O0/O2. It does not compare expected runtime stderr in this helper. Other runners already check error output, so the opportunity is consistent per-fixture exact failure oracles across a broader optimization subset. Its temporary directory is cleaned unconditionally, meaning individual failing generated sources and IR are not automatically retained there. The shared memory runner retains the suite source and generation controls, which helps replay but is not the same artifact.

The local adversarial suite already exercises receiver mutation during index/slice arguments, growth while evaluating an add argument, indexed-assignment evaluation order, short-circuit effects, shadowing, early return, shared diamonds, ownership transfers, Unicode metamorphic properties and arithmetic oracles. The candidates below intentionally extend dimensions around these cases.

## Harness decisions

**FileCheck: adopt selectively, after a small pilot.** Its [documented pattern language](https://llvm.org/docs/CommandGuide/FileCheck.html) supports function labels, captures, ordered checks and scoped negative assertions. Compare this with existing ad hoc string extraction/assertions in ownership/codegen tests. Pilot five stable frontend contracts: checked integer arithmetic, consuming versus nonconsuming Text join calls, ownership-frame selection, scalar-record construction, and readonly-parameter lowering. Check only meaningful operations and control-flow relationships; avoid snapshotting every temporary number or whole optimized functions. Runtime execution remains the semantic oracle. Pin the LLVM tool version used in CI and ensure negative checks cover the intended interval, rather than a convenient but incomplete prefix.

**lit: optional pilot, not a wholesale migration.** Inspection of [TestRunner.py][lit-runner] shows substantial command parsing/execution machinery, substitutions, timeout handling and integrated directives. That is useful when each fixture needs distinct tool pipelines. Minyar's Python suites already encode independent models and profile matrices; converting those to RUN comments creates work without stronger evidence. A standalone `tests/codegen` suite could use lit discovery, filtering and capability metadata while remaining a separate Make target. Test the integration on Windows before expanding it. [lit's own timeout regression][lit-timeout] is a useful model for checking the harness, not just the compiler.

**libc++ phase taxonomy: adapt.** [Its format implementation][libcxx-format] separates compile-pass, compile-fail, link-pass, link-fail, run-pass, diagnostic verification and generated tests, and reports unsupported configurations distinctly. Minyar can record equivalent phase metadata in its existing runners without renaming everything or taking on C++ machinery. Do not let a linker failure satisfy a compile-rejection test.

**DejaGNU: reject as a new dependency.** GCC's [dg runner][gcc-dg] and [torture support][torture] provide valuable ideas: target probes, option matrices, explicit unsupported reasons and isolation of compile/run failures. Tcl/Expect, GCC-specific driver assumptions and board support are disproportionate for the present project. Implement the small useful subset in Python; do not port the GCC runner.

**Capability probes: adapt only where needed.** [GCC target support][targets] models whether a configuration can perform an operation. Probe optional LTO, matching `opt`/FileCheck and sanitizer support once, preserve the result, and fail required CI configurations when unavailable. A skipped required platform must not look like a passing test.

## Concrete candidate tests

Priority P0 means first useful increment; P1 follows if the initial subset finds value; P2 is conditional. Effort S is roughly a few focused hours, M one to three days, L longer infrastructure work. These are estimates, not implementation commitments. All candidates should be freshly written in Minyar/C against Minyar semantics.

| ID / priority / effort | Upstream evidence and precise Minyar adaptation | Existing coverage and additional value |
| --- | --- | --- |
| C01 / P0 / S | [Clang checked arithmetic][overflow]: parameterized add/subtract/multiply/negate at signed 64-bit endpoints, with one safe neighboring value per trap. Compare exact stderr, status, and preceding stdout at O0/O2/O3/Os. | `test_integer_boundaries` and arithmetic oracle already exist; extend their error oracle and optimization dimensions, not duplicate ordinary arithmetic. |
| C02 / P0 / S | [LLVM overflow combine][sadd]: `(x + 13) - 7` with `x = MAX-10` must trap at the first operation even though a reassociated mathematical expression could fit. Mirror near MIN; use runtime parameters to avoid purely constant coverage. | Random safe arithmetic is not evidence that intermediate traps survive algebraic simplification. Keep expected behavior independently computed step-by-step. |
| C03 / P0 / S | Same [overflow combine][sadd]: safe chained additions and mixed-sign operations near boundaries must execute rather than falsely report overflow. Pair with C02 and compare every emitted output. | Adds positive controls to trap-preservation tests. Do not copy LLVM `nsw`/poison assumptions into the language oracle. |
| C04 / P0 / M | [GCC alias regression][alias2]: pass the same mutable `List<Integer>` as two parameters; write via one, read through the other before/after a helper call and loop. Repeat with two distinct Lists. | Shared-list semantics already tested in readonly-parameters; add branch/loop reload and cross-module/LTO variants to challenge incorrect noalias/readonly inference. C pointer casts and overlapping subarrays themselves do not transfer. |
| C05 / P1 / S | [GCC sequencing][eval3]: an event `List<Integer>` records execution of nested function calls, List literal elements, receiver/index/RHS expressions and selected Boolean branches. Assert the complete trace. | Existing evaluation-order cases are strong; extend only missing expression combinations, with a semantic check against Minyar's specified order. Do not import C++ assignment ordering. |
| C06 / P1 / S | [GCC chained receiver test][eval2]: construct nested Text/List expressions where an argument mutates the receiver's owning List and another argument reads it. Assert exact values plus retained aliases. | Local receiver-survival and caller-protection tests already cover simple forms; combine nesting with growth boundaries and LTO. No `std::string::replace` API is proposed. |
| C07 / P1 / M | [libc++ vector push_back][vector]: append at capacities just below/at/above growth boundaries, checking *every* prior element after each append; repeat Integer, Text and record payloads with aliases. | `bounded-list-capacity.c`, ownership suites and runtime matrices exist; extend the same corpus across payload kinds and backend configurations after checking current cases for duplication. |
| C08 / P1 / M | Same [vector fixture][vector]: run C07 under fixed/lazy tiny heaps with native and sanitized builds, expecting the specified exhaustion status and diagnostic when allocation cannot complete. | Existing pool-exhaustion checks should be reused. New dimension is the growth/payload cross-product; Minyar stops on failure, so C++ exception rollback/continued execution is not the oracle. |
| C09 / P0 / S | [libc++ string append][append]: repeated `text = text + text` crossing Minyar's growth thresholds, preserving an alias from before each join; include empty text, multibyte scalars and embedded NUL. | Runtime unit tests already check owned-chain geometric growth and shared fallback. This extends self-alias/UTF-8/threshold combinations through generated LLVM. |
| C10 / P1 / S | Same [append fixture][append]: concatenate a slice with its own root and overlapping sibling slices; discard outer bindings; verify content, scalar length and indexing after further allocations. | Existing flattened-root/tiny-slice/copy tests provide baseline. Add overlap at growth boundaries rather than re-test simple slices. C++ SSO sizes are irrelevant. |
| C11 / P1 / M | [libc++ ASan annotation test][asan-string]: a runtime-level negative control deliberately accesses a region meant to be poisoned and must produce an ASan failure; pair it with valid end-boundary reads. | Minyar already tests sanitizer poisoning and leak-detector rejection. Extend only untested allocation/profile boundaries; do not introduce a second redundant ASan smoke suite. |
| C12 / P0 / M | [LLVM dominance verifier fixture][dominates]: generate nested if/while/early-return/short-circuit programs, verify emitted IR explicitly, then execute. Save malformed IR on verifier failure. | Linking already rejects many malformed modules. A dedicated verifier stage identifies frontend IR failure before optimization, with better phase attribution and retained evidence. Exceptions/landing pads from the upstream fixture do not apply. |
| C13 / P0 / M | [GCC LTO suite driver][gcc-lto]: small cross-module alias/return/overflow cases compiled with LTO enabled and disabled; compare status/stdout/stderr to an independent oracle. | Module artifact tests already exercise LTO. Expand a deliberately small semantic subset; do not claim first LTO coverage. Use release driver settings as well as direct IR linking. |
| C14 / P1 / S | [LLVM signed argument fixture][signedargs]: mixed negative, zero, MIN/MAX and Boolean/Character arguments through high-arity forward/recursive calls and record returns. | Large parameter fallback and scalar-record tests exist. Add ABI value-pattern permutations and supported native architecture execution; C narrow integer promotions do not apply. |
| C15 / P0 / M | [lit timeout self-test][lit-timeout]: runner fixture child process hangs after spawning a descendant; verify bounded termination, correct timeout classification and preserved logs. | Memory-contract harness already checks a hanging compiler/process groups. Extend whichever proposed codegen/torture runner is new; reuse existing helper rather than repeat infrastructure. |
| C16 / P1 / M | [llvm-reduce entry point][reduce]: deliberately inject a known wrong-result failure into a test-only candidate, save the exact source/IR/tool commands and reduce the IR with an interestingness script that preserves the failure. | AFL crash minimization is already policy. No general retained wrong-result reduction pipeline was identified in the inspected local runners; this validates the reporting workflow itself. |

## Optimization and differential campaign design

The inspected [GCC dg runner][gcc-dg] defaults to O0/O1/O2, aggressive O3 variants and Os; [torture support][torture] separately supplies LTO combinations. Adapt the principle, not its GCC-only flags. Keep ordinary O0/O2 gates, and add a curated C01–C04/C09/C12/C13 nightly matrix of O3, Os, and supported LTO on/off. Avoid multiplying every expensive heap/sanitizer configuration by every backend option. Start with one native system-heap profile, then pairwise high-risk combinations.

For each case preserve source, emitted unoptimized LLVM, exact compiler/Clang/linker versions, flags, runtime hash, target triple, environment, stdout/stderr/status and timeout phase. Compare against a Python semantic oracle or explicit expected output. Merely comparing O0 and O3 can miss a shared frontend bug. Differential testing between compiler bootstrap stages is supplementary because a fixed point is already present and is not an independent language implementation.

A separate cross-Clang-version lane can reveal backend regressions, subject to compatible LLVM IR and target support. Record versions and classify tool incompatibility separately from a wrong answer. Native architecture runs provide stronger ABI evidence than cross-compilation alone. Csmith-style C generation does not directly test Minyar; building a semantics-preserving translator is a separate large project, so defer it.

When a mismatch occurs, first classify frontend rejection, verifier failure, optimization failure, link failure, crash, timeout or wrong result. Use [llvm-reduce][reduce] only for IR failures with an executable interestingness predicate; it does not understand Minyar source. A source reducer must preserve typing, module closure and the oracle. Promote the minimized result to the normal deterministic corpus with the original failure metadata. Do not auto-rewrite expected results to make a changed compiler pass.

## Reject or defer

- **Bulk C++ conformance import:** templates, overload resolution, implicit conversions, raw pointer aliasing, object layout, exceptions, RTTI, inheritance and most standard-library APIs have no corresponding Minyar semantics. Porting them would be noise or a language expansion.
- **C++ undefined-behavior expectations:** Minyar's signed overflow traps, checked bounds, Boolean-only conditions, Unicode scalar indexing, immutable record fields and shared mutable Lists differ materially. In particular, the inspected [C array indexing regression][indexing] mixes unsigned arithmetic and narrow signed types; reject a literal port.
- **Return-address/frame-pointer cases:** the inspected [GCC return-address test][return-address] uses alloca and compiler builtins. Minyar's real stack-bound tests already address its contract; the GCC fixture is not a replacement.
- **Whole LLVM/GCC backends:** running upstream suites validates a toolchain distribution, not Minyar lowering. Delegate their maintenance upstream; retain tiny Minyar reproductions when a supported LLVM release demonstrably regresses.
- **Full optimized-IR snapshots:** [GVN's own regression][gvn] is appropriate for a specific LLVM pass, but snapshotting all LLVM optimization output would couple Minyar to backend implementation details. Restrict FileCheck to stable frontend obligations.
- **GoogleTest/DejaGNU framework replacement:** no identified need justifies converting existing Python or C assertion suites.
- **Benchmarks as semantic gates:** whole-program correctness and timing are distinct evidence. Preserve Minyar's existing controlled performance category; do not introduce hosted-runner latency thresholds from this audit.

## Provenance and rollout

Prefer original Minyar fixtures derived from a described bug pattern. Track an upstream URL, revision, original intent, semantic differences and Minyar destination for every adapted case. If copying source text, retain notices and evaluate the file-specific license before merging. LLVM's [license][llvm-license] is Apache-2.0 with LLVM exceptions and documents legacy/third-party terms; inspected libc++ fixtures carry explicit SPDX notices. GCC's [COPYING3][gcc-license] supplies GPLv3 terms, but the notice and provenance of the particular file still matter. A GCC runtime exception must not be presumed to cover tests. The separate [LLVM test-suite license][suite-license] includes multiple licenses; its programs are not uniformly licensed. This audit copies no upstream implementation or fixture code into the repository.

Suggested first delivery: 6–10 small independently authored cases from C01–C04/C09/C12/C13, a shared retained-result schema, and a five-fixture FileCheck trial. Accept the trial only if it catches a controlled lowering mutation, correctly distinguishes unsupported tools from failures, and is portable across required CI hosts. Measure incremental runtime before expanding. Preserve current suites and evidence artifacts throughout. Follow with capacity sweeps and automated reduction only after the first tranche proves useful.

[llvm-config]: https://github.com/llvm/llvm-project/blob/d30940d9dc3690bc8433411ce9b1e9eca45f9e62/llvm/test/lit.cfg.py
[clang-config]: https://github.com/llvm/llvm-project/blob/d30940d9dc3690bc8433411ce9b1e9eca45f9e62/clang/test/lit.cfg.py
[libcxx-format]: https://github.com/llvm/llvm-project/blob/d30940d9dc3690bc8433411ce9b1e9eca45f9e62/libcxx/utils/libcxx/test/format.py
[lit-runner]: https://github.com/llvm/llvm-project/blob/d30940d9dc3690bc8433411ce9b1e9eca45f9e62/llvm/utils/lit/lit/TestRunner.py
[lit-timeout]: https://github.com/llvm/llvm-project/blob/d30940d9dc3690bc8433411ce9b1e9eca45f9e62/llvm/utils/lit/tests/shtest-timeout.py
[overflow]: https://github.com/llvm/llvm-project/blob/d30940d9dc3690bc8433411ce9b1e9eca45f9e62/clang/test/CodeGen/integer-overflow.c
[sadd]: https://github.com/llvm/llvm-project/blob/d30940d9dc3690bc8433411ce9b1e9eca45f9e62/llvm/test/Transforms/InstCombine/sadd-with-overflow.ll
[vector]: https://github.com/llvm/llvm-project/blob/d30940d9dc3690bc8433411ce9b1e9eca45f9e62/libcxx/test/std/containers/sequences/vector/vector.modifiers/push_back.pass.cpp
[append]: https://github.com/llvm/llvm-project/blob/d30940d9dc3690bc8433411ce9b1e9eca45f9e62/libcxx/test/std/strings/basic.string/string.modifiers/string_append/pointer_size.pass.cpp
[asan-string]: https://github.com/llvm/llvm-project/blob/d30940d9dc3690bc8433411ce9b1e9eca45f9e62/libcxx/test/libcxx/strings/basic.string/asan.pass.cpp
[dominates]: https://github.com/llvm/llvm-project/blob/d30940d9dc3690bc8433411ce9b1e9eca45f9e62/llvm/test/Verifier/dominates.ll
[gvn]: https://github.com/llvm/llvm-project/blob/d30940d9dc3690bc8433411ce9b1e9eca45f9e62/llvm/test/Transforms/GVN/basic.ll
[reduce]: https://github.com/llvm/llvm-project/blob/d30940d9dc3690bc8433411ce9b1e9eca45f9e62/llvm/tools/llvm-reduce/llvm-reduce.cpp
[llvm-license]: https://github.com/llvm/llvm-project/blob/d30940d9dc3690bc8433411ce9b1e9eca45f9e62/LICENSE.TXT
[gcc-dg]: https://github.com/gcc-mirror/gcc/blob/3526c3b792cc55d00a0585639baa5a6810899df1/gcc/testsuite/lib/gcc-dg.exp
[torture]: https://github.com/gcc-mirror/gcc/blob/3526c3b792cc55d00a0585639baa5a6810899df1/gcc/testsuite/lib/torture-options.exp
[targets]: https://github.com/gcc-mirror/gcc/blob/3526c3b792cc55d00a0585639baa5a6810899df1/gcc/testsuite/lib/target-supports.exp
[alias2]: https://github.com/gcc-mirror/gcc/blob/3526c3b792cc55d00a0585639baa5a6810899df1/gcc/testsuite/gcc.dg/torture/alias-2.c
[eval2]: https://github.com/gcc-mirror/gcc/blob/3526c3b792cc55d00a0585639baa5a6810899df1/gcc/testsuite/g++.dg/cpp1z/eval-order2.C
[eval3]: https://github.com/gcc-mirror/gcc/blob/3526c3b792cc55d00a0585639baa5a6810899df1/gcc/testsuite/g++.dg/cpp1z/eval-order3.C
[gcc-lto]: https://github.com/gcc-mirror/gcc/blob/3526c3b792cc55d00a0585639baa5a6810899df1/gcc/testsuite/g++.dg/lto/lto.exp
[indexing]: https://github.com/gcc-mirror/gcc/blob/3526c3b792cc55d00a0585639baa5a6810899df1/gcc/testsuite/gcc.c-torture/execute/20000412-1.c
[return-address]: https://github.com/gcc-mirror/gcc/blob/3526c3b792cc55d00a0585639baa5a6810899df1/gcc/testsuite/gcc.c-torture/execute/20010122-1.c
[gcc-license]: https://github.com/gcc-mirror/gcc/blob/3526c3b792cc55d00a0585639baa5a6810899df1/COPYING3
[suite-config]: https://github.com/llvm/llvm-test-suite/blob/57fbfe58ed5b1363083ad8d3515a2aae4108ae84/lit.cfg
[suite-license]: https://github.com/llvm/llvm-test-suite/blob/57fbfe58ed5b1363083ad8d3515a2aae4108ae84/LICENSE.TXT
[signedargs]: https://github.com/llvm/llvm-test-suite/blob/57fbfe58ed5b1363083ad8d3515a2aae4108ae84/SingleSource/UnitTests/2003-07-09-SignedArgs.c
