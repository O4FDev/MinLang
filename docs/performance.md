# Performance testing

Frontend tests measure source-to-LLVM compilation. Complete-build tests also
include Clang compilation and linking.

```sh
make check-performance
make check-scaling
make check-budget
```

`check-performance` checks compiler fixed-point output, measures self-compilation
and generated programs, and compares workloads at different sizes. Measurements
are written to `build/performance.json`. `check-scaling` covers large declaration
sets, late-bound calls, and module graphs.

## Local baselines

```sh
python3 tests/performance.py --save-baseline
```

This saves `build/performance-baseline.json`. Later runs fail when measurements
exceed the configured tolerance. Compare runs on the same host with the same
build configuration.

## Absolute compiler budget

`check-budget` enforces fixed ceilings on self-compilation wall time, CPU time,
peak memory, and retired instructions. The ceilings in
[`tests/self-compile-budget.py`](../tests/self-compile-budget.py) remain
75 million instructions, 10 MiB, 22 ms CPU, and 25 ms wall time. They were
calibrated against an earlier, smaller compiler on an Apple M-series laptop.
They are regression targets, not a statement that the current branch passes.

The October hardening review reconstructs the starting compiler and runtime
instead of comparing against old documentation. That branch already exceeded
the instruction and memory limits. Typed source positions defer diagnostic
formatting, lexer reads reuse known characters, and direct buffer writes remove
trivial wrappers. Cold stack-bound initialization and checked LLVM success paths
reduce runtime work while retaining the error and ownership contracts.

The latest 50-sample compiler campaign measures 72.347 million median retired
instructions and 9.281 MiB maximum RSS. On each compiler's own source, CPU falls
from 17.733 ms to 7.275 ms; identical-original-source results are recorded
separately. The independent 3×100-run budget gate also passes: 9.16 ms wall p90, 7.65 ms
CPU p90, 9.3 MiB maximum RSS, and 71.88 million instructions. Its original
ceilings and batch method are unchanged. See the
hardening report for current evidence.

The budget test runs outside the development limiter because background
priority changes absolute timings. It takes the 90th percentile across batches;
shared-host load can still affect results. Most other checks run under
`scripts/with-limits.sh`, with background priority and CPU, memory, and output
limits. Avoid parallel test jobs when comparing timings.

The public launcher's first-use bootstrap keeps those resource caps and low CPU
priority, but does not add the macOS background scheduling class. This prevents
an interactive cold build from starving behind unrelated background indexing
or backups. Bulk development checks and fuzz campaigns retain their background
policy; bootstrap invoked by an already throttled parent inherits that context.

The previous-v2 comparison retains the original and measured sources with their
hashes. When the previous source uses the removed file and argument builtins,
`prepare-compiler-budget.py` renames those calls and supplies native shims, keeping
streamed output. It leaves literals and the previous frontend rules intact. Both
compiler roles receive the identical adapted source, library arguments, runtime,
and optimization flags. The compatibility report records every renamed API;
the measured result therefore compares the previous frontend after API adaptation.

## Known release-build cost

In the September 2026 release-build fixture, the larger incremental runtime IR
raised complete release-build CPU by 16.5% because Clang optimizes and links it
with each program. Runtime artifact reuse already removed repeated C compilation;
further improvement requires separating runtime optimization from final LTO and
must be evaluated alongside application performance. This is a retained tuning
target, not a claim that the added ownership machinery is free.

## Ownership ablations

The measured 15% gap on borrowed record calls is not evidence of a missing
retain/release pair: readonly parameters already borrow their caller-owned
value and omit an ownership frame. That ablation also removes ordinary call and
stack-safety costs. Shared List replacement remains the expensive case because
the compiler cannot consume a value while another live alias exists. The new
direct Text self-replacement transfer is a deliberately narrow reuse inference;
broader borrow and last-use inference remains a measured optimization target.

## Scope ownership experiment

The direct compiler's `--scope-owners` mode removes all legacy ownership-frame
calls from the measured 721-function compiler. On Linux x86_64 with LLVM 23.1.2,
seven retained hardware-counter samples per executable measured 3,726,245,596
median eager instructions versus 4,710,602,580 for the same-source legacy
control: a 20.90% reduction. The corresponding incremental experiment fell from
8,692,398,963 to 3,436,339,021 instructions, a 60.47% reduction. Its explicit
per-cell release sequence has the different cleanup contract documented in
[runtime memory](runtime-memory.md#scope-ownership-lowering); it is not the
launcher's default bounded lowering.

Arena measured 1,188,040,017 instructions with scope lowering. A subsequent
inline eager release path reduced the same scope compiler from 3,726,245,042
to 2,873,927,153 median instructions, another 22.87%. Its matching arena measured
1,188,040,249, giving 2.4191 times arena. An unmodified runtime rebuilt through the prototype's exact path differed
from the saved eager control by only 144 instructions. All 32 follow-up outputs
matched the same frozen LLVM. The counters and runtime/header identities are in
[`frames-inline-release.json`](../experiments/memory/frames-inline-release.json).
These current-source Linux counts cannot be compared directly to earlier ARM
compiler campaigns.
All 48 executions, including warmups and legacy controls, produced exactly the
frozen original compiler's LLVM bytes. Source, LLVM, runtime and executable
hashes, every observation and the complete flags are retained in
[`frames-ownership.json`](../experiments/memory/frames-ownership.json).

Adjacent plain-borrow coalescing then reduced eager instructions from
2,873,927,000 to 2,655,982,553, a further 7.58%. Matching arena counts were
1,188,040,852 and 1,188,040,574, giving 2.2356 times arena. Both same-source
722-function scope modules have no
legacy frame calls or fallbacks. Coalescing removes 532 temporary cells,
retains and releases while preserving lasting owners and adding 15 return
polls. All 32 executions match the same frozen original LLVM, with continuous,
unscaled counters. This campaign uses one fresh output filename for all four
executables. Counts, every observation and input/runtime/executable identities
are in [`frames-borrow-coalescing.json`](../experiments/memory/frames-borrow-coalescing.json).

Removing a plain projected Text borrow used only by the next equality call
reduced eager instructions from 2,655,982,210 to 2,367,788,224, another 10.85%.
The fresh matching arena counts were 1,188,040,675 and 1,188,611,354, a 0.048%
increase. Eager now reaches 1.9921 times arena; the 1.2-times target remains
unmet. Both same-source 725-function modules have no legacy frame calls or
fallbacks. The pass removes 520 temporary cells and retains, and 869 cleanup
releases, while preserving service with 364 affected-function return polls.
All 32 executions reproduce the frozen original LLVM with continuous unscaled
counters. The new campaign output filename is shared by all four executables;
the reported reduction compares only its fresh matching controls. Complete
observations and identities are in
[`frames-compare-borrows.json`](../experiments/memory/frames-compare-borrows.json).

Extending the same lifetime proof to allocating Text join/search helpers showed
no self-compile instruction gain. Its eager median was 2,367,902,557 versus
2,367,788,397 for the fresh same-source control, a 0.00482% increase. Matching
arena medians were 1,188,611,457 and 1,188,611,839, respectively; candidate eager
is 1.9922 times arena. The pass removes 66 static cells/retains and 67 releases
and preserves service with 48 additional exit polls, but static counts do not
establish a performance improvement. Both 725-function modules have zero legacy
calls/fallbacks; all 32 outputs match the frozen original LLVM and all counters
remain continuous and unscaled. The campaign uses fresh matching controls and
one shared output filename. Complete observations and identities are in
[`frames-runtime-borrows.json`](../experiments/memory/frames-runtime-borrows.json).

[`frames-instructions.py`](../experiments/memory/frames-instructions.py) measures
Linux x86_64 user-space hardware instructions through `perf_event_open`. It
attaches to a stopped child, enables at exec, excludes the Python parent and
kernel, drops inherited sudo privileges in the compiler child, and rejects
multiplexed or unavailable counters. Permission to open hardware counters is
required; the study used `sudo -n` without changing kernel settings. One warmup
precedes retained samples and execution order alternates. Link identical legacy
and scope compiler LLVM against each runtime with the recorded ThinLTO flags,
freeze one input and library, then supply the executables as repeated
`--profile NAME=PATH` arguments. The directory must contain the measured
`compiler-stage2.ll`; `--input`, `--library` and `--report` select the artifacts.

## Modules

```sh
make check-module-performance
make check-incremental-module-performance
make build/tooling/tests/incremental-module-performance build/tooling/tests/incremental-module-memory
./build/tooling/tests/incremental-module-performance --link --sizes 400 --shapes wide
./build/tooling/tests/incremental-module-memory
```

The ordinary module benchmark measures fresh frontend processes for chains,
wide imports, and shared dependencies. It writes `build/module-performance.json`.
The incremental benchmark includes the cache driver and exercises unchanged
builds, source edits, interface edits, and cold caches. Add `--link` to include
native compilation and linking.

Memory measurements report maximum child-process RSS, rather than the sum of
simultaneous parent and child memory. See [incremental builds](incremental-builds.md)
for cache behavior and platform limits.

## Comparing generated code with C++

`experiments/memory/critical-path-study.py` checks arithmetic, indexed List work,
and record access against independent Python results and equivalent checked C++.
Use `--measure --count 5000000 --samples 31 --output results.json` for a local
comparison after correctness passes. Keep the machine idle during measurement.
One explicit warm-up pair precedes the retained samples; execution order then
alternates between languages. Setup and complete teardown are outside the
timed function and remain subject to separate correctness and allocation checks.

The report retains every measured observation, each language's median CPU time,
and the median of adjacent Minyar/C++ CPU ratios. These two ways of summarizing
ratios can differ when host conditions change, so both remain visible. Ratios
below one favor Minyar. A deterministic 95% percentile bootstrap resamples
complete pairs; its seed, sample count, full range, and method accompany the
interval. The interval assumes independent pairs and cannot account for an
unobserved workload or sustained host drift. It is evidence, not a timing gate
that can be made green by discarding inconvenient samples.

The October final default-build measurements close the earlier arithmetic,
record, and indexed-List CPU gaps on the maintained workloads. The scalar study
adds shifts, Unicode scalar conversion, Float-to-Integer and abs/clamp; the
hardening report retains ratios and confidence intervals.
System-allocation LTO List work still has a measured 1.02% CPU gap and more
retired instructions. Its disassembly identifies memory-effect/alias information
as remaining work; faster default CPU measurements do not establish lower
instruction counts. Preserve this distinction when reporting results.
