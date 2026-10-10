/* Direct-runtime synthetic pilot, not a generated-language/application result.
 * CLI: SHAPE N SEED MODE CSV, MODE = diagnostic | sampled | batch.
 * All construction and independent content checks precede retirement timing.
 */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#ifdef __APPLE__
#define _DARWIN_C_SOURCE 1
#include <mach/mach_time.h>
#endif
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <inttypes.h>
#include <stdint.h>
#include <time.h>
#ifdef RESEARCH_DIAGNOSTIC
#define MINYAR_RC_TESTING 1
#endif
#include "../../runtime/minyar_runtime.c"
#ifdef NDEBUG
#error Assertions are required for this research fixture.
#endif

typedef struct { uint64_t ns; size_t work, pending; long long bytes; } Sample;
static uint64_t rng;
#ifdef __APPLE__
static mach_timebase_info_data_t timebase;
#endif
static uint64_t now_ns(void) {
#ifdef __APPLE__
    return (uint64_t)(((__uint128_t)mach_absolute_time() * timebase.numer) / timebase.denom);
#else
    struct timespec t;
    assert(!clock_gettime(CLOCK_MONOTONIC, &t));
    return (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
#endif
}
static uint64_t random_word(void) {
    rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17;
    return rng;
}
static size_t number(const char *s, size_t low, size_t high) {
    char *end;
    unsigned long long n = strtoull(s, &end, 10);
    if (!*s || *s == '-' || *end || n < low || n > high) exit(2);
    return (size_t)n;
}
static void observe(Sample *s, uint64_t duration, size_t work) {
    s->ns = duration; s->work = work; s->pending = rc_pending_count;
    s->bytes = -1;
#ifdef RESEARCH_DIAGNOSTIC
    s->bytes = (long long)rc_bytes;
#endif
}
static void clear_caches(void) {
    while (rc_free_frames) {
        RcFrame *f = rc_free_frames;
        rc_free_frames = f->previous;
#ifdef MINYAR_BOUNDED_RC
        rc_heap_deallocate(f->locals); rc_heap_deallocate(f);
#else
        free(f->locals); free(f->temporaries); free(f);
#endif
    }
#ifdef MINYAR_BOUNDED_RC
    rc_bounded_cached_frame_bytes = 0;
#else
    free(rc_pending); rc_pending = NULL; rc_pending_capacity = 0;
#endif
}
int main(int argc, char **argv) {
    if (argc != 6) return 2;
    const char *shape = argv[1], *mode = argv[4];
    size_t n = number(argv[2], 2, 1000000), seed = number(argv[3], 1, 1000000000);
    int chain = !strcmp(shape, "chain"), frames = !strcmp(shape, "frames");
    int dag = !strcmp(shape, "dag"), wide = !strcmp(shape, "wide");
    int sampled = !strcmp(mode, "sampled"), batch = !strcmp(mode, "batch");
    int diagnostic = !strcmp(mode, "diagnostic");
    if (!(chain || frames || dag || wide) || !(sampled || batch || diagnostic)) return 2;
#ifdef __APPLE__
    assert(!mach_timebase_info(&timebase));
#endif
#ifdef RESEARCH_DIAGNOSTIC
    assert(diagnostic);
#else
    assert(!diagnostic);
#endif
    rng = seed;
    size_t capacity = 12 * n + 1024;
    Sample *samples = calloc(capacity, sizeof(*samples)); assert(samples);
    /* Identical touched trace footprint in batch and sampled builds. */
    for (size_t i = 0; i < capacity; i++) ((volatile Sample *)samples)[i].bytes = -1;
    MinyarRecord *sentinel = minyar_record_new_scalar(1);
    minyar_record_set_scalar(sentinel, 0, 1729);
    void *root = NULL;
    uint64_t checksum = 0;
    if (chain) {
        root = sentinel; minyar_rc_retain(root);
        for (size_t i = 0; i < n; i++) {
            MinyarRecord *node = minyar_record_new(1);
            minyar_record_set_take(node, 0, (long long)(uintptr_t)root);
            root = node;
        }
        void *p = root;
        for (size_t i = 0; i < n; i++) {
            assert(p != sentinel);
            p = (void *)(uintptr_t)minyar_record_get(p, 0);
            checksum++;
        }
        assert(p == sentinel);
    } else {
        MinyarRecord **nodes = malloc(n * sizeof(*nodes));
        size_t *order = malloc(n * sizeof(*order)); assert(nodes && order);
        if (frames) minyar_rc_enter((long long)n);
        for (size_t i = 0; i < n; i++) {
            MinyarRecord *payload = minyar_record_new_scalar(17);
            for (size_t j = 0; j < 17; j++)
                minyar_record_set_scalar(payload, (long long)j, (long long)(17 * i + j));
            MinyarRecord *node = minyar_record_new(3);
            minyar_record_set_take(node, 0, (long long)(uintptr_t)payload);
            minyar_record_set_reference(node, 1, (long long)(uintptr_t)sentinel);
            if (dag && i) minyar_record_set_reference(node, 2,
                (long long)(uintptr_t)nodes[random_word() % i]);
            nodes[i] = node; order[i] = i;
        }
        if (dag) for (size_t i = n - 1; i; i--) {
            size_t j = random_word() % (i + 1), old = order[i];
            order[i] = order[j]; order[j] = old;
        }
        MinyarList *list = NULL;
        if (!frames) { list = minyar_list_new(); minyar_list_references(list); root = list; }
        for (size_t i = 0; i < n; i++) {
            MinyarRecord *node = nodes[order[i]];
            MinyarRecord *payload = (void *)(uintptr_t)minyar_record_get(node, 0);
            for (size_t j = 0; j < 17; j++)
                assert(minyar_record_get(payload, (long long)j) == (long long)(17 * order[i] + j));
            assert((void *)(uintptr_t)minyar_record_get(node, 1) == sentinel);
            checksum += order[i];
            if (frames) {
                minyar_rc_local_take((long long)i, node);
                if (i % 4 == 0) minyar_rc_borrow(node);
            } else minyar_list_add_take(list, (long long)(uintptr_t)node);
        }
        assert(checksum == (uint64_t)n * (n - 1) / 2);
        free(nodes); free(order);
    }
    assert(!rc_pending_count);
    long long prepared = -1;
#ifdef RESEARCH_DIAGNOSTIC
    prepared = (long long)rc_bytes;
    assert(rc_object_count == (chain ? n + 1 : 2 * n + 1 + !frames));
#endif
    uint64_t clock_min = UINT64_MAX;
    if (!diagnostic) for (size_t i = 0; i < 10000; i++) {
        uint64_t t = now_ns(), delta = now_ns() - t;
        if (delta && delta < clock_min) clock_min = delta;
    }
    size_t count = 0, polls = 0, total_work = 0;
    uint64_t start = diagnostic ? 0 : now_ns();
    if (frames) minyar_rc_leave(); else minyar_rc_release(root);
    uint64_t first_end = sampled ? now_ns() : 0;
    size_t initial_work = 0;
#if defined(RESEARCH_DIAGNOSTIC) && defined(MINYAR_BOUNDED_RC)
    initial_work = rc_bounded_last_work;
    assert(initial_work <= MINYAR_RC_POLL_BUDGET);
#endif
    if (!batch) observe(&samples[count++], sampled ? first_end - start : 0, initial_work);
    total_work += initial_work;
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count) {
        assert(count < capacity && polls < capacity);
        uint64_t t = sampled ? now_ns() : 0;
        size_t work = minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
        uint64_t end = sampled ? now_ns() : 0;
        assert(work && work <= MINYAR_RC_POLL_BUDGET);
        if (!batch) observe(&samples[count++], sampled ? end - t : 0, work);
        total_work += work; polls++;
        if (diagnostic) assert(minyar_record_get(sentinel, 0) == 1729);
    }
#endif
    uint64_t elapsed = diagnostic ? 0 : now_ns() - start;
    assert(!rc_pending_count && !rc_frames);
    assert(minyar_record_get(sentinel, 0) == 1729);
#ifdef RESEARCH_DIAGNOSTIC
    assert(rc_object_count == 1 && (((RcObject *)sentinel - 1)->ownership >> 3) == 1);
#endif
    minyar_rc_release(sentinel); clear_caches();
    long long final_bytes = -1;
#ifdef RESEARCH_DIAGNOSTIC
    final_bytes = (long long)rc_bytes;
    assert(!rc_bytes && !rc_object_count);
#ifdef MINYAR_BOUNDED_RC
    assert(!rc_heap_allocation_count);
#endif
#endif
    if (!batch) {
        FILE *f = fopen(argv[5], "w"); assert(f);
        fprintf(f, "sample,kind,ns,work,pending,managed_bytes\n");
        for (size_t i = 0; i < count; i++) fprintf(f, "%zu,%s,%" PRIu64 ",%zu,%zu,%lld\n",
            i, i ? "poll" : "retire", samples[i].ns, samples[i].work,
            samples[i].pending, samples[i].bytes);
        assert(!fclose(f));
    }
    printf("{\"shape\":\"%s\",\"nodes\":%zu,\"seed\":%zu,\"mode\":\"%s\","
           "\"checksum\":%" PRIu64 ",\"polls\":%zu,\"samples\":%zu,"
           "\"elapsed_ns\":%" PRIu64 ",\"initial_ns\":%" PRIu64 ","
           "\"clock_positive_min_ns\":%" PRIu64 ",\"prepared_bytes\":%lld,"
           "\"final_bytes\":%lld,\"diagnostic_total_work\":%lld}\n",
           shape, n, seed, mode, checksum, polls, count, elapsed,
           sampled ? first_end - start : 0, clock_min == UINT64_MAX ? 0 : clock_min,
           prepared, final_bytes, diagnostic ? (long long)total_work : -1LL);
    free(samples);
    return 0;
}
