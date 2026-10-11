/* Rooted callback/capture graph with generated-style cleanup service points. */
#define MINYAR_RC_TESTING 1
#define MINYAR_INTEGER_TEXT_CACHE_LIMIT 0
#include "../build/managed-graphs-engine.c"
#include <assert.h>

static long long slot(void *p) {
    return (long long)(uintptr_t)p;
}
static int pending(void) {
#ifdef MINYAR_BOUNDED_RC
    return rc_pending_count != 0;
#else
    return rc_cycle_pending != 0;
#endif
}
static void poll_once(void) {
    size_t units = rc_cycle_units;
#ifdef MINYAR_BOUNDED_RC
    size_t work = minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
    assert(work <= MINYAR_RC_POLL_BUDGET);
    assert(rc_cycle_units - units <= work);
#else
    (void)minyar_callbackruntime_service();
    assert(rc_cycle_units - units <= 32);
#endif
}
static void drain(void) {
    size_t n = 0;
    while (pending()) {
        assert(++n < 2000000);
        poll_once();
    }
}
static MinyarRecord *peer(MinyarRecord *core) {
    MinyarRecord *p = minyar_record_new_traced(2);
    MinyarRecord *env = minyar_record_new_traced(3);
    MinyarRecord *cb = minyar_record_new_traced(3);
    MinyarRecord *details = minyar_record_new_traced(16);
    minyar_record_set_traced(env, 0, minyar_callback_domain());
    minyar_record_set_reference_traced(env, 1, slot(core));
    minyar_record_set_reference_traced(env, 2, slot(p));
    minyar_record_set_traced(cb, 0, 0);
    minyar_record_set_reference_traced(cb, 1, slot(env));
    minyar_record_set_traced(cb, 2, minyar_callback_domain());
    minyar_record_set_reference_traced(details, 0, slot(core));
    minyar_record_set_reference_traced(details, 1, slot(cb));
    minyar_record_set_reference_traced(p, 0, slot(cb));
    minyar_record_set_reference_traced(p, 1, slot(details));
    minyar_rc_release(env);
    minyar_rc_release(cb);
    minyar_rc_release(details);
    return p;
}
static MinyarRecord *graph(unsigned n, MinyarList **entries) {
    MinyarRecord *core = minyar_record_new_traced(2);
    MinyarList *list = minyar_list_new_traced();
    minyar_list_references(list);
    minyar_record_set_reference_traced(core, 0, slot(list));
    minyar_record_set_reference_traced(core, 1, slot(core));
    for (unsigned i = 0; i < n; i++)
        minyar_list_add_take_traced(list, slot(peer(core)));
    minyar_rc_release(list);
    *entries = list;
    drain();
    assert(rc_object_count == 4u * n + 2);
    return core;
}
static void read_borrows(MinyarRecord *core, MinyarList *entries, unsigned n) {
    size_t before = rc_cycle_units, epochs = rc_cycle_epochs;
    for (unsigned round = 0; round < 200; round++) {
        unsigned at = round % n;
        MinyarRecord *p = (MinyarRecord *)(uintptr_t)entries->values[at];
        MinyarRecord *cb = (MinyarRecord *)(uintptr_t)p->values[0];
        MinyarRecord *env = (MinyarRecord *)(uintptr_t)cb->values[1];
        minyar_rc_retain_traced(p);
        minyar_rc_retain_traced(cb);
        minyar_rc_retain_traced(env);
        minyar_callback_check(cb);
        minyar_callback_check_environment(env);
        /* Real generated helpers poll while their argument temporaries
         * remain held, not only after a short retain/drop pair. */
        for (unsigned calls = 0; calls < 256; calls++)
            poll_once();
        rc_drop(env);
        rc_drop(cb);
        rc_drop(p);
        assert(rc_cycle_pending); /* Last temporary requests are really queued. */
#ifdef MINYAR_BOUNDED_RC
        assert(rc_pending_count >= 1);
#endif
        long long wait = minyar_callbackruntime_serviceWait(20);
        assert(wait == 20 || (wait >= 0 && wait <= 10));
        assert(rc_object_count == 4u * n + 2);
        assert(env->values[1] == slot(core));
        MinyarRecord *details = (MinyarRecord *)(uintptr_t)p->values[1];
        minyar_record_set_traced(details, 15, round); /* Scalar update changes no edge. */
    }
    drain();
    fprintf(stderr, "stable reads n=%u: units=%zu epochs=%zu\n", n, rc_cycle_units - before,
            rc_cycle_epochs - epochs);
    assert(rc_cycle_units - before <= 8u * 200);
    assert(rc_cycle_epochs - epochs <= 2);
}
int main(int argc, char **argv) {
    unsigned n = argc > 1 ? (unsigned)strtoul(argv[1], NULL, 10) : 2048;
    assert(n == 32 || n == 256 || n == 2048);
    MinyarList *entries;
    MinyarRecord *core = graph(n, &entries);
    read_borrows(core, entries, n);
    /* Severing a real owning edge invalidates a previously rooted proof.
     * The detached callback/capture component must be reclaimed exactly. */
    minyar_list_set_traced(entries, 0, 0);
    drain();
    assert(rc_object_count == 4u * (n - 1) + 2);
    MinyarRecord *replacement = peer(core);
    drain();
    /* Transfer the sole external owner into a traced aggregate without a
     * count decrement. The old root proof cannot remain authoritative. */
    minyar_list_set_take_traced(entries, 0, slot(replacement));
    drain();
    assert(rc_object_count == 4u * n + 2);
    read_borrows(core, entries, n);
    /* A read temporary becomes the actual only external root. */
    MinyarRecord *held = (MinyarRecord *)(uintptr_t)entries->values[n - 1];
    minyar_rc_retain_traced(held);
    minyar_rc_release(core);
    drain();
    assert(rc_object_count == 4u * n + 2);
    minyar_rc_release(held);
    drain();
    assert(!rc_object_count && !rc_bytes && !rc_cycle_head && !rc_cycle_pending);
    /* An unrelated anchored component must not certify this entire registry. */
    MinyarList *again;
    core = graph(32, &again);
    MinyarRecord *outside = minyar_record_new_traced(1);
    minyar_record_set_reference_traced(outside, 0, slot(outside));
    drain();
    minyar_rc_release(core);
    drain();
    assert(rc_object_count == 1);
    minyar_rc_release(outside);
    drain();
    assert(!rc_object_count && !rc_bytes && !rc_cycle_head && !rc_cycle_pending);
    printf("cycle witness: n=%u units=%zu epochs=%zu objects=0 bytes=0\n", n, rc_cycle_units,
           rc_cycle_epochs);
    return 0;
}
