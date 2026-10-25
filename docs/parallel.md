# Safe data parallelism

`parallel for` divides an Integer range into independent iterations. Existing
scalar buffers keep their owners on the calling thread. Each iteration writes
only its own index, while scalar captures are snapshots. The compiler rejects
reference escape, resizing, changed indices, shared scalar mutation and callees
that can reach raw machine or native effects. Input buffers, and Bytes elements
of a captured `List<Bytes>`, may also be read through Bytes getters or passed
whole to parallel functions, which borrow them read-only; such reads count as
reads at any index for the alias checks below. Same-index aliases remain safe
when their storage begins at the same byte. Bytes guards compare backing
ranges, so C-layout views with distinct headers cannot hide shifted overlaps.
Read/write pairs and pairs of outputs are checked before dispatch; adjacent
views remain usable.
The [language guide](language.md#parallel-ranges) describes the supported syntax.

## Windows, scratch space and records

An iteration that produces several values writes a window,
`out.window(index, width)`: slots `index * width` up to
`index * width + width` of a captured output. Disjointness is proved at compile
time from the shape alone: the first argument must be the loop index token, and
the width must be an Integer literal or a captured binding (captures are
snapshots), the same token for every window of that buffer in the loop. Two
iterations `i != j` then own `[i·w, i·w + w)` and `[j·w, j·w + w)`, which do
not meet. The only runtime cost is one check per window taken (the product is
overflow-checked and must lie in `0..length - width`); every access through the
window keeps the ordinary per-access bounds check against `width`, so no write
leaves it. The window is a five-word header in the worker's entry block, laid
out like a Bytes view (negative capacity) and a List (`{ values, length,
capacity }`), pointing into the owner's storage; it owns nothing and no
ownership operation reaches it. The windowed buffer is otherwise untouchable in
that loop except for `.length`, so no direct-index access can reach another
iteration's slots. Windowed outputs join the alias guards: every input read
in the loop (even at the loop index), every other output of the same type and
every buffer reachable through a captured record is compared with them before
dispatch, and Bytes windows count as read away from the index for the
backing-range check.

Writable parameters extend this to functions. A parallel function that writes
a buffer parameter (by index or a Bytes `set` method) marks that parameter as
written; passing a parameter on to a written parameter marks it too, to a
fixed point over the whole program. Each call made inside a safe loop records
what it passes to buffer parameters, and a written parameter must receive this
iteration's window there. A captured buffer, an element of a `List<Bytes>`, or a
buffer field of a record reaches a callee read-only, so passing one to a
written parameter is rejected: "'fill' writes its parameter 'slots', so it
needs this iteration's window". Ordinary code is single-threaded and may pass
any buffer. Raw `parallelEntry` callers pass Integers, so functions with buffer
or record parameters cannot be raw entries.

Per-iteration scratch space is a window of an owner-allocated buffer:
`scratch.window(index, size)` over `count * size` slots. Nothing is allocated
in workers: allocation and ownership tracking are single-threaded, so a worker
cannot create managed values. Scratch is per iteration rather than per worker,
which costs `count * size` slots but keeps results independent of scheduling.

Records reach parallel code read-only, as loop captures or parallel function
parameters. A field read is a plain load of the record's slot
(`.minyar.record.get.checked`), without a retain, in every ownership mode
(legacy frames, `--bounded-owners`, `--scope-owners`, release): the owner thread
is blocked in the dispatch until every worker joins, so no field can be
reassigned and no value released while a worker holds it, and workers cannot
assign fields. The effect audit admits that reader but not the field writer.
Reachable fields may be Integer, Float, Boolean, Character, Bytes, scalar Lists
and nested records; Text, Maps, Lists of managed values, record methods and
records whose fields lead back to their own type are rejected, the last because
the buffers a record can reach must be finite to guard them: before dispatch,
every Bytes or List field reachable from a captured record is compared with each
output of its type. The Bytes elements of a captured `List<Bytes>` are compared
with every Bytes output in the same way, one comparison per element.

The diagnostics, in the order the checks run:

| rejection | diagnostic |
|---|---|
| `x.window(...)` outside a safe loop | window is available only inside a parallel for body |
| first argument not the index | the first window argument must be the loop index 'index' |
| width computed in the loop | a window width must be an Integer literal or a value from outside the loop |
| two widths for one buffer | every window of 'out' in one loop needs the same width |
| window of a non-captured or managed buffer | a window divides a captured Bytes or List of Integers, Floats, Booleans or Characters |
| window used as a value | bind a window with let … or pass it whole to a parallel function |
| other use of a window binding | a window can be indexed, measured with .length, read or written with Bytes get and set methods, or passed whole to a parallel function |
| reassigning a window binding | the window 'w' cannot be reassigned |
| touching the windowed buffer | 'out' is divided into windows in this loop |
| read-only buffer to a written parameter | 'f' writes its parameter 'p', so it needs this iteration's window |
| record field to a written parameter | parallel function 'f' passes a buffer field of record 'r' to 'g', which writes its parameter 'p' |
| field write / buffer-field write | records are read-only here / buffers inside records are read-only here |
| Text or other managed field | only Integer, Float, Boolean, Character, Bytes, scalar List and record fields can be read |
| self-referential record | its record's fields lead back to their own type |
| window too large at run time | parallel for window i of width w does not fit in a buffer of length n |

On macOS and Linux, persistent pthread workers claim chunks of up to 128
indices from separate queues and steal unfinished chunks. A range shorter than
four chunks per thread uses smaller chunks, down to one index, so a loop with
one long iteration per segment still spreads over the workers; reductions keep
128-index chunks so Float grouping stays independent of the thread count. The caller also works, then
waits for every worker to acknowledge completion. Worker LLVM contains no
ownership or call-depth operations. Capture storage is allocated once per
lexical loop in the caller's entry block, so repeated dispatch has fixed stack
cost. Checked byte accesses inline the buffer's pointer/length prefix and
validate positions and byte values before loading or storing; invalid accesses
use the ordinary runtime diagnostic. C layout assertions protect that prefix.
The pool has no managed allocations or per-job heap allocation for
ordinary loops. A reduction uses one profile-accounted scratch word per chunk,
allocated and freed by the owner. Workers produce private partial sums, and
deterministic chunk-order combination happens after the join. Integer additions
are checked, including the final combination. Float grouping is fixed across
thread counts; an empty reduction preserves its initial bits.

`MINYAR_PARALLEL_THREADS=1` uses the same chunk semantics on the caller. Values
from 2 to 64 request additional workers; the default uses online processors,
capped at 64. Thread creation can fall back to fewer workers if the host refuses
one. Windows and recoverable execution use the sequential backend. Native
thread stacks and the fixed pool metadata are real storage costs, independent
of managed heap ownership.

Freestanding programs initially run the same chunks sequentially. Starting
the OS processors installs the existing synchronous processor-entry scheduler;
safe loops and reductions then use those processors without pthreads. The
trusted `machine.setParallelScheduler(entry, context)` hook accepts a scheduler
with four Integer arguments: context, chunk entry, chunk count and arguments.
It must call the chunk entry once per index and join every processor before
returning. The environment remains on the owner's stack until that join.
The setup hook and device memory remain trusted machine operations, outside
the safe loop body.

`tests/parallel-for/boot.min` boots the real ARM64 processor scheduler, fills
5,003 owned slots, and checks Integer and Float reductions. It also checks
typed pixel blending, masks and the clipped desktop glow against checksum
`315453`, then identical-start and adjacent C-layout views against checksum
`31405`. Build it with
`make -C os ARCH=arm64 KERNEL_SOURCE=/absolute/path/to/tests/parallel-for/boot.min`
and boot its kernel with QEMU's `virt,gic-version=3`, 1 GiB RAM, and one or four
processors. Both runs must print `SAFE PARALLEL OK 623386` with the processor
count. The program halts after reporting, keeping processor storage alive.

The first measured `benchmarks/parallel.min` run on an Apple M1 Pro with eight
performance cores and two efficiency cores took 5.24, 2.51, 1.25, 0.70 and 0.67
seconds at 1, 2, 4, 8 and 10 threads. Every run printed checksum `483691130`.
That is 7.49× at eight threads and 7.82× at ten. Maximum resident storage rose
from 14,663,680 to 14,909,440 bytes. These are first samples on the shared
overnight machine, with some sanitizer work overlapping the run; they are
measurements, not regression thresholds. Allocation, three render passes,
serial checksum and pool shutdown are included. Keep the complete
`/usr/bin/time -l` output when comparing another revision or host.

`check-parallel-for` exercises optimized and unoptimized programs with exact
output and ownership cleanup, checks worker isolation, and requires invalid
worker accesses to fail without deadlock. `check-parallel-pool-tsan` checks the
independent scheduler oracle under ThreadSanitizer. `check-parallel-backend`
exercises the bare dispatcher and reductions through four joined processor-entry
threads; its `-tsan` target checks that boundary under ThreadSanitizer.
Correctness and timing are separate evidence.

The desktop's glow now draws owned canvases through checked byte slots, with
immutable opacity-table reads. Clipping, row padding and overlapping edge
bands preserve the previous packed-pixel result. Device-backed canvases retain
the raw adapter. The typed pixel tests compare blends, masks, coverage and
desktop glow against those existing packed routines at O0/O2 with ownership
checks. Coverage is a sequential prefix scan, not an independent pixel loop.
Safe BGR0 rendering visits four byte slots per pixel, with checked scalar
arithmetic; it can cost more CPU than the raw packed routines. The desktop
glow restricts dispatch to damaged rows and clips writes by column, retaining
each row's stride and padding. The Mandelbrot scaling measurements do not imply packed
SIMD throughput for byte operations.

Run `./minyar --release examples/gallery/parallel.min -o /tmp/garden`, then
`/tmp/garden /tmp/garden.png`, for the 1200×800 Julia garden. Without arguments
it prints a woven Unicode preview. Orbits, palette lookup, pixel blending and
PNG scanline conversion use safe parallel slots. The PNG writer stores its
scanlines without compression and checksums them on the owner thread; this
keeps the gallery independent of graphics libraries. A two-by-two PNG is
compared byte-for-byte with an independently constructed fixture, including
chunk CRCs and the stream checksum.
