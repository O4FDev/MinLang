/* Compare eager and finite-pool release, including all deferred work.
 * Diagnostic measurement only: no existing performance baseline is changed. */
#define _POSIX_C_SOURCE 200809L
#ifdef __APPLE__
#define _DARWIN_C_SOURCE
#endif
#include <time.h>
#include <assert.h>
#define MINYAR_RC_TESTING
#include <sys/resource.h>
#ifndef MINYAR_RUNTIME_SOURCE
#define MINYAR_RUNTIME_SOURCE "../../runtime/minyar_runtime.c"
#endif
#include MINYAR_RUNTIME_SOURCE

#ifdef CLOCK_MONOTONIC_RAW
#define STUDY_CLOCK CLOCK_MONOTONIC_RAW
#else
#define STUDY_CLOCK CLOCK_MONOTONIC
#endif

static double ns(void) {
    struct timespec t;
    assert(clock_gettime(STUDY_CLOCK, &t) == 0);
    return (double)t.tv_sec * 1e9 + t.tv_nsec;
}

#ifdef MINYAR_RELEASE_CPU_DIAGNOSTIC
/* Additional clocks perturb short calls. Use only to diagnose wall outliers;
 * never mix these runs with the ordinary latency/throughput comparisons. */
static double thread_ns(void) {
    struct timespec t;
    assert(!clock_gettime(CLOCK_THREAD_CPUTIME_ID, &t));
    return (double)t.tv_sec * 1e9 + t.tv_nsec;
}
#endif

int main(int argc, char **argv) {
    assert(argc == 3);
    size_t n = (size_t)strtoull(argv[2], NULL, 10);
    assert(n && n <= 800000);
    void *root = NULL;
    if (!strcmp(argv[1], "chain")) {
        for (size_t i = 0; i < n; i++) {
            MinyarRecord *r = minyar_record_new(1);
            minyar_record_set_take(r, 0, (long long)(uintptr_t)root);
            root = r;
        }
    } else {
        MinyarList *list = minyar_list_new();
        minyar_list_references(list);
        root = list;
        MinyarRecord *shared = NULL;
        if (!strcmp(argv[1], "shared")) shared = minyar_record_new_scalar(2);
        else assert(!strcmp(argv[1], "wide"));
        for (size_t i = 0; i < n; i++) {
            if (shared) minyar_list_add(list, (long long)(uintptr_t)shared);
            else minyar_list_add_take(list, (long long)(uintptr_t)minyar_record_new_scalar(2));
        }
        if (shared) minyar_rc_release(shared);
    }
    size_t before = rc_object_count, bytes = rc_bytes;
#ifdef MINYAR_RELEASE_CPU_DIAGNOSTIC
    struct rusage release_start_usage;
    assert(!getrusage(RUSAGE_SELF, &release_start_usage));
    double cpu_start = thread_ns();
#endif
    double start = ns();
    minyar_rc_release(root);
    double first = ns() - start;
#ifdef MINYAR_RELEASE_CPU_DIAGNOSTIC
    double max_cpu = thread_ns() - cpu_start, cpu_at_max_wall = max_cpu;
#endif
#if defined(MINYAR_BOUNDED_RC) || defined(MINYAR_BOUNDED_HEAP)
    assert(before - rc_object_count <= MINYAR_RC_POLL_BUDGET);
#endif
    double maximum = first, total = first;
    size_t calls = 1, after_first = rc_bytes;
    size_t maximum_reclaimed_bytes = bytes - after_first;
#if defined(MINYAR_BOUNDED_RC) || defined(MINYAR_BOUNDED_HEAP)
    assert(rc_bounded_last_work <= MINYAR_RC_POLL_BUDGET);
    while (rc_pending_count) {
        size_t before_slice = rc_bytes;
#ifdef MINYAR_RELEASE_CPU_DIAGNOSTIC
        cpu_start = thread_ns();
#endif
        start = ns();
        size_t work = minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
        double elapsed = ns() - start;
#ifdef MINYAR_RELEASE_CPU_DIAGNOSTIC
        double cpu_elapsed = thread_ns() - cpu_start;
        if (cpu_elapsed > max_cpu) max_cpu = cpu_elapsed;
#endif
        assert(work > 0 && work <= MINYAR_RC_POLL_BUDGET);
        if (elapsed > maximum) {
            maximum = elapsed;
            maximum_reclaimed_bytes = before_slice - rc_bytes;
#ifdef MINYAR_RELEASE_CPU_DIAGNOSTIC
            cpu_at_max_wall = cpu_elapsed;
#endif
        }
        total += elapsed;
        calls++;
    }
#endif
    assert(rc_object_count == 0 && rc_bytes == 0);
    struct timespec resolution; assert(!clock_getres(STUDY_CLOCK, &resolution));
    struct rusage usage; assert(!getrusage(RUSAGE_SELF, &usage));
#ifdef MINYAR_RELEASE_CPU_DIAGNOSTIC
    fprintf(stderr, "{\"max_wall_ns\":%.0f,\"thread_cpu_at_max_wall_ns\":%.0f,"
            "\"max_thread_cpu_ns\":%.0f,\"release_minor_faults\":%ld,\"release_major_faults\":%ld}\n",
            maximum, cpu_at_max_wall, max_cpu, usage.ru_minflt - release_start_usage.ru_minflt,
            usage.ru_majflt - release_start_usage.ru_majflt);
#endif
    size_t pool_peak = 0, pool_steps = 0;
#ifdef MINYAR_BOUNDED_HEAP
    assert(minyar_pool_used == 0);
    pool_peak = minyar_pool_high_water;
    pool_steps = minyar_pool_max_steps;
#endif
    printf("{\"first_ns\":%.0f,\"max_slice_ns\":%.0f,\"sum_timed_ns\":%.0f,"
           "\"calls\":%zu,\"objects\":%zu,\"bytes\":%zu,\"bytes_after_first\":%zu,"
           "\"max_slice_reclaimed_bytes\":%zu,\"clock_resolution_ns\":%ld,\"peak_rss_platform_units\":%ld,\"pool_peak_bytes\":%zu,\"max_allocator_steps\":%zu}\n",
           first, maximum, total, calls, before, bytes, after_first,
           maximum_reclaimed_bytes, resolution.tv_nsec, usage.ru_maxrss, pool_peak, pool_steps);
}
