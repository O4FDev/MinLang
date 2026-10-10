/* Protected source owners across header service and subsequent retirement. */
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include "../runtime/minyar_stack_frames.h"
#include <assert.h>

static void drain(void) {
    while (rc_pending_count) {
        size_t work = minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
        assert(work && work <= MINYAR_RC_POLL_BUDGET);
    }
}
static void dispose_cache(void) {
    while (rc_free_frames) {
        RcFrame *frame = rc_free_frames;
        rc_free_frames = frame->previous;
        rc_heap_deallocate(frame->locals);
        rc_heap_deallocate(frame);
    }
    rc_bounded_cached_frame_bytes = 0;
}

static void check(unsigned mode, long long length) {
    RcFrame header;
    struct {
        void *owner;
        size_t index;
    } storage;
    _Static_assert(sizeof(storage) == 16, "One stack owner slot is 16 bytes");
    if (mode == 2)
        minyar_rc_enter_stack_v1(&header, &storage, 1);
    else
        minyar_rc_enter(mode == 0 ? 1 : 0);
    int actual_stack = rc_frames == &header;
    assert(actual_stack == (mode == 2 && MINYAR_RC_POLL_BUDGET > 1));
    MinyarList *source = minyar_list_new();
    for (long long i = 0; i < length; i++)
        minyar_list_add(source, i * 37 - 11);
    if (mode == 1) {
        minyar_rc_borrow(source);
        minyar_rc_release(source);
    } else {
        minyar_rc_local_take(0, source);
    }
    /* Header poll drops this independent physical owner; active caller remains. */
    MinyarRecord *retired = minyar_record_new(1);
    minyar_record_set_reference(retired, 0, (long long)(uintptr_t)source);
    assert((((RcObject *)source - 1)->ownership >> 3) == 2);
    rc_drop(retired);
    assert(rc_pending_count == 1);
    MinyarList *result = minyar_list_appended(source, -313, 0, 0);
    assert(result != source && result->length == length + 1);
    assert((((RcObject *)source - 1)->ownership >> 3) == 1);
    if (length)
        assert(result->values != source->values);
    for (long long i = 0; i < length; i++)
        assert(result->values[i] == i * 37 - 11 && source->values[i] == i * 37 - 11);
    if (mode == 1) {
        minyar_rc_step();
        drain();
        minyar_rc_leave();
    } else if (mode == 2) {
        minyar_rc_leave_stack_v1(&header);
    } else {
        minyar_rc_leave();
    }
    drain();
    dispose_cache();
    assert(!rc_frames && rc_object_count == 1);
    for (long long i = 0; i < length; i++)
        assert(result->values[i] == i * 37 - 11);
    assert(result->values[length] == -313);
    minyar_rc_release(result);
    drain();
    assert(!rc_object_count && !rc_bytes && !rc_pending_count);
#ifdef MINYAR_BOUNDED_HEAP
    assert(!minyar_pool_used);
#else
    assert(!rc_heap_allocation_count);
#endif
    printf("mode=%u length=%lld stack=%d recovered\n", mode, length, actual_stack);
}
int main(void) {
    for (unsigned mode = 0; mode < 3; mode++) {
        check(mode, 0);
        check(mode, 257);
    }
    return 0;
}
