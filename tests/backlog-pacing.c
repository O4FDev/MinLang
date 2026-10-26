/* The old-object backlog (docs/bounded-runtime-contract.md, "Scheduling and
 * batching"): object work left at the end of a service point is served at an
 * average of MINYAR_RC_BACKLOG_BUDGET (K/8) units per managed allocation, in
 * K-unit batches, unless an idle service point lifts the pace. Other service
 * points never see it. Exact expectations at the configured K (8 or more). */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_RC_TESTING 1
#ifndef MINYAR_RC_BACKLOG_BUDGET
#define MINYAR_RC_BACKLOG_BUDGET (MINYAR_RC_POLL_BUDGET / 8)
#endif
static void pacing_freed(void *object);
#define MINYAR_RC_OBJECT_RELEASE_OBSERVER pacing_freed
#include "../runtime/minyar_runtime.c"
#include <assert.h>

enum { K = MINYAR_RC_POLL_BUDGET, P = MINYAR_RC_BACKLOG_BUDGET, BATCH = K / P };
_Static_assert(P > 0 && K % P == 0, "pacing fixture needs K >= 8 with K/8 dividing K");

/* Leaves carry their group in field 0 so free order can be checked. */
static long long freed_group[1 << 16];
static size_t freed_count;
static void pacing_freed(void *pointer) {
    RcObject *object = pointer;
    if ((object->ownership & 7) == RC_SCALAR_RECORD)
        freed_group[freed_count++] = ((MinyarRecord *)(object + 1))->values[0];
}

static MinyarList *leaves(size_t count, long long group) {
    MinyarList *list = minyar_list_new();
    minyar_list_references(list);
    for (size_t i = 0; i < count; i++) {
        MinyarRecord *leaf = minyar_record_new_scalar(1);
        minyar_record_set(leaf, 0, group);
        minyar_list_add_take(list, (long long)(uintptr_t)leaf);
    }
    return list;
}

static void empty(void) {
    while (rc_pending_count || rc_backlog_count) minyar_rc_poll_idle(K);
    assert(!rc_object_count && !rc_backlog_count && !rc_backlog_credit);
    freed_count = 0;
}

/* A dropped List costs one unit per entry plus its retirement. The first
 * service point does K of it; the rest becomes backlog and earns P credit per
 * managed allocation, so exactly every BATCH-th allocation does a K batch.
 * Ordinary polls do nothing for it. */
static void cadence(void) {
    size_t entries = 40 * K;
    minyar_rc_release(leaves(entries, 1));
    /* Left-over work gets one more full service point, then becomes backlog. */
    assert(rc_bounded_last_work == K && !rc_backlog_count && rc_pending_count == 1);
    assert(minyar_rc_poll(K) == K && rc_backlog_count == 1 && rc_pending_count == 0);
    assert(minyar_rc_poll(K) == 0 && !rc_backlog_credit);
    size_t remaining = entries + 1 - 2 * K, allocations = 0;
    while (remaining) {
        void *data = rc_allocate_data(16);
        allocations++;
        size_t work = rc_bounded_last_work;
        rc_free_data(data);
        if (allocations % BATCH) assert(work == 0 && rc_backlog_credit == (allocations % BATCH) * P);
        else {
            assert(work == (remaining < K ? remaining : K));
            remaining -= work;
        }
    }
    assert(!rc_pending_count && !rc_backlog_count && !rc_backlog_credit && !rc_object_count);
    assert(allocations == BATCH * ((entries + 1 - 2 * K + K - 1) / K));
    freed_count = 0;
}

/* Frame exits and statements keep their direct paths and never serve the
 * backlog; the allocations around them do. */
static void direct_paths(void) {
    minyar_rc_release(leaves(400 * K, 2));
    for (size_t round = 0; round < 4 * BATCH; round++) {
        minyar_rc_enter(2);
        minyar_rc_local_take(0, copy_c_text("a"));
        minyar_rc_keep(copy_c_text("b"));
        size_t credit = rc_backlog_credit;
        minyar_rc_step();
        assert(rc_bounded_last_work == 2 && rc_backlog_credit == credit);
        minyar_rc_leave();
        assert(rc_bounded_last_work == 2 && rc_backlog_credit == credit);
        assert(rc_backlog_count == 1 && !rc_pending_count);
    }
    empty();
}

/* Idle service points give the backlog the whole budget. */
static void idle(void) {
    minyar_rc_release(leaves(10 * K, 3));
    for (int i = 0; i < 5; i++) assert(minyar_rc_poll_idle(K) == K);
    assert(rc_backlog_count == 1);
    empty();
}

/* Work handed to an empty backlog continues exactly: a dropped chain still
 * frees in allocation-reverse order. Later left-over work joins the backlog
 * behind older work: group 4 finishes before any of group 5 is freed. */
static void order(void) {
    MinyarRecord *root = NULL;
    for (long long i = 0; i < 3 * K; i++) {
        MinyarRecord *leaf = minyar_record_new_scalar(1);
        minyar_record_set(leaf, 0, i);
        MinyarRecord *node = minyar_record_new(2);
        minyar_record_set_take(node, 0, (long long)(uintptr_t)leaf);
        minyar_record_set_take(node, 1, (long long)(uintptr_t)root);
        root = node;
    }
    minyar_rc_release(root);
    while (rc_pending_count || rc_backlog_count) minyar_rc_poll_idle(K);
    assert(freed_count == (size_t)(3 * K));
    for (size_t i = 0; i < freed_count; i++) assert(freed_group[i] == (long long)(3 * K - 1 - i));
    freed_count = 0;
    /* Each drop's own service point frees its first K entries; the left-over
     * work then runs oldest first. */
    MinyarList *older = leaves(4 * K, 4), *newer = leaves(4 * K, 5);
    minyar_rc_release(older);
    minyar_rc_poll(K);
    assert(rc_backlog_count == 1 && !rc_pending_count);
    minyar_rc_release(newer);
    while (rc_pending_count || rc_backlog_count) minyar_rc_poll_idle(K);
    assert(freed_count == (size_t)(8 * K));
    /* 4 (its first two service points), 5 (its fresh service, while the
     * backlog takes its share of the idle poll), then the rest of 4 before
     * the rest of 5: exactly four runs. */
    size_t runs = 1;
    for (size_t i = 1; i < freed_count; i++) runs += freed_group[i] != freed_group[i - 1];
    assert(freed_group[0] == 4 && runs == 4 && freed_group[freed_count - 1] == 5);
    empty();
}

/* A sleep is an idle service point. */
static void sleeping(void) {
    minyar_rc_release(leaves(200 * K, 6));
    minyar_rc_poll(K);
    assert(rc_backlog_count == 1);
    struct timespec start, end;
    clock_gettime(CLOCK_MONOTONIC, &start);
    assert(minyar_runtime_sleepNanoseconds(200000000) == 0);
    clock_gettime(CLOCK_MONOTONIC, &end);
    long long elapsed = (long long)(end.tv_sec - start.tv_sec) * 1000000000LL + (end.tv_nsec - start.tv_nsec);
    assert(elapsed >= 200000000);
    assert(!rc_pending_count && !rc_backlog_count && !rc_object_count);
    freed_count = 0;
}

/* The small system heap keeps allocating from one page until it fills: a
 * page that regains a free slot goes second, not first. */
static void page_order(void) {
#if MINYAR_SYSTEM_SMALL_HEAP
    enum { N = 2 * ((RC_SYSTEM_PAGE_BYTES - RC_SYSTEM_PAGE_PREFIX) / 64) };
    void *slots[N];
    for (int i = 0; i < N; i++) slots[i] = rc_system_allocate(40);
    RcSystemPage *first = ((RcSystemSlot *)slots[0] - 1)->page;
    RcSystemPage *second = ((RcSystemSlot *)slots[N - 6] - 1)->page;
    assert(first != second && !first->link && !second->link);
    rc_system_deallocate(slots[0]);
    rc_system_deallocate(slots[1]);
    void *a = rc_system_allocate(40);
    assert(((RcSystemSlot *)a - 1)->page == first);
    rc_system_deallocate(slots[N - 6]);
    void *b = rc_system_allocate(40);
    assert(((RcSystemSlot *)b - 1)->page == first);
    void *c = rc_system_allocate(40);
    assert(((RcSystemSlot *)c - 1)->page == second);
    rc_system_deallocate(a); rc_system_deallocate(b); rc_system_deallocate(c);
    for (int i = 2; i < N; i++) if (i != N - 6) rc_system_deallocate(slots[i]);
#endif
}

int main(void) {
    page_order(); /* First, before any other allocation of its size class. */
    cadence();
    direct_paths();
    idle();
    order();
    sleeping();
    printf("old-object backlog: K%d, %d units per allocation in K batches; direct paths, idle, order, sleep and page order hold\n", K, P);
    return 0;
}
