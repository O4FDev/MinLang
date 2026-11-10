# Trade-offs vs debt: what each Minyar guarantee costs (2026-10-31)

Lane `ablation`. Question (Luke, 2026-10-31): which of the remaining gap to C/C++/Rust is bad code (DEBT, fix without
asking) and which is the price of a language guarantee (TRADE-OFF, Luke decides)? Method: ablation builds that turn
off ONE guarantee each (`tools/ablation.sh`, `docs/testing.md` "Ablation builds"; experimental, never shipped), run
over `benchmarks/compare` (21 programs, cachegrind Ir, outputs byte-identical to C/C++/Rust) and
`benchmarks/bothmodes` (6 programs, serial Ir at 1 thread + parallel wall at 4 threads vs `par.rs`) on box D.
Base = goal/2026-10-30 a886425c8. No semantics were changed; nothing here is a recommendation to ship a switch.

## Decision list (one line per trade-off)

Visible = `benchmarks/compare` geomean vs fastest of C/C++/Rust; hidden = orchestrator's 20-program score;
b = both-modes serial. "Price" = how much faster Minyar gets with the guarantee switched off.

| # | trade-off (what it buys) | price: visible / hidden / both-modes serial | recommendation |
|---|---|---|---|
| T5 | memory is reclaimed at all, deterministically (RC + frames) | **-30% / -49% / -22%** (never-free arena; both-modes serial 1.95 -> 1.80, parallel 1.98 -> 1.63; not a real option: json needs >15.7 GB) | KEEP. Most of this is DEBT (Rust frees too): allocator, RC traffic, per-object teardown (U1, U6, U12, O1-O4). Fix those; optionally (d) an opt-in region/arena scope for parse-then-drop phases (new feature, Luke) |
| T4 | bounded cleanup pauses (scheduler) instead of eager freeing | -2.5% (worst 16.6x -> 9.3x) / **-26%** (worst 18.8 -> 14.4) / -3% (1.95 -> 1.89) | KEEP the bound, make it near zero-cost: free leaves/unshared objects immediately, batch List teardown, no polls in loops that free nothing (O1, O4 = DEBT). Already (d): `--memory-profile eager` exists. Luke: decide whether batch programs should default to eager |
| T7 | data-race freedom by construction (parallel restrictions C1/C3/C4/C5, O5) | not switchable; textindex 84% / mapreduce 44% of Ir forced serial; parallel geomean 1.98x par.rs | KEEP race freedom; lift the restrictions that it does not need (ordinary code in tasks, frozen sharing, growing per-task outputs, disjoint sub-window `join`) - DEBT-like work |
| T6 | thread runtime safety for managed values | 0 on visible compare; bothmodes/server @1 thread +8.3% Ir; hidden b not separable (5 programs start threads); C2: +29-50% on managed code | (b) zero-cost when unused: per-thread heaps/no TLS on single-thread paths (mostly DEBT) |
| T2 | List/Bytes bounds checks | -0.8% / -1.3% / **-10%** (topk 23%, sort 16%; parallel 1.98 -> 1.87) | KEEP (Rust keeps them too); (c) prove away: versioned loops with one hoisted check per window, range facts (U15) |
| T3 | Unicode Character indexing | -0.6% / -2.8% / 0% | KEEP semantics; ASCII-known fast path hoisted out of scanning loops (DEBT) and byte-position stdlib scanners for parsers |
| T1 | checked integer overflow | 0.0% / -0.5% / -0.5% (removing it RAISES Ir on grid +8%, par-reduce +23%) | KEEP; (c) range facts for induction/index arithmetic only. Dropping it buys nothing measurable |
| T8 | automatic cycle collection | 0 on every suite program (none links the cycle runtime) | already (b) zero-cost when unused; fix the collector pathology on `List.add`-built trees (judge.md) as DEBT |
| T9 | live patching | 0 in `--release` (no patch points in any benchmark IR) | already (b): dispatch slots only in `minyar build --hot` images |
| T10 | stack-overflow diagnosis (C8) | ~0 after guard pages (calls lane) | KEEP |
| T11 | determinism | not separately switchable; no cost found in these profiles | KEEP |

Totals: price of ALL guarantees (base / all-off) = **1.48x visible, 2.15x hidden**; almost all of it is T5/T4.
Debt ceiling with every guarantee off: visible **2.43x** (1.95x vs Rust), hidden **3.25x** (2.18x vs Rust): even a
guarantee-free Minyar is 2-3x behind, so the gap is DEBT first. No trade-off needs to be given up to make progress;
T5/T4 decisions matter only after the allocation/RC debt is paid.


## Ablation table

| config | visible geomean vs fastest | worst vs fastest | geomean vs Rust | worst vs Rust | bothmodes serial (fastest / Rust) | bothmodes parallel @4 | outputs | hidden geomean / worst |
|---|---:|---:|---:|---:|---:|---:|---|---|
| base | 3.60 | 16.58 exprparse | 2.90 | 13.05 exprparse | 1.95 / 1.35 | 1.98 | identical | 6.98 / 18.79 (b 4.17 / 2.09) |
| overflow | 3.60 | 16.28 exprparse | 2.90 | 12.81 exprparse | 1.94 / 1.33 | 1.98 | identical | 6.95 / 18.72 (b 4.10 / 2.10) |
| bounds | 3.57 | 16.58 exprparse | 2.87 | 13.05 exprparse | 1.76 / 1.21 | 1.87 | identical | 6.90 / 18.74 (b 3.99 / 2.17) |
| unicode | 3.58 | 15.62 exprparse | 2.88 | 12.29 exprparse | 1.95 / 1.35 | 1.90 | base row used: json | 6.79 / 18.79 (b 4.05 / 2.17) |
| reclaim | 2.53 | 11.98 json | 2.03 | 7.11 json | 1.80 / 1.24 | 1.63 | base row used: json server(bm) | 3.59 / 11.91; Rust 2.41 / 8.75 (b 1.52 / 1.24, 5 b failed) |
| scheduler | 3.51 | 9.31 exprparse | 2.83 | 7.33 exprparse | 1.89 / 1.30 | 1.96 | identical | 5.19 / 14.38; Rust 3.48 / 10.57 (b 3.62 / 2.16) |
| all | 2.43 | 11.98 json | 1.95 | 7.11 json | 1.58 / 1.09 | 1.53 | base row used: json server(bm) | 3.25 / 11.89; Rust 2.18 / 8.74 (b 1.36 / 1.20, 5 b failed) |
| threads | = base (no compare program links the thread runtime) | | | | server @1: 425.9M -> 393.2M Ir (-7.7%) | server traps @4 | identical @1 | 6.98 / 18.79; Rust 4.68 / 12.99 (5 b trap: they start threads) |

Hidden: orchestrator, box D, same trees (vs fastest geomean / worst; b = both-modes serial / parallel geomean;
parallel wall ±15-20%, box loaded). Visible: compare Ir (par-* at 4 threads, pool spin included); bothmodes serial
Ir at 1 thread, parallel wall at 4 threads n=3 vs `par.rs`. "base row used" = ablated build not valid for that
program (json: non-ASCII data under UNICODE, out of memory at 15.7 GB under RECLAIM; server: managed threads refuse
the arena, and THREADS traps at 4 threads), so its baseline ratio stays in the geomean. Trees
`/home/agent/minyar/abl-<config>`, raw results `/home/agent/minyar/abl-results/` (box D, deleted 09:40 UTC).

Wall checks (box D, bench lock, n=5 interleaved, ms): OVERFLOW off: grid 1,622 -> 1,794 (slower, matches its +8% Ir),
par-reduce 173 -> 130 (25% faster although Ir +23%: vectorised reduction), par-forkjoin 148 -> 136.
THREADS off on server @1: Ir -7.7% but wall 2,305 -> 3,397 ms (n=3; the plain runtime's I/O path waits differently,
not CPU) - so the thread-runtime tax on this program is ~8% Ir, not wall.

Instructions removed by each switch (% of baseline Minyar Ir; bm- = bothmodes at 1 thread; '-' = not valid):

| program | overflow | bounds | unicode | reclaim | scheduler | all |
|---|---:|---:|---:|---:|---:|---:|
| bytecode | 2.9 | 2.9 | 0.0 | 0.0 | -145.2 | 37.0 |
| config | 0.1 | 0.3 | 0.2 | 45.5 | 21.3 | 46.1 |
| exprparse | 1.8 | -0.0 | 5.8 | 75.8 | 43.9 | 81.7 |
| grid | -8.2 | 5.9 | -0.0 | 17.3 | 6.4 | 0.6 |
| httpparse | -0.0 | 0.2 | 0.3 | 44.4 | 18.1 | 44.7 |
| intmap | 0.3 | -0.0 | -0.0 | 11.0 | 3.3 | 11.6 |
| inventory | 0.5 | 0.4 | -0.0 | 69.0 | 37.1 | 69.7 |
| json | 0.1 | 0.5 | - | - | 34.2 | - |
| logstats | -0.0 | 0.3 | 0.1 | 29.2 | 3.6 | 29.7 |
| matrix | -0.4 | 0.3 | -0.0 | 5.1 | 3.0 | 5.6 |
| nbody | -0.0 | -0.0 | -0.0 | 2.9 | -78.3 | 2.9 |
| orders | 0.7 | 4.7 | -0.0 | 10.8 | -6.5 | 16.2 |
| par-forkjoin | 17.9 | 0.0 | -0.0 | 11.2 | 5.2 | 29.1 |
| par-mandel | 1.0 | 0.4 | -0.0 | 2.0 | 1.3 | 3.5 |
| par-reduce | -22.5 | 1.4 | 0.0 | 1.0 | 1.0 | -20.1 |
| service | -0.0 | 0.1 | -0.1 | 34.4 | 13.7 | 34.5 |
| sortrows | 1.7 | 0.0 | 0.0 | 3.5 | -23.7 | 5.2 |
| sorttext | -0.0 | 0.2 | 0.0 | 15.3 | -23.6 | 15.5 |
| textops | 0.2 | 0.3 | 0.6 | 38.2 | 15.6 | 39.5 |
| tokenizer | 0.5 | 0.3 | 3.8 | 40.9 | 7.4 | 45.9 |
| treewalk | 0.4 | 0.6 | -0.0 | 68.9 | -5.8 | 70.0 |
| wordfreq | 0.5 | 0.0 | 0.4 | 19.2 | 4.3 | 19.8 |
| bm-forkjoin | 2.0 | 5.5 | 0.0 | 4.5 | 2.5 | 12.0 |
| bm-mapreduce | 0.1 | 4.9 | -0.0 | 13.7 | -11.3 | 19.5 |
| bm-server | 2.2 | 0.4 | 0.0 | - | 12.0 | - |
| bm-sort | 1.1 | 16.3 | 0.0 | 5.0 | 3.6 | 24.8 |
| bm-textindex | 1.4 | 7.1 | -0.0 | 19.4 | 11.0 | 32.0 |
| bm-topk | -1.3 | 23.1 | -0.0 | 2.0 | 1.2 | 22.8 |
## Classification of every known cause

DEBT = the same semantics allow a cheaper implementation (fix, no approval). TRADE-OFF = cost of a guarantee
(Luke decides). Several causes are mixed: the guarantee is a trade-off, but most of today's cost of it is debt.

| id | cause (source report) | class | why |
|---|---|---|---|
| U1 | Text pieces are heap objects (split/slice views, copies) | DEBT | immutable Text allows borrowed views/iterators; peers scan in place with the same safety |
| U2 | Map ops probe 2-3 times | DEBT | one-probe lowering is semantics-preserving (exists on codegen-map-update) |
| U3 | interpolation via generic varargs runtime | DEBT | compiler knows every part's kind |
| U4 | `text[i]` costs 13-15 Ir | mostly DEBT, part TRADE-OFF T3 | UNICODE ablation removes only 0-6% Ir; the rest is check placement/reloads (alias facts, hoisting) |
| U5 | sorting: generic merge sort, thunk + closure per compare | DEBT (+ small T6 part) | specialised/monomorphised sorts keep stability; the closure's TLS domain check is a thread-safety cost (T6) |
| U6 | non-escaping aggregates on the heap | DEBT | escape analysis keeps semantics |
| U7 | one TBAA tag for all fields, no Text-header TBAA | DEBT | facts the language already guarantees |
| U8 | List append dispatches on ownership kind at run time | DEBT | element kind is static |
| U9 | json library representation | DEBT | library design |
| U10 | parse-from-slice allocates a view | DEBT | read-once views can be borrowed |
| U11 | checked arithmetic blocks reassociation/vectorisation | TRADE-OFF T1 | overflow is a guarantee; range proofs (c) keep it |
| U12 | allocator 26+18 Ir per object | DEBT | size-class/slab allocator, same semantics |
| U13 | SLP vectorisation of a scalar recurrence (par-mandel) | DEBT | codegen choice |
| U14 | no in-place filter | DEBT | `retain`-style API/lowering keeps semantics |
| U15 | checked index arithmetic in kernels (overflow + bounds + reloads) | mostly DEBT, part T1/T2 | BOUNDS/OVERFLOW ablations remove 0-6% on the kernels; header reloads and per-step re-checks are debt; range facts (c) remove the rest legally |
| O1 | objects freed through the bounded scheduler cost 25-80 Ir/unit | mixed: TRADE-OFF T4 + DEBT | see T4/T5 below: the bound itself is a guarantee, the per-object cost is mostly implementation |
| O2 | `Ok(...)` of a reference is a heap record; `try` takes a field | DEBT | representation |
| O3 | scope cells zeroed/tested on every call | DEBT | liveness of written cells only |
| O4 | loops that own nothing poll the scheduler | DEBT (T4 machinery) | a loop that frees nothing needs no poll |
| O5 | pool tasks cannot run ordinary code | TRADE-OFF T7 today, DEBT in design | the race-freedom guarantee does not require the scalar-only restriction |
| C1 | parallel code is a scalar sublanguage | TRADE-OFF T7 (restriction), largely liftable | same as O5 |
| C2 | thread runtime slower for managed code even on one thread | TRADE-OFF T6 + DEBT | see T6 |
| C3 | no shared read-only managed data | TRADE-OFF T7 | frozen/immutable sharing keeps race freedom: liftable (DEBT-like) |
| C4 | outputs must be fixed windows indexed by the loop variable | TRADE-OFF T7 | race freedom by construction; growing per-task outputs keep it (liftable) |
| C5 | `join` arguments read-only (no in-place divide-and-conquer) | TRADE-OFF T7 | disjoint sub-window borrows keep race freedom (liftable) |
| C6 | idiomatic serial paths slow (List.sort, records per element) | DEBT | same as U5/U6/U12 |
| C7 | single-threaded event loop | DEBT (landed e870232d8) | |
| C8 | per-call bookkeeping (call-depth counter) | TRADE-OFF (stack-overflow diagnosis), now ~0 | guard pages (calls lane) make it zero-cost |
| C9 | pool dispatch 1,435 Ir / 1.9 us per loop | DEBT | scheduling implementation |
| new N1 | record-field length checks (codegen audit) | DEBT, fixed | static field index; the record helper has no check at a886425c8 |
| new N2 | release target was baseline x86-64 | DEBT, fixed (x86-64-v3 default) | |
| new N3 | cycle runtime collection cost when a program builds cyclic-capable graphs with `List.add` (judge.md: tens of seconds vs <1 s with `appended`) | TRADE-OFF T8 | automatic cycle collection is a guarantee; no suite program links the cycle runtime |
| new N4 | OVERFLOW off raises Ir on grid/par-reduce | finding | LLVM re-plans loops once adds are plain `nsw`; see T1 |


## Trade-offs in detail

### T1 Checked integer overflow (U11, part of U15)
Buys: arithmetic never silently wraps; overflow stops with a diagnostic. Switch: `%checked` intrinsics -> `nsw`
(C semantics). Cost: visible geomean 3.60 -> 3.60; largest wins bytecode 2.9%, exprparse 1.8%, sortrows 1.7%,
par-forkjoin 17.9% (Ir at 4 threads). Regressions: grid +8.2%, par-reduce +22.5% Ir (LLVM re-plans unrolling/
vectorisation once the adds are plain; wall: grid 10% slower, par-reduce 25% faster). Hidden -0.5%. Options: (a) keep; (c) range facts so loop
counters/indexes skip the check (keeps semantics); (d) a per-scope wrapping block; (e) drop. Recommend (a)+(c).

### T2 Bounds checks (part of U15)
Buys: no out-of-range read/write. Switch: inline List/Bytes position checks always pass (runtime-internal checks
stay). Cost: visible 3.60 -> 3.57 (orders 4.7%, grid 5.9%, bytecode 2.9%); both-modes serial 1.95 -> 1.76
(topk 23%, sort 16%, textindex 7%, forkjoin 5.5%, mapreduce 4.9%); hidden -1.3% (b serial 4.17 -> 3.99). Rust pays
the same check. Options: (a) keep; (c) versioned loops: one hoisted check per window/loop, range facts for `a + i`
indexes; (d) per-scope unchecked block; (e) drop. Recommend (a)+(c): the kernel cost is check placement, i.e. DEBT.

### T3 Unicode Character indexing (part of U4)
Buys: `text[i]` and `text.length` count Characters, never split a code point. Switch: byte index/length (valid only
on ASCII data; json decodes `\u00e9` and fails, excluded). Cost: visible -0.6% (exprparse 5.8%, tokenizer 3.8%);
hidden -2.8%. U4's remaining 13-15 Ir per index is reload/re-validation (DEBT). Options: (a) keep; (b) ASCII-known
fast path hoisted per loop; (c) prove ASCII per Text once; (d) explicit byte APIs for parsers; (e) byte semantics.
Recommend (a)+(b)+(d).

### T4 Bounded reclamation scheduler (O1, O4; codegen-audit #5)
Buys: cleanup work per step is bounded, so releasing a large structure never causes a long pause (tail latency).
Switch: eager profile (`--scope-owners`, free at once). Cost: visible 3.60 -> 3.51, but exprparse 16.6x -> 9.3x,
json -34%, inventory -37%, config -21%; eager is *slower* on bytecode (+145%), nbody (+78%), sortrows/sorttext (+24%)
because the eager path lacks the bounded path's recent ownership codegen (so the true price is larger than the
geomean shows). Hidden 6.98 -> 5.19 (-26%), worst 18.8 -> 14.4. Options: (a) keep as is; (b) near zero-cost:
free leaves and unshared objects immediately inside the budget, batch-free Lists of leaves, no polls in loops that
free nothing (O1/O4, DEBT); (d) eager per program already exists (`--memory-profile eager`); (e) eager default.
Recommend (b) now; Luke decides (e) for batch programs after (b) lands.

### T5 Reclamation at all (RC, frames, deferred frees)
Buys: memory is returned deterministically without a tracing GC. Switch: arena runtime (never free; RC/frames
no-ops). Cost: visible 3.60 -> 2.53 (exprparse 76%, inventory 69%, treewalk 69%, config 46%, httpparse 44%,
tokenizer 41%, textops 38%, service 34%, logstats 29%); hidden 6.98 -> 3.59 (-49%); json and 5 hidden both-modes
programs run out of memory, so (e) is not an option. C/C++/Rust free too: their alloc+free is ~5 Ir/object vs
Minyar's 44 (U12) plus RC and per-element teardown, so most of this column is DEBT. Options: (a) keep; (c) escape
analysis/stack and inline storage (U6), borrowed Text views (U1); (d) opt-in region scopes (language feature).
Recommend (a)+(c); (d) is a feature proposal for Luke.

### T6 Thread runtime tax (C2)
Buys: managed values are safe to hand between threads. Switch: plain runtime for programs carrying the thread marker
(starting a thread traps). Visible: only bothmodes/server links it; hidden: 5 b programs start threads (not
measurable by the switch); bothmodes/server at 1 thread: 425.9M -> 393.2M Ir (-7.7%) without it. C2 measured +29-50% Ir at 1 thread on managed code. Recommend (b): single-thread paths
pay nothing (per-thread heaps without TLS indirection when no thread was started) - mostly DEBT.

### T7 Parallel restrictions (C1, C3, C4, C5, O5)
Buys: no data races by construction. Not switchable (programs would not compile). Cost seen as serial fallbacks
(textindex 84%, mapreduce 44% of Ir) and parallel geomean 1.98x `par.rs`. Recommend keep race freedom and lift
the restrictions it does not need (C1/C3/C4/C5 have race-free designs in reports/serial-and-parallel.md).

### T8-T11
Cycle collection: zero-cost when unused (no suite program links the cycle runtime); its pathology on
`List.add`-built trees is collector DEBT. Live patching: no patch points in `--release`. Stack-overflow diagnosis: ~0
after guard pages. Determinism: no measurable cost found.

