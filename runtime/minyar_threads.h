/* Managed OS-thread lifecycle. Native controls outlive local shells,
 * blocked joins and running packets; descendants always join before exit. */
#ifdef MINYAR_RC_TESTING
static _Atomic size_t rc_thread_domain_exits, rc_thread_native_joins;
static MINYAR_THREAD_LOCAL unsigned rc_thread_test_fail_start, rc_thread_test_fail_join;
#endif
typedef long long (*RcThreadBridge)(long long, void *, void *);
typedef struct RcManagedThread {
    RcThreadControl owner;
    RcThreadMutex mutex;
    RcThreadCondition changed;
#ifdef _WIN32
    HANDLE thread;
#else
    pthread_t thread;
#endif
    unsigned joining, joined, finished;
    long long result, status;
    /* Accessed only by the creator domain, never by the worker/destructor. */
    struct RcManagedThread *parent_next;
} RcManagedThread;
static MINYAR_THREAD_LOCAL RcManagedThread *rc_thread_children, *rc_thread_current;
/* A packet entry receives its unpacked arguments as language slots. */
typedef long long (*RcPacketBridge)(const long long *);
typedef struct {
    RcManagedThread *thread;
    RcThreadBridge bridge;
    long long seed;
    RcFrozenBytes *frozen;
    RcBytesChannel *channel;
    RcPacketBridge packet_bridge;
    RcPacket *packet;
} RcThreadLaunch;
static void rc_managed_thread_destroy(void *pointer) {
    RcManagedThread *t = pointer;
#ifdef _WIN32
    if (t->thread) CloseHandle(t->thread);
#endif
    rc_thread_condition_destroy(&t->changed);
    rc_thread_mutex_destroy(&t->mutex);
    rc_thread_native_free(t, sizeof(*t));
}
void minyar_thread_join_children(void);
#ifdef _WIN32
static unsigned __stdcall rc_thread_entry(void *pointer) {
#else
static void *rc_thread_entry(void *pointer) {
#endif
    minyar_stack_guard_attach_thread();
    RcThreadLaunch launch = *(RcThreadLaunch *)pointer;
    rc_thread_native_free(pointer, sizeof(launch));
    rc_thread_domain_init();
    rc_thread_current = launch.thread;
    long long result;
    long long *arguments = NULL;
    long long argument_count = 0;
    if (launch.packet) {
        /* Rebuild every argument in this domain; the guard frame owns them. */
        const char *field = rc_descriptor_count(launch.packet->descriptor + 1, &argument_count);
        arguments = rc_thread_native_allocate((size_t)(argument_count ? argument_count : 1) * sizeof(long long));
        minyar_rc_enter(argument_count);
        const long long *words = launch.packet->words;
        for (long long i = 0; i < argument_count; ++i) {
            int reference = rc_descriptor_reference(field);
            field = rc_packet_get(&words, field, &arguments[i]);
            if (reference) minyar_rc_local_take(i, (void *)(uintptr_t)arguments[i]);
        }
        rc_packet_free(launch.packet, 1);
        result = launch.packet_bridge(arguments);
    } else {
        /* The guard frame owns fresh wrappers independently of the entry's
         * generated borrowing convention. The launch packet owned their shares. */
        minyar_rc_enter(2);
        RcThreadLeaf *frozen = rc_thread_wrap(launch.frozen);
        minyar_rc_local_take(0, frozen);
        RcThreadLeaf *channel = rc_thread_wrap(launch.channel);
        minyar_rc_local_take(1, channel);
        result = launch.bridge(launch.seed, frozen, channel);
    }
    long long status = minyar_recovery_pending() ? 2 : 0;
    minyar_thread_join_children();
    minyar_rc_leave();
    if (arguments) rc_thread_native_free(arguments, (size_t)(argument_count ? argument_count : 1) * sizeof(long long));
    rc_thread_domain_dispose();
    RC_NATIVE_ACCOUNT(atomic_fetch_add(&rc_thread_domain_exits, 1));
    RcManagedThread *t = launch.thread;
    rc_thread_mutex_lock(&t->mutex);
    t->result = result;
    t->status = status;
    t->finished = 1;
    rc_thread_mutex_unlock(&t->mutex);
    rc_thread_current = NULL;
    rc_thread_control_release(t); /* Running share survives all local teardown. */
    minyar_stack_guard_detach();
#ifdef _WIN32
    return 0;
#else
    return NULL;
#endif
}

/* Internal status protocol: allocations remain process fatal. Recoverable OS
 * failures preserve caller ownership and output; convenience exports stop. */
static long long rc_thread_launch_try(RcThreadLaunch prepared, void **output);
static long long rc_thread_spawn_try(RcThreadBridge bridge, long long seed,
        const RcThreadLeaf *frozen, const RcThreadLeaf *channel, void **output) {
    return rc_thread_launch_try((RcThreadLaunch){NULL, bridge, seed, frozen->control, channel->control, NULL, NULL}, output);
}
/* Takes the packet in every outcome. */
static long long rc_thread_spawn_packet_try(RcPacketBridge bridge, RcPacket *packet, void **output) {
    if (packet->cursor) rc_transfer_invalid();
    return rc_thread_launch_try((RcThreadLaunch){NULL, NULL, 0, NULL, NULL, bridge, packet}, output);
}
static long long rc_thread_launch_try(RcThreadLaunch prepared, void **output) {
    RcManagedThread *t = rc_thread_native_allocate(sizeof(*t));
    memset(t, 0, sizeof(*t));
    if (rc_thread_mutex_init(&t->mutex)) {
        rc_thread_native_free(t, sizeof(*t));
        if (prepared.packet) rc_packet_free(prepared.packet, 0);
        return 2;
    }
    if (rc_thread_condition_init(&t->changed)) {
        rc_thread_mutex_destroy(&t->mutex);
        rc_thread_native_free(t, sizeof(*t));
        if (prepared.packet) rc_packet_free(prepared.packet, 0);
        return 2;
    }
    /* One share each for returned wrapper, parent registry, running packet. */
    rc_thread_control_init(&t->owner, 3, rc_managed_thread_destroy);
    RcThreadLaunch *launch = rc_thread_native_allocate(sizeof(*launch));
    *launch = prepared;
    launch->thread = t;
    if (!launch->packet) {
        rc_thread_control_retain(launch->frozen);
        rc_thread_control_retain(launch->channel);
    }
#ifdef MINYAR_RC_TESTING
    int failed = rc_thread_test_fail_start != 0;
#else
    int failed = 0;
#endif
    if (!failed) {
#ifdef _WIN32
        t->thread = (HANDLE)_beginthreadex(NULL, 0, rc_thread_entry, launch, 0, NULL);
        failed = !t->thread;
#else
        pthread_attr_t storage;
        pthread_attr_t *attributes = minyar_guarded_thread_attributes(&storage);
        failed = pthread_create(&t->thread, attributes, rc_thread_entry, launch) != 0;
        if (attributes) pthread_attr_destroy(attributes);
#endif
    }
    if (failed) {
        if (launch->packet) rc_packet_free(launch->packet, 0);
        else {
            rc_thread_control_release(launch->frozen);
            rc_thread_control_release(launch->channel);
        }
        rc_thread_native_free(launch, sizeof(*launch));
        rc_thread_control_release(t);
        rc_thread_control_release(t);
        rc_thread_control_release(t);
        return 2;
    }
    t->parent_next = rc_thread_children;
    rc_thread_children = t;
    *output = rc_thread_wrap(t);
    return 0;
}
void *minyar_thread_spawn(RcThreadBridge bridge, long long seed,
                         const RcThreadLeaf *frozen, const RcThreadLeaf *channel) {
    void *result;
    if (rc_thread_spawn_try(bridge, seed, frozen, channel, &result))
        minyar_stop("the system could not start this thread.");
    return result;
}
static long long rc_thread_join_try(RcManagedThread *t, long long *output) {
    if (t == rc_thread_current) return 1;
    rc_thread_control_retain(t); /* Includes each blocked joiner's lifetime. */
    rc_thread_domain_drain();
    rc_thread_mutex_lock(&t->mutex);
    while (t->joining && !t->joined) rc_thread_condition_wait(&t->changed, &t->mutex);
    if (!t->joined) {
        t->joining = 1;
        rc_thread_mutex_unlock(&t->mutex);
#ifdef MINYAR_RC_TESTING
        int failed = rc_thread_test_fail_join != 0;
#else
        int failed = 0;
#endif
        if (!failed) {
#ifdef _WIN32
            failed = WaitForSingleObject(t->thread, INFINITE) != WAIT_OBJECT_0;
#else
            failed = pthread_join(t->thread, NULL) != 0;
#endif
        }
        rc_thread_mutex_lock(&t->mutex);
        t->joining = 0;
        if (!failed) {
            t->joined = 1;
            RC_NATIVE_ACCOUNT(atomic_fetch_add(&rc_thread_native_joins, 1));
        }
        rc_thread_condition_wake(&t->changed);
        if (failed) {
            rc_thread_mutex_unlock(&t->mutex);
            rc_thread_control_release(t);
            return 2;
        }
    }
    long long status = t->status;
    if (!status) *output = t->result;
    rc_thread_mutex_unlock(&t->mutex);
    rc_thread_control_release(t);
    return status ? 3 : 0;
}
static void rc_thread_untrack_joined(RcManagedThread *thread) {
    /* Only the creator's TLS registry can contain this control. A foreign
     * joiner has its own list and never reads/writes the creator's links. */
    RcManagedThread **link = &rc_thread_children;
    while (*link && *link != thread) link = &(*link)->parent_next;
    if (*link) {
        *link = thread->parent_next;
        thread->parent_next = NULL;
        rc_thread_control_release(thread);
    }
}
long long minyar_thread_join(const RcThreadLeaf *thread) {
    long long result;
    long long status = rc_thread_join_try(thread->control, &result);
    if (!status || status == 3) rc_thread_untrack_joined(thread->control);
    if (status)
        minyar_stop("this thread could not be joined.");
    return result;
}
void minyar_thread_join_children(void) {
    while (rc_thread_children) {
        RcManagedThread *t = rc_thread_children;
        long long result;
        long long status = rc_thread_join_try(t, &result);
        if (status && status != 3) minyar_stop("a child thread could not be joined.");
        rc_thread_children = t->parent_next;
        rc_thread_control_release(t);
    }
}

void *minyar_thread_spawn_packet(RcPacketBridge bridge, RcPacket *packet) {
    void *result;
    if (rc_thread_spawn_packet_try(bridge, packet, &result))
        minyar_stop("the system could not start this thread.");
    return result;
}
void *minyar_thread_spawn_packet_result(RcPacketBridge bridge, RcPacket *packet) {
    void *thread = NULL;
    long long status = rc_thread_spawn_packet_try(bridge, packet, &thread);
    MinyarRecord *record = minyar_record_new(2);
    minyar_record_set(record, 0, status);
    minyar_record_set_reference(record, 1, (long long)(uintptr_t)thread);
    minyar_rc_release(thread);
    return record;
}

long long minyar_thread_try_spawn(RcThreadBridge bridge, long long seed,
        const RcThreadLeaf *frozen, const RcThreadLeaf *channel, void **output) {
    return rc_thread_spawn_try(bridge, seed, frozen, channel, output);
}
long long minyar_thread_try_join(const RcThreadLeaf *thread, long long *output) {
    long long status = rc_thread_join_try(thread->control, output);
    if (!status || status == 3) rc_thread_untrack_joined(thread->control);
    return status == 3 ? 2 : status;
}
void *minyar_thread_spawn_result(RcThreadBridge bridge, long long seed,
        const RcThreadLeaf *frozen, const RcThreadLeaf *channel) {
    void *thread = NULL;
    long long status = minyar_thread_try_spawn(bridge, seed, frozen, channel, &thread);
    MinyarRecord *record = minyar_record_new(2);
    minyar_record_set(record, 0, status);
    minyar_record_set_reference(record, 1, (long long)(uintptr_t)thread);
    minyar_rc_release(thread); /* Record's own field now owns the local wrapper. */
    return record;
}
void *minyar_thread_join_result(const RcThreadLeaf *thread) {
    long long result = 0;
    long long status = minyar_thread_try_join(thread, &result);
    MinyarRecord *record = minyar_record_new_scalar(2);
    minyar_record_set_scalar(record, 0, status);
    minyar_record_set_scalar(record, 1, result);
    return record;
}

long long minyar_thread_result_code(const MinyarRecord *result) {
    return minyar_record_get(result, 0);
}
static long long rc_thread_result_payload(const MinyarRecord *result) {
    if (minyar_record_get(result, 0) != 0)
        minyar_stop("a failed thread Result has no value.");
    return minyar_record_get(result, 1);
}
void *minyar_thread_start_result_value(const MinyarRecord *result) {
    void *thread = (void *)(uintptr_t)rc_thread_result_payload(result);
    minyar_rc_retain(thread);
    return thread;
}
long long minyar_thread_join_result_value(const MinyarRecord *result) {
    return rc_thread_result_payload(result);
}
