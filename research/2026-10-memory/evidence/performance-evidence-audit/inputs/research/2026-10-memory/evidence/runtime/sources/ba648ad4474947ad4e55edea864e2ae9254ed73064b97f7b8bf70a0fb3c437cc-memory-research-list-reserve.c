/* Count backing allocator calls separately from the ownership work counters. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#include <stdlib.h>
#include <assert.h>
#include <stdio.h>

static size_t allocation_calls, resize_calls;
static size_t fail_allocation;
#ifndef MINYAR_BOUNDED_HEAP
static void *research_allocate(size_t bytes) {
    allocation_calls++;
    if (allocation_calls == fail_allocation)
        return NULL;
    return malloc(bytes);
}
static void *research_resize(void *pointer, size_t bytes) {
    resize_calls++;
    return realloc(pointer, bytes);
}
#define malloc research_allocate
#define realloc research_resize
#endif
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#undef malloc
#undef realloc

static void drain(void) {
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count)
        assert(minyar_rc_poll(1) == 1);
#endif
    assert(rc_object_count == 0 && rc_bytes == 0);
#ifdef MINYAR_SYSTEM_HEAP
    assert(rc_heap_allocation_count == 0);
#elif defined(MINYAR_BOUNDED_HEAP)
    assert(minyar_pool_used == 0);
#endif
}

/* Model the documented policy independently, rather than consulting the
 * destination's capacity planner. The source may have excess spare capacity. */
static long long expected_capacity(long long length) {
    long long capacity = 0;
    while (capacity < length) {
#ifdef MINYAR_BOUNDED_HEAP
        capacity = capacity ? capacity * 2 + 1 : 3;
#else
        capacity = capacity ? capacity * (capacity >= 4096 ? 4 : 2) : 2;
#endif
    }
    return capacity;
}

static void check_scalar(long long length) {
    MinyarList *source = minyar_list_new();
    for (long long i = 0; i < length; i++)
        minyar_list_add(source, i * 37 - 11);
    size_t allocations = allocation_calls, resizes = resize_calls;
    MinyarList *result = minyar_list_appended(source, -313, 0, 0);
    size_t append_allocations = allocation_calls - allocations;
    size_t append_resizes = resize_calls - resizes;
    printf("length=%lld allocations=%zu resizes=%zu\n", length, append_allocations, append_resizes);
    assert(result != source && result->length == length + 1);
    assert(result->capacity == expected_capacity(length + 1));
    for (long long i = 0; i < length; i++) {
        assert(result->values[i] == i * 37 - 11);
        assert(source->values[i] == i * 37 - 11);
    }
    assert(result->values[length] == -313 && source->length == length);
#if !defined(MINYAR_BOUNDED_HEAP)
    /* One List header, one backing buffer; no intermediate reallocations. */
    if (!getenv("MINYAR_RESEARCH_MEASURE_COUNTS"))
        assert(append_allocations == 2 && append_resizes == 0);
#endif
    minyar_rc_release(source);
    minyar_rc_release(result);
    drain();
}

static void check_references(int take) {
    enum { LENGTH = 257 };
    MinyarText *shared = copy_c_text("shared");
    MinyarText *tail = copy_c_text("tail");
    MinyarList *source = minyar_list_new();
    minyar_list_references(source);
    for (int i = 0; i < LENGTH; i++)
        minyar_list_add(source, (long long)(uintptr_t)shared);
    MinyarList *result = minyar_list_appended(source, (long long)(uintptr_t)tail, 1, take);
    assert((((RcObject *)shared - 1)->ownership >> 3) == 2 * LENGTH + 1);
    assert((((RcObject *)tail - 1)->ownership >> 3) == (size_t)(take ? 1 : 2));
    minyar_rc_release(source);
    minyar_rc_release(shared);
    if (!take)
        minyar_rc_release(tail);
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count)
        assert(minyar_rc_poll(1) == 1);
#endif
    assert(rc_object_count == 3);
    for (int i = 0; i < LENGTH; i++)
        assert(result->values[i] == (long long)(uintptr_t)shared);
    assert(result->values[LENGTH] == (long long)(uintptr_t)tail);
    assert(tail->byte_length == 4 && !memcmp(tail->bytes, "tail", 4));
    assert((((RcObject *)shared - 1)->ownership >> 3) == LENGTH);
    minyar_rc_release(result);
    drain();
}

int main(int argc, char **argv) {
    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc == 2) {
        if (!strcmp(argv[1], "overflow")) {
            MinyarList empty = {NULL, 0, LLONG_MAX};
            list_grow(&empty);
        } else if (!strcmp(argv[1], "oom-object") || !strcmp(argv[1], "oom-data")) {
            MinyarList *source = minyar_list_new();
            fail_allocation = allocation_calls + (!strcmp(argv[1], "oom-object") ? 1 : 2);
            minyar_list_appended(source, 1, 0, 0);
        }
#ifdef MINYAR_BOUNDED_HEAP
        else if (!strcmp(argv[1], "oom-pool")) {
            MinyarList source = {NULL, (long long)MINYAR_BOUNDED_HEAP_BYTES, 0};
            minyar_list_appended(&source, 1, 0, 0);
        }
#endif
        return 1;
    }
    const long long lengths[] = {0, 1, 2, 3, 15, 31, 1023, 1024, 4095, 4096, 8193};
    for (size_t i = 0; i < sizeof(lengths) / sizeof(*lengths); i++)
        check_scalar(lengths[i]);
    check_references(0);
    check_references(1);
    puts("known-length append allocation, contents, policy and ownership verified");
    return 0;
}
