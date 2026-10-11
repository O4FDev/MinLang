/* Independent progress and cleanup contract for reactor-driven graph debt. */
#define MINYAR_RC_TESTING 1
#define MINYAR_INTEGER_TEXT_CACHE_LIMIT 0
#include "../build/managed-graphs-engine.c"
#include <assert.h>
#include <time.h>
#include <errno.h>

static long long slot(void *value) {
    return (long long)(uintptr_t)value;
}
static size_t waits, maximum_work;

static long long service_wait(long long timeout) {
#ifdef MINYAR_CYCLE_LEGACY_SERVICE
    long long result = minyar_callbackruntime_service() ? 0 : timeout;
#else
    long long result = minyar_callbackruntime_serviceWait(timeout);
#endif
#ifdef MINYAR_BOUNDED_RC
    assert(rc_bounded_last_work <= MINYAR_RC_POLL_BUDGET);
    if (maximum_work < rc_bounded_last_work)
        maximum_work = rc_bounded_last_work;
#endif
    assert(result == timeout || (result >= 0 && result <= 10));
    return result;
}
static int pending(void) {
#ifdef MINYAR_BOUNDED_RC
    return rc_pending_count != 0;
#else
    return rc_cycle_pending != 0;
#endif
}
static void drain(void) {
    size_t batches = 0;
    while (pending()) {
        assert(++batches < 100000);
        (void)service_wait(-1);
    }
}
static double wall_seconds(void) {
#ifdef _WIN32
    return (double)GetTickCount64() / 1000.0;
#else
    struct timespec now;
    assert(clock_gettime(CLOCK_MONOTONIC, &now) == 0);
    return (double)now.tv_sec + (double)now.tv_nsec / 1e9;
#endif
}
static double cpu_seconds(void) {
#ifdef _WIN32
    FILETIME created, exited, kernel, user;
    assert(GetProcessTimes(GetCurrentProcess(), &created, &exited, &kernel, &user));
    ULARGE_INTEGER k, u;
    k.LowPart = kernel.dwLowDateTime;
    k.HighPart = kernel.dwHighDateTime;
    u.LowPart = user.dwLowDateTime;
    u.HighPart = user.dwHighDateTime;
    return (double)(k.QuadPart + u.QuadPart) / 1e7;
#else
    return (double)clock() / CLOCKS_PER_SEC;
#endif
}
static void sleep_ms(long long milliseconds) {
    assert(milliseconds > 0 && milliseconds <= 1000);
#ifdef _WIN32
    Sleep((DWORD)milliseconds);
#else
    struct timespec request = {milliseconds / 1000, milliseconds % 1000 * 1000000};
    while (nanosleep(&request, &request) && errno == EINTR) {
    }
#endif
}
static void no_debt(void) {
    const long long timeouts[] = {-1, 0, 1, 20, 2147483647};
    assert(!pending());
    for (size_t i = 0; i < sizeof(timeouts) / sizeof(*timeouts); i++)
        assert(service_wait(timeouts[i]) == timeouts[i]);
#ifndef MINYAR_CYCLE_LEGACY_SERVICE
    const long long invalid[] = {LLONG_MIN, -2, 2147483648LL, LLONG_MAX};
    for (size_t i = 0; i < sizeof(invalid) / sizeof(*invalid); i++)
        assert(minyar_callbackruntime_serviceWait(invalid[i]) == invalid[i]);
#endif
}
static void ordinary_debt(void) {
    MinyarRecord *record = minyar_record_new(512);
    MinyarRecord *child = minyar_record_new_scalar(1);
    for (long long i = 0; i < 512; i++)
        minyar_record_set_reference(record, i, slot(child));
    minyar_rc_release(child);
    minyar_rc_release(record);
    while (pending()) {
        long long wait = service_wait(-1);
        /* Ordinary frame/object/chunk debt remains immediately runnable. */
        if (pending())
            assert(wait == 0);
    }
    assert(!rc_object_count && !rc_bytes);
    no_debt();
}
int main(int argc, char **argv) {
    enum { F = 3 };
    unsigned N = argc > 2 ? (unsigned)strtoul(argv[2], NULL, 10) : 32;
    assert(N == 32 || N == 2048 || N == 4096);
    double seconds = argc > 1 ? strtod(argv[1], NULL) : 1.0;
    assert(seconds >= 0.1 && seconds <= 30);
    no_debt();
    ordinary_debt();
    MinyarRecord *nodes[4096];
    for (unsigned i = 0; i < N; i++)
        nodes[i] = minyar_record_new_traced(F);
    for (unsigned i = 0; i < N; i++) {
        minyar_record_set_reference_traced(nodes[i], 0, slot(nodes[i]));
        minyar_record_set_reference_traced(nodes[i], 1, slot(nodes[(i + 1) % N]));
        minyar_record_set_reference_traced(nodes[i], 2, slot(nodes[(i + N - 1) % N]));
    }
    for (unsigned i = 1; i < N; i++)
        minyar_rc_release(nodes[i]);
    drain();
    assert(rc_object_count == N);
    /* A large live cohort must not force the reactor to spin until its
     * final field. Pacing applies after each bounded cycle-only batch,
     * including ROOTS/MARK/SWEEP, while the real job stays queued. */
    if (N >= 2048) {
        size_t completed = rc_cycle_completed;
        minyar_rc_retain_traced(nodes[1]);
        minyar_rc_release(nodes[1]);
        assert(pending() && rc_cycle_phase != RC_CYCLE_IDLE);
        assert(rc_cycle_completed == completed);
        const long long timeouts[] = {-1, 20, 1, 0};
        for (size_t i = 0; i < sizeof(timeouts) / sizeof(*timeouts); i++) {
            long long wait = service_wait(timeouts[i]);
            assert(pending() && rc_cycle_completed == completed);
            assert(wait == (timeouts[i] < 0 || timeouts[i] > 10 ? 10 : timeouts[i]));
        }
    }
    size_t attempts = 0, epochs = rc_cycle_epochs;
    /* Real helper calls borrow an interior node without changing the graph.
     * Their last transient external owner repeatedly requests a new epoch.
     * A completed captured snapshot must let the reactor wait finitely. */
    for (;;) {
        minyar_rc_retain_traced(nodes[1]);
        minyar_rc_release(nodes[1]);
        long long wait = service_wait(-1);
        if (wait != 0) {
            /* Infinite waits cannot strand newly requested graph debt. */
            if (pending())
                assert(wait > 0 && wait <= 10);
            break;
        }
        if (++attempts >= 16u * N * F + 16) {
            fprintf(stderr, "borrow-only churn: attempts=%zu epochs=%zu objects=%zu\n", attempts,
                    rc_cycle_epochs - epochs, rc_object_count);
            assert(!"a completed snapshot must permit a bounded reactor wait");
        }
    }
    double start = wall_seconds(), cpu_start = cpu_seconds();
    while (wall_seconds() - start < seconds) {
        minyar_rc_retain_traced(nodes[1]);
        minyar_rc_release(nodes[1]);
        long long wait = service_wait(20);
        assert(rc_object_count == N);
        assert(minyar_record_get(nodes[0], 0) == slot(nodes[0]));
        if (wait > 0) {
            waits++;
            sleep_ms(wait);
        }
    }
    double elapsed = wall_seconds() - start;
    double idle_cpu = (cpu_seconds() - cpu_start) / elapsed;
    assert(waits > 0);
    assert(idle_cpu <= 0.02);
    /* Unreachable cycles must disappear even while helper borrows of a
     * separate large live graph keep requesting new captured cohorts.
     * Model every returned wake deadline without sleeping: the fixed input
     * graph gives a finite call bound, and no call can postpone it >10ms. */
    MinyarRecord *garbage[2];
    for (unsigned i = 0; i < 2; i++)
        garbage[i] = minyar_record_new_traced(1);
    minyar_record_set_reference_traced(garbage[0], 0, slot(garbage[1]));
    minyar_record_set_reference_traced(garbage[1], 0, slot(garbage[0]));
    minyar_rc_release(garbage[0]);
    minyar_rc_release(garbage[1]);
    size_t cleanup_batches = 0, cleanup_deadline_ms = 0;
    while (rc_object_count > N) {
        assert(++cleanup_batches < 64u * N * (F + 1) + 64);
        minyar_rc_retain_traced(nodes[1]);
        minyar_rc_release(nodes[1]);
        long long wait = service_wait(-1);
        if (pending())
            assert(wait >= 0 && wait <= 10);
        if (wait > 0)
            cleanup_deadline_ms += (size_t)wait;
        assert(minyar_record_get(nodes[0], 0) == slot(nodes[0]));
    }
    assert(rc_object_count == N);
    /* The very same temporary may really become the last external owner.
     * Keeping cycle requests preserves eventual reclamation after it drops. */
    minyar_rc_retain_traced(nodes[1]);
    minyar_rc_release(nodes[0]);
    drain();
    assert(rc_object_count == N);
    assert(minyar_record_get(nodes[1], 0) == slot(nodes[1]));
    minyar_rc_release(nodes[1]);
    drain();
    assert(!rc_object_count && !rc_bytes && !rc_cycle_head && !rc_cycle_pending);
    no_debt();
    printf("cycle progress: nodes=%u borrows=%zu epochs=%zu waits=%zu idle_cpu=%.6f max_work=%zu "
           "churn_cleanup_batches=%zu churn_deadline_ms=%zu objects=0 "
           "bytes=0\n",
           N, attempts, rc_cycle_epochs, waits, idle_cpu, maximum_work, cleanup_batches,
           cleanup_deadline_ms);
    return 0;
}
