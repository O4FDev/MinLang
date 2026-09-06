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
[`tests/self-compile-budget.py`](../tests/self-compile-budget.py) were calibrated
on an Apple M-series laptop. They were reset after full token columns, stack
guards, ownership-transfer lowering, and the expanded compiler/runtime surface
changed the measured workload. Before the sequential Unicode cursor, isolated
runs retired 67.6--69.8 million instructions, peaked at 9.3 MiB, and measured a
25--26 ms CPU 90th percentile. The cursor reduced two repeated CPU measurements
to 14.6--14.9 ms. Current ceilings are 75 million instructions, 10 MiB, 22 ms
CPU and 25 ms wall time.
For comparison, a clean build of the preceding repository revision retired
38.0 million instructions on the same host, already above the former 32 million
ceiling. This is an explicit baseline change, not a claim that the added work
is free; the fixed ceilings continue to fail subsequent regressions.

The budget test runs outside the development limiter because background
priority changes absolute timings. It takes the 90th percentile across batches;
shared-host load can still affect results. Most other checks run under
`scripts/with-limits.sh`, with background priority and CPU, memory, and output
limits. Avoid parallel test jobs when comparing timings.

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
