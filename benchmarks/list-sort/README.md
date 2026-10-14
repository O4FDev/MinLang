# Stable sorting peer fixture

Run on an otherwise idle Linux Boat sandbox with the built core and callback
frontends, Rust and Swift available:

```sh
make build/minyarc build/minyarc-callbacks build/tooling/benchmarks/list-sort/run
./build/tooling/benchmarks/list-sort/run --lock /home/user/ws3/build.lock --prepare-only
(flock 9 && ./build/tooling/benchmarks/list-sort/run --lock /home/user/ws3/build.lock --run-prepared --repeats 5) 9>/home/user/ws3/build.lock
```

The runner fixes CPU affinity, rejects other active WS3 build jobs, rotates
peer order with a fixed seed, verifies independently computed order/stability
checksums, and saves commands, toolchain versions and raw observations.
Timings cover sorting; fixture construction, loading and checksum checks are
outside the timed interval. All Minyar fixtures use the system heap. The Text
input contains two million actual SHA256 hexadecimal hashes, with duplicate
values. Record sorting uses the generated signed comparator callback.

The retained 2026-10-12 run has one warmup and five measured repetitions per
peer/workload, 72 observations including warmups:

| Workload | Minyar | Rust | Swift | Python |
|---|---:|---:|---:|---:|
| 262,144 Integers | 5.215 ms | 2.827 ms | 8.774 ms | 21.490 ms |
| 262,144 records by key, stable | 54.438 ms | 2.833 ms | 4.094 ms | 20.558 ms |
| 2,000,000 SHA256 Text values | 0.669 s | 0.672 s | 2.237 s | 0.864 s |

All peer checksums agree. The callback record path is considerably slower
than the peer native comparators; the Text path is close to Rust on this
fixture. These measurements describe the new API and different peer layouts.
They do not qualify the separate existing-application <=1% regression gate.
Raw receipts and source/artifact hashes are in `evidence/ws3-sort-20261012/`.
Native macOS/Windows and the full common workload gate remain pending the
integrator's admitted platform routes.
