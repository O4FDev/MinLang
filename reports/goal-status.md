# FOR LUKE (2026-11-01 00:00 UTC) — run-2 Wafer budget binds before Sunday 21:00
$6.2 of the $15 run-2 Wafer budget is spent after 3.5 h (about $1.8/h with 10–11 lanes; one third of it is prompt-cache
misses after idle waits, now being cut by ending agent sessions on waits and resuming at `medium` effort). At this rate
the budget reaches $13 (where I stop re-dispatching, keeping $2 for fixes) around 04:00–06:00 UTC, 15+ hours before the
21:00 stop. Raise it? Until you answer, lanes are paced, not stopped.

**Trade-off awaiting you — Float contraction (FMA):** nbody 1.30× → 1.11× of C, but `a * b + c` is rounded once instead
of twice, so some Float results print differently. On side branch `goal/r2-cg-fma`, not merged; before/after program in
reports/tradeoffs.md once the cg lane writes it.

# DECISION FOR LUKE — opt-in `region { … }` block (c5 measured a 29–76% Ir ceiling on parse-then-drop programs)
```minyar
// before (today): every node of `tree` is freed object by object through the bounded cleanup scheduler
for line in lines {
    let tree = parse(line)
    total = total + eval(tree)
}

// after (proposed): everything allocated inside the block is freed in one step when the block exits
for line in lines {
    region {
        let tree = parse(line)
        total = total + eval(tree)   // `total` is an Integer, so nothing escapes
    }
}
// letting a region value escape is a compile error, e.g. `results.add(tree)` inside the block:
//   error: `tree` was allocated in a region and cannot outlive it
```
What it costs the user: one new keyword; code that wants the speed must say `region`; values cannot leave the block.
What it buys: no per-object teardown for the region's allocations (measured ceiling −29% to −76% instructions).
Bounded pauses: the region exit is allocator work (page frees), outside the cleanup unit budget — the contract would need a
sentence saying so. Status: mechanism prototyped on `goal/cake-c5` (opt-in env flag); not merged; awaiting your call.

---

# CORRECTION (2026-10-31 21:10 UTC): the last two merged batches were gated red — RESOLVED 22:40 UTC
The 3-way sharded gates for the final batch (tag f15) and the c8 revert (tag rv) each reported one failed check,
`check-determinism-runtime`, and I merged anyway: the merged output listed the failure but printed no red/green verdict, and
I misread it. Cause: three runtime helpers added by the Result-in-registers work and parallel-worker ownership
(`minyar_result_box`, `minyar_choice_box`, `minyar_parallel_chunk_drain`) were never classified in the determinism audit.
Box B's full gate on 86f8a0405 confirmed it (2 of 337 failed: that check and `check-portable`, which depends on it;
livepatch soak green: 0 errors, exactly-once).
Fixed in 01a0bfe46 (all three only compute from their arguments → pure list). `shard/shard-collect.sh` now prints
GREEN/RED and exits non-zero on RED. Box B full gate + soak on 01a0bfe46: **GREEN** (337/337; soak 282,733 requests, 0 errors, exactly-once), 22:40 UTC.
Merge rule since 21:55: every batch is gated on `candidate/<name>`; the goal branch moves only on an explicit GREEN gate,
a clean hidden re-score (no program slower than +0.1% Ir) and a clean visible compare.

## Run 2 progress (2026-10-31 20:30 → 2026-11-01 00:00 UTC)
| step | hidden h geomean (vs Rust) | b serial / parallel | visible compare (vs Rust) | notes |
|---|---|---|---|---|
| start 86f8a0405 (c8 reverted) | 4.826 (3.236) | 3.460 / 2.133 | 2.52 (2.03) | |
| + 01a0bfe46 determinism fix + c8 re-land a9edf1232 | **4.671 (3.133)** | 3.282 / 2.175, b07 compiles | exprparse −5.6%, tokenizer −5.3% | nested Text loop copies get unique names |
| candidate r2b (cg unroll, memmem, txt split) — not merged | 4.477 (3.002) | 3.168 / 1.850 | 2.37 (1.91) | h12 +4.9% (cg +3.2%, txt +1.6%), h04 +1.1% (txt), wordfreq +0.25% (memmem): lanes reworking |
| candidate r2d (res eager small-aggregate retirement) — not merged | 4.611 (3.093) | 3.252 / 2.073 | — | h17 +0.45%: res reworking |
| r2e merged f77542df3 (tooling + docs) | 4.671 | 3.282 | unchanged | |
| r2h2 merged c8d30adca (Map hashing + txt positional split, both reworked) | **4.384 (2.941)** | 3.117 | 2.34 | h06 −32%, h13 −25%, h20 −19%, h08 −14%; nothing slower |
| r2i+r2j merged 1ab0fef98 (httpstls listener; compiler huge pages) | 4.384 | 3.117 | unchanged | SYS-18 closed in Minyar; objstore adopts one line |
| r2l merged b27b0710b (dev-check narrows: compiler edit ~24/337 checks) | 4.384 | 3.117 | unchanged | |
| 4-thread re-measure (quiet box B, n=5 medians) | — | parallel: no program slower beyond noise | bothmodes Ir@4 equal or lower | scoreboard.md |
| in flight | brw (treewalk −25%; RED after rebase: crash hunt), esc+fbip (inline List slots + buffer reuse), res2, cg | | | |
Gap register: SYS-18 (`http.listenTLS`, blocks minyar-objstore) added and in progress; SYS-19 (projects behind the
`Text(bytes)` API change) filed to the owning loops.

# Minyar goal status (2026-10-31 20:25 UTC — end of the cake swarm window; boxes D/F/G/H–O deleted at 21:30)

## NEXT SESSION — first merge batch (unmerged wins, with branches)
1. **c8 Text loop versioning** — `goal/cake-c8` 821bca9bb (exprparse −4%, tokenizer −5%). Merged then reverted
   (84e2e01a3): nested versioning emits `multiple definition of local value 'value.N.fastA.fastB'` on a hidden program's
   nested loops. Fix the copy naming for loops inside an already-versioned region, add that shape to
   tests/text-scanning.min, re-gate, re-score hidden.
2. ~~c10~~ — measured on top of c4 (`goal/cake-c10-on-c4` 75275c87c): neutral (word scan) or worse (inline frees, inventory +7.6%); c4's subunit drain already removed the costs it shaved. Dropped.
3. **c5 region mechanism** — `goal/cake-c5` 663771786, a7e041b0d, only if Luke approves D2 (`region { … }`).
4. **c1 header recycling** (treewalk −9.3%) — blocked by a latent double-release in borrow bookkeeping (reports/cake/c1.md);
   fix that bug first (it is a memory-safety bug regardless of recycling).
5. **Gate flow:** switch merges to the fast-tests loop's sharded `fast-gate` once it announces itself in
   ~/Projects/goal-loops/REQUESTS.md (branch goal/fast-tests). Until then use ~/Projects/minyar-goal-20261030/shard/
   (3-way sharded gate = 10.5 min vs ~25 min single box).
6. **Harness v2** is merged (function-level selection; docs/dev-check.md). It is the default pre-gate check for every lane
   and Wafer agent. What's left (reports/harness.md): compiler/runtime edits still select 78–90 checks (12–17 min) because
   many checks hash the compiler binary as data; 26 checks lack coverage; SIGKILLed processes lose counts. The coverage
   index must be re-recorded on the next session's boxes (`make dev-check-index`, ~57 min once).

## Current numbers
| | baseline 3832f4373 | now (goal tip) |
|---|---|---|
| hidden h01–h20 vs fastest of C/C++/Rust | 7.453 (max 19.47) | **4.826** (max 12.94); vs Rust **3.236** (max 9.51) |
| hidden b01–b07 (serial / 4-thread) | 6.38 / 2.97 | **3.46 / 2.13** (vs Rust 2.60 / 2.13) |
| visible compare suite (22 programs) | 5.32 | **2.52** (vs Rust 2.03); worst json 6.38 |
Phase 1 bars (≤ 1.25×, no program > 2×; Luke's ≤ 1.0×, none > 1.2×) are **not met**. Phase 2 register rows built but
not yet adopted by the projects that asked; async I/O and SIMD not started.

## Decisions for Luke (from the cake swarm, reports/cake.md has the code examples)
- D1 (recent-first cleanup order) — MOOT: on c4's subunit drain even pure recent-first cannot starve the old batch (c10's
  sustained-load fixture drains a 4,000-record chain to one live object either way), and the order no longer changes Ir.
- D2 opt-in `region { … }` block (new syntax; ceiling −29% to −76% Ir on parse-then-drop programs).
- D3 json member index needs a private `Value` field (breaks `json.Value { … }` literals; wins only from ~32 members).
- Already decided by Luke today: T4b coarser scheduler unit APPROVED (landed via c4's subunit drain); json API break and
  new arena syntax NOT approved; everything else keeps its guarantee.

## Spend (2026-10-31)
Wafer Code: $6.46 for the swarm (14:20 UTC on), $6.99 for the whole day (01:10 UTC on). Boxes: H, I–L, M–O inside
Luke's $10; nothing else created.

---
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

## Handover notes (07:58 UTC)
- Box B (survives the shutdown): `/home/judge/minyar` now holds the final hidden set from box D (h01–h20 + b01–b07, score.sh
  with Rust-only fields and a CPU-keyed cache); the previous box-B copy is `/home/judge/minyar.boxB-20261030`. judge is in
  group agent. Before scoring there: sync the tree to `/home/agent/minyar/score` (`BB_HOST=agent@178.62.55.155 bb score …`)
  and wrap runs in `flock /home/agent/bench.lock`. Done 08:12 UTC: box B reproduces box D's instruction counts exactly (baseline 7.453, ff36ca1f2 5.028), so box B is the scoring box now.
- Unmerged work on laptop branches: `goal/2026-10-30-tbaa` (Wafer Code, per-field alias tags U7 — unverified, still
  running at shutdown), `goal/2026-10-30-codegen-map-update` (superseded by maps), `goal/2026-10-30-maps-sort` (do not land).
- Wafer Code spend for this goal (01:10 UTC onward, `~/.wafer-code/logs`): $0.27 over 294 requests (cap $5).
- Lane reports with full detail: `~/Projects/minyar-goal-20261030/reports/*.md`; scoreboard history `reports/scoreboard.md`.
