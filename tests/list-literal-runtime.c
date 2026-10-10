/* Direct runtime contract tests for compiler-owned immutable scalar sources.
 * NULL is allowed for a zero-length source; a List receiver is always valid.
 * Positive sources are non-overlapping i64 arrays, matching compiler globals.
 */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#include <assert.h>
#include <limits.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef LIST_LITERAL_FAULTS
#include "allocation-fault-runtime.c"
#else
static size_t raw_allocations, raw_resizes;
static void *counted_malloc(size_t bytes) { ++raw_allocations; return malloc(bytes); }
static void *counted_realloc(void *pointer, size_t bytes) { ++raw_resizes; return realloc(pointer, bytes); }
#define malloc counted_malloc
#define realloc counted_realloc
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#undef malloc
#undef realloc
#endif

static const long long constants[] = {LLONG_MIN, -101, -1, 0, 1, 97, LLONG_MAX};
static long long generated[100000];

static void initialize_source(void) {
    for (size_t i = 0; i < sizeof(generated) / sizeof(*generated); ++i)
        generated[i] = (long long)(i % 2001) - 1000;
}

static size_t allocation_operations(void) {
#ifdef LIST_LITERAL_FAULTS
    return fault_allocations + fault_resizes;
#elif defined(MINYAR_BOUNDED_HEAP) && !defined(MINYAR_COMPILER_ARENA)
    return minyar_pool_allocation_count;
#else
    return raw_allocations + raw_resizes;
#endif
}

static void release_list(MinyarList *list) {
#ifndef MINYAR_COMPILER_ARENA
    minyar_rc_release(list);
#else
    (void)list; /* Compiler arena lifetime intentionally covers the process. */
#endif
}

static void cleanup(void) {
#ifdef MINYAR_COMPILER_ARENA
    MinyarArena *arenas[] = {&object_arena, &data_arena, &list_arena, &large_list_arena};
    for (size_t i = 0; i < sizeof(arenas) / sizeof(*arenas); ++i) {
        MinyarArenaBlock *block = arenas[i]->block;
        while (block) {
            MinyarArenaBlock *next = block->next;
            free(block);
            block = next;
        }
        arenas[i]->block = NULL;
    }
#else
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count) assert(minyar_rc_poll(32) > 0);
#else
    assert(rc_pending_count == 0);
#endif
    assert(rc_frames == NULL && rc_object_count == 0 && rc_bytes == 0);
#ifdef MINYAR_BOUNDED_HEAP
    assert(minyar_pool_used == 0);
#endif
#endif
}

static void one_reserve(void) {
    MinyarList *list = minyar_list_new();
    size_t before = allocation_operations();
    minyar_list_append_scalars(list, generated, 100000);
    assert(allocation_operations() - before == 1);
    assert(list->length == 100000 && list->capacity >= 100000);
    for (long long i = 0; i < list->length; ++i)
        assert(minyar_list_get(list, i) == i % 2001 - 1000);
    release_list(list);
}

static void copies_and_prefixes(void) {
    MinyarList *first = minyar_list_new(), *second = minyar_list_new();
    size_t before = allocation_operations();
    minyar_list_append_scalars(first, NULL, 0);
    assert(first->length == 0 && first->capacity == 0 && first->values == NULL);
    assert(allocation_operations() == before);
    minyar_list_append_scalars(first, constants, 7);
    minyar_list_append_scalars(second, constants, 7);
    assert(first != second && first->values != second->values);
    assert(first->values != constants && second->values != constants);
    minyar_list_set(first, 0, 42);
    assert(minyar_list_get(first, 0) == 42);
    assert(minyar_list_get(second, 0) == LLONG_MIN && constants[0] == LLONG_MIN);
    for (long long i = 1; i < 7; ++i) {
        assert(minyar_list_get(first, i) == constants[i]);
        assert(minyar_list_get(second, i) == constants[i]);
    }
    long long *old_values = first->values;
    long long old_capacity = first->capacity;
    before = allocation_operations();
    minyar_list_append_scalars(first, NULL, 0);
    assert(first->length == 7 && first->values == old_values && first->capacity == old_capacity);
    assert(allocation_operations() == before);
    minyar_list_append_scalars(first, generated, 8193);
    assert(first->length == 8200 && minyar_list_get(first, 0) == 42);
    for (long long i = 1; i < 7; ++i) assert(minyar_list_get(first, i) == constants[i]);
    for (long long i = 0; i < 8193; ++i) assert(minyar_list_get(first, i + 7) == i % 2001 - 1000);
    for (long long i = 0; i < 7; ++i) assert(minyar_list_get(second, i) == constants[i]);
    release_list(first); release_list(second);
}

static void capacity_parity(void) {
    const long long lengths[] = {0,1,2,3,4,7,8,15,16,31,32,2047,2048,2049,4095,4096,4097,16383,16384,16385,65537};
    for (size_t c = 0; c < sizeof(lengths) / sizeof(*lengths); ++c) {
        MinyarList *bulk = minyar_list_new(), *individual = minyar_list_new();
        minyar_list_append_scalars(bulk, generated, lengths[c]);
        for (long long i = 0; i < lengths[c]; ++i) minyar_list_add(individual, generated[i]);
        assert(bulk->length == lengths[c] && individual->length == lengths[c]);
        assert(bulk->capacity == individual->capacity);
        for (long long i = 0; i < lengths[c]; ++i) {
            assert(minyar_list_get(bulk, i) == i % 2001 - 1000);
            assert(minyar_list_get(individual, i) == i % 2001 - 1000);
        }
        /* Appending again covers nonempty prefixes and growth boundaries. */
        minyar_list_append_scalars(bulk, constants, 7);
        for (long long i = 0; i < 7; ++i) minyar_list_add(individual, constants[i]);
        assert(bulk->length == lengths[c] + 7 && bulk->capacity == individual->capacity);
        for (long long i = 0; i < lengths[c]; ++i) assert(minyar_list_get(bulk, i) == i % 2001 - 1000);
        for (long long i = 0; i < 7; ++i) assert(minyar_list_get(bulk, lengths[c] + i) == constants[i]);
        release_list(bulk); release_list(individual);
    }
}

#ifdef LIST_LITERAL_FAULTS
static MinyarList *failure_list;
static long long *failure_values;
static long long failure_length, failure_capacity;
static void verify_failure_preserved(void) {
    assert(fault_fired == 1);
    assert(failure_list->values == failure_values);
    assert(failure_list->length == failure_length && failure_list->capacity == failure_capacity);
    for (long long i = 0; i < failure_length; ++i) assert(failure_list->values[i] == constants[i]);
    assert(constants[0] == LLONG_MIN && constants[6] == LLONG_MAX);
    puts("old-list-preserved");
}
static void fail_allocation(int resizing) {
    failure_list = minyar_list_new();
    if (resizing) minyar_list_append_scalars(failure_list, constants, 7);
    failure_values = failure_list->values;
    failure_length = failure_list->length; failure_capacity = failure_list->capacity;
    assert(atexit(verify_failure_preserved) == 0);
    if (resizing) fault_resize_index = fault_resizes + 1;
    else fault_allocation_index = fault_allocations + 1;
    minyar_list_append_scalars(failure_list, generated, 100000);
    abort();
}
#endif

int main(int argc, char **argv) {
    assert(argc == 2);
    initialize_source();
    if (!strcmp(argv[1], "normal")) {
        copies_and_prefixes(); capacity_parity(); cleanup(); puts("copies-prefixes-capacities-ok"); return 0;
    }
    if (!strcmp(argv[1], "one-reserve")) {
        one_reserve(); cleanup(); puts("one-reserve-ok"); return 0;
    }
#ifdef LIST_LITERAL_FAULTS
    if (!strcmp(argv[1], "fail-fresh")) fail_allocation(0);
    if (!strcmp(argv[1], "fail-resize")) fail_allocation(1);
#endif
    /* Synthetic headers make arithmetic failure deterministic and avoid any
     * physical huge allocation; each must fail before touching NULL data. */
    MinyarList synthetic = {NULL, 0, 0};
    if (!strcmp(argv[1], "negative-count")) minyar_list_append_scalars(&synthetic, NULL, -1);
    else if (!strcmp(argv[1], "negative-length")) { synthetic.length = -1; minyar_list_append_scalars(&synthetic, NULL, 0); }
    else if (!strcmp(argv[1], "count-overflow")) { synthetic.length = LLONG_MAX; minyar_list_append_scalars(&synthetic, NULL, 1); }
    else if (!strcmp(argv[1], "byte-overflow")) minyar_list_append_scalars(&synthetic, NULL, (long long)(SIZE_MAX / sizeof(long long)) + 1);
    else if (!strcmp(argv[1], "negative-capacity")) { synthetic.capacity = -1; list_reserve(&synthetic, 1); }
    else if (!strcmp(argv[1], "negative-reserve")) list_reserve(&synthetic, -1);
    else if (!strcmp(argv[1], "growth-overflow")) { synthetic.capacity = LLONG_MAX / 2 + 1; list_reserve(&synthetic, synthetic.capacity + 1); }
    else if (!strcmp(argv[1], "reserve-byte-overflow")) list_reserve(&synthetic, (long long)(SIZE_MAX / sizeof(long long)) + 1);
    else if (!strcmp(argv[1], "grow-maximum")) { synthetic.capacity = LLONG_MAX; list_grow(&synthetic); }
    else abort();
    abort();
}
