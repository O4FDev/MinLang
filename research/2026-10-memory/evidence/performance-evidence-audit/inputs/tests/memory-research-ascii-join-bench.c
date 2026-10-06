/* Uninstrumented generated-program timing, including construction and output. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#include "../runtime/minyar_runtime.c"
#include "../runtime/minyar_stack_frames.h"
#include <time.h>

static uint64_t start_cpu, start_wall;

static uint64_t nanoseconds(clockid_t clock) {
    struct timespec value;
    if (clock_gettime(clock, &value))
        abort();
    return (uint64_t)value.tv_sec * 1000000000 + (uint64_t)value.tv_nsec;
}

__attribute__((constructor)) static void start_measurement(void) {
    start_cpu = nanoseconds(CLOCK_PROCESS_CPUTIME_ID);
    start_wall = nanoseconds(CLOCK_MONOTONIC);
}

__attribute__((destructor)) static void report_measurement(void) {
    uint64_t wall = nanoseconds(CLOCK_MONOTONIC) - start_wall;
    uint64_t cpu = nanoseconds(CLOCK_PROCESS_CPUTIME_ID) - start_cpu;
    struct timespec resolution;
    if (clock_getres(CLOCK_PROCESS_CPUTIME_ID, &resolution))
        abort();
    fprintf(stderr, "{\"cpu_ns\":%llu,\"wall_ns\":%llu,\"cpu_resolution_ns\":%llu}\n",
            (unsigned long long)cpu, (unsigned long long)wall,
            (unsigned long long)((uint64_t)resolution.tv_sec * 1000000000 + resolution.tv_nsec));
}
