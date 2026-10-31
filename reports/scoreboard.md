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
