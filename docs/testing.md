# Shared memory tests

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

Linux also runs two independent verification jobs. `make check-coverage`
measures SanitizerCoverage control-flow edges directly in the self-hosted
compiler IR and LLVM source coverage for runtime lines and branches. The
current measured values are 81.48% compiler edges, 76.38% runtime lines, and
58.00% runtime branches; regression floors are 79%, 72%, and 55% respectively.
Each run retains a JSON report and raw profiles under
`build/coverage/`; the CI job uploads them even when a floor fails.

`make check-mutation-score` discovers comparison and Boolean operators outside
comments and literals across the whole compiler, samples them evenly and
deterministically, then runs diagnostics, conformance, regressions, grammar
fuzzing, and module tests against each viable mutant. Stillborn mutants are
excluded rather than counted as killed. The current 16-mutant score is 100%
(16/16), with an 85% regression floor and a machine-readable
`build/mutation-score.json`.

## Fuzzing

`make check-fuzz` is deterministic and replayable. In addition to hostile byte
strings and arithmetic oracles, it generates typed full-language programs with
records, Lists, functions, calls, branches, loops, mutation, Unicode Text,
slices, joins and module graphs. Generated programs execute at O0 and O2.

Text storage has structural oracles in `tests/runtime-unit.c`: full and nested
slices must share a flattened owning root, tiny slices of large sources must
copy, owned join chains must keep one Text identity with geometric capacity,
and shared join operands must take the copying fallback. The compiler test also
asserts that only owned producer tokens select the consuming join entry point.

Diagnostic locations are captured at token start. The byte-exact corpus covers
lexer, parser, type, encoding, and whole-program failures; every current golden
diagnostic asserts both line and column, including duplicate declarations and
module-compatible location text.

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

## Checked failure paths

Generated functions check the current thread's actual stack bounds on Linux,
macOS, and Windows, reserving enough stack to report an error. Platforms where
bounds are unavailable use a conservative 32,768-call fallback. A 5,000-deep
program must run; compiler or program exhaustion must exit with
`Minyar stopped: the program exceeded the maximum call depth.` rather than a
signal.

The production compiler is covered by this gate. An AddressSanitizer build can
consume substantially more stack in a parser function's instrumentation
prologue, before the called function reaches Minyar's entry check. Pathological
nesting may therefore end in AddressSanitizer's own stack-overflow report; it is
useful sanitizer evidence, but is not treated as the portable user diagnostic.

Runtime printing checks writes and flushes, ignores SIGPIPE where available,
and reports closed stdout through the normal error channel. File regressions
cover directory reads, invalid UTF-8, directory/nonexistent-parent writes and
creation failures. Windows file sizing uses `_fseeki64`/`_ftelli64`; other
targets retain their native 64-bit `long` path, with explicit `LLONG_MAX` and
`SIZE_MAX` checks before allocation. The Windows CI gate creates an NTFS sparse
file above 2 GiB and checks the runtime's factored length probe directly, so it
does not need a multi-gigabyte allocation or disk image.
