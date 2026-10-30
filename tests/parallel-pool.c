/* Independent exactly-once oracle for the scalar scheduler. */
#define MINYAR_SYSTEM_HEAP 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>

enum { PARALLEL_TEST_COUNT = 50003 };
static int slots[PARALLEL_TEST_COUNT];
static pthread_t owner;
static _Atomic int foreign;
static pthread_mutex_t gate_mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t gate_ready = PTHREAD_COND_INITIALIZER;
static int arrivals, gate_open;

static void fill(long long first, long long after, void *argument) {
    pthread_mutex_lock(&gate_mutex);
    if (!gate_open) {
        ++arrivals;
        if (arrivals >= (parallel_pool.count > 1 ? 2 : 1)) {
            gate_open = 1;
            pthread_cond_broadcast(&gate_ready);
        }
        while (!gate_open) pthread_cond_wait(&gate_ready, &gate_mutex);
    }
    pthread_mutex_unlock(&gate_mutex);
    if (!pthread_equal(owner, pthread_self())) atomic_store(&foreign, 1);
    int *values = argument;
    for (long long index = first; index < after; ++index) ++values[index];
}

typedef struct { long long first, after; _Atomic uint64_t total; } Bounds;
static void edge(long long first, long long after, void *argument) {
    Bounds *bounds = argument;
    assert(first >= bounds->first && after <= bounds->after && first < after);
    atomic_fetch_add(&bounds->total, (uint64_t)after - (uint64_t)first);
}

/* A few long iterations (one per segment) must still spread over workers. */
static _Atomic int short_foreign;
static void short_range(long long first, long long after, void *argument) {
    (void)argument;
    assert(first < after);
    struct timespec pause = { 0, 20000000 };
    nanosleep(&pause, NULL);
    if (!pthread_equal(owner, pthread_self())) atomic_store(&short_foreign, 1);
}

static void *independent_owner(void *argument) {
    (void)argument;
    int values[2003] = {0};
    for (int round = 0; round < 20; ++round) minyar_parallel_run(fill, 0, 2003, values);
    for (int index = 0; index < 2003; ++index) assert(values[index] == 20);
    return NULL;
}

static long long sum_indices(long long first, long long after, void *argument) {
    (void)argument;
    long long sum = 0;
    for (long long index = first; index < after; ++index) sum += index;
    return sum;
}

/* Fork-join: recursive joins below a cutoff, and loops nested in loops. */
typedef struct { long long n, result; } Fib;
static long long fib_serial(long long n) { return n < 2 ? n : fib_serial(n - 1) + fib_serial(n - 2); }
static void fib_task(void *argument) {
    Fib *job = argument;
    if (job->n < 12) { job->result = fib_serial(job->n); return; }
    Fib left = { job->n - 1, 0 }, right = { job->n - 2, 0 };
    minyar_parallel_join(fib_task, &left, fib_task, &right);
    job->result = left.result + right.result;
}
static _Atomic long long nested_cells;
static _Atomic int nested_foreign;
static void nested_inner(long long first, long long after, void *argument) {
    (void)argument;
    atomic_fetch_add(&nested_cells, after - first);
    if (!pthread_equal(owner, pthread_self())) atomic_store(&nested_foreign, 1);
    else if (parallel_pool.count > 1) {
        /* While the owner is busy here, its forked nested spans must be stolen. */
        for (int wait = 0; wait < 5000 && !atomic_load(&nested_foreign); ++wait) {
            struct timespec pause = { 0, 1000000 };
            nanosleep(&pause, NULL);
        }
    }
}
static void nested_outer(long long first, long long after, void *argument) {
    (void)argument;
    for (long long row = first; row < after; ++row) minyar_parallel_run(nested_inner, 0, 1000 + row, NULL);
}

int main(void) {
    owner = pthread_self();
    for (int round = 0; round < 100; ++round) {
        minyar_parallel_run(fill, 1, PARALLEL_TEST_COUNT - 1, slots);
        minyar_parallel_run(fill, 0, 0, slots);
        minyar_parallel_run(fill, 4, 1, slots);
    }
    assert(slots[0] == 0 && slots[PARALLEL_TEST_COUNT - 1] == 0);
    for (int index = 1; index < PARALLEL_TEST_COUNT - 1; ++index) assert(slots[index] == 100);
    Bounds bounds = { LLONG_MIN, LLONG_MIN + 10003, 0 };
    minyar_parallel_run(edge, bounds.first, bounds.after, &bounds);
    assert(atomic_load(&bounds.total) == 10003);
    bounds.first = LLONG_MAX - 10003; bounds.after = LLONG_MAX;
    atomic_store(&bounds.total, 0);
    minyar_parallel_run(edge, bounds.first, bounds.after, &bounds);
    assert(atomic_load(&bounds.total) == 10003);
    int requested = atoi(getenv("MINYAR_PARALLEL_THREADS"));
    assert(parallel_pool.count == (size_t)requested);
    assert(atomic_load(&foreign) == (requested > 1));
    minyar_parallel_run(short_range, 0, 8, NULL);
    assert(atomic_load(&short_foreign) == (requested > 1));
    assert(minyar_parallel_reduce(sum_indices, 0, 5003, NULL, 1, 5) == 12512508);
    assert(minyar_parallel_reduce(sum_indices, -1000, 1001, NULL, 1, 42) == 42);
    assert(minyar_parallel_reduce(sum_indices, 4, 1, NULL, 1, 42) == 42);
    pthread_t callers[3];
    for (int index = 0; index < 3; ++index) assert(pthread_create(&callers[index], NULL, independent_owner, NULL) == 0);
    for (int index = 0; index < 3; ++index) assert(pthread_join(callers[index], NULL) == 0);
    for (int round = 0; round < 3; ++round) {
        Fib job = { 27, 0 };
        minyar_parallel_join(fib_task, &job, fib_task, &(Fib){ 3, 0 });
        assert(job.result == 196418);
    }
    minyar_parallel_run(nested_outer, 0, 64, NULL);
    assert(atomic_load(&nested_cells) == 64 * 1000 + 64 * 63 / 2);
    assert(atomic_load(&nested_foreign) == (requested > 1));
    puts("parallel pool: exact coverage, concurrent callers, joins and signed endpoints passed");
    puts("parallel pool: recursive joins and nested loops passed");
}
