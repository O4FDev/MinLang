# Why Minyar is still slower: profile-backed causes for every visible benchmark over 1.1x (2026-10-30)

## FINAL 2026-11-01 (release candidate 7d4576591, box B same-box run, cachegrind Ir)
Geomean 2.25 vs fastest (baseline 5.32), 1.81 vs Rust. Programs over 1.1x keep the cause and owner listed in the 04:00 table below;
what landed since then: borrow inference (treewalk −24.8%), Text runtime scans (logstats −8.7%), cheaper reclamation (httpparse −2.2%,
exprparse −1.9%, json −1.8%), last-use moves (exprparse −1.8%), guarded List-walk loops (grid −0.9%).

| program | ratio vs fastest | fastest | vs Rust |
|---|---|---|---|
| json | 6.25 | c | 3.71 |
| grid | 4.81 | c | 3.56 |
| inventory | 4.58 | rust | 4.58 |
| exprparse | 4.55 | c | 3.58 |
| config | 3.84 | c | 2.54 |
| httpparse | 3.50 | rust | 3.50 |
| tokenizer | 3.42 | c | 3.16 |
| textops | 3.17 | cpp | 1.87 |
| bytecode | 2.88 | c | 1.11 |
| logstats | 2.34 | c | 1.29 |
| wordfreq | 2.06 | c | 1.74 |
| sortrows | 1.92 | cpp | 1.48 |
| intmap | 1.85 | rust | 1.85 |
| orders | 1.83 | cpp | 1.68 |
| par-forkjoin | 1.81 | c | 1.81 |
| sorttext | 1.50 | rust | 1.50 |
| service | 1.38 | cpp | 0.89 |
| treewalk | 1.33 | c | 1.14 |
| nbody | 1.30 | cpp | 1.28 |
| par-mandel | 1.20 | c | 1.19 |
| matrix | 1.10 | c | 1.07 |
| par-reduce | 0.83 | rust | 0.83 |

## STATUS 2026-11-01 04:00 UTC — every visible program over 1.1x, at goal tip f939afb71 (box K, cachegrind Ir)
Geomean 2.32 vs fastest (was 5.32 at the 3832f4373 baseline and 2.52 at the start of run 2); 1.87 vs Rust. Dominant
remaining cost per program from the run-2 visible profile (reports/next-phase.md "Visible programs"); the cause catalogue and
per-program sections below still hold, with the ratios superseded by this table.

| program | ratio 2026-10-30 | ratio now | vs Rust | dominant remaining cost (profile) | fix in flight / owner |
|---|---|---|---|---|---|
| json | 12.17 | 6.38 | 3.79 | reclamation 23% + allocation 17% + Text 17% (parseValue, small-aggregate retirement) | esc (inline slots), res2 (eager retirement), txt3 |
| exprparse | 17.16 | 4.74 | 3.73 | user 64% (Parser.peek/unary: Result and record traffic), RC 16% | brw (borrow inference, next: move-into-call ≈7%), cg |
| grid | 5.36 | 4.86 | 3.59 | user 96%: 5-point stencil, checked adds block vectorisation | cg (pragma unroll −25% READY path; range-guarded unchecked loop version) |
| inventory | 6.22 | 4.58 | 4.58 | user 67% + List 12% (merge sort) + RC 10% | esc/fbip (List storage), cg (sort) |
| config | 7.58 | 3.94 | 2.61 | user 40% + Text 35% + Map 8% | txt3 (join/search/slice), map (landed: −2.7%) |
| httpparse | 5.47 | 3.62 | 3.62 | Text 35% + RC 19% + allocation 12% | txt3, res2 |
| tokenizer | 5.69 | 3.46 | 3.20 | user 64% (tokenize) + allocation 14% + Text 14% | cg, txt3 |
| textops | 5.54 | 3.28 | 1.94 | Text 42% (text_search_next 14%) + RC 17% | txt3 (search), res2 |
| bytecode | 2.88 | 2.88 | 1.11 | user 100%: interpreter dispatch loop | cg |
| logstats | 5.84 | 2.67 | 1.47 | Text 45% (split/slice) — positional split landed (−47%) | txt3 |
| wordfreq | 3.94 | 2.11 | 1.79 | user 49% + split_next 24% | txt3, map (landed −3%) |
| sortrows | 4.11 | 1.92 | 1.48 | List sort 96% (record merge sort) | cg (sort kernels) |
| intmap | 2.98 | 1.85 | 1.85 | user 86% (inlined Map probes) | map (landed −5.7%) |
| orders | 2.20 | 1.84 | 1.69 | user 79% + sort 11% | cg |
| par-forkjoin | 1.99 | 1.81 | 1.81 | user 100% (serial fib + combine) | cg |
| treewalk | 4.59 | 1.77 | 1.52 | user 88% + allocation 12% | brw (−24.7% in candidate r2n), esc/fbip |
| sorttext | 2.48 | 1.54 | 1.54 | List sort 60% + Text compare 16% | txt3, cg |
| service | 4.07 | 1.43 | 0.92 | Text 36% + RC 28% (split landed −45%) | txt3, res2 |
| nbody | 1.63 | 1.30 | 1.28 | user 100% Float math; FMA contraction would give 1.11 (trade-off for Luke) | cg (FMA held for Luke) |
| par-mandel | 1.21 | 1.20 | 1.19 | user 100% parallel escape loop | cg |
| matrix | 1.12 | 1.10 | 1.07 | user 98% multiply-add | cg |
| par-reduce | 0.84 | 0.83 | 0.83 | faster than every peer | — |

Lane `perfgaps`, branch `goal/2026-10-30-perfgaps` = goal/integrate-ownership `2d1d5d632` (goal base + codegen +
systems + ownership + stdlib + parallel lanes). Analysis only: no compiler, runtime or library change.

## Method

- Box D (Linux x86-64 AMD EPYC, 4 vCPU), LLVM 23.1.3, every measurement under `/home/agent/bench.lock`.
- Ratios: `python3 benchmarks/compare/run.py --json ...` (cachegrind `--cache-sim=no`, all threads, full workload,
  every output byte-identical to C, C++ and Rust) and `python3 benchmarks/bothmodes/run.py --repeats 5`
  (serial = Minyar Ir at 1 thread / best serial Ir; parallel = Minyar wall at 4 threads / std-only parallel Rust at 4).
  `benchmarks/bothmodes` is not on this branch; it was checked out from goal/2026-10-30-bothmodes (010e8ba26) unchanged.
- **Two trees.** "now" = this branch. "+owned" = a scratch tree (`goal/2026-10-30-perfgaps-next`, not for landing) with
  the owned but not yet integrated work cherry-picked on top: ownership2 (141c5cde9 scope cells, 0395fa569 local
  scheduler state, d5637f81e try-consumption of cycle-capable Results, 41fe68afa/d04230fa4 scalar choice cases) and
  calls (e5f4f68a5 guard pages + 3 follow-ups). `run.py --check` on box D: 22/22 programs match C at O0 and release.
  Root causes below are attributed on the "+owned" tree, so they are what is left *after* the owning lanes land.
- Profiles: full-size cachegrind function tables of the measured binaries (`.perfgaps/classify.py`, cost classes by
  symbol); callgrind `--dump-instr=yes` on a `-g` release build at about 1/10 of the workload for every program
  (`.perfgaps/cgprof.sh NAME N`: per-function, per-source-file and per-instruction Ir joined with `objdump`); the
  fastest reference cachegrinded with `-g` on the full input. Instruction-level reading of the hot loops of both.
  Shares below are percent of Minyar Ir; "Ir/unit" divides by the program's unit of work.
- Generated Minyar code carries no debug lines, so inlined runtime helpers (bounds checks, Text indexing, List
  append, RC fast paths, scope cells) count as "user" code; where it matters the hot instructions were read and
  attributed by hand (named in each section).
- Owners: `ownership2` (scope cells, reclamation scheduler, call-releases-nothing effect, Results without heap,
  frames, acyclic recursive types), `calls` (guard-page stack checks, inlining, attributes), `parallel2` (tasks
  running ordinary code, shared frozen data, growing outputs, in-place join). Lanes that have finished (codegen,
  stdlib, systems, ownership, parallel, bothmodes) own nothing now; their leftovers are listed as **unowned**.
- "Expected gain" numbers are estimates from the measured shares (share x the fraction a fix removes, stated per
  cause), not measurements of a fix.

## Results: ratio now vs the visible baseline

`benchmarks/compare` (box D; baseline = visible lane 98152d6f0, whose box-B numbers equal box D's to the instruction
per the codegen/calls lanes; par-forkjoin baseline = parallel lane 42b1cbc46). Geomean **5.32 -> 3.68 now -> 3.22
with the owned work**. Every program except par-reduce is still over 1.1x.

| program | baseline Ir | baseline | now Ir | **now** | +owned Ir | **+owned** | fastest ref | ref Ir |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| exprparse | 42,139M | 28.34 | 25,518M | **17.16** | 13,758M | 9.25 | c | 1,487M |
| json | 14,452M | 16.50 | 10,659M | **12.17** | 8,197M | 9.36 | c | 876M |
| config | 5,410M | 8.16 | 5,021M | **7.58** | 3,780M | 5.70 | c | 663M |
| inventory | 6,893M | 6.41 | 6,692M | **6.22** | 5,339M | 4.97 | rust | 1,075M |
| logstats | 5,757M | 6.33 | 5,309M | **5.84** | 5,265M | 5.79 | c | 909M |
| tokenizer | 6,024M | 5.74 | 5,972M | **5.69** | 4,859M | 4.63 | c | 1,050M |
| textops | 5,665M | 5.83 | 5,388M | **5.54** | 4,921M | 5.06 | cpp | 972M |
| httpparse | 17,566M | 12.04 | 7,977M | **5.47** | 6,780M | 4.65 | rust | 1,459M |
| grid | 10,294M | 5.38 | 10,255M | **5.36** | 9,776M | 5.11 | c | 1,914M |
| treewalk | 38,265M | 13.72 | 12,812M | **4.59** | 7,572M | 2.72 | c | 2,789M |
| sortrows | 3,300M | 5.09 | 2,664M | **4.11** | 2,301M | 3.55 | cpp | 649M |
| service | 3,232M | 4.26 | 3,092M | **4.07** | 2,873M | 3.78 | cpp | 759M |
| wordfreq | 4,221M | 4.08 | 4,083M | **3.94** | 4,045M | 3.91 | c | 1,035M |
| intmap | 3,554M | 4.49 | 2,358M | **2.98** | 2,264M | 2.86 | rust | 792M |
| bytecode | 9,770M | 6.05 | 4,645M | **2.88** | 4,645M | 2.88 | c | 1,614M |
| sorttext | 3,396M | 3.31 | 2,542M | **2.48** | 2,367M | 2.31 | rust | 1,026M |
| orders | 504M | 2.68 | 414M | **2.20** | 390M | 2.07 | cpp | 188M |
| par-forkjoin | 1,266M | 1.99 | 1,266M | **1.99** | 1,219M | 1.91 | c | 637M |
| nbody | 4,035M | 3.69 | 1,779M | **1.63** | 1,719M | 1.57 | cpp | 1,094M |
| par-mandel | 2,247M | 1.56 | 1,745M | **1.21** | 1,735M | 1.20 | c | 1,444M |
| matrix | 2,938M | 3.43 | 959M | **1.12** | 945M | 1.10 | c | 857M |
| par-reduce | 2,129M | 0.93 | 1,927M | **0.84** | 1,919M | 0.83 | rust | 2,300M |
| **geomean** | | **5.32** | | **3.68** | | **3.22** | | |

`benchmarks/bothmodes` at this tree (box D, load average 4.9-5.5 from a gate outside the bench lock, so the wall
columns are +-15-20%; "was" = the bothmodes lane's final table, tree bb09cb359):

| program | serial Ir@1 / best | was | parallel wall@4 / Rust@4 | was | Ir@4 Minyar / Rust | scaling Minyar / Rust |
|---|---:|---:|---:|---:|---:|---|
| topk | **2.63** (c) | 2.63 | **1.32** | 1.47 | 1.90 | 2.15 / 1.95 |
| textindex | **2.68** (c) | 2.69 | **2.70** | 2.96 | 1.70 | 0.91 / 1.67 |
| sort | **2.10** (c) | 2.10 | **2.11** | 2.51 | 1.62 | 2.05 / 1.31 |
| mapreduce | **1.89** (rust) | 1.89 | **2.17** | 2.46 | 1.47 | 1.26 / 1.23 |
| server | **1.55** (c) | 2.22 | 0.92 | 1.04 | 0.36 | 2.56 / 2.23 |
| forkjoin | **1.39** (c) | 1.39 | 1.04 | 1.06 | 1.15 | 1.79 / 1.80 |
| geomean | **1.98** | 2.10 | **1.58** | 1.76 | | |

server's serial ratio fell 2.22 -> 1.55 because the parallel lane's thread-runtime commits are on this branch
(92426765e shared ASCII literals, 2d1d5d632 Text/List storage on the thread's small heap). Over 1.1x: every serial
column, and the parallel column of topk, textindex, sort and mapreduce.

## Where the remaining instructions go (+owned tree, full workload, percent of Minyar Ir by cost class)

Classes by symbol: sched = `rc_bounded_service`/`step_chunks`/polls; rc = retain/release/take/set-reference calls;
alloc = small-heap allocate/free, `list_grow`; text, map, list/sort = those runtime families; libc = mem*/printf;
user = generated code including everything inlined into it.

| program | Minyar Ir/unit | ref Ir/unit | unit | sched | rc | alloc | text | map | list/sort | libc | user |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| json | 81,970 | 8,760 | user record | 25 | 6 | 15 | 17 | 1 | 2 | 4 | 28 |
| exprparse | 1,101 | 119 | expression node | 18 | 12 | 14 | 8 | 0 | 0 | 0 | 47 |
| logstats | 2,632 | 454 | line | 18 | 2 | 9 | 53 | 10 | 2 | 3 | 3 |
| config | 8,310 | 1,457 | parsed entry | 6 | 6 | 9 | 32 | 24 | 0 | 5 | 17 |
| grid | 204 | 40 | cell x generation | 0 | 0 | 1 | 0 | 0 | 0 | 3 | 96 |
| textops | 12,302 | 2,430 | line | 14 | 5 | 11 | 50 | 2 | 0 | 5 | 10 |
| inventory | 1,780 | 358 | operation | 22 | 3 | 3 | 0 | 0 | 6 | 6 | 60 |
| httpparse | 16,950 | 3,648 | request | 15 | 4 | 10 | 39 (+3 unicode) | 12 | 0 | 3 | 12 |
| tokenizer | 935 | 202 | token | 0 | 5 | 12 | 11 | 22 | 0 | 5 | 42 |
| wordfreq | 708 | 181 | word | 11 | 1 | 5 | 29 | 38 | 2 | 9 | 5 |
| service | 2,873 | 759 | request | 16 | 4 | 10 | 58 | 4 | 2 | 0 | 5 |
| sortrows | 11,507 | 3,243 | row (7 sorts) | 0 | 2 | 0 | 0 | 0 | 60 | 3 | 35 |
| bytecode | 24 | 8.4 | VM instruction | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 100 |
| intmap | 2,264 | 792 | edge | 0 | 0 | 4 | 0 | 73 | 3 | 5 | 16 |
| treewalk | 1,709 | 629 | interpreted call | 0 | 12 | 15 | 0 | 0 | 0 | 0 | 73 |
| sorttext | 5,917 | 2,566 | word | 6 | 2 | 3 | 14 | 0 | 39 | 3 | 33 |
| orders | 32 | 16 | order x pass | 0 | 0 | 7 | 0 | 0 | 18 | 1 | 74 |
| par-forkjoin | 129 | 67 | List element | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 100 |
| nbody | 573 | 365 | step | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 100 |
| par-mandel | 17.3 | 14.4 | escape iteration | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 100 |
| matrix | 4.4 | 4.0 | multiply-add | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 99 |

The owned work replaces heap frames with inline scope cells (the frame class drops to 0; their remaining cost is
inside "user") and removes most RC calls; what is left is dominated by five
things: (1) Text values materialised as heap objects (split Lists, slice views, per-line copies) and their teardown,
(2) the reclamation scheduler's per-object cost for what is still freed through it, (3) Map operations probed two or
three times per source operation, (4) generic, closure-driven sorting, and (5) generated scalar code that re-checks
and reloads (Text indexing, List append dispatch, bounds/overflow checks, header reloads after stores).

## Cause catalogue (ids used in the program sections)

Unowned (no active lane):
- **U1 Text pieces are heap objects.** `split` builds a full `List<Text>` of 48-byte view objects
  (`runtime/minyar_text.h:103`), each view retains its root; a slice that is under 1/8 of a source over 4 KiB is
  *copied* (`runtime/minyar_runtime.c:1166-1172`), so every line of `file.split("\n")` is a malloc + memcpy; the
  List, the views and the copies are then torn down through the scheduler. C/C++/Rust scan in place (pointer + length).
- **U2 Map operations probe 2-3 times per source operation.** `if m.has(k) { m[k] += 1 } else { m[k] = 1 }` and
  `m.has(a) ... m[a]` pay `has` + `get` + `set` (recovery checks, read guards, memo, hash) — `runtime/minyar_maps.h:245-330`.
  A one-probe lowering exists on `goal/2026-10-30-codegen-map-update` (tested) but was not landed because adding
  entry points to `minyar_maps.h` changed clang's LTO inlining of `has`/`map_find` (codegen report).
- **U3 String interpolation is a generic varargs runtime call.** `minyar_interpolate` (`runtime/minyar_runtime.c:1432`)
  switches on a kind code per part, formats integers one digit per division (`write_integer_digits`), copies every
  literal part through `interpolation_bytes`; the compiler knows every part's kind and every literal's length.
- **U4 `text[i]` in scanning loops.** Each Character index runs `minyar_text_character_at`
  (`runtime/minyar_runtime.c:1110`): negative-length sentinel test, bounds test, offsets-table test, then the byte;
  the Text header loads carry no Minyar TBAA, so they are reloaded after every record-field store (`self.position += 1`).
  ~13-15 instructions per index and two indexes per comparison chain (`self.text[p] >= '0' && self.text[p] <= '9'`).
- **U5 Sorting.** `sortBy` calls a compiler thunk (`.minyar.sort.compare.N`: callback check + 2 record reads) that calls
  the closure (TLS domain check, field reads) from a recursive top-down merge sort with no small-sort base case or run
  detection (`runtime/minyar_sort.h:63`, `:237`; `compiler/closure-compiler.min:3-31`). Text comparators written as
  `a.key < b.key` then `a.key > b.key` compare the bytes twice.
- **U6 Non-escaping aggregates live on the heap.** A `List` or `Text` that never leaves its function (treewalk's
  per-call `frame`, tokenizer's `source.slice(i, i + 2)` probe) is heap-allocated, grown from capacity 2 and freed;
  C/Rust use the stack. Needs escape analysis + stack/inline storage.
- **U7 Alias precision.** All record fields share one TBAA tag and Text headers have none, so `self.stack`,
  `self.text` and List headers are reloaded after every field store (bytecode, exprparse, grid); `self.executed += 1`
  cannot be kept in a register.
- **U8 List append dispatches at run time.** `minyar_list_add` (`runtime/minyar_collections.h:124`) tests the List's
  ownership kind (`& 7`, three compares) and polls the scheduler on every add, although `List<Integer>`/`List<Record>`
  is static; ~25-40 instructions per append in the measured loops vs ~4 in C.
- **U9 json library representation.** Every scalar leaf is a 6-field `Value` with two fresh empty Lists
  (`library/json.min:40`), members are found by linear Text comparison (`library/json.min:474`), numbers are parsed to
  Float and converted back (`asInteger`), and the whole tree is torn down object by object.
- **U10 Parse-from-slice.** `Integer(t.slice(a, b))`, `trim()`/`slice()` chains allocate a view only to read it once.
- **U11 Checked arithmetic blocks loop transforms.** `llvm.sadd.with.overflow` is not reassociable, so LLVM cannot do
  accumulator tail-recursion elimination (`fib(n-1) + fib(n-2)`) or vectorise reductions. Language semantics; only
  range proofs remove it.
- **U12 Allocator cost per object.** `rc_heap_allocate` ~26 Ir + `rc_system_deallocate` ~18 Ir per object
  (`runtime/minyar_system_small_heap.h:71-133`, measured exprparse/treewalk) vs ~5 for the peers' arenas.
- **U13 SLP vectorisation of a scalar recurrence** (par-mandel): real/imaginary packed into one xmm with 3 shuffles
  per iteration; clang keeps the C loop scalar.
- **U14 No in-place filter.** `kept = []; for x in xs { if p(x) { kept.add(x) } }; xs = kept` is the only idiom: it
  retains every survivor and then releases the old List element by element through the scheduler. Rust uses
  `Vec::retain`, C compacts in place.

- **U15 Checked index arithmetic in scalar kernels.** In the both-modes kernels every `xs[a + i]` carries an
  overflow test on the index expression and a bounds test, and List headers/values pointers or spilled indexes are
  reloaded inside the inner loop (topk DAAT loop ~21 instructions per posting step; sort merge-path ~20 per merged
  element). The Rust peers keep bounds checks but not overflow checks (topk Rust 8.4G vs C 5.9G vs
  Minyar 15.6G). Fix: range facts for induction/index values (an index proven `< length` cannot overflow `+ 1`),
  versioned loops with one hoisted bounds test per window, header loads hoisted out of call-free loops.

Owned (remaining work found inside an active lane's scope):
- **O1 ownership2 / scheduler:** objects still freed through `rc_bounded_service` cost 25-80 Ir per unit; dead
  Lists whose elements are still shared (inventory prune) or unique leaves (split views) are queued and visited one
  unit at a time instead of decremented/freed in a tight loop within the budget.
- **O2 ownership2 / Results without heap:** `Ok(...)` of a reference payload is still a heap record; `try` pays
  `minyar_record_take_field` (exprparse 5.8%, json 1.5%).
- **O3 ownership2 / scope cells:** a function with N cells zeroes all N at entry and tests/clears all N at exit
  (treewalk `execute`: 12 cells, ~60 instructions per call on a path that writes 2); `for x in list` over a parameter
  still retains each element twice when the body calls a function (no call-releases-nothing effect yet).
- **O4 ownership2 / polls:** loops that own nothing still poll `rc_pending_count` and the frame chunk queue at the
  back edge (par-forkjoin `main`, grid `step`, parser digit loops).
- **O5 parallel2:** pool tasks cannot run ordinary code (textindex 84% / mapreduce 44% of Ir forced serial), no
  in-place `join` over halves (sort), no growing per-task outputs (topk/textindex).
- calls: guard pages landed on its branch (sortrows -12%, treewalk/orders/sorttext -3..-4%). Remaining in its scope:
  bothmodes forkjoin's `parallel function combine` stays out of line in its recursive caller (~5-10% of that program).

## Per program (`benchmarks/compare`, ordered by the +owned ratio)

Numbers are full-workload Ir on the +owned tree unless marked "now"; "x% " = share of that program's Minyar Ir.

### exprparse — 17.16 now, 9.25 +owned (C 119 Ir per node, Minyar 1,101)
Profile (+owned, 13,758M): `rc_bounded_service` 2,474M 18.0%; `Parser.unary` (with `primary` inlined) 2,041M 14.8%;
`Parser.peek` 1,902M 13.8%; `evaluate` 1,148M 8.3%; `rc_heap_allocate` 1,120M + `rc_system_deallocate` 852M 14.3%;
`minyar_record_take_field` 794M 5.8%; `text_slice_bytes` 516M + `minyar_text_integer` 504M 7.4%; `minyar_rc_release`
436M + `minyar_record_set_reference` 404M 6.1%. C: `unary` 589M, `term` 343M, `evaluate` 293M, arena nodes, no frees.
About 3.3 heap objects per expression node (40.9M allocations at full size: Expr node, `Ok` wrappers, number slice).
Causes:
- O1 scheduler: every line's tree, its Results and Texts are retired through the bounded queue: 18%. (ownership2)
- O2 Results on the heap: `Ok(Expr)` at each of expression/sum/term/unary/primary; `take_field` 5.8% plus about
  a third of the allocations: ~10%. (ownership2, not started)
- U4 Text indexing: `peek`/`skipSpaces` and the digit loop index `self.text[self.position]` 2-3 times per character
  (~15 instructions each, header reloaded after each `self.position += 1` store, plus a `jo` per increment and a
  scheduler poll at the loop back edge, O4): ~24% of Ir; a hoisted ASCII byte path would remove ~60% of it (~14%).
- U10 `Integer(self.text.slice(start, self.position))`: 7.4% for a view object that is parsed once and freed.
- U12 allocator per object (~44 Ir) on the remaining node allocations: ~8%; the C peer uses an arena (benchmark note:
  arena allocation is idiomatic C; Minyar has no region allocation to match it).
Expected after O1+O2+U4+U10: roughly 13.8G -> 7G (ratio ~4.7).

### json — 12.17 now, 9.36 +owned (C 8,760 Ir per user, Minyar 81,970)
Profile: `rc_bounded_service` 2,051M 25.0%; `json.parseValue` 990M 12.1%; allocation 870M 10.6%;
`minyar_runtime_jsonStringEnd` 395M + `jsonNumber` 356M + `decimal_shift` 131M (number/string scanning) 10.8%;
`leaf` 329M 4.0%; `text_slice_bytes` 298M; memcpy 253M; `Value.get` 203M + `asInteger` 197M; `report` (quote +
interpolation + sort) 31% inclusive at 1/10. C: `parse_value` 456M, `parse_string` 280M, arena, strings point into input.
Causes:
- O1 scheduler: tearing down ~3M `Value` records, their Lists and Texts: 25%. (ownership2)
- U9 json representation: two empty Lists per scalar leaf, `leaf` record construction, linear `keys` scan in `get`,
  Float-then-Integer numbers: ~20% (allocation of the leaf Lists is about half of `alloc`; `leaf` 4%; `get`/`asInteger`
  5%; decimal path 4%). Fix in `library/json.min` (lazy or shared immutable empty Lists, Integer fast path when the
  literal has no fraction/exponent, index or hash for objects past a few members). Unowned (stdlib lane finished).
- U1/U12 string values sliced and copied (`text_slice_bytes` + memcpy 6.7%).
- U3 report: `json.quote` + interpolation of the output lines (~8%).
Expected after O1+U9: ~8.2G -> ~4.5G.

### logstats — 5.84 now, 5.79 +owned (C 454 Ir per line, Minyar 2,632)
Profile: `minyar_text_split` 1,529M 29.0%; `rc_bounded_service` 967M 18.4%; `text_slice_bytes` 822M 15.6%;
`minyar_text_integer` 361M 6.9%; `rc_system_deallocate` 252M + `rc_heap_allocate` 155M 7.7%; Map `has`/`hash`/`get`
509M 9.7%; `list_reserve` 108M; memcmp 110M. C: one pass over the buffer, hand-parsed fields, own hash table.
Causes:
- U1 Text pieces: per line, the line itself is copied out of the 2M-line file (slice < 1/8 of a >4 KiB root), then
  `line.split(",")` builds a List of 5 views; all of it is freed through the scheduler: split + slice + reserve +
  allocation + the scheduler share ≈ 70% of Ir. An iterator lowering of `for line in text.split(...)`, views that
  share the root's bytes without a copy, and indexed access `fields[k]` without materialising unused pieces would
  remove most of it.
- O1 scheduler: the dead `fields` Lists and line copies: 18% (overlaps U1; whichever lands first takes it).
- U2 Map: `services.has(fields[2])` then `services[fields[2]]` hashes the same Text twice: ~5%.
Ownership2's scope cells changed logstats by -0.8%: its cost is not in frames.

### config — 7.58 now, 5.70 +owned (C 1,457 Ir per entry, Minyar 8,310)
Profile: Map 865M 22.9% (`hash` 271M, `get` 258M, `has` 240M, `set` 96M); `text_slice_bytes` 387M 10.2%;
`minyar_text_trim` 264M 7.0%; `rc_bounded_service` 230M 6.1%; `parseConfig` 21.0% / `parseValue` 28.6% inclusive;
allocation 282M 7.5%; `minyar_text_split` 144M; `minyar_text_find` 106M; memcmp 102M; interpolation 132M.
C: 62% in `main` (single pass), 38% printf/snprintf for the output.
Causes:
- U2 Map: `config.sections.has(current)`, `self.sections.has(section) && self.sections[section].has(key)` then
  `self.sections[section][key]`: three to four hashes of the same keys per query: ~15% recoverable.
- U1/U10 Text pieces: `rawLine.trim()`, `line.slice(0, equals).trim()`, `value.slice(...)`, `split(",")` each allocate a
  view: slice + trim + split + allocation ≈ 27%; most are read once (prefix tests, Integer parse).
- O1 scheduler 6%. ownership2 already removed 24.7% (frames, Results at `try`).

### grid — 5.36 now, 5.11 +owned (C 40 Ir per cell-generation, Minyar 204)
Profile: `main` 96% (everything inlined); memcpy 2.7% (List growth); allocation 1%.
Hot loop (callgrind per instruction): per cell, `liveNeighbours` runs a 3-iteration `ny` loop whose `nx` loop is
unrolled; each `ny` step re-loads `cells[ny]` (outer List bounds test, row pointer, row header) and each neighbour
add carries `jo`; ~38 instructions per `ny` step, ~155 per cell, plus `row.add` (~15, U8) and a scheduler poll.
Causes:
- **Benchmark note:** the C/C++/Rust peers use a padded byte grid and a branch-free 8-neighbour sum; the Minyar
  program tests every neighbour against the edges inside nested loops over `List<List<Integer>>`. A literal C
  translation of the Minyar algorithm (rows as separately allocated int64 arrays, same bounds tests, growable
  queue, `.perfgaps/literal/grid_literal.c` in the lane worktree, byte-identical output) is **3,395M Ir**: the
  peers' algorithm accounts for 1.77x of the 5.11x, Minyar's code generation for the remaining **2.88x** over the
  same algorithm.
- U7 alias precision: the row pointer and List headers are reloaded per neighbour row because stores to `row`
  (List slots) and the loop's other stores are not provably disjoint from `cells` headers.
- U11 overflow checks on `count += cells[ny][nx]` (8 per cell) block if-conversion of the edge tests.
- U8 append: `row.add(...)` 4.8M times per generation with the kind dispatch and capacity reload.

### textops — 5.54 now, 5.06 +owned (C++ 2,430 Ir per line, Minyar 12,302)
Profile: `rc_bounded_service` 712M 14.5%; `minyar_text_split` 673M 13.7%; `text_slice_bytes` 532M 10.8%;
`text_search_next` 528M 10.7% (find/replace scanning); interpolation 443M 9.0%; allocation 380M 7.7%;
`minyar_rc_release` 234M; memchr 194M; `list_grow` 68M. C++: `main` 54%, memchr 27%, string_view throughout.
Causes: U1 (split/slice/teardown ≈ 40% incl. its scheduler share), U3 interpolation 9%, O1 scheduler 14.5%,
`text_search_next` (the `replaceAll` helper written with split + join because the program predates `Text.replace`;
the generic search is ~2x memchr per byte) ~5%.

### inventory — 6.22 now, 4.97 +owned (Rust 358 Ir per operation, Minyar 1,780)
Profile: `main` 2,866M 53.7% (prune loop, item updates, all inlined); `rc_bounded_service` 1,174M 22.0%; memcpy
305M 5.7%; sort 6% (`list_sort_merge` 134M, `list_sort_compare` 95M, thunk 86M, closure 82M); `minyar_rc_release`
156M; `Warehouse.take` 143M; `Catalog.newItem` 116M.
The hot loop is `Warehouse.prune` (every 1,024 operations over ~23k items): per surviving item `kept.add(item)` costs
~40 instructions (kind dispatch, retain `count += 8`, store, poll), then `self.items = kept` drops the old List and the
scheduler visits every element again (~25-50 Ir each). Rust uses `items.retain(...)` in place; C compacts in place.
Causes: U14 + O1 (~60% of Ir together), U8 append, U5 sort ~6%. ownership2 already removed 20% (statement temporaries).

### httpparse — 5.47 now, 4.65 +owned (Rust 3,648 Ir per request, Minyar 16,950)
Profile: `rc_bounded_service` 1,020M 15.0%; `text_slice_bytes` 617M 9.1%; interpolation 844M 12.4%;
`minyar_text_split` 286M; `text_search_next` 272M + `minyar_text_find` 182M; Map 705M 10.4% (per-request
`Map<Text, Text>` of headers: `set` 246M, `hash` 229M, `has` 190M); `unicode_case` 199M 2.9% (ASCII fast path landed);
`minyar_text_trim` 151M; allocation 621M 9.2%; `Server.handle` 18% inclusive. Rust: `main` 50% + `fmt::write` 35%.
Causes: U1 (the request stream split into header lines, each line split again, every piece a view; ~30% with
teardown), U3 interpolation + `+` concatenation of the response head (12%), U2 Map (header Map built and probed with
`has` then `[]`: ~5%), O1 scheduler 15%.

### tokenizer — 5.69 now, 4.63 +owned (C 202 Ir per token, Minyar 935)
Profile: `tokenize` 34% self, 73% inclusive; Map/Set 1,071M 22.0% (`has` 507M, `hash` 328M); allocation 494M 10.2%;
`text_slice_bytes` 408M 8.4%; `minyar_rc_release` 174M; memcmp 135M; `append_in_place` 113M (string literal
building); `minyar_text_integer` 82M.
Causes:
- U4 `source[i]` Character indexing in every scanning loop (`while i < length && (isLetter(source[i]) || isDigit(source[i]))`
  indexes twice per character): most of `tokenize`'s self 34%; the C peer walks a byte pointer.
- U2 `identifiers.has(t)` then `identifiers[t] += 1` (3 probes) and `keywords.contains(word)`: ~10% recoverable.
- U6 `twoCharacterOperators.contains(source.slice(i, i + 2))` allocates a 2-byte view per operator character (1.5M).
- U1/U12 every token's Text is a heap view + a `Token` record (needed: tokens are kept), ~15%.

### wordfreq — 3.94 now, 3.91 +owned (C 181 Ir per word, Minyar 708)
Profile: Map 1,540M 38.1% (`has` 554M, `set` 351M, `hash` 320M, `get` 315M); `minyar_text_split` 706M 17.5%;
`text_slice_bytes` 428M 10.6%; `rc_bounded_service` 429M 10.6%; memcmp 340M 8.4%; dealloc 140M.
C: own open-addressing table on (pointer, length), one probe per word.
Causes: U2 (`if counts.has(word) { counts[word] += 1 } else { counts[word] = 1 }` = has + get + set, three hashes
of a new Text view each time the memo misses: ~20% recoverable), U1 (line copies + word views + teardown: ~35%),
O1 ~10% (overlaps U1).

### service — 4.07 now, 3.78 +owned (C++ 759 Ir per request, Minyar 2,873)
Profile: `minyar_interpolate` 526M + `interpolation_bytes` 309M = 29.1%; `rc_bounded_service` 448M 15.6%;
`minyar_text_split` 409M 14.2%; `text_slice_bytes` 294M 10.2%; allocation 266M; `minyar_text_integer` 107M.
C++: `append_int` 195M + `string::_M_replace` 189M + `main` 269M.
Causes: U3 interpolation (two per request, 7 and 11 parts: ~835 Ir per request vs ~380 in C++ for the same text),
U1 (`line.split(" ")` to read `parts[1]`, `path.slice(7, ...)`: ~25%), O1 15.6% (the interpolated Texts and split Lists).

### sortrows — 4.11 now, 3.55 +owned (C++ 3,243 Ir per row for 7 sorts, Minyar 11,507)
Profile: `list_sort_merge` 898M 39.0%; comparator closures 813M 35.3%; `.minyar.sort.compare.N` thunks 455M 19.8%;
memcpy 58M. C++: `std::sort` introsort with the lambda inlined (325M) + memcmp 201M.
Cause: U5 entirely: per comparison the merge calls the thunk (callback check, two record reads) which calls the
closure (TLS domain check, field reads, Text compare twice for `<` then `>`), and the merge has no small-sort base
case. Expected with a per-call-site monomorphised sort and the comparator inlined: ~2.3G -> ~0.9G (ratio ~1.4).
The calls lane's guard pages already removed 13.6% (call-depth counter inside the comparator).

### bytecode — 2.88 now, 2.88 +owned (C 8.4 Ir per VM instruction, Minyar 24.1)
Profile: `main` 100% (VM loop inlined). Per instruction (callgrind per-instruction): dispatch 9 instructions
(`self.executed += 1` with `jo` and a store to the record, instruction pointer load, `op` load, jump table) and per
operation ~10-15 more: `sp += 1` with `jo`, reload of `self.stack` from the Machine record and of its header after the
`executed` store, two List bounds tests per stack access pair.
Causes: U7 (field-precise TBAA would keep `self.stack`, its header and `executed` in registers: ~20% estimated),
List bounds checks (language safety; the Rust peer has them and is 4,182M, slower than Minyar), U11 overflow checks
on `sp`/`executed` (~10%). The C peer is the same algorithm without checks.

### intmap — 2.98 now, 2.86 +owned (Rust 792 Ir per edge, Minyar 2,264)
Profile: Map 1,650M 72.9% (`has` 586M, `hash` 327M, `set` 281M, `get` 278M, `remove` 133M); `main` 15.6%;
memset 4.6% (bucket records zeroed on grow); `list_sort_integers_merge` 66M.
Causes: U2 (`increment`: has + get + set; adjacency: has + set + get + add; ~25% recoverable), Map runtime fixed
overheads per call (recovery checks, read guard, memo update) on Integer keys where Rust's `HashMap` entry API does one
probe; bucket zeroing on grow (memset 4.6%).

### treewalk — 4.59 now, 2.72 +owned (C 629 Ir per interpreted call, Minyar 1,709)
Profile (+owned): `Interpreter.execute` 2,606M 34.4%; `evaluate` 1,935M 25.5%; `call` 986M 13.0%;
`minyar_rc_release` 893M 11.8%; `rc_heap_allocate` 506M + `rc_system_deallocate` 420M 12.2%; `list_grow` 226M 3.0%.
C: `evaluate` 2,222M + `execute` 566M, frames on the C stack.
Causes:
- O3 scope cells: `execute` has 12 cells; every call zeroes 96 bytes and tests/clears all 12 at exit (~60 instructions
  per call) and retains each `statement` twice per loop iteration; `evaluate` itself is now tight (jump table).
- U6 per-call `frame: List<Integer>` (heap, grown 2 -> 4 -> 8, freed): allocation + growth + release ≈ 25%. The C peer
  uses `int64_t frame[8]` on the stack (benchmark note: the program's comment asks for a fresh List per call).
- ownership2 + calls already took this program from 12.8G to 7.6G.

### sorttext — 2.48 now, 2.31 +owned (Rust 2,566 Ir per word, Minyar 5,917)
Profile: comparator closure `$top.1` 637M (26.9%, Text `<` then `>` byte loops), `list_sort_texts_merge` 298M,
`list_sort_merge` 252M, `list_sort_integers_merge` 101M, thunks 136M, `minyar_text_split` 188M, scheduler 132M.
Rust: pdqsort/driftsort with inlined comparisons, memcmp.
Causes: U5 (~65%: closure path, double comparison, merge without small-sort), U1 split ~10%.

### orders — 2.20 now, 2.07 +owned (C++ 16 Ir per order-pass, Minyar 32)
Profile: `main` 74% (RNG with checked `*`/`+`/`%`, record construction, the 20 filter passes); sort 18%;
allocation 7% (600k `Order` records). Causes: U11 overflow checks on the RNG and totals (~8%, codegen-audit
counterfactual), records boxed behind pointers (`List<Order>` is a List of 64-byte objects; C++ walks a contiguous
`std::vector<Order>`), U5 sort 18%, `regions[order.region] += total` header reload (U7).

### par-forkjoin — 1.99 now, 1.91 +owned (C 67 Ir per element, Minyar 129)
Profile: `main` 538M (List build of 9.4M `values.add`), `fibSerial` 701M, `total` 26M; pool <0.1%.
Causes: U8 + O4: ~57 instructions per append vs 17 in C (kind dispatch, header reloads, back-edge poll);
U11: `fibSerial` is `add; jo` after two calls, while clang turns C's `fib(n-1) + fib(n-2)` into one call plus a loop
(accumulator tail-recursion elimination): 701M vs 474M. Scheduling and joins are not the gap (Ir identical at 1 and 4
threads).

### nbody — 1.63 now, 1.57 +owned (C++ 365 Ir per step, Minyar 573)
The pair loop is clean after the codegen lane (35 instructions per pair, AVX, no record checks). Remaining:
**benchmark note** — the peers iterate a compile-time `N = 5` array (fully unrolled, body fields in registers);
Minyar iterates a runtime-length List of record pointers, and `b.*` is reloaded after each `o.v* =` store because
both are fields of the same record type (U7 cannot separate them: same field, two objects). Per step the call-depth
counter is gone on +owned; the step loop's scheduler poll remains (O4).

### par-mandel — 1.21 now, 1.20 +owned (C 14.2 Ir per escape iteration, Minyar 16.4)
Parallel body 95%: 16 instructions per iteration including 3 shuffles from SLP packing `(real, imaginary)` into one
xmm (U13); the C loop is scalar, 14 instructions, unrolled by two. Pool cost <0.1%. Wall at 4 threads 1.59x Rust in
the parallel lane's `--perf` run (scaling, not instructions).

### matrix — 1.12 now, 1.10 +owned (C 4.0 Ir per multiply-add, Minyar 4.4)
`main` 99%: the AVX2 inner loop matches C's; the extra 10% is the row-pointer/List header loads per row
(`List<List<Float>>` vs a contiguous array in C) and List growth while building. At the threshold; no action.

### par-reduce — 0.84 (faster than all peers). Not analysed further.

## Ranked unowned causes: (expected Ir saved across the suite) / effort

Basis: the +owned tree (what remains after ownership2 and calls land). "Saved" = estimated Ir removed on the 22
`benchmarks/compare` programs (sum of per-program estimates from the shares above; bothmodes noted separately);
"geomean" = suite geomean if only that fix landed (3.22 today on +owned). Effort: S (days, one file family),
M (a compiler lowering or runtime redesign with tests), L (new analysis). Score = saved / effort (S=1, M=2, L=3).

| rank | cause | fix (where) | saved | programs (ratio +owned -> estimate) | geomean | effort | score |
|---:|---|---|---:|---|---:|---|---:|
| 1 | U1 Text pieces as heap objects | compiler: lower `for x in t.split(s)` and `t.split(s)[k]` to an in-place scan (no List); runtime: views of a Text whose root outlives the loop share bytes instead of copying lines (`minyar_runtime.c:1166-1172` copy rule); free dead piece Lists inline (with O1) | ~6.5G | logstats 5.79->3.6, wordfreq 3.91->3.0, textops 5.06->4.0, httpparse 4.65->4.0, service 3.78->3.0, config 5.70->5.0, sorttext, tokenizer, json | 3.22->2.99 | M-L | 2.6G |
| 2 | U15 checked index arithmetic in scalar kernels | compiler: range facts for loop/index values, hoisted window bounds tests, header loads out of call-free loops | ~4.5G on `benchmarks/bothmodes` (topk ~3.6G, sort ~0.7G, forkjoin ~0.3G); bytecode/grid in compare | topk serial 2.63->~2.0, sort 2.10->~1.7 | n/a | L | 1.5G |
| 3 | U4 `text[i]` scanning | compiler: version scanning loops on "Text is ASCII with a known length" (one test outside the loop, byte loads inside); give the Text header fields a Minyar TBAA tag so `length` is not reloaded after field stores (`expressions.min:725`, `runtime-abi.min:349`) | ~2.7G | exprparse 9.25->8.0, tokenizer 4.63->3.9 | 3.22->3.17 | M | 1.35G |
| 4 | U2 Map multi-probe | land the one-probe update (`goal/2026-10-30-codegen-map-update`) after giving `minyar_maps.h` one stable out-of-line probe so new entry points cannot change LTO inlining of `has`/`map_find`; lower `if m.has(k) { m[k] ... }` to one probe + `getOr`-style slot (`compiler/stages/assignment.min`, `expressions.min`) | ~2.2G (+0.3G textindex) | intmap 2.86->2.2, wordfreq 3.91->3.3, config, tokenizer, logstats, httpparse | 3.22->3.12 | M | 1.25G |
| 5 | U3 interpolation | compiler: emit a sized builder per interpolation (literal lengths are constants, integer digits counted, Text lengths read) and write parts directly; runtime: two-digits-per-division integer formatting (`minyar_runtime.c:1398-1470`) | ~1.7G | service 3.78->3.1, httpparse, textops, json, config; bothmodes server | 3.22->3.16 | S-M | 1.15G |
| 6 | U10 parse/compare from a slice | compiler peephole: `Integer(t.slice(a, b))`, `t.slice(a, b) == lit`, `.trim()` of a fresh slice become range operations without a view (`minyar_text.h:198`) | ~1.1G | exprparse 9.25->8.65, config, tokenizer | 3.22->3.20 | S | 1.1G |
| 7 | U9 json representation | `library/json.min`: no per-leaf empty Lists (lazy/shared immutable), Integer fast path for integral literals, member index for objects | ~1.6G | json 9.36->7.5 | 3.22->3.19 | S-M | 1.07G |
| 8 | U5 sorting | compiler: monomorphise `sortBy`/`sort` per call site with the comparator inlined (no thunk, no per-compare callback/TLS checks); runtime: small-sort base case + run detection in `minyar_sort.h:63`; CSE `a < b` / `a > b` on the same Texts into one three-way compare | ~2.6G | sortrows 3.55->1.4, sorttext 2.31->1.5, orders, inventory, wordfreq | 3.22->3.00 | M-L | 1.02G |
| 9 | U7 alias precision | codegen: one TBAA tag per (record type, field index) under "minyar record field"; tagged Text header loads (`runtime-abi.min` helpers, 79e1b8e25 follow-up) | ~1.4G | bytecode 2.88->2.3, grid, orders | 3.22->3.17 | S-M | 0.95G |
| 10 | U8 typed List append | compiler: `List<scalar>`/`List<record>` append emits the kind-specific store (no `& 7` dispatch, no poll for scalars) and keeps length/capacity in registers between adds (`minyar_collections.h:124`) | ~0.9G | par-forkjoin 1.91->1.44, grid, inventory, json | 3.22->3.17 | S | 0.9G |
| 11 | U6 non-escaping aggregates on the heap | compiler escape analysis: a `List` that never escapes gets inline/stack storage of its observed size; temporary Text views for comparisons on the stack | ~1.6G | treewalk 2.72->2.2, tokenizer | 3.22->3.18 | L | 0.55G |
| 12 | U12 allocator per-object cost | one always-inline small-heap pop/push path (~10 Ir each) kept stable under LTO (the codegen lane found the current fast path inlining-fragile) | ~1.0G net of 1/6/9/O2 | exprparse, json, tokenizer, treewalk | 3.22->3.20 | M | 0.5G |
| 13 | U14 in-place filter idiom | compiler: `kept = []; for x in xs { if p { kept.add(x) } }; xs = kept` with a unique `xs` compacts in place; stdlib `List.retain` | ~1.0G | inventory 4.97->4.0 | 3.22->3.19 | L | 0.33G |
| 14 | U11 checked arithmetic blocks transforms | range analysis for induction/accumulator values; a checked-accumulator form LLVM can reassociate | ~0.85G | par-forkjoin, bytecode, grid, orders | 3.22->3.16 | L | 0.28G |
| 15 | U13 SLP shuffles | LTO pipeline: no SLP for loop-carried 2-wide recurrences (cost model) | ~0.2G | par-mandel 1.20->1.06 | 3.22->3.20 | S | 0.2G |

All fourteen compare-suite rows together (overlaps ignored): +owned geomean 3.22 -> ~2.3.

Owned work still worth most (for the owning lanes; same basis):
- O1 scheduler per-object cost (ownership2): 9.6G of the suite still flows through `rc_bounded_service`
  (exprparse 2.5G, json 2.1G, inventory 1.2G, httpparse 1.0G, logstats 1.0G, textops 0.7G, service 0.4G, wordfreq
  0.4G). Halving the per-unit cost or freeing small dead aggregates inline within the budget: ~4G.
- O2 Results without heap (ownership2): ~1.7G (exprparse 1.3G, json 0.3G).
- O3 scope-cell exit cost + element retains in loops that call functions (ownership2): treewalk ~1G.
- O4 back-edge polls in loops that own nothing (ownership2): ~0.45G.

## Per program (`benchmarks/bothmodes`, serial = Ir at 1 thread, parallel = wall at 4 threads vs parallel Rust)

Callgrind `--dump-instr=yes` of the measured binaries at 1 thread (topk at 1/10 of its workload), best serial peer
cachegrinded. Serial peers: C/C++/Rust Ir in brackets.

### topk — serial 2.63 (C 5.9G, C++ 6.4G, Rust 8.4G; Minyar 15.6G), parallel 1.32
94% in the `parallel for` body (`search` inlined). The DAAT inner loop costs ~21 instructions per posting step (C's
loop has none of the following): a bounds test per List access (Rust has them too: Rust is 1.42x C), an overflow test on `t + 1`/`q * 4 + j`/
`score +=`, and the `postDocs` values pointer and two spilled loop values reloaded every step. Causes: U15 (~45% of the
gap), bounds checks (language safety, shared with Rust). Parallel: scaling equals Rust's (2.15 vs 1.95); the parallel
ratio is the serial instruction gap (Ir@4 ratio 1.90). Owner: none for U15 (unowned).

### textindex — serial 2.68 (C 1.6G, Rust 1.6G; Minyar 4.25G), parallel 2.70
`main` 57% self (serial dictionary and posting build over Bytes lines), `parallel for` body 16% (FNV hashing into
windows), `minyar_map_has` 14.9% + `get` 5.3% + `hash` 3.7% (U2: `has` then `[]`), sort 16% inclusive
(`list_sort_merge` + closure thunk, U5), List growth 6% (`list_grow`/`rc_reallocate_data_in`/`rc_heap_resize`, U8).
Parallel: 84% of the one-thread Ir is forced serial because a pool task cannot build a Map or grow a List (Amdahl
bound 1.14x; measured 0.91x scaling vs Rust 1.67x). Owner: parallel2 (tasks running ordinary code, growing outputs);
serial part U2/U5/U8 unowned.

### sort — serial 2.10 (C 1.7G, Rust 2.1G; Minyar 3.55G), parallel 2.11
`quicksort` 43% (inner partition loop is as tight as C's: 5-6 instructions per element), merge-path `parallel for`
body 38% (~20 instructions per merged element: two `jo` on `a + i`/`b + j`, two bounds tests, values pointer reload),
`main` 18% (key generation and checksum). Causes: U15 on the merge (~0.7G). Parallel: the merge rounds and the
serial 18% cap scaling; an in-place parallel quicksort is not expressible (`join` arguments are read-only). Owner:
parallel2 (in-place join over disjoint halves) for the parallel column; U15 unowned.

### mapreduce — serial 1.89 (Rust 1.0G; Minyar 1.93G), parallel 2.17
`parallel reduce` body 56% (reads `sales[i].region` etc.: each element a pointer to a separately allocated record,
fields loaded through it; the peers walk a contiguous array of structs), `main` 34% building 4M records
(`rc_heap_allocate` 9.6% of Ir). Causes: boxed records in `List<Record>` (no inline/contiguous record storage; same
as orders/nbody), allocation per record (U12). Parallel: the 44% serial record build (Amdahl 1.73x; measured scaling
1.26x vs Rust 1.23x). Owner: parallel2 (tasks that build managed values) for the parallel column; record layout
unowned (not in the ranked table: a representation change, effort L, shares measured only here, in orders and nbody).

### server — serial 1.55 (C 275M; Minyar 426M), parallel 0.92
`serve` 19%, `minyar_interpolate` + `interpolation_bytes` 27% (U3: the response is built by interpolation), glibc
`malloc`/`free`/`_int_free` ~8% (Bytes buffers still on malloc in thread programs: the remaining thread-runtime tax),
`rc_bounded_step_chunks` 4.7%, `minyar_rc_enter/leave` 4.8% (this tree has no scope cells). Causes: U3, the thread
runtime's buffer allocator (unowned now that the parallel lane has finished; owner suggestion parallel2 or a runtime
lane), O1/O3. Parallel column is at parity.

### forkjoin — serial 1.39 (C 2.4G, Rust 2.7G; Minyar 3.37G), parallel 1.04
`serial` 44%, `combine` 40% (kept out of line: called once per node with push/pop and the `mix` body), `build` 16%.
Per node: bounds tests on `left[node]`, `right[node]` (Rust has them), overflow tests in `combine`'s `+`/`*`, the call
to `combine`; `build` appends through the generic List append (U8). Causes: U15/U11 (~15%), inlining of the
`parallel function` `combine` into its recursive caller (calls lane scope: inlining), U8. Parallel column at parity.

## Benchmark notes (peers that do more than translate the Minyar program)

No benchmark is wrong (all print identical output and are idiomatic in their language), but several ratios mix
language cost with a different algorithm or memory layout in the peers. None of these were edited.
- grid: peers use a padded byte grid with a branch-free neighbour sum. A literal C translation of the Minyar
  algorithm (nested int64 rows, same edge tests) is 3,395M Ir vs padded C 1,914M: 1.77x of the 5.11x is the
  algorithm; 2.88x is Minyar vs the same algorithm.
- nbody: peers use a compile-time `N = 5` array (fully unrolled); Minyar iterates a runtime List.
- exprparse, json: C peers allocate nodes from an arena and never free; treewalk's C peer keeps frames on the stack.
  Minyar has no region allocation, so these ratios include allocation + teardown the peers do not perform.
- inventory: Rust uses `Vec::retain`, C compacts in place; the Minyar program has no in-place filter (U14).
- textops: written with split + join for `replaceAll` (the program predates `Text.replace`).

## Reproduction

All on box D under `flock /home/agent/bench.lock`; logs in `~/Projects/minyar-goal-20261030/logs/perfgaps-*`.
- `python3 benchmarks/compare/run.py --json build/compare-perfgaps.json` (this tree) and the same in a checkout of
  `goal/2026-10-30-perfgaps-next` (+owned).
- `python3 benchmarks/bothmodes/run.py --json build/bothmodes-perfgaps.json --repeats 5`.
- Function tables: `cg_annotate` of `build/compare/NAME/cachegrind.minyar.out` grouped by `.perfgaps/classify.py`.
- Instruction profiles: `bash .perfgaps/cgprof.sh NAME N` (-g release build, `callgrind --dump-instr=yes`,
  `cgfiles.py` per source file, `hotasm.py` per instruction joined with objdump); references:
  `bash .perfgaps/refprof.sh NAME LANG`. The `.perfgaps/` helpers live in the lane worktree, not in this commit.
