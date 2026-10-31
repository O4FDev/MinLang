# Minyar goal status (2026-10-31, before the 09:40 UTC box shutdown)

Goal: find exactly why Minyar is slower than heavily optimised C/C++/Rust and fix it in the compiler, runtime and
stdlib; build the features other projects need (parallelism first); since Luke's 2026-10-30/31 direction: serial and
parallel both fast from one idiomatic source, target ≤ 1.0× the reference, trade-offs decided by Luke.
Branch `goal/2026-10-30` (local only, not pushed). Coordination folder: `~/Projects/minyar-goal-20261030`.

## Decisions for Luke (from `reports/tradeoffs.md`; nothing below has been changed without you)
| # | trade-off | price (visible / hidden / both-modes serial) | recommendation |
|---|---|---|---|
| T5 | memory reclaimed at all (RC + frames) | −30% / −49% / −8% if never freed (not a real option) | KEEP; most of it is DEBT (allocator, RC traffic, teardown) — being fixed. Your call: opt-in arena/region scope for parse-then-drop phases (new feature) |
| T4 | bounded cleanup scheduler (latency bound) vs eager freeing | −2.5% / −26% / −3% | KEEP the bound, make it near-free (DEBT). Your call: default batch programs to `--memory-profile eager`? |
| T4b | scheduler "unit" definition: let a dead record's scalar slots (≤ 7) cost no unit | exprparse −3.4%, json −3.3% further (ownership3 measurement) | needs your OK (changes the documented unit) |
| T7 | data-race freedom (parallel restrictions) | not switchable; textindex 84% / mapreduce 44% forced serial | KEEP; lift unneeded restrictions (partly done: join runs ordinary code, spans, addAll) |
| T6 | thread runtime safety | 0 visible; server +8.3% Ir at 1 thread | make it free when single-threaded (DEBT) |
| T2 | bounds checks | −0.8% / −1.3% / −10% | KEEP; prove away (hoisted window checks) |
| T3 | Unicode character indexing | −0.6% / −2.8% / ~0 | KEEP; ASCII fast paths (DEBT) |
| T1 | checked overflow | 0% / −0.5% / −0.5% | KEEP; dropping buys nothing |
| T8–T11 | cycle collection, live patching, stack-overflow diagnosis, determinism | ~0 | already zero-cost when unused; KEEP |
| API | json `Value.items/keys` are public mutable Lists, so each scalar leaf allocates two empty Lists | json-heavy code | your call: make them read-only/lazy (API change) or keep |
Scheduler-unit proposal and json API are the only items needing you now. Debt ceiling (every guarantee off): visible 2.43× (1.95× vs Rust), hidden 3.25× (2.18× vs Rust) → the gap is DEBT first.

## Numbers (box D, AMD, cachegrind Ir; identical output everywhere)
| | baseline 3832f4373 | now |
|---|---|---|
| hidden h01–h20 geomean vs fastest of C/C++/Rust | 7.453 (max 19.47) | **5.028** (max 13.40) at 1ddea7b87; vs Rust **3.373** (max 9.85) |
| hidden b01–b07 one-source both modes (serial / 4-thread) | 6.38 / 2.97 (at 010e8ba26) | **3.49 / 1.92** (vs Rust 2.62 / 1.92) |
| visible compare suite geomean (22 programs) | 5.32 (21 programs) | **2.80** at 1ddea7b87 (**2.26** vs Rust); worst json 8.76 |
| visible both-modes (6 programs) serial / parallel | 2.10 / 1.76 | 1.87 / ~1.6–1.9 (wall noisy on shared box) |
Phase 1 bars (≤ 1.25×, no program > 2×; then ≤ 1.1×; Luke's newer ≤ 1.0×, none > 1.2×) are **not met**.
Full history: `~/Projects/minyar-goal-20261030/reports/scoreboard.md`.

## Done (all on goal/2026-10-30 = 1ddea7b87, 120+ commits over 3832f4373; last gate 339/339 on box G: check-portable + check-benchmarks + compare + bothmodes + new checks)
- Profiling: four-language visible suite (`benchmarks/compare`, 21 programs), one-source both-modes suite
  (`benchmarks/bothmodes`), `reports/perf-gaps.md` (root cause per program), `reports/serial-and-parallel.md`,
  `reports/tradeoffs.md` + experimental ablation switches.
- Compiler/runtime/stdlib: record fields without length checks, x86-64-v3 release default, TBAA for Lists, guard-page
  stack checks (no per-call counter), scope cells by default, cheaper bounded scheduler, borrowed match payloads/globals,
  try consumption, scalar choice records, zero-copy split/views, inline Text length/indexing, compiled interpolation,
  slice fusion, faster search, ASCII casing, specialised sorts + per-call-site sortBy merge, Map fast paths + one-probe
  update, Text keys compared as words, inline scalar List append, hoisted List headers in parallel functions.
- Parallelism: threads that own I/O, typed channels + select + eventloop wake, atomics with orderings + wait/notify,
  one work-stealing pool with `join` (ordinary functions, disjoint spans, addAll), per-thread heaps (thread-mode tax
  from up to 2× down to ≤ 1.04× on most programs).
- neo-db requests: doc-reader fix, allocation-free eventloop, syncer sync-now/fsync, CRC32C, O_DIRECT, lazy libcrypto,
  TLS bundles, keep-alive streaming http, math extras, Bytes.addRange, files status/link — "adopt + confirm" in
  `~/Projects/goal-loops/REQUESTS.md` (none confirmed adopted yet, so register rows stay open).

## Blockers / open
- Gap register (`reports/gaps.md`): many rows built but not yet **used by the project that asked** (neo-db etc.); async
  I/O (sockets on io_uring/kqueue, async model) and SIMD not started.
- After 09:40 UTC only box B (Intel, 4 vCPU, shared with neo-db) remains; the hidden set is backed up there
  (`/home/judge/backup-boxD`) and in `/Users/luke/.goal-judge/minyar` (mode 700). Box B needs the hidden set restored to
  `/home/judge/minyar` and a re-baseline (Intel ≠ AMD instruction counts) before the goal's box-B checks can run.
- Wafer Code spend: see the line at the end.

## Next (in order)
1. Free-path/RC debt (ownership3, then allocator size classes measured by wall time), json representation once you decide.
2. Text scanning loop versioning (U4 rest), per-field TBAA (U7), Map lookups inline into generated code.
3. Async I/O and SIMD (phase 2), neo-db adoption confirmations.
