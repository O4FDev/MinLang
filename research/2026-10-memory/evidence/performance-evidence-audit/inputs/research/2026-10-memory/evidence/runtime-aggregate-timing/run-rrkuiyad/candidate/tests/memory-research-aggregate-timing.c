/* No allocation/work counters. Process clocks cover construction and cleanup. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#include "../runtime/minyar_runtime.c"
#include "../runtime/minyar_stack_frames.h"
#include <sys/resource.h>
#include <time.h>
static uint64_t started_cpu, started_wall, started_user, started_system;
static uint64_t nanoseconds(clockid_t clock) {
    struct timespec value;
    if (clock_gettime(clock, &value))
        abort();
    return (uint64_t)value.tv_sec * 1000000000 + (uint64_t)value.tv_nsec;
}
static uint64_t cpu_time(struct timeval value) {
    return (uint64_t)value.tv_sec * 1000000000 + (uint64_t)value.tv_usec * 1000;
}
__attribute__((constructor)) static void begin(void) {
    struct rusage usage;
    if (getrusage(RUSAGE_SELF, &usage))
        abort();
    started_user = cpu_time(usage.ru_utime);
    started_system = cpu_time(usage.ru_stime);
    started_cpu = nanoseconds(CLOCK_PROCESS_CPUTIME_ID);
    started_wall = nanoseconds(CLOCK_MONOTONIC);
}
__attribute__((destructor)) static void finish(void) {
    struct rusage usage;
    if (getrusage(RUSAGE_SELF, &usage))
        abort();
    fprintf(stderr,
            "{\"cpu_ns\":%llu,\"wall_ns\":%llu,\"user_ns\":%llu,\"system_ns\":%llu,"
            "\"maxrss_platform_units\":%ld}\n",
            (unsigned long long)(nanoseconds(CLOCK_PROCESS_CPUTIME_ID) - started_cpu),
            (unsigned long long)(nanoseconds(CLOCK_MONOTONIC) - started_wall),
            (unsigned long long)(cpu_time(usage.ru_utime) - started_user),
            (unsigned long long)(cpu_time(usage.ru_stime) - started_system), usage.ru_maxrss);
}
