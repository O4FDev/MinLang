/* Allocation oracle and runtime graph/alias tests for the finite-heap profile. */
#define MINYAR_BOUNDED_HEAP 1
#ifndef MINYAR_BOUNDED_HEAP_BYTES
#define MINYAR_BOUNDED_HEAP_BYTES (8u * 1024u * 1024u)
#endif
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>

static size_t drain(void) {
    size_t work = 0, calls = 0;
    while (rc_pending_count) {
        size_t step = minyar_rc_poll(SIZE_MAX);
        assert(step > 0 && step <= MINYAR_RC_POLL_BUDGET);
        assert(++calls < 1000000);
        work += step;
    }
    assert(rc_object_count == 0 && rc_bytes == 0);
    return work;
}
static void empty_pool(void) {
    assert(!minyar_pool_used);
    void *whole = minyar_pool_try_allocate(MINYAR_POOL_BYTES);
    assert(whole == minyar_pool);
    assert(!minyar_pool_try_allocate(1));
    minyar_pool_deallocate(whole);
    assert(minyar_pool_mask == ((size_t)1 << minyar_pool_max_order));
}
static unsigned random_word(unsigned *state) {
    *state = *state * 1664525u + 1013904223u;
    return *state;
}
static void allocation_model(void) {
    enum { SLOTS = 128, STEPS = 20000 };
    unsigned char *values[SLOTS] = {0};
    size_t lengths[SLOTS] = {0};
    unsigned char contents[SLOTS] = {0};
    unsigned random = 0x39752u;
    for (unsigned step = 0; step < STEPS; step++) {
        unsigned slot = random_word(&random) % SLOTS;
        unsigned op = random_word(&random) % 3;
        size_t size = (random_word(&random) >> 8) % 4096 + 1;
        if (values[slot] && op == 0) {
            minyar_pool_deallocate(values[slot]); values[slot] = NULL;
        } else {
            size_t preserve = lengths[slot] < size ? lengths[slot] : size;
            if (values[slot]) {
                values[slot] = minyar_pool_resize(values[slot], lengths[slot], size);
                for (size_t i = 0; i < preserve; i++) assert(values[slot][i] == contents[slot]);
            } else values[slot] = minyar_pool_allocate(size);
            lengths[slot] = size;
            contents[slot] = (unsigned char)(step * 17);
            memset(values[slot], contents[slot], size);
            assert((uintptr_t)values[slot] % _Alignof(max_align_t) == 0);
        }
        /* Every outstanding byte is checked against an independent oracle.
         * Pairwise interval checks detect overlapping live allocations. */
        for (unsigned a = 0; a < SLOTS; a++) if (values[a]) {
            for (size_t i = 0; i < lengths[a]; i++) assert(values[a][i] == contents[a]);
            for (unsigned b = a + 1; b < SLOTS; b++) if (values[b]) {
                uintptr_t x = (uintptr_t)values[a], y = (uintptr_t)values[b];
                assert(x + lengths[a] <= y || y + lengths[b] <= x);
            }
        }
        assert(minyar_pool_last_steps <= 4 * minyar_pool_max_order + 1);
    }
    for (unsigned slot = 0; slot < SLOTS; slot++) minyar_pool_deallocate(values[slot]);
    empty_pool();
}
static void resize_at_capacity(void) {
    size_t half = MINYAR_POOL_BYTES / 2;
    unsigned char *value = minyar_pool_allocate(half);
    memset(value, 0x53, half);
    unsigned char *grown = minyar_pool_resize(value, half, MINYAR_POOL_BYTES);
    assert(grown == value && minyar_pool_used == MINYAR_POOL_BYTES);
    for (size_t i = 0; i < half; i++) assert(grown[i] == 0x53);
    memset(grown + half, 0xa7, half);
    unsigned char *shrunk = minyar_pool_resize(grown, MINYAR_POOL_BYTES, 127);
    assert(shrunk == value && minyar_pool_used == 128);
    for (size_t i = 0; i < 127; i++) assert(shrunk[i] == 0x53);
    void *large = minyar_pool_allocate(half);
    minyar_pool_deallocate(large); minyar_pool_deallocate(shrunk);
    empty_pool();
}
static void fragmentation(void) {
    void *blocks[4];
    for (unsigned i = 0; i < 4; i++) blocks[i] = minyar_pool_allocate(MINYAR_POOL_BYTES / 4);
    minyar_pool_deallocate(blocks[0]); minyar_pool_deallocate(blocks[2]);
    assert(minyar_pool_used == MINYAR_POOL_BYTES / 2);
    /* Total free bytes do not imply a sufficiently large contiguous block. */
    assert(!minyar_pool_try_allocate(MINYAR_POOL_BYTES / 2));
    minyar_pool_deallocate(blocks[1]); minyar_pool_deallocate(blocks[3]);
    empty_pool();
}
static void wide_and_debt(void) {
    MinyarList *wide = minyar_list_new();
    minyar_list_references(wide);
    for (size_t i = 0; i < 50000; i++) {
        MinyarRecord *leaf = minyar_record_new_scalar(1);
        minyar_record_set(leaf, 0, (long long)i);
        minyar_list_add_take(wide, (long long)(uintptr_t)leaf);
    }
    void *fillers[256];
    size_t count = 0;
    while (count < 256 && (fillers[count] = minyar_pool_try_allocate(32768))) count++;
    size_t objects_before = rc_object_count;
    minyar_rc_release(wide);
    assert(rc_object_count >= objects_before - MINYAR_RC_POLL_BUDGET); /* At most one leaf per visit. */
    assert(rc_bounded_last_work == MINYAR_RC_POLL_BUDGET);
    assert(minyar_rc_poll(0) == 0);
    /* Pending garbage does not trigger an unbounded allocation-time drain. */
    assert(!minyar_pool_try_allocate(MINYAR_POOL_BYTES / 2));
    size_t pending_before = rc_pending_count;
    assert(!minyar_pool_try_allocate(MINYAR_POOL_BYTES));
    assert(rc_pending_count == pending_before);
    assert(drain() == 50001 - MINYAR_RC_POLL_BUDGET);
    for (size_t i = 0; i < count; i++) minyar_pool_deallocate(fillers[i]);
    empty_pool();
}
static void chain(void) {
    MinyarRecord *root = NULL;
    for (size_t i = 0; i < 100000; i++) {
        MinyarRecord *next = minyar_record_new(1);
        minyar_record_set_take(next, 0, (long long)(uintptr_t)root);
        root = next;
    }
    minyar_rc_release(root);
    assert(rc_object_count >= 100000 - MINYAR_RC_POLL_BUDGET);
    assert(drain() == 200000 - MINYAR_RC_POLL_BUDGET);
    empty_pool();
}
static void aliases_and_mixed(void) {
    MinyarText *survivor = copy_c_text("a🙂éz");
    assert(minyar_text_length(survivor) == 4);
    for (long long width = 0; width <= 130; width++) {
        MinyarRecord *record = minyar_record_new(width);
        for (long long i = 0; i < width; i++) {
            if (i % 3 == 0) minyar_record_set_reference(record, i, (long long)(uintptr_t)survivor);
            else if (i % 3 == 1) minyar_record_set(record, i, (long long)(uintptr_t)survivor);
        }
        minyar_rc_release(record);
        while (rc_pending_count) {
            assert(minyar_text_character_at(survivor, 1) == 0x1f642);
            minyar_rc_poll(1);
        }
        assert(rc_object_count == 1);
        assert((((RcObject *)survivor - 1)->ownership >> 3) == 1);
    }
    MinyarList *aliases = minyar_list_new(); minyar_list_references(aliases);
    for (size_t i = 0; i < 10000; i++) minyar_list_add(aliases, (long long)(uintptr_t)survivor);
    minyar_list_set(aliases, 0, minyar_list_get(aliases, 0));
    minyar_rc_release(aliases);
    while (rc_pending_count) {
        minyar_rc_retain(survivor); minyar_rc_release(survivor);
        assert(minyar_text_character_at(survivor, 2) == 0xe9);
    }
    minyar_rc_release(survivor); drain(); empty_pool();
}
static void frames_and_temporaries(void) {
    for (size_t round = 0; round < 100; round++) {
        minyar_rc_enter(31);
        for (size_t slot = 0; slot < 31; slot++) {
            MinyarText *text = copy_c_text("frame");
            minyar_rc_local_take((long long)slot, text);
            minyar_rc_borrow(text);
        }
        minyar_rc_leave(); drain();
    }
    assert(!rc_frames);
    /* Frames are an intentional reusable high-water cache. The test releases
     * that cache explicitly to check the backing allocator's full recovery. */
    while (rc_free_frames) {
        RcFrame *frame = rc_free_frames;
        rc_free_frames = frame->previous;
        minyar_pool_deallocate(frame->locals);
#ifndef MINYAR_BOUNDED_TEMP_CHUNKS
        minyar_pool_deallocate(frame->temporaries);
#endif
        minyar_pool_deallocate(frame);
    }
    rc_bounded_cached_frame_bytes = 0;
    empty_pool();
}
int main(int argc, char **argv) {
    if (argc > 1 && !strcmp(argv[1], "oom")) {
        minyar_pool_allocate(SIZE_MAX); return 2;
    }
    if (argc > 1 && !strcmp(argv[1], "stale")) {
        volatile unsigned char *value = minyar_pool_allocate(32);
        minyar_pool_deallocate((void *)value);
        return value[0]; /* Sanitizer runner must reject this access. */
    }
    if (argc > 1 && !strcmp(argv[1], "resize")) { resize_at_capacity(); return 0; }
    allocation_model(); resize_at_capacity(); fragmentation(); wide_and_debt(); chain();
    aliases_and_mixed(); frames_and_temporaries();
    assert(minyar_pool_max_steps <= 4 * minyar_pool_max_order + 1);
    printf("bounded runtime passed: 20,000 allocator transitions, fragmentation/debt exhaustion, "
           "50,000-wide and 100,000-deep graphs, aliases, mixed records, frames; "
           "pool=%zu bytes, metadata=%zu bytes, allocator steps<=%zu\n",
           MINYAR_POOL_BYTES, MINYAR_POOL_MAP_BYTES, minyar_pool_max_steps);
    return 0;
}
