/* Synchronous scalar jobs. Managed allocation, counts and ownership frames
 * stay on the calling thread; workers borrow only compiler-checked slots. */
#include <stdatomic.h>

typedef void (*MinyarParallelEntry)(long long, long long, void *);

void minyar_parallel_no_alias(const void *input, const void *output,
                              long long first, long long after) {
    if (first < after && input == output)
        minyar_stop("a parallel input read at another index aliases a buffer written by parallel for; use a separate input buffer.");
}

#define MINYAR_PARALLEL_LIMIT 64
#define MINYAR_PARALLEL_GRAIN 128

static void parallel_chunk(MinyarParallelEntry entry, void *environment,
                           long long first, long long after, uint64_t chunk) {
    uint64_t distance = (uint64_t)after - (uint64_t)first;
    uint64_t offset = chunk * MINYAR_PARALLEL_GRAIN;
    uint64_t count = distance - offset;
    if (count > MINYAR_PARALLEL_GRAIN) count = MINYAR_PARALLEL_GRAIN;
    entry((long long)((uint64_t)first + offset),
          (long long)((uint64_t)first + offset + count), environment);
}

static void parallel_serial(MinyarParallelEntry entry, long long first,
                            long long after, void *environment) {
    uint64_t distance = (uint64_t)after - (uint64_t)first;
    uint64_t chunks = distance / MINYAR_PARALLEL_GRAIN +
                      (distance % MINYAR_PARALLEL_GRAIN != 0);
#if (defined(__APPLE__) || defined(__linux__)) && !defined(MINYAR_FREESTANDING)
    int previous = minyar_parallel_active;
    minyar_parallel_active = 1;
#endif
    for (uint64_t chunk = 0; chunk < chunks; ++chunk)
        parallel_chunk(entry, environment, first, after, chunk);
#if (defined(__APPLE__) || defined(__linux__)) && !defined(MINYAR_FREESTANDING)
    minyar_parallel_active = previous;
#endif
}

#if (defined(__APPLE__) || defined(__linux__)) && !defined(MINYAR_FREESTANDING)
#include <unistd.h>

typedef struct {
    _Alignas(64) _Atomic uint64_t next;
    uint64_t after;
} MinyarParallelLane;

typedef struct {
    pthread_mutex_t admission;
    pthread_mutex_t mutex;
    pthread_cond_t ready;
    pthread_cond_t finished;
    pthread_t threads[MINYAR_PARALLEL_LIMIT - 1];
    size_t identities[MINYAR_PARALLEL_LIMIT - 1];
    MinyarParallelLane lanes[MINYAR_PARALLEL_LIMIT];
    size_t count;
    size_t pending;
    uint64_t generation;
    int stopping;
    MinyarParallelEntry entry;
    void *environment;
    long long first;
    long long after;
} MinyarParallelPool;

static MinyarParallelPool parallel_pool = {
    .admission = PTHREAD_MUTEX_INITIALIZER,
    .mutex = PTHREAD_MUTEX_INITIALIZER,
    .ready = PTHREAD_COND_INITIALIZER,
    .finished = PTHREAD_COND_INITIALIZER,
    .count = 1
};
static pthread_once_t parallel_once = PTHREAD_ONCE_INIT;

static void parallel_work(size_t own) {
    MinyarParallelPool *pool = &parallel_pool;
    /* Each lane has its own claim cursor. Exhausted workers steal chunks
     * from the other lanes; no job or managed object is allocated here. */
    for (size_t offset = 0; offset < pool->count; ++offset) {
        size_t victim = (own + offset) % pool->count;
        MinyarParallelLane *lane = &pool->lanes[victim];
        uint64_t chunk = atomic_fetch_add_explicit(&lane->next, 1, memory_order_relaxed);
        while (chunk < lane->after) {
            parallel_chunk(pool->entry, pool->environment, pool->first, pool->after, chunk);
            chunk = atomic_fetch_add_explicit(&lane->next, 1, memory_order_relaxed);
        }
    }
}

static void *parallel_worker(void *argument) {
    minyar_parallel_active = 1;
    size_t own = *(size_t *)argument;
    uint64_t seen = 0;
    MinyarParallelPool *pool = &parallel_pool;
    pthread_mutex_lock(&pool->mutex);
    for (;;) {
        while (!pool->stopping && seen == pool->generation)
            pthread_cond_wait(&pool->ready, &pool->mutex);
        if (pool->stopping) break;
        seen = pool->generation;
        pthread_mutex_unlock(&pool->mutex);
        parallel_work(own);
        pthread_mutex_lock(&pool->mutex);
        if (--pool->pending == 0) pthread_cond_signal(&pool->finished);
    }
    pthread_mutex_unlock(&pool->mutex);
    return NULL;
}

static void parallel_shutdown(void) {
    MinyarParallelPool *pool = &parallel_pool;
    pthread_mutex_lock(&pool->admission);
    pthread_mutex_lock(&pool->mutex);
    pool->stopping = 1;
    pthread_cond_broadcast(&pool->ready);
    pthread_mutex_unlock(&pool->mutex);
    for (size_t index = 1; index < pool->count; ++index)
        pthread_join(pool->threads[index - 1], NULL);
    pthread_mutex_unlock(&pool->admission);
}

static void parallel_initialize(void) {
    long available = sysconf(_SC_NPROCESSORS_ONLN);
    size_t count = available > 0 ? (size_t)available : 1;
    if (count > MINYAR_PARALLEL_LIMIT) count = MINYAR_PARALLEL_LIMIT;
    const char *configured = getenv("MINYAR_PARALLEL_THREADS");
    if (configured && *configured) {
        size_t requested = 0;
        for (const char *digit = configured; *digit; ++digit) {
            if (*digit < '0' || *digit > '9' || requested > MINYAR_PARALLEL_LIMIT)
                minyar_stop("MINYAR_PARALLEL_THREADS must be an integer from 1 to 64.");
            requested = requested * 10 + (size_t)(*digit - '0');
        }
        if (requested < 1 || requested > MINYAR_PARALLEL_LIMIT)
            minyar_stop("MINYAR_PARALLEL_THREADS must be an integer from 1 to 64.");
        count = requested;
    }
    MinyarParallelPool *pool = &parallel_pool;
    if (atexit(parallel_shutdown) != 0)
        minyar_stop("the parallel thread pool could not register its cleanup.");
    for (size_t index = 1; index < count; ++index) {
        pool->identities[index - 1] = index;
        if (pthread_create(&pool->threads[index - 1], NULL, parallel_worker,
                           &pool->identities[index - 1]) != 0) break;
        pool->count = index + 1;
    }
}
#endif

void minyar_parallel_run(MinyarParallelEntry entry, long long first,
                         long long after, void *environment) {
    if (first >= after) return;
#if (defined(__APPLE__) || defined(__linux__)) && !defined(MINYAR_FREESTANDING)
    pthread_once(&parallel_once, parallel_initialize);
    MinyarParallelPool *pool = &parallel_pool;
    if (pool->count == 1) { parallel_serial(entry, first, after, environment); return; }
    uint64_t distance = (uint64_t)after - (uint64_t)first;
    uint64_t chunks = distance / MINYAR_PARALLEL_GRAIN +
                      (distance % MINYAR_PARALLEL_GRAIN != 0);
    if (chunks == 1) { parallel_serial(entry, first, after, environment); return; }
    pthread_mutex_lock(&pool->admission);
    pthread_mutex_lock(&pool->mutex);
    pool->entry = entry;
    pool->environment = environment;
    pool->first = first;
    pool->after = after;
    pool->pending = pool->count - 1;
    uint64_t base = chunks / pool->count;
    uint64_t extra = chunks % pool->count;
    uint64_t start = 0;
    for (size_t index = 0; index < pool->count; ++index) {
        uint64_t length = base + (index < extra);
        atomic_store_explicit(&pool->lanes[index].next, start, memory_order_relaxed);
        pool->lanes[index].after = start + length;
        start += length;
    }
    ++pool->generation;
    pthread_cond_broadcast(&pool->ready);
    pthread_mutex_unlock(&pool->mutex);
    int previous = minyar_parallel_active;
    minyar_parallel_active = 1;
    parallel_work(0);
    minyar_parallel_active = previous;
    pthread_mutex_lock(&pool->mutex);
    while (pool->pending) pthread_cond_wait(&pool->finished, &pool->mutex);
    pthread_mutex_unlock(&pool->mutex);
    pthread_mutex_unlock(&pool->admission);
#else
    parallel_serial(entry, first, after, environment);
#endif
}
