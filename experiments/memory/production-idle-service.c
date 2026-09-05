/* Independent idle-service accounting: observable owner counts, not just the
 * instrumentation value, prove that immediate leaf work consumes one unit. */
#if !defined(MINYAR_SYSTEM_HEAP) && !defined(MINYAR_BOUNDED_HEAP)
#define MINYAR_SYSTEM_HEAP 1
#endif
#define MINYAR_RC_TESTING 1
#ifndef MINYAR_RUNTIME_SOURCE
#define MINYAR_RUNTIME_SOURCE "../../runtime/minyar_runtime.c"
#endif
#include MINYAR_RUNTIME_SOURCE
#include <assert.h>

static size_t references(void *value) {
    return (((RcObject *)value - 1)->ownership >> 3);
}

int main(void) {
    rc_bounded_last_work = 123;
    assert(rc_service_pending(0) == 0 && rc_bounded_last_work == 0);
    rc_bounded_last_work = 123;
    assert(rc_service_pending(SIZE_MAX) == 0 && rc_bounded_last_work == 0);
    rc_bounded_last_work = 123;
    MinyarRecord *leaf = minyar_record_new_scalar(1);
    assert(rc_bounded_last_work == 0);
    rc_bounded_last_work = 123;
    void *bytes = rc_allocate_data(13);
    assert(rc_bounded_last_work == 0);
    rc_bounded_last_work = 123;
    bytes = rc_reallocate_data(bytes, 29);
    assert(rc_bounded_last_work == 0);
    rc_free_data(bytes);
    rc_bounded_last_work = 123;
    minyar_rc_release(NULL);
    assert(rc_bounded_last_work == 0);

    MinyarRecord *shared = minyar_record_new_scalar(1);
    minyar_record_set(shared, 0, 1729);
    MinyarList *wide = minyar_list_new();
    minyar_list_references(wide);
    for (size_t i = 0; i < 4096; i++)
        minyar_list_add(wide, (long long)(uintptr_t)shared);
    rc_drop(wide); /* Queue without spending a public-release service budget. */
    size_t before = references(shared);
    assert(before == 4097 && rc_pending_count == 1);
    rc_bounded_last_work = 123;
    minyar_rc_release(leaf);
    assert(rc_bounded_last_work == MINYAR_RC_POLL_BUDGET);
    assert(before - references(shared) == MINYAR_RC_POLL_BUDGET - 1);
    before = references(shared);
    minyar_rc_release(NULL);
    assert(rc_bounded_last_work == MINYAR_RC_POLL_BUDGET);
    assert(before - references(shared) == MINYAR_RC_POLL_BUDGET);
    before = references(shared);
    rc_bounded_last_work = 123;
    assert(rc_service_pending(0) == 0 && rc_bounded_last_work == 0);
    assert(references(shared) == before);
    while (rc_pending_count) assert(minyar_rc_poll(1) == 1);
    assert(references(shared) == 1 && shared->values[0] == 1729);
    minyar_rc_release(shared);
    assert(rc_bounded_last_work == 1);
    assert(!rc_object_count && !rc_bytes);
#ifdef MINYAR_SYSTEM_HEAP
    assert(!rc_heap_allocation_count);
#else
    assert(!minyar_pool_used);
#endif
    puts("idle reset and exact immediate-leaf budget verified by independent owner counts");
    return 0;
}
