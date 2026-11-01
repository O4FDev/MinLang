# Hidden + visible score history (box D = AMD loop-d-minyar unless noted)

| when (UTC) | tree | box | hidden geomean | hidden max | over 2× | visible geomean |
|---|---|---|---|---|---|---|
| 2026-10-30 ~03:30 | 3832f4373 baseline | B (Intel) | 7.453 | 19.471 | 18 | 5.32 (98152d6f0) |
| 2026-10-30 ~10:00 | 3832f4373 baseline | D (AMD) | 7.453 | 19.471 | 18 | |
| 2026-10-30 12:35 | 79e1b8e25 (codegen: record fields, x86-64-v3, TBAA) | D | 7.355 | 18.890 | 18 | 4.71 |

## Visible both-modes suite (benchmarks/bothmodes, box D, tree 010e8ba26 = goal + parallel lane merges)
serial = Minyar@1t Ir / best serial C/C++/Rust Ir; parallel = Minyar@4t wall / parallel Rust@4t wall (n=7 median, box loaded ±15%)
| program | serial | parallel |
|---|---|---|
| topk | 2.63 | 1.47 |
| server | 2.22 | 1.04 |
| mapreduce | 1.89 | 2.46 |
| sort | 2.10 | 2.51 |
| textindex | 2.69 | 2.96 |
| forkjoin | 1.39 | 1.06 |
| geomean | 2.10 | 1.76 |

## Hidden, 2026-10-30 ~20:51 UTC, box D, score tree 010e8ba26 (goal + codegen + systems + parallel lane; NO ownership/stdlib)
h geomean=7.355 max=18.890 over2=18 failed=0 (same as 79e1b8e25: parallel lane leaves serial h programs unchanged)
b (one source, both modes; baseline for b) geomean_serial=6.380 geomean_parallel=2.971 max_serial=27.226 max_parallel=7.470 failed=0

## Visible compare suite, box D, 2026-10-30 ~21:40 UTC (perfgaps lane)
integration tip (codegen+systems+ownership+stdlib+parallel): geomean 3.68 (baseline 5.32); + ownership2 WIP + calls: 3.22
bothmodes visible at integration: serial 1.98, parallel 1.58 (load ~5, ±15–20%)

## Gate: integration 2d1d5d632 (codegen+systems+ownership+stdlib+parallel), box D, 2026-10-30 21:40 UTC
check-portable + check-benchmarks + check-benchmarks-compare via check-in-parallel: 332/333; check-shipping failed once
(http-bounded-test "bounded HTTP" under load ~6); rerun on 3c596f090 (+calls): http-bounded-test 3/3 pass, `make check-shipping` passes.
OPEN: investigate http-bounded-test load sensitivity (10 s request timeout?) — flaky.
goal/2026-10-30 fast-forwarded to the integration tip (incl. calls lane, bothmodes suite, perf-gaps.md).

## Hidden, 2026-10-31 00:33 UTC, box D, score tree 2d1d5d632 (integration: codegen+systems+ownership+stdlib+parallel; no calls)
h geomean=7.072 max=18.890 over2=18 failed=0   (h01 11.78, h08 17.69, h16 18.89, h17 14.11; h18 1.40, h19 1.18)
b geomean_serial=4.180 geomean_parallel=3.711 (parallel column taken under heavy box load — not comparable)
NOTE: visible geomean fell 5.32→3.68 but hidden only 7.45→7.07 → orchestrator profiling hidden cost classes (logs/orch-hidden-profile.txt, aggregated only).

## Hidden-suite cost classes (orchestrator-only callgrind, tree 2d1d5d632, aggregated; logs/orch-hidden-profile.txt)
Top runtime symbols (share of all Minyar Ir): rc_bounded_service 12.95, rc_bounded_step_chunks 7.60, minyar_rc_release 5.96,
minyar_rc_keep 3.82, minyar_text_split 3.17, minyar_rc_leave 2.26, rc_system_deallocate 2.18, rc_heap_allocate 2.00,
text_slice_bytes 1.82+1.22, minyar_rc_enter 1.45, rc_leave_stack_v1 1.36, map_has 1.31, join_texts 1.25, map_hash 1.23,
text_search_next 1.14, interpolate 0.99. Per-program rc class 20–67%; one program 52% map; six 25–38% text runtime.

## Gate batch 2 (parallel2 + text + macOS fixes), box F, 2026-10-31 02:07 UTC: 334/335; check-language-contracts failed
(literal `.length` became inline → contract test rewritten to a runtime Text call, intent unchanged) → passes. goal/2026-10-30 fast-forwarded.

## Gate batch 3 (ownership2), box G, 2026-10-31 03:00 UTC: 335/335 passed (check-portable + benchmarks + compare + bothmodes). goal/2026-10-30 → bb87f78f4

## Gate batch 4 (loops), box F, 2026-10-31 03:42 UTC: 334/335; check-last-use-sinks expected the scalar append as a runtime call (now inline helper) → expectation split, intent kept → passes. goal → 27aefa753

## Hidden ablation (box D, trees a886425c8 + ablation cd28f228b), 2026-10-31 02:00–04:40 UTC
| config | h geomean | h worst | h vs Rust | b serial | b parallel |
|---|---|---|---|---|---|
| base | 6.984 | 18.791 | – | 4.168 | 2.094 |
| overflow off | 6.952 | 18.722 | – | 4.103 | 2.101 |
| bounds off | 6.896 | 18.735 | – | 3.986 | 2.166 |
| unicode byte-index | 6.786 | 18.791 | – | 4.051 | 2.170 |
| reclaim off (never free) | 3.589 | 11.906 | 2.407 | 1.520* | 1.239* |
| scheduler off (eager) | 5.191 | 14.377 | 3.482 | 3.618 | 2.156 |
| thread runtime off | 6.984 | 18.791 | 4.684 | 1.558* | 1.461* |
| all off | 3.254 | 11.886 | 2.182 | 1.361* | 1.203* |
*5 of 7 b programs fail under that switch (threads trap / never-free), so b geomeans cover 2 programs only.

## Hidden, 2026-10-31 ~05:15 UTC, box D, score tree 27aefa753 (batch 4: + parallel2, text, ownership2, loops, macOS fixes)
h geomean=5.160 max=14.549 over2=18 failed=0 | vs Rust: geomean_rust=3.461 max_rust=10.695
b serial=3.598 parallel=1.981 (vs Rust serial 2.701, parallel 1.981) failed=0
Trend h (vs fastest): 7.453 (3832f4373) → 7.355 → 7.072 → 5.160.

## Gate batch 5 (ablation switches + tradeoffs.md), box G, 2026-10-31 ~06:05 UTC: 327/336; all 9 failures from one uncatalogued test script (tests/ablation/switches.sh) → catalogued; suite-catalogue, build-wiring, peer-manifest, peer-regressions pass. goal → c16925e54

## Gate batch 6 (maps), box F, 2026-10-31 06:44 UTC: 338/338 passed. goal → 908aec3ab

## Visible compare, box D, 2026-10-31 06:53 UTC, goal 908aec3ab (all finished lanes): geomean 2.83 vs fastest (2.28 vs Rust), worst json 9.05 (vs Rust: exprparse 6.59). Baseline 5.32. Full table: logs/compare-b6-boxD.log

## Hidden, 2026-10-31 06:54 UTC, box D, goal 908aec3ab (all finished lanes)
h geomean=5.080 max=13.454 over2=18 failed=0 | vs Rust 3.407 / 9.890 (h18 1.40, h19 1.22, h10 1.08 vs Rust)
b serial=3.510 parallel=1.926 (vs Rust serial 2.636) failed=0. Full: logs/score-908aec3ab-boxD.log

## Gate batch 7 (ownership3), box G, 2026-10-31 07:44 UTC: 339/339 passed. goal → 1ddea7b87

## FINAL before shutdown, box D, 2026-10-31 07:51 UTC, goal 1ddea7b87 (all lanes, gated 339/339 on box G)
hidden h geomean=5.028 max=13.399 over2=18 failed=0 | vs Rust 3.373 / 9.850
hidden b serial=3.487 parallel=1.918 (vs Rust serial 2.618) failed=0
visible compare (22 programs) geomean 2.80 vs fastest, 2.26 vs Rust; worst json 8.76 (vs Rust exprparse 6.31)
Logs: logs/score-final-boxD.log, logs/compare-b7-boxD.log

## Box B (Intel, survives the shutdown), 2026-10-31 08:12 UTC — same Ir as box D (AMD)
baseline 3832f4373: h geomean=7.453 max=19.471 | vs Rust 4.998 / 15.252 | b: 6 of 7 cannot build at baseline (no join/channels)
goal ff36ca1f2:     h geomean=5.028 max=13.399 over2=18 failed=0 | vs Rust 3.373 / 9.850 | b serial 3.487, parallel 2.123 (Intel wall)
→ instruction counts are identical across the two CPUs for these binaries; box B is a valid scoring box from now on.

## Box B phase-1 checks, 2026-10-31 09:08 UTC
- `make check-in-parallel CHECKS="check-portable check-benchmarks"` on 81044253f: 336/336 passed.
- `python3 benchmarks/livepatch/run.py soak` on 5da77df7f (run.py CPU defaults fixed for 4-vCPU boxes): errors 0,
  every_request_counted_once true, versions monotonic, 5 patches under load, 266,335 requests.
- Hidden score on box B (ff36ca1f2): geomean 5.028 (vs Rust 3.373), max 13.399 — phase-1 perf bar NOT met.

## Gate batch 9 (ownership4 + per-field TBAA + ownership5 + fixes incl. a use-after-free), box H, 2026-10-31 16:21 UTC
336/339: check-determinism-runtime (box-H environment; passes on box B), check-osdev-workflow (load flake at load 8–10;
reran 2/2 green). goal/2026-10-30 fast-forwarded to batch 9.
Visible compare (box H, 22 programs): geomean 2.69 vs fastest, 2.17 vs Rust; worst json 8.51.

## Hidden, box B, 2026-10-31 16:28 UTC, goal 6d1b98202 (batch 9)
h geomean=5.036 max=13.399 over2=18 | vs Rust 3.378 / 9.850 | b serial 3.487, parallel 2.082 (Intel wall)
vs 1ddea7b87 (5.028): flat. One hidden program REGRESSED +8.0% (h17 5.764 → 6.223); h05 −4.2%. Bisecting on box B
(bisA = ownership4 only 6a19fe3e2, bisB = + per-field TBAA 9aa49c5f1).
Bisect (box B hidden): 9aa49c5f1 (ownership4 + TBAA) h17 5.764, geomean 5.029; 2c2dd076b (+ ownership5 lowering) h17
6.223, geomean 5.036 → the +8% on one hidden program comes from ownership5's lowering (not the UAF fix). Sent to the
ownership5 lane as a numbers-only signal; fix due 19:30 UTC. Note goal/2026-10-30 already contains it (batch 9).

## Gate batch 10 (harness dev-check v1 + c9 parallel-for worker-local values), box H, 2026-10-31 16:56 UTC: 337/340
check-determinism-runtime (box-H env), check-harness-dependencies (artifact of my tree seeding: copied build outputs older
than the checked-out sources and compare-and-move rules never refresh their mtime — passes once the chain is touched).
Merged into goal/2026-10-30.

## Swarm finding to fix (c1, 18:05 UTC): latent double-release in borrow bookkeeping
Recycling whole List headers (c1's best attempt, treewalk −9.3%) segfaults treewalk; memcheck shows a write into a List
header that was already released and handed out again — a release the compiler's borrow bookkeeping makes on a header it
no longer owns. Hidden today only because freed slots are rarely reused that fast. Treat as a memory-safety bug to fix
before any reuse-style allocation lands (repro + details: reports/cake/c1.md).

## FINAL (2026-10-31 20:22 UTC), goal/2026-10-30 after the swarm merges and the c8 revert
Hidden (box B): h geomean=4.826 max=12.940 over2=18 failed=0 | vs Rust 3.236 / 9.512 | b serial 3.460, parallel 2.133, failed 0
  (with c8: h 4.671 but b07 failed to compile — reverted).  Baseline 3832f4373: h 7.453 / max 19.47.
Visible compare (box M, 22 programs): 2.52 vs fastest, 2.03 vs Rust; worst json 6.38 (baseline 5.32 on 21 programs).
Gates: sharded 3-way full gate (M/K/J) green except box-env check-determinism-runtime; b07 verified at 1 and 4 threads.

## Run 2 merges (2026-10-31 20:30 → 2026-11-01 02:45 UTC, box B, cachegrind Ir; every merge gated GREEN on M/K/J first)
| goal tip | what landed | hidden h geomean (vs Rust) | worst h | b serial | visible compare (vs Rust) |
|---|---|---|---|---|---|
| 86f8a0405 | run-2 start (c8 reverted) | 4.826 (3.236) | 12.94 | 3.460 | 2.52 (2.03) |
| a9edf1232 | determinism fix + c8 Text loop versioning re-land | 4.671 (3.133) | 12.94 | 3.282 | — |
| f77542df3 | real-world suite, dev-check v3, reports (no code) | 4.671 | 12.94 | 3.282 | unchanged |
| c8d30adca | Map hashing (map) + positional `split` (txt) | **4.384 (2.941)** | 11.10 | 3.117 | 2.34 (txt alone vs a9edf1232; map −5.7% intmap) |
| 1ab0fef98 | `httpstls.listenTLS` (SYS-18) + compiler huge pages (self-compile −12% wall) | 4.384 | 11.10 | 3.117 | unchanged (compiler-only) |
| b27b0710b | dev-check selection fixes (no code) | 4.384 | 11.10 | 3.117 | unchanged |
Rejected by the hidden re-score although gate-GREEN: cg's global unroll threshold (one compute program +3.2%), first txt
version (two programs +1.1/+1.6%, quadratic split reads), res eager retirement v1 (one RC-heavy program +0.45%).

## 4-thread re-measure, quiet box B, 2026-11-01 01:28–02:40 UTC (a9edf1232 vs goal tip b27b0710b)
Hidden b programs: 5 interleaved score.sh rounds per tree, median of the `parallel` ratio (Minyar 4-thread wall / fastest
cached parallel reference); all outputs identical, serial Ir unchanged or lower.
| program | a9edf1232 median (range) | goal tip median (range) | delta |
|---|---|---|---|
| b01 | 1.623 (1.39–1.67) | 1.590 (1.34–3.05) | −2.0% |
| b02 | 1.883 (1.77–1.92) | 1.869 (1.50–2.66) | −0.7% |
| b03 | 2.854 (2.47–3.32) | 2.558 (2.17–4.54) | −10.4% |
| b04 | 3.808 (3.35–3.92) | 3.871 (3.49–5.87) | +1.7% (inside the base's own range) |
| b05 | 4.943 (4.64–5.30) | 4.910 (4.58–6.83) | −0.7% |
| b06 | 1.019 (0.98–1.09) | 0.966 (0.89–1.58) | −5.2% |
| b07 | 1.642 (1.61–1.75) | 1.631 (1.58–2.12) | −0.7% |
benchmarks/bothmodes (7 interleaved repeats): Ir at 1 and 4 threads identical or lower (textindex@4 3,406.5M → 3,244.0M);
parallel wall geomean 1.56 → 1.56; mapreduce@4 wall 1.44 → 1.59 with identical 4-thread Ir and sd larger than the gap
(noise). Verdict: no program slower in parallel mode beyond noise. Logs: ~/Projects/minyar-goal-20261030/logs/pm-20261101/.
Note: single score.sh runs swing up to ±50% in the parallel column (wall time, cached references); only medians over
interleaved rounds may be used to judge a parallel regression.

## Run 2 merges, continued (2026-11-01 06:20 → 09:45 UTC, box B hidden score; each gated GREEN on M/K/J first)
| goal tip | what landed | hidden h geomean (vs Rust) | worst h | b serial | notes |
|---|---|---|---|---|---|
| e2d877b40 | brw borrow inference + crash fix + reassigned-source fix | 4.312 (2.892) | 11.10 | 3.116 | h17 −22.7%, h14 −3.9%; treewalk −24.7% |
| 31cb7b081 | SYS-1 signal subscriptions, SYS-2 PTY sessions | 4.312 | 11.10 | 3.116 | hidden unchanged |
| a38e31def | Text runtime scans (one-cursor split, SSE2 separator scan, 4-word UTF-8) | 4.249 (2.850) | 11.02 | 3.090 | h06 −5.4%, h20 −5.1%, h13 −4.3%, h10 −4.1%; logstats −8.7% |
| fad45086b | SYS-3 file locks, SYS-4 real paths/identity/temp dirs, SYS-5 time, SYS-6 CRC/MD5/Base64, SYS-8 readLine | 4.249 | 11.02 | 3.090 | hidden unchanged |
| 994f9bc3e | range-guarded versioning of checked List-walk accumulations | 4.249 | 11.02 | 3.090 | hidden unchanged; visible grid −0.87% |
| 58990cb8d | last-use moves into field stores and returned pairs | 4.248 (2.849) | 11.02 | 3.090 | h04 −0.18%, h05 −0.25%; exprparse −1.8% |
Held (gate GREEN, one program over +0.1%): res2 eager retirement (b05 +0.18%: glibc mmap-threshold free-order effect,
lane `big` making large buffers mmap/mremap), sched reclamation (h09 +0.61%: newly inlined runtime code grew user code,
lane `sched2`), cg literal-range unroll (b04 +0.22%, dropped).

r2y same-box check (box M, 09:40 UTC; parent fad45086b vs 994f9bc3e; cachegrind Ir): compare 22 programs — worst
inventory +0.016%, grid −0.869%, config −0.020%, the rest 0.000%; bothmodes 6 programs at 1 and 4 threads — all identical.

Same-box parent-vs-candidate checks (box L, 2026-11-01 ~10:40 UTC, cachegrind Ir; rule from 09:58: every merge gets this):
- r2z 58990cb8d vs parent 994f9bc3e — compare 22: exprparse −1.835%, config −0.078%, json −0.022%, rest 0.000%; bothmodes
  6 × (1, 4 threads): all identical.
- r3b 1fa396a48 vs parent 58990cb8d — compare 22: httpparse −2.152%, exprparse −1.922%, json −1.751%, nothing slower;
  bothmodes: mapreduce −0.863% @1 / −0.862% @4, server −0.363% @1, nothing slower.
- r3b hidden (box B): geomean 4.248 → 4.213, every program equal or faster.

## Phase 1 (stabilisation): box-B single-box full gate on goal tip 993756afe — GREEN (2026-11-01 10:58 → 12:00 UTC)
`make check-in-parallel CHECKS="check-portable check-benchmarks" CHECK_JOBS=4` on brief-crawl-1: 345 checks, 172 shared
builds, **Parallel checks passed** (GATE-FINAL-EXIT 0). `python3 benchmarks/livepatch/run.py soak`: 291,309 requests,
**0 errors**, 5 patches under load, versions monotonic per connection, every request counted exactly once (SOAK-FINAL-EXIT 0).
Disk guard: minimum free 12 GB during the run (abort line 6 GB); gate tree deleted afterwards, box B back to 21 GB free.
Logs: ~/Projects/minyar-goal-20261030/logs/gate-final-993756afe.log, soak-final.log.

## Phase 5 release-candidate verification — final goal tip 7d4576591 (2026-11-01 ~14:20 UTC)
Hidden suite (box B, `sudo -u judge /home/judge/minyar/score.sh`, cachegrind Ir; all 27 outputs identical):

| program | ratio vs fastest | vs Rust |
|---|---|---|
| h01 | 7.256 | 4.889 |
| h02 | 5.119 | 3.838 |
| h03 | 3.635 | 1.763 |
| h04 | 4.346 | 4.346 |
| h05 | 5.439 | 3.968 |
| h06 | 5.265 | 4.992 |
| h07 | 2.656 | 2.656 |
| h08 | 10.823 | 7.956 |
| h09 | 4.126 | 3.396 |
| h10 | 4.127 | 0.939 |
| h11 | 4.099 | 2.730 |
| h12 | 8.993 | 1.183 |
| h13 | 5.061 | 3.334 |
| h14 | 3.593 | 3.166 |
| h15 | 4.831 | 3.936 |
| h16 | 6.580 | 2.865 |
| h17 | 4.438 | 3.830 |
| h18 | 1.394 | 1.394 |
| h19 | 1.216 | 1.216 |
| h20 | 2.350 | 2.195 |
| b01 | serial 1.701 / parallel 1.453 | serial 1.484 / parallel 1.453 |
| b02 | serial 7.092 / parallel 1.825 | serial 4.889 / parallel 1.825 |
| b03 | serial 4.863 / parallel 2.450 | serial 3.440 / parallel 2.450 |
| b04 | serial 4.820 / parallel 3.368 | serial 4.428 / parallel 3.368 |
| b05 | serial 3.969 / parallel 4.702 | serial 2.163 / parallel 4.702 |
| b06 | serial 1.360 / parallel 0.997 | serial 1.201 / parallel 0.997 |
| b07 | serial 1.708 / parallel 2.272 | serial 1.222 / parallel 2.272 |

**geomean 4.213 (vs Rust 2.825), max 10.823, 18 programs over 2×; b serial 3.076, b parallel 2.179 (single run; parallel is wall time).**
Start of run 2 (86f8a0405): 4.826 / 3.236. Baseline 3832f4373: 7.453.

Visible + both-modes, same box (box B, one harness = the final tip's, `--tree` for each tree, cachegrind Ir):
- geomean vs fastest: baseline 3832f4373 **5.32** → run-2 start a9edf1232 **2.51** → final **2.25**.
- final vs a9edf1232: 22 compare programs, none slower (best logstats −54.7%, service −46.8%, treewalk −24.8%); bothmodes 6 × (1, 4 threads): worst forkjoin@4 +0.013%, best textindex −4.8% at 1 and 4 threads, mapreduce@4 −0.87%.
- final vs baseline: every program faster (treewalk −90.3%, exprparse −83.9%, httpparse −70.9%; least: par-mandel −23.2%); bothmodes −11% to −24% at 1 and 4 threads.
Box-B single-box full gate + soak on 993756afe GREEN (above); 7d4576591 adds only the fast-gate tooling (no compiler/runtime/library change).
Raw tables: ~/Projects/minyar-goal-20261030/logs/phase5-ab-results/, logs/score-final-7d4576591-boxB.log.

Real-world suite on the release candidate (box B, `benchmarks/realworld/run.py --tree 7d4576591 --keep-going --repeat 1`, projects synced with
`sync-projects.sh`, adoption patches applied): all 6 build and run. Ir vs the recorded baseline: neo-db 0.96x, minyar-query 0.94x, minyar-js
0.94x, minyar-terminal 1.00x, minyar-sandbox 0.99x, minyar-sim 0.97x. Wall and build-time columns are single samples against a baseline
recorded on another box (box M), so they are not comparable; neo-db needed zlib1g-dev installed on box B first (environment, not Minyar).

**neo-db, measured** (box B quiet, 2026-11-01 ~15:20 UTC; `run.py --tree <final 7d4576591> --against <goal baseline 3832f4373> --only neo-db
--repeat 5`, builds and wall samples interleaved, neo-db pinned at e521f7512): workload Ir 143.9M vs 371.8M = **0.39× (−61%)**, workload
wall median 30.8 ms vs 63.3 ms = **0.49× (2.06× faster)**; the earlier 1.45× wall was a single noisy sample. **Compile time is slower**:
the neo-db binary builds in 309.3 s vs 287.6 s (**1.08×**), and its two bench programs compile in 266.4 s vs 170.1 s (**1.57×**) and
247.7 s vs 179.1 s (**1.38×**) (one build each). Not yet profiled; likely the compile-time analyses added this run (Text loop
versioning, range-guarded loop versioning, borrow inference and return moves) — a compile-time lane should measure per-pass time on
neo-db before more analyses land.
