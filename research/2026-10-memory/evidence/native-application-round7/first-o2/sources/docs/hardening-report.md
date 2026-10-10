# Language hardening review — October 2026

The compiler is frozen at source SHA `8519fd17…`. The unchanged resource-budget
gate, full macOS check, and all 61 recorded Linux correctness checks pass.
The final mutation, coverage, fuzzing, leak, and compatibility checks also pass;
source snapshots and earlier attempts remain available separately.

This pass focuses on Minyar's compiler, runtime, build tools, and tests. It keeps
the pre-existing Minecraft and bounded-runtime work in the working tree. The
game is a package/linking integration fixture, rather than the language's
architecture. No commit, release, or deployment is part of this pass.

## Organization and language experience

The self-hosted implementation now lives in `compiler/`. The root Makefile is
configuration plus small includes for compiler, runtime, examples, checks, and
research rules. Collections, numeric operations, and Bytes have named private
runtime fragments while retaining a single translation unit and the existing
runtime ABI. EditorConfig and a pinned ClangFormat check establish repeatable
formatting. [Architecture](architecture.md) explains the Swift/Rust references,
boundaries, and the remaining single-unit bootstrap constraint.

Ordinary programs now receive `-O2` optimization automatically. `--debug` selects
O0 with debug information; `--release` enables LTO. Help, version identity, and
a doctor command make first-use failures actionable. `--check` validates source
without linking a program. Native output is published atomically; failed links
preserve the prior executable and source/output aliases are rejected. A missing
source is diagnosed before spending time bootstrapping. The doctor performs real
opaque-IR, C-header, 64-bit-target, and LTO link probes.

Expressions can wrap inside parentheses and brackets, and `else` can follow a
newline or comments. The bootstrap and self-hosted compiler agree. Constants
are checked even when unused; parameters and local bindings shadow constants
consistently. [Syntax review](syntax-review.md) records the design choices and
the semantic work needed before further surface changes are justified.

## Correctness, portability, and robustness

- Fixed bootstrap signed overflow while reading the valid maximum Integer;
  GCC's optimized bootstrap could previously crash. UBSan now checks both the
  boundary fixture and the complete compiler source.
- Fixed overflowing Float constants, long leading-zero decimal normalization,
  minimum negative hexadecimal integers, and Character literal lowering.
- Validate native symbols, signatures, declaration collisions, and function
  bodies before producing LLVM. Package declarations reach direct and module
  compilation consistently. Native declarations are also checked against the
  full emitted runtime ABI catalog, preventing duplicate declarations and
  conflicting signatures without a manually maintained symbol blacklist.
- Ordinary language functions have a separate LLVM namespace. A user function
  named `malloc`, `printf`, or a runtime helper can no longer replace C symbols.
  Native declarations retain their C ABI. Cached module interface/delta versions
  advance together, so older bodies rebuild. Calling the executable entry `main`
  now receives a source diagnostic instead of generating a mismatched native call.
- Incremental compilation falls back to the ordinary compiler for graphs with
  constants or native/package declarations that its cache representation cannot
  yet represent. It preserves successful prior state and resumes caching when
  those constructs are removed.
- Toolchain identity and flags invalidate cached compiler/runtime artifacts,
  including on Apple's whole-second GNU Make. Native package artifacts track
  headers, flags, and compiler identity without reading an entire compiler
  binary on each link. Atomic publication and an OS bootstrap lock protect
  concurrent launcher invocations.
- Toolchain flags are parsed into literal arguments; paths with spaces work.
  Unix math libraries occur after their users. Windows graphics loads modern
  OpenGL functions through GLFW and links the correct platform library.
- Linux cold bootstrap selects matching LLD with one linker thread, avoiding
  excessive virtual-address reservations within the existing 768 MiB development
  limit. Explicit linker flags remain authoritative. A real cold public-launcher
  test covers this limit and toolchain/project/output paths containing spaces.
- Bytes shrinking and clearing avoid scanning discarded capacity. Growth and
  native extension still initialize newly visible bytes, including recycled
  storage. Unicode indexing reuses a cursor for nearby backward accesses as
  well as forward scans.
- Float formatting preserves negative zero and bit roundtrips, repairs shortest
  decimal output at asymmetric powers-of-two boundaries, handles zero-capacity
  buffers, and fast-paths exactly representable small integers.
- Reject negative List capacities before capacity multiplication; sanitizer
  regressions cover the minimum Integer as well as allocation-size boundaries.
- Stack-bound discovery is a cold initialization path. Native bounds and ASan
  fake-stack fallback protections remain covered at exact policy boundaries.
- Checked List reads, scalar writes, and length loads are visible to LLVM in
  ordinary builds. Layout assertions and tests protect the ABI, bounds errors,
  aliased growth, evaluation order, and reference ownership.

The [toolchain audit](toolchain.md) covers actual Apple Clang 17, upstream LLVM
22.1.5 and 23.1.2, Linux Clang 18, GCC, and the configured Windows CI jobs.
Local Docker execution is Linux ARM64 evidence; it does not certify Windows or
Linux x86-64 execution. Native Windows without MSYS2 and Windows incremental
caching remain outside the implemented support boundary.

## Tests and evidence

Fixes were developed from failing examples and checked against independent
oracles: byte-exact diagnostics, modeled integer arithmetic and ownership,
binary64 bit patterns and shortest representations, Bytes state transitions,
and explicit operation-count bounds. Both ordinary and sanitized generated
programs run at O0/O2. Bootstrap fixed points are checked from fresh C builds.

The review also repaired false confidence in the harnesses. Fuzzing now honors
the selected candidate/compiler runtime; mutation campaigns require a passing
baseline and distinguish killed, stillborn, timed-out, and surviving mutants.
Coverage includes runtime implementation headers and rejects empty denominators
and invalid thresholds. Fault-injection tests check those failure modes.
Coverage now records both distinct LLVM edges and the raw sites after inlining.
Assigning edge identities before inlining prevents duplicated List guards from
inflating the distinct-branch denominator; it excludes no guards or functions.
An executable one-call/sixteen-call fixture verifies this property and both
branch arms, and both instrumented compilers must preserve the fixed point.

[Testing](testing.md) maps this strategy to primary Swift, Rust, LLVM, Zig,
Csmith, and equivalent-program testing references. It distinguishes semantic
generation from crash discovery and records limitations of the current typed
templates. Test counts or a high mutation score do not prove superiority over
all mature language implementations.

The final native and sanitized bootstrap chains reproduce byte-identical LLVM.
There are 30 focused compiler-hardening tests, six source-location contracts,
112 tokenizer/profile/optimization checks, and independent scalar arithmetic,
conversion, ownership, and allocation models. The six linkage regressions pass,
including real native C calls, actual cache reuse, and distinct names across
modules. A separate migration check rejects actual prior-ABI cached bodies and
executes the rebuilt program at O0 and O2.

The complete macOS `check` target passes on the final source. It reuses only the
unchanged runtime-only stack-ownership matrix, whose 40 configurations already
passed; the report records both logs and source identities. LLVM 22 also verifies
and LTO-links the final compiler, reproduces its exact self-hosted IR, and passes
the 14 numeric tests and ordinary symbol-isolation regression. Evidence is in
`build/hardening-evidence/final/macos-check.json`,
`build/hardening-evidence/legacy-linkage-cache/results.json`, and
`build/toolchain-evidence/final-linkage-llvm22/results.json`.

The final Linux LLVM 23 snapshot passes all 61 recorded correctness checks,
including native/sanitized module artifacts, LTO, and independent benchmark
oracles. The supplemental campaign kills all 16 sampled viable compiler mutants
from 1,604 discovered operator sites, with no stillborn mutants or build timeouts.
Compiler coverage is 1,914/2,230 distinct edges (85.83%); raw post-inlining coverage
is 2,606/4,331 sites (60.17%). Runtime coverage is 1,114/1,409 lines (79.06%) and
464/694 branches (66.86%). The original coverage floors remain unchanged.

AFL++ completes 68,364 executions in 60 seconds, finding 627 new corpus entries
with no saved crashes or hangs. Leak replay passes with a positive detector
control. Native graphics, GCC bootstrap, example execution, LLVM IR verification,
and all four ordinary/release/incremental game link modes pass. These campaigns
measure specific configurations and durations, not the absence of all bugs.

The first mutation campaign on this exact production source killed 14/16 mutants.
The two survivors exposed missing comparator equality and parent-import/library
interaction tests. Added ordering-contract units and a mixed import regression
reject those exact retained mutants and pass with and without sanitizers on
macOS and Linux. The complete strengthened campaign then kills 16/16. Its six
test/wiring changes are recorded in a separate snapshot; production code is
byte-identical to the broad Linux run. Both campaigns remain available under
`build/toolchain-evidence/final-pairs-linux`, alongside their logs and sources.

Two survivors in an earlier source revision also exposed test weaknesses, not
reasons to lower its floor. A source-path unit now checks empty-path index-zero
reuse and insertion invariants; readonly-parameter tests check ownership
lowering. Both fail against their exact retained mutants. Internal unit tests
now load the selected mutant source instead of silently loading the working
compiler. Eight seeded compiler faults and five runtime faults are separate
checks. The absolute-budget harness also rejects a failed instruction-counter
process instead of interpreting its short execution as an inexpensive compile.

Independent-module artifact tests retain the entire compiler helper prelude.
Generated sanitizer attributes survive object assembly and instrumentation runs
once at the LTO link; a deliberate cross-module heap overflow verifies detection.
All reports retain failed attempts and their resolution rather than replacing
them with unexplained successful summaries.

The final evidence index is `build/hardening-evidence/final/summary.json`, with
report paths and hashes. Raw local evidence remains under `build/` and `notes/`;
CI uploads its corresponding reports, logs, and fuzzing artifacts. Hosted Windows execution
remains separate from local macOS and Linux ARM64 evidence.

## Measured performance

These measurements use Apple Clang 17 on this ARM64 Mac. Compiler measurements
exclude the launcher and native link; runtime measurements exclude setup and
teardown. Compiler and Bytes comparisons use the original runtime and compiler
reconstructed from the starting working tree, including its pre-existing
bounded-runtime work. The List comparison isolates the final LLVM helper change
against the already hardened implementation immediately preceding it.
The evidence records source hashes, flags, sample distributions, and output
equivalence checks. They are local measurements, not cross-platform guarantees.

| Workload | Before | After | Result |
| --- | --- | --- | --- |
| Compile each compiler's own source, median CPU | 17.733 ms | 7.275 ms | 2.44× faster |
| Same self-compilation, median wall time | 18.944 ms | 8.305 ms | 2.28× faster |
| Same self-compilation, median retired instructions | 243.428 million | 72.347 million | 70.3% fewer |
| Same self-compilation, maximum measured RSS | 12.578 MiB | 9.281 MiB | 26.2% less |
| Bytes clear/refill, 20,000 iterations on a 1 MiB buffer | 0.663073 s | 0.460739 s | 30.5% less CPU time |
| Format exactly representable integer-valued Floats | 0.358015 s | 0.005997 s | 59.7× faster |
| Format mixed Float values | 0.187454 s | 0.149371 s | 20.3% less CPU time |
| Format fractional Float values | 0.313012 s | 0.313906 s | Approximately unchanged |

The compiler comparison retains 50 timing samples and five counter samples per
case. Original and final compilers use their actual corresponding runtimes.
All five final instruction observations are below 75 million; the largest is
72.656 million. The final paired campaign's CPU p90 is 7.835 ms and wall p90 is
11.179 ms. The separate unchanged 3×100-run budget gate also passes: 9.16 ms wall p90,
7.65 ms CPU p90, 9.3 MiB maximum RSS, and 71.88 million instructions.

Source revisions differ in the own-source comparison. An ASCII spelling of the
compiler's BOM scalar preserves BOM support while avoiding Unicode indexing of
the compiler source. On identical original source, instructions fall from
243.428 million to 121.068 million and CPU from 17.733 ms to 9.808 ms. This
separates implementation improvements from source-representation effects.
Exploratory runtime-swap cases in the report are labeled separately and do not
replace the unmodified starting baseline.

Typed source positions and shared module paths defer diagnostic formatting;
a successful self-compile formats roughly 151 locations instead of 42,223.
Cached character reads, borrowing the coordinate buffer once per tokenizer,
and removing trivial output wrappers reduce repeated compiler work. Positions
store full-width line/column pairs; per-token module path indices are allocated
only when needed. A 44,000-token lexer oracle and a 50,000-token internal unit
protect against the capacity cliff that the former three-value layout exposed. Checked
scalar success paths are visible to LLVM without requiring LTO or weakening
failure diagnostics, overflow rules, or conversion checks.

The final C++ comparison uses 31 alternating adjacent pairs of five million
steps per case, independent semantic and allocation oracles, and equal
optimization levels. Ratios below one favor Minyar; intervals are deterministic
95% percentile bootstraps of the paired ratios. All observations and warmups are
retained. These are per-workload intervals on one host, not universal guarantees.

| Default build workload | Minyar / C++ CPU ratio | 95% interval |
| --- | --- | --- |
| Checked arithmetic | 0.9995 | 0.9916–1.0049 |
| Indexed List updates | 0.9619 | 0.9457–0.9706 |
| Record updates | 1.0001 | 0.9952–1.0042 |
| Checked shifts | 1.0019 | 0.9978–1.0067 |
| Unicode scalar conversion | 0.9896 | 0.9860–0.9979 |
| Float-to-Integer | 0.9638 | 0.9573–0.9659 |
| Absolute value / clamp | 0.9989 | 0.9940–1.0035 |

The former default-build gaps are closed on these workloads. Indexed List work
and Float conversion are about 3.8% and 3.6% faster respectively; arithmetic,
records, shifts, and abs/clamp overlap parity. The initial final-core run and the
repeated final-harness run are both retained, rather than selecting whichever
run favors Minyar.

A separate system-allocation LTO List case remains 1.02% slower (interval
0.76–1.46% slower). Disassembly and five counter pairs show real extra work:
header/backing-pointer reloads, repeated bounds checks, and signed arithmetic
that C++ can simplify after forwarding the stored value. Whole-process retired
instruction counts for this fixture are also larger, including under the
faster default configuration. Lower CPU time is not a claim of fewer
instructions. Further optimization needs proven memory-effect/type information;
this pass adds no unsupported aliasing or arithmetic promises to hide that gap.

C fixtures bind directly to the compiler's isolated language symbols. For Darwin
LTO, C-generated asm alias names are canonicalized to those exact LLVM names;
replacement counts, expected sets, before/after IR and hashes are retained.
Measured Minyar functions are unchanged. The older critical fixture only renames
its unused entry; the scalar fixture uses its actual generated entry and native
driver declaration.

The later native-declaration and source-position fixes produce byte-identical
benchmark LLVM with both the current compiler and the exact budget binary.
All runtime, driver, C++ and harness inputs remain unchanged. The comparison is
retained rather than re-timing identical programs; `cpp-final-ir-bridge.json`
records the old/new sources, binaries, emitted IR, hashes and all 35 case mappings.

Reports: `build/hardening-evidence/critical-path-final-performance.json`,
`checked-scalars-final-performance.json`, and
`critical-book-final-instructions.json`. The maintained studies report every
ownership/LTO profile independently, including less favorable results.

## Remaining engineering targets

The fixed self-compilation ceilings remain 75 million retired instructions,
10 MiB, 22 ms CPU p90, and 25 ms wall p90. No ceiling or saved baseline is raised.
Both the paired campaign and the independent gate fit them. See [performance](performance.md).

The parser, type checker, ownership lowering, and emitter still share the
bootstrap compilation unit. Typed intermediate representations are the next
architectural boundary; the current typed source map already removes eager
location strings. Cached compilation of constants/native graphs needs a
versioned representation before its correct full-build fallback can be removed.

Comparison with optimized C++ must preserve checks, observable work, compiler
flags, setup, and teardown. The maintained experiments report each workload
separately; a local win does not establish a language-wide result. No blanket
“faster than optimized C++” claim is made here.
