/* A function/statement retirement shares one cleanup budget regardless of
 * locals/temporaries. Exercise completely full heaps and three-way fairness. */
#define MINYAR_BOUNDED_HEAP 1
#define MINYAR_BOUNDED_HEAP_BYTES (8u * 1024u * 1024u)
#define MINYAR_RC_TESTING 1
#ifndef MINYAR_RC_POLL_BUDGET
#define MINYAR_RC_POLL_BUDGET 1
#endif
#include "../runtime/minyar_runtime.c"
#include <assert.h>

static void drain(void) {
    size_t calls = 0;
    while (rc_pending_count) {
        assert(minyar_rc_poll(SIZE_MAX) > 0);
        assert(rc_bounded_last_work <= MINYAR_RC_POLL_BUDGET);
        assert(++calls < 1000000);
    }
    assert(rc_object_count == 0 && rc_bytes == 0);
}
static void release_frame_cache(void) {
    while (rc_free_frames) {
        RcFrame *frame = rc_free_frames;
        rc_free_frames = frame->previous;
        assert(frame->temporary_head == NULL && frame->temporary_count == 0);
        minyar_pool_deallocate(frame->locals);
        minyar_pool_deallocate(frame);
    }
}
static void complete_recovery(void) {
    release_frame_cache();
    rc_bounded_cached_frame_bytes = 0;
    assert(minyar_pool_used == 0);
    void *whole = minyar_pool_try_allocate(MINYAR_POOL_BYTES);
    assert(whole == minyar_pool);
    minyar_pool_deallocate(whole);
}
static size_t fill_heap(void **fillers, size_t limit) {
    size_t count = 0;
    while (minyar_pool_mask) {
        assert(count < limit);
        unsigned order = (unsigned)__builtin_ctzll((unsigned long long)minyar_pool_mask);
        fillers[count++] = minyar_pool_try_allocate(pool_block_size(order));
        assert(fillers[count - 1]);
    }
    assert(minyar_pool_used == MINYAR_POOL_BYTES);
    return count;
}
static void frame_and_fairness(void) {
    enum { LOCALS = 4096, TEMPORARIES = 8192, CHILDREN = 4096 };
    minyar_rc_enter(LOCALS);
    for (size_t i = 0; i < LOCALS; i++)
        minyar_rc_local_take((long long)i, minyar_record_new_scalar(1));
    for (size_t i = 0; i < TEMPORARIES; i++)
        minyar_rc_keep(minyar_record_new_scalar(1));
    MinyarList *wide = minyar_list_new(); minyar_list_references(wide);
    for (size_t i = 0; i < CHILDREN; i++)
        minyar_list_add_take(wide, (long long)(uintptr_t)minyar_record_new_scalar(1));
    minyar_rc_release(wide);
    void *fillers[128];
    size_t filler_count = fill_heap(fillers, 128);
    size_t objects = rc_object_count, allocations = minyar_pool_allocation_count;
    minyar_rc_leave();
    assert(rc_frames == NULL);
    assert(rc_object_count >= objects - MINYAR_RC_POLL_BUDGET);
    assert(rc_bounded_last_work <= MINYAR_RC_POLL_BUDGET);
    assert(minyar_pool_allocation_count == allocations);
    assert(rc_bounded_active && rc_bounded_frame_head && rc_bounded_chunk_head);
    size_t cursor = rc_bounded_cursor;
    RcFrame *frame = rc_bounded_frame_head;
    size_t locals = frame->local_count;
    RcTemporaryChunk *chunk = rc_bounded_chunk_head;
    size_t count = chunk->count;
    for (unsigned i = 0; i < 3; i++) assert(minyar_rc_poll(1) == 1);
    assert(rc_bounded_cursor == cursor + 1);
    assert(frame->local_count == locals - 1);
    assert(rc_bounded_chunk_head != chunk || chunk->count < count);
    assert(minyar_pool_allocation_count == allocations);
    drain();
    for (size_t i = 0; i < filler_count; i++) minyar_pool_deallocate(fillers[i]);
    complete_recovery();
}
static void statement_and_alias(void) {
    minyar_rc_enter(1);
    MinyarText *survivor = copy_c_text("kept🙂");
    minyar_rc_local_take(0, survivor);
    for (size_t i = 0; i < 8192; i++) {
        minyar_rc_retain(survivor);
        minyar_rc_keep(survivor);
    }
    void *fillers[128];
    size_t count = fill_heap(fillers, 128);
    size_t references = ((RcObject *)survivor - 1)->ownership >> 3;
    size_t allocations = minyar_pool_allocation_count;
    minyar_rc_step();
    assert(rc_frames->temporary_count == 0 && rc_frames->temporary_head == NULL);
    assert((((RcObject *)survivor - 1)->ownership >> 3) >= references - MINYAR_RC_POLL_BUDGET);
    assert(minyar_pool_allocation_count == allocations);
    /* Repeated empty steps must not duplicate the detached chain. */
    for (size_t i = 0; i < 13; i++) minyar_rc_step();
    for (size_t i = 0; i < count; i++) minyar_pool_deallocate(fillers[i]);
    for (size_t i = 0; i < 128; i++) {
        minyar_rc_enter(1); /* May reuse a frame while old chunks still own aliases. */
        minyar_rc_local(0, survivor);
        minyar_rc_borrow(survivor);
        minyar_rc_leave();
        assert(minyar_text_character_at(survivor, 4) == 0x1f642);
    }
    /* Model a borrowed return acquiring its independent result owner. */
    minyar_rc_retain(survivor);
    minyar_rc_leave();
    while (rc_pending_count) {
        minyar_rc_poll(1);
        assert(minyar_text_character_at(survivor, 0) == 'k');
    }
    assert((((RcObject *)survivor - 1)->ownership >> 3) == 1);
    minyar_rc_release(survivor); drain(); complete_recovery();
}
int main(void) {
    frame_and_fairness(); statement_and_alias();
    printf("bounded step/leave passed at budget %u: full-heap retirement without allocation, "
           "4096 locals, 8192 temporaries, three-queue fairness, continued execution and aliases\n",
           (unsigned)MINYAR_RC_POLL_BUDGET);
    return 0;
}
