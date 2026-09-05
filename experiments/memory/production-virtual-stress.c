/* TEST-ONLY shuffled lifetimes and sparse-address checks for lazy VM backing.
 * No timing assertions, no graph scanner, no whole-arena allocation under ASan.
 * Compile with MINYAR_RUNTIME_SOURCE naming an isolated candidate runtime.
 * Optional MINYAR_BOUNDED_HEAP_BYTES=(1ULL<<40) exercises wide native offsets.
 * RSS observations are descriptive: OS compression/eviction can change them.
 * Default debt assertions are TDD requirements for bounded retained growth.
 * MINYAR_EXPECT_CLEANUP_DEBT instead verifies earlier counterexamples. */
#define MINYAR_BOUNDED_HEAP 1
#define MINYAR_LAZY_HEAP 1
#define MINYAR_RC_TESTING 1
#ifndef MINYAR_BOUNDED_HEAP_BYTES
#define MINYAR_BOUNDED_HEAP_BYTES (64u * 1024u * 1024u)
#endif
#ifndef MINYAR_RUNTIME_SOURCE
#define MINYAR_RUNTIME_SOURCE "../../runtime/minyar_runtime.c"
#endif
#include MINYAR_RUNTIME_SOURCE
#include <assert.h>
#ifdef __APPLE__
#include <mach/mach.h>
#endif
#ifndef MINYAR_POOL_BYTES
#define MINYAR_POOL_BYTES sizeof(minyar_pool)
#define MINYAR_POOL_MAP_BYTES sizeof(minyar_pool_map)
#endif

static size_t rss(void) {
#ifdef __APPLE__
    mach_task_basic_info_data_t info;
    mach_msg_type_number_t count = MACH_TASK_BASIC_INFO_COUNT;
    assert(task_info(mach_task_self(), MACH_TASK_BASIC_INFO, (task_info_t)&info, &count) == KERN_SUCCESS);
    return (size_t)info.resident_size;
#else
    return 0; /* Correctness tests remain usable; no invented RSS measurement. */
#endif
}

static unsigned word(unsigned *state) {
    *state = *state * 1664525u + 1013904223u;
    return *state;
}

static void recovered(void) {
    assert(minyar_pool_used == 0);
    assert(minyar_pool_mask == ((size_t)1 << minyar_pool_max_order));
    assert(minyar_pool_free[minyar_pool_max_order] == (PoolLink *)minyar_pool);
    assert(minyar_pool_map[0] == minyar_pool_max_order + 1);
}

static size_t shuffled_lifetimes(void) {
    enum { SLOTS = 96, ROUNDS = 24 };
    unsigned random = 719817;
    size_t observed_peak = rss();
    for (size_t round = 0; round < ROUNDS; round++) {
        unsigned char *blocks[SLOTS];
        size_t sizes[SLOTS], order[SLOTS];
        for (size_t i = 0; i < SLOTS; i++) {
            sizes[i] = 1 + (word(&random) >> 8) % 65536;
            blocks[i] = minyar_pool_allocate(sizes[i]);
            memset(blocks[i], (unsigned char)(i + round), sizes[i]);
            order[i] = i;
            for (size_t j = 0; j < i; j++) {
                uintptr_t a = (uintptr_t)blocks[i], b = (uintptr_t)blocks[j];
                assert(a + sizes[i] <= b || b + sizes[j] <= a);
            }
        }
        size_t current = rss();
        if (current > observed_peak) observed_peak = current;
        for (size_t i = SLOTS - 1; i > 0; i--) {
            size_t j = word(&random) % (i + 1), saved = order[i];
            order[i] = order[j]; order[j] = saved;
        }
        for (size_t i = 0; i < SLOTS; i++) {
            size_t slot = order[i];
            for (size_t j = 0; j < sizes[slot]; j++)
                assert(blocks[slot][j] == (unsigned char)(slot + round));
            minyar_pool_deallocate(blocks[slot]);
        }
        recovered();
    }
    return observed_peak;
}

static void wide_offsets(void) {
#ifndef MINYAR_POOL_ASAN
    /* Reserving a logically large block is cheap in native lazy mode, but ASan
     * deliberately poisons the allocated span. Never run this giant-span probe
     * under instrumentation: it would commit a proportional shadow region. */
    if (MINYAR_POOL_BYTES >= ((size_t)1 << 40)) {
        size_t large = (size_t)1 << 38;
        unsigned char *low = minyar_pool_allocate(large);
        unsigned char *high = minyar_pool_allocate(32);
        assert(pool_offset(high) >= large);
        assert(pool_offset(high) / MINYAR_POOL_MINIMUM > UINT32_MAX);
        low[0] = 17; low[large - 1] = 19; high[0] = 23; high[31] = 29;
        assert(low[0] == 17 && low[large - 1] == 19 && high[0] == 23 && high[31] == 29);
        minyar_pool_deallocate(low);
        assert(high[0] == 23 && high[31] == 29);
        minyar_pool_deallocate(high);
        recovered();
    }
#endif
}

static void repeated_graph_debt(size_t *peak_objects, size_t *remaining_objects) {
    enum { WIDTH = 2048, ROUNDS = 24, SURVIVORS = 8 };
    MinyarRecord *survivors[SURVIVORS] = {0};
    *peak_objects = 0;
    for (size_t round = 0; round < ROUNDS; round++) {
        MinyarList *list = minyar_list_new();
        minyar_list_references(list);
        for (size_t i = 0; i < WIDTH; i++) {
            MinyarRecord *leaf = minyar_record_new_scalar(1);
            minyar_record_set(leaf, 0, (long long)(round * WIDTH + i));
            minyar_list_add_take(list, (long long)(uintptr_t)leaf);
            if (rc_object_count > *peak_objects) *peak_objects = rc_object_count;
        }
        size_t slot = round % SURVIVORS, index = (round * 97) % WIDTH;
        MinyarRecord *saved = (MinyarRecord *)(uintptr_t)minyar_list_get(list, (long long)index);
        minyar_rc_retain(saved);
        minyar_rc_release(survivors[slot]);
        survivors[slot] = saved;
        minyar_rc_release(list);
        assert(saved->values[0] == (long long)(round * WIDTH + index));
        /* There is deliberately no extra drain between lifetimes: allocation
         * and release must service cleanup at the configured production rate. */
    }
    *remaining_objects = rc_object_count;
    if (MINYAR_RC_POLL_BUDGET == 1) {
#ifdef MINYAR_EXPECT_CLEANUP_DEBT
        assert(*remaining_objects > WIDTH * ROUNDS / 4);
#else
        assert(*peak_objects <= 3 * WIDTH + SURVIVORS);
#endif
    }
    if (MINYAR_RC_POLL_BUDGET >= 4)
        assert(*peak_objects <= 3 * WIDTH + SURVIVORS);
    for (size_t i = 0; i < SURVIVORS; i++) minyar_rc_release(survivors[i]);
    while (rc_pending_count) assert(minyar_rc_poll(32) > 0);
    assert(!rc_object_count && !rc_bytes);
    recovered();
}

static size_t repeated_shared_edge_debt(void) {
    enum { WIDTH = 8191, ROUNDS = 96 };
    MinyarRecord *shared = minyar_record_new_scalar(1);
    minyar_record_set(shared, 0, 4242);
    for (size_t round = 0; round < ROUNDS; round++) {
        MinyarList *list = minyar_list_new();
        minyar_list_references(list);
        for (size_t i = 0; i < WIDTH; i++)
            minyar_list_add(list, (long long)(uintptr_t)shared);
        minyar_rc_release(list);
        assert(shared->values[0] == 4242);
    }
    size_t retained = rc_bytes;
    /* Creating many edges to one existing value provides only logarithmically
     * many buffer-growth polls. The default budget cannot keep up here. */
#ifdef MINYAR_EXPECT_CLEANUP_DEBT
    if (MINYAR_RC_POLL_BUDGET <= 32)
        assert(retained > (size_t)WIDTH * sizeof(long long) * ROUNDS / 2);
#else
    assert(retained <= (size_t)WIDTH * sizeof(long long) * 4);
#endif
    minyar_rc_release(shared);
    while (rc_pending_count) assert(minyar_rc_poll(32) > 0);
    assert(!rc_object_count && !rc_bytes);
    recovered();
    return retained;
}

static size_t unassigned_frame_debt(void) {
    enum { SLOTS = 4096, ROUNDS = 96 };
    for (size_t i = 0; i < ROUNDS; i++) {
        minyar_rc_enter(SLOTS);
        minyar_rc_leave();
    }
    assert(!rc_frames && !rc_object_count && !rc_bytes);
    size_t retained = minyar_pool_used;
    size_t one_frame = SLOTS * sizeof(void *) + sizeof(RcFrame);
#ifdef MINYAR_EXPECT_CLEANUP_DEBT
    assert(retained > one_frame * 8);
#else
    assert(retained <= one_frame * 4);
#endif
    while (rc_pending_count) assert(minyar_rc_poll(32) > 0);
    /* Reusable frames are an intentional cache, released in this oracle only. */
    while (rc_free_frames) {
        RcFrame *frame = rc_free_frames;
        rc_free_frames = frame->previous;
        minyar_pool_deallocate(frame->locals);
        minyar_pool_deallocate(frame);
    }
#ifdef MINYAR_BOUNDED_TRACKED_LOCALS
    rc_bounded_cached_frame_bytes = 0;
#endif
    recovered();
    return retained;
}

static size_t mixed_record_debt(void) {
    enum { WIDTH = 4096, ROUNDS = 96 };
    MinyarRecord *shared = minyar_record_new_scalar(1);
    minyar_record_set(shared, 0, 6161);
    for (size_t round = 0; round < ROUNDS; round++) {
        MinyarRecord *value = minyar_record_new(WIDTH);
        minyar_record_set_reference(value, 0, (long long)(uintptr_t)shared);
        for (size_t i = 1; i < WIDTH; i++) minyar_record_set(value, (long long)i, (long long)i);
        minyar_rc_release(value);
        assert(shared->values[0] == 6161);
    }
    size_t retained = rc_bytes;
#ifdef MINYAR_EXPECT_CLEANUP_DEBT
    if (MINYAR_RC_POLL_BUDGET <= 32)
        assert(retained > (size_t)WIDTH * 9 * ROUNDS / 2);
#else
    assert(retained <= (size_t)WIDTH * 9 * 4);
#endif
    minyar_rc_release(shared);
    while (rc_pending_count) assert(minyar_rc_poll(32) > 0);
    assert(!rc_object_count && !rc_bytes);
    recovered();
    return retained;
}

static size_t rotating_frame_cache(void) {
    enum { DEPTH = 16, LARGE_SLOTS = 16384 };
    for (size_t large_depth = 0; large_depth < DEPTH; large_depth++) {
        for (size_t depth = 0; depth < DEPTH; depth++)
            minyar_rc_enter(depth == large_depth ? LARGE_SLOTS : 1);
        for (size_t depth = 0; depth < DEPTH; depth++) minyar_rc_leave();
        /* Intentionally drain all pending obligations: any residual growth is
         * cache policy, independent of cleanup service or its byte credits. */
        while (rc_pending_count) assert(minyar_rc_poll(32) > 0);
        assert(!rc_frames && !rc_object_count && !rc_bytes);
    }
    size_t retained = minyar_pool_used;
    size_t maximum_live_stack = LARGE_SLOTS * sizeof(void *)
                              + DEPTH * (sizeof(RcFrame) + sizeof(void *));
#ifdef MINYAR_EXPECT_CLEANUP_DEBT
    assert(retained > maximum_live_stack * 8);
#else
    assert(retained <= maximum_live_stack * 4);
#endif
    while (rc_free_frames) {
        RcFrame *frame = rc_free_frames;
        rc_free_frames = frame->previous;
        minyar_pool_deallocate(frame->locals);
        minyar_pool_deallocate(frame);
    }
#ifdef MINYAR_BOUNDED_TRACKED_LOCALS
    rc_bounded_cached_frame_bytes = 0;
#endif
    recovered();
    return retained;
}

static size_t temporary_owner_debt(void) {
    enum { OWNERS = 8192, ROUNDS = 24 };
    MinyarRecord *shared = minyar_record_new_scalar(1);
    minyar_record_set(shared, 0, 9191);
    minyar_rc_enter(0);
    for (size_t round = 0; round < ROUNDS; round++) {
        for (size_t i = 0; i < OWNERS; i++) minyar_rc_borrow(shared);
        minyar_rc_step();
        assert(shared->values[0] == 9191);
    }
    size_t retained = minyar_pool_used;
#ifdef MINYAR_EXPECT_CLEANUP_DEBT
    if (MINYAR_RC_POLL_BUDGET <= 32) assert(retained > (size_t)OWNERS * 16 * 8);
#else
    assert(retained <= (size_t)OWNERS * 16 * 4);
#endif
    minyar_rc_leave();
    minyar_rc_release(shared);
    while (rc_pending_count) assert(minyar_rc_poll(32) > 0);
    assert(!rc_object_count && !rc_bytes);
    while (rc_free_frames) {
        RcFrame *frame = rc_free_frames;
        rc_free_frames = frame->previous;
        minyar_pool_deallocate(frame->locals);
        minyar_pool_deallocate(frame);
    }
#ifdef MINYAR_BOUNDED_TRACKED_LOCALS
    rc_bounded_cached_frame_bytes = 0;
#endif
    recovered();
    return retained;
}

static size_t variable_size_hostage(int wrapped) {
    enum { EDGES = 65535, ROUNDS = 16 };
    const long long length = (1LL << 20) - 9; /* buffer + data header = 1 MiB */
    MinyarRecord *shared = minyar_record_new_scalar(1);
    minyar_record_set(shared, 0, 5151);
    MinyarList *wide = minyar_list_new();
    minyar_list_references(wide);
    for (size_t i = 0; i < EDGES; i++) minyar_list_add(wide, (long long)(uintptr_t)shared);
    minyar_rc_release(wide);
    minyar_rc_release(shared);
    for (size_t i = 0; i < ROUNDS; i++) {
        unsigned char *bytes = new_bytes(length);
        memset(bytes, 'x', (size_t)length);
        bytes[length] = 0;
        MinyarText *text = new_text(bytes, length, length);
        assert(minyar_text_length(text) == length);
        if (wrapped) {
            /* A leaf fast-free alone cannot help when this tiny owning parent
             * waits behind an older large cursor before dropping its child. */
            MinyarList *parent = minyar_list_new();
            minyar_list_references(parent);
            minyar_list_add_take(parent, (long long)(uintptr_t)text);
            minyar_rc_release(parent);
        } else minyar_rc_release(text);
    }
    size_t retained = rc_bytes;
#ifdef MINYAR_EXPECT_CLEANUP_DEBT
    if (MINYAR_RC_POLL_BUDGET <= 32) assert(retained > (size_t)length * 8);
#else
    assert(retained <= (size_t)length * 4);
#endif
    while (rc_pending_count) assert(minyar_rc_poll(32) > 0);
    assert(!rc_object_count && !rc_bytes);
    recovered();
    return retained;
}

int main(int argc, char **argv) {
    if (argc > 1) {
        assert(argc == 2);
        if (!strcmp(argv[1], "shared"))
            printf("{\"shared_edge_bytes_before_drain\":%zu}\n", repeated_shared_edge_debt());
        else if (!strcmp(argv[1], "frames"))
            printf("{\"unassigned_frame_retained_bytes\":%zu}\n", unassigned_frame_debt());
        else if (!strcmp(argv[1], "records"))
            printf("{\"mixed_record_bytes_before_drain\":%zu}\n", mixed_record_debt());
        else if (!strcmp(argv[1], "frame-cache"))
            printf("{\"rotating_frame_cache_bytes\":%zu}\n", rotating_frame_cache());
        else if (!strcmp(argv[1], "temporaries"))
            printf("{\"temporary_owner_retained_bytes\":%zu}\n", temporary_owner_debt());
        else if (!strcmp(argv[1], "bytes"))
            printf("{\"variable_size_hostage_bytes\":%zu}\n", variable_size_hostage(0));
        else if (!strcmp(argv[1], "wrapped-bytes"))
            printf("{\"wrapped_variable_size_hostage_bytes\":%zu}\n", variable_size_hostage(1));
        else if (!strcmp(argv[1], "graphs")) {
            size_t peak, remaining;
            repeated_graph_debt(&peak, &remaining);
            printf("{\"graph_peak_objects\":%zu,\"graph_objects_before_drain\":%zu}\n", peak, remaining);
        } else assert(!"unknown stress phase");
        return 0;
    }
    size_t initial = rss();
    assert(!minyar_pool_try_allocate(SIZE_MAX));
    assert(!minyar_pool_try_allocate((size_t)MINYAR_POOL_BYTES + 1));
    recovered();
    void *small = minyar_pool_allocate(17);
    memset(small, 0x19, 17);
    minyar_pool_deallocate(small);
    size_t after_small = rss();
    recovered();
    size_t observed_peak = shuffled_lifetimes();
    size_t after_reuse = rss(), ordinary_high_water = minyar_pool_high_water;
    size_t graph_peak, graph_remaining;
    repeated_graph_debt(&graph_peak, &graph_remaining);
    size_t shared_edge_bytes = repeated_shared_edge_debt();
    size_t unassigned_frame_bytes = unassigned_frame_debt();
    size_t mixed_record_bytes = mixed_record_debt();
    size_t frame_cache_bytes = rotating_frame_cache();
    size_t temporary_owner_bytes = temporary_owner_debt();
    size_t hostage_bytes = variable_size_hostage(0);
    size_t wrapped_hostage_bytes = variable_size_hostage(1);
    wide_offsets();
    printf("{\"virtual_pool_bytes\":%zu,\"virtual_map_bytes\":%zu,\"initial_rss\":%zu,"
           "\"after_small_rss\":%zu,\"observed_peak_rss\":%zu,\"after_reuse_rss\":%zu,"
           "\"ordinary_allocated_high_water\":%zu,\"final_allocated_bytes\":%zu,\"rounds\":24,"
           "\"poll_budget\":%u,\"graph_peak_objects\":%zu,\"graph_objects_before_drain\":%zu,"
           "\"shared_edge_bytes_before_drain\":%zu,\"unassigned_frame_retained_bytes\":%zu,"
           "\"mixed_record_bytes_before_drain\":%zu,\"temporary_owner_retained_bytes\":%zu,"
           "\"variable_size_hostage_bytes\":%zu,\"wrapped_variable_size_hostage_bytes\":%zu,"
           "\"rotating_frame_cache_bytes\":%zu}\n",
           (size_t)MINYAR_POOL_BYTES, (size_t)MINYAR_POOL_MAP_BYTES, initial, after_small,
           observed_peak, after_reuse, ordinary_high_water, minyar_pool_used,
           (unsigned)MINYAR_RC_POLL_BUDGET, graph_peak, graph_remaining, shared_edge_bytes,
           unassigned_frame_bytes, mixed_record_bytes, temporary_owner_bytes, hostage_bytes,
           wrapped_hostage_bytes, frame_cache_bytes);
    return 0;
}
