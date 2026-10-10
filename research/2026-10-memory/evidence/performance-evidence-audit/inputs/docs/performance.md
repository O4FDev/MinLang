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
[hardening report](hardening-report.md) for current evidence.

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

## Modules

```sh
make check-module-performance
make check-incremental-module-performance
python3 tests/incremental-module-performance.py --link --sizes 400 --shapes wide
python3 tests/incremental-module-memory.py
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
[hardening report](hardening-report.md) retains ratios and confidence intervals.
System-allocation LTO List work still has a measured 1.02% CPU gap and more
retired instructions. Its disassembly identifies memory-effect/alias information
as remaining work; faster default CPU measurements do not establish lower
instruction counts. Preserve this distinction when reporting results.
