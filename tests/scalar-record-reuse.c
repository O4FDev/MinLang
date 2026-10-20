/* The runner substitutes the ordinary/cycle engine at this include. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static size_t allocation_requests;
static void *counted_malloc(size_t bytes) { allocation_requests++; return malloc(bytes); }
static void *counted_calloc(size_t count, size_t bytes) {
    allocation_requests++;
    return calloc(count, bytes);
}
static void *counted_realloc(void *pointer, size_t bytes) {
    allocation_requests++;
    return realloc(pointer, bytes);
}
#define malloc counted_malloc
#define calloc counted_calloc
#define realloc counted_realloc
#define MINYAR_RC_TESTING 1
#define MINYAR_INTEGER_TEXT_CACHE_LIMIT 0
#define MINYAR_SYSTEM_SMALL_HEAP 0
#include "../runtime/minyar_runtime.c"
#undef malloc
#undef calloc
#undef realloc

static size_t allocations(void) {
#ifdef MINYAR_BOUNDED_HEAP
    return minyar_pool_allocation_count;
#else
    return allocation_requests;
#endif
}

static void drain(void) {
#ifndef MINYAR_COMPILER_ARENA
#ifdef MINYAR_BOUNDED_RC
    size_t steps = 0;
    while (rc_pending_count) {
        minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
        assert(rc_bounded_last_work <= MINYAR_RC_POLL_BUDGET);
        assert(++steps < 100000);
    }
#else
    minyar_rc_release(NULL);
#endif
    assert(rc_object_count == 0 && rc_bytes == 0 && rc_pending_count == 0);
#ifdef MINYAR_SYSTEM_HEAP
    assert(rc_heap_allocation_count == 0);
#elif defined(MINYAR_BOUNDED_HEAP)
    assert(minyar_pool_used == 0);
    assert(minyar_pool_mask == ((size_t)1 << minyar_pool_max_order));
    assert(minyar_pool_free[minyar_pool_max_order] == (PoolLink *)minyar_pool);
#endif
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
    assert(!rc_cycle_pending && !rc_cycle_head && !rc_cycle_known_head);
#endif
#endif
}

static void fresh(MinyarRecord *record, long long fields) {
    assert(record && record->length == fields);
    for (long long field = 0; field < fields; field++)
        assert(minyar_record_get(record, field) == 0);
#ifndef MINYAR_COMPILER_ARENA
    assert(((RcObject *)record - 1)->ownership == (8 | RC_SCALAR_RECORD));
#endif
}

static void unique_and_shared(void) {
    MinyarRecord *old = minyar_record_new_scalar(2);
    minyar_record_set_scalar(old, 0, LLONG_MIN);
    minyar_record_set_scalar(old, 1, LLONG_MAX);
    long long first = minyar_record_get(old, 0), second = minyar_record_get(old, 1);
    size_t before = allocations();
    MinyarRecord *next = minyar_record_reuse_scalar_take(old, 2);
#ifdef MINYAR_COMPILER_ARENA
    assert(next != old);
    fresh(next, 2);
    assert(minyar_record_get(old, 0) == first && minyar_record_get(old, 1) == second);
#else
    assert(next == old && allocations() == before);
    assert(minyar_record_get(next, 0) == first && minyar_record_get(next, 1) == second);
#endif
    minyar_record_set_scalar(next, 0, second);
    minyar_record_set_scalar(next, 1, first);
    assert(minyar_record_get(next, 0) == LLONG_MAX && minyar_record_get(next, 1) == LLONG_MIN);
    for (long long index = 0; index < 1000; index++) {
        uintptr_t address = (uintptr_t)next;
        before = allocations();
        next = minyar_record_reuse_scalar_take(next, 2);
#ifndef MINYAR_COMPILER_ARENA
        assert((uintptr_t)next == address && allocations() == before);
#else
        assert((uintptr_t)next != address);
#endif
        minyar_record_set_scalar(next, 0, index);
        minyar_record_set_scalar(next, 1, -index);
    }
    minyar_rc_release(next);
    drain();

    old = minyar_record_new_scalar(2);
    minyar_record_set_scalar(old, 0, 73);
    minyar_rc_retain(old);
    before = allocations();
    next = minyar_record_reuse_scalar_take(old, 2);
    assert(next != old && minyar_record_get(old, 0) == 73);
    fresh(next, 2);
#ifndef MINYAR_COMPILER_ARENA
    assert(allocations() == before + 1);
    assert((((RcObject *)old - 1)->ownership >> 3) == 1);
#endif
    minyar_record_set_scalar(next, 0, 19);
    assert(minyar_record_get(old, 0) == 73 && minyar_record_get(next, 0) == 19);
    minyar_rc_release(old);
    minyar_rc_release(next);
    drain();
}

static void fallback_kinds(void) {
    MinyarRecord *old = minyar_record_new_scalar(3);
    uintptr_t address = (uintptr_t)old;
    size_t before = allocations();
    MinyarRecord *next = minyar_record_reuse_scalar_take(old, 2);
    assert((uintptr_t)next != address);
    fresh(next, 2);
#ifndef MINYAR_COMPILER_ARENA
    assert(allocations() == before + 1);
#endif
    minyar_rc_release(next);
    drain();

    old = minyar_record_new(2);
    MinyarText *child = minyar_native_copy_text((const unsigned char *)"child", 5);
    minyar_record_set_take(old, 0, (long long)(uintptr_t)child);
    address = (uintptr_t)old;
    next = minyar_record_reuse_scalar_take(old, 2);
    assert((uintptr_t)next != address);
    fresh(next, 2);
    minyar_rc_release(next);
    drain();

    MinyarText *text = minyar_native_copy_text((const unsigned char *)"not a record", 12);
    address = (uintptr_t)text;
    next = minyar_record_reuse_scalar_take((MinyarRecord *)text, 2);
    assert((uintptr_t)next != address);
    fresh(next, 2);
    minyar_rc_release(next);
    drain();

    MinyarBytes *native = minyar_c_record_new(16);
    address = (uintptr_t)native;
    next = minyar_record_reuse_scalar_take((MinyarRecord *)native, 2);
    assert((uintptr_t)next != address);
    fresh(next, 2);
    minyar_rc_release(next);
    drain();

    static const struct { size_t ownership; long long length, values[2]; } immortal =
        {5, 2, {17, 29}};
    next = minyar_record_reuse_scalar_take((MinyarRecord *)&immortal.length, 2);
    fresh(next, 2);
    assert(immortal.ownership == 5 && immortal.values[0] == 17 && immortal.values[1] == 29);
    minyar_rc_release(next);
    drain();

    next = minyar_record_reuse_scalar_take(NULL, 0);
    fresh(next, 0);
    old = next;
    next = minyar_record_reuse_scalar_take(old, 0);
#ifndef MINYAR_COMPILER_ARENA
    assert(next == old);
#else
    assert(next != old);
#endif
    minyar_rc_release(next);
    drain();

#if defined(MINYAR_CYCLE_LOCAL_PROOFS) && !defined(MINYAR_COMPILER_ARENA)
    old = minyar_record_new_traced(2);
    minyar_record_set_reference_traced(old, 0, (long long)(uintptr_t)old);
    address = (uintptr_t)old;
    next = minyar_record_reuse_scalar_take(old, 2);
    assert((uintptr_t)next != address);
    fresh(next, 2);
    minyar_rc_release(next);
    drain();
#endif
}

#ifndef MINYAR_COMPILER_ARENA
/* Prepare every input before introducing debt, so constructor polls cannot
 * accidentally satisfy the service assertion intended for the new helper. */
static MinyarRecord *input(int mode, void **alias) {
    *alias = NULL;
    if (mode == 4)
        return (MinyarRecord *)minyar_native_copy_text((const unsigned char *)"text", 4);
    if (mode == 5) return NULL;
    if (mode == 3) return minyar_record_new(2);
#if defined(MINYAR_CYCLE_LOCAL_PROOFS)
    if (mode == 6) return minyar_record_new_traced(2);
#endif
    MinyarRecord *record = minyar_record_new_scalar(mode == 2 ? 3 : 2);
    minyar_record_set_scalar(record, 0, 83);
    if (mode == 1) {
        minyar_rc_retain(record);
        *alias = record;
    }
    return record;
}

static void pending_objects(void) {
    for (int mode = 0; mode < 6; mode++) {
        void *alias;
        MinyarRecord *old = input(mode, &alias);
        MinyarRecord *pending = minyar_record_new(4096);
        rc_drop(pending);
        assert(rc_pending_count > 0);
        MinyarRecord *next = minyar_record_reuse_scalar_take(old, 2);
        assert(next->length == 2);
        if (mode == 0) assert(next == old && minyar_record_get(next, 0) == 83);
        if (alias) assert(minyar_record_get(alias, 0) == 83);
#ifdef MINYAR_BOUNDED_RC
        assert(rc_bounded_last_work <= MINYAR_RC_POLL_BUDGET);
        size_t expected = 2 * MINYAR_RC_POLL_BUDGET;
        if (mode == 2 || mode == 4) expected--;
        if (mode == 5) expected = MINYAR_RC_POLL_BUDGET;
        if (mode != 3) assert(rc_bounded_cursor == expected);
        assert(rc_bounded_cursor > 0 && rc_bounded_cursor <= 2 * MINYAR_RC_POLL_BUDGET);
#else
        assert(rc_pending_count == (mode == 5 ? 1 : 0));
#endif
        if (alias) minyar_rc_release(alias);
        minyar_rc_release(next);
        drain();
    }
}

#ifdef MINYAR_CYCLE_LOCAL_PROOFS
static void pending_cycles(void) {
    for (int mode = 0; mode < 7; mode++) {
        void *alias;
        MinyarRecord *old = input(mode, &alias);
        MinyarRecord *ring = minyar_record_new_traced(512);
        minyar_record_set_reference_traced(ring, 0, (long long)(uintptr_t)ring);
        rc_drop(ring);
        assert(rc_cycle_pending);
        size_t before = rc_cycle_units;
        MinyarRecord *next = minyar_record_reuse_scalar_take(old, 2);
        size_t work = rc_cycle_units - before;
#ifdef MINYAR_BOUNDED_RC
        assert(work > 0 && work <= 2 * MINYAR_RC_POLL_BUDGET);
        assert(rc_bounded_last_work <= MINYAR_RC_POLL_BUDGET);
#else
        if (mode == 5) assert(work == 0);
        else assert(work > 0 && work <= 32);
#endif
        if (alias) minyar_rc_release(alias);
        minyar_rc_release(next);
        drain();
    }
}
#endif
#endif

int main(int argc, char **argv) {
    if (argc > 1) {
        MinyarRecord *old = minyar_record_new_scalar(0);
        long long count = -1;
        if (!strcmp(argv[1], "overflow")) count = LLONG_MAX;
        if (!strcmp(argv[1], "bytes")) count = (long long)(SIZE_MAX / sizeof(long long));
        minyar_record_reuse_scalar_take(old, count);
        return 2;
    }
    unique_and_shared();
    fallback_kinds();
#ifndef MINYAR_COMPILER_ARENA
    pending_objects();
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
    pending_cycles();
#endif
#endif
    puts("Scalar record reuse: identity, copying, owners and cleanup passed");
    return 0;
}

