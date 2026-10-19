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
cost. The pool has no managed allocations or per-job heap allocation.

`MINYAR_PARALLEL_THREADS=1` uses the same chunk semantics on the caller. Values
from 2 to 64 request additional workers; the default uses online processors,
capped at 64. Thread creation can fall back to fewer workers if the host refuses
one. Windows, freestanding targets and recoverable execution currently use the
sequential backend. Native thread stacks and the fixed pool metadata are real
storage costs, independent of managed heap ownership.

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
independent scheduler oracle under ThreadSanitizer. Correctness and timing are
separate evidence.
