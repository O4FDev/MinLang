/* Queue-empty buddy placement search, using the real retained/runtime append.
 * Raw pool allocations represent unrelated live backing storage. Follow-on
 * probes use try_allocate so rejection is observable without killing the search.
 * Every admitted append checks contents/capacity and complete pool recovery. */
#define MINYAR_BOUNDED_HEAP 1
#ifndef MINYAR_BOUNDED_HEAP_BYTES
#define MINYAR_BOUNDED_HEAP_BYTES 65536
#endif
#define MINYAR_RC_TESTING 1
#ifndef MINYAR_RESEARCH_RUNTIME
#define MINYAR_RESEARCH_RUNTIME "../runtime/minyar_runtime.c"
#endif
#include MINYAR_RESEARCH_RUNTIME
#include <assert.h>

static uint32_t random_state;
static uint32_t next_random(void) {
    random_state ^= random_state << 13;
    random_state ^= random_state >> 17;
    random_state ^= random_state << 5;
    return random_state;
}

static void cohort(uint32_t seed) {
    random_state = seed;
    long long length = ((long long)1 << (2 + seed % 8)) - 1;
    MinyarList *source = minyar_list_new();
    for (long long i = 0; i < length; i++)
        minyar_list_add(source, 37 * i);
    void *fillers[512] = {0};
    size_t order[512], count = 0;
    while (count < 512) {
        size_t bytes = (size_t)32 << (next_random() % 9);
        void *value = minyar_pool_try_allocate(bytes);
        if (!value)
            break;
        fillers[count] = value;
        order[count] = count;
        count++;
    }
    for (size_t i = count; i > 1; i--) {
        size_t j = next_random() % i, saved = order[i - 1];
        order[i - 1] = order[j];
        order[j] = saved;
    }
    for (size_t i = 0; i < count / 2; i++) {
        size_t index = order[i];
        minyar_pool_deallocate(fillers[index]);
        fillers[index] = NULL;
    }
    assert(rc_pending_count == 0);
    unsigned long long initial_hash = 1469598103934665603ULL;
    for (size_t i = 0; i < MINYAR_POOL_MAP_BYTES; i++)
        initial_hash = (initial_hash ^ minyar_pool_map[i]) * 1099511628211ULL;
    for (unsigned i = 0; i <= minyar_pool_max_order; i++)
        initial_hash =
            (initial_hash ^ (minyar_pool_free[i] ? pool_offset(minyar_pool_free[i]) + 1 : 0)) *
            1099511628211ULL;
    /* Separate small header space and at least one final-sized block. */
    size_t target = (size_t)(length + 1) * 16;
    unsigned target_order = 0;
    for (size_t bytes = 32; bytes < target; bytes *= 2)
        target_order++;
    size_t lower_orders = ((size_t)1 << target_order) - 1;
    int admitted = (minyar_pool_mask & lower_orders) && (minyar_pool_mask & ~lower_orders);
    MinyarList *result = NULL;
    unsigned accepted = 0;
    size_t result_offset = SIZE_MAX;
    if (admitted) {
        result = minyar_list_appended(source, 919, 0, 0);
        assert(rc_pending_count == 0);
        assert(result->length == length + 1 && result->capacity == 2 * length + 1 &&
               result->values[length] == 919);
        for (long long i = 0; i < length; i++)
            assert(result->values[i] == source->values[i]);
        result_offset = pool_offset((RcData *)result->values - 1);
        void *probes[6] = {0};
        const size_t requests[] = {32, 128, 512, 2048, 8192, 16384};
        for (size_t i = 0; i < 6; i++) {
            probes[i] = minyar_pool_try_allocate(requests[i]);
            if (probes[i])
                accepted |= 1u << i;
        }
        for (size_t i = 0; i < 6; i++)
            minyar_pool_deallocate(probes[i]);
    }
    printf("{\"seed\":%u,\"length\":%lld,\"initial_hash\":%llu,\"admitted\":%d,\"result_offset\":%"
           "zu,\"accepted\":%u}\n",
           seed, length, initial_hash, admitted, result_offset, accepted);
    minyar_rc_release(result);
    minyar_rc_release(source);
    while (rc_pending_count)
        minyar_rc_poll(1);
    for (size_t i = 0; i < count; i++)
        minyar_pool_deallocate(fillers[i]);
    assert(rc_object_count == 0 && rc_bytes == 0 && minyar_pool_used == 0);
}

int main(int argc, char **argv) {
    uint32_t first = argc > 1 ? (uint32_t)strtoul(argv[1], NULL, 0) : 1;
    uint32_t count = argc > 2 ? (uint32_t)strtoul(argv[2], NULL, 0) : 2048;
    assert(first && count && count <= 16384 && first <= UINT32_MAX - count);
    for (uint32_t seed = first; seed < first + count; seed++)
        cohort(seed);
    return 0;
}
