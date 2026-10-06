/* Source-level append/copy work, separately from managed request/poll events. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#include <assert.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int research_phase;
static size_t research_adds, research_takes, research_copies, research_copy_bytes;
static size_t research_retains, research_guard_pending;
static size_t events[512][5], event_count;
static void research_event(size_t kind, size_t a, size_t b, size_t c, size_t d) {
    if (!research_phase)
        return;
    assert(event_count < 512);
    size_t *event = events[event_count++];
    event[0] = kind;
    event[1] = a;
    event[2] = b;
    event[3] = c;
    event[4] = d;
}
static void *research_copy(void *target, const void *source, size_t size) {
    if (research_phase) {
        research_copies++;
        research_copy_bytes += size;
    }
    return memcpy(target, source, size);
}
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
#undef memcpy
#define memcpy research_copy
#include "../runtime/minyar_runtime.c"
#undef memcpy
#include "memory-research-list-bulk-pressure.h"
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

static void check_reference_edges(int take) {
    MinyarList *empty = minyar_list_new();
    minyar_list_references(empty);
    MinyarList *null_tail = minyar_list_appended(empty, 0, 1, take);
    assert(!empty->length && null_tail->length == 1 && !null_tail->values[0]);
    minyar_rc_release(empty);
    minyar_rc_release(null_tail);
    drain();

    static struct {
        RcObject owner;
        MinyarText value;
    } literal = {{RC_TEXT}, {(const unsigned char *)"immortal", 8, 8, NULL, NULL}};
    MinyarList *immortals = minyar_list_new();
    minyar_list_references(immortals);
    minyar_list_add(immortals, (long long)(uintptr_t)&literal.value);
    minyar_list_add(immortals, 0);
    MinyarList *immortal_tail =
        minyar_list_appended(immortals, (long long)(uintptr_t)&literal.value, 1, take);
    assert(immortal_tail->length == 3 && !immortal_tail->values[1]);
    assert(literal.owner.ownership == RC_TEXT);
    minyar_rc_release(immortals);
    minyar_rc_release(immortal_tail);
    drain();

    MinyarText *shared = copy_c_text("tail aliases source member");
    MinyarList *source = minyar_list_new();
    minyar_list_references(source);
    minyar_list_add(source, (long long)(uintptr_t)shared);
    minyar_list_add(source, (long long)(uintptr_t)shared);
    if (take)
        minyar_rc_retain(shared);
    MinyarList *result = minyar_list_appended(source, (long long)(uintptr_t)shared, 1, take);
    assert((((RcObject *)shared - 1)->ownership >> 3) == 6);
    minyar_rc_release(source);
    minyar_rc_release(shared);
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count)
        assert(minyar_rc_poll(1) == 1);
#endif
    assert((((RcObject *)shared - 1)->ownership >> 3) == 3);
    for (int i = 0; i < 3; i++)
        assert(result->values[i] == (long long)(uintptr_t)shared);
    minyar_rc_release(result);
    drain();
}

#ifdef MINYAR_BOUNDED_RC
static void check_debt_schedule(void) {
    MinyarList *source = minyar_list_new();
    for (int i = 0; i < 31; i++)
        minyar_list_add(source, i * 37);
    rc_drop(minyar_record_new(2 * MINYAR_RC_POLL_BUDGET));
    size_t resizes = resize_calls;
    MinyarList *result = minyar_list_appended(source, 313, 0, 0);
    assert(!rc_pending_count && rc_object_count == 2);
    assert(result->length == 32 && result->values[31] == 313);
#ifdef MINYAR_SYSTEM_HEAP
    /* Pending retirement retains the original four realloc service hooks. */
    assert(resize_calls - resizes == 4);
#else
    (void)resizes;
#endif
    minyar_rc_release(source);
    minyar_rc_release(result);
    drain();
}
#endif

int main(int argc, char **argv) {
    setvbuf(stdout, NULL, _IONBF, 0);
    atexit(research_emit);
    if (argc == 2) {
        if (!strcmp(argv[1], "overflow")) {
            MinyarList empty = {NULL, LLONG_MAX, 0};
            research_begin();
            minyar_list_appended(&empty, 1, 0, 0);
        } else if (!strcmp(argv[1], "oom-object") || !strcmp(argv[1], "oom-data")) {
            MinyarList *source = minyar_list_new();
            fail_allocation = allocation_calls + (!strcmp(argv[1], "oom-object") ? 1 : 2);
            research_begin();
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
    check_reference_edges(0);
    check_reference_edges(1);
#ifdef MINYAR_BOUNDED_RC
    check_debt_schedule();
#endif
    puts("known-length append allocation, contents, policy and ownership verified");
    return 0;
}
