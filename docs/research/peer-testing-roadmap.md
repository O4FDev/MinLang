# Ten-language testing audit and adoption roadmap

Date: 2026-10-04. Minyar baseline: `8e5231607ca7d796764697e00822b747a5622e30`.

**Recommendation: keep Minyar's existing test infrastructure, add controlled allocation failures and better failure reproduction, and port a small set of semantic boundary cases. Pilot FileCheck for a handful of LLVM contracts; do not import an entire foreign language suite.**

Three subagents investigated upstream repositories, with an additional independent review of the JavaScript/Java research and Python/Swift coverage comparisons. The audit covers **ten distinct languages**; C++ includes Clang, GCC and libc++ but counts once, and JavaScript includes Test262 and V8 but counts once. The five detailed reports contain **97 candidate rows**, including explicitly covered, conditional and rejected ideas. That is a research shortlist, not 97 missing tests or discovered bugs.

## Coverage and evidence

| Language | Official codebases and families examined | Most useful transfer | Detailed evidence |
| --- | --- | --- | --- |
| Python | CPython regression runner, compiler/codec/list/integer tests, environment and reference-leak helpers | Contamination/replay discipline; malformed-encoding matrices | [Python/Swift report](peer-tests-python-swift.md#cpython-inventory) |
| Swift | Compiler lit tests, ARC/IR tests, dependency scans, validation/stdlib lifetime tests | Small function-scoped IR checks paired with runtime evidence; failure-preserving retry policy | [Python/Swift report](peer-tests-python-swift.md#swift-inventory) |
| C++ | LLVM/Clang, libc++, GCC compiler suites, LLVM whole programs | Small optimization torture matrix; FileCheck; overlap/capacity regressions | [C++ report](peer-tests-cpp.md) |
| Rust | compiletest UI/run-make, codegen/incremental families, Miri scope | Huge-index regressions; revision/mode metadata and harness self-tests | [Rust/Go/Zig report](peer-tests-rust-go-zig.md#rust) |
| Go | Compiler regression harness, package tests, runtime tests, command script/cache scenarios | Readable multi-file driver scenarios and stage-specific assertions | [Rust/Go/Zig report](peer-tests-rust-go-zig.md#go) |
| Zig | Compile-error/safety/behavior/standalone tests, standard-library test allocators | Systematic allocation and separate resize failure injection | [Rust/Go/Zig report](peer-tests-rust-go-zig.md#zig) |
| JavaScript | Test262 language/spec metadata and V8 engine/variant/status harnesses | Explicit expected failure phase, specification mapping, complete output assertions | [JavaScript/Java report](peer-tests-javascript-java.md#javascript-suite-map-and-decisions) |
| Java | OpenJDK javac rejection cases, HotSpot optimizer regressions, jtreg groups and IR framework | Control-flow/trap preservation; conditional IR assertions and suite membership | [JavaScript/Java report](peer-tests-javascript-java.md#java-suite-map-and-decisions) |
| Ruby | Bootstrap, Test::Unit, Ruby Spec/MSpec, array/string/runtime tests | Pairwise configuration coverage accounting; resource cleanup | [Ruby/Lua report](peer-tests-ruby-lua.md#ruby-inventory-and-inspected-evidence) |
| Lua | All test families enumerated in compact `testes/` tree, `ltests.c`, allocator/error/UTF-8 cases | Allocation ordinal sweeps and always-moving realloc stress | [Ruby/Lua report](peer-tests-ruby-lua.md#lua-inventory-and-inspected-evidence) |

Each report pins official source revisions, maps major test roots, identifies inspected harnesses and representative cases, compares Minyar coverage, and records semantic/copying limits. Full upstream suites were not executed. This is **not an exhaustive line-by-line reading of every upstream test**. Some recursive GitHub inventories were truncated (Rust, Test262, OpenJDK); reports disclose that and, where done, document complete subtree follow-ups. No claim of full test counts is made from truncated inventories.

## What Minyar already does

The baseline was checked against actual runners and fixtures, not just README claims:

- [Conformance](../../tests/conformance.py) already runs feature-indexed programs at O0/O2 against exact output; [diagnostics](../../tests/diagnostics.py) compares full stderr, status, columns, and absence of LLVM output.
- [Adversarial tests](../../tests/adversarial.py) already cover evaluation order, mutation during receiver use, short-circuit effects, escaping references, Unicode properties, and arithmetic oracles.
- [Fuzzing](../../tests/fuzz.py) already generates typed programs, arithmetic expressions and module chains. AFL++ has a persistent nightly campaign and deterministic regression corpus.
- Ownership and pool matrices already use independent graph models, exact cleanup debt/storage recovery, sanitizer instrumentation, and stack-owner admission/fallback assertions.
- Incremental tests already cover corrupt cache artifacts, same-mtime edits, concurrency, failure publication, identity changes and detailed cold/warm counters. Generic advice to “test caches” adds little.
- The project already has bootstrap fixed points, mutation scoring, measured coverage, platform gates, memory-runner self-tests and separate performance evidence.

The independent review also found existing exact Unicode scalar-boundary cases and multi-boundary forward Text-index tests. Proposed Unicode work below therefore focuses on compositions, invalid encodings, access order and integration paths.

## Ranked work packages

These priorities supersede the differing P0/P1 labels in individual reports. Effort is a planning estimate: small means a focused fixture/helper change, medium means several days of integration and validation, large means a separate project. Implementations are proposed, not completed by this audit.

| Rank | Work package | Evidence / destination | Acceptance criteria | Effort |
| --- | --- | --- | --- | --- |
| 1 | Complete result assertions and retained failure evidence | C++ C01/C15/C16, JS9, Rust R8. Extend `CompilerTestCase` and `tests/fuzz.py`, reusing memory-contract evidence conventions. | Correct stdout/status plus unexpected stderr fails. On compile/link/run failure or timeout, retain exact source/module tree, IR if produced, command, flags, versions, runtime/source hashes, output bytes and failure phase. Replay works after original temporary directory disappears. Harness fault cases prove failure detection. | Medium; stderr tightening alone is small |
| 2 | Controlled allocation/resize failure and relocation | Zig Z1–Z3; Lua allocation/relocation rows. Add test-only hooks around actual runtime allocation entry points. | Successful baseline establishes observed allocation ordinals; every requested failpoint demonstrably fires in a fresh child. Test Text join, nested construction and List growth with live aliases. Separately force relocation and resize failure. Require specified fatal status/message or documented recoverable invariants. Hooks absent from ordinary builds. | Medium |
| 3 | Small checked-arithmetic/alias optimization matrix | C++ C01–C04/C13; Rust R4; Zig Z5/Z6; Java J1–J4. Extend existing regressions and release/module scenarios. | Safe neighbors succeed; unused required-overflow operations still fail; unreachable traps never execute; intermediate overflow cannot disappear through reassociation; shared List writes remain visible across calls/modules. Compare independent expected stdout/stderr/status at O0/O2 plus a curated O3/Os/LTO subset. | Small–medium |
| 4 | Huge-index and storage-boundary cases | Rust R1/R2; C++ C07/C09/C10; Ruby shared-view/growth rows. | Huge signed indices never wrap into valid reads/writes; bounds error occurs before unsafe memory access. Self-concat, overlapping Text slices and List growth preserve live aliases/content at capacity boundaries and pass existing cleanup/sanitizer oracles. | Small–medium |
| 5 | Encoding and lexical interaction matrices | Python UTF-8/newline/NUL rows; Rust R5; Lua UTF-8 rows; JS6. | Malformed width/truncation/surrogate/range cases reject across applicable input paths. Mixed-width composed Text survives slicing/joining/NUL/file paths. Descending/random scalar access crosses index-cache boundaries. Exact columns follow an explicitly chosen column contract. | Small–medium |
| 6 | Verified LLVM contracts, with a FileCheck pilot | C++ C12 and harness section; Swift ARC row; Java IR framework. | Explicit verifier failure is attributed to emitted IR and retains it. Five small function-scoped frontend checks catch a controlled lowering error, while native execution proves behavior. Required tools are pinned/probed on CI; missing required tooling fails. Avoid whole optimized-IR goldens. | Medium |
| 7 | Thin fixture/configuration manifest | Rust revisions, Test262 metadata, Java groups, Ruby pairwise accounting, Zig Z10. Extend current Python/Make organization. | Stable case IDs specify feature, expected phase, required configurations and optional capabilities. Lint rejects missing goldens, duplicate IDs, empty selections and missing requested variants. Report skip reasons and required-pair coverage. Preserve mandatory full matrices. | Medium; start with a few cases |
| 8 | Scenario isolation and contamination checks | CPython environment/order, Go G3/G9, Ruby resource cleanup, Swift failure policy. | Logged seed/order reproduces failures; public-driver cold/warm diagnostics agree where contract requires; timeout cleans descendants; next scenario remains usable. A retry may gather diagnostics but cannot turn the original failing run green. | Medium; only add retry machinery if otherwise needed |
| 9 | Failure reduction and promotion | C++ C16; extend existing fuzz-regression policy. | A controlled wrong-result failure produces a smaller reproducer preserving the same oracle. `llvm-reduce` is only for LLVM-stage failures; source reduction preserves typing and module closure. Minimized cases become normal deterministic regressions, with provenance. | Medium–large |

Start with package 1 and a small tranche from 3/4, then package 2. Evidence retention makes new stress campaigns useful when they fail. This order is a recommendation, not authorization to change language semantics or a claim about existing compiler defects.

### Concrete first tranche

Use the existing Python runners and original Minyar fixtures. Keep the first batch small enough to review and time:

1. Unexpected-stderr negative control for the shared execution helper; retain/replay one intentionally failing generated case.
2. `(x + 13) - 7` with `x = MAX-10`: require intermediate overflow, plus a safe neighboring input.
3. Unused overflowing local and unreachable overflowing branch: distinguish required execution from dead code.
4. Two parameters alias the same List, mutate through one and read through the other across a helper/module; pair with distinct Lists.
5. One-element Lists indexed/replaced near signed maximum and address-scaling boundaries: exact bounds error, no memory fault.
6. Self-concatenation and overlapping Text slices with retained aliases, multibyte scalars and NUL across growth boundaries.
7. One Text allocation-failure sweep, one nested construction sweep, and one forced-moving List growth case, using existing success-path cleanup oracles.

Run normal cases at O0/O2 and select the trap/alias cases for a bounded release/optimizer lane. Measure additional CI time before enlarging the matrix. A shared wrong answer at two optimization levels is still wrong; independent oracles remain necessary.

## System adoption decisions

| System or method | Decision | Reason |
| --- | --- | --- |
| LLVM FileCheck | **Pilot adoption** as an external pinned tool | Direct fit for LLVM emission, scoped captures/negative checks; prove value on five contracts first. |
| LLVM lit | **Optional**, only for the small codegen suite if useful | Existing Python suits independent models and profile matrices; no demonstrated benefit to wholesale migration. |
| Zig/Lua fault injection | **Adopt methodology**, implement small Minyar test hooks | Exercises failure positions/relocation that ordinary exhaustion does not systematically force. |
| GCC torture configurations | **Adapt a selected matrix** | Relevant optimizer stress without GCC-specific flags or huge Cartesian products. |
| Rust compiletest, Go scripts, Test262 metadata | **Adapt thin concepts** | Modes, revisions, spec links and readable multi-file fixtures fit; foreign execution stacks do not. |
| CPython libregrtest, Ruby MSpec, Swift test stack, Java jtreg | **Do not import wholesale** | Language/runtime-specific dependencies; useful isolation/tiering practices can extend current runners. |
| Miri, full independent Minyar interpreter | **Defer** | Miri cannot interpret Minyar. A new semantics engine is a substantial separate project, not a harness installation. |
| Entire upstream corpora | **Do not bulk-import** | Most test contracts concern absent or incompatible language features. Write selected Minyar cases with exact provenance. |

## Semantic decisions before freezing expectations

Checked Integer arithmetic differs from C++ undefined overflow, Java/Ruby/Python integer behavior and Lua wrapping arithmetic. Unicode scalar Text differs from JavaScript UTF-16 indexing, Swift grapheme semantics and Lua byte strings. Shared mutable Lists differ from Swift copy-on-write arrays; immutable records differ from mutable object models. Minyar's bounded deferred cleanup does not promise immediate destructors or fatal-exit unwinding.

Resolve currently under-specified column units, bare-CR/Unicode line separator treatment, and constant-loop reachability before introducing normative goldens. The JavaScript/Java review also notes that current runtime division/remainder share a MIN/-1 guard; document intended remainder behavior before declaring a cross-language expectation. Do not broaden the language simply to accommodate borrowed tests.

No upstream implementation was copied. Reports record file/repository notices and immutable sources for later imports; copying a fixture requires its own provenance record, not a blanket assumption about repository licensing.

## Validation and completion

The deliverable is research and a prioritized implementation backlog. Source inventories, linked source bodies, harness code and local assertions were inspected. Independent review corrected overclaimed Unicode gaps, Swift full-width division relevance, V8 combined-timeout behavior, and a malformed pinned OpenJDK historical fixture. That fixture is explicitly excluded as evidence of working upstream coverage.

Only research documents were added. No compiler/runtime/test behavior was changed; neither Minyar's full test suite nor upstream suites were run for this documentation-only task. Completion means all ten languages have source-grounded reports and adoption decisions, not that every upstream test has been read or the proposed tests have been implemented.
