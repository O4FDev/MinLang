// C peer for main.min: Collatz step sum and hash histogram over 4 pthreads,
// chunks of indices interleaved across threads, per-thread partial results.
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

enum { THREADS = 4, BUCKETS = 16, CHUNK = 4096 };
static int64_t count, samples;
static int32_t *steps;
static int64_t partial_steps[THREADS];
static int64_t partial_bins[THREADS][BUCKETS];

static int32_t collatz_steps(uint64_t value) {
    int32_t n = 0;
    while (value != 1) { value = (value & 1) ? 3 * value + 1 : value >> 1; n++; }
    return n;
}

static int64_t mix(int64_t value) {
    for (int64_t round = 0; round < 4; round++) {
        value ^= value >> 31;
        value = (int64_t)((uint64_t)value * 0x2545F4914F6CDD1DULL);
        value ^= value >> 29;
        value = (int64_t)((uint64_t)value + (uint64_t)round);
    }
    return value;
}

static void *collatz_worker(void *arg) {
    long t = (long)arg; int64_t sum = 0;
    for (int64_t first = t * CHUNK; first < count; first += THREADS * CHUNK) {
        int64_t last = first + CHUNK < count ? first + CHUNK : count;
        for (int64_t i = first; i < last; i++) { steps[i] = collatz_steps((uint64_t)i + 1); sum += steps[i]; }
    }
    partial_steps[t] = sum;
    return NULL;
}

static void *histogram_worker(void *arg) {
    long t = (long)arg; int64_t bins[BUCKETS] = {0};
    for (int64_t first = t * CHUNK; first < samples; first += THREADS * CHUNK) {
        int64_t last = first + CHUNK < samples ? first + CHUNK : samples;
        for (int64_t s = first; s < last; s++) bins[(mix(s) >> 11) & 15]++;
    }
    for (int b = 0; b < BUCKETS; b++) partial_bins[t][b] = bins[b];
    return NULL;
}

static void run(void *(*worker)(void *)) {
    pthread_t threads[THREADS];
    for (long t = 0; t < THREADS; t++) pthread_create(&threads[t], NULL, worker, (void *)t);
    for (int t = 0; t < THREADS; t++) pthread_join(threads[t], NULL);
}

int main(int argc, char **argv) {
    count = atoll(argv[1]);
    steps = malloc((size_t)count * sizeof *steps);
    run(collatz_worker);
    int64_t total = 0;
    for (int t = 0; t < THREADS; t++) total += partial_steps[t];
    int64_t longest = 0, longest_start = 1;
    for (int64_t i = 0; i < count; i++) if (steps[i] > longest) { longest = steps[i]; longest_start = i + 1; }
    printf("steps %lld\nlongest %lld %lld\n", (long long)total, (long long)longest_start, (long long)longest);
    samples = count * 8;
    run(histogram_worker);
    for (int b = 0; b < BUCKETS; b++) {
        int64_t sum = 0;
        for (int t = 0; t < THREADS; t++) sum += partial_bins[t][b];
        printf("bucket %d %lld\n", b, (long long)sum);
    }
    return 0;
}
