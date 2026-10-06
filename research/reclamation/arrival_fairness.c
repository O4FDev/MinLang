/* Adversarial actual-runtime scheduling, deliberately independent of allocation
 * service frequency. Prepare finite arrivals first, then retire one per unit. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_RC_TESTING 1
#include "../../runtime/minyar_runtime.c"
#include <assert.h>
static size_t cursor(RcObject *o) {
    if (rc_bounded_active == o) return rc_bounded_cursor;
    /* Decode saved record cursor independently, bit by bit. */
    MinyarRecord *r = (MinyarRecord *)(o + 1);
    unsigned char *map = (unsigned char *)(r->values + r->length);
    size_t value = 0;
    for (size_t bit = 0; bit < sizeof(size_t) * CHAR_BIT && bit / 7 < (size_t)r->length; bit++)
        if (map[bit / 7] & (1u << (1 + bit % 7))) value |= (size_t)1 << bit;
    return value;
}
int main(void) {
    enum { OLD = 8192, ARRIVALS = 1536 };
    MinyarRecord *shared = minyar_record_new_scalar(1);
    minyar_record_set_scalar(shared, 0, 1729);
    MinyarRecord *old = minyar_record_new(OLD), *newer[ARRIVALS];
    minyar_record_set_reference(old, OLD - 1, (long long)(uintptr_t)shared);
    for (size_t i = 0; i < ARRIVALS; i++) {
        newer[i] = minyar_record_new(2);
        minyar_record_set_reference(newer[i], 1, (long long)(uintptr_t)shared);
    }
    minyar_rc_enter(OLD);
    for (size_t i = 0; i < OLD; i++) {
        minyar_rc_local((long long)i, shared);
        minyar_rc_borrow(shared);
    }
    minyar_rc_leave();
    assert(rc_bounded_frame_head && rc_bounded_chunk_head);
    RcFrame *frame = rc_bounded_frame_head;
    rc_drop(old);
    RcObject *o = (RcObject *)old - 1;
    while (!cursor(o)) assert(minyar_rc_poll(1) == 1);
    size_t initial = cursor(o), frame_initial = frame->local_count, window = initial;
    for (size_t i = 0; i < ARRIVALS; i++) {
        assert(rc_bounded_frame_head == frame && rc_bounded_chunk_head);
        rc_drop(newer[i]);
        assert(minyar_rc_poll(1) == 1);
#ifndef RESEARCH_LIFO
        if (i % 6 == 5) {
            assert(cursor(o) > window);
            window = cursor(o);
        }
#else
        (void)window;
#endif
    }
    size_t progress = cursor(o) - initial, frame_progress = frame_initial - frame->local_count;
#ifdef RESEARCH_LIFO
    assert(progress == 0);
#else
    assert(progress >= ARRIVALS / 6);
#endif
    assert(frame_progress >= ARRIVALS / 3);
    while (rc_pending_count) assert(minyar_rc_poll(1) == 1);
    assert(rc_object_count == 1 && ((RcObject *)shared - 1)->ownership >> 3 == 1);
    assert(minyar_record_get(shared, 0) == 1729);
    minyar_rc_release(shared);
    while (rc_free_frames) {
        RcFrame *f = rc_free_frames; rc_free_frames = f->previous;
        rc_heap_deallocate(f->locals); rc_heap_deallocate(f);
    }
    assert(!rc_bytes && !rc_object_count && !rc_heap_allocation_count);
    printf("{\"arrivals\":%u,\"old_object_visits\":%zu,\"frame_visits\":%zu,\"final_bytes\":%zu}\n",
           ARRIVALS, progress, frame_progress, rc_bytes);
}
