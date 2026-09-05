#define MINYAR_BOUNDED_HEAP 1
#define MINYAR_LAZY_HEAP 1
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>
#include <sys/resource.h>

static size_t rss(void) {
    struct rusage usage;
    assert(!getrusage(RUSAGE_SELF, &usage));
#ifdef __APPLE__
    return (size_t)usage.ru_maxrss;
#else
    return (size_t)usage.ru_maxrss * 1024;
#endif
}
static void recovered(void) {
    assert(!rc_pending_count && !rc_object_count && !rc_bytes && !minyar_pool_used);
    assert(minyar_pool_mask == ((size_t)1 << minyar_pool_max_order));
    assert(minyar_pool_free[minyar_pool_max_order] == (PoolLink *)minyar_pool);
    assert(minyar_pool_map[0] == minyar_pool_max_order + 1);
}
int main(int argc, char **argv) {
    if (argc > 1 && !strcmp(argv[1], "sanitizer-limit")) {
        minyar_pool_allocate((64u * 1024u * 1024u) + 1);
        return 2;
    }
    size_t startup = rss();
    assert(startup < 32u * 1024u * 1024u && "lazy startup touched its entire reservation");
    /* Many small objects exercise split links and map offsets all the way up
     * to the reservation's largest buddies, without initializing that space. */
    for (size_t round = 0; round < 100; round++) {
        MinyarRecord *objects[128];
        for (size_t i = 0; i < 128; i++) {
            objects[i] = minyar_record_new_scalar(2);
            minyar_record_set(objects[i], 0, (long long)(round + i));
        }
        for (size_t i = 0; i < 128; i++) {
            size_t index = (i * 73) % 128;
            assert(minyar_record_get(objects[index], 0) == (long long)(round + index));
            minyar_rc_release(objects[index]);
        }
        while (rc_pending_count) minyar_rc_poll(SIZE_MAX);
        recovered();
    }
    size_t small = rss();
    assert(small < 32u * 1024u * 1024u && "small objects touched excessive backing/metadata");
    /* Exactly 64 MiB of live managed scalar-record blocks, even when the
     * reservation is much larger. Values are initialized and checked. */
    MinyarRecord *large[63];
    for (size_t i = 0; i < 63; i++) {
        size_t bytes = (i == 62 ? 2u : 1u) * 1024u * 1024u;
        long long fields = (long long)((bytes - 16) / 8);
        large[i] = minyar_record_new_scalar(fields);
        assert(minyar_record_get(large[i], fields - 1) == 0);
        minyar_record_set(large[i], fields - 1, (long long)i);
    }
    assert(minyar_pool_used == 64u * 1024u * 1024u);
    void *extra = minyar_pool_try_allocate(1);
    if (MINYAR_POOL_BYTES == 64u * 1024u * 1024u) assert(!extra);
    else { assert(extra); minyar_pool_deallocate(extra); }
    size_t live = rss();
    for (size_t i = 0; i < 63; i++) {
        size_t index = (i * 32) % 63;
        assert(minyar_record_get(large[index], large[index]->length - 1) == (long long)index);
        minyar_rc_release(large[index]);
    }
    while (rc_pending_count) minyar_rc_poll(SIZE_MAX);
    recovered();
    printf("lazy capacity=%zu map=%zu startup_peak=%zu small_peak=%zu live_64MiB_peak=%zu "
           "logical_highwater=%zu bytes; zero objects/tasks/used blocks after cleanup\n",
           MINYAR_POOL_BYTES, MINYAR_POOL_MAP_BYTES, startup, small, live, minyar_pool_high_water);
    return 0;
}
