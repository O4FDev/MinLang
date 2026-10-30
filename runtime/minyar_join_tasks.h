/* `join` over ordinary functions in a thread program. Included only when
 * MINYAR_THREADED == 1, after the transfer packets and the pool.
 *
 * Every OS thread of a thread program is its own ownership domain, and so is
 * each pool worker. A branch runs in the domain of whichever participant runs
 * it: the joining thread (always, with one pool thread) or a worker that stole
 * it. Managed arguments were packed once at the fork, so each branch rebuilds
 * its own copy wherever it runs, as a thread entry does.
 *
 * A branch that ran on the joining thread leaves its owned result in its slot.
 * A stolen branch runs on fresh small-heap pages with empty ownership caches;
 * when it returns, its deferred releases are finished, so the only live
 * objects on those pages are its result. The pages travel with the result and
 * the joining thread adopts them: the result moves without a copy, and no
 * managed object is reachable from two domains at once. Without the small
 * heap (sanitizer builds) every object is a malloc block, which any thread may
 * free, so the result moves the same way. The cycle runtime, whose collector
 * keeps per-thread lists of traced objects, copies the result instead. */

#ifndef MINYAR_MAP_CYCLE_RUNTIME
#define MINYAR_JOIN_ADOPT 1
#endif
#if defined(MINYAR_JOIN_ADOPT) && MINYAR_SYSTEM_SMALL_HEAP
#define MINYAR_JOIN_PAGES 1
#endif

typedef struct {
    void (*thunk)(void *);  /* Reads slots[0..count), calls, stores slots[count]. */
    long long *slots;
    long long count;
    const char *arguments;  /* "rN." of every parameter when any is managed, else NULL. */
    const char *result;     /* The result's transfer descriptor. */
    RcPacket *packet;       /* Packed arguments, then a stolen branch's copied result. */
    void *domain;           /* The joining thread's domain. */
    long long stolen;
#ifdef MINYAR_JOIN_PAGES
    RcSystemHeap heap;      /* A stolen branch's pages, holding its result. */
#endif
#ifdef MINYAR_RC_TESTING
    size_t objects, bytes, allocations;
#endif
} MinyarJoinTask;

static inline void *rc_join_domain(void) { return (void *)&rc_frames; }

#ifdef MINYAR_JOIN_ADOPT
typedef struct {
    RcFrame *free_frames;
#ifdef MINYAR_BOUNDED_RC
    size_t cached_frame_bytes;
#ifdef MINYAR_BOUNDED_OWNER_CACHE
    RcTemporaryChunk *cached_chunk;
#endif
#endif
#ifdef MINYAR_JOIN_PAGES
    RcSystemHeap heap;
#endif
#ifdef MINYAR_RC_TESTING
    size_t objects, bytes, allocations;
#endif
} RcJoinSaved;
/* Generated code reserves 24 words for each task (compiler/join-compiler.min). */
_Static_assert(sizeof(MinyarJoinTask) <= 24 * sizeof(long long), "a join task must fit its generated storage");

/* Before a stolen branch: finish this domain's own deferred releases, so no
 * object of the suspended work is freed while the branch's pages are current,
 * and set aside every per-thread cache that holds heap storage. */
static void rc_join_enter_foreign(RcJoinSaved *saved) {
    rc_thread_domain_drain();
    saved->free_frames = rc_free_frames;
    rc_free_frames = NULL;
#ifdef MINYAR_BOUNDED_RC
    saved->cached_frame_bytes = rc_bounded_cached_frame_bytes;
    rc_bounded_cached_frame_bytes = 0;
#ifdef MINYAR_BOUNDED_OWNER_CACHE
    saved->cached_chunk = rc_bounded_cached_chunk;
    rc_bounded_cached_chunk = NULL;
#endif
#endif
#ifdef MINYAR_JOIN_PAGES
    memset(&saved->heap, 0, sizeof(saved->heap));
    rc_system_swap(&saved->heap);
#endif
#ifdef MINYAR_RC_TESTING
    saved->objects = rc_object_count;
    saved->bytes = rc_bytes;
    saved->allocations = rc_heap_allocation_count;
#endif
    rc_join_foreign++;
}

/* After it: free the branch's garbage and caches on its own pages, detach the
 * pages for the joining thread and restore this thread's state. */
static void rc_join_leave_foreign(RcJoinSaved *saved, MinyarJoinTask *task) {
    rc_thread_domain_drain();
    while (rc_free_frames) {
        RcFrame *frame = rc_free_frames;
        rc_free_frames = frame->previous;
#ifdef MINYAR_BOUNDED_RC
        rc_heap_deallocate(frame->locals);
        rc_heap_deallocate(frame);
#else
        free(frame->locals);
        free(frame->temporaries);
        free(frame);
#endif
    }
#ifdef MINYAR_BOUNDED_RC
#ifdef MINYAR_BOUNDED_OWNER_CACHE
    rc_bounded_chunk_cache_clear();
    rc_bounded_cached_chunk = saved->cached_chunk;
#endif
    rc_bounded_cached_frame_bytes = saved->cached_frame_bytes;
#endif
    rc_free_frames = saved->free_frames;
#ifdef MINYAR_JOIN_PAGES
    /* The branch's lists move into the task; this thread's come back. */
    memset(&task->heap, 0, sizeof(task->heap));
    rc_system_swap(&task->heap);
    rc_system_swap(&saved->heap);
#endif
#ifdef MINYAR_RC_TESTING
    /* What the branch left alive belongs to the joining thread from now on. */
    task->objects = rc_object_count - saved->objects;
    task->bytes = rc_bytes - saved->bytes;
    task->allocations = rc_heap_allocation_count - saved->allocations;
    rc_object_count = saved->objects;
    rc_bytes = saved->bytes;
    rc_heap_allocation_count = saved->allocations;
#endif
    rc_join_foreign--;
}
#endif

static void rc_join_task_run(void *pointer) {
    MinyarJoinTask *task = pointer;
    int foreign = task->domain != rc_join_domain();
#ifdef MINYAR_JOIN_ADOPT
    RcJoinSaved saved;
    if (foreign) rc_join_enter_foreign(&saved);
#endif
    if (task->arguments) {
        /* The guard frame owns the rebuilt arguments; the callee borrows them. */
        long long count;
        const char *field = rc_descriptor_count(task->arguments + 1, &count);
        if (count != task->count) rc_transfer_invalid();
        minyar_rc_enter(count);
        const long long *words = task->packet->words;
        for (long long i = 0; i < count; ++i) {
            int reference = rc_descriptor_reference(field);
            field = rc_packet_get(&words, field, &task->slots[i]);
            if (reference) minyar_rc_local_take(i, (void *)(uintptr_t)task->slots[i]);
        }
        rc_packet_free(task->packet, 1);
        task->packet = NULL;
    }
    task->thunk(task->slots);
    if (task->arguments) minyar_rc_leave();
    if (foreign) {
        task->stolen = 1;
#ifdef MINYAR_JOIN_ADOPT
        rc_join_leave_foreign(&saved, task);
#else
        if (rc_descriptor_reference(task->result)) {
            long long value = task->slots[task->count];
            RcPacket *packet = rc_packet_new(task->result);
            rc_packet_put(packet, task->result, value);
            minyar_rc_release((void *)(uintptr_t)value);
            task->packet = packet;
        }
        rc_thread_domain_drain();
#endif
    }
}

/* Packs one branch's arguments at the fork; `slots` holds them as words. */
void minyar_join_task_pack(MinyarJoinTask *task) {
    if (!task->arguments) return;
    RcPacket *packet = rc_packet_new(task->arguments);
    long long count;
    const char *field = rc_descriptor_count(task->arguments + 1, &count);
    if (count != task->count) rc_transfer_invalid();
    for (long long i = 0; i < count; ++i) field = rc_packet_put(packet, field, task->slots[i]);
    task->packet = packet;
}

void minyar_join_tasks(MinyarJoinTask *left, MinyarJoinTask *right) {
    void *domain = rc_join_domain();
    left->domain = domain;
    right->domain = domain;
    left->packet = NULL;
    right->packet = NULL;
    left->stolen = 0;
    right->stolen = 0;
    minyar_join_task_pack(left);
    minyar_join_task_pack(right);
    minyar_parallel_join(rc_join_task_run, left, rc_join_task_run, right);
}

/* The branch's result as an owned value of the joining domain. */
long long minyar_join_task_result(MinyarJoinTask *task) {
    if (!task->stolen) return task->slots[task->count];
    task->stolen = 0;
#if defined(MINYAR_RC_TESTING) && defined(MINYAR_JOIN_ADOPT)
    rc_object_count += task->objects;
    rc_bytes += task->bytes;
    rc_heap_allocation_count += task->allocations;
#endif
#ifdef MINYAR_JOIN_PAGES
    rc_system_adopt(&task->heap);
#endif
#ifdef MINYAR_JOIN_ADOPT
    return task->slots[task->count];
#else
    RcPacket *packet = task->packet;
    if (!packet) return task->slots[task->count];
    task->packet = NULL;
    const long long *words = packet->words;
    long long value;
    rc_packet_get(&words, task->result, &value);
    rc_packet_free(packet, 1);
    return value;
#endif
}
