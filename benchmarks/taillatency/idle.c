/* Idle-time cleanup for cache.min: service queued ownership cleanup until none
 * is pending or the monotonic deadline passes. minyar_rc_poll is the runtime's
 * public service point; it performs at most the configured budget per call. */
#define _POSIX_C_SOURCE 200809L
#include <stddef.h>
#include <stdint.h>
#include <time.h>

/* Weak: the eager profile frees immediately and has no queued work to poll. */
__attribute__((weak)) size_t minyar_rc_poll(size_t budget);

static long long tailidle_now(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (long long)t.tv_sec * INT64_C(1000000000) + t.tv_nsec;
}

long long minyar_tailidle_releaseIdle(long long deadline) {
    long long work = 0;
    if (!minyar_rc_poll) return 0;
    for (;;) {
        for (int i = 0; i < 16; i++) {
            size_t done = minyar_rc_poll(1024);
            if (!done) return work;
            work += (long long)done;
        }
        if (tailidle_now() >= deadline) return work;
    }
}
