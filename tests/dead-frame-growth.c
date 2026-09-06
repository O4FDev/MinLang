#define MINYAR_RC_TESTING 1
#define MINYAR_BOUNDED_HEAP 1
#define MINYAR_BOUNDED_HEAP_BYTES 4096
/* Admit the old 64-byte frame plus 1024-byte locals, then naturally evict the
 * enlarged frame. Recovery must not depend on editing the runtime's cache. */
#define MINYAR_FRAME_CACHE_BYTES 1088
#include "../runtime/minyar_runtime.c"
#include <assert.h>

static void drain(void) {
    size_t calls = 0;
    while (rc_pending_count) {
        assert(++calls < 10000);
        size_t work = minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
        assert(work > 0 && work <= MINYAR_RC_POLL_BUDGET);
    }
}

int main(void) {
    minyar_rc_enter(0);
    RcFrame *frame = rc_frames;
    minyar_rc_leave();
    drain();
    void *blocker = rc_heap_allocate(1024);
    void *lower = rc_heap_allocate(1024);
    minyar_rc_enter(64);
    assert(rc_frames == frame);
    assert(pool_offset(blocker) == 1024 && pool_offset(lower) == 2048);
    assert(pool_offset(frame->locals) == 3072);
    void *owned = minyar_record_new_scalar(1);
    minyar_record_set(owned, 0, 99);
    minyar_rc_local_take(63, owned);
    minyar_rc_leave();
    drain();
    assert(!rc_object_count && !rc_bytes && !rc_pending_count);
    assert(rc_bounded_cached_frame_bytes == 1088);
    rc_heap_deallocate(lower);

    /* No separately free 2048-byte block exists. The retired locals and their
     * lower buddy together satisfy growth; retaining dead bytes must not OOM. */
    minyar_rc_enter(128);
    assert(rc_frames == frame && pool_offset(frame->locals) == 2048);
    assert(rc_bounded_cached_frame_bytes == 0);
    for (size_t i = 0; i < 128; i++) assert(frame->locals[i] == NULL);
    minyar_rc_leave();
    drain();
    assert(!rc_frames && !rc_free_frames && !rc_bounded_cached_frame_bytes);
    assert(!rc_object_count && !rc_bytes && !rc_pending_count);
    rc_heap_deallocate(blocker);
    assert(!minyar_pool_used);

    /* Inspect shadow state before reading free-list links, whose accessor
     * restores poison and could otherwise conceal a missing-poison defect. */
#ifdef MINYAR_POOL_ASAN
    for (size_t i = 1024; i < MINYAR_POOL_BYTES; i++)
        assert(__asan_address_is_poisoned(minyar_pool + i));
#endif
    assert(minyar_pool_mask == ((size_t)1 << minyar_pool_max_order));
    assert(minyar_pool_free[minyar_pool_max_order] == (PoolLink *)minyar_pool);
    assert(minyar_pool_map[0] == minyar_pool_max_order + 1);
    for (size_t i = 1; i < MINYAR_POOL_MAP_BYTES; i++) assert(!minyar_pool_map[i]);
    PoolLink root = pool_read_link(minyar_pool_free[minyar_pool_max_order]);
    assert(!root.previous && !root.next);
    puts("retired frame growth admits lower buddy, clears locals and fully recovers");
}
