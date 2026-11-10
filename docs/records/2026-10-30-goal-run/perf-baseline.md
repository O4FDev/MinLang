# Minyar performance baseline against C, C++ and Rust

Suite: `benchmarks/compare/` (21 programs), measured at commit `98152d6f0`
(branch `goal/2026-10-30-visible`, v2 base `3832f4373`) with
`python3 benchmarks/compare/run.py --jobs 3 --json build/compare-baseline.json`.

- Host: box B, Linux x86-64, 4 vCPU, shared; measurements held `/home/agent/bench.lock`.
- Metric: retired instructions (cachegrind `--cache-sim=no`, all threads), full workload from each `sizes`.
  Instruction counts are deterministic for single-threaded programs; the two parallel programs
  were run with 4 threads and their counts include any spinning by idle workers.
- Ratio = Minyar Ir / min(C, C++, Rust Ir). Every program printed byte-identical output in all four languages.
- Toolchains: clang 23.1.3 (`-O3 -march=x86-64-v3`, C++ `-std=c++20`), rustc 1.99.1
  (`-C opt-level=3 -C target-cpu=x86-64-v3 -C codegen-units=1 -C lto=fat -C panic=abort`),
  valgrind 3.22.0, Minyar `./minyar --release` (default target CPU; the launcher only applies
  `-march` when `MINYAR_TARGET_CPU` is set, so Minyar code is baseline x86-64 here).

| program | identical | Minyar Ir | C Ir | C++ Ir | Rust Ir | ratio | fastest |
|---|---|---:|---:|---:|---:|---:|---|
| exprparse | yes | 42,139M | 1,487M | 3,311M | 1,890M | 28.34 | c |
| json | yes | 14,452M | 876M | 3,894M | 1,475M | 16.50 | c |
| treewalk | yes | 38,265M | 2,789M | 3,068M | 3,242M | 13.72 | c |
| httpparse | yes | 17,566M | 2,301M | 2,942M | 1,459M | 12.04 | rust |
| config | yes | 5,410M | 663M | 1,614M | 999M | 8.16 | c |
| inventory | yes | 6,893M | 1,361M | 1,578M | 1,075M | 6.41 | rust |
| logstats | yes | 5,757M | 909M | 1,250M | 1,653M | 6.33 | c |
| bytecode | yes | 9,770M | 1,614M | 3,534M | 4,182M | 6.05 | c |
| textops | yes | 5,665M | 1,179M | 972M | 1,646M | 5.83 | cpp |
| tokenizer | yes | 6,024M | 1,050M | 2,445M | 1,135M | 5.74 | c |
| grid | yes | 10,294M | 1,914M | 2,010M | 2,586M | 5.38 | c |
| sortrows | yes | 3,300M | 1,549M | 649M | 840M | 5.09 | cpp |
| intmap | yes | 3,554M | 849M | 1,184M | 792M | 4.49 | rust |
| service | yes | 3,232M | 1,709M | 759M | 1,178M | 4.26 | cpp |
| wordfreq | yes | 4,221M | 1,035M | 1,272M | 1,220M | 4.08 | c |
| nbody | yes | 4,035M | 1,152M | 1,094M | 1,107M | 3.69 | cpp |
| matrix | yes | 2,938M | 857M | 869M | 877M | 3.43 | c |
| sorttext | yes | 3,396M | 1,599M | 1,306M | 1,026M | 3.31 | rust |
| orders | yes | 504M | 199M | 188M | 206M | 2.68 | cpp |
| par-mandel | yes | 2,247M | 1,445M | 1,453M | 1,448M | 1.56 | c |
| par-reduce | yes | 2,129M | 2,303M | 2,306M | 2,300M | 0.93 | rust |
| **geomean** | | | | | | **5.32** | |

## Where Minyar's instructions go

Share of Minyar Ir by function class, from the same cachegrind runs. rc/frames is
`minyar_rc_*`, `rc_bounded_*` and `minyar_record_set_reference`; alloc/free is the
heap and `malloc`/`free`; user code is `main` and `.minyar.*` functions, where
inlined checks and helpers also land.

| program | rc/frames | alloc/free | unicode | text rt | map/set rt | list rt | libc mem | parallel rt | user code | other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| bytecode | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 100 | 0 |
| config | 36 | 7 | 0 | 22 | 16 | 0 | 3 | 0 | 15 | 1 |
| exprparse | 67 | 5 | 0 | 3 | 0 | 0 | 0 | 0 | 25 | 0 |
| grid | 0 | 1 | 0 | 0 | 0 | 0 | 3 | 0 | 96 | 0 |
| httpparse | 15 | 5 | 52 | 15 | 4 | 0 | 2 | 0 | 4 | 2 |
| intmap | 2 | 4 | 0 | 0 | 75 | 6 | 1 | 0 | 11 | 1 |
| inventory | 34 | 2 | 0 | 0 | 0 | 3 | 4 | 0 | 55 | 1 |
| json | 44 | 10 | 0 | 8 | 1 | 1 | 2 | 0 | 32 | 2 |
| logstats | 19 | 11 | 0 | 43 | 12 | 0 | 7 | 0 | 4 | 6 |
| matrix | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 100 | 0 |
| nbody | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 94 | 0 |
| orders | 0 | 6 | 0 | 0 | 0 | 10 | 1 | 0 | 83 | 0 |
| par-mandel | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 100 | 0 |
| par-reduce | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 100 | 0 |
| service | 24 | 11 | 0 | 53 | 4 | 0 | 2 | 0 | 6 | 1 |
| sortrows | 1 | 0 | 0 | 0 | 0 | 38 | 8 | 0 | 53 | 0 |
| sorttext | 7 | 2 | 0 | 9 | 0 | 41 | 15 | 0 | 25 | 1 |
| textops | 25 | 9 | 0 | 42 | 2 | 0 | 6 | 0 | 11 | 5 |
| tokenizer | 14 | 9 | 0 | 9 | 17 | 0 | 4 | 0 | 44 | 3 |
| treewalk | 58 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 39 | 0 |
| wordfreq | 11 | 7 | 0 | 25 | 36 | 1 | 12 | 0 | 6 | 3 |

## First-pass root causes of the five worst ratios

Profiles: `benchmarks/compare/profile.sh NAME N` (callgrind on a `-g` release build)
at exprparse 100000, json 30000, treewalk 30000, httpparse 100000 and config 50000.

| program | ratio | main class | evidence |
|---|---:|---|---|
| exprparse | 28.3 | RC traffic: bounded incremental reclamation | `rc_bounded_service` 38% self, entered ~60 times per input line (~530 Ir each); all rc/frames functions 67%. Each line's Expr tree, Result wrappers and Text slices die at once and are retired 32 units per poll. `--memory-profile eager` cuts Minyar Ir by 57% (ratio 12.3). |
| json | 16.5 | RC traffic, then the stdlib parser | `rc_bounded_service` 26%, rc/frames 44%, allocation 10%. The `json` library allocates a Value record and member Lists per value and parses numbers through the decimal runtime. Eager profile: −36% (ratio 10.6). |
| treewalk | 13.7 | RC traffic: per-call frame protocol | `minyar_rc_release` 20%, `minyar_rc_leave` 20%, `minyar_rc_enter` 8%, `rc_bounded_service` 7%. Every recursive `evaluate`/`execute` call enters a frame, registers match-bound payloads as owned locals and releases them on leave, though the tree is never mutated. Eager profile: −53% (ratio 6.4). |
| httpparse | 12.0 | Stdlib algorithm | `unicode.lowercased` is 57% inclusive: binary searches of the case tables for every scalar, with no ASCII fast path. The peers use an ASCII tolower; Text has no ASCII case API. Without it, the rest is about 4x Rust: RC/reclamation 15%, Text runtime 15%. |
| config | 8.2 | Mixed | rc/frames 36%, Text runtime 22% (per-line `trim`/`slice`/`split` results), Map 16%. With no single-probe optional `Map` lookup, the idiomatic `if m.has(k) { m[k] }` hashes twice. Eager profile: −26%. |

## Build-setting sensitivity (same programs, Minyar only)

| setting | effect |
|---|---|
| `--memory-profile eager` | exprparse −57%, treewalk −53%, json −36%, config −26%, httpparse −8% |
| `MINYAR_TARGET_CPU=x86-64-v3` | matrix 3.43 → 1.12 (AVX2 vectorisation), par-mandel 1.56 → 1.21, nbody 3.69 → 3.43; bytecode, grid, orders and exprparse unchanged |

The references build with `-march=x86-64-v3`, but the default Minyar release build targets baseline x86-64.
The table above uses the default Minyar build.
