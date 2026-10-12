#ifndef MINYAR_THREAD_BUFFERS_H
#define MINYAR_THREAD_BUFFERS_H
/* Managed threading fragment, included only by MINYAR_THREADED == 1.
 * Public pointers are domain-local RC leaves. Only native controls/buffers
 * cross threads; their strong counts are atomic from construction onward. */
#include <stdatomic.h>
#ifdef _WIN32
#include <process.h>
typedef SRWLOCK RcThreadMutex;
typedef CONDITION_VARIABLE RcThreadCondition;
static int rc_thread_mutex_init(RcThreadMutex *m) { InitializeSRWLock(m); return 0; }
static void rc_thread_mutex_lock(RcThreadMutex *m) { AcquireSRWLockExclusive(m); }
static void rc_thread_mutex_unlock(RcThreadMutex *m) { ReleaseSRWLockExclusive(m); }
static void rc_thread_mutex_destroy(RcThreadMutex *m) { (void)m; }
static int rc_thread_condition_init(RcThreadCondition *c) { InitializeConditionVariable(c); return 0; }
static void rc_thread_condition_wake(RcThreadCondition *c) { WakeAllConditionVariable(c); }
static void rc_thread_condition_destroy(RcThreadCondition *c) { (void)c; }
static void rc_thread_condition_wait(RcThreadCondition *c, RcThreadMutex *m) {
    if (!SleepConditionVariableSRW(c, m, INFINITE, 0))
        minyar_stop("a thread condition wait failed.");
}
#else
typedef pthread_mutex_t RcThreadMutex;
typedef pthread_cond_t RcThreadCondition;
static int rc_thread_mutex_init(RcThreadMutex *m) { return pthread_mutex_init(m, NULL); }
static void rc_thread_mutex_lock(RcThreadMutex *m) {
    if (pthread_mutex_lock(m)) minyar_stop("a thread mutex lock failed.");
}
static void rc_thread_mutex_unlock(RcThreadMutex *m) {
    if (pthread_mutex_unlock(m)) minyar_stop("a thread mutex unlock failed.");
}
static void rc_thread_mutex_destroy(RcThreadMutex *m) {
    if (pthread_mutex_destroy(m)) minyar_stop("a thread mutex destruction failed.");
}
static int rc_thread_condition_init(RcThreadCondition *c) { return pthread_cond_init(c, NULL); }
static void rc_thread_condition_wake(RcThreadCondition *c) {
    if (pthread_cond_broadcast(c)) minyar_stop("a thread condition wake failed.");
}
static void rc_thread_condition_destroy(RcThreadCondition *c) {
    if (pthread_cond_destroy(c)) minyar_stop("a thread condition destruction failed.");
}
static void rc_thread_condition_wait(RcThreadCondition *c, RcThreadMutex *m) {
    if (pthread_cond_wait(c, m)) minyar_stop("a thread condition wait failed.");
}
#endif

#ifdef MINYAR_RC_TESTING
static _Atomic size_t rc_thread_native_bytes, rc_thread_native_allocations;
static _Atomic size_t rc_thread_transit_bytes, rc_thread_transit_allocations;
static _Atomic size_t rc_thread_frozen_destructions;
static MINYAR_THREAD_LOCAL size_t rc_thread_test_fail_allocation_after = SIZE_MAX;
#define RC_NATIVE_ACCOUNT(expression) ((void)(expression))
#else
#define RC_NATIVE_ACCOUNT(expression) ((void)0)
#endif
static void *rc_thread_native_allocate(size_t size) {
#ifdef MINYAR_RC_TESTING
    if (rc_thread_test_fail_allocation_after != SIZE_MAX) {
        if (!rc_thread_test_fail_allocation_after) out_of_memory();
        rc_thread_test_fail_allocation_after--;
    }
#endif
    void *p = malloc(size);
    if (!p) out_of_memory();
    RC_NATIVE_ACCOUNT(atomic_fetch_add(&rc_thread_native_bytes, size));
    RC_NATIVE_ACCOUNT(atomic_fetch_add(&rc_thread_native_allocations, 1));
    return p;
}
static void rc_thread_native_free(void *p, size_t size) {
    (void)size;
    RC_NATIVE_ACCOUNT(atomic_fetch_sub(&rc_thread_native_bytes, size));
    RC_NATIVE_ACCOUNT(atomic_fetch_sub(&rc_thread_native_allocations, 1));
    free(p);
}

typedef struct {
    _Atomic size_t strong;
    void (*destroy)(void *);
} RcThreadControl;
static void rc_thread_control_init(RcThreadControl *c, size_t strong, void (*destroy)(void *)) {
    atomic_init(&c->strong, strong);
    c->destroy = destroy;
}
static void rc_thread_control_retain(void *pointer) {
    RcThreadControl *c = pointer;
    size_t old = atomic_load_explicit(&c->strong, memory_order_relaxed);
    for (;;) {
        if (!old || old == SIZE_MAX) minyar_stop("this shared value has too many references.");
        if (atomic_compare_exchange_weak_explicit(&c->strong, &old, old + 1,
                memory_order_relaxed, memory_order_relaxed)) return;
    }
}
static void rc_thread_control_release(void *pointer) {
    RcThreadControl *c = pointer;
    if (atomic_fetch_sub_explicit(&c->strong, 1, memory_order_acq_rel) == 1) {
        c->destroy(c);
    }
}
/* Takes an existing native share, never a foreign local owner. */
static RcThreadLeaf *rc_thread_wrap(void *control) {
    RcThreadLeaf *leaf = rc_allocate_object(sizeof(*leaf), 0);
    *leaf = (RcThreadLeaf){control, rc_thread_control_release};
    return leaf;
}

/* Permitted profiles both allocate the RcData prefix with libc; preserve
 * provenance explicitly rather than freeing the interior payload address. */
enum { RC_THREAD_EAGER_DATA = 1, RC_THREAD_SYSTEM_DATA = 2 };
typedef struct {
    RcData *data;
    long long length, capacity;
    unsigned allocator;
} RcThreadBuffer;
static inline size_t rc_thread_buffer_charge(RcThreadBuffer b) { return sizeof(*b.data) + b.data->size; }
static void rc_thread_validate_bytes(const MinyarBytes *b) {
    if (!b || b->backing || b->character_offsets || b->byte_length < 0 ||
        b->character_length < b->byte_length ||
        ((RcData *)b->bytes - 1)->size != (size_t)b->character_length + 1)
        minyar_stop("these Bytes cannot be detached.");
}
static RcThreadBuffer rc_thread_detach(MinyarBytes *b, unsigned char *replacement) {
    RcThreadBuffer result = {(RcData *)b->bytes - 1, b->byte_length, b->character_length,
#ifdef MINYAR_SYSTEM_HEAP
                            RC_THREAD_SYSTEM_DATA
#else
                            RC_THREAD_EAGER_DATA
#endif
    };
    RC_ACCOUNT(rc_bytes -= rc_thread_buffer_charge(result));
#ifdef MINYAR_BOUNDED_RC
    RC_ACCOUNT(rc_heap_allocation_count--);
#endif
    b->bytes = replacement;
    b->byte_length = b->character_length = 0;
    return result;
}
static void rc_thread_buffer_free(RcThreadBuffer b) {
    if (b.allocator != RC_THREAD_EAGER_DATA && b.allocator != RC_THREAD_SYSTEM_DATA)
        minyar_stop("a shared buffer has invalid allocator provenance.");
    free(b.data);
}
static void rc_thread_transit_add(RcThreadBuffer b) {
    (void)b;
    RC_NATIVE_ACCOUNT(atomic_fetch_add(&rc_thread_transit_bytes, rc_thread_buffer_charge(b)));
    RC_NATIVE_ACCOUNT(atomic_fetch_add(&rc_thread_transit_allocations, 1));
}
static void rc_thread_transit_remove(RcThreadBuffer b) {
    (void)b;
    RC_NATIVE_ACCOUNT(atomic_fetch_sub(&rc_thread_transit_bytes, rc_thread_buffer_charge(b)));
    RC_NATIVE_ACCOUNT(atomic_fetch_sub(&rc_thread_transit_allocations, 1));
}
static void rc_thread_buffer_adopt(MinyarBytes *b, RcThreadBuffer packet) {
    rc_free_data((void *)b->bytes);
    RC_ACCOUNT(rc_bytes += rc_thread_buffer_charge(packet));
#ifdef MINYAR_BOUNDED_RC
    RC_ACCOUNT(rc_heap_allocation_count++);
#endif
    b->bytes = (unsigned char *)(packet.data + 1);
    b->byte_length = packet.length;
    b->character_length = packet.capacity;
}

typedef struct { RcThreadControl owner; RcThreadBuffer buffer; } RcFrozenBytes;
static void rc_frozen_destroy(void *pointer) {
    RcFrozenBytes *f = pointer;
    RC_NATIVE_ACCOUNT(atomic_fetch_sub(&rc_thread_native_bytes, rc_thread_buffer_charge(f->buffer)));
    RC_NATIVE_ACCOUNT(atomic_fetch_sub(&rc_thread_native_allocations, 1));
    RC_NATIVE_ACCOUNT(atomic_fetch_add(&rc_thread_frozen_destructions, 1));
    rc_thread_buffer_free(f->buffer);
    rc_thread_native_free(f, sizeof(*f));
}
static RcThreadLeaf *rc_frozen_wrap_buffer(RcThreadBuffer buffer) {
    RcFrozenBytes *f = rc_thread_native_allocate(sizeof(*f));
    rc_thread_control_init(&f->owner, 1, rc_frozen_destroy);
    f->buffer = buffer;
    return rc_thread_wrap(f);
}
void *minyar_frozen_bytes_copy(const MinyarBytes *bytes) {
    size_t size = (size_t)bytes->byte_length + 1;
    RcData *data = rc_thread_native_allocate(sizeof(*data) + size);
    data->size = size;
    unsigned char *payload = (unsigned char *)(data + 1);
    memcpy(payload, bytes->bytes, size - 1);
    payload[size - 1] = 0;
    return rc_frozen_wrap_buffer((RcThreadBuffer){data, bytes->byte_length, bytes->byte_length,
                                                 RC_THREAD_EAGER_DATA});
}
void *minyar_frozen_bytes_take(MinyarBytes *bytes) {
    rc_thread_validate_bytes(bytes);
    unsigned char *replacement = rc_allocate_data(1);
    replacement[0] = 0;
    RcThreadBuffer packet = rc_thread_detach(bytes, replacement);
    RC_NATIVE_ACCOUNT(atomic_fetch_add(&rc_thread_native_bytes, rc_thread_buffer_charge(packet)));
    RC_NATIVE_ACCOUNT(atomic_fetch_add(&rc_thread_native_allocations, 1));
    return rc_frozen_wrap_buffer(packet);
}
static RcFrozenBytes *rc_frozen(const RcThreadLeaf *frozen) { return frozen->control; }
void *minyar_frozen_bytes_local_copy(const RcThreadLeaf *frozen) {
    RcThreadBuffer b = rc_frozen(frozen)->buffer;
    MinyarBytes *local = minyar_bytes_new(b.length);
    memcpy((void *)local->bytes, b.data + 1, (size_t)b.length);
    return local;
}
long long minyar_frozen_bytes_length(const RcThreadLeaf *frozen) { return rc_frozen(frozen)->buffer.length; }
static void rc_frozen_check(RcThreadBuffer b, long long position, long long size) {
    if (position < 0 || position > b.length - size)
        bytes_position_stop(position, size, b.length);
}
long long minyar_frozen_bytes_get_uint8(const RcThreadLeaf *frozen, long long position) {
    RcThreadBuffer b = rc_frozen(frozen)->buffer;
    rc_frozen_check(b, position, 1);
    return ((const unsigned char *)(b.data + 1))[position];
}
long long minyar_frozen_bytes_get_int64(const RcThreadLeaf *frozen, long long position) {
    RcThreadBuffer b = rc_frozen(frozen)->buffer;
    rc_frozen_check(b, position, 8);
    return (long long)bytes_load((const unsigned char *)(b.data + 1) + position, 8);
}

typedef union { RcThreadBuffer bytes; RcFrozenBytes *frozen; } RcChannelMessage;
enum { RC_CHANNEL_BYTES = 1, RC_CHANNEL_FROZEN = 2 };
typedef struct {
    RcThreadControl owner;
    RcThreadMutex mutex;
    RcThreadCondition changed;
    unsigned transport; /* Immutable before the first share is published. */
    size_t max_bytes, max_messages, retained_bytes, count, head;
    unsigned closed;
#ifdef MINYAR_RC_TESTING
    size_t waiters; /* Read/write only under the native mutex. */
#endif
    RcChannelMessage messages[];
} RcBytesChannel;
static void rc_channel_destroy(void *pointer) {
    RcBytesChannel *c = pointer;
    /* Last share implies no running or blocked operation; no foreign RC. */
    for (size_t i = 0; i < c->count; i++) {
        RcChannelMessage message = c->messages[(c->head + i) % c->max_messages];
        if (c->transport == RC_CHANNEL_FROZEN) rc_thread_control_release(message.frozen);
        else {
            rc_thread_transit_remove(message.bytes);
            rc_thread_buffer_free(message.bytes);
        }
    }
    rc_thread_condition_destroy(&c->changed);
    rc_thread_mutex_destroy(&c->mutex);
    rc_thread_native_free(c, sizeof(*c) + c->max_messages * sizeof(*c->messages));
}
static void *rc_channel_new(long long max_bytes, long long max_messages, unsigned transport) {
    if (max_bytes < 0 || max_messages <= 0 ||
        (unsigned long long)max_messages > (SIZE_MAX - sizeof(RcBytesChannel)) / sizeof(RcChannelMessage))
        minyar_stop("a BytesChannel needs nonnegative byte capacity and positive message capacity.");
    RcBytesChannel *c = rc_thread_native_allocate(sizeof(*c) + (size_t)max_messages * sizeof(*c->messages));
    rc_thread_control_init(&c->owner, 1, rc_channel_destroy);
    if (rc_thread_mutex_init(&c->mutex) || rc_thread_condition_init(&c->changed))
        minyar_stop("a BytesChannel could not be initialized.");
#ifdef MINYAR_RC_TESTING
    c->waiters = 0;
#endif
    c->transport = transport;
    c->max_bytes = (size_t)max_bytes;
    c->max_messages = (size_t)max_messages;
    c->retained_bytes = c->count = c->head = c->closed = 0;
    return rc_thread_wrap(c);
}
void *minyar_bytes_channel_new(long long max_bytes, long long max_messages) {
    return rc_channel_new(max_bytes, max_messages, RC_CHANNEL_BYTES);
}
static void rc_channel_require(RcBytesChannel *c, unsigned transport) {
    if (c->transport != transport) minyar_stop("this channel has the wrong message type.");
}
static void rc_channel_wait(RcBytesChannel *c) {
#ifdef MINYAR_RC_TESTING
    c->waiters++;
    rc_thread_condition_wake(&c->changed);
#endif
    rc_thread_condition_wait(&c->changed, &c->mutex);
#ifdef MINYAR_RC_TESTING
    c->waiters--;
#endif
}
static _Bool rc_channel_send(const RcThreadLeaf *channel, MinyarBytes *bytes, unsigned blocking) {
    rc_thread_validate_bytes(bytes);
    RcBytesChannel *c = channel->control;
    rc_channel_require(c, RC_CHANNEL_BYTES);
    rc_thread_control_retain(c); /* Operation pins the native owner through wait. */
    rc_thread_domain_drain(); /* Never run a collector under the channel lock. */
    size_t capacity = (size_t)bytes->character_length;
    if (capacity > c->max_bytes) { rc_thread_control_release(c); return 0; }
    unsigned char *replacement = rc_allocate_data(1);
    replacement[0] = 0;
    rc_thread_mutex_lock(&c->mutex);
    while (!c->closed && (c->count == c->max_messages || capacity > c->max_bytes - c->retained_bytes)) {
        if (!blocking) break;
        rc_channel_wait(c);
    }
    _Bool sent = !c->closed && c->count < c->max_messages && capacity <= c->max_bytes - c->retained_bytes;
    if (sent) {
        RcThreadBuffer b = rc_thread_detach(bytes, replacement);
        rc_thread_transit_add(b);
        c->messages[(c->head + c->count) % c->max_messages].bytes = b;
        c->count++;
        c->retained_bytes += capacity;
        rc_thread_condition_wake(&c->changed);
    }
    rc_thread_mutex_unlock(&c->mutex);
    if (!sent) rc_free_data(replacement);
    rc_thread_control_release(c);
    return sent;
}
_Bool minyar_bytes_channel_try_send(const RcThreadLeaf *channel, MinyarBytes *bytes) {
    return rc_channel_send(channel, bytes, 0);
}
_Bool minyar_bytes_channel_send(const RcThreadLeaf *channel, MinyarBytes *bytes) {
    return rc_channel_send(channel, bytes, 1);
}
static long long rc_channel_receive(const RcThreadLeaf *channel, MinyarBytes *destination, unsigned blocking) {
    rc_thread_validate_bytes(destination);
    RcBytesChannel *c = channel->control;
    rc_channel_require(c, RC_CHANNEL_BYTES);
    rc_thread_control_retain(c);
    rc_thread_domain_drain();
    rc_thread_mutex_lock(&c->mutex);
    while (!c->count && !c->closed && blocking) rc_channel_wait(c);
    long long status = c->count ? 1 : c->closed ? 2 : 0;
    RcThreadBuffer b = {0};
    if (status == 1) {
        b = c->messages[c->head].bytes;
        c->head = (c->head + 1) % c->max_messages;
        c->count--;
        c->retained_bytes -= (size_t)b.capacity;
        rc_thread_condition_wake(&c->changed);
    }
    rc_thread_mutex_unlock(&c->mutex);
    if (status == 1) {
        rc_thread_transit_remove(b);
        rc_thread_buffer_adopt(destination, b);
    }
    rc_thread_control_release(c);
    return status;
}
long long minyar_bytes_channel_try_receive(const RcThreadLeaf *channel, MinyarBytes *destination) {
    return rc_channel_receive(channel, destination, 0);
}
_Bool minyar_bytes_channel_receive(const RcThreadLeaf *channel, MinyarBytes *destination) {
    return rc_channel_receive(channel, destination, 1) == 1;
}
static void rc_channel_close(const RcThreadLeaf *channel) {
    RcBytesChannel *c = channel->control;
    rc_thread_control_retain(c);
    rc_thread_mutex_lock(&c->mutex);
    c->closed = 1;
    rc_thread_condition_wake(&c->changed);
    rc_thread_mutex_unlock(&c->mutex);
    rc_thread_control_release(c);
}

void minyar_bytes_channel_close(const RcThreadLeaf *channel) {
    rc_channel_require(channel->control, RC_CHANNEL_BYTES);
    rc_channel_close(channel);
}

void *minyar_frozen_channel_new(long long max_bytes, long long max_messages) {
    return rc_channel_new(max_bytes, max_messages, RC_CHANNEL_FROZEN);
}
static _Bool rc_frozen_channel_send(const RcThreadLeaf *channel, const RcThreadLeaf *frozen, unsigned blocking) {
    RcBytesChannel *c = channel->control;
    rc_channel_require(c, RC_CHANNEL_FROZEN);
    RcFrozenBytes *f = frozen->control;
    rc_thread_control_retain(c);
    rc_thread_domain_drain();
    size_t capacity = (size_t)f->buffer.capacity;
    if (capacity > c->max_bytes) { rc_thread_control_release(c); return 0; }
    rc_thread_mutex_lock(&c->mutex);
    while (!c->closed && (c->count == c->max_messages || capacity > c->max_bytes - c->retained_bytes)) {
        if (!blocking) break;
        rc_channel_wait(c);
    }
    _Bool sent = !c->closed && c->count < c->max_messages && capacity <= c->max_bytes - c->retained_bytes;
    if (sent) {
        rc_thread_control_retain(f);
        c->messages[(c->head + c->count) % c->max_messages].frozen = f;
        c->count++;
        c->retained_bytes += capacity;
        rc_thread_condition_wake(&c->changed);
    }
    rc_thread_mutex_unlock(&c->mutex);
    rc_thread_control_release(c);
    return sent;
}
_Bool minyar_frozen_channel_try_send(const RcThreadLeaf *channel, const RcThreadLeaf *frozen) {
    return rc_frozen_channel_send(channel, frozen, 0);
}
_Bool minyar_frozen_channel_send(const RcThreadLeaf *channel, const RcThreadLeaf *frozen) {
    return rc_frozen_channel_send(channel, frozen, 1);
}
static void *rc_frozen_channel_receive(const RcThreadLeaf *channel, unsigned blocking) {
    RcBytesChannel *c = channel->control;
    rc_channel_require(c, RC_CHANNEL_FROZEN);
    rc_thread_control_retain(c);
    rc_thread_domain_drain();
    rc_thread_mutex_lock(&c->mutex);
    while (!c->count && !c->closed && blocking) rc_channel_wait(c);
    long long status = c->count ? 0 : c->closed ? 2 : 1;
    RcFrozenBytes *frozen = NULL;
    if (status == 0) {
        frozen = c->messages[c->head].frozen;
        c->head = (c->head + 1) % c->max_messages;
        c->count--;
        c->retained_bytes -= (size_t)frozen->buffer.capacity;
        rc_thread_condition_wake(&c->changed);
    }
    rc_thread_mutex_unlock(&c->mutex);
    /* Queue share becomes a fresh local shell's share; no payload copy. */
    RcThreadLeaf *leaf = frozen ? rc_thread_wrap(frozen) : NULL;
    MinyarRecord *record = minyar_record_new(2);
    minyar_record_set(record, 0, status);
    minyar_record_set_reference(record, 1, (long long)(uintptr_t)leaf);
    minyar_rc_release(leaf);
    rc_thread_control_release(c);
    return record;
}
void *minyar_frozen_channel_try_receive(const RcThreadLeaf *channel) {
    return rc_frozen_channel_receive(channel, 0);
}
void *minyar_frozen_channel_receive(const RcThreadLeaf *channel) {
    return rc_frozen_channel_receive(channel, 1);
}
void minyar_frozen_channel_close(const RcThreadLeaf *channel) {
    rc_channel_require(channel->control, RC_CHANNEL_FROZEN);
    rc_channel_close(channel);
}
long long minyar_frozen_result_code(const MinyarRecord *result) { return minyar_record_get(result, 0); }
void *minyar_frozen_result_value(const MinyarRecord *result) {
    if (minyar_record_get(result, 0) != 0)
        minyar_stop("an unsuccessful FrozenBytes Result has no value.");
    void *frozen = (void *)(uintptr_t)minyar_record_get(result, 1);
    minyar_rc_retain(frozen);
    return frozen;
}

#endif
