/* Native primitive projection. The opaque checksum is a separate object. */
#if defined(MINYAR_RESEARCH_COUNT)
#include "count-prelude.h"
#endif
#ifdef MINYAR_RESEARCH_TEST_ACCOUNTING
#define MINYAR_RC_TESTING 1
#endif
#include "../runtime/minyar_runtime.c"
#if defined(MINYAR_RESEARCH_COUNT)
#undef memcpy
#endif
#include <assert.h>
#include <time.h>

extern uint64_t research_checksum(const long long *, size_t, uintptr_t);

static void drain(void) {
    while (rc_pending_count)
        minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
}
static uint64_t slot(size_t position, uint64_t seed) {
    return seed + (uint64_t)position * UINT64_C(0x9e3779b97f4a7c15);
}
static uint64_t cpu_nanoseconds(void) {
    struct timespec value;
    assert(clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &value) == 0);
    return (uint64_t)value.tv_sec * UINT64_C(1000000000) + (uint64_t)value.tv_nsec;
}

int main(int argc, char **argv) {
    assert(argc == 6);
    size_t length = (size_t)strtoull(argv[1], NULL, 10);
    size_t repetitions = (size_t)strtoull(argv[2], NULL, 10);
    unsigned mode = (unsigned)strtoul(argv[3], NULL, 10);
    uint64_t seed = strtoull(argv[4], NULL, 16);
    uint64_t expected = strtoull(argv[5], NULL, 16);
    assert(length <= 8193 && repetitions && repetitions <= 8388608 && mode <= 2);
    MinyarText *shared = mode == 2 ? copy_c_text("shared reference") : NULL;
    MinyarList *source = minyar_list_new();
    if (mode == 2)
        minyar_list_references(source);
    for (size_t i = 0; i < length; i++) {
        long long word;
        uint64_t bits = mode == 2 ? (uint64_t)(uintptr_t)shared : slot(i, seed);
        memcpy(&word, &bits, sizeof(word));
        minyar_list_add(source, word);
    }
    minyar_rc_retain(source);
    uint64_t tail_bits = mode == 2 ? (uint64_t)(uintptr_t)shared : UINT64_C(0xfedcba9876543210);
    long long tail;
    memcpy(&tail, &tail_bits, sizeof(tail));
    drain();
    uint64_t start = cpu_nanoseconds();
    uint64_t combined = 0;
    for (size_t i = 0; i < repetitions; i++) {
        if (mode == 1)
            rc_drop(minyar_record_new(4 * MINYAR_RC_POLL_BUDGET + 2));
#if defined(MINYAR_RESEARCH_COUNT)
        research_adds = research_takes = research_copies = research_copy_bytes = 0;
        research_guard_pending = research_retains = event_count = 0;
        research_phase = 1;
#endif
        MinyarList *result = minyar_list_appended(source, tail, mode == 2, 0);
#if defined(MINYAR_RESEARCH_COUNT)
        research_phase = 0;
        printf("{\"kind\":\"counts\",\"guard_pending\":%zu,\"adds\":%zu,"
               "\"copies\":%zu,\"copy_bytes\":%zu,\"retains\":%zu}\n",
               research_guard_pending, research_adds, research_copies, research_copy_bytes,
               research_retains);
#endif
        assert(result != source && result->length == (long long)length + 1);
        uint64_t checksum = research_checksum(result->values, length + 1, (uintptr_t)shared);
        assert(checksum == expected);
        combined ^= checksum + (uint64_t)i;
        minyar_rc_release(result);
        drain();
    }
    uint64_t duration = cpu_nanoseconds() - start;
    /* Outside the timed interval: inspect all values and mutation independence. */
    MinyarList *control = minyar_list_appended(source, tail, mode == 2, 0);
    assert(control->values != source->values || !length);
    for (size_t i = 0; i < length; i++) {
        uint64_t value;
        memcpy(&value, &source->values[i], sizeof(value));
        assert(value == (mode == 2 ? (uint64_t)(uintptr_t)shared : slot(i, seed)));
        assert(control->values[i] == source->values[i]);
    }
    assert(control->values[length] == tail);
    if (length) {
        long long old = source->values[0];
        minyar_list_set(control, 0, 0);
        assert(source->values[0] == old);
    }
    minyar_rc_release(control);
    minyar_rc_release(source);
    assert(source->length == (long long)length);
    minyar_rc_release(source);
    if (shared)
        minyar_rc_release(shared);
    drain();
    assert(!rc_pending_count && !rc_frames && !rc_free_frames);
#ifdef MINYAR_RC_TESTING
    assert(!rc_object_count && !rc_bytes);
#endif
#ifdef MINYAR_BOUNDED_HEAP
    assert(!minyar_pool_used);
#else
#ifdef MINYAR_RC_TESTING
    assert(!rc_heap_allocation_count);
#endif
#endif
    printf("{\"kind\":\"result\",\"cpu_nanoseconds\":%llu,\"checksum\":\"%016llx\","
           "\"repetitions\":%zu,\"quiescent\":true,\"recovery_scope\":\"pending-zero;"
           "frames-absent;fixed-pool-zero;managed-gauges-only-if-testing\"}\n",
           (unsigned long long)duration, (unsigned long long)combined, repetitions);
    return 0;
}
