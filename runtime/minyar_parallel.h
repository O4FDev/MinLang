/* Synchronous scalar jobs. Managed allocation, counts and ownership frames
 * stay on the calling thread; workers borrow only compiler-checked slots. */
#include <stdatomic.h>

typedef void (*MinyarParallelEntry)(long long, long long, void *);

void minyar_parallel_no_alias(const void *input, const void *output,
                              long long first, long long after) {
    if (first < after && input == output)
        minyar_stop("a parallel input read at another index or beside a window aliases a buffer written by parallel for; use a separate input buffer.");
}

void minyar_parallel_bytes_no_overlap(const MinyarText *left, const MinyarText *right,
                                      long long first, long long after, long long same_index) {
    if (first >= after) return;
    uintptr_t a = (uintptr_t)left->bytes, b = (uintptr_t)right->bytes;
    if (same_index && a == b) return;
    if (left->byte_length <= 0 || right->byte_length <= 0) return;
    /* Differences avoid wrapping an end pointer, including for trusted native
     * address views. Ordinary Bytes copies have independent backing storage. */
    int overlaps = a <= b ? b - a < (uint64_t)left->byte_length
                          : a - b < (uint64_t)right->byte_length;
    if (overlaps) {
        if (same_index)
            minyar_stop("parallel for buffers overlap at different indices; use separate Bytes storage or copy a view before writing.");
        minyar_stop("a parallel input read at another index or beside a window aliases a buffer written by parallel for; use a separate input buffer.");
    }
}

/* Bytes elements of a List<Bytes> that a loop reads must not overlap a Bytes
 * output; the check costs one comparison per element. */
void minyar_parallel_bytes_list_no_overlap(const MinyarList *list, const MinyarText *output,
                                           long long first, long long after) {
    if (first >= after) return;
    for (long long index = 0; index < list->length; ++index)
        minyar_parallel_bytes_no_overlap((const MinyarText *)(uintptr_t)list->values[index], output,
                                         first, after, 0);
}

/* Records in a List a loop reads: the buffer at `path` (field positions; record
 * layout { length, values[] }) in every element must not alias the output. */
void minyar_parallel_record_list_guard(const MinyarList *list, const long long *path, long long depth,
                                       const void *output, long long bytes, long long first,
                                       long long after) {
    if (first >= after) return;
    for (long long index = 0; index < list->length; ++index) {
        const long long *value = (const long long *)(uintptr_t)list->values[index];
        for (long long step = 0; step < depth; ++step)
            value = (const long long *)(uintptr_t)value[1 + path[step]];
        if (bytes)
            minyar_parallel_bytes_no_overlap((const MinyarText *)value, (const MinyarText *)output,
                                             first, after, 0);
        else
            minyar_parallel_no_alias(value, output, first, after);
    }
}

/* A window is iteration index's own `width` slots, starting at index * width. */
void minyar_parallel_window_stop(long long index, long long width, long long length) {
    char message[200];
    if (width < 0)
        snprintf(message, sizeof(message), "a parallel for window cannot have the negative width %lld.", width);
    else
        snprintf(message, sizeof(message),
                 "parallel for window %lld of width %lld does not fit in a buffer of length %lld; give the buffer one window per iteration.",
                 index, width, length);
    minyar_stop(message);
}

#define MINYAR_PARALLEL_LIMIT 64
#define MINYAR_PARALLEL_GRAIN 128

static void parallel_chunk(MinyarParallelEntry entry, void *environment,
                           long long first, long long after, uint64_t chunk, uint64_t grain) {
    uint64_t distance = (uint64_t)after - (uint64_t)first;
    uint64_t offset = chunk * grain;
    uint64_t count = distance - offset;
    if (count > grain) count = grain;
    entry((long long)((uint64_t)first + offset),
          (long long)((uint64_t)first + offset + count), environment);
}

#include "minyar_parallel_backend.h"

static void parallel_serial(MinyarParallelEntry entry, long long first,
                            long long after, void *environment, uint64_t grain) {
    uint64_t distance = (uint64_t)after - (uint64_t)first;
    uint64_t chunks = distance / grain + (distance % grain != 0);
#if (defined(__APPLE__) || defined(__linux__)) && !defined(MINYAR_FREESTANDING)
    int previous = minyar_parallel_active;
    minyar_parallel_active = 1;
#endif
    for (uint64_t chunk = 0; chunk < chunks; ++chunk)
        parallel_chunk(entry, environment, first, after, chunk, grain);
#if (defined(__APPLE__) || defined(__linux__)) && !defined(MINYAR_FREESTANDING)
    minyar_parallel_active = previous;
#endif
}

#if (defined(__APPLE__) || defined(__linux__)) && !defined(MINYAR_FREESTANDING)
#include <unistd.h>
#include <sched.h>

/* One persistent pool, shared by every parallel for, reduction and join.
 * Each participant owns a Chase-Lev deque of tasks that live on the stacks of
 * the joins that forked them. An owner pushes and pops at the bottom; idle
 * participants steal from the top of another deque. A parallel for is a binary
 * tree of joins over its chunks, so loops nest inside loops and joins, and a
 * waiting join runs stolen work instead of blocking. No job or managed object
 * is allocated here. */
enum { MINYAR_DEQUE_SIZE = 4096 };

typedef struct MinyarTask {
    void (*run)(void *);
    void *environment;
    _Atomic int done;
} MinyarTask;

typedef struct {
    _Alignas(64) _Atomic long long top;
    _Alignas(64) _Atomic long long bottom;
    _Atomic(MinyarTask *) slots[MINYAR_DEQUE_SIZE];
} MinyarDeque;

typedef struct {
    pthread_mutex_t admission;
    pthread_mutex_t mutex;
    pthread_cond_t ready;
    pthread_t threads[MINYAR_PARALLEL_LIMIT - 1];
    size_t identities[MINYAR_PARALLEL_LIMIT - 1];
    MinyarDeque deques[MINYAR_PARALLEL_LIMIT];
    size_t count;
    _Atomic int active;
    int stopping;
} MinyarParallelPool;

static MinyarParallelPool parallel_pool = {
    .admission = PTHREAD_MUTEX_INITIALIZER,
    .mutex = PTHREAD_MUTEX_INITIALIZER,
    .ready = PTHREAD_COND_INITIALIZER,
    .count = 1
};
static pthread_once_t parallel_once = PTHREAD_ONCE_INIT;
/* This thread's deque while it takes part in pool work, else -1. */
static _Thread_local int parallel_participant = -1;

static int parallel_push(MinyarDeque *deque, MinyarTask *task) {
    long long bottom = atomic_load_explicit(&deque->bottom, memory_order_relaxed);
    long long top = atomic_load_explicit(&deque->top, memory_order_acquire);
    if (bottom - top >= MINYAR_DEQUE_SIZE) return 0;
    atomic_store_explicit(&deque->slots[bottom & (MINYAR_DEQUE_SIZE - 1)], task, memory_order_relaxed);
    /* Publishes the task's fields to the thief that reads `bottom` with acquire. */
    atomic_store_explicit(&deque->bottom, bottom + 1, memory_order_release);
    return 1;
}

static MinyarTask *parallel_pop(MinyarDeque *deque) {
    long long bottom = atomic_load_explicit(&deque->bottom, memory_order_relaxed) - 1;
    atomic_store_explicit(&deque->bottom, bottom, memory_order_relaxed);
    atomic_thread_fence(memory_order_seq_cst);
    long long top = atomic_load_explicit(&deque->top, memory_order_relaxed);
    MinyarTask *task = NULL;
    if (top <= bottom) {
        task = atomic_load_explicit(&deque->slots[bottom & (MINYAR_DEQUE_SIZE - 1)], memory_order_relaxed);
        if (top == bottom) {
            if (!atomic_compare_exchange_strong_explicit(&deque->top, &top, top + 1,
                    memory_order_seq_cst, memory_order_relaxed)) task = NULL;
            atomic_store_explicit(&deque->bottom, bottom + 1, memory_order_relaxed);
        }
    } else {
        atomic_store_explicit(&deque->bottom, bottom + 1, memory_order_relaxed);
    }
    return task;
}

static MinyarTask *parallel_steal(MinyarDeque *deque) {
    long long top = atomic_load_explicit(&deque->top, memory_order_acquire);
    atomic_thread_fence(memory_order_seq_cst);
    long long bottom = atomic_load_explicit(&deque->bottom, memory_order_acquire);
    if (top >= bottom) return NULL;
    MinyarTask *task = atomic_load_explicit(&deque->slots[top & (MINYAR_DEQUE_SIZE - 1)], memory_order_relaxed);
    if (!atomic_compare_exchange_strong_explicit(&deque->top, &top, top + 1,
            memory_order_seq_cst, memory_order_relaxed)) return NULL;
    return task;
}

static void parallel_execute(MinyarTask *task) {
    task->run(task->environment);
    atomic_store_explicit(&task->done, 1, memory_order_release);
}

/* One pass over the other deques, starting after `own`. */
static int parallel_steal_once(size_t own) {
    MinyarParallelPool *pool = &parallel_pool;
    for (size_t offset = 1; offset < pool->count; ++offset) {
        MinyarTask *task = parallel_steal(&pool->deques[(own + offset) % pool->count]);
        if (task) { parallel_execute(task); return 1; }
    }
    return 0;
}

static void parallel_idle(unsigned *failures) {
    if (++*failures < 64) {
#if defined(__x86_64__) || defined(__i386__)
        __builtin_ia32_pause();
#elif defined(__aarch64__)
        __asm__ __volatile__("yield");
#endif
    } else {
        sched_yield();
    }
}

/* Runs `a` here and `b` here or on a thief; returns when both finished. */
static void parallel_join_inside(int own, void (*a)(void *), void *a_environment,
                                 void (*b)(void *), void *b_environment) {
    MinyarParallelPool *pool = &parallel_pool;
    MinyarDeque *deque = &pool->deques[own];
    MinyarTask task = { b, b_environment, 0 };
    if (!parallel_push(deque, &task)) {
        a(a_environment);
        b(b_environment);
        return;
    }
    a(a_environment);
    MinyarTask *popped = parallel_pop(deque);
    if (popped == &task) {
        b(b_environment);
        return;
    }
    /* Stolen: an older task may have come back instead; keep it for its own join. */
    if (popped) parallel_push(deque, popped);
    unsigned failures = 0;
    while (!atomic_load_explicit(&task.done, memory_order_acquire)) {
        if (parallel_steal_once((size_t)own)) failures = 0;
        else parallel_idle(&failures);
    }
}

static void *parallel_worker(void *argument) {
    minyar_stack_guard_attach_thread();
    minyar_parallel_active = 1;
    size_t own = *(size_t *)argument;
    parallel_participant = (int)own;
    MinyarParallelPool *pool = &parallel_pool;
    for (;;) {
        pthread_mutex_lock(&pool->mutex);
        while (!pool->stopping && !atomic_load_explicit(&pool->active, memory_order_acquire))
            pthread_cond_wait(&pool->ready, &pool->mutex);
        int stopping = pool->stopping;
        pthread_mutex_unlock(&pool->mutex);
        if (stopping) break;
        unsigned failures = 0;
        while (atomic_load_explicit(&pool->active, memory_order_acquire)) {
            MinyarTask *task = parallel_pop(&pool->deques[own]);
            if (task) { parallel_execute(task); failures = 0; continue; }
            if (parallel_steal_once(own)) failures = 0;
            else parallel_idle(&failures);
        }
    }
    minyar_stack_guard_detach();
    return NULL;
}

static void parallel_shutdown(void) {
    MinyarParallelPool *pool = &parallel_pool;
    /* exit from inside pool work cannot wait for the job it belongs to. */
    if (parallel_participant >= 0) return;
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
    pthread_attr_t storage;
    pthread_attr_t *attributes = minyar_guarded_thread_attributes(&storage);
    for (size_t index = 1; index < count; ++index) {
        pool->identities[index - 1] = index;
        if (pthread_create(&pool->threads[index - 1], attributes, parallel_worker,
                           &pool->identities[index - 1]) != 0) break;
        pool->count = index + 1;
    }
    if (attributes) pthread_attr_destroy(attributes);
}

/* Runs one join from a thread outside the pool: it becomes participant 0 for
 * the job, as the caller of a parallel for always has. Callers on several
 * Minyar threads take turns. */
static void parallel_join_root(void (*a)(void *), void *a_environment,
                               void (*b)(void *), void *b_environment) {
    MinyarParallelPool *pool = &parallel_pool;
    pthread_mutex_lock(&pool->admission);
    pthread_mutex_lock(&pool->mutex);
    atomic_store_explicit(&pool->active, 1, memory_order_release);
    pthread_cond_broadcast(&pool->ready);
    pthread_mutex_unlock(&pool->mutex);
    int previous = minyar_parallel_active;
    minyar_parallel_active = 1;
    parallel_participant = 0;
    parallel_join_inside(0, a, a_environment, b, b_environment);
    parallel_participant = -1;
    minyar_parallel_active = previous;
    atomic_store_explicit(&pool->active, 0, memory_order_release);
    pthread_mutex_unlock(&pool->admission);
}

static void parallel_join(void (*a)(void *), void *a_environment,
                          void (*b)(void *), void *b_environment) {
    if (parallel_participant >= 0) {
        parallel_join_inside(parallel_participant, a, a_environment, b, b_environment);
        return;
    }
    pthread_once(&parallel_once, parallel_initialize);
    if (parallel_pool.count == 1) {
        int previous = minyar_parallel_active;
        minyar_parallel_active = 1;
        a(a_environment);
        b(b_environment);
        minyar_parallel_active = previous;
        return;
    }
    parallel_join_root(a, a_environment, b, b_environment);
}

typedef struct {
    MinyarParallelEntry entry;
    void *environment;
    long long first, after;
    uint64_t grain;
} MinyarParallelLoop;

typedef struct {
    const MinyarParallelLoop *loop;
    uint64_t first_chunk, after_chunk;
} MinyarParallelSpan;

/* Splits chunk ranges in halves: the right half may be stolen while the left
 * runs here, recursively, so every participant takes large contiguous spans. */
static void parallel_span(void *argument) {
    MinyarParallelSpan *span = argument;
    uint64_t first = span->first_chunk, after = span->after_chunk;
    while (after - first > 1) {
        uint64_t middle = first + (after - first) / 2;
        MinyarParallelSpan left = { span->loop, first, middle };
        MinyarParallelSpan right = { span->loop, middle, after };
        parallel_join(parallel_span, &left, parallel_span, &right);
        return;
    }
    if (first < after)
        parallel_chunk(span->loop->entry, span->loop->environment, span->loop->first,
                       span->loop->after, first, span->loop->grain);
}
#endif

/* Reductions keep 128-index chunks so Float grouping is independent of the
 * thread count. Other loops shrink chunks for short ranges, down to one index,
 * so a few long iterations (one per segment, say) still use every worker. */
static void parallel_run_grain(MinyarParallelEntry entry, long long first,
                               long long after, void *environment, int fixed) {
    if (first >= after) return;
    if (parallel_backend_run(entry, first, after, environment)) return;
#if (defined(__APPLE__) || defined(__linux__)) && !defined(MINYAR_FREESTANDING)
    pthread_once(&parallel_once, parallel_initialize);
    MinyarParallelPool *pool = &parallel_pool;
    uint64_t distance = (uint64_t)after - (uint64_t)first;
    uint64_t grain = MINYAR_PARALLEL_GRAIN;
    if (!fixed) {
        grain = distance / ((uint64_t)pool->count * 4);
        if (grain < 1) grain = 1;
        if (grain > MINYAR_PARALLEL_GRAIN) grain = MINYAR_PARALLEL_GRAIN;
    }
    if (pool->count == 1) { parallel_serial(entry, first, after, environment, grain); return; }
    uint64_t chunks = distance / grain + (distance % grain != 0);
    if (chunks == 1) { parallel_serial(entry, first, after, environment, grain); return; }
    MinyarParallelLoop loop = { entry, environment, first, after, grain };
    uint64_t middle = chunks / 2;
    MinyarParallelSpan left = { &loop, 0, middle };
    MinyarParallelSpan right = { &loop, middle, chunks };
    parallel_join(parallel_span, &left, parallel_span, &right);
#else
    (void)fixed;
    parallel_serial(entry, first, after, environment, MINYAR_PARALLEL_GRAIN);
#endif
}

void minyar_parallel_run(MinyarParallelEntry entry, long long first,
                         long long after, void *environment) {
    parallel_run_grain(entry, first, after, environment, 0);
}

/* `join(a, b)` from generated code: both thunks read their arguments from and
 * write their results to their own environment. */
void minyar_parallel_join(void (*a)(void *), void *a_environment,
                          void (*b)(void *), void *b_environment) {
#if (defined(__APPLE__) || defined(__linux__)) && !defined(MINYAR_FREESTANDING)
    parallel_join(a, a_environment, b, b_environment);
#else
    a(a_environment);
    b(b_environment);
#endif
}

/* Threads a safe parallel range runs on: MINYAR_PARALLEL_THREADS, else the online processors (at most 64). */
long long minyar_parallel_workers(void) {
#if (defined(__APPLE__) || defined(__linux__)) && !defined(MINYAR_FREESTANDING)
    pthread_once(&parallel_once, parallel_initialize);
    return (long long)parallel_pool.count;
#else
    return 1;
#endif
}


typedef long long (*MinyarParallelReduceEntry)(long long, long long, void *);
typedef struct {
    MinyarParallelReduceEntry entry;
    void *environment;
    long long first;
    long long *partials;
} MinyarParallelReduction;

static void parallel_reduce_chunk(long long first, long long after, void *environment) {
    MinyarParallelReduction *job = environment;
    uint64_t chunk = ((uint64_t)first - (uint64_t)job->first) / MINYAR_PARALLEL_GRAIN;
    job->partials[chunk] = job->entry(first, after, job->environment);
}

long long minyar_parallel_reduce(MinyarParallelReduceEntry entry, long long first,
                                 long long after, void *environment, long long type,
                                 long long initial) {
    if (first >= after) return initial;
    uint64_t distance = (uint64_t)after - (uint64_t)first;
    uint64_t chunks = distance / MINYAR_PARALLEL_GRAIN +
                      (distance % MINYAR_PARALLEL_GRAIN != 0);
    if (chunks > SIZE_MAX / sizeof(long long)) out_of_memory();
    /* The owner allocates and frees this profile-accounted raw buffer.
     * Each worker writes only the scalar word for its unique chunk. */
    long long *partials = data_allocate((size_t)chunks * sizeof(*partials), sizeof(*partials));
    MinyarParallelReduction job = { entry, environment, first, partials };
    parallel_run_grain(parallel_reduce_chunk, first, after, &job, 1);
    long long result = initial;
    if (type == 1) {
        for (uint64_t chunk = 0; chunk < chunks; ++chunk) {
            long long value = partials[chunk];
            if ((value > 0 && result > LLONG_MAX - value) ||
                (value < 0 && result < LLONG_MIN - value)) minyar_fail_integer_overflow();
            result += value;
        }
    } else {
        double sum;
        memcpy(&sum, &initial, sizeof(sum));
        for (uint64_t chunk = 0; chunk < chunks; ++chunk) {
            double value;
            memcpy(&value, &partials[chunk], sizeof(value));
            sum += value;
        }
        memcpy(&result, &sum, sizeof(result));
    }
#ifndef MINYAR_COMPILER_ARENA
    rc_free_data(partials);
#endif
    return result;
}
