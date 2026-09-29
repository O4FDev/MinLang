/* Cycles use the public owning-slot API; no collector-specific roots. */
#define MINYAR_RC_TESTING 1
#define MINYAR_INTEGER_TEXT_CACHE_LIMIT 0
#include "../runtime/minyar_runtime.c"
#include <assert.h>

static long long slot(void *p) { return (long long)(uintptr_t)p; }
static void poll_many(size_t n) {
#ifdef MINYAR_BOUNDED_RC
    while (n--) {
        size_t work = minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
        assert(work <= MINYAR_RC_POLL_BUDGET);
        assert(rc_bounded_last_work <= MINYAR_RC_POLL_BUDGET);
    }
#else
    (void)n;
    minyar_rc_release(NULL);
#endif
}
static MinyarRecord *self_loop(void) {
    MinyarRecord *r = minyar_record_new(1);
    minyar_record_set_reference(r, 0, slot(r));
    return r;
}
static void empty(void) {
    poll_many(200000);
    assert(rc_object_count == 0);
    assert(rc_bytes == 0);
}
int main(void) {
    MinyarRecord *r = self_loop();
    poll_many(1000);
    assert(minyar_record_get(r, 0) == slot(r));
    minyar_rc_release(r);
    empty();
    /* Repeated garbage must fit a small fixed/lazy pool. */
    for (size_t i = 0; i < 20000; i++) {
        r = self_loop();
        minyar_rc_release(r);
        poll_many(16);
        assert(rc_object_count < 100);
    }
    empty();
    /* A long ring needs many batches, then becomes garbage mid-collection. */
    MinyarRecord *first = minyar_record_new(1), *last = first;
    for (size_t i = 1; i < 1000; i++) {
        MinyarRecord *next = minyar_record_new(1);
        minyar_record_set_reference(last, 0, slot(next));
        if (last != first) minyar_rc_release(last);
        last = next;
    }
    minyar_record_set_reference(last, 0, slot(first));
    minyar_rc_release(last);
    poll_many(1);
    minyar_rc_release(first);
    empty();
    /* An expression temporary is the only external owner. */
    minyar_rc_enter(0);
    r = self_loop();
    minyar_rc_keep(r);
    poll_many(4000);
    assert(minyar_record_get(r, 0) == slot(r));
    minyar_rc_leave();
    empty();
    /* Take transfers and repeated root/edge changes during collection. */
    MinyarList *roots = minyar_list_new();
    minyar_list_references(roots);
    r = self_loop();
    minyar_list_add_take(roots, slot(r));
    for (size_t i = 0; i < 4000; i++) {
        minyar_rc_retain(r);
        minyar_list_set(roots, 0, 0);
        poll_many(1);
        assert(minyar_record_get(r, 0) == slot(r));
        minyar_list_set_take(roots, 0, slot(r));
        poll_many(1);
        MinyarRecord *dead = self_loop();
        minyar_rc_release(dead);
    }
    minyar_rc_release(roots);
    empty();
    puts("cycles: roots, transfers, interleavings, bounded batches and recovery");
}
