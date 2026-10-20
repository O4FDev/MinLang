# A bounded cache of fully retired temporary storage

Design recorded before implementation, October 20, 2026. This is independent
of the sole-queue batching experiment and must be measured separately.

An eight-slot temporary chunk is allocated whenever an expression's current
chunk is absent/full, then freed after its last owner visit and one separately
charged finalization. With 30.9M keeps and 14.5M chunks in the memory lane's
rounded observation, a chunk averages only 2.13 owners. Increasing its capacity
cannot amortize independent statements. Reusing storage after retirement can.

Keep at most **one fully finalized chunk per execution domain**. The cache is
not a queue and owns no references. Its count is zero; stale pointer bits are
never roots or read as owners. A chunk becomes eligible only at the existing
separate finalization unit, after unlinking it from the retirement FIFO. Cache
hits transfer that storage back to an active frame, initialize its next/count,
and remove its byte charge from the cache. Active and pending chunks never
enter the cache, so frames can still be reused while earlier chunks retire.

Charge the cached chunk against the existing MINYAR_FRAME_CACHE_BYTES total,
using rc_heap_charge: requested storage on system heap and rounded buddy block
on fixed/lazy heaps. Do not create a second independent capacity allowance.
At most sizeof(RcTemporaryChunk) requested bytes (80 on the current ABI), or
one rounded block, displaces cached frames. Zero cache capacity disables reuse.
If the cap is full or a chunk is already cached, perform the existing free.
Active/retired storage remains outside this cache cap, as before. There is no
claim of lower RSS or universal live/retired memory ratio.

Preserve **both** keep service opportunities, including the pre-storage one on
a cache hit. Null/immortal keep stays poll-free. Incoming owned references
already protect their values during the pre-storage poll. Every owner visit
and finalization keeps its existing work unit and queue turn. rc_drop and all
cycle barriers are unchanged. Cache insertion/removal never creates retirement
debt; finalization still decrements pending once. Explicit allocator-recovery
checks and numeric thread-domain disposal must drain the cache as well as free
frames, preserving their existing zero-allocation/whole-pool assertions.

For C chunk lifecycles, let M be cache misses and H hits. There remain exactly
T + C owner/finalization units; caching removes H allocation/free pairs at
constant O(1) bookkeeping per hit/finalization. A sequential allocation-retire
stream with no intervening cap pressure has M=1 regardless of C. With arbitrary
concurrency/pressure M can be C: this is a workload-dependent constant-factor
improvement, not a universal asymptotic reduction in ownership work. Cache
storage is bounded by the unchanged existing cap and one chunk.

Validation must prove no early reuse at K1, no retained owner references, exact
K-total work/service on cache hits/misses, alias safety, active cycle barriers,
cache-cap zero/too-small/full boundaries, numeric-domain cleanup, and complete
buddy-pool recovery. Existing strict physical-allocation assertions stay; their
explicit cache teardown must be extended rather than relaxed. Compare cache-only
and batching-only variants against the same original runtime and identical LLVM;
retain regressions and unscaled hardware-counter samples.
