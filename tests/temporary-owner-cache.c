/* Physical reuse and exact cleanup work, not a timing or RSS benchmark.
 * The runner instruments only copied poll and backing-allocation definitions. */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE 1
#endif
#define MINYAR_RC_TESTING 1
#define MINYAR_INTEGER_TEXT_CACHE_LIMIT 0
#include <stddef.h>
#ifdef MINYAR_SYSTEM_HEAP
/* Declared before the included engine so its copied allocator can record
 * cumulative events. Live allocation counts cannot detect alloc/free churn.
 * Match numeric-domain isolation even if this fixture gains real workers. */
static _Thread_local size_t observed_heap_allocation_events;
#endif
static size_t observed_calls, observed_work;
/* Direct frame exit and statement cleanup replace one poll call. */
#define MINYAR_RC_DIRECT_SERVICE_OBSERVER(work) (observed_calls++, observed_work += (work))
#include MINYAR_RUNTIME_SOURCE
#include <assert.h>

static RcObject immortal = { RC_TEXT };
size_t minyar_rc_poll(size_t budget) {
    size_t work = cache_probe_poll_impl(budget);
    assert(work <= budget && work <= MINYAR_RC_POLL_BUDGET);
    observed_calls++;
    observed_work += work;
    return work;
}
static void drain(void) {
    size_t calls = 0;
    while (rc_pending_count) {
        assert(++calls < 100000);
        assert(minyar_rc_poll(SIZE_MAX) > 0);
    }
}
static size_t allocation_counter(void) {
#ifdef MINYAR_SYSTEM_HEAP
    return observed_heap_allocation_events;
#else
    return minyar_pool_allocation_count;
#endif
}
static void assert_allocation_events(size_t expected) {
    size_t actual = allocation_counter();
    assert(actual == expected && "temporary-owner allocation-event oracle");
}
static size_t frame_charge(RcFrame *frame) {
    size_t bytes = rc_heap_charge(frame, sizeof(*frame));
    if (frame->locals)
        bytes += rc_heap_charge(frame->locals, frame->local_capacity * (sizeof(void *) + sizeof(size_t)));
    return bytes;
}
static void account_cache(void) {
    size_t bytes = 0;
    for (RcFrame *frame = rc_free_frames; frame; frame = frame->previous)
        bytes += frame_charge(frame);
    if (rc_bounded_cached_chunk) {
        assert(!rc_bounded_cached_chunk->count && !rc_bounded_cached_chunk->next);
        bytes += rc_heap_charge(rc_bounded_cached_chunk, sizeof(*rc_bounded_cached_chunk));
        for (RcTemporaryChunk *chunk = rc_bounded_chunk_head; chunk; chunk = chunk->next)
            assert(chunk != rc_bounded_cached_chunk);
        for (RcFrame *frame = rc_frames; frame; frame = frame->previous)
            for (RcTemporaryChunk *chunk = frame->temporary_head; chunk; chunk = chunk->next)
                assert(chunk != rc_bounded_cached_chunk);
    }
    assert(bytes == rc_bounded_cached_frame_bytes && bytes <= MINYAR_FRAME_CACHE_BYTES);
}
static void clear_frames(void) {
    while (rc_free_frames) {
        RcFrame *frame = rc_free_frames;
        rc_free_frames = frame->previous;
        rc_bounded_cached_frame_bytes -= frame_charge(frame);
        rc_heap_deallocate(frame->locals);
        rc_heap_deallocate(frame);
    }
}
static void recover(void) {
    drain();
    assert(!rc_frames && !rc_scopes && !rc_object_count && !rc_bytes);
    assert(!rc_bounded_frame_head && !rc_bounded_frame_tail);
    assert(!rc_bounded_chunk_head && !rc_bounded_chunk_tail);
    assert(!rc_bounded_active && !rc_bounded_head && !rc_bounded_recent_head);
    account_cache();
    clear_frames();
    rc_bounded_chunk_cache_clear();
    assert(!rc_bounded_cached_chunk && !rc_bounded_cached_frame_bytes);
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
    assert(!rc_cycle_head && !rc_cycle_known_head && !rc_cycle_pending);
#endif
#ifdef MINYAR_SYSTEM_HEAP
    assert(!rc_heap_allocation_count);
#else
    assert(!minyar_pool_used);
    void *whole = minyar_pool_try_allocate(MINYAR_POOL_BYTES);
    assert(whole == minyar_pool);
    minyar_pool_deallocate(whole);
    assert(!minyar_pool_used);
#endif
}
static MinyarRecord *shared_value(void) {
    MinyarRecord *shared = minyar_record_new_scalar(1);
    minyar_record_set(shared, 0, 73);
    return shared;
}
static void finish(MinyarRecord *shared) {
    minyar_rc_leave();
    drain();
    assert(((RcObject *)shared - 1)->ownership == (8 | RC_SCALAR_RECORD));
    assert(shared->values[0] == 73);
    minyar_rc_release(shared);
    recover();
}
static void exact_retirement_and_reuse(void) {
    recover();
    minyar_rc_enter(0);
    MinyarRecord *shared = shared_value();
    for (unsigned i = 0; i < RC_TEMPORARY_CHUNK_SLOTS; i++) minyar_rc_borrow(shared);
    RcTemporaryChunk *first = rc_frames->temporary_head;
    size_t bytes = rc_heap_charge(first, sizeof(*first));
    rc_bounded_retire_temporaries(rc_frames);
    observed_work = observed_calls = 0;
    for (unsigned i = 0; i < RC_TEMPORARY_CHUNK_SLOTS; i++) {
        assert(minyar_rc_poll(1) == 1);
        assert(rc_bounded_chunk_head == first && first->count == RC_TEMPORARY_CHUNK_SLOTS - i - 1);
        assert(!rc_bounded_cached_chunk && rc_pending_count == 1);
    }
    /* Even a zero-owner chunk remains pending until a separate ninth unit. */
    assert(observed_work == RC_TEMPORARY_CHUNK_SLOTS);
    assert(minyar_rc_poll(1) == 1 && !rc_pending_count);
    assert(observed_work == RC_TEMPORARY_CHUNK_SLOTS + 1);
    int admitted = bytes <= MINYAR_FRAME_CACHE_BYTES;
    assert((rc_bounded_cached_chunk != NULL) == admitted);
    if (admitted) assert(rc_bounded_cached_chunk == first);
    account_cache();
    size_t allocations = allocation_counter();
    minyar_rc_borrow(shared);
    assert_allocation_events(allocations + !admitted);
    assert(!rc_bounded_cached_chunk && !rc_bounded_cached_frame_bytes);
    if (admitted) assert(rc_frames->temporary_head == first);
    assert(rc_frames->temporary_head->count == 1 && rc_frames->temporary_head->next == NULL);
    finish(shared);
    puts("eight owner visits and separate finalization; actual reuse and alias recovery passed");
}
static void keep_service(void) {
    recover();
    minyar_rc_enter(0);
    MinyarRecord *shared = shared_value();
    minyar_rc_borrow(shared);
    minyar_rc_step();
    drain();
    RcTemporaryChunk *cached = rc_bounded_cached_chunk;
    /* Scalar fields keep the same object ready through all three batches. A
     * record unit examines eight fields, so a debt worth four K units holds
     * four K unit-batches of fields. */
    MinyarRecord *debt = minyar_record_new(4 * MINYAR_RC_POLL_BUDGET * 8 + 5);
    rc_drop(debt);
    observed_calls = observed_work = 0;
    size_t allocations = allocation_counter();
    minyar_rc_borrow(shared);
    assert(observed_calls == 2 && observed_work == 2 * MINYAR_RC_POLL_BUDGET);
    assert_allocation_events(allocations + (cached == NULL));
    if (cached) assert(rc_frames->temporary_tail == cached);
    observed_calls = observed_work = 0;
    minyar_rc_borrow(shared);
    assert(observed_calls == 1 && observed_work == MINYAR_RC_POLL_BUDGET);
    observed_calls = observed_work = 0;
    minyar_rc_keep(NULL);
    minyar_rc_keep(&immortal + 1);
    minyar_rc_borrow(NULL);
    minyar_rc_borrow(&immortal + 1);
    assert(!observed_calls && !observed_work);
    finish(shared);
    puts("cache hit/miss keeps preserve both K batches; existing/null/immortal keep limits passed");
}
static void one_chunk_and_shared_cap(void) {
    recover();
    minyar_rc_enter(0);
    MinyarRecord *shared = shared_value();
    for (unsigned i = 0; i < 17; i++) minyar_rc_borrow(shared);
    RcTemporaryChunk *first = rc_frames->temporary_head;
    size_t chunk_bytes = rc_heap_charge(first, sizeof(*first));
    observed_work = 0;
    minyar_rc_step();
    drain();
    assert(observed_work == 17 + 3); /* Three chunks, not one batched task. */
    if (chunk_bytes <= MINYAR_FRAME_CACHE_BYTES) assert(rc_bounded_cached_chunk == first);
    else assert(!rc_bounded_cached_chunk);
    assert(((RcObject *)shared - 1)->ownership == (8 | RC_SCALAR_RECORD));
    account_cache();
    finish(shared);

    minyar_rc_enter(0);
    minyar_rc_enter(0);
    minyar_rc_leave();
    drain();
    size_t frame_bytes = rc_bounded_cached_frame_bytes;
    shared = shared_value();
    minyar_rc_borrow(shared);
    RcTemporaryChunk *chunk = rc_frames->temporary_head;
    chunk_bytes = rc_heap_charge(chunk, sizeof(*chunk));
    minyar_rc_step();
    drain();
    int room = chunk_bytes <= MINYAR_FRAME_CACHE_BYTES &&
               frame_bytes <= MINYAR_FRAME_CACHE_BYTES - chunk_bytes;
    assert((rc_bounded_cached_chunk != NULL) == room);
    if (room) assert(rc_bounded_cached_chunk == chunk);
    assert(rc_bounded_cached_frame_bytes == frame_bytes + (room ? chunk_bytes : 0));
    account_cache();
    finish(shared);
    puts("one cached chunk shares exact zero/too-small/full frame cap boundaries");
}
static void no_early_k1_reuse(void) {
#if MINYAR_RC_POLL_BUDGET == 1
    recover();
    minyar_rc_enter(0);
    MinyarRecord *shared = shared_value();
    for (unsigned i = 0; i < 8; i++) minyar_rc_borrow(shared);
    RcTemporaryChunk *retiring = rc_frames->temporary_head;
    minyar_rc_step();
    assert(rc_bounded_chunk_head == retiring && retiring->count == 7 && !rc_bounded_cached_chunk);
    minyar_rc_borrow(shared); /* Its two polls cannot finish the old chunk. */
    assert(rc_frames->temporary_head != retiring && retiring->count == 5);
    assert(!rc_bounded_cached_chunk);
    drain();
    assert(((RcObject *)shared - 1)->ownership >> 3 == 2);
    assert(rc_frames->temporary_head->values[0] == shared && shared->values[0] == 73);
    finish(shared);
    puts("K1 never reuses pending storage while another chunk still owns its alias");
#endif
}
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
static void active_cycles(void) {
    recover();
    MinyarRecord *root = minyar_record_new_traced(2);
    MinyarRecord *child = minyar_record_new_traced(2);
    minyar_record_set_traced(root, 1, 73);
    minyar_record_set_traced(child, 1, 91);
    minyar_record_set_reference_traced(root, 0, (long long)(uintptr_t)child);
    minyar_record_set_reference_traced(child, 0, (long long)(uintptr_t)root);
    rc_drop(child);
    drain();
    minyar_rc_enter(0);
    for (unsigned phase = RC_CYCLE_ROOTS; phase <= RC_CYCLE_SWEEP; phase++) {
        minyar_rc_borrow_traced(child);
        minyar_rc_step();
        drain();
        RcTemporaryChunk *cached = rc_bounded_cached_chunk;
        minyar_rc_borrow_traced(child);
        if (cached) assert(rc_frames->temporary_head == cached);
        rc_cycle_request(); /* Requests a full rescan, not an idle proof hit. */
        size_t turns = 0;
        while (rc_cycle_phase != phase) {
            assert(++turns < 100000);
            assert(minyar_rc_poll(1) == 1);
        }
        rc_bounded_retire_temporaries(rc_frames);
        rc_bounded_next_queue = 2;
        size_t cycle_units = rc_cycle_units;
        assert(minyar_rc_poll(1) == 1 && rc_cycle_units == cycle_units);
        assert(root->values[0] == (long long)(uintptr_t)child && root->values[1] == 73);
        assert(child->values[0] == (long long)(uintptr_t)root && child->values[1] == 91);
        drain();
        account_cache();
    }
    minyar_rc_leave();
    drain();
    rc_drop(root);
    drain();
    recover();
    puts("reused chunks retain traced barriers in genuine ROOTS/MARK/SWEEP phases");
}
#endif
#if MINYAR_THREADED
static void leave_cached_chunk(void) {
    minyar_rc_enter(0);
    minyar_rc_keep(minyar_record_new_scalar(1));
    minyar_rc_leave();
    drain();
    clear_frames();
    assert(!rc_frames && !rc_free_frames && !rc_pending_count && !rc_object_count && !rc_bytes);
    assert(rc_bounded_cached_chunk && rc_bounded_cached_frame_bytes);
}
#endif
int main(int argc, char **argv) {
#if MINYAR_THREADED
    rc_thread_domain_init();
    if (argc == 2 && !strcmp(argv[1], "residual")) {
        leave_cached_chunk();
        rc_thread_domain_init(); /* Must reject cache-only residual state. */
        return 99;
    }
#else
    (void)argv;
#endif
    assert(argc == 1);
    exact_retirement_and_reuse();
    keep_service();
    one_chunk_and_shared_cap();
    no_early_k1_reuse();
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
    active_cycles();
#endif
#if MINYAR_THREADED
    leave_cached_chunk();
    rc_thread_domain_dispose();
    assert(!rc_bounded_cached_chunk && !rc_bounded_cached_frame_bytes && !rc_heap_allocation_count);
    puts("numeric-domain disposal frees finalized storage; residual-state initialization rejects");
#endif
    recover();
    puts("temporary owner cache: all ownership/work/backing invariants passed");
    return 0;
}
