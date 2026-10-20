/* Direct public-entry probes; compile against ordinary or generated cycle C. */
#define MINYAR_RC_TESTING 1
#define MINYAR_INTEGER_TEXT_CACHE_LIMIT 0
#ifndef MINYAR_PUBLIC_RELEASE_ENGINE
#define MINYAR_PUBLIC_RELEASE_ENGINE "minyar_runtime.c"
#endif
#include MINYAR_PUBLIC_RELEASE_ENGINE
#include <assert.h>

static const struct {
    size_t ownership;
    unsigned char payload[8];
} immortal = {RC_TEXT, {0}};

static void empty_heap(void) {
    assert(rc_pending_count == 0);
    assert(rc_object_count == 0 && rc_bytes == 0 && rc_immortal_object_count == 0);
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
    assert(!rc_cycle_pending && !rc_cycle_head && !rc_cycle_known_head);
#endif
}

#ifndef MINYAR_BOUNDED_RC
static void queue_ordinary(void) {
    MinyarRecord *queued = rc_allocate_object(sizeof(*queued), RC_RECORD);
    queued->length = 0;
    rc_drop(queued); /* Inject debt without servicing it through public release. */
    assert(rc_pending_count == 1);
}

static void eager_release_paths(void) {
    minyar_rc_release(NULL);
    minyar_rc_release((void *)immortal.payload);
    assert(immortal.ownership == RC_TEXT);
    MinyarRecord *shared = minyar_record_new_scalar(0);
    minyar_rc_retain(shared);
    size_t ownership = ((RcObject *)shared - 1)->ownership;
    size_t bytes = rc_bytes;
    minyar_rc_release(shared);
    assert(((RcObject *)shared - 1)->ownership == ownership - 8);
    assert(rc_object_count == 1 && rc_bytes == bytes);
    minyar_rc_release(shared); /* Last leaf owner must reach destruction. */
    empty_heap();

    /* Each request independently starts with debt; a later drain cannot hide
     * a shared/immortal/NULL entry that silently skipped its service point. */
    for (unsigned request = 0; request < 4; request++) {
        shared = minyar_record_new_scalar(0);
        if (request == 1) minyar_rc_retain(shared);
        queue_ordinary();
        assert(rc_object_count == 2);
        minyar_rc_scope_release_v1(NULL);
        assert(rc_pending_count == 1 && rc_object_count == 2);
        if (request == 0) {
            /* Taking its address also requires the ordinary external ABI. */
            void (*volatile release_entry)(void *) = minyar_rc_release;
            release_entry(NULL);
        } else if (request == 1) {
            minyar_rc_release(shared);
            assert(((RcObject *)shared - 1)->ownership == (8 | RC_SCALAR_RECORD));
        } else if (request == 2) {
            minyar_rc_release((void *)immortal.payload);
            assert(immortal.ownership == RC_TEXT);
        } else {
            minyar_rc_release(shared);
        }
        assert(rc_pending_count == 0);
        assert(rc_object_count == (request == 3 ? 0u : 1u));
        if (request != 3) minyar_rc_release(shared);
        empty_heap();
    }
}

#ifdef MINYAR_CYCLE_LOCAL_PROOFS
static void eager_cycle_paths(void) {
    /* With no prior debt, dropping this shared traced count creates work.
     * Treating it as an ordinary shared decrement leaks the self-cycle. */
    MinyarRecord *node = minyar_record_new_traced(1);
    minyar_record_set_reference_traced(node, 0, (long long)(uintptr_t)node);
    minyar_rc_release(NULL);
    assert(!rc_cycle_pending && !rc_pending_count && rc_object_count == 1);
    minyar_rc_release(node);
    empty_heap();

    MinyarRecord *shared = minyar_record_new_scalar(0);
    minyar_rc_retain(shared);
    MinyarList *cycle = minyar_list_new_traced();
    minyar_list_references(cycle);
    for (size_t i = 0; i < 512; i++)
        minyar_list_add_traced(cycle, (long long)(uintptr_t)cycle);
    minyar_rc_release(NULL); /* Establish an idle, externally held cohort. */
    assert(!rc_cycle_pending && !rc_pending_count);
    rc_drop(cycle); /* Leave more than 32 units of cycle-only debt. */
    assert(rc_cycle_pending && !rc_pending_count);
    size_t before = rc_cycle_units;
    minyar_rc_release(shared);
    assert(rc_cycle_units - before == 32 && rc_cycle_pending);
    assert(((RcObject *)shared - 1)->ownership == (8 | RC_SCALAR_RECORD));
    before = rc_cycle_units;
    minyar_rc_release((void *)immortal.payload);
    assert(rc_cycle_units - before == 32 && rc_cycle_pending);
    assert(immortal.ownership == RC_TEXT);
    before = rc_cycle_units;
    minyar_rc_scope_release_v1(NULL);
    assert(rc_cycle_units == before && rc_cycle_pending);
    minyar_rc_release(NULL);
    assert(rc_cycle_units - before > 32);
    assert(!rc_cycle_pending && !rc_pending_count && rc_object_count == 1);
    minyar_rc_release(shared);
    empty_heap();
}
#endif
#else
static void bounded_release_paths(void) {
    MinyarRecord *shared = minyar_record_new_scalar(1);
    minyar_record_set_scalar(shared, 0, 42);
    minyar_rc_retain(shared);
    rc_bounded_last_work = MINYAR_RC_POLL_BUDGET;
    minyar_rc_release(shared);
    assert(rc_bounded_last_work == 0);
    assert(((RcObject *)shared - 1)->ownership == (8 | RC_SCALAR_RECORD));
    rc_bounded_last_work = MINYAR_RC_POLL_BUDGET;
    minyar_rc_release((void *)immortal.payload);
    assert(rc_bounded_last_work == 0 && immortal.ownership == RC_TEXT);
    rc_bounded_last_work = MINYAR_RC_POLL_BUDGET;
    minyar_rc_scope_release_v1(NULL);
    assert(rc_bounded_last_work == MINYAR_RC_POLL_BUDGET);
    minyar_rc_release(NULL);
    assert(rc_bounded_last_work == 0);
    minyar_rc_release(shared);
    assert(rc_bounded_last_work == 1);
    empty_heap();

    shared = minyar_record_new_scalar(1);
    minyar_rc_retain(shared);
    MinyarRecord *chain = NULL;
    for (size_t i = 0; i < 160; i++) {
        MinyarRecord *next = minyar_record_new(1);
        minyar_record_set_take(next, 0, (long long)(uintptr_t)chain);
        chain = next;
    }
    rc_drop(chain);
    assert(rc_pending_count == 1);
    minyar_rc_release((void *)immortal.payload);
    assert(rc_bounded_last_work == MINYAR_RC_POLL_BUDGET);
    assert(immortal.ownership == RC_TEXT);
    printf("immortal %zu %zu %zu\n", rc_bounded_last_work, rc_pending_count, rc_object_count);
    minyar_rc_release(shared);
    assert(rc_bounded_last_work == MINYAR_RC_POLL_BUDGET);
    assert(((RcObject *)shared - 1)->ownership == (8 | RC_SCALAR_RECORD));
    printf("shared %zu %zu %zu\n", rc_bounded_last_work, rc_pending_count, rc_object_count);
    size_t pending = rc_pending_count, work = rc_bounded_last_work;
    minyar_rc_scope_release_v1(NULL);
    assert(rc_pending_count == pending && rc_bounded_last_work == work);
    minyar_rc_release(NULL);
    assert(rc_bounded_last_work == MINYAR_RC_POLL_BUDGET);
    printf("null %zu %zu %zu\n", rc_bounded_last_work, rc_pending_count, rc_object_count);
    minyar_rc_release(shared);
    assert(rc_bounded_last_work == MINYAR_RC_POLL_BUDGET);
    printf("last %zu %zu %zu\n", rc_bounded_last_work, rc_pending_count, rc_object_count);
    size_t batches = 0;
    while (rc_pending_count) {
        assert(++batches < 10000);
        size_t serviced = minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
        assert(serviced > 0 && serviced <= MINYAR_RC_POLL_BUDGET);
        assert(rc_bounded_last_work == serviced);
    }
    empty_heap();
#ifdef MINYAR_SYSTEM_HEAP
    assert(rc_heap_allocation_count == 0);
#else
    assert(minyar_pool_used == 0);
    assert(minyar_pool_mask == ((size_t)1 << minyar_pool_max_order));
    assert(minyar_pool_free[minyar_pool_max_order] == (PoolLink *)minyar_pool);
#endif
}
#endif

int main(void) {
#ifdef MINYAR_BOUNDED_RC
    bounded_release_paths();
#else
    eager_release_paths();
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
    eager_cycle_paths();
#endif
#endif
    empty_heap();
    puts("public release accounting passed");
    return 0;
}
