/* Deterministic adversarial acceptance fixture. Built against a frozen,
 * instrumented copy of the REAL runtime by test_acceptance.py. No clocks.
 * Poll totals are checked against independently observed reference-count drops.
 */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#define MINYAR_RC_TESTING 1
#include "../../runtime/minyar_runtime.c"
#include "../../runtime/minyar_stack_frames.h"
#include <assert.h>
#ifdef NDEBUG
#error Acceptance fixtures require assertions.
#endif
#ifdef ACCEPTANCE_ADAPTER
#include ACCEPTANCE_ADAPTER
#else
#include "acceptance_adapter.h"
#endif

enum { CALLS = 32, WIDTH = 6 * CALLS * MINYAR_RC_POLL_BUDGET + 1024 };
static size_t refs(void *value) { return (((RcObject *)value - 1)->ownership >> 3); }
static MinyarRecord *sentinel(void) {
    MinyarRecord *s = minyar_record_new_scalar(1);
    minyar_record_set_scalar(s, 0, 1729);
    return s;
}
static MinyarRecord *wide(MinyarRecord *s, size_t width) {
    MinyarRecord *r = minyar_record_new((long long)width);
    for (size_t i = 0; i < width; i++)
        minyar_record_set_reference(r, (long long)i, (long long)(uintptr_t)s);
    return r;
}
static void finish(MinyarRecord *s) {
    size_t limit = 1000000;
    while (rc_pending_count && limit--) assert(minyar_rc_poll(MINYAR_RC_POLL_BUDGET));
    assert(!rc_pending_count && !rc_frames);
    assert(refs(s) == 1 && minyar_record_get(s, 0) == 1729);
    minyar_rc_release(s);
    while (rc_pending_count) assert(minyar_rc_poll(MINYAR_RC_POLL_BUDGET));
    assert(!rc_bytes && !rc_object_count);
    while (rc_free_frames) {
        RcFrame *f = rc_free_frames; rc_free_frames = f->previous;
        rc_heap_deallocate(f->locals); rc_heap_deallocate(f);
    }
    rc_bounded_cached_frame_bytes = 0;
#ifdef MINYAR_SYSTEM_HEAP
    assert(!rc_heap_allocation_count);
#else
    assert(!minyar_pool_used);
#endif
}
static void print_result(size_t work, size_t visits, size_t extra, size_t pending) {
    printf("{\"work\":%zu,\"visits\":%zu,\"extra\":%zu,\"pending\":%zu,"
           "\"event_scope\":%d,\"idle\":%d,\"final_bytes\":%zu}\n",
           work, visits, extra, pending, ACCEPTANCE_HAS_EVENT_SCOPE,
           ACCEPTANCE_HAS_IDLE, rc_bytes);
}

static void operations(const char *op, size_t budget) {
    MinyarRecord *s = sentinel(), *old = wide(s, WIDTH);
    MinyarRecord *record = minyar_record_new(CALLS);
    MinyarList *list = minyar_list_new(); minyar_list_references(list);
    for (size_t i = 0; i < CALLS; i++) minyar_list_add(list, (long long)(uintptr_t)s);
    void *created[CALLS] = {0};
    MinyarRecord *leaves[CALLS];
    for (size_t i = 0; i < CALLS; i++) leaves[i] = minyar_record_new_scalar(1);
    minyar_rc_enter(2);
    /* Private rc_drop prepares debt without spending the event's budget. */
    rc_drop(old);
    size_t before = refs(s), start = acceptance_queued_work;
    acceptance_event_begin(budget);
    for (size_t i = 0; i < CALLS; i++) {
        if (!strcmp(op, "poll")) minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
        else if (!strcmp(op, "allocate")) created[i] = minyar_record_new_scalar(1);
        else if (!strcmp(op, "text")) created[i] = copy_c_text("a real allocation");
        else if (!strcmp(op, "record")) created[i] = minyar_record_new(3);
        else if (!strcmp(op, "append")) minyar_list_add(list, (long long)(uintptr_t)s);
        else if (!strcmp(op, "replace")) minyar_list_set(list, 0, (long long)(uintptr_t)s);
        else if (!strcmp(op, "field")) minyar_record_set_reference(record, (long long)i, (long long)(uintptr_t)s);
        else if (!strcmp(op, "local")) minyar_rc_local(0, s);
        else if (!strcmp(op, "borrow")) minyar_rc_borrow(s);
        else if (!strcmp(op, "step")) minyar_rc_step();
        else if (!strcmp(op, "frame")) { minyar_rc_enter(1); minyar_rc_leave(); }
        else if (!strcmp(op, "release")) { minyar_rc_release(leaves[i]); leaves[i] = NULL; }
        else if (!strcmp(op, "stack")) {
            uint64_t header[8], storage[2];
            minyar_rc_enter_stack_v1(header, storage, 1);
            minyar_rc_local(0, s);
            minyar_rc_leave_stack_v1(header);
        } else assert(!"unknown operation");
    }
    acceptance_event_end();
    size_t work = acceptance_queued_work - start;
    if (!strcmp(op, "allocate") || !strcmp(op, "text") || !strcmp(op, "record"))
        for (size_t i = 0; i < CALLS; i++) {
            assert(created[i]);
            if (!strcmp(op, "text")) assert(minyar_text_length(created[i]) == 17);
        }
    if (!strcmp(op, "append")) assert(minyar_list_length(list) == 2 * CALLS);
    for (long long i = 0; i < minyar_list_length(list); i++)
        assert((void *)(uintptr_t)minyar_list_get(list, i) == s);
    if (!strcmp(op, "field"))
        for (size_t i = 0; i < CALLS; i++) assert((void *)(uintptr_t)minyar_record_get(record, (long long)i) == s);
    if (!strcmp(op, "local")) assert(rc_bounded_local_value(rc_frames, 0) == s);
    if (!strcmp(op, "borrow")) assert(rc_frames->temporary_count == CALLS);
    /* Operations can add owners of s. Count the old object's actual cursor
     * instead, independently of the scheduler's reported work. It cannot have
     * finished: WIDTH exceeds all work generated by this finite fixture. */
    size_t visits = 0;
    if (rc_bounded_active == (RcObject *)old - 1) visits = rc_bounded_cursor;
    else {
        unsigned char *map = (unsigned char *)(old->values + old->length);
        for (size_t bit = 0; bit < sizeof(size_t) * CHAR_BIT; bit++)
            if (map[bit / 7] & (1u << (1 + bit % 7))) visits |= (size_t)1 << bit;
    }
    assert(visits <= work);
    if (!strcmp(op, "poll") || !strcmp(op, "allocate") || !strcmp(op, "text") ||
        !strcmp(op, "record") || !strcmp(op, "step") || !strcmp(op, "frame") || !strcmp(op, "release"))
        assert(before - refs(s) == visits);
    size_t pending = rc_pending_count;
    assert(minyar_record_get(s, 0) == 1729);
    minyar_rc_leave();
    for (size_t i = 0; i < CALLS; i++) { minyar_rc_release(created[i]); minyar_rc_release(leaves[i]); }
    minyar_rc_release(record); minyar_rc_release(list);
    finish(s);
    print_result(work, visits, 0, pending);
}

static void scopes(const char *kind, size_t budget) {
    MinyarRecord *s = sentinel(); rc_drop(wide(s, WIDTH));
    size_t start = acceptance_queued_work, before = refs(s), extra = 0;
    acceptance_event_begin(budget);
    if (!strcmp(kind, "nested_tight") || !strcmp(kind, "nested_partial")) {
        if (!strcmp(kind, "nested_partial") && budget) minyar_rc_poll(1);
        size_t inner_start = acceptance_queued_work;
        acceptance_event_begin(!strcmp(kind, "nested_tight") ? budget / 2 : 1024);
        for (size_t i = 0; i < CALLS; i++) minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
        acceptance_event_end();
        extra = acceptance_queued_work - inner_start;
    }
    for (size_t i = 0; i < CALLS; i++) minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
    if (!strcmp(kind, "nested")) {
        acceptance_event_begin(1024);
        for (size_t i = 0; i < CALLS; i++) minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
        acceptance_event_end();
        for (size_t i = 0; i < CALLS; i++) minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
    }
    acceptance_event_end();
    size_t work = acceptance_queued_work - start, visits = before - refs(s);
    assert(visits == work);
    if (!strcmp(kind, "reset")) {
        start = acceptance_queued_work;
        acceptance_event_begin(budget);
        for (size_t i = 0; i < CALLS; i++) minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
        acceptance_event_end();
        extra = acceptance_queued_work - start;
    } else if (!strcmp(kind, "outside")) {
        start = acceptance_queued_work;
        minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
        extra = acceptance_queued_work - start;
    }
    size_t pending = rc_pending_count;
    finish(s); print_result(work, visits, extra, pending);
}

typedef struct { size_t calls, stop; } Ready;
static int ready(void *context) {
    Ready *r = context;
    return r->calls++ >= r->stop;
}
static void idle_case(const char *kind, size_t budget, size_t stop) {
    MinyarRecord *s = sentinel();
    if (strcmp(kind, "empty")) rc_drop(wide(s, WIDTH));
    Ready r = {0, stop};
    size_t start = acceptance_queued_work, before = refs(s);
    if (!strcmp(kind, "inside")) acceptance_event_begin(0);
    size_t returned = acceptance_idle(budget, ready, &r);
    if (!strcmp(kind, "inside")) acceptance_event_end();
    size_t work = acceptance_queued_work - start, visits = before - refs(s);
    assert(work == visits && returned == work);
    size_t pending = rc_pending_count;
    finish(s); print_result(work, visits, r.calls, pending);
}

static void sustained(size_t width, size_t burst) {
    MinyarRecord *s = sentinel();
    size_t stable = rc_bytes, max_debt = 0, failed = 0, total = 0;
    for (size_t cycle = 0; cycle < 128; cycle++) {
        MinyarRecord *roots[16]; assert(burst <= 16);
        for (size_t i = 0; i < burst; i++) roots[i] = wide(s, width);
        acceptance_event_begin(0);
        for (size_t i = 0; i < burst; i++) minyar_rc_release(roots[i]);
        acceptance_event_end();
        if (rc_bytes - stable > max_debt) max_debt = rc_bytes - stable;
        size_t demand = burst * (width + 1), start = acceptance_queued_work;
        Ready r = {0, SIZE_MAX};
        size_t returned = acceptance_idle(demand, ready, &r);
        assert(returned == acceptance_queued_work - start && returned <= demand);
        total += returned;
        if (rc_pending_count || rc_bytes != stable || refs(s) != 1) failed++;
        assert(minyar_record_get(s, 0) == 1729);
        /* Failure must not turn subsequent cases into OOM. This teardown is
         * outside the measured opportunity; failed windows remain failures. */
        while (rc_pending_count) assert(minyar_rc_poll(MINYAR_RC_POLL_BUDGET));
    }
    finish(s); print_result(total, failed, max_debt, 0);
}

static void safety(const char *kind, size_t budget) {
    MinyarRecord *s = sentinel(); size_t before, observed;
    if (!strcmp(kind, "chain") || !strcmp(kind, "dag")) {
        void *root;
        if (!strcmp(kind, "chain")) {
            root = s; minyar_rc_retain(s);
            for (size_t i = 0; i < 16384; i++) {
                MinyarRecord *r = minyar_record_new(1);
                minyar_record_set_take(r, 0, (long long)(uintptr_t)root); root = r;
            }
        } else {
            MinyarRecord *nodes[256];
            MinyarList *list = minyar_list_new(); minyar_list_references(list);
            for (size_t i = 0; i < 256; i++) {
                nodes[i] = minyar_record_new(2);
                minyar_record_set_reference(nodes[i], 0, (long long)(uintptr_t)s);
                if (i) minyar_record_set_reference(nodes[i], 1, (long long)(uintptr_t)nodes[(i * 17 + i / 3 + 3) % i]);
            }
            /* Permutation of every index, deliberately unrelated to edges. */
            for (size_t i = 0; i < 256; i++) minyar_list_add_take(list, (long long)(uintptr_t)nodes[(i * 73) % 256]);
            root = list;
        }
        rc_drop(root);
        while (rc_pending_count) {
            before = rc_object_count;
            size_t work = minyar_rc_poll(budget);
            assert(work && work <= budget && before - rc_object_count <= work);
            assert(minyar_record_get(s, 0) == 1729);
        }
    } else if (!strcmp(kind, "shared")) {
        MinyarRecord *a = wide(s, 127), *b = wide(s, 129);
        rc_drop(a); rc_drop(b);
        while (rc_pending_count) {
            before = refs(s); size_t work = minyar_rc_poll(budget);
            assert(work && work <= budget && before - refs(s) <= work);
            assert(minyar_record_get(s, 0) == 1729);
        }
        assert(refs(s) == 1);
    } else if (!strcmp(kind, "text")) {
        MinyarText *root = copy_c_text("abcdefgh"), *v = minyar_text_slice(root, 1, 7);
        MinyarText *alias = minyar_text_slice(v, 1, 4);
        minyar_rc_release(root); minyar_rc_release(v);
        assert(minyar_text_length(alias) == 3);
        before = rc_object_count;
        minyar_rc_release(alias);
        observed = before - rc_object_count;
        assert(observed <= MINYAR_RC_POLL_BUDGET && observed <= rc_bounded_last_work);
    } else if (!strcmp(kind, "zero_poll")) {
        rc_drop(wide(s, 127)); before = refs(s);
        assert(minyar_rc_poll(0) == 0 && refs(s) == before);
    } else if (!strcmp(kind, "stack")) {
        uint64_t header[8], storage[16];
        minyar_rc_enter_stack_v1(header, storage, 8);
        for (size_t i = 0; i < 8; i++) minyar_rc_local((long long)i, s);
        minyar_rc_leave_stack_v1(header);
        /* The stack storage dies here; overwrite it to expose queued aliases. */
        memset(header, 0xa5, sizeof(header)); memset(storage, 0xa5, sizeof(storage));
    } else assert(!"unknown safety case");
    finish(s); print_result(0, 0, 0, 0);
}

int main(int argc, char **argv) {
    assert(argc == 5);
    size_t budget = (size_t)strtoull(argv[3], NULL, 10), extra = (size_t)strtoull(argv[4], NULL, 10);
    if (!strcmp(argv[1], "operation")) operations(argv[2], budget);
    else if (!strcmp(argv[1], "scope")) scopes(argv[2], budget);
    else if (!strcmp(argv[1], "idle")) idle_case(argv[2], budget, extra);
    else if (!strcmp(argv[1], "sustained")) sustained(budget, extra);
    else if (!strcmp(argv[1], "safety")) safety(argv[2], budget);
    else if (!strcmp(argv[1], "capability")) print_result(0, 0, 0, 0);
    else return 2;
}
