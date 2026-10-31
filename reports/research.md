# Research log — run 2, agent `res`

Goal (Luke 20:40): broadly faster than today's Minyar, aiming at optimised C. This lane invents past the known
techniques and measures what it can. Base: `bbee03178` (run-2 base, compare geomean 2.52 vs fastest reference,
2.03 vs Rust). Everything below is measured on box H unless stated; Ir = cachegrind instructions.

Known techniques already taken or in flight by other lanes: escape analysis / stack storage (`esc`), Perceus
borrow+drop inference (`brw`, `drp`), in-place reuse (`fbip`), SwissTable Maps (`map`), Text views without headers
(`txt`), codegen/SIMD (`cg`), profiling (`prof`). This log deliberately does not repeat those.

## Idea queue (design → why it could pass the known limits → status)

| # | idea | why it is new here | status |
|---|---|---|---|
| R1 | Text hash memoised in the header, interned short Texts | Map-heavy programs re-hash the same Text 2–3× per source op (wordfreq: hash 14%, memcmp 8%); text values are immutable, so a cached hash and a canonical copy are sound | measuring |
| R2 | Interned Text = pointer-equal keys (bounded, per-thread table) | turns Map key compare into a pointer compare for repeated keys and removes allocation for repeats | design |
| R3 | Lazy `for x in text.split(sep)` (split-list sinking) | the List of views exists only to be iterated: logstats split+slice+teardown ≈ 70% | design |
| R4 | Allocation-site "escape on demand": bump-allocate objects in a per-call region, promote on an escaping store | static escape rejects 96–98% of functions; a runtime store barrier is 2–3 compares per store vs 40–70 Ir per object for alloc+free+scheduler | design |
| R5 | Frame-limited reuse in the other direction: a short-lived *region* per loop iteration for aggregates the compiler proves die at the backedge | frame-limited reuse paper bounds the space; Minyar frees per object today | design |
| R6 | Checked-overflow facts from induction variables (loop versioning on a range proof) | pure-compute programs are 99% user code and overflow tests block vectorisation and reassociation (U11) | design |
| R7 | Pure-compute: hoist Text header loads out of call-free scan loops with a "text bytes are immutable" alias fact | U4/U7 | design |

## Measurement protocol

- `python3 benchmarks/compare/run.py --only NAME` (Ir, deterministic) on box H; compare against
  `/home/agent/swarm/base-results/compare.json`; a change is kept only if every measured program is within +0.1%
  and at least one is better.
- Wall only for the few programs that matter, n=3 interleaved under `flock /home/agent/bench.lock`.
- Correctness: compare `--check` (O0 + release, C-identical output) and the narrowest `make check-*`.

## Log

(pending base seed)

### R1 — Text hash memoised in the header (measured, rejected)

Idea: Text is immutable, so compute the Map hash once and keep it in the `MinyarText` header; key kinds 1-4 hash
without running user code, so `m.has(k)` then `m[k]` hashes the same Text twice, and every `set` a third time.

Prototype: one `unsigned long long hash` field (last, so existing positional initializers keep meaning), cleared at
the five sites that mutate bytes/range (`append_in_place`, `text_compact_kept_piece`, `split_next` reuse, the ASCII
character cache); relaxed atomics because a shared frozen Text can be hashed from two threads; immortal Texts may
live in read-only data, so the cache writes only when the header has an owner count (the first version wrote to a
rodata literal and SIGSEGV'd tokenizer/config — caught by `run.py`).

| variant | config | tokenizer | json | wordfreq | intmap |
|---|---|---|---|---|---|
| base Ir (M) | 2765.3 | 4138.2 | 5587.6 | 2248.4 | 1555.0 |
| cache all Text keys | 2683.9 (−2.9%) | 4100.7 (−0.9%) | 5594.9 (+0.1%) | 2319.8 (+3.2%) | 1576.6 (+1.4%) |
| cache only keys ≥ 8 bytes | 2670.1 (**−3.4%**) | 4102.2 (−0.9%) | 5592.7 (+0.1%) | 2280.0 (+1.4%) | 1579.1 (+1.6%) |

Verdict: rejected by the no-program-slower rule. Where it helps (config, long repeated section/key names) the saved
hash is real; where it hurts (wordfreq, intmap) the extra 8 bytes per Text make every short inline-Text allocation
one size class larger and add a header store per creation, and short keys hash in a handful of instructions anyway.
Conclusion for the Text lane: only cache a hash if the header does not grow (e.g. overlaid on a field that is null
for ASCII Text), otherwise the creation path pays for every temporary.

### R2 — a small aggregate retires inside the release that kills it (kept)

Idea: the scheduler exists so a *service point* has a bounded pause, but the common case is a small, short-lived
aggregate (record with ≤ 8 slots, reference List with ≤ 8 slots) whose last owner is released inside ordinary user
code. Paying a queue write there and a later service visit costs more than doing the unit's work at the release:
`rc_bounded_retire_small_in` already retires up to eight such aggregates in constant work, and the contract's
"Public release: K units, including immediate leaf and small-aggregate destruction" already allows it. Nothing is
invented, but the split of "eager vs queued" had never been moved for aggregates.

Placement matters, twice over:
1. First version put the test inside `rc_drop_in`. That made `rc_drop_in` big enough that the scheduler stopped
   inlining it: inventory paid a call per dropped child and went +1.4% while logstats won 6%. Fixed by an
   `rc_drop_eager_in` used only from `rc_bounded_release` (the generated-code path); the scheduler keeps `rc_drop_in`.
2. Records-only and Lists-only were measured separately: records-only lost (inventory +2.5%, logstats flat),
   lists-only won. With the isolated path both are now inside one prototype and records are neutral.
3. Eager records inside `rc_drop_in` also made the whole runtime object compile differently (`rc_bounded_service`
   1,071M → 1,232M on inventory); the isolated version leaves it at 1,071M.

| program | base Ir (M) | eager release Ir (M) | delta |
|---|---:|---:|---:|
| logstats | 4690.1 | 4440.1 | **−5.3%** |
| service | 1967.3 | 1835.9 | **−6.7%** |
| textops | 3399.8 | 3291.4 | **−3.2%** |
| sorttext | 1717.2 | 1667.2 | **−2.9%** |
| httpparse | 5397.7 | 5271.6 | **−2.3%** |
| exprparse | 7463.5 | 7379.5 | −1.1% |
| config | 2765.3 | 2752.4 | −0.5% |
| inventory | 4927.5 | 4927.5 | 0.0% |
| json, tokenizer, wordfreq, grid, treewalk, … | — | — | ≤ 0.1% |
| compare geomean (22) | 2.52 | **2.49** | vs Rust 2.03 → 2.01 |

Verdict: kept. No program slower, eight faster, one unit of contract slack already documented. The remaining
scheduler share on h01-like programs is now the *large* graph backlog, which this does not touch.

### R3 — intern short Text pieces in a bounded direct-mapped cache (measured, rejected)

Idea: most Text pieces are keys (words, tokens, header names, JSON member names) and most repeat. An immutable Text
can be shared, so a 4096-slot per-thread direct-mapped cache of pieces ≤ 64 bytes could return the same object for
equal bytes: no allocation, no copy, no later retirement, and a Map probe would find a pointer-equal key.

Prototype: `text_intern` at the top of `text_slice_bytes` (after the full-slice case), hashing the bytes, comparing the
slot, retaining a hit, replacing (and releasing) a miss. Table 4096 slots, 64-byte cap, per thread.

| program | R2 Ir (M) | + intern (M) | delta |
|---|---:|---:|---:|
| logstats | 4440.1 | 4633.3 | **+4.4%** |
| config | 2752.4 | 2977.3 | **+8.2%** |
| exprparse | 7379.5 | 7409.4 | +0.4% |
| json | 5586.4 | 5555.7 | −0.6% |
| tokenizer | 4137.7 | 4137.0 | 0.0% |
| wordfreq | 2245.7 | 2245.7 | 0.0% |

Verdict: rejected. Two lessons worth keeping. (1) A direct-mapped 4096-slot cache is too small for wordfreq-class key
populations (about 50k distinct words) and thrashes; hits are near zero, so only the hash+cache test remains.
(2) Interning *views* turns a 56-byte header into a header plus a copied byte range, so every unique piece (most of
logstats' fields) pays a memcpy it did not pay before, and losing the root-sharing view means the shared-root retain
is replaced by a copy. The sounder design is to intern only where the compiler knows the value becomes a Map key or
Set element, not every slice.

## Designs that are too big for one prototype, with what would decide them

These are the "invent past the known techniques" answers to the four costs in reports/next-phase.md. Each says what has
to be true, what it would cost, and how to falsify it cheaply.

### D1 — Speculative per-call region with escape promotion (reclamation + allocation)

Static escape analysis rejects 96–98% of functions (c5), but the interesting fact is per *allocation site*, not per
function: a parse `line` call allocates five records and a List, all dead before it returns. Proposal: the compiler
emits a region enter for a function that allocates; allocations inside bump-allocate from a thread-local region stack
(one pointer add, no header initialisation beyond kind). Every reference store gets a barrier:
`if (value is in a live region && target is outside it or in an older region) promote(value)`. Promotion copies the
object (and, on demand, its region-owned children) into the ordinary heap and moves its ownership there; a promoted
object is exactly a normal heap object afterwards, so nothing downstream changes. A region pops at return with one
pointer reset; anything unpromoted was, by construction, unreachable outside, so no traversal and no queue.
Why it beats the static approach: the barrier only has to answer "can this pointer outlive its region", which is two
range compares, and it is paid on stores, not on allocations; a site whose objects escape mostly can be switched to
ordinary allocation per site after `hits/misses` are counted, so the worst case is the heap path plus a counter.
What has to be true: (a) reference stores all go through compiler-emitted calls (`record_set_*`, `list_add*`,
`map_set`, `rc_local_move_owner`) — reading the ownership stage, they do; (b) promotion preserves identity, which is
only observable within the program's own pointers, and an escaped object is promoted before anyone outside can hold
it; (c) the contract gains one sentence: a function's region exit frees its unpromoted allocations in O(1), so the
pause bound improves. Cost: one compare pair per reference store (measured store density: ~2 stores per allocated
object in the parse benchmarks) against 40–70 Ir per object for allocate + retire + queue. Ceiling from the measured
profile: ≈49% of h01, ≈30% of h06/h13, and the `rc_*` + `alloc/free` classes of the visible suite (9–25% each).
Falsification: prototype for one construct only — a `List` backing growth and `Text` pieces inside `split` — with
the barrier limited to `minyar_list_add*` and Text creation, and measure logstats/service. If the barrier cost is
below the saved alloc+free there, the full design is worth building.

### D2 — Caller-provided result storage for returned graphs ("destination passing")

A function that returns a freshly built record graph (a parser) could write it into storage the caller names
(`sret`-style), so the caller owns the buffer and the callee's allocations become one bump allocation the caller
frees in one step. This is destination-passing style: it gives RVO for graphs without static escape analysis,
because the *callee* knows it is constructing into a destination while the *caller* decides the lifetime.
What has to be true: the destination is big enough — unknown for a parse of arbitrary depth — so the realistic form
is "the callee allocates the graph in its own region (D1) and returns the region, not the object": the caller then
holds a region handle and frees it in one step when the graph dies, with per-object RC disabled inside. That
combination is what makes a `parse(line); eval(tree)` loop cost two allocations total instead of thousands.
Falsification: the same prototype as D1, applied only to the graph returned by a single recognised constructor
chain; measure exprparse/json.

### D3 — Grouped allocation for split pieces (Text runtime)

`split` allocates one 56-byte header plus inline bytes per piece. Proposal: a group allocation — one block holding
up to 64 piece headers, with a shared owner count; each piece keeps its own reference count for language-level
ownership, but the block's bytes are freed when the last piece of the group dies. Pieces can escape freely (the
block stays alive until the last one is dropped), so this is semantically invisible; it only batches the allocator
calls. Costs: a new object kind, and a block-level count on every piece release (one decrement, one branch on zero).
Ceiling: for logstats, allocation + deallocation + header init is ~22% of the program; batching 64 pieces per
allocator call removes most of the per-piece page/free-list work. Falsification: implement only for the 1-byte
separator path in `minyar_text_split` and measure logstats/textops; if the block bookkeeping eats the gain, drop it.

### D4 — Intern only where the compiler knows the value is a key

R3's interning lost because it taxed every slice. The compiler, however, sees `m[key]` and `m.has(key)` and
`set.add(x)`: it can emit an interning slice (`minyar_text_slice_intern`) for exactly those argument positions.
Then the cost is paid only where a hash or comparison follows, and the Map probe can compare canonical pointers
first. This needs no representation change and reuses the existing inlined Map entry points.
Falsification: change the lowering for Map/Set subscript and `has`/`contains`/`getOr` Text arguments only, keep the
R3 cache, and measure wordfreq/config/json/tokenizer, which all build the key from a split piece.

### R4 — one "hot" freed slot per size class in front of the page free list (measured, rejected)

Idea: allocation and deallocation walk a page free list and update page/global live counts (a microbenchmark over
`rc_system_allocate(64)`/`rc_system_deallocate` measured 29 Ir per allocate and 102 Ir per allocate+free pair in the
single-object churn worst case). A thread-local one-slot magazine per size class should make the common pair two TLS
accesses.
Prototype (non-threaded builds only; thread pages move between threads): allocate pops the class's hot slot, free
parks the slot there without touching the page's live count.

| program | candidate tree Ir (M) | + hot slot (M) | delta |
|---|---:|---:|---:|
| json | 5581.9 | 5726.2 | **+2.6%** |
| config | 2751.0 | 2818.9 | **+2.5%** |
| textops | 3287.9 | 3386.7 | **+3.0%** |
| exprparse | 6963.4 | 7030.0 | +1.0% |
| logstats | 3853.0 | 3869.0 | +0.4% |

Verdict: rejected. Parking the slot keeps its page's live count high, so the page is never reset or unlinked at the
moment the program's objects die, and the allocator loses the page-reuse path that made the existing free list
cheap; the extra TLS test on every free is paid even when the magazine is empty. The lesson: the allocator is
already near the cost of its own bookkeeping, and the remaining per-object cost is the *page* lifecycle, not the
free-list walk. A real win here needs a different object lifetime (D1), not a faster free list.

### D2 implementation map (for the next agent; not prototyped here)

Destination-passing result storage was the next pick, but it is a calling-convention change, not a runtime tweak, and
this lane ran out of context before it could be attempted honestly. Where it would go, from reading the compiler:

- `compiler/stages/calls.min:93` `emitCall` is the single place every call's argument list is built (`returnType != 5`
  decides the `ptr` result). A hidden out-parameter would be appended there for a callee whose return is a fresh
  record/List allocated by the callee.
- `compiler/stages/functions.min:193-211` lowers `return <expr>`; a destination form means `store` into the
  out-pointer and `ret void` for the same functions, with the ownership stage treating the stored value as taken.
- Every caller must allocate the destination: a fresh record of the callee's return shape, or for a List a header
  with reserved capacity. That requires the callee's *shape* (field count) to be known at the call site, which it is
  for a nominal record type; for a List it is not, which is why the realistic variant is "callee allocates the graph
  in its own region and returns the region handle" (D1), with the caller freeing the region in one step.
- Risks to close: `Result`/choice payloads are multiplied by `compiler/stages/choice-*`; parallel outlining
  (`compiler/parallel-outline.min`) and native calls (`compiler/stages/native.min`) have their own signatures;
  recursive calls need one destination per active frame; and diagnostics/ownership fixtures test the current shape.
- Falsification before any of that: hand-write the transformed IR for one benchmark function (a parser returning a
  record) and cachegrind it. If removing that allocation + its retirement is under 2% of the program, the ABI churn
  is not worth it; exprparse's per-node cost (3.3 heap objects per node, allocation + retire ≈ 30%) says it is not.
