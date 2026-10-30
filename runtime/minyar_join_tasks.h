/* `join` over ordinary functions in a thread program. Included only when
 * MINYAR_THREADED == 1, after the transfer packets and the pool.
 *
 * Every OS thread of a thread program is its own ownership domain, and so is
 * each pool worker. A branch runs in the domain of whichever participant runs
 * it: the joining thread (always, with one pool thread) or a worker that stole
 * it. Managed arguments were packed once at the fork, so each branch rebuilds
 * its own copy wherever it runs, as a thread entry does. A branch that ran on
 * the joining thread leaves its owned result in its slot; a stolen branch packs
 * the result, which the joining thread rebuilds after the join. No managed
 * object is ever reachable from two domains. */

typedef struct {
    void (*thunk)(void *);  /* Reads slots[0..count), calls, stores slots[count]. */
    long long *slots;
    long long count;
    const char *arguments;  /* "rN." of every parameter when any is managed, else NULL. */
    const char *result;     /* The result's transfer descriptor. */
    RcPacket *packet;       /* Packed arguments, then a stolen branch's result. */
    void *domain;           /* The joining thread's domain. */
} MinyarJoinTask;

static inline void *rc_join_domain(void) { return (void *)&rc_frames; }

static void rc_join_task_run(void *pointer) {
    MinyarJoinTask *task = pointer;
#ifdef MINYAR_RC_TESTING
    size_t live_before = rc_object_count - rc_immortal_object_count;
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
    if (task->domain != rc_join_domain()) {
        /* Stolen: hand the result over as a packet and leave this worker's
         * domain with no pending releases. */
        if (rc_descriptor_reference(task->result)) {
            long long value = task->slots[task->count];
            RcPacket *packet = rc_packet_new(task->result);
            rc_packet_put(packet, task->result, value);
            minyar_rc_release((void *)(uintptr_t)value);
            task->packet = packet;
        }
        rc_thread_domain_drain();
#ifdef MINYAR_RC_TESTING
        /* The worker may be inside another branch of its own; this one must
         * leave nothing behind in it. */
        if (rc_object_count - rc_immortal_object_count > live_before) minyar_stop("a stolen join branch left managed values on its worker.");
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
    minyar_join_task_pack(left);
    minyar_join_task_pack(right);
    minyar_parallel_join(rc_join_task_run, left, rc_join_task_run, right);
}

/* The branch's result as an owned value of the joining domain. */
long long minyar_join_task_result(MinyarJoinTask *task) {
    RcPacket *packet = task->packet;
    if (!packet) return task->slots[task->count];
    task->packet = NULL;
    const long long *words = packet->words;
    long long value;
    rc_packet_get(&words, task->result, &value);
    rc_packet_free(packet, 1);
    return value;
}
