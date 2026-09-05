/* TEST-ONLY independent owner accounting for deferred frame and chunk queues.
 * Requires the bounded frame/chunk profile; MINYAR_RUNTIME_SOURCE may select
 * an isolated candidate. Includes the existing object-queue oracle and model. */
#include <stddef.h>
static size_t scan_frame_owners(void);
#define PRODUCTION_EXTRA_OWNER_SCAN() scan_frame_owners()
#define main graph_only_main
#include "production-live-oracle.c"
#undef main

static void owner(void *value) {
    if (value) entries[entry((RcObject *)value - 1)].expected++;
}

static void *local_value(RcFrame *frame, size_t index) {
#ifdef MINYAR_BOUNDED_TRACKED_LOCALS
    return (void *)((uintptr_t)frame->locals[index] & ~(uintptr_t)1);
#else
    return frame->locals[index];
#endif
}

static void scan_locals(RcFrame *frame, int pending) {
#ifdef MINYAR_BOUNDED_TRACKED_LOCALS
    size_t *indices = frame->locals ? (size_t *)(frame->locals + frame->local_capacity) : NULL;
    size_t registered = pending ? frame->local_count : frame->written_count;
    assert(registered <= frame->local_capacity);
    unsigned char *seen = calloc(frame->local_capacity ? frame->local_capacity : 1, 1);
    assert(seen);
    for (size_t i = 0; i < registered; i++) {
        assert(indices[i] < frame->local_capacity);
        if (!pending) assert(indices[i] < frame->local_count);
        assert((uintptr_t)frame->locals[indices[i]] & 1);
        assert(!seen[indices[i]]);
        seen[indices[i]] = 1;
        if (pending) owner(local_value(frame, indices[i]));
    }
    if (!pending) {
        size_t tags = 0;
        for (size_t i = 0; i < frame->local_count; i++) {
            tags += ((uintptr_t)frame->locals[i] & 1) != 0;
            owner(local_value(frame, i));
        }
        assert(tags == registered);
    }
    free(seen);
#else
    (void)pending;
    for (size_t i = 0; i < frame->local_count; i++) owner(frame->locals[i]);
#endif
}

static size_t scan_chunks(RcTemporaryChunk *chunk) {
    size_t count = 0;
    for (; chunk; chunk = chunk->next) {
        assert(++count < 8192 && chunk->count <= 8);
        for (size_t i = 0; i < chunk->count; i++) owner(chunk->values[i]);
    }
    return count;
}

static size_t scan_frame_owners(void) {
    size_t count = 0, active = 0;
    for (RcFrame *frame = rc_frames; frame; frame = frame->previous) {
        assert(++active < 8192);
        scan_locals(frame, 0);
        scan_chunks(frame->temporary_head);
    }
    for (RcFrame *frame = rc_bounded_frame_head; frame; frame = frame->previous) {
        assert(++count < 8192);
        scan_locals(frame, 1);
        assert(!frame->temporary_head && !frame->temporary_tail && !frame->temporary_count);
        for (RcFrame *cached = rc_free_frames; cached; cached = cached->previous)
            assert(cached != frame); /* Partial retirement cannot be reused. */
    }
    return count + scan_chunks(rc_bounded_chunk_head);
}

static MinyarRecord *record(long long value) {
    MinyarRecord *result = minyar_record_new(4);
    minyar_record_set(result, 0, value);
    return result;
}

static void clear_frame_cache(void) {
    while (rc_free_frames) {
        RcFrame *frame = rc_free_frames;
        rc_free_frames = frame->previous;
#ifdef MINYAR_SYSTEM_HEAP
        rc_heap_deallocate(frame->locals);
        rc_heap_deallocate(frame);
#else
        minyar_pool_deallocate(frame->locals);
        minyar_pool_deallocate(frame);
#endif
    }
#ifdef MINYAR_BOUNDED_TRACKED_LOCALS
    rc_bounded_cached_frame_bytes = 0;
#endif
}

static void sparse_frame_reassignment(void) {
    const size_t extents[] = {4096, 2, 8192, 3};
    MinyarRecord *roots[ROOTS] = {record(101), record(202)};
    for (size_t round = 0; round < sizeof(extents) / sizeof(*extents); round++) {
        size_t extent = extents[round];
        minyar_rc_enter((long long)extent);
        size_t slots[] = {extent - 1, 0, extent / 2};
        for (size_t step = 0; step < 48; step++) {
            size_t slot = slots[step % 3];
            minyar_rc_local((long long)slot, roots[step % 2]);
            verify(roots);
            minyar_rc_local_take((long long)slot, NULL);
            minyar_rc_local_take((long long)slot, NULL);
            verify(roots);
            minyar_rc_local((long long)slot, roots[(step + 1) % 2]);
            verify(roots);
        }
#ifdef MINYAR_BOUNDED_TRACKED_LOCALS
        assert(rc_frames->written_count == (extent == 2 ? 2 : 3));
#endif
        minyar_rc_leave();
        while (rc_pending_count) { verify(roots); assert(minyar_rc_poll(1) <= 1); }
        verify(roots);
    }
    for (size_t i = 0; i < 2; i++) { minyar_rc_release(roots[i]); roots[i] = NULL; }
    while (rc_pending_count) { verify(roots); assert(minyar_rc_poll(1) <= 1); }
    verify(roots);
    clear_frame_cache();
    assert(!rc_object_count && !rc_bytes);
    assert_backend_empty();
    puts("sparse frame writes, repeated clear/reassign, shrinking and growing reuse preserve exact owners");
}

static void frame_lifetimes(void) {
    enum { LOCALS = 4096, TEMPORARIES = 8192 };
    MinyarRecord *roots[ROOTS] = {0};
    minyar_rc_enter(LOCALS);
    MinyarRecord *original = record(7171);
    minyar_rc_local_take(0, original);
    for (size_t i = 1; i < LOCALS; i++) minyar_rc_local((long long)i, original);
    for (size_t i = 0; i < TEMPORARIES; i++) minyar_rc_borrow(original);
    verify(roots);
    size_t before = ((RcObject *)original - 1)->ownership >> 3;
    minyar_rc_step();
    size_t after = ((RcObject *)original - 1)->ownership >> 3;
    assert(before >= after && before - after <= MINYAR_RC_POLL_BUDGET);
    assert(rc_bounded_chunk_head); /* step cannot drain all 8192 owners. */
    verify(roots);

    /* Preserve a returned alias while its old activation retires gradually. */
    minyar_rc_retain(original); roots[0] = original;
    RcFrame *retiring = rc_frames;
    before = ((RcObject *)original - 1)->ownership >> 3;
    minyar_rc_leave();
    after = ((RcObject *)original - 1)->ownership >> 3;
    assert(before >= after && before - after <= MINYAR_RC_POLL_BUDGET);
    assert(rc_bounded_frame_head && !rc_frames);
    verify(roots);

    minyar_rc_enter(3);
    assert(rc_frames != retiring);
    minyar_rc_local_take(0, record(8181));
    minyar_rc_local(1, original);
    /* Observe partial retirement with one-unit polls before testing repeated
     * full-budget steps. Otherwise a larger valid budget could finish the
     * queues before the reuse observation, without any runtime defect. */
    size_t polls = 0;
    int reused_before_chunks_finished = 0;
    while (rc_pending_count) {
        assert(minyar_rc_poll(1) <= 1);
        assert(++polls < 100000);
        if (!(polls % 127)) verify(roots);
        if (!reused_before_chunks_finished && rc_free_frames == retiring && rc_bounded_chunk_head) {
            minyar_rc_enter(2);
            assert(rc_frames == retiring);
            minyar_rc_local(0, original);
            minyar_rc_borrow(original);
            verify(roots);
            minyar_rc_leave();
            reused_before_chunks_finished = 1;
        }
        assert(original->values[0] == 7171);
        assert(((MinyarRecord *)local_value(rc_frames, 0))->values[0] == 8181);
    }
    assert(reused_before_chunks_finished);
    verify(roots);
    /* Repeated step on a live frame must not duplicate detached chunks. */
    for (size_t round = 0; round < 12; round++) {
        minyar_rc_borrow(original);
        minyar_rc_step();
        minyar_rc_step();
        verify(roots);
    }
    minyar_rc_leave();
    minyar_rc_release(roots[0]); roots[0] = NULL;
    while (rc_pending_count) { verify(roots); assert(minyar_rc_poll(1) <= 1); }
    verify(roots);
    assert(!rc_frames && !rc_object_count && !rc_bytes);
    clear_frame_cache();
    assert_backend_empty();
    puts("deferred frames/chunks preserve every owner; step/leave drop <=K owners; aliases and full storage recovery passed");
}

int main(void) {
    graph_only_main();
    sparse_frame_reassignment();
    frame_lifetimes();
    return 0;
}
