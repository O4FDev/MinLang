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
configuration. Eligible leaf functions with at most `min(8, K−1)` owner slots
use compiler-generated stack storage; K1 retains ordinary ownership frames.
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
| `MINYAR_FRAME_CACHE_BYTES` | 256 KiB | Cache capacity in bytes |
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

The compiler inserts ownership operations automatically. Immutable record
fields and restrictions on recursive List mutation prevent ownership cycles.
The runtime uses no tracing, background collector, or user finalizers. Its
reference counts are single-threaded: managed objects cannot be shared across
native threads through this ownership mechanism.

An aggregate whose count reaches zero joins a retirement queue. Its header
holds the queue link, and its outgoing references keep children alive until
cleanup visits them. Text, scalar Lists and records, empty reference
aggregates, and Lists containing only immortal references can be freed
immediately. Once a List receives a mortal reference, it permanently switches
to ordinary reference traversal.

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

## The work budget

Let **K** be `MINYAR_RC_POLL_BUDGET`.
`minyar_rc_poll(budget)` performs at most `min(budget, K)` queued work units
and returns the number performed. One unit visits an object field or a
frame/temporary owner, or finalizes a task. Releasing a visited owner may also
free one leaf, requiring at most three backing frees. Cleanup never recursively
walks the object graph. Queue selection examines at most three queues.

The limits for individual runtime operations are:

| Operation | Cleanup limit |
| --- | --- |
| Public release | K, including immediate leaf destruction |
| Managed object/data allocation or data resize | K queued units |
| Frame entry, frame exit, or statement cleanup | K each |
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
these operations. Nor does the table bound all work inside a call: frame entry
still clears its local array and may resize it, while the written-slot index
adds one machine word per capacity slot. Record initialization, Text processing,
List growth and copying, I/O, system allocation, page faults, and scheduling
fall outside the cleanup budget. An application deadline requires bounds on
all operations along its critical path and validation on the target system.

## Scheduling and batching

Objects, frames, and temporary chunks receive round-robin service. Within the
object queue, service alternates between recent work and an older captured
batch. New arrivals cannot join that batch. Once it is exhausted, the recent
stack becomes the next batch in constant bookkeeping work. Each captured task
therefore has finitely many predecessors; finite acyclic data is eventually
reclaimed if polling continues.

When all three queues and both object classes stay ready, the active older
object advances within six queued work units. An object behind it must first
wait for its predecessors, so the six-unit bound does not apply to every object.

Suspended cursors occupy dead List capacity fields or the upper bits of dead
record reference-map bytes. Reference flags remain intact. Cursor encoding
uses at most ten bytes on the tested 64-bit ABI.

Batching reduces scheduler overhead under specific conditions:

- Contiguous List visits share the remaining budget and stop when they create
  new recent work. A whole List never counts as one unit.
- If the last captured object is an already-visited unary record, it can be
  finalized before its recent child. This frees chains in reverse allocation
  order and delays recent service by at most one object unit. It cannot bypass
  another captured object.
- With exactly one unvisited unary record, no active object or frame/temporary
  tasks, and at least two units left, a field visit and finalization run as a
  pair. They still cost two units. Budget-one and competing-work cases follow
  the ordinary scheduler.
- A uniquely owned unary child can continue directly into the next pair. This
  requires at least four remaining units, leaving two for the child. Each
  iteration costs two; the final ordinary pair publishes queue, cursor, count,
  and parity state before returning. Shared children use the normal decrement
  path.

These paths require non-reentrant runtime and allocator hooks. Intermediate
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
| 32,768 (default) | 3 MiB | 256 KiB |
| 256 | 24 KiB | 2 KiB |

With eager or system allocation, the default cache requests 1,758,362 heap
bytes plus the table, excluding allocator overhead. These are capacity costs,
not startup RSS figures. A smaller cache does not shrink a pre-touched pool;
it also means more formatting and allocation for repeated uncached values.
For example, set `-DMINYAR_INTEGER_TEXT_CACHE_LIMIT=256` when compiling the
runtime source, rather than when linking an existing runtime object or IR file.

The frame cache has a separate `MINYAR_FRAME_CACHE_BYTES` cap. Charges include
each frame header and the full capacity of its local-value and written-index
arrays. Pool profiles count rounded blocks; the system profile counts requested
bytes without allocator overhead. Active frames and frames awaiting retirement
are outside this cache cap.

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
