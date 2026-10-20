/* Independent indexed-owner model. Compare semantic transcripts; only the
 * candidate is required to clear retired/cached physical payload slots. */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE 1
#endif
#define MINYAR_RC_TESTING 1
#define MINYAR_INTEGER_TEXT_CACHE_LIMIT 0
#ifndef FRAME_CLEAN_EXPECT
#define FRAME_CLEAN_EXPECT 1
#endif
#include MINYAR_RUNTIME_SOURCE
#include <assert.h>

enum { ROOTS = 4, MAX_SLOTS = 128 };
static MinyarRecord *roots[ROOTS];
static size_t transferred[ROOTS], serial;
static RcObject immortal = { RC_TEXT };
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
static unsigned activated_cycle;
#endif
static struct {
    RcFrame *frame;
    size_t count, capacity, written, pending, finalized;
    unsigned active, tagged[MAX_SLOTS];
    size_t order[MAX_SLOTS], released[MAX_SLOTS], release_count;
    void *values[MAX_SLOTS];
} model;

static size_t number(void *value) {
    if (!value) return 0;
    if (value == &immortal + 1) return ROOTS + 1;
    for (size_t i = 0; i < ROOTS; i++) if (value == roots[i]) return i + 1;
    assert(!"owner absent from independent model");
    return 0;
}
static void require_clean(RcFrame *frame, size_t slot) {
#if FRAME_CLEAN_EXPECT
    if (frame->locals[slot] != NULL) {
        fprintf(stderr, "frame-clean invariant: retired/cached capacity slot %zu is non-NULL\n", slot);
        abort();
    }
#else
    (void)frame; (void)slot;
#endif
}
static void cached_slots(void) {
    for (RcFrame *frame = rc_free_frames; frame; frame = frame->previous)
        for (size_t i = 0; i < frame->local_capacity; i++) require_clean(frame, i);
}
static void verify(void) {
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
    if (activated_cycle) {
        assert(rc_cycle_present && !rc_cycle_pending && rc_cycle_phase == RC_CYCLE_IDLE);
        assert(!rc_cycle_head && !rc_cycle_known_head && !rc_cycle_active && !rc_cycle_gray_head);
    }
#endif
    size_t expected[ROOTS];
    for (size_t i = 0; i < ROOTS; i++) expected[i] = roots[i] ? 1 + transferred[i] : 0;
    if (model.frame) {
        assert(model.capacity <= MAX_SLOTS);
        if (model.active) {
            assert(rc_frames == model.frame && model.frame->local_count == model.count);
            assert(model.frame->written_count == model.written);
            for (size_t i = 0; i < model.count; i++) {
                uintptr_t wanted = (uintptr_t)model.values[i] | model.tagged[i];
                assert((uintptr_t)model.frame->locals[i] == wanted);
                size_t id = number(model.values[i]);
                if (id && id <= ROOTS) expected[id - 1]++;
            }
            for (size_t i = model.count; i < model.capacity; i++) require_clean(model.frame, i);
        } else if (!model.finalized) {
            assert(!rc_frames && rc_bounded_frame_head == model.frame);
            assert(model.frame->local_count == model.pending && rc_pending_count == 1);
            unsigned pending[MAX_SLOTS] = {0};
            for (size_t i = 0; i < model.pending; i++) {
                size_t slot = model.order[i];
                pending[slot] = 1;
                assert((uintptr_t)model.frame->locals[slot] == ((uintptr_t)model.values[slot] | 1));
                size_t id = number(model.values[slot]);
                if (id && id <= ROOTS) expected[id - 1]++;
            }
            for (size_t i = 0; i < model.capacity; i++)
                if (!pending[i]) require_clean(model.frame, i);
        } else {
            assert(!rc_frames && !rc_pending_count && rc_free_frames == model.frame);
        }
        if (!model.finalized)
            for (size_t i = 0; i < (model.active ? model.written : model.pending); i++)
                assert(rc_bounded_local_indices(model.frame)[i] == model.order[i]);
    }
    for (size_t i = 0; i < ROOTS; i++) if (roots[i]) {
        assert(((RcObject *)roots[i] - 1)->ownership == (expected[i] * 8 | RC_SCALAR_RECORD));
        assert(roots[i]->values[0] == 100 + (long long)i);
    }
    assert(!rc_bounded_active && !rc_bounded_head && !rc_bounded_recent_head);
    assert(!rc_bounded_chunk_head);
    cached_slots();
}
static void record(const char *label, size_t request, size_t work) {
    assert(work <= request && work <= MINYAR_RC_POLL_BUDGET && rc_bounded_last_work == work);
    verify();
    printf("%s:%zu request=%zu work=%zu debt=%zu live=%zu bytes=%zu next=%u parity=%u "
           "cursor=%zu cache=%zu count=%zu cap=%zu written=%zu pending=%zu finalized=%zu roots[",
           label, serial++, request, work, rc_pending_count, rc_object_count, rc_bytes,
           rc_bounded_next_queue, rc_bounded_recent_turn, rc_bounded_cursor,
           rc_bounded_cached_frame_bytes, model.count, model.capacity,
           model.written, model.pending, model.finalized);
    for (size_t i = 0; i < ROOTS; i++)
        printf("%zu,", (size_t)(roots[i] ? ((RcObject *)roots[i] - 1)->ownership >> 3 : 0));
    printf("] remaining[");
    if (model.frame && !model.active)
        for (size_t i = 0; i < model.pending; i++)
            printf("%zu/%zu,", model.order[i], number(model.values[model.order[i]]));
    printf("] released[");
    for (size_t i = 0; i < model.release_count; i++)
        printf("%zu/%zu,", model.released[i], number(model.values[model.released[i]]));
    puts("]");
}
static void clear_caches(void) {
    while (rc_free_frames) {
        RcFrame *frame = rc_free_frames;
        rc_free_frames = frame->previous;
        rc_heap_deallocate(frame->locals); rc_heap_deallocate(frame);
    }
#ifdef MINYAR_BOUNDED_OWNER_CACHE
    rc_bounded_chunk_cache_clear();
#endif
    rc_bounded_cached_frame_bytes = 0;
}
static void recover(void) {
    assert(!rc_frames && !rc_scopes && !rc_pending_count && !rc_object_count && !rc_bytes);
    cached_slots();
    memset(&model, 0, sizeof(model));
    clear_caches();
    assert(!rc_bounded_frame_head && !rc_bounded_frame_tail && !rc_bounded_chunk_head);
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
static void model_set(size_t slot, void *value) {
    assert(model.active && slot < model.count);
    if (!model.tagged[slot] && value) {
        assert(model.written < MAX_SLOTS);
        model.order[model.written++] = slot;
        model.tagged[slot] = 1;
    }
    model.values[slot] = value;
}
static void assign(size_t slot, void *value) {
    minyar_rc_local((long long)slot, value);
    model_set(slot, value);
    record("assign", 0, 0);
}
static void *move(size_t slot, int consuming, void *borrowed) {
    void *value = model.values[slot];
    if (consuming) {
        minyar_rc_local_move_owner((long long)slot, borrowed);
        if (!value) value = borrowed;
    } else minyar_rc_local_move((long long)slot);
    model.values[slot] = NULL;
    size_t id = number(value);
    if (id && id <= ROOTS) transferred[id - 1]++;
    record("move", 0, 0);
    return value;
}
static void release_transfer(void *value) {
    size_t id = number(value);
    assert(id && id <= ROOTS && transferred[id - 1]);
    minyar_rc_release(value);
    transferred[id - 1]--;
    record("release-transfer", 0, 0);
}
static void take(size_t slot, void *value) {
    size_t id = number(value);
    assert(id && id <= ROOTS && transferred[id - 1]);
    minyar_rc_local_take((long long)slot, value);
    transferred[id - 1]--;
    model_set(slot, value);
    record("take", 0, 0);
}
static void begin(size_t count) {
    assert(count <= MAX_SLOTS && !rc_pending_count);
    RcFrame *cached = rc_free_frames;
    size_t capacity = cached ? cached->local_capacity : 0;
    minyar_rc_enter((long long)count);
    if (cached) assert(rc_frames == cached);
    memset(&model, 0, sizeof(model));
    model.frame = rc_frames;
    model.count = count;
    model.capacity = count > capacity ? count : capacity;
    model.active = 1;
    assert(model.frame->local_capacity == model.capacity);
    record("entry", 0, 0);
}
static void advance(size_t work) {
    while (work--) {
        if (model.pending) {
            model.released[model.release_count++] = model.order[--model.pending];
        } else {
            assert(!model.finalized);
            model.finalized = 1;
        }
    }
}
static void poll_model(size_t request) {
    size_t expected = model.finalized ? 0 : model.pending + 1;
    if (expected > request) expected = request;
    if (expected > MINYAR_RC_POLL_BUDGET) expected = MINYAR_RC_POLL_BUDGET;
    size_t work = minyar_rc_poll(request);
    assert(work == expected);
    advance(work);
    record("poll", request, work);
}
static void leave(void) {
    model.active = 0;
    model.pending = model.written;
    minyar_rc_leave();
    size_t expected = model.pending + 1;
    if (expected > MINYAR_RC_POLL_BUDGET) expected = MINYAR_RC_POLL_BUDGET;
    assert(rc_bounded_last_work == expected);
    advance(expected);
    record("leave", MINYAR_RC_POLL_BUDGET, expected);
    poll_model(0);
    /* One-unit observations prove the exact reverse release order and the
     * still-owned prefix, even when the configured ceiling exceeds one. */
    while (!model.finalized) poll_model(1);
    poll_model(SIZE_MAX);
    for (size_t i = 0; i < ROOTS; i++) assert(transferred[i] == 0);
}
static void fill(size_t count, unsigned dense, unsigned round) {
    if (!count) return;
    if (dense) {
        for (size_t i = 0; i < count; i++)
            assign((i * 37) % count, roots[(i + round) % ROOTS]);
        return;
    }
    if (count < 8) {
        assign(count - 1, roots[round % ROOTS]);
        if (count > 1) assign(0, &immortal + 1);
        assign(count / 2, NULL);
        assign(count / 2, NULL);
        return;
    }
    assign(1, NULL); assign(1, NULL); /* Never-written NULL stays unindexed. */
    assign(count - 1, roots[0]); assign(count - 1, roots[0]);
    assign(count - 1, NULL); assign(count - 1, NULL);
    assign(count - 1, roots[1]);
    assign(0, roots[2]); release_transfer(move(0, 0, NULL));
    assign(count / 2, roots[3]);
    take(count / 2, move(count / 2, 1, roots[3]));
    take(2, move(1, 1, roots[0])); /* Borrowed parameter fallback owner. */
    assign(3, &immortal + 1);
    assign(4, roots[0]); assign(4, NULL);
}
static void family(const size_t *counts, size_t count) {
    recover();
    for (size_t i = 0; i < ROOTS; i++) {
        roots[i] = minyar_record_new_scalar(1);
        minyar_record_set(roots[i], 0, 100 + (long long)i);
    }
    for (size_t round = 0; round < count; round++) {
        begin(counts[round]);
        fill(counts[round], !(round & 1), (unsigned)round);
        leave();
    }
    memset(&model, 0, sizeof(model));
    for (size_t i = 0; i < ROOTS; i++) {
        assert(!transferred[i]);
        minyar_rc_release(roots[i]);
        roots[i] = NULL;
    }
    recover();
    puts("family fully recovered");
}
#ifndef MINYAR_SYSTEM_HEAP
static void raw_drain(void) {
    size_t turns = 0;
    while (rc_pending_count) {
        assert(++turns < 10000);
        size_t work = minyar_rc_poll(SIZE_MAX);
        assert(work > 0 && work <= MINYAR_RC_POLL_BUDGET);
        cached_slots();
        printf("lower-poll work=%zu debt=%zu live=%zu bytes=%zu next=%u parity=%u cache=%zu\n",
               work, rc_pending_count, rc_object_count, rc_bytes, rc_bounded_next_queue,
               rc_bounded_recent_turn, rc_bounded_cached_frame_bytes);
    }
}
static void lower_growth(void) {
    /* Preserve every physical layout/eviction/recovery assertion from the
     * maintained dead-frame-growth fixture; require clean cached slots too. */
    assert(MINYAR_POOL_BYTES == 4096 && MINYAR_FRAME_CACHE_BYTES == 1088);
    minyar_rc_enter(0);
    RcFrame *frame = rc_frames;
    minyar_rc_leave(); raw_drain();
    void *blocker = rc_heap_allocate(1024);
    void *lower = rc_heap_allocate(1024);
    memset(lower, 0xa5, 1024); /* Discard relocation cannot rely on old zeros. */
    minyar_rc_enter(64);
    assert(rc_frames == frame && pool_offset(blocker) == 1024 && pool_offset(lower) == 2048);
    assert(pool_offset(frame->locals) == 3072);
    void *owned = minyar_record_new_scalar(1);
    minyar_record_set(owned, 0, 99);
    minyar_rc_local_take(63, owned);
    minyar_rc_leave(); raw_drain();
    assert(!rc_object_count && !rc_bytes && !rc_pending_count);
    assert(rc_bounded_cached_frame_bytes == 1088);
    cached_slots();
    rc_heap_deallocate(lower);
    minyar_rc_enter(128);
    assert(rc_frames == frame && pool_offset(frame->locals) == 2048);
    assert(!rc_bounded_cached_frame_bytes);
    for (size_t i = 0; i < 128; i++) assert(frame->locals[i] == NULL);
    minyar_rc_leave(); raw_drain();
    assert(!rc_frames && !rc_free_frames && !rc_bounded_cached_frame_bytes);
    assert(!rc_object_count && !rc_bytes && !rc_pending_count);
    rc_heap_deallocate(blocker);
    assert(!minyar_pool_used);
#ifdef MINYAR_POOL_ASAN
    for (size_t i = 1024; i < MINYAR_POOL_BYTES; i++)
        assert(__asan_address_is_poisoned(minyar_pool + i));
#endif
    assert(minyar_pool_mask == ((size_t)1 << minyar_pool_max_order));
    assert(minyar_pool_free[minyar_pool_max_order] == (PoolLink *)minyar_pool);
    assert(minyar_pool_map[0] == minyar_pool_max_order + 1);
    for (size_t i = 1; i < MINYAR_POOL_MAP_BYTES; i++) assert(!minyar_pool_map[i]);
    PoolLink root = pool_read_link(minyar_pool_free[minyar_pool_max_order]);
    assert(!root.previous && !root.next);
    recover();
    puts("lower-buddy full initialization, eviction, poison and whole-pool recovery passed");
}
#endif
/* Retire a real self-cycle first; the sticky scheduler selection then stays
 * active while the unchanged scalar-frame model excludes competing queues. */
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
static void activate_cycle(void) {
    assert(!rc_frames && !rc_pending_count && !rc_object_count && !rc_bytes);
    MinyarRecord *cycle = minyar_record_new_traced(1);
    minyar_record_set_reference_traced(cycle, 0, (long long)(uintptr_t)cycle);
    assert(rc_cycle_present);
    minyar_rc_release(cycle);
    size_t turns = 0;
    while (rc_pending_count) {
        assert(++turns < 10000);
        assert(minyar_rc_poll(1) == 1);
    }
    assert(rc_cycle_present && !rc_object_count && !rc_bytes && !rc_cycle_pending);
    assert(rc_cycle_phase == RC_CYCLE_IDLE && !rc_cycle_head && !rc_cycle_known_head);
    activated_cycle = 1;
    recover();
    puts("genuine self-cycle fully retired; four-queue scheduler remains selected");
}
#endif
int main(int argc, char **argv) {
    assert(argc == 2);
    if (!strcmp(argv[1], "lower")) {
#ifndef MINYAR_SYSTEM_HEAP
        lower_growth();
        return 0;
#else
        assert(!"lower-buddy case requires a pool");
#endif
    }
    if (!strcmp(argv[1], "activated")) {
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
        activate_cycle();
#else
        assert(!"activated case requires the cycle runtime");
#endif
    } else assert(!strcmp(argv[1], "main"));
    const size_t capacities[] = {64, 3, 96, 1, 97, 8, 32, 0};
    const size_t same_block[] = {5, 6, 2, 7};
    family(capacities, sizeof(capacities) / sizeof(*capacities));
    family(same_block, sizeof(same_block) / sizeof(*same_block));
    puts("frame initialization semantic transcript complete");
    return 0;
}
