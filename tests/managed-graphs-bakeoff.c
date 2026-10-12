/* Preserve the strict Sol bakeoff producer/growth contracts at 73c0749.
 * Only the owning-slot/barrier names are adapted to the optional runtime. */
#define main managed_graphs_fixture_main
#include "managed-graphs-runtime.c"
#undef main

#ifdef MINYAR_BOUNDED_RC
static void bakeoff_drain(void) {
    size_t remaining = 10000000;
    while (rc_pending_count && remaining--) poll_many(1);
    assert(!rc_pending_count);
}

static void growing_mutator(void) {
    MinyarList *live = minyar_list_new_traced();
    minyar_list_references(live);
    minyar_list_add_traced(live, slot(live));
    MinyarRecord *garbage = self_loop();
    minyar_rc_retain_traced(live);
    rc_drop(live);
    rc_drop(garbage);
    for (size_t i = 0; i < 1000; i++) {
        minyar_list_add_traced(live, slot(live));
        MinyarRecord *late = self_loop();
        minyar_rc_release(late);
        poll_many(1);
    }
    bakeoff_drain();
    assert(rc_object_count == 1);
    assert(minyar_list_length(live) == 1001);
    minyar_rc_release(live);
    empty();
}

static void outgrow_one_unit(void) {
    MinyarList *live = minyar_list_new_traced();
    minyar_list_references(live);
    list_reserve(live, 24000);
    minyar_list_add_traced(live, slot(live));
    MinyarRecord *garbage = self_loop();
    bakeoff_drain();
    minyar_rc_retain_traced(live);
    rc_drop(live);
    rc_drop(garbage);
    for (size_t i = 0; i < 10000; i++) {
        /* Two appends for exactly ONE queued unit, bypassing automatic
         * service just as the original regression did. */
        for (size_t j = 0; j < 2; j++) {
            minyar_rc_retain_traced(live);
            rc_cycle_edge_insert(live, live);
            live->values[live->length++] = slot(live);
            rc_cycle_commit_insert(live, live);
        }
        size_t before = rc_cycle_units;
        size_t work = minyar_rc_poll(1);
        assert(work <= 1 && rc_bounded_last_work <= 1);
        assert(rc_cycle_units - before <= work);
        if (i == 1000) assert(rc_object_count == 1);
    }
    assert(rc_object_count == 1);
    assert(minyar_list_length(live) == 20001);
    minyar_rc_release(live);
    empty();
}

static void producer(void) {
    size_t peak = 0;
    for (size_t i = 0; i < 10000; i++) {
        MinyarRecord *garbage = self_loop();
        minyar_rc_release(garbage);
        if (rc_object_count > peak) peak = rc_object_count;
    }
    /* No explicit poll or drain between allocations; original bound. */
    assert(peak < 1000);
    empty();
    printf("bakeoff producer peak=%zu\n", peak);
}

static void shared_live_producer(void) {
    enum { LIVE = 512, STEPS = 10000 };
    MinyarRecord *nodes[LIVE];
    for (size_t i = 0; i < LIVE; i++) nodes[i] = minyar_record_new_traced(1);
    for (size_t i = 0; i < LIVE; i++)
        minyar_record_set_reference_traced(nodes[i], 0, slot(nodes[(i + 1) % LIVE]));
    for (size_t i = 1; i < LIVE; i++) minyar_rc_release(nodes[i]);
    size_t peak = 0;
    for (size_t i = 0; i < STEPS; i++) {
        MinyarRecord *garbage = minyar_record_new_traced(2);
        minyar_record_set_reference_traced(garbage, 0, slot(garbage));
        minyar_record_set_reference_traced(garbage, 1, slot(nodes[0]));
        minyar_rc_release(garbage);
        minyar_record_replace_traced(nodes[i % LIVE], 0, slot(nodes[(i + 1) % LIVE]), 0);
        if (rc_object_count > peak) peak = rc_object_count;
        assert(rc_object_count < 5000);
    }
    bakeoff_drain();
    assert(rc_object_count == LIVE);
    minyar_rc_release(nodes[0]);
    empty();
    printf("bakeoff shared producer peak=%zu live=%u\n", peak, LIVE);
}
#endif

int main(int argc, char **argv) {
    const char *selected = argc > 1 ? argv[1] : "all";
    assert(!strcmp(selected, "all") || !strcmp(selected, "growing") ||
           !strcmp(selected, "outgrow") || !strcmp(selected, "producer") ||
           !strcmp(selected, "shared"));
#ifdef MINYAR_BOUNDED_RC
    if (!strcmp(selected, "all") || !strcmp(selected, "growing")) growing_mutator();
    if (!strcmp(selected, "all") || !strcmp(selected, "outgrow")) outgrow_one_unit();
    if (!strcmp(selected, "all") || !strcmp(selected, "producer")) producer();
    if (!strcmp(selected, "all") || !strcmp(selected, "shared")) shared_live_producer();
#endif
    empty();
    puts("bakeoff: original producer and continuous-growth bounds");
}
