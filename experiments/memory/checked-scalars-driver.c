/* Native package driver: the generated Minyar main enters through this ABI. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#define _POSIX_C_SOURCE 200809L
#ifdef __APPLE__
#define _DARWIN_C_SOURCE
#endif
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#ifdef MINYAR_SCALAR_ACCOUNTING
static size_t scalar_system_operations;
static int scalar_active;
static void *checked_malloc(size_t n) {
    if (scalar_active)
        scalar_system_operations++;
    return malloc(n);
}
static void *checked_realloc(void *p, size_t n) {
    if (scalar_active)
        scalar_system_operations++;
    return realloc(p, n);
}
static void checked_free(void *p) {
    if (scalar_active && p)
        scalar_system_operations++;
    free(p);
}
#define malloc checked_malloc
#define realloc checked_realloc
#define free checked_free
#define MINYAR_RC_TESTING
#endif
#include "../../runtime/minyar_runtime.c"
#ifdef MINYAR_SCALAR_ACCOUNTING
#undef malloc
#undef realloc
#undef free
#endif

#include "../../tests/llvm_symbols.h"

extern long long checkedScalarShift(long long, long long)
    MINYAR_TEST_LANGUAGE_SYMBOL(checkedScalarShift);
extern long long checkedScalarCharacter(long long, long long)
    MINYAR_TEST_LANGUAGE_SYMBOL(checkedScalarCharacter);
extern long long checkedScalarFloat(long long, long long)
    MINYAR_TEST_LANGUAGE_SYMBOL(checkedScalarFloat);
extern long long checkedScalarAbsClamp(long long, long long)
    MINYAR_TEST_LANGUAGE_SYMBOL(checkedScalarAbsClamp);
extern long long cppScalarShift(long long, long long);
extern long long cppScalarCharacter(long long, long long);
extern long long cppScalarFloat(long long, long long);
extern long long cppScalarAbsClamp(long long, long long);

static uint64_t ticks(clockid_t which) {
    struct timespec value;
    assert(!clock_gettime(which, &value));
    return (uint64_t)value.tv_sec * 1000000000u + (uint64_t)value.tv_nsec;
}

long long minyar_checked_scalars_runScalarStudy(void) {
    assert(minyar_argument_count() == 4);
    MinyarText *arguments[4];
    for (int i = 0; i < 4; i++)
        arguments[i] = minyar_argument(i);
    const char *language = (const char *)arguments[0]->bytes;
    const char *kind = (const char *)arguments[1]->bytes;
    long long count = strtoll((const char *)arguments[2]->bytes, NULL, 10);
    long long seed = strtoll((const char *)arguments[3]->bytes, NULL, 10);
    assert(count >= 0 && count <= 100000000 && seed >= 0 && seed < 1000003);
    int cpp = !strcmp(language, "cpp");
    assert(cpp || !strcmp(language, "minyar"));
    long long (*function)(long long, long long) = NULL;
    if (!strcmp(kind, "shift"))
        function = cpp ? cppScalarShift : checkedScalarShift;
    if (!strcmp(kind, "character"))
        function = cpp ? cppScalarCharacter : checkedScalarCharacter;
    if (!strcmp(kind, "float"))
        function = cpp ? cppScalarFloat : checkedScalarFloat;
    if (!strcmp(kind, "abs-clamp"))
        function = cpp ? cppScalarAbsClamp : checkedScalarAbsClamp;
    assert(function);
    for (int i = 0; i < 4; i++)
        minyar_rc_release(arguments[i]);
#ifdef MINYAR_BOUNDED_HEAP
    while (rc_pending_count)
        minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
#endif
#ifdef MINYAR_SCALAR_ACCOUNTING
    size_t objects_before = rc_object_count, bytes_before = rc_bytes;
    RcFrame *frames_before = rc_frames;
#ifdef MINYAR_BOUNDED_HEAP
    size_t allocations_before = minyar_pool_allocation_count;
#endif
    scalar_active = 1;
#endif
    uint64_t cpu_start = ticks(CLOCK_THREAD_CPUTIME_ID), wall_start = ticks(CLOCK_MONOTONIC);
    long long result = function(count, seed);
    uint64_t wall = ticks(CLOCK_MONOTONIC) - wall_start;
    uint64_t cpu = ticks(CLOCK_THREAD_CPUTIME_ID) - cpu_start;
#ifdef MINYAR_SCALAR_ACCOUNTING
    size_t system_operations = 0, pool_allocations = 0;
    scalar_active = 0;
    system_operations = scalar_system_operations;
#ifdef MINYAR_BOUNDED_HEAP
    pool_allocations = minyar_pool_allocation_count - allocations_before;
#endif
    assert(!system_operations && !pool_allocations);
    assert(rc_object_count == objects_before && rc_bytes == bytes_before);
    assert(!rc_pending_count && rc_frames == frames_before);
    /* Prove the allocation monitor observes a real runtime allocation. */
    scalar_active = 1;
    void *control = minyar_record_new_scalar(2);
    minyar_rc_release(control);
    scalar_active = 0;
#ifdef MINYAR_BOUNDED_HEAP
    assert(minyar_pool_allocation_count > allocations_before);
    while (rc_pending_count)
        minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
#else
    assert(scalar_system_operations > system_operations);
#endif
#endif
    printf("{\"result\":%lld,\"wall_ns\":%llu,\"cpu_ns\":%llu,", result, (unsigned long long)wall,
           (unsigned long long)cpu);
#ifdef MINYAR_SCALAR_ACCOUNTING
    printf("\"system_operations\":%zu,\"pool_allocations\":%zu,"
           "\"allocation_monitoring\":true}\n",
           system_operations, pool_allocations);
#else
    puts("\"system_operations\":null,\"pool_allocations\":null,"
         "\"allocation_monitoring\":false}");
#endif
    return 0;
}
