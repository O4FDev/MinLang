/* Included only by incremental ownership runtimes, after the backing heap.
 * One fully finalized chunk shares the existing frame-cache byte allowance.
 * Cached slots contain no owners; their stale pointer bits are never read. */
#define MINYAR_BOUNDED_OWNER_CACHE 1
static MINYAR_THREAD_LOCAL RcTemporaryChunk *rc_bounded_cached_chunk;

static inline RcTemporaryChunk *rc_bounded_chunk_allocate(void) {
    RcTemporaryChunk *chunk = rc_bounded_cached_chunk;
    if (!chunk) return rc_heap_allocate(sizeof(*chunk));
    rc_bounded_cached_chunk = NULL;
    rc_bounded_cached_frame_bytes -= rc_heap_charge(chunk, sizeof(*chunk));
    return chunk;
}

/* The caller has unlinked this zero-owner task and charges its finalization
 * separately from its last owner visit, even when storage will be reused. */
static inline void rc_bounded_chunk_retire(RcTemporaryChunk *chunk) {
    size_t bytes = rc_heap_charge(chunk, sizeof(*chunk));
    if (!rc_bounded_cached_chunk && bytes <= MINYAR_FRAME_CACHE_BYTES &&
        rc_bounded_cached_frame_bytes <= MINYAR_FRAME_CACHE_BYTES - bytes) {
        chunk->next = NULL;
        rc_bounded_cached_chunk = chunk;
        rc_bounded_cached_frame_bytes += bytes;
    } else rc_heap_deallocate(chunk);
}

/* Numeric-domain disposal and explicit allocator-recovery test oracles only;
 * ordinary service points never evict caches or perform an unbounded drain. */
static inline void rc_bounded_chunk_cache_clear(void) {
    RcTemporaryChunk *chunk = rc_bounded_cached_chunk;
    if (!chunk) return;
    rc_bounded_cached_chunk = NULL;
    rc_bounded_cached_frame_bytes -= rc_heap_charge(chunk, sizeof(*chunk));
    rc_heap_deallocate(chunk);
}
