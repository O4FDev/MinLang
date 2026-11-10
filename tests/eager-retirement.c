/* A small reference aggregate that loses its last owner is retired by that
 * release, inside the release's K units, instead of joining the retirement
 * queue. A larger one still queues, so the scheduler keeps its role and its
 * work bound. The observer counts finalized objects, so the assertions see
 * exactly when destruction happens.
 *
 * Built with MINYAR_RC_POLL_BUDGET=1: a release may then service at most one
 * queued unit, so "was queued" and "was retired by the release" are
 * distinguishable from the outside. */
#ifndef MINYAR_RC_POLL_BUDGET
#error this test must be compiled with MINYAR_RC_POLL_BUDGET=1
#endif
#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_RC_TESTING 1
static void count_release(void *pointer);
#define MINYAR_RC_OBJECT_RELEASE_OBSERVER count_release
#include "../runtime/minyar_runtime.c"
#include <assert.h>

static size_t freed;
static void count_release(void *pointer) {
    (void)pointer;
    freed++;
}

static MinyarList *reference_list(void) {
    MinyarList *list = minyar_list_new();
    minyar_list_references(list);
    return list;
}

int main(void) {
    /* One slot List of one unique record: both die in the release call. */
    MinyarList *small = reference_list();
    MinyarRecord *child = minyar_record_new(1);
    minyar_record_set(child, 0, 7);
    minyar_list_add_take(small, (long long)(uintptr_t)child);
    size_t before = freed;
    size_t queued = rc_pending_count;
    minyar_rc_release(small);
    assert(freed == before + 2);
    assert(rc_pending_count == queued);
    assert(rc_bounded_last_work <= MINYAR_RC_POLL_BUDGET);

    /* A full small List retires in the same release, and its unique small
     * children go with it, up to the unit allowance. */
    MinyarList *full = reference_list();
    for (int index = 0; index < RC_SMALL_LIST_SLOTS; index++)
        minyar_list_add_take(full, (long long)(uintptr_t)minyar_record_new_scalar(1));
    before = freed;
    queued = rc_pending_count;
    minyar_rc_release(full);
    assert(freed > before);
    assert(rc_pending_count == queued);

    /* One slot beyond the allowance: the List is queued. A K=1 release may
     * service one queued unit but cannot retire the whole List, so work stays
     * pending where the small case left none. */
    MinyarList *large = reference_list();
    for (int index = 0; index <= RC_SMALL_LIST_SLOTS; index++)
        minyar_list_add_take(large, (long long)(uintptr_t)minyar_record_new_scalar(1));
    before = freed;
    queued = rc_pending_count;
    minyar_rc_release(large);
    assert(rc_pending_count > queued);

    /* Queued work still retires under the documented budget. */
    while (rc_pending_count) {
        size_t work = minyar_rc_poll_idle(MINYAR_RC_POLL_BUDGET);
        assert(work > 0 && work <= MINYAR_RC_POLL_BUDGET);
    }
    assert(freed == before + (size_t)RC_SMALL_LIST_SLOTS + 2);
    return 0;
}
