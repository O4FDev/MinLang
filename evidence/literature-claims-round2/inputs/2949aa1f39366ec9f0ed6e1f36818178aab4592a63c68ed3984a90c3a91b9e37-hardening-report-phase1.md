# Language hardening review — October 2026

Work is continuing. The results below record the first implementation phase;
its remaining performance failures are open requirements, not accepted limits.

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
a doctor command make first-use failures actionable. The doctor performs real
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
  compilation consistently.
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

The final Linux run uses the frozen implementation with Clang/LLVM 23.1.2.
Its source hashes, test updates, commands, and logs are retained under
`build/toolchain-evidence/final-list-linux/`. Convenient result copies are in
`build/hardening-evidence/`.

| Validation | Result |
| --- | --- |
| Fresh C bootstrap and ordinary/module compiler fixed points | Passed on macOS and Linux; native and sanitized LLVM agree |
| Portable suite, release builds, incremental modules | Passed on Linux LLVM 23; macOS broad suite and corrected-target reruns passed |
| Cold public bootstrap | Default development limits, spaced paths, and explicit LTO flags passed on macOS and Linux; both craft release-link paths passed on Linux LLVM 23 |
| Compiler hardening | 22 native and sanitized regressions, including exact numeric boundaries, source wrapping, native declarations, and module ordering |
| Checked List access | Six native and sanitized contracts; positive cases also pass exact ownership cleanup checks |
| Systematic compiler mutation | 16 viable mutants, 16 killed; baseline passed, no stillborn mutants or build timeouts |
| Compiler edge coverage | 85.32% distinct edges, against unchanged 79% floor; 66.05% raw sites after inlining also retained |
| Runtime coverage, including mapped headers | 78.15% lines and 66.42% branches, against unchanged 72%/55% floors |
| AFL++ on the final compiler | 32,298 executions in 60 seconds, zero saved crashes or hangs |
| Ordinary and incremental sanitizers | Linux ASan/UBSan gates passed; generated LLVM is instrumented too |
| Numeric formatting | 37,628 stratified/random bit-pattern checks, 24 golden strings, alias executions at O0/O2, native and sanitized |
| Bytes | 20,000 modeled operations per profile; eager, arena, system, fixed, and lazy, native and sanitized |
| Critical-path reference models | Five configurations, 48 oracle/allocator checks each, including instrumented generated code |
| Graphics and examples | Native loader success/failure/retry checks and both craft release-link paths passed; macOS executable examples and rejecting diagnostics passed |

Before the List optimization, the first final-source mutation run scored 87.5%, above
its 85% floor. Both survivors were reviewed rather than accepted: one mishandled
hyphenated package names, the other indexed before the first token when declarations
preceded imports. New positive and negative fixtures pass on the compiler and fail on
those retained mutants. The repeated campaign killed all 16; a new campaign against the
final List implementation also killed all 16 sampled operators. Eight seeded compiler
faults and five seeded runtime faults are caught separately.

The large macOS `make -k check` run also caught a missing bootstrap conversion and
malformed-budget diagnostic regressions during development. Those fixes, the final
compiler tests, seeded mutations, and the sanitizer fixed point were rebuilt and rerun
successfully. Final Linux testing also caught an artifact-assembly assumption that
dropped internal helper definitions, and LLVM 23 exposed sanitizer/LTO linking
differences. Both are exercised by the expanded independent-module artifact tests.
Sanitizer attributes stay on generated IR, with optimization and instrumentation applied
once at the LTO link; an intentional cross-module heap overflow verifies detection. The
full gate is still not green because the unchanged absolute instruction and memory
budgets remain unmet. `check-examples` is independently runnable, so a performance
failure need not hide its semantic assertions. Windows execution remains CI work, not a
local result.

Raw local evidence is retained under `build/` and `notes/`; CI uploads its
corresponding reports, logs, and fuzzing artifacts.

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
| Compile each compiler's own source, median CPU | 19.691 ms | 11.597 ms | 1.70× faster |
| Same self-compilation, median wall time | 22.733 ms | 13.918 ms | 1.63× faster |
| Same self-compilation, median retired instructions | 244.900 million | 109.703 million | 55.2% fewer |
| Indexed List updates, default system policy without LTO | 8.675 ms | 6.273 ms | 27.7% less CPU time |
| Bytes clear/refill, 20,000 iterations on a 1 MiB buffer | 0.663073 s | 0.460739 s | 30.5% less CPU time |
| Format exactly representable integer-valued Floats | 0.358015 s | 0.005997 s | 59.7× faster |
| Format mixed Float values | 0.187454 s | 0.149371 s | 20.3% less CPU time |
| Format fractional Float values | 0.313012 s | 0.313906 s | Approximately unchanged |

The compiler comparison uses 50 timing samples and five counter samples per
case. Its source revisions differ: replacing a literal BOM with its scalar
value lets the compiler source use ASCII indexing while preserving BOM support
for user programs. On identical original source, instructions fell from 244.900
million to 163.403 million and median CPU from 19.691 ms to 14.758 ms. This
separates implementation improvements from the self-source representation change.
Peak self-compilation memory rose slightly, from about 12.59 to 12.92 MiB.

The separate unchanged budget gate measured 18.81 ms wall p90 and 11.84 ms CPU
p90, passing its 25/22 ms ceilings, but failed at 12.9 MiB and 109.75 million
instructions against 10 MiB and 75 million. Its best-of-three, 100-run batches
are distinct from the paired measurement above. The paired campaign's wall p90
was 32.48 ms and exceeded 25 ms; its CPU p90 was 14.27 ms. The better gate result
does not erase that tail or establish a latency guarantee on this shared host.

The checked C++ experiment uses 21 alternating samples of one million steps per
workload, the same optimization level, and independent result oracles. Under the default
system allocation policy without LTO, arithmetic and record updates were about 5–6%
slower than C++; indexed List updates were 24% slower, reduced from 74% before the
helper change. The C++ List control changed by about 1% between those runs. With LTO,
arithmetic, records, and indexed updates were 0.4%, 0.8%, and 1.2% slower respectively.
Other allocation profiles have their own results in
`build/hardening-evidence/critical-path-performance.json`; they are not substitutes for
the default-policy comparison. Bounds and arithmetic checks stay enabled.

## Remaining engineering targets

The fixed self-compilation ceilings remain 75 million retired instructions and
10 MiB. The starting branch already exceeded both. Improvements in this pass
do not justify raising those ceilings or claiming they are met. CPU and wall
time are separate measurements. See [performance](performance.md).

The parser, type checker, ownership lowering, and emitter still share the
bootstrap compilation unit. Explicit typed representations and source spans
are the next useful architectural boundaries: eager token-location strings,
generic List accesses, and repeated symbol scans remain concrete profiling
targets. Cached compilation of constants/native graphs needs a versioned state
representation before its fallback can be removed.

Comparison with optimized C++ must preserve checks, observable work, compiler
flags, setup, and teardown. The maintained critical-path experiment reports
each workload separately; a local win does not establish a language-wide result.
No blanket “faster than optimized C++” claim is made here.
