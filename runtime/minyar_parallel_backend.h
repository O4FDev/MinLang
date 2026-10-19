/* Trusted processor-entry integration. The scheduler must finish every chunk
 * before returning; the dispatcher and environment live on the owner stack. */
typedef void (*MinyarParallelScheduler)(long long, long long, long long, long long);
static MinyarParallelScheduler parallel_scheduler;
static long long parallel_scheduler_context;

typedef struct {
    MinyarParallelEntry entry;
    void *environment;
    long long first, after;
} MinyarParallelDispatch;

void minyar_runtime_setParallelScheduler(long long entry, long long context) {
    parallel_scheduler = (MinyarParallelScheduler)(uintptr_t)entry;
    parallel_scheduler_context = context;
}

static void parallel_dispatch(long long item, long long argument) {
    MinyarParallelDispatch *job = (MinyarParallelDispatch *)(uintptr_t)argument;
#if defined(__APPLE__) || defined(__linux__)
    int previous = minyar_parallel_active;
    minyar_parallel_active = 1;
#endif
    uint64_t distance = (uint64_t)job->after - (uint64_t)job->first;
    uint64_t chunks = distance / MINYAR_PARALLEL_GRAIN +
                      (distance % MINYAR_PARALLEL_GRAIN != 0);
    if (item < 0 || (uint64_t)item >= chunks)
        minyar_stop("the native parallel scheduler supplied an invalid chunk.");
    parallel_chunk(job->entry, job->environment, job->first, job->after, (uint64_t)item);
#if defined(__APPLE__) || defined(__linux__)
    minyar_parallel_active = previous;
#endif
}

static int parallel_backend_run(MinyarParallelEntry entry, long long first,
                                 long long after, void *environment) {
    if (!parallel_scheduler) return 0;
    uint64_t distance = (uint64_t)after - (uint64_t)first;
    uint64_t chunks = distance / MINYAR_PARALLEL_GRAIN +
                      (distance % MINYAR_PARALLEL_GRAIN != 0);
    MinyarParallelDispatch job = { entry, environment, first, after };
    parallel_scheduler(parallel_scheduler_context, (long long)(uintptr_t)parallel_dispatch,
                       (long long)chunks, (long long)(uintptr_t)&job);
    return 1;
}
