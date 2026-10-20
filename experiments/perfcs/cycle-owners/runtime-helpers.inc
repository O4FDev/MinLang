/* Appended after the complete cycle runtime and stack-frame entry points.
 * Only proof runtime wrappers define MINYAR_RC_TESTING. No queue is fabricated. */
#include <assert.h>
#if defined(MINYAR_COMPILER_ARENA) || !defined(MINYAR_BOUNDED_RC) || !defined(MINYAR_SYSTEM_HEAP)
#error This study requires the shipping default bounded system-heap runtime.
#endif
#ifdef NDEBUG
#error This study requires its activation and cleanup assertions.
#endif

static void perfcs_owner_drain(void) {
    size_t calls = 0;
    for (;;) {
        size_t work = minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
        assert(work <= MINYAR_RC_POLL_BUDGET);
        if (!work) break;
        assert(++calls < 100000000);
    }
    assert(!rc_pending_count && !rc_cycle_pending);
    assert(rc_cycle_phase == RC_CYCLE_IDLE);
}

void perfcs_owner_prepare(int active) {
    assert(!rc_frames && !rc_scopes && !rc_pending_count && !rc_cycle_present);
#ifdef MINYAR_RC_TESTING
    assert(!rc_object_count && !rc_bytes && !rc_immortal_object_count);
    assert(!rc_heap_allocation_count);
#endif
    if (active) {
        /* Public construction, edge store, external release and service only.
         * There is no direct cycle request, proof mutation or queue editing. */
        MinyarRecord *cycle = minyar_record_new_traced(1);
        minyar_record_set_reference_traced(cycle, 0, (long long)(uintptr_t)cycle);
        assert((((RcObject *)cycle - 1)->ownership & 7) == RC_TRACED);
        minyar_rc_release(cycle);
        perfcs_owner_drain();
        assert(rc_cycle_present == 1 && rc_cycle_completed > 0);
        assert(!rc_cycle_head && !rc_cycle_known_head);
#ifdef MINYAR_RC_TESTING
        assert(rc_cycle_units > 0 && !rc_object_count && !rc_bytes);
        assert(!rc_heap_allocation_count);
#endif
    } else {
        assert(!rc_cycle_present && !rc_cycle_completed);
    }
}

void perfcs_owner_finish(int active) {
    assert(!rc_frames && !rc_scopes);
    perfcs_owner_drain();
    assert(rc_cycle_present == (unsigned)active);
    assert(!rc_cycle_head && !rc_cycle_tail && !rc_cycle_known_head && !rc_cycle_known_tail);
    assert(!rc_cycle_gray_head && !rc_cycle_gray_tail && !rc_cycle_active);
    assert(!rc_bounded_active && !rc_bounded_head && !rc_bounded_tail);
    assert(!rc_bounded_recent_head && !rc_bounded_recent_tail);
    assert(!rc_bounded_frame_head && !rc_bounded_frame_tail);
    assert(!rc_bounded_chunk_head && !rc_bounded_chunk_tail);
#ifdef MINYAR_RC_TESTING
    assert(!rc_object_count && !rc_bytes && !rc_immortal_object_count);
#endif
    /* Normal owners have completed their public bounded retirement. Reclaim
     * only the physically cached, fully retired frame and chunk storage. */
    while (rc_free_frames) {
        RcFrame *frame = rc_free_frames;
        rc_free_frames = frame->previous;
        rc_bounded_cached_frame_bytes -= rc_heap_charge(frame, sizeof(*frame));
        if (frame->locals)
            rc_bounded_cached_frame_bytes -= rc_heap_charge(frame->locals,
                frame->local_capacity * (sizeof(void *) + sizeof(size_t)));
        rc_heap_deallocate(frame->locals);
        rc_heap_deallocate(frame);
    }
    rc_bounded_chunk_cache_clear();
    assert(!rc_free_frames && !rc_bounded_cached_chunk && !rc_bounded_cached_frame_bytes);
#ifdef MINYAR_RC_TESTING
    assert(!rc_heap_allocation_count);
#endif
#if !MINYAR_THREADED && MINYAR_SYSTEM_SMALL_HEAP
    for (unsigned index = 0; index < RC_SYSTEM_SIZE_CLASSES; ++index)
        assert(!rc_system_available[index]);
#endif
}
