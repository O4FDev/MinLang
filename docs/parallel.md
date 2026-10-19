# Safe data parallelism

`parallel for` divides an Integer range into independent iterations. Existing
scalar buffers keep their owners on the calling thread. Each iteration writes
only its own index, while scalar captures are snapshots. The compiler rejects
reference escape, resizing, changed indices, shared scalar mutation and callees
that can reach raw machine or native effects. Same-index aliases remain safe.
The [language guide](language.md#parallel-ranges) describes the supported syntax.

On macOS and Linux, persistent pthread workers claim chunks of 128 indices
from separate queues and steal unfinished chunks. The caller also works, then
waits for every worker to acknowledge completion. Worker LLVM contains no
ownership or call-depth operations. Capture storage is allocated once per
lexical loop in the caller's entry block, so repeated dispatch has fixed stack
cost. The pool has no managed allocations or per-job heap allocation for
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
`315453`. Build it with
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

Run `./minyar --release examples/gallery/parallel.min -o /tmp/garden`, then
`/tmp/garden /tmp/garden.png`, for the 1200×800 Julia garden. Without arguments
it prints a woven Unicode preview. Orbits, palette lookup, pixel blending and
PNG scanline conversion use safe parallel slots. The PNG writer stores its
scanlines without compression and checksums them on the owner thread; this
keeps the gallery independent of graphics libraries. A two-by-two PNG is
compared byte-for-byte with an independently constructed fixture, including
chunk CRCs and the stream checksum.
