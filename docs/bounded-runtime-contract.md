# Incremental reference counting

Launcher-built programs and the Makefile's ordinary program runtime use
system-backed incremental reference counting by default, with K32 cleanup
batches. Graph traversal is spread across runtime calls. K is not a bound on
total operation time: allocator calls, copying, page faults, I/O and operating
system scheduling remain outside it. Some operations perform multiple batches.
The explicit eager profile opts out and can release an entire graph at once.

## Choosing a profile

Use `./minyar --memory-profile system|fixed|lazy|eager` before the source path.
`--cleanup-budget N` selects 1–1024 for incremental profiles (default 32).
`--heap-bytes N` applies only to fixed/lazy pools: ASCII decimal, a power of two
from 4096 through 2^62 on supported 64-bit targets. That representable range does
not guarantee the host can allocate or link the requested capacity.

For example:

```sh
./minyar --release app.min -o app
./minyar --release --memory-profile fixed --heap-bytes 1048576 --cleanup-budget 32 app.min -o app
```

A single launcher setting controls both compiler ownership lowering and runtime
configuration. For K above 1 the launcher lowers owners to stack scope cells
(`--scope-owners --bounded-owners K`, see
[scope cells](#scope-cells-under-a-cleanup-budget)); a function with a cleanup
point that would drop more than K cells keeps an ordinary heap frame. K1
retains ordinary ownership frames. The direct compiler's `--bounded-owners K`
alone keeps frames, with compiler-generated stack storage for eligible leaf
functions with at most `min(8, K−1)` owner slots.
The optional incremental module cache includes this effective policy in its
identity. No ownership annotation is required in Minyar source.

`MINYAR_RUNTIME_FLAGS` supplies runtime C flags; `MINYAR_CLANG_FLAGS` supplies
final link flags. Target, sysroot and sanitizer choices must agree between them.
Launcher-selected profile, budget and pool capacity override conflicting `-D`
or `-U` definitions in runtime flags. Custom tools/forced includes are trusted.
The standard system/K32 runtime is built once and reused; its Makefile targets
depend on the runtime implementation, headers and build recipe. Other incremental
profile settings, or an explicitly set `MINYAR_CLANG` or `MINYAR_RUNTIME_FLAGS`,
compile an incremental runtime inside the invocation's temporary directory.
The eager profile uses cached Makefile artifacts; its runtime compilation uses
the Makefile's toolchain flags rather than `MINYAR_RUNTIME_FLAGS`.
This keeps custom incremental configuration
isolated while avoiding repeated runtime compilation for ordinary builds.
When changing Makefile toolchain variables, use a clean build as usual.

For direct runtime C builds, the corresponding flags are:

| Flags | Allocation | Main tradeoff |
| --- | --- | --- |
| `-DMINYAR_SYSTEM_HEAP=1` | System `malloc`, `realloc`, and `free` | Cleanup traversal is incremental, but allocator latency and resident memory are unbounded by the runtime. |
| `-DMINYAR_BOUNDED_HEAP=1` | Finite buddy pool, touched at startup | Fixed capacity and bounded allocator bookkeeping, with an upfront memory and startup cost. |
| `-DMINYAR_BOUNDED_HEAP=1 -DMINYAR_LAZY_HEAP=1` | Finite pool backed by POSIX `mmap` | Avoids touching the whole pool at startup; later accesses can incur page faults. |

System and pool allocation are mutually exclusive. Lazy backing requires the
pool flag and a POSIX mapping implementation; the lazy flag alone does not
activate incremental cleanup. Combining lazy and system allocation is rejected.

### Defaults

| Setting | Default | Allowed values |
| --- | ---: | --- |
| `MINYAR_RC_POLL_BUDGET` | 32 work units | 1–1,024 |
| `MINYAR_BOUNDED_HEAP_BYTES` | 64 MiB | A representable power of two, at least 4,096 bytes |
| `MINYAR_RC_BACKLOG_BUDGET` | 0 (one object queue) | 0–K, system heap only; average old-object backlog units per managed allocation |
| `MINYAR_FRAME_CACHE_BYTES` | 256 KiB | Shared frame and retired temporary-chunk cache capacity |
| `MINYAR_INTEGER_TEXT_CACHE_LIMIT` | 32,768 entries | 0–32,768 |

The pool needs one metadata byte per 32 bytes of capacity. With the default
fixed-pool settings, startup touches 64 MiB of pool storage and 2 MiB of metadata.
Touching pages does not lock them in physical memory.

Lazy backing reserves separate data and metadata mappings without
`MAP_NORESERVE`. Failed reservations produce an error. Successful reservations
can still encounter physical-memory pressure, and reuse does not return
touched pages to the OS. In lazy ASan builds,
`MINYAR_LAZY_ASAN_MAX_BLOCK_BYTES` caps each rounded allocation at 64 MiB by
default to limit sanitizer shadow work. Poisoning and unpoisoning can scale
with allocation size; never-allocated virtual holes are not all poisoned.

## What happens to a released value

The compiler inserts ownership operations automatically and keeps ordinary
allocation acyclic. Cycle-capable record/List components
instead use the automatically selected traced runtime described in
[runtime ownership](runtime-memory.md#closures-cycles-and-execution-domains).
Cleanup runs on the owning thread, without background collection or user
finalizers. Its
reference counts are single-threaded: managed objects cannot be shared across
native threads through this ownership mechanism.

An aggregate whose count reaches zero joins a retirement queue. Its header
holds the queue link, and its outgoing references keep children alive until
cleanup visits them. Text, scalar Lists and records, empty reference
aggregates, and Lists containing only immortal references can be freed
immediately. Once a List receives a mortal reference, it permanently switches
to ordinary reference traversal.

Destroying a Text view frees its own header/index and drops its reference to
the owning Text. If that drop makes the owner unreachable, the owner joins the
object queue as a fieldless task. Its destruction consumes a separate work
unit, so even a K=1 release cannot destroy both objects in one call.

Ordinary heap-frame exit and statement cleanup detach owner chains without
scanning them or allocating queue metadata. Stack-frame exit immediately visits
its written owner slots (at most `min(8, K−1)`), charges those visits to K, and
uses the remaining budget for queued work. Its stack storage is never queued.
Temporary owners retire in chunks of eight,
independently of the frame that created them. Frames index local slots when
first assigned a non-null value. Cleanup visits that index, including slots
later cleared; slots that only ever held null need no visit.

Cleanup advances only when the program reaches a service point. A long
computation or foreign call can leave retired values waiting.
Sleeping (`process.sleepNanoseconds`) and an event loop about to wait for
readiness are idle service points: they spend the wait on queued cleanup,
rereading the clock after each K-unit batch, so a sleep can end at most one
batch late. Native code can do the same through `minyar_rc_poll_idle(budget)`.

## The work budget

Let **K** be `MINYAR_RC_POLL_BUDGET`.
`minyar_rc_poll(budget)` performs at most `min(budget, K)` queued work units
and returns the number performed. One unit visits a record field or a
frame/temporary owner, or finalizes a task: a record unit examines at most
eight fields, passing over the ones that own nothing and visiting the next
owner, so a record whose compared fields own nothing costs fewer units than it
has fields. Non-owning fields still cost constant work (at most eight field
examinations per unit); they share the unit with the next owner or with the
record's finalization.

A **small aggregate** — a record with at most eight slots, or a reference List
with at most eight slots — is retired by one unit: that unit visits the
aggregate's owner slots and finalizes it, so a small aggregate costs one unit
however many owners it has. When a visited owner is itself a unique small
aggregate, the unit takes it and retires it too, up to eight aggregates per
unit. An aggregate beyond that allowance, a shared child, and any larger
record or List follow the ordinary path: the drop frees a leaf, queues an
aggregate, or leaves it for a later unit. A unit therefore performs a constant
amount of work (at most eight aggregates of at most eight slots, plus the
backing frees they need), and K units still bound a service point. Cleanup
never recursively walks the object graph: the unit's own fixed stack holds its
allowance. Queue selection examines at most three queues.

The limits for individual runtime operations are:

| Operation | Cleanup limit |
| --- | --- |
| Public release | K, including immediate leaf and small-aggregate destruction |
| Managed object/data allocation or data resize | K queued units |
| Frame entry, frame exit, or statement cleanup | K each |
| Scope-cell statement cleanup or return | K each, including one unit per cell |
| Local assignment or indexed replacement in an ordinary reference List | K total immediate and queued units |
| Reference List append | K after storing the value; growth can service another K beforehand |
| Mixed-record field write | K after storing the value |
| Temporary keep or borrow | K, or 2K when creating a new owner chunk |
| Scalar List write, immortal-only List write, or scalar record setter | No release or poll |
| Null or immortal temporary keep | No poll |

Assignment anchors the new reference before releasing the old one.
`minyar_rc_local_take` transfers ownership; `minyar_rc_local` retains it.
A borrowed temporary is retained before following the same limits as a keep.

**K is not a per-expression limit.** A source expression can invoke several of
these operations. Nor does the table bound all work inside a call: heap-frame
storage growth clears its complete new value extent and may resize it. Fully
retired cached frames already have NULL value slots, cleared at their existing
owner visits, so reuse skips another entry clear. Explicit stack entry still
initializes its supplied array. The written-slot index adds one machine word
per capacity slot. Record initialization, Text processing,
List growth and copying, I/O, system allocation, page faults, and scheduling
fall outside the cleanup budget. An application deadline requires bounds on
all operations along its critical path and validation on the target system.

## Scheduling and batching

Work queued since the previous service point is fresh: objects, detached
frames and temporary chunks. Fresh work receives round-robin service across
those three queues. Within the object queue, service alternates between
recent work and an older captured batch. New arrivals cannot join that batch.
Once it is exhausted, the recent stack becomes the next batch in constant
bookkeeping work.

With `MINYAR_RC_BACKLOG_BUDGET` set above zero (system heap only; K/8 is
the tested setting), object work that is still pending at the end of the
service point after the one that queued it becomes the old-object backlog
(the traced runtime that cycle-capable programs select keeps one object
queue, see
[runtime ownership](runtime-memory.md#closures-cycles-and-execution-domains)):
a second instance of the same object queue, served in arrival order, whose
units free objects into the backlog itself. A drop that fits in two service
points' budgets therefore keeps the unpaced schedule exactly. If the backlog
was empty it continues exactly where the fresh queue stopped. Only managed
allocations (object, data and resize) serve it: each one that finds it
pending earns it `MINYAR_RC_BACKLOG_BUDGET` units of credit, up to K, and
the allocation at which a whole K has accrued reserves min(budget, share)
units for the backlog and gives it whatever fresh work leaves, up to the
credit. Every other service point ignores the backlog and keeps its direct
paths. Reclamation of old work thus keeps pace with allocation: at K/8 a
large dropped graph is reclaimed over about eight times as many allocations
as fresh work would take, unless idle service points drain it sooner. Every
service point still performs at most K units.

The default is zero. On edge's tail-latency loop (8 vCPU Boat box, two
pinned CPUs, 20,000 requests, three rounds) K/8 cuts p99.9 from 1.7–2.3 ms to
0.19–0.35 ms (Rust 1.7–2.4 ms, Go 0.38–1.25 ms), but closed-loop p50 rises
from 11 µs to 14–17 µs and total time by about 14%: cleanup trickled between
allocations is less cache-friendly than cleanup in bursts. Allocation-heavy
programs also run 0.2–1.6% more instructions (self-compile 4% fewer). Fixed
and lazy pools must keep zero: their capacity planning assumes every pending
object is served at the next service point, and allocation under pressure
depends on it.

Each captured or backlog task has finitely many predecessors, so finite
acyclic data is eventually reclaimed if service points continue. Pacing
retains a dropped graph's storage for longer; it does not change the units
spent on it.

When all three fresh queues and both object classes stay ready, the active
older object advances within six queued work units. An object behind it must
first wait for its predecessors, so the six-unit bound does not apply to every
object.

Suspended cursors occupy dead List capacity fields or the upper bits of dead
record reference-map bytes. Reference flags remain intact. Cursor encoding
uses at most ten bytes on the tested 64-bit ABI.

Batching reduces scheduler overhead under specific conditions:

- Contiguous List visits share the remaining budget and stop when they create
  new recent work. A whole List never counts as one unit. Record fields share
  one unit up to the eight-field examination limit above; the first field that
  owns a reference, or the record's finalization, ends that unit.
- If the last captured object is an already-visited unary record, it can be
  finalized before its recent child. This frees chains in reverse allocation
  order and delays recent service by at most one object unit. It cannot bypass
  another captured object.

- Frame exit and statement cleanup usually find nothing pending (an
  old-object backlog does not count). When the exiting
  frame's written slots plus its retirement, or the statement's temporaries
  plus their chunk retirements, fit within K, they are released at that
  service point without entering the queues, in the order and with the units
  the scheduler would use. A frame that exits with statement temporaries
  still attached alternates frame and chunk units from the scheduler's
  current queue turn, as the queues would. If a release queues an object, the
  remaining slots or chunks are queued and the scheduler continues from the
  state it would have reached. `make check-direct-service` compares both
  paths' complete transcripts at K 1, 2, 4, 7, 32 and 1,024, with no
  backlog and with a K/8 one.

These paths require non-reentrant runtime and allocator hooks.

### Scope cells under a cleanup budget

With scope cells a function keeps its owners in initialized-null stack cells
instead of a frame (the lowering is described in
[runtime memory](runtime-memory.md#scope-ownership-lowering)). Entering a scope
and storing a temporary are not service points. Each statement cleanup and
return is one: it visits each of its n cells (at most K, checked by the
compiler) for one unit, releasing the cell's value without servicing (an
unshared leaf is freed in that unit; a dead aggregate joins the object queue),
then services up to K − n queued units. Cells never enter a queue or cache, so
a cleanup point never defers its own cells; it may finish them before older
queued work that the frame scheduler would have interleaved with them. That
order is not part of this contract; the K units per service point are.
Replacing a local's value releases the old value with its own service, as
`minyar_rc_local` does (K total). Diagnostic unwinding releases each live cell
like an ordinary release. Intermediate
pending ownership remains local to the poll; batching neither raises K nor
delays a competing queue.

## Pool allocation and exhaustion

The buddy pool has depth `D = log2(heap_capacity / 32)`, or 21 at the default
capacity. Allocation splits at most D blocks; freeing merges at most D buddies.
Unlinking a free block needs no scan. Resize validates an in-place growth path
before changing it, then falls back to allocation, copying, and freeing when
necessary. Metadata iterations are bounded by `4D + 1`; copying takes time
proportional to the retained bytes. Per-allocation rounding uses less than
`2 × max(requested_bytes, 32)`, excluding the state map.

Fragmentation can still prevent an allocation. So can pending cleanup, even
when the program can no longer reach the values occupying the pool. Capacity
must cover live values, children held by unprocessed edges, retired frames and
chunks, caches, rounding, and both buffers during a resize. There is no universal
ratio between live bytes and retained bytes: an owner-count budget cannot bound
the storage of variable-sized objects.

On exhaustion, the pool reports failure. It does not expand, switch to the
system allocator, or perform an unbounded cleanup drain. System allocation
failures are also reported.

### Cache costs

Integer-to-Text conversion caches nonnegative values below
`MINYAR_INTEGER_TEXT_CACHE_LIMIT`. Entries are filled on demand and last until
process exit. A zero limit removes the pointer table and formats every value
into ordinary owned Text.

On the supported 64-bit layout, a full cache costs:

| Entry limit | Fixed/lazy pool blocks | Static pointer table |
| --- | ---: | ---: |
| 32,768 (default) | 2 MiB | 256 KiB |
| 256 | 16 KiB | 2 KiB |

With eager or system allocation, the default cache requests 1,758,362 heap
bytes plus the table, excluding allocator overhead. These are capacity costs,
not startup RSS figures. A smaller cache does not shrink a pre-touched pool;
it also means more formatting and allocation for repeated uncached values.
For example, set `-DMINYAR_INTEGER_TEXT_CACHE_LIMIT=256` when compiling the
runtime source, rather than when linking an existing runtime object or IR file.

The ownership-storage cache has a separate `MINYAR_FRAME_CACHE_BYTES` cap.
Charges include each frame header, the full capacity of its local-value and
written-index arrays, and at most one completely retired temporary chunk.
The chunk is cached only after its separate finalization unit; it owns no
values and never joins the pending queues again until reused. Both keep service
opportunities remain on cache hits. Pool profiles count rounded blocks; the
system profile counts requested bytes without allocator overhead. On the
current ABI the chunk requests 80 bytes (one 128-byte pool block), sharing the
existing cap with frames. A zero cap disables both caches. Active and pending
frames/chunks are outside this cache cap.

Native integrations that manually discard private ownership roots must also
discard the chunk-cache root. Normal numeric thread-domain disposal frees it.
The cache invariant and amortized cost are in
[the temporary-storage design](records/2026-10-20-perfcs/temporary-cache.md).

There is no full cleanup drain at process exit. Measurements of complete
reclamation must add one to their harness.

## Platforms and checks

The tested ABI uses an eight-byte ownership header and a 64-bit target.
Correctness checks have run on macOS arm64 and Ubuntu 24.04/glibc with Clang 18
on Linux aarch64 and x86_64. Linux runs used OrbStack on Apple Silicon, with
x86_64 emulation. Native Linux performance, embedded-libc integration, Windows,
and 32-bit microcontroller ports remain unverified. See [Linux testing](../experiments/linux/README.md).

```sh
make check-bounded            # Finite pool and source ownership
make check-memory-profiles    # System, fixed, and lazy profiles
make check-integer-text-cache # Values, aliases, and cache storage
make check-critical-path     # Prepared arithmetic, Lists, and scalar records
```

The profile runner supports native and sanitizer checks at budgets 1, 32, and
1,024.
