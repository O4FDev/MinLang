#if defined(__linux__) && !defined(_POSIX_C_SOURCE)
#define _POSIX_C_SOURCE 200809L
#endif
#ifndef MINYAR_RESEARCH_RUNTIME
#define MINYAR_RESEARCH_RUNTIME "../runtime/minyar_runtime.c"
#endif
#include MINYAR_RESEARCH_RUNTIME
#include <time.h>

static uint64_t nanoseconds(clockid_t clock) {
    struct timespec value;
    if (clock_gettime(clock, &value))
        abort();
    return (uint64_t)value.tv_sec * 1000000000 + (uint64_t)value.tv_nsec;
}

int main(int argc, char **argv) {
    if (argc != 4)
        return 2;
    long long length = strtoll(argv[1], NULL, 10);
    long long iterations = strtoll(argv[2], NULL, 10);
    int append = !strcmp(argv[3], "append");
    if (length < 1 || length > 100000 || iterations < 1 || iterations > 1000000)
        return 2;
    MinyarList *source = minyar_list_new();
    for (long long i = 0; i < length; i++)
        minyar_list_add(source, i * 37);
    uint64_t sum = 0, cpu = nanoseconds(CLOCK_PROCESS_CPUTIME_ID),
             wall = nanoseconds(CLOCK_MONOTONIC);
    for (long long iteration = 0; iteration < iterations; iteration++) {
        MinyarList *result;
        if (append) {
            result = minyar_list_appended(source, iteration, 0, 0);
        } else {
            result = minyar_list_new();
            for (long long i = 0; i < length; i++)
                minyar_list_add(result, i * 37);
        }
        sum += (uint64_t)result->values[result->length - 1] + (uint64_t)result->values[0];
        minyar_rc_release(result);
    }
    uint64_t elapsed_wall = nanoseconds(CLOCK_MONOTONIC) - wall;
    uint64_t elapsed_cpu = nanoseconds(CLOCK_PROCESS_CPUTIME_ID) - cpu;
    minyar_rc_release(source);
    printf("{\"cpu_ns\":%llu,\"wall_ns\":%llu,\"checksum\":%llu}\n",
           (unsigned long long)elapsed_cpu, (unsigned long long)elapsed_wall,
           (unsigned long long)sum);
    return 0;
}
