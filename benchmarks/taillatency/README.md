# Request tail latency while dropping a cache generation

`cache.min`, `cache.rs` and `cache.go` run the same request loop: each request
builds 200 sessions (a Text, a four-Integer List and an Integer) for the next
cache generation and reads 64 sessions from the current one. Every 1000
requests the generations swap, dropping 200,000 sessions. Output is the
per-request latency distribution in nanoseconds.

```sh
benchmarks/taillatency/run.sh 3                          # closed loop
TAIL_INTERVAL_NS=100000 TAIL_VARIANTS="minyar-k32 minyar-k32-idle minyar-eager \
  minyar-k1024-idle rust rust-defer go" benchmarks/taillatency/run.sh 3   # 100 µs arrivals
```

`TAIL_SLOW_NS=N` prints each request at or above N ns as
`position-in-generation@microseconds`; `TAIL_SLOW_TIMES=1` adds
`[monotonic-start+duration]` so profiler samples can be matched to requests. `TAIL_IDLE=1` spends idle gaps on queued
cleanup through `idle.c`; `TAIL_DEFER=1` makes Rust drop the old generation on a
background thread.

Measured 2026-10-25 (Boat box, 8 vCPU Linux 6.8 VM, two pinned CPUs, 100 µs
arrivals, 20,000 requests, three rounds) — p99.9 service time:
Minyar K32 7.3–8.9 ms, K32 with idle cleanup 7.0–8.1 ms, eager 8.3–10.4 ms,
K1024 with idle cleanup 0.46–1.4 ms (max 20–27 ms); Rust 2.4–2.6 ms, Rust
background drop 0.9–2.1 ms; Go 0.54–0.94 ms. Today this is a loss for Minyar:
the K32 runtime pays the dropped generation inside the next eight requests, and
every profile shows a further ~10 ms request soon after a swap: glibc's
`malloc_consolidate` merging the ~600k just-freed chunks on the first
allocation that misses its fast caches (18% of user CPU with libc symbols;
small reallocs then take 0.6–55 ms). Preloading jemalloc or mimalloc does not
fix p99.9, because the eager swap request's own ~600k frees (~7 ms) dominate.
