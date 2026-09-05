#define _POSIX_C_SOURCE 200809L
#ifdef __APPLE__
#define _DARWIN_C_SOURCE
#endif
#include <assert.h>
#include <time.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>

#ifdef MINYAR_CRITICAL_ACCOUNTING
static size_t critical_system_operations;
static int critical_active;
static void *checked_malloc(size_t n) {
    if (critical_active) critical_system_operations++;
    return malloc(n);
}
static void *checked_realloc(void *p, size_t n) {
    if (critical_active) critical_system_operations++;
    return realloc(p, n);
}
static void checked_free(void *p) {
    if (critical_active && p) critical_system_operations++;
    free(p);
}
#define malloc checked_malloc
#define realloc checked_realloc
#define free checked_free
#define MINYAR_RC_TESTING
#endif
#ifndef MINYAR_RUNTIME_SOURCE
#define MINYAR_RUNTIME_SOURCE "../../runtime/minyar_runtime.c"
#endif
#include MINYAR_RUNTIME_SOURCE
#ifdef MINYAR_CRITICAL_ACCOUNTING
#undef malloc
#undef realloc
#undef free
#endif

extern long long criticalArithmetic(long long, long long);
extern long long criticalBook(MinyarList *, long long, long long);
extern long long criticalRecords(long long, long long);
extern long long cppArithmetic(long long, long long);
extern long long cppBook(MinyarList *, long long, long long);
extern long long cppRecords(long long, long long);

static uint64_t ticks(clockid_t which) {
    struct timespec value;
    assert(!clock_gettime(which, &value));
    return (uint64_t)value.tv_sec * 1000000000u + (uint64_t)value.tv_nsec;
}

int main(int argc, char **argv) {
    assert(argc == 5);
    long long count = strtoll(argv[3], NULL, 10), seed = strtoll(argv[4], NULL, 10);
    assert(count >= 0 && count <= 100000000 && seed >= 0 && seed < 1000003);
    int cpp = !strcmp(argv[1], "cpp");
    assert(cpp || !strcmp(argv[1], "minyar"));
    int arithmetic = !strcmp(argv[2], "arithmetic"), book_path = !strcmp(argv[2], "book");
    assert(arithmetic || book_path || !strcmp(argv[2], "records"));
    MinyarList *book = minyar_list_new();
    for (int i = 0; i < 257; i++) minyar_list_add(book, i);
#ifdef MINYAR_BOUNDED_HEAP
    while (rc_pending_count) minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
#endif
#ifdef MINYAR_CRITICAL_ACCOUNTING
    size_t objects_before = rc_object_count, bytes_before = rc_bytes;
#ifdef MINYAR_BOUNDED_HEAP
    size_t allocations_before = minyar_pool_allocation_count;
#endif
    critical_active = 1;
#endif
    uint64_t cpu_start = ticks(CLOCK_THREAD_CPUTIME_ID), wall_start = ticks(CLOCK_MONOTONIC);
    long long result;
    if (arithmetic) result = cpp ? cppArithmetic(count, seed) : criticalArithmetic(count, seed);
    else if (book_path) result = cpp ? cppBook(book, count, seed) : criticalBook(book, count, seed);
    else result = cpp ? cppRecords(count, seed) : criticalRecords(count, seed);
    uint64_t wall = ticks(CLOCK_MONOTONIC) - wall_start;
    uint64_t cpu = ticks(CLOCK_THREAD_CPUTIME_ID) - cpu_start;
    size_t system_operations = 0, pool_allocations = 0;
#ifdef MINYAR_CRITICAL_ACCOUNTING
    critical_active = 0;
    system_operations = critical_system_operations;
#ifdef MINYAR_BOUNDED_HEAP
    pool_allocations = minyar_pool_allocation_count - allocations_before;
#endif
    assert(!system_operations && !pool_allocations);
    assert(rc_object_count == objects_before && rc_bytes == bytes_before);
    assert(!rc_pending_count && !rc_frames);
    // Prove that the allocator monitor is live, using a real runtime object.
    critical_active = 1;
    void *control = minyar_record_new_scalar(2);
    minyar_rc_release(control);
    critical_active = 0;
#ifdef MINYAR_BOUNDED_HEAP
    assert(minyar_pool_allocation_count > allocations_before);
#else
    assert(critical_system_operations > system_operations);
#endif
#endif
    printf("{\"result\":%lld,\"wall_ns\":%llu,\"cpu_ns\":%llu,"
           "\"system_operations\":%zu,\"pool_allocations\":%zu,\"values\":[",
           result, (unsigned long long)wall, (unsigned long long)cpu,
           system_operations, pool_allocations);
    for (int i = 0; i < 257; i++) printf("%s%lld", i ? "," : "", book->values[i]);
    puts("]}");
    minyar_rc_release(book);
#ifdef MINYAR_BOUNDED_HEAP
    while (rc_pending_count) minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
#endif
#ifdef MINYAR_CRITICAL_ACCOUNTING
    assert(!rc_object_count && !rc_bytes);
#endif
}
