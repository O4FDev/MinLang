# Testing strategy

Use `make check-portable` for the cross-platform compiler/runtime gate and
`make check` for the broader local suite, including absolute performance
budgets. `make check-examples` runs the executable examples and rejecting
diagnostics independently. Coverage, systematic mutation, and AFL++ campaigns
have separate targets described below. Current results and unmet performance
targets are recorded in the [hardening review](hardening-report.md).

`make check-cold-bootstrap`, also in the portable gate, exercises the public
incremental launcher from an empty build directory with default development
limits, toolchain and project paths containing spaces, and explicit LTO flags.
It skips hosts without the POSIX incremental frontend.
`tests/launcher-bootstrap-policy.py` independently checks that this interactive
bootstrap context preserves resource caps, cannot raise an inherited hard CPU
cap, stays scoped to bootstrap, and leaves bulk-check background policy intact.

`make check-peer-semantics` runs the original focused Rust, Swift, LLVM, Zig,
Go, Nim, Koka and Lean semantic adaptations, plus literal-true loop reachability
regressions. It checks generated execution at O0 and O2 without downloading a
peer corpus. `make check-memory-regressions` runs six focused native builds for
known-length List append, tight-pool object/frame/chunk cleanup admission and
indexed Unicode Text join, including malformed UTF8 diagnosis. Both are in the portable/full gates;
their sanitizer variants are in `check-sanitize`. Broad profile matrices and
research timing comparisons remain opt-in.

Correctness needs complementary oracles: exact diagnostics, independently
modeled values and ownership, equivalent program variants, optimized and
unoptimized execution, and sanitizer instrumentation. Harness fault injection
checks that missing evidence, stale candidates, and broken baselines cannot
produce a passing result.

The launcher suites verify that failed links preserve the previous executable,
that a partially linked file is never published, and that source/output aliases
are rejected before building. `--check` exercises real local and standard-library
modules without invoking the native linker. The incremental variant asserts
that the cache driver actually ran, so an ordinary compile cannot accidentally
stand in for an incremental check.

`make check-runtime-traps` exercises exact numeric failure messages and List
capacity boundaries across all five runtime profiles; its sanitizer variant is
part of `check-sanitize`. `check-checked-arithmetic` and `check-checked-scalars`
compare optimized and unoptimized language behavior against independent models,
including operand evaluation order and conversion boundaries. Generated LLVM
and runtime C are both instrumented in their sanitizer variants.

## Memory contracts

## Peer-derived tests and failure evidence

`make check-peer-regressions` exercises checked-arithmetic traps, huge List
indices, module aliases, terminal evaluation order, mixed-width Text access and
growth with live aliases at O0/O2. It is included in `check-portable` and `check`.
`make check-peer-optimizations` adds O3/Os and two selected runtime-LTO cases;
`MINYAR_TEST_LTO_FLAGS` supplies platform linker flags when required.
`make check-peer-sanitize` runs the compiler and emitted programs under ASan/UBSan.
It uses the production error-exit contract; fatal paths do not promise ownership
unwinding. `make check-peer-ownership` runs the selected normal-return lifetime
cases with sanitized ownership instrumentation, requiring empty frames and no
remaining reclaimable objects at exit. It is included in `check-ownership` and
the peer CI job. `check-peer-manifest` validates the actual audit ledger and runs
controlled checks that reject missing review decisions, pending enumeration and
unsupported completion claims. `make check-peer-audit-complete` additionally
requires the exhaustive review and implementation backlog to be empty, every
applicability decision to be resolved, and every generated cohort to have its
corresponding checked ledger row. Domain artifacts are discovered even when
every ledger reference is missing. The Zig integer-log domain checks all
646,728 source-generated identities, with the 210 operands outside signed
Integer explicitly rejected. A deferred row never counts as completion.

Every peer-suite invocation writes a separate JSON report under
`build/peer-results/` (override with `MINYAR_PEER_RESULTS`). Reports preserve
selected and omitted methods, skip reasons, partial platform domains, the
requested gate, and required versus observed link configurations. A successful
invocation with exclusions does not report complete coverage. The CI artifact
includes these reports; failed cases additionally retain their full workspaces.

`make check-stateful-lists` runs four seeded sequences against an independent
Python List model at O0/O2/O3/Os. Every checkpoint compares all three roots'
lengths and every element, preserving alias identity in the model and copying
only for fresh `appended` results. The sequences include growth with a live alias,
indexed mutation, rebinding and swaps. Seeds, operations, generated programs and
exact output oracles are retained on failure. It is part of `check-fuzz`.
`check-stateful-lists-sanitize` repeats the sequences at O0/O2 with compiler and
ownership-runtime sanitizers, and is part of `check-sanitize` and the peer CI job.
This adapts stateful differential testing; it does not add deque/pop APIs.

`make check-list-literals` checks constant-run lowering, fresh mutable storage,
signed endpoints, dynamic evaluation order, source diagnostics, linker namespace
isolation, and cached module globals. A 16,384-element literal must retain every
cell while producing one bulk append and bounded instruction count.
`check-list-literals-sanitize` repeats the contracts with compiler/program
ASan/UBSan. `check-list-literal-runtime` exercises six allocator profiles at
O0/O2/O3/Os and sanitized O0/O2, checking capacity parity, independent copies,
one backing allocation, arithmetic rejection, and refusal without corrupting a
prior List. These gates also run in the peer correctness CI job. The separate
Lua-derived 263,145-element fixture checks every position in all peer lanes.

`make check-performance-metrics` verifies complete-build reporting independently
of host speed. Frontend and native-link CPU/wall times are summed separately;
optional peak-RSS measurements use a maximum. Missing CPU stays unavailable and
never substitutes wall time for a CPU ceiling. Profiling samples require fresh
LLVM output matching the self-hosted fixed point before their instruction count
is accepted. This control suite runs in `check` and the peer correctness CI job.

`make check-allocation-faults` runs test-only system-allocation instrumentation
natively and under ASan/UBSan at cleanup budgets 1 and 32. Each observed malloc/
calloc and realloc ordinal is independently refused in a fresh process. Every
successful realloc moves the buffer. Sixteen suffix bytes guard each allocation;
fresh payloads and grown tails are filled with a distinct byte pattern, and
released payloads are overwritten before free. Controls corrupt both ends of
the suffix, check successful/refused shrinking and reject invalid fault ordinals.
The campaign requires actual failpoint
activation, the precise OOM diagnostic, and successful normal-return ownership
drain. Fatal OOM is not required to unwind. The wrapper and its controls live
entirely under `tests/`; production allocator code is unchanged. Results are in
`build/allocation-faults.json`. Use `--mode native` or `--mode sanitize` with
`python3 tests/allocation-faults.py` for a focused run.

Both scopes also sweep live-payload byte budgets. The baseline records every
allocation, moving replacement and free. An independent trace reconstruction
finds each new prefix maximum; budgets immediately below each maximum must fail
at the matching allocation with the exact baseline trace prefix and bookkeeping.
Zero, the maximum and maximum-plus-one provide boundary controls. A resize counts
both old and new payloads until the old allocation is freed; a fixed self-test
requires its 48-byte peak and rejects a 47-byte budget. The budget excludes
allocator headers, guards, trace storage and unhooked libc allocations. This
establishes boundary coverage for the selected deterministic, fail-fast workloads;
it does not establish recovery/retry or general host-memory-pressure behavior.

`make check-compiler-allocation-faults` applies both campaigns to the
self-hosted compiler. It compiles a small assignment and a function/List/Text
program under the production arena and under system allocation with cleanup
budgets 1/32, natively and with ASan/UBSan. Successful output must exactly match
the ordinary compiler's LLVM and produce the expected native program output.
Every baseline allocation/resize ordinal must fail with the exact OOM diagnostic;
the next ordinal must remain inactive. Arena mode retains its process-lifetime
allocation policy. Its four arena chains are checked for suffix corruption at
exit, with controls corrupting both head and older blocks. Successful byte budgets
must preserve emitted LLVM. Failure does not promise an absent or atomic output
file, nor does compiler failure test execution of the generated program.
Results are written to `build/compiler-allocation-faults.json`.

`make check-runtime-size-guards` uses synthetic List headers near signed-capacity
and byte-size limits. Both append ownership paths must reject before allocation
or payload access, with the exact size diagnostic rather than sanitizer output
or OOM. It runs native and ASan/UBSan builds of system, eager, arena, bounded and
lazy profiles (the lazy profile is unavailable on Windows). A 4,097-element
normal-growth control checks every value in each configuration. These are native
arithmetic-boundary tests, not claims that gigantic Lists can be allocated.
Results are written to `build/runtime-size-guards.json`.

`make check-codegen` is a five-fixture FileCheck pilot covering checked arithmetic,
readonly parameters, owned Text joins, scalar-record construction and stack
ownership. It verifies emitted LLVM, executes O0/O2 programs, and checks that
deliberately removed guards and invalid dominance are rejected. It requires
`opt` and `FileCheck`; set `MINYAR_LLVM_BIN` if they are outside PATH. Missing
tools fail this explicitly requested target. The separate CI job uses LLVM 18;
ordinary portable checks do not acquire this dependency.

Test runners require Python assertions to be enabled; optimized Python (`-O`)
is rejected by the evidence harness. The shared regression helper and deterministic fuzz runner retain failing
workspaces in `build/test-evidence/` (override with `MINYAR_TEST_EVIDENCE`).
`evidence.json` records source/artifact hashes, commands, captured output bytes,
timeouts, selected environment controls and available tool versions. Successful
workspaces are deleted. A subtest failure retains its workspace even when later
subtests pass. Successful executions require empty stderr unless the test declares
an expected error. `make check-evidence-harness` verifies these rules, including
descendant-process cleanup on POSIX and rejection of changed replay inputs.

File-producing cases pass `(path, expected_bytes)` pairs through the shared
`executes(..., file_outputs=...)` helper. It removes each output immediately
before every executable invocation and checks that a fresh file contains the
exact bytes. Evidence records the expected length and hash. Harness controls
reject a missing later write and a same-length wrong payload, so an earlier
optimization's output cannot make a broken execution pass.

Malformed UTF-8 file cases distinguish raw ingress from strict character
validation. They observe the byte length after the reader returns, before the
character operation fails, or use a separate successful check of every raw byte.
An expected decoder diagnostic alone could also pass if the reader failed early.
The independent stage-oracle controls retain both the old false passes and the
corrected rejections of a runtime variant that validates inside `readTextFile`.

Replay one recorded command with:

```sh
python3 tests/test_evidence.py build/test-evidence/RUN/evidence.json --command 0
```

Replay checks the original retained paths and frozen file/tool hashes. It does
not relocate the workspace, reconstruct redirected file descriptors, or rerun
the test's semantic oracle automatically; the manifest records expected outputs
for generated execution cases. Keep the workspace and original compiler/runtime
available. Running a recorded compile/link command can update its recorded output
files, so preserve a copy before experimenting with different inputs.

`tools/reduce-minyar.py` performs bounded line-deletion reduction of a valid
Minyar program using an explicit oracle command (`--oracle`, with `{source}` or
`{llvm}` placeholders). The original and each accepted candidate must compile;
oracle exit zero means the same failure persists. Timeouts/signals abort instead
of counting as useful reductions. Imported `.min` files below the input directory
are snapshotted and preserved beside the output. Imports outside that tree need
a self-contained reproducer first. This tool targets wrong results/runtime
failures, not compiler crashes, and does not claim a globally minimal program.
`make check-reduction-harness` verifies it preserves a controlled compiled-program
mismatch and required definitions, preserves runnable imports after relocation,
rejects a non-reproducing baseline, protects existing reports, and checks the
actual relocated output against the oracle before certifying success.

The [peer roadmap](research/peer-testing-roadmap.md) records the initial research.
The [exhaustive review ledger](research/exhaustive/README.md) is a separate,
ongoing audit; inventory counts are not claims that all tests were read.

## Shared memory contract runner

Run `make check-memory-contracts` to test the current compiler and runtime
with the same fixtures across eager reference counting, bounded cleanup with
system allocation, the fixed pool, and the lazy pool. It runs native and
AddressSanitizer/UndefinedBehaviorSanitizer configurations. This is a separate
entry point for memory work; `make check` still runs the existing project checks.

To test an experimental compiler/runtime pair without installing it:

```sh
python3 tests/memory-contracts.py \
  --compiler /absolute/path/to/candidate-compiler \
  --runtime-source /absolute/path/to/runtime/minyar_runtime.c \
  --level standard --profiles eager system fixed lazy --mode both \
  --output-dir /tmp/minyar-contract-evidence
```

The runtime argument is the C file. Its sibling headers, the compiler executable,
and the shared fixtures are copied into an isolated snapshot before testing.
Run the same command with the baseline pair to compare correctness coverage.

| Level | Coverage |
| --- | --- |
| `smoke` | Existing CLI diagnostics, determinism, language and module compilation, file access, normal output, runtime errors and explicit exit status. |
| `standard` | Smoke plus the eager C ownership model, generated alias programs, independent recursive-type graph model, recursive structures and escaping-reference regressions. Language executions run at both O0 and O2. |
| `extended` | Standard plus general and adversarial compiler regressions and the existing independent bounded-runtime models, including reclamation fairness and pool recovery. |

Use `--budgets 1 32 1024` to exercise multiple bounded-cleanup budgets. The eager
profile has no bounded scheduler and is run once per instrumentation mode.
`--mode native` or `--mode sanitize` selects one mode. `--timeout` sets a limit
per build or test suite; a timeout terminates the suite's process group and
records a failure. Large campaigns may need a higher timeout.

Each run prints a retained evidence directory. `results.json` contains source
hashes, exact commands, environment controls, logs, exit codes, and timeout
results. Smoke LLVM, executables and runtime objects are retained per
configuration. Existing Python suites use temporary cases; their frozen test
sources and recorded generation controls allow replay, but individual case
files are not retained after those suites finish. The runner stops on the
first failure and retains its evidence.

The test runtime requires an empty owner stack on normal return, drains any
deferred reclamation, and checks that only immortal cached objects remain.
This drain exists only in tests and must never ship in the production runtime.
Explicit language exit and runtime errors currently terminate without unwinding;
those paths are checked for their specified output and status rather than
normal-return cleanup. Compiler-arena mode intentionally retains memory and is
outside this runner's cleanup assertions.

Sanitized language tests instrument generated LLVM as well as C runtime code.
The supplied compiler executable itself is not automatically instrumented.
Self-hosting fixed points, compiler sanitization, the launcher wrapper, native
target-platform validation, and performance measurements remain separate checks.
No passing correctness result establishes a maximum wall-clock pause.

`make check-memory-contracts-harness` tests the runner itself. It checks a real
successful smoke run, then verifies that an injected leak, a failing compiler,
and a hanging compiler are rejected with useful evidence. Invalid UTF-8 in a
compiler diagnostic must also produce a retained failure. This small check is
also included in `make check`.

The runner does not execute performance tests or write performance baselines.
It hashes protected performance inputs before and after each run and reports
failure if they change, including changes from concurrent work.

Performance remains a separate evidence category. The September 2026
seven-sample critical-path rerun put LTO configurations at 0.96-1.05x the
checked C++ controls for its arithmetic, book and record fixtures. Ownership
ablations remain less uniform: compared with no reference-count updates or
frees, the current O2 scale-4 runs measured about 15% for borrowed record
calls, 39% for returned aliases, 42% for Unicode temporaries and 145% for
shared List replacement. These are diagnostic ratios rather than release
thresholds; in particular, they keep shared replacement inference open.

## Compiler-selected stack ownership

The combined candidate includes three maintained checks in `make check`:

- `make check-ownership-policy`: ordinary/module compiler budget boundaries,
  malformed-budget rejection, nonleaf fallback, compatible policy reuse, and
  source-edit delta replay through both the direct frontend and public driver.
  Direct replay catches failures that a driver cold retry could otherwise hide.
  Generated programs execute against matching system runtimes. Structural
  checks require stack entry to replace the heap frame without disturbing the
  call-depth guard, and require loop cleanup service only in ownership-using
  functions.
- `make check-stack-ownership`: 36 bounded profile/budget/instrumentation
  configurations plus four eager/arena fallback configurations. An independent
  physical graph oracle checks reference ownership, exact cleanup debt, retained
  returns, nested scopes, storage recovery and rejection of retired stack
  addresses before following them. Native and ASan/UBSan executions require
  actual stack admission whenever eligible.
- `make check-runtime-cache`: actual default builds reuse a complete configured
  runtime, header edits invalidate it, and custom runtime flags stay isolated.

The stack test shares `experiments/memory/production-live-oracle.c`, an existing
maintained fixture. It has no dependency on the archived stack experiments.
For an individual instrumentation mode use
`python3 tests/stack-ownership.py --mode native` or `--mode sanitize`.
The Linux correctness runner includes these three checks and both compiler
fixed points. Correctness under virtualization or instruction translation is
not a latency measurement on native deployment hardware.

## Per-commit platform gates

`.github/workflows/ci.yml` runs on every push and pull request. Linux runs the
isolated correctness/sanitizer evidence harness, macOS runs the portable
compiler/runtime/module suite, and Windows runs that portable suite under
UCRT64. The portable gate includes the byte-identical compiler fixed point,
feature conformance, exact diagnostic snapshots, deterministic grammar fuzzing,
and graceful compiler/program stack exhaustion.

The Linux matrix also runs incremental-module correctness natively and with
sanitizers, temporary-owner admission, compiler slice-cache checks, the memory
contract harness, ownership mutation checks, and both scalar-constructor modes.
After correctness passes, `scripts/check-linux-leaks.py` replays the eligible
runtime fixtures with LeakSanitizer enabled, first verifying that the detector
rejects a deliberate leak. Compiler arenas remain excluded from leak replay.
Linux uploads JSON reports and detailed logs on both success and failure;
each top-level correctness check also prints its result and elapsed time.
Performance and RSS ceilings remain separate from this hosted-runner matrix.

Linux also runs two independent verification jobs. `make check-coverage`
measures [SanitizerCoverage](https://clang.llvm.org/docs/SanitizerCoverage.html)
control-flow edges directly in the self-hosted compiler IR and LLVM source
coverage for runtime lines and branches. It uses matching `opt`, Clang,
`llvm-profdata`, and `llvm-cov` tools; `LLVM_OPT`, `MINYAR_TEST_CLANG`,
`LLVM_PROFDATA`, and `LLVM_COV` can select their paths. The
runner rejects LLVM major-version mismatches and records every selected tool's
identity. Pre-inlining instrumentation uses the selected Clang target triple,
so targetless Minyar IR keeps the host object-format requirements. The
legacy measurement before the runtime header split was 81.48% compiler edges,
76.38% runtime lines, and 58.00% runtime branches. Those numbers describe that
source revision and denominator, not the current coverage. Configured regression
floors are 79%, 72%, and 55% respectively. Each current run aggregates every
instrumented implementation file under `runtime/`, including sibling headers,
and lists its source hash and individual counts. Test harness files are excluded.
Moving implementation into a header must not improve coverage by removing it
from the denominator. Empty profiles or mapped runtime lines fail the gate.
Each run retains a JSON report and raw profiles under
`build/coverage/`; the CI job uploads them even when a floor fails.

The instrumented candidates run the checked arithmetic, scalar conversion, and
parameter optimization suites as well as diagnostics, conformance, generated
programs, and self-compilation. These checks retain their independent value and
failure oracles; collecting coverage does not replace their assertions.
The maintained peer semantic and literal-true loop regressions run in both
instrumentation orders too; the report records that exact suite list.

Compiler edge IDs are assigned before inlining, so copies of the same helper
retain a shared identity for each distinct branch. No helper or safety branch
is excluded. The report also runs the same corpus with instrumentation after
inlining and retains that raw site count and percentage. Both instrumented
compilers must reproduce the ordinary self-hosted fixed point exactly. The 79%
gate applies to distinct edges; raw cloned-site coverage is a separate metric.
`tests/coverage-inlining.py` verifies that one and sixteen calls keep the same
distinct-edge denominator, that both branch arms are measured, and that the raw
measurement still exposes duplication. This matters because inline bounds checks
repeat compiler-internal invariant failures at many call sites.

`make check-mutation-score` discovers comparison and Boolean operators outside
comments and literals across the whole compiler, samples them evenly and
deterministically, then runs diagnostics, conformance, regressions, grammar
fuzzing, compiler hardening, parameter optimization, source-map and symbol-order
units, and module tests against each viable mutant. Internal units receive the mutated source via
`MINYAR_TEST_SOURCE`, as well as the candidate executable; otherwise a unit could
accidentally compile the unmodified implementation and miss the fault. The
same suites must first pass against the baseline compiler. Stillborn mutants
are excluded rather than counted as killed; build timeouts fail an incomplete
campaign. The configured regression floor is 85%. The current campaign score
and denominator are recorded in `build/mutation-score.json`; an earlier 16/16
result predates candidate-selection and baseline-gate fixes and must not be
used as evidence for the strengthened campaign. The
[hardening report](hardening-report.md) records the separate strengthened
campaign and its source-bound evidence.

A campaign with no viable mutants fails even when the score floor is zero,
and records a null score rather than a percentage.
`make check-mutation-score-harness` verifies failed and timed-out baseline checks,
failed and timed-out mutant builds, empty discovery, surviving and killed
mutants, candidate environment propagation and exclusion of stillborn mutants.
It runs before the real mutation-score campaign. Sources, commands, statuses,
logs and the report are also retained under `build/mutation/campaign-*/`.
Symbol-order units compare exhaustive pairs with independent Python string/tuple
ordering, check reflexivity, antisymmetry and transitivity, and verify that the
sorted lookup preserves every input entry. Equal-content distinct strings,
duplicate symbols with different kinds, prefixes and Unicode distinguish these
contracts from checking a few sorted examples. Import regressions combine parent
and local paths with a selected library and same-named package. Both tests were
verified against the exact surviving mutants that exposed their coverage gaps.

A score is evidence about the selected operator mutations, not a probability
that the language or compiler is correct. Survivors require review; equivalent
mutants must not be waived merely because they are difficult to kill.

## Fuzzing

`make check-fuzz` is deterministic and replayable. It honors
`MINYAR_TEST_COMPILER`, `MINYAR_TEST_RUNTIME`, `MINYAR_TEST_CLANG` and
`MINYAR_TEST_LINK_FLAGS`, so candidate, mutation and coverage runs exercise
the selected artifacts. Generated programs must match independent Python
results, exit successfully and produce no stderr at both O0 and O2.

Arithmetic trees cover `+`, `-`, `*`, `/` and `%`. Division truncates toward
zero and remainder is modeled accordingly rather than using Python's floor
division semantics. Intermediate values stay bounded, divisors stay nonzero,
and separate fixtures cover both 64-bit endpoints. Typed programs exercise
records, shared Lists, functions, branches, loops, mutation, Unicode Text,
slices, joins and module graphs. Additional modeled cases cover all ordered
comparisons, short-circuit side effects, loop `break`/`continue`, shifts,
bitwise operations, shared Bytes, unaligned little-endian reads, and exact
Float-to-Integer conversion. Direct arithmetic and identity-function variants
must have identical modeled results, adding a simple metamorphic relation.
This is template-based generation, not a complete language interpreter or a
full arbitrary typed-program generator. O0/O2 both use the same Minyar
frontend and LLVM backend; their agreement is not an independent compiler
implementation.

Every AFL seed in `tests/fuzz-corpus/inputs/` has an oracle in `seeds.json`.
Positive seeds compile and execute at O0/O2 against recorded stdout; rejecting
seeds must return status 1 with a diagnostic. Unlisted or missing seeds fail.
The corpus includes integer boundaries, signed division, side effects, loop
control, packed Bytes and combining/non-BMP Unicode. Hostile generation
contains actual newline and tab characters. The minimized rejecting regression
corpus must be nonempty; success, unexpected statuses and internal failures
all fail its replay.

```sh
python3 tests/fuzz.py --cases 2000 --program-cases 40 --seed 0x20261002 \
  --output-dir /tmp/minyar-fuzz-evidence
python3 tests/fuzz-harness.py
```

Campaign directories retain sources, expected output, emitted LLVM, executables
and `results.json` on success and failure. The report includes compiler/runtime
hashes, seed, counts, exact commands, statuses, timeouts and captured output.
Use a fresh seed for broader nightly exploration and preserve each failing seed
as a focused regression. Subprocesses have limits; timeouts kill the process
group on POSIX or the process tree on Windows. Invalid UTF-8 diagnostics are
escaped into evidence rather than losing the report. The fault-injection harness
checks candidate selection, stderr rejection, rejecting/empty corpora, retained
failure evidence, invalid diagnostic encoding and POSIX descendant cleanup.

Text storage has structural oracles in `tests/runtime-unit.c`: full and nested
slices must share a flattened owning root, tiny slices of large sources must
copy, owned join chains must keep one Text identity with geometric capacity,
and shared join operands must take the copying fallback. The compiler test also
asserts that only owned producer tokens select the consuming join entry point.

Diagnostic locations are captured at token start. The byte-exact corpus covers
lexer, parser, type, encoding, and whole-program failures; every current golden
diagnostic asserts both line and column, including duplicate declarations and
module-compatible location text.

`make check-source-map` independently checks full-width line/column values,
shared Unicode paths, sparse cached origins, and direct/cold/warm/changed-module
diagnostic parity. It instruments location formatting and places a work bound on
successful expression compilation. The tokenizer matrix separately counts Text
reads and conversions, preserving UTF-8 behavior while catching repeated work
that a wall-clock assertion could miss.

`make check-fuzz-coverage` is the coverage-guided layer. It instruments the
self-hosted compiler with AFL++ LLVM mode, enables AddressSanitizer and
UndefinedBehaviorSanitizer, starts from the small corpus in
`tests/fuzz-corpus/`, uses a Minyar token dictionary, and treats both crashes
and hangs as failures. `MINYAR_AFL_SECONDS` controls campaign length; CI runs a
60-second smoke campaign on every commit. A separate nightly one-hour campaign
restores and saves the evolving AFL++ queue so coverage discoveries survive
fresh runners; it can also be dispatched manually with a longer duration within
the runner's six-hour job limit.
Local campaigns reuse `build/afl-findings` through AFL++ auto-resume.

Every crashing input belongs in `tests/fuzz-regressions/` after minimization so
the deterministic and sanitizer suites replay it without AFL++.

## Bounded allocator verification

Buddy resize planning and same-base shrink/grow execution are shared by normal
and discard-resize operations. The lower-buddy relocation needed by
discard-resize is the only specialized path. The profile matrix checks exact
pool recovery, lower-buddy moves, exhaustion diagnostics and sanitizer
poisoning at cleanup budgets 1, 32 and 1024. The lazy-heap matrix separately
checks 64 MiB, 64 GiB and 1 TiB reservations plus reservation and metadata
rollback, natively and under ASan/UBSan.

## Diagnostics and language conformance

`make check-diagnostics` compares complete stderr bytes for every file in
`tests/errors/`, `tests/fuzz-regressions/`, and `tests/diagnostics/cases/`.
Adding a rejecting fixture without its golden file fails the suite. The lexer
accepts a leading UTF-8 byte-order mark and gives an exact line and column for
unsupported non-ASCII identifier characters.

`make check-conformance` executes the feature-indexed programs under
`tests/conformance/` at O0 and O2. Its README maps every section of the language
specification to primary positive evidence and to negative/boundary suites.

## Language linkage

`make check-linkage` checks collisions with libc functions, global data names,
and runtime helpers through the C bootstrap, ordinary compiler, and cold, warm,
and edited module caches. It checks symbol isolation before linking or executing
an artifact, then requires independent output values at O0/O2. Valid previous
schema payloads must rebuild rather than reuse the former linkage ABI.
`check-linkage-sanitize` repeats those paths with generated LLVM instrumentation.
The ordinary compiler case also runs against mutation and coverage candidates.
Source-map mutation checks load the actual mutant source and include large
default-path storage, sparse path gaps/resets, full-width positions, and cached
origin invariants.

## Checked failure paths

Generated functions check the current thread's actual stack bounds on Linux,
macOS, and Windows, reserving enough stack to report an error. Platforms where
bounds are unavailable use a conservative 32,768-call fallback. A 5,000-deep
program must run; compiler or program exhaustion must exit with
`Minyar stopped: the program exceeded the maximum call depth.` rather than a
signal.

Both native and sanitized compilers are covered. The sanitizer build instruments
the self-hosted second-stage LLVM, preserving its runtime call-depth guards.
The bootstrap emitter does not emit those guards and is not the sanitizer build
input. `check-stack-overflow-sanitize` checks deeply nested parentheses and
100,000 unary operators, plus safe and exhausting generated-program recursion.

`make check-statement-nesting` requires all nine results from a 50,000-branch
conditional chain, including an imported function. It also checks deep then
blocks, while loops, exact diagnostics, and scoped reference lifetimes. Ordinary
cases run at O0/O2; the imported large chain and deep then/while executions use
O0. A separate 20,000-loop case checks frontend success and LLVM parsing without
native code generation, whose nested-loop processing is expensive at that depth.
`check-statement-nesting-sanitize` instruments both compilers and the generated
programs; `check-statement-nesting-ownership` checks normal-return scope and
module cases with the ownership oracle. These run through the portable,
sanitizer, and ownership gates respectively.

Functions that allocate at least 4,096 control-flow labels receive `noinline`
to bound LLVM's function-cloning cost. After normal statement validation, a
complete chain comparing one unassigned Integer parameter against increasing
nonnegative Integer literals, with nonnegative literal results and fallback,
becomes a sorted constant table and a bounded binary search. This preserves
every case while avoiding LLVM's expensive processing of enormous branch and
return graphs. Imported tables use the module's stable literal namespace.

The compiler arena uses a 32-byte Text prefix because its storage lives until
process exit. Ordinary Text objects and emitted literal layouts retain their
ownership fields. `check-compiler-slice-cache` verifies the compact field offsets
and reads actual full-size LLVM literals, including Unicode index updates,
slicing, and joining, at O0/O2 with sanitizers and collision mutation controls.

Runtime printing checks writes and flushes, ignores SIGPIPE where available,
and reports closed stdout through the normal error channel. File regressions
cover directory reads, invalid UTF-8, directory/nonexistent-parent writes and
creation failures. Windows file sizing uses `_fseeki64`/`_ftelli64`; other
targets retain their native 64-bit `long` path, with explicit `LLONG_MAX` and
`SIZE_MAX` checks before allocation. The Windows CI gate creates an NTFS sparse
file above 2 GiB and checks the runtime's factored length probe directly, so it
does not need a multi-gigabyte allocation or disk image.


## How the testing strategy compares with established compiler practice

The engineering target is several complementary oracles and gates whose own
failure behavior is tested. Suite counts and one mutation score do not establish
that Minyar tests better than a mature compiler.

| Reference practice | Minyar application |
| --- | --- |
| [Swift contribution guidance](https://www.swift.org/contributing/) requires a regression for fixes and tests close to the affected abstraction, reduced to the relevant behavior. | First add an exact failing language/runtime/harness case, implement the fix, and keep the minimized case in the appropriate portable gate. |
| [Swift's testing guide](https://github.com/swiftlang/swift/blob/main/docs/Testing.md) separates primary, validation, unit, long, and stress suites and includes real projects. | Portable checks, the full sanitizer/model matrix, nightly campaigns, and actual package/game linking remain distinct gates. Passing a small unit suite cannot substitute for integration evidence. |
| [Rust compiletest](https://rustc-dev-guide.rust-lang.org/tests/compiletest.html) uses distinct diagnostic, incremental, codegen, MIR and general build suites. | Keep diagnostic bytes, executable semantics, emitted LLVM invariants, incremental behavior and driver failures separately observable. |
| [TypeScript's compiler tests](https://github.com/microsoft/TypeScript/blob/main/CONTRIBUTING.md) keep generated local baselines separate from accepted reference baselines. | Exact diagnostic goldens and independently modeled output remain explicit review contracts. Never accept a new baseline merely to make a failing compiler or performance gate pass. |
| [Go's compiler script runner](https://go.googlesource.com/go/+/master/src/cmd/compile/script_test.go) replaces the installed compiler with the actual candidate under test. | Candidate selection is explicit throughout fuzzing, sanitizers, mutation, and module tests; injected wrong candidates verify that overrides are actually honored. |
| [Go fuzzing](https://go.dev/doc/security/fuzz/) replays seed inputs in ordinary tests and retains minimized failures as regressions. | The versioned seed manifest requires exact output/status oracles, every retained regression is replayed without AFL++, and nightly discovery preserves its queue. |
| [LLVM testing guidance](https://llvm.org/docs/TestingGuide.html) distinguishes unit, focused regression and whole-program reference-output tests. | Runtime models, minimized compiler regressions and O0/O2 language executions test different failure classes. |
| [Zig language testing documentation](https://ziglang.org/documentation/master/#Zig-Test) describes executable test declarations, failure status and leak-aware allocation checks. | Require exact process status and output, and supplement language behavior with ownership/allocator models and instrumented cleanup assertions. |
| [Csmith research](https://users.cs.utah.edu/~regehr/papers/pldi11-preprint.pdf) generates programs with defined behavior for differential testing; [EMI research](https://web.cs.ucdavis.edu/~su/emi-project/) compares equivalent program variants. | Bounded arithmetic, nonzero divisors and exact conversions make output comparisons meaningful; direct/function-wrapped variants complement Python semantic results. More independent transformations remain a coverage opportunity. |

For every compiler or runtime change, record the red command and expected
failure, then the passing command after the fix. Keep a focused regression as
well as broader generated stress when the bug depends on ownership, nesting
or optimization. Add a harness fault injection when a failure could otherwise
be mistaken for success, a stillborn mutation or missing evidence.

Current coverage reports measure compiler edges and the eager runtime files
actually compiled into the instrumented binaries. Bounded/pool allocation,
compiler-arena ownership and optional graphics/native backends have separate
correctness suites; this report does not claim coverage for their uncompiled
branches. Header aggregation preserves the active configuration's denominator,
but it cannot count preprocessing paths that were not built. Likewise, AFL
crash/hang discovery does not detect wrong code by itself: valid-program
semantic and metamorphic campaigns must remain separate gates. Broader typed
AST generation, richer equivalent variants and multiple runtime/backend/profile
coverage campaigns are future extensions, with their results to be reported
per configuration rather than mixed into a single flattering percentage.

## Host test source catalogue

`make check-suite-catalogue` recursively discovers every `.py`, `.c`, `.h`, and
`.sh` under `tests/` and requires exact agreement with `tests/suite-catalogue.json`.
New nested sources, duplicate declarations, stale entries and missing consumers
fail the gate. Each entry states whether it is a suite, support module, fixture,
manual tool or an explicitly ungated probe. Consumer references are checked as
text; this does not prove execution or Make dependency reachability. Minyar
fixtures and data/oracle files remain the responsibility of their own harnesses.
The documented incremental-module RSS measurement is currently manual.

The catalogue review found four existing C probes without runners.
`make check-scalar-cleanup-probes` now runs them with C assertions enabled,
natively and under ASan/UBSan at cleanup budgets 1, 32 and 1024. They check scalar
owner counts, retained aliases, cleanup work bounds and scalar setter bounds.
These probes use the system heap and bounded reference-count cleanup. Their
transcript comparison checks native/sanitizer agreement; it is not an independent
reference scheduler. Failures retain command, source and output evidence.

The peer regression gates execute four suites: `peer-regressions.py`,
`peer-cpp-java-js.py`, `peer-rust-go-zig.py`, and
`peer-python-swift-ruby-lua.py`. `check-peer-optimizations` runs executable cases
at O0/O2/O3/Os; compile-only cases stay frontend checks. `check-peer-sanitize`
uses the sanitized compiler and production runtime at O0/O2, and
`check-peer-ownership` selects the validated lifetime/cleanup cases. The peer
manifest discovers direct `CompilerTestCase` subclasses in `peer-*.py` so omitting
an entire suite from its declarations fails validation.

Unicode filename vectors preserve upstream platform guards. Normalization-sensitive
vectors excluded on macOS remain unresolved until tested on an applicable host.
Output files are removed before each optimization run and their bytes are checked
immediately afterward, preventing stale outputs from hiding missing writes.
