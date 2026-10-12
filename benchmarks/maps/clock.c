#define _POSIX_C_SOURCE 200809L
#include <time.h>
#include <stdint.h>
long long minyar_mapbench_tick(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (long long)t.tv_sec * INT64_C(1000000000) + t.tv_nsec;
}
