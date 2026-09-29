/* Cycles use the public owning-slot API; no collector-specific roots. */
#define MINYAR_RC_TESTING 1
#define MINYAR_INTEGER_TEXT_CACHE_LIMIT 0
#include "../runtime/minyar_runtime.c"
#include <assert.h>

static size_t maximum_poll_work;
static long long slot(void *p) { return (long long)(uintptr_t)p; }
static void poll_many(size_t n) {
#ifdef MINYAR_BOUNDED_RC
    while (n--) {
        size_t before = rc_cycle_units;
        size_t work = minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
        assert(rc_cycle_units - before <= work);
        if (work > maximum_poll_work) maximum_poll_work = work;
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
#ifdef MINYAR_BOUNDED_RC
    size_t batches = 0;
    while (rc_pending_count) {
        assert(++batches < 2000000);
        size_t work = minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
        assert(work > 0);
        if (work > maximum_poll_work) maximum_poll_work = work;
        assert(rc_bounded_last_work <= MINYAR_RC_POLL_BUDGET);
    }
#else
    minyar_rc_release(NULL);
#endif
    assert(!rc_cycle_head && !rc_cycle_pending);
    assert(rc_object_count == 0);
    assert(rc_bytes == 0);
}

/* Independent graph oracle: only modeled reachable objects may be read or
 * mutated. Reacquiring an owner from an edge tests the root-insertion barrier. */
static void graph_oracle(void) {
    enum { N = 48, F = 3 };
    unsigned random = 314159u;
    for (unsigned round = 0; round < 40; round++) {
        MinyarRecord *nodes[N];
        int edges[N][F], roots[N];
        for (int i = 0; i < N; i++) {
            nodes[i] = minyar_record_new(F + 1);
            minyar_record_set(nodes[i], F, i);
            roots[i] = 1;
            for (int f = 0; f < F; f++) {
                edges[i][f] = -1;
                minyar_record_set_take(nodes[i], f, 0);
            }
        }
        for (unsigned step = 0; step < 2000; step++) {
            int live[N], queue[N], count = 0;
            for (int i = 0; i < N; i++) {
                live[i] = roots[i];
                if (live[i]) queue[count++] = i;
            }
            for (int q = 0; q < count; q++)
                for (int f = 0; f < F; f++) {
                    int to = edges[queue[q]][f];
                    if (to >= 0 && !live[to]) { live[to] = 1; queue[count++] = to; }
                }
            if (!count) break;
            for (int i = 0; i < N; i++) if (live[i]) {
                assert(minyar_record_get(nodes[i], F) == i);
                for (int f = 0; f < F; f++)
                    assert(minyar_record_get(nodes[i], f) ==
                           (edges[i][f] < 0 ? 0 : slot(nodes[edges[i][f]])));
            }
            random = random * 1664525u + 1013904223u;
            int a = queue[(random >> 8) % (unsigned)count];
            int b = queue[(random >> 16) % (unsigned)count];
            int f = (int)((random >> 24) % F);
            switch (random % 5) {
            case 0:
                if (roots[a]) { roots[a] = 0; minyar_rc_release(nodes[a]); }
                break;
            case 1:
                if (!roots[a]) { minyar_rc_retain(nodes[a]); roots[a] = 1; }
                break;
            default:
                edges[a][f] = b;
                minyar_record_replace(nodes[a], f, slot(nodes[b]), 0);
            }
            poll_many(1);
        }
        for (int i = 0; i < N; i++) if (roots[i]) minyar_rc_release(nodes[i]);
        empty();
    }
}

static void growing_list(void) {
    MinyarList *list = minyar_list_new();
    minyar_list_references(list);
    size_t before = rc_cycle_epochs;
    for (size_t i = 0; i < 1024; i++) {
        MinyarRecord *node = self_loop();
        minyar_list_add(list, slot(node));
        minyar_rc_release(node);
        poll_many(2);
        assert(minyar_record_get((MinyarRecord *)(uintptr_t)minyar_list_get(list, i), 0) == slot(node));
    }
    assert(rc_cycle_epochs > before);
    minyar_rc_release(list);
    empty();
    /* A List itself can also be a cycle in the native owning-slot API. */
    list = minyar_list_new();
    minyar_list_references(list);
    minyar_list_add(list, slot(list));
    minyar_rc_release(list);
    empty();
    /* K1 must include the constant-depth Text-view backing destruction. */
    MinyarText *text = copy_c_text("long enough for a view");
    MinyarText *view = minyar_text_slice(text, 0, 10);
    minyar_rc_release(text);
    minyar_rc_release(view);
#ifdef MINYAR_BOUNDED_RC
    assert(rc_bounded_last_work <= MINYAR_RC_POLL_BUDGET);
#endif
    empty();
}

int main(void) {
#ifndef MINYAR_BOUNDED_RC
    /* Eager cycle work must also advance during scalar loop service points. */
    minyar_rc_enter(0);
    MinyarList *loop = minyar_list_new();
    minyar_list_references(loop);
    for (size_t i = 0; i < 1000; i++) minyar_list_add(loop, slot(loop));
    minyar_rc_release(loop);
    for (size_t i = 0; i < 2000; i++) minyar_rc_step();
    assert(rc_object_count == 0);
    minyar_rc_leave();
#endif
    growing_list();
    graph_oracle();
    /* Transfer the only external owner into a receiver owned by that same
     * object: garbage can arise without any ordinary count decrement. */
    MinyarList *inside = minyar_list_new();
    minyar_list_references(inside);
    MinyarRecord *moved = minyar_record_new(1);
    minyar_record_set_take(moved, 0, slot(inside));
    minyar_list_add_take(inside, slot(moved));
    empty();
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
    printf("cycles: roots, transfers, oracle, interleavings; units=%zu epochs=%zu max-poll=%zu", rc_cycle_units, rc_cycle_epochs, maximum_poll_work);
#ifdef MINYAR_BOUNDED_HEAP
    printf(" peak-pool=%zu", minyar_pool_high_water);
#endif
    puts("");
}
