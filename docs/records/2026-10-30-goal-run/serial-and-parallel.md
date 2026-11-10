# Why one idiomatic Minyar program is not fast on one core and on many (2026-10-30)

Lane `bothmodes`, branch `goal/2026-10-30-bothmodes` = goal/2026-10-30 (c26af6a9d) + the `parallel` lane
(42b1cbc46: threads that own I/O, typed channels, atomics, one work-stealing pool with `join`). Every number below is
from box D (AMD, 4 vCPU, Linux, LLVM 23.1.3) unless marked laptop; instruction counts are cachegrind Ir
(`--cache-sim=no`, all threads), outputs byte-identical. Reproduce with the commands in the last section.

## Answer in six lines

1. **Parallel Minyar is a separate, scalar sublanguage.** A `parallel for` body, a `parallel function` and a `join`
   branch may not create records, Text, Lists or Maps, may not read Text or Maps, may not call ordinary functions,
   may not grow a buffer, and may write only fixed-width windows indexed by the loop variable. The idiomatic
   Minyar a product is written in (records, Text, Map, recursive choices) cannot be parallelised at all; it has to
   be rewritten into Lists of scalars and Bytes first.
2. **That sublanguage is also the fast serial Minyar.** Written in it, the six both-modes programs are 2.10x the
   best of C/C++/Rust on one thread (geomean Ir), against 4.71x for the idiomatic serial suite. The same work
   written the idiomatic way is 3.1x (sort with `List.sort`) and 3.5x (a tree as a recursive `choice`) *more*
   instructions than the parallel form. So the rule "parallel code pays nothing serially" holds, but only because
   the parallel form bans exactly the features that make serial Minyar slow.
3. **What cannot be expressed stays serial, and Amdahl caps the speed-up.** Building the records of a map-reduce,
   the dictionary of a text index, the posting lists of a search index: 44%, 84% and 6% of the one-thread
   instructions of those programs are forced onto one thread, capping 4-thread speed-up at 1.73x, 1.14x and
   3.4x before any scheduling cost. The Rust peers parallelise those phases with plain `Vec`/`HashMap` per thread.
   Result on box D: parallel ratio 1.76 (geomean, Minyar@4 / Rust@4 wall) against serial 2.10 (Ir); on mapreduce,
   sort and textindex Minyar on 4 threads is slower than parallel Rust on 1.
4. **Using threads anywhere makes all managed code slower.** A program that contains a `thread function` (or an
   atomic cell) links the thread runtime: +60% Ir for the idiomatic text index and +75% for the event-loop server
   *at one thread, on the main thread, with no thread ever started*. The parallel lane's per-thread small heap
   (4a3140b1f, landed during this investigation) cut that to +29% and +50%; the rest is buffer data still on
   `malloc`, Text literals copied on every use and a slower RC scheduler cursor. This is the one place where serial
   code pays for parallelism it does not use.
5. **Crossing threads copies.** `startThread` copies every argument into the new heap and a typed channel
   rebuilds every message: ~7,650 Ir per small record (`{Integer, Text, List of 8}`) through a channel against
   ~2,870 Ir to build and use it locally; only `FrozenBytes` is shared, and reading it costs 3.3x a List read.
   Shared read-only state (an index, a table, a catalog) has no shared managed form.
6. **neo-db search is single-core for those reasons, not because of its own design alone.** Only the main-chunk
   top-k kernels (parallel functions over Bytes arenas, fixed windows of global scratch Lists) run on the pool, and
   the event-loop thread blocks while they run; parsing, planning, deltas, settling, merging and encoding cannot
   leave the loop thread because pool workers cannot allocate managed values, and a second loop thread cannot share
   the index without copying it.

## 1. Evidence

### 1.1 Hidden and visible scores (orchestrator, numbers only)

| suite | serial, product-style programs | parallel programs |
|---|---|---|
| hidden (20 programs) | 5–20x the best of C/C++/Rust | h18/h19: 1.18–1.40x |
| visible `benchmarks/compare` | 2.5–28x, geomean 4.71 (after codegen lane) | par-mandel 1.21x, par-reduce 0.84x, par-forkjoin 1.99x Ir |
| visible attribution (visible.md) | rc/frames, alloc, Text, Map runtime dominate | par-mandel / par-reduce: 100% user code, 0% rc/alloc |

The parallel programs score close to C because a parallel body cannot contain the features that cost the serial
programs their time. Their remaining gap is codegen (checked arithmetic, List append) and scaling, not ownership.

### 1.2 The both-modes suite (new: `benchmarks/bothmodes`, one source per program)

Each Minyar program is one idiomatic-as-allowed source, run at `MINYAR_PARALLEL_THREADS=1` and `=4`. Serial column:
Minyar Ir at 1 thread / min(C, C++, Rust serial Ir). Parallel column: Minyar wall at 4 threads / std-only parallel Rust
(`par.rs`) at 4 threads, n=7 interleaved, median ± half the range. Scaling = wall at 1 / wall at 4 for the same binary.

| program | same | Minyar@1 Ir | best serial Ir | **serial** | Minyar@4 ms | Rust par@4 ms | **parallel** | Minyar@1 ms | Rust par@1 ms | scaling M / R |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| topk | yes | 15,644.6M | 5,942.7M c | 2.63 | 891.5±68.0 | 608.5±42.2 | 1.47 | 1978.4±94.3 | 1384.3±78.4 | 2.22 / 2.28 |
| server | yes | 610.6M | 275.3M c | 2.22 | 881.9±64.2 | 850.0±48.3 | 1.04 | 2339.6±131.9 | 2227.0±101.7 | 2.65 / 2.62 |
| mapreduce | yes | 1,926.2M | 1,017.1M rust | 1.89 | 770.2±45.8 | 312.7±42.1 | 2.46 | 960.2±22.1 | 451.0±14.5 | 1.25 / 1.44 |
| sort | yes | 3,549.8M | 1,686.5M c | 2.10 | 513.3±18.7 | 204.6±7.4 | 2.51 | 1114.6±38.6 | 341.5±20.9 | 2.17 / 1.67 |
| textindex | yes | 4,267.8M | 1,588.3M c | 2.69 | 3056.1±440.8 | 1034.0±187.5 | 2.96 | 3106.8±345.6 | 2204.2±213.3 | 1.02 / 2.13 |
| forkjoin | yes | 3,371.9M | 2,434.2M c | 1.39 | 364.8±6.3 | 345.1±46.1 | 1.06 | 716.2±27.7 | 677.3±16.7 | 1.96 / 1.96 |
| **geomean** | | | | **2.10** | | | **1.76** | | | |

Tree: bothmodes bb09cb359 (goal/2026-10-30 + parallel lane through 4a3140b1f). Ir: `run.py --repeats 7`
(logs/bothmodes/run-D-final.log); walls: `run.py --wall-only --repeats 7` (logs/bothmodes/wall-D-3.log) at box D load
average 2.5–2.9 (other lanes' gates run outside the bench lock; earlier runs at load 4–6 gave parallel geomeans 1.50,
1.64 and 1.72 with the same ordering, so treat the wall columns as ±15%). Ir columns are deterministic. On mapreduce,
sort and textindex, Minyar on 4 threads is slower than the parallel Rust peer on 1. CPU time / wall at 4 threads
(measure.py --cpu, load 5–6): Minyar textindex 1.00 and mapreduce 1.41 (the serial phases), topk 2.09 vs Rust 2.26,
forkjoin 1.87 vs 2.49 (Rust's join workers spin; Minyar's sleep without a root job). The server's serial ratio
includes the thread-runtime tax of section 1.4: it was 2.57 before the parallel lane's 4a3140b1f, and the same server
without a `thread function` is 405.6M Ir, 1.47x C (serial geomean would be 1.94).

What each program had to give up to be one source (the finding, per program):

| program | idiomatic serial form | form the language accepts for both modes | serial phase left |
|---|---|---|---|
| topk | `List<Posting>` records, a heap record | CSR Lists of Integers, per-query windows for cursors and the top 10 | posting-list build (growing Lists per term) |
| mapreduce | `List<Sale>` records, Map per group | records are read-only in the body; chunk windows of counters, serial combine | building the records (no record creation in a body) |
| sort | `keys.sort()` | hand-written quicksort per run + merge-path merge rounds into fixed windows | key generation and checksum, 18% (Rust generates keys on every thread) |
| textindex | `text.split`, `Map<Text, Integer>`, posting Lists | lines as Bytes, FNV hashes into fixed windows of 16 tokens | dictionary + postings (Map, growing Lists) |
| forkjoin | recursive `choice Expr` | node arrays (`left`, `right`, `size` Lists), `join` over indices | building the arrays |
| server | one event loop, records per connection | one thread per shard, each owns its loop, sockets and table copy | none |

### 1.3 Serial cost of writing for both modes (variants, 1 thread, Ir)

`benchmarks/bothmodes/variants/measure.py`, same input and byte-identical output as the program:

| program | variant | Ir | vs both-modes form |
|---|---|---:|---:|
| sort | both-modes form (runs + merge rounds) | 3,549.8M | 1.000 |
| sort | serial idiom `keys.sort()` | 10,896.9M | **3.070** |
| forkjoin | both-modes form (node arrays + `join`) | 3,371.9M | 1.000 |
| forkjoin | serial idiom (recursive `choice Expr`, `match`) | 11,658.1M | **3.457** |
| mapreduce | both-modes form (chunks, windows, `reduce`) | 1,926.1M | 1.000 |
| mapreduce | serial idiom (one plain loop per pass) | 1,870.0M | 0.971 |
| textindex | both-modes form (Bytes, hashes into windows, Map of hashes) | 4,267.8M | 1.000 |
| textindex | serial idiom (`split`, `Map<Text, Integer>`) | 4,444.4M | 1.041 |
| textindex | serial idiom + one never-started `thread function` | 6,822.4M | **1.599** (5,737.4M, 1.344 after 4a3140b1f) |
| topk | `parallel for` + parallel functions | 15,644.6M | 1.000 |
| topk | plain `for` + same parallel functions (fresh Lists per query: windows exist only in `parallel for`) | 16,965.2M | 1.084 |
| topk | plain `for` + ordinary functions | 16,965.2M | 1.084 |
| server | both-modes form (`thread function` per shard; 1 shard at 1 thread) | 707.9M | 1.000 |
| server | same server, no `thread function` | 405.6M | **0.573** (main.min 610.6M after 4a3140b1f: 0.664) |

Readings:
- The work-stealing pool costs nothing measurable at one thread (topk, mapreduce within 3-8%, both directions).
- `parallel function` vs `function` makes no difference here: the calls are leaves or bounded trees that already
  drop the call-depth frame (calls lane), and the parallel bodies have no ownership frames.
- The structured parallel forms are *cheaper* than the idioms they replace when the idiom is a slow runtime path
  (`List.sort` with its generic comparator path; a recursive choice with per-node allocation and frames).
- The thread runtime is the measurable serial tax: +60% and +75% Ir at one thread.

### 1.4 The thread-runtime tax, attributed

Top functions (cachegrind, 1 thread, at 42b1cbc46), textindex serial idiom without / with a never-started thread
function:

| without thread function | Ir | with thread function | Ir |
|---|---:|---|---:|
| main | 615.5M | main | 838.4M |
| minyar_map_has | 548.4M | `_int_free` (glibc) | 636.1M |
| text_slice_bytes | 495.3M | minyar_text_split | 513.6M |
| rc_bounded_service | 413.9M | `_int_malloc` (glibc) | 438.6M |
| minyar_text_split | 319.6M | rc_bounded_schedule | 409.9M |
| minyar_map_hash | 318.5M | text_slice_bytes | 373.3M |
| minyar_map_get | 312.1M | `malloc` (glibc) | 365.1M |

Server, main.min (thread function present) vs no thread function: `_int_free` 76.2M, `malloc` 63.5M, `free` 43.7M
appear only in the threaded build; `rc_bounded_step_chunks` 69.2M vs 19.0M.

Cause in the source (at 42b1cbc46): `runtime/minyar_heap.h` compiled `rc_heap_allocate/deallocate/resize` to
`rc_system_allocate` (the size-class small heap) only `#if !MINYAR_THREADED && MINYAR_SYSTEM_SMALL_HEAP`; thread
programs fell back to `malloc`/`free`/`realloc`.

**Update, parallel lane 4a3140b1f (per-thread small-object heap), re-measured on box D:**

| variant (1 thread) | at 42b1cbc46 | after 4a3140b1f | tax left vs no thread function |
|---|---:|---:|---:|
| textindex serial idiom, no thread function | 4,444.4M | 4,444.4M | — |
| textindex serial idiom + never-started thread function | 6,822.4M (+59.9%) | 5,737.4M | **+29.1%** |
| server without thread function | 405.6M | 405.6M | — |
| server main.min (thread function, 1 shard) | 707.9M (+74.5%) | 610.6M | **+50.5%** |

What is left, from the profiles after 4a3140b1f:
- Buffer storage (Bytes, Text and List data) still uses glibc `malloc`/`realloc`/`free` in thread programs, because a
  buffer can move to another thread (`sendBytes`, `freezeBytesTake`) and be freed there: textindex `_int_malloc`
  224M, `realloc` + `_int_realloc` 302M, `_int_free` 159M. Fix: keep buffers on the owner's small pages and free
  remotely (a per-page or per-thread atomic return list, as mimalloc does), or copy a small buffer at the moment it
  moves; only moved buffers would pay.
- Every Text literal is copied on use in thread programs (`minyar_thread_text_literal` →
  `minyar_native_copy_text`, runtime/minyar_thread_domain.h:69), because compiler literals carry lazily built
  character indexes: server `minyar_native_copy_text` 34.6M + `utf8_scan` 18.7M, absent without threads. Fix: build
  literal indexes at compile time (or publish them once with an atomic), then share literals as immortal objects.
- The bounded scheduler keeps its cursor in the small-heap slot header only `#if ... && !MINYAR_THREADED`
  (runtime/minyar_bounded_rc.h:41, 61), so thread programs walk the record's map bytes: server
  `rc_bounded_step_chunks` 69.2M vs 19.0M. Objects now live on small pages in thread mode too, so the condition can
  probably be lifted.

### 1.5 What the compiler rejects (the idiomatic attempt, verbatim diagnostics)

`benchmarks/bothmodes/variants/rejected/*.min` (each is the natural way to write one step of the programs above):

| file | attempt | diagnostic |
|---|---|---|
| p1-record-in-body | build `sales[i] = Sale {...}` in a `parallel for` | iterations would write shared 'sales'; use a buffer with one slot per iteration |
| p2-ordinary-callee | call an ordinary helper from the body | 'twice' must be a pure parallel function; shared state, raw machine operations and native effects could race |
| p3-map-in-body | read a captured `Map` | shared values may only be scalar buffers read by index or through .length; managed values cannot escape or be changed |
| p4-text-in-body | read `words[i].length` of a `List<Text>` | same as p3 |
| p5-recursive-choice | a `parallel function` over a recursive `choice` | parallel function 'total' may use only Integer, Float, Boolean and Character values |
| p6-join-writes-halves | `join` two calls that write disjoint halves of one List (parallel quicksort) | 'fill' writes its parameter 'keys', so it needs this iteration's window |
| p7-growing-output | each iteration appends to its own `columns[c]` (neo-db WAL apply) | same as p3 |
| p8-constant-width | window width from a module `constant` | a window width must be an Integer literal or a value from outside the loop |
| p9-variable-width | each iteration writes a variable-length run | the first window argument must be the loop index 'i' |
| p10-pool-task-ordinary | `join` two ordinary functions that build Lists | join runs parallel functions; 'build' is not a parallel function |
| p11-thread-shares-list | give a thread a read-only `List` | accepted, but the List is copied into the thread |

Also: `window` is "available only inside a parallel for body", so a function written against windows cannot be
reused by the serial path of the same program (topk-plain-loop had to allocate fresh Lists per query).

### 1.6 Forced serial phases (Amdahl), from the one-thread profiles

| program | Ir in parallel bodies | Ir forced serial (what) | 4-thread bound | measured Minyar | parallel Rust |
|---|---:|---|---:|---:|---:|
| mapreduce | 56.3% | 43.7% (records built in `main`, allocation) | 1.73x | 1.25x | 1.44x |
| textindex | 16.0% | 84.0% (`Map` dictionary, posting Lists, sort) | 1.14x | 1.02x | 2.13x |
| topk | 94.0% | 6.0% (posting lists grown per term) | 3.39x | 2.22x | 2.28x |
| sort | 81.6% | 18.4% (key generation, checksum) | 2.58x | 2.17x | 1.67x |
| forkjoin | 83.8% | 16.2% (tree build; also serial in Rust) | 2.68x | 1.96x | 1.96x |

The Rust peers generate the records, the per-term posting lists and the per-range dictionaries on every thread
(`Vec`, `HashMap` per thread, merged by partition), which Minyar cannot express.

### 1.7 Crossing threads (`variants/thread-share.min`, `micro.sh`)

| measure | Ir | per unit |
|---|---:|---|
| 4 threads each get a 4M-element `List<Integer>` (copied) and sum it | 203.5M total; memcpy 22.2M, sums 44.0M | sum 2.75 Ir/element; copy cheap in Ir but 4 x 32 MB resident |
| same table as `FrozenBytes` (shared), summed with `getInt64` | 273.4M total; sums 144.0M | 9.0 Ir/element: 3.3x the List read |
| 62,500 records `{id, Text, List of 8}` through a typed channel to one worker | 478.4M | 7,650 Ir per record end to end |
| the same records built and summed locally | 179.2M | 2,870 Ir per record: the channel adds ~4,800 Ir per message |
| one `parallel for` of 64 tiny iterations, 1 thread / 4 threads | 1,435 Ir / 3,580 Ir per loop | wall 116 ns / 1.9 µs per loop (2 threads: 1.2 µs) |

The thread-share rows run in the thread runtime as of 42b1cbc46 (before 4a3140b1f), like any program that uses threads.

Dispatch is cheap enough for per-query loops (neo-db's pkRun); copies and channels are what make "share the index,
send the request" designs expensive.

### 1.8 neo-db search (read-only code reading; numbers from neo-db docs/r2/search.md)

Paired matrix (box searchq, neo-db 8bd5f3d vs pg_search 0.26): per core neo-db wins 1.3–2.5x on hn_sub top-10
(1 client), but at 8 clients pg_search serves 222–732 QPS where neo-db stays at 55–492, i.e. 1.5–4x slower; "every
other neo-db row runs on one core" except COUNT and conjunction top-10. What stops the other cores, path by path:

| code path (neo-db) | what runs where | what stops more cores | kind |
|---|---|---|---|
| docs/adr/001 | one event-loop thread per database; workers only during a dispatch | Minyar had no threads that own loops (fixed by e870232d8 on the parallel branch) | language/runtime (now partial) |
| src/search/index.min `pkRun` (6073) | each (query, chunk) item runs `pkChunk` on the pool | windows of global scratch Lists sized to the worst case (`kmax`, `nmax` terms, `words`); grown serially before every dispatch; merged serially after | language (fixed-width windows, no per-item outputs) |
| `pkTopK` (6001) | the loop thread blocks in the dispatch | while one query runs on all workers, no other connection is served: 8 clients serialise on the loop | neo-db design forced by language (workers cannot run statements) |
| `prefetchTopK` (6044) | batches several queries' chunks in one dispatch | only when `built < 4 * workers` chunks; on wiki 8 GB / hn_sub it cost 8–35% (longer pass, cache footprint) | neo-db design |
| `pkPlan` / `flatPlan` (3141) | only flat AND/OR of plain terms and fast phrases go parallel | the general evaluator uses records, Lists and Text (query tree, candidates, positions): not allowed in a parallel body | language (scalar sublanguage) |
| deltas, suspect/locked rows, settle, BM25 statistics, parse, plan, result encoding | loop thread | managed values; workers "cannot allocate managed values" (ADR-001 amendment) | language/runtime |
| docs/r2/MULTICORE.md step 1–2 | engine per thread / partitions | an engine per thread is now expressible, but one hot index cannot be shared read-only by several loop threads without a copy (FrozenBytes only) | language/runtime |
| search.md:185 | — | "parallel for cannot call functions with buffers or write per-iteration ranges, and tasks workers copy data into separate heaps" | language |

Fix for neo-db search concurrency, in order of payoff: (a) N loop threads per database that each serve their own
connections and run whole search statements, reading one shared immutable index (main-chunk arenas, directory, doc
lengths, `mainValid`) — needs shared frozen managed data (cause C3) and a fast thread runtime (cause C2); writes and
deltas stay on one owner thread and publish a new frozen snapshot per index version; (b) until then, run the
top-k dispatch without blocking the loop (send the compiled query to search threads over a channel with the frozen
arenas, merge the reply on the loop) — expressible today with `freezeBytesTake` per arena, typed channels and
`channels.wakeSocket` in the loop, but FrozenBytes offers only `getUInt8`/`getInt64` (the containers use 16- and
32-bit fields), reads at 3.3x a List, and the whole server would pay the remaining C2 tax on its 1-client path, so
the goal-loops REQUESTS row says not to adopt it before C2 is near zero.

## 2. Causes, ranked by payoff

Payoff = how much of the gap in *both* columns the fix removes, weighted by how many programs/products hit it.

| # | cause | measurement | costs serial | costs parallel | fix | owner |
|---|---|---|---|---|---|---|
| C1 | Parallel code is a scalar sublanguage: no record/Text/List/Map creation, no Text/Map reads, no ordinary callees, no recursive types, no growing outputs, join arguments read-only | probes p1–p10; textindex 84% and mapreduce 44% of Ir forced serial; neo-db pkPlan/pkRun | nothing directly; idiomatic code stays 5–20x behind (hidden) because the fast form is a rewrite | Amdahl: textindex bound 1.14x, mapreduce 1.73x at 4 threads; whole neo-db statements cannot leave the loop | give pool workers managed domains: a task/parallel body may allocate and call ordinary functions; values it creates are owned by the worker's domain and either die there or move to the joining caller (per-iteration owned outputs, `collect`); captured values stay read-only | parallel (PAR-2 remainder) + ownership |
| C2 | The thread runtime is slower for managed code even on one thread | textindex +59.9% / server +74.5% Ir at 1 thread at 42b1cbc46; **+29.1% / +50.5% after 4a3140b1f** (per-thread small heap) | +29–50% today on managed code of any program that mentions a thread or atomic | the same on every thread, plus malloc arena contention | done: per-thread small heap (4a3140b1f). Left: buffer data on small pages with remote free; literal Text shared instead of copied per use; bounded cursor in the slot header in thread mode | parallel (thread runtime) |
| C3 | No shared read-only managed data: arguments and messages are copied; only FrozenBytes is shared and it reads at 3.3x a List | thread-share: channel +4,800 Ir per small record; FrozenBytes 9.0 vs 2.75 Ir/element | none | every "share the index/table" design pays copies (memory x threads) or slow reads; neo-db cannot run 2 loops over one index | `freeze(value)` for Lists/records/Text graphs: immutable, RC-exempt while frozen (immortal until the last thread scope ends), readable from any thread and from parallel bodies; inline FrozenBytes getters | ownership + parallel |
| C4 | Outputs must be fixed-width windows indexed by the loop variable; windows exist only inside `parallel for` | p7–p9; topk/neo-db scratch sized to kmax; topk-plain-loop needed fresh Lists | serial path cannot reuse window code (+8.4% in topk-plain-loop) | worst-case scratch, serial grow-before and merge-after phases | per-iteration owned outputs moved back in index order (`parallel for ... collect`), windows over explicit ranges with a disjointness check, windows usable in ordinary code | parallel |
| C5 | `join` arguments are read-only, so in-place divide-and-conquer (quicksort, partitioned writes) is not expressible | p6 | none | sort needs merge-path rounds; parallel quicksort/radix impossible | `join` over disjoint sub-windows of one buffer (`keys.split(at)` giving two exclusive views) | parallel |
| C6 | Idiomatic serial paths are slow where the parallel form avoids them (`List.sort`, recursive choices, records per element) | sort idiom 3.07x, choice tree 3.46x the both-modes form | 3x on these idioms | n/a | codegen/stdlib: unboxed `List<Integer>.sort` fast path, scalar-payload choices without frames (ownership change 5 started this) | stdlib, ownership, codegen |
| C7 | The event loop was single-threaded by construction | server scales 2.65x (Rust 2.62x) with one loop per thread now | n/a | before e870232d8 no Minyar server could use a second core | landed on the parallel branch (threads own sockets, files, loops); remaining cost is C2 | parallel (done) |
| C8 | Per-call bookkeeping blocks inlining (call-depth counter) | no difference measured in these programs (leaf calls already drop the frame) | small here; large in call-heavy code (calls lane) | same | guard pages instead of the counter (calls lane design) | calls |
| C9 | Pool dispatch and scheduling | 1,435 Ir / 116 ns per loop at 1 thread; 1.9 µs at 4; Ir identical at 1 and 4 threads for every compute program | none measurable (topk/mapreduce within 3–8%) | 1.9 µs per loop: fine for per-query loops, too much per row | none needed now | — |

Not found: atomic reference counts on thread-local values (RC is non-atomic and `_Thread_local` in thread programs),
`parallel` capture copies (captures are borrowed), pool spin-wait in serial phases (workers sleep without a root job;
Ir at 4 threads equals Ir at 1 thread for every compute program).

## 3. What makes one source fast in both modes

The cheapest path to "write it once, fast on one core and on many" is to make the fast form the idiomatic one, in
this order:
1. C2 (finish the thread runtime: buffers on small pages with remote free, shared literals, slot-header cursor):
   removes the only serial tax of using threads; local to the runtime. The per-thread small heap (4a3140b1f) did half.
2. C1 + C4 (managed domains for pool tasks, owned per-iteration outputs): lets the idiomatic program be the parallel
   program, so the serial phases in mapreduce/textindex/topk/neo-db become parallel without a rewrite. Serial code
   pays nothing as long as task domains exist only inside pool work.
3. C3 (frozen shared graphs): one index or table read by every thread; prerequisite for neo-db's N loops per
   database.
4. C6 in the serial lanes, measured on the same suite so the serial column improves with the parallel one.

Standing rule check for these fixes: C2 changes only thread programs (serial programs keep MINYAR_THREADED=0);
C1/C4/C5 change only code inside parallel constructs; C3 adds a new value kind. Each must still be measured in both
columns of `benchmarks/bothmodes/run.py` and on `benchmarks/compare`.

## 4. Method and reproduction

- Suite: `python3 benchmarks/bothmodes/run.py [--json OUT]` (box D under `flock /home/agent/bench.lock`);
  `--wall-only` re-times the last build and prints the load average; `make check-benchmarks-bothmodes` for
  correctness (O0 + release, 1 and 4 threads, small inputs).
- Variants: `python3 benchmarks/bothmodes/variants/measure.py --profile NAME,...`; micro-measures:
  `sh benchmarks/bothmodes/variants/micro.sh`; rejections: `./minyar --release benchmarks/bothmodes/variants/rejected/pN-*.min`.
- Caveat on wall times: box D is shared; gates of other lanes run outside the bench lock. Wall columns above were
  taken with the load average printed by `--wall-only`; Ir columns are deterministic.
- Hidden versions of the both-modes programs (Luke's step 4) belong to the judge lane; this suite is the visible half.
