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
on an Apple M-series laptop. Recorded runs have exceeded these limits.

The budget test runs outside the development limiter because background
priority changes absolute timings. It takes the 90th percentile across batches;
shared-host load can still affect results. Most other checks run under
`scripts/with-limits.sh`, with background priority and CPU, memory, and output
limits. Avoid parallel test jobs when comparing timings.

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
