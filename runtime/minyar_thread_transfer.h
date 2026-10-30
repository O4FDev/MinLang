#ifndef MINYAR_THREAD_TRANSFER_H
#define MINYAR_THREAD_TRANSFER_H
/* Managed threading fragment, included only by MINYAR_THREADED == 1.
 *
 * Values cross threads as packets: the sender copies a value graph into
 * unmanaged words, and the receiver rebuilds it in its own domain. No managed
 * object is ever reachable from two domains, so reference counts stay local.
 * Shared handles (FrozenBytes, channels, queues, atomics) carry one native
 * share each; the receiver wraps it in a fresh local leaf.
 *
 * The compiler emits each sendable type's descriptor as a constant string:
 *   i        one scalar slot (Integer, Float, Boolean, Character, enum)
 *   t / b    Text / Bytes
 *   h        shared handle (an RcThreadLeaf around an RcThreadControl)
 *   l D      List of D
 *   r N . D1 ... DN   record of N fields
 * Reference values may be null; each one starts with a presence word. */
#include <stdatomic.h>
#include <limits.h>
#include <time.h>
#ifndef _WIN32
#include <errno.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <unistd.h>
#endif

typedef struct RcPacket {
    struct RcPacket *next;
    const char *descriptor; /* Program-lifetime constant. */
    const char *cursor;     /* Next field while a tuple is being built. */
    long long fields_left;
    long long *words;
    size_t length, capacity;
} RcPacket;

static _Noreturn void rc_transfer_invalid(void) {
    minyar_stop("a thread value descriptor is invalid.");
}

static const char *rc_descriptor_count(const char *d, long long *count) {
    long long n = 0;
    if (*d < '0' || *d > '9') rc_transfer_invalid();
    while (*d >= '0' && *d <= '9') {
        if (n > (LLONG_MAX - 9) / 10) rc_transfer_invalid();
        n = n * 10 + (*d++ - '0');
    }
    if (*d++ != '.') rc_transfer_invalid();
    *count = n;
    return d;
}

/* The first byte after one complete descriptor. */
static const char *rc_descriptor_skip(const char *d) {
    switch (*d) {
    case 'i': case 't': case 'b': case 'h': return d + 1;
    case 'l': return rc_descriptor_skip(d + 1);
    case 'r': {
        long long n;
        d = rc_descriptor_count(d + 1, &n);
        while (n-- > 0) d = rc_descriptor_skip(d);
        return d;
    }
    default: rc_transfer_invalid();
    }
}

static int rc_descriptor_reference(const char *d) { return *d != 'i'; }

static void rc_packet_reserve(RcPacket *p, size_t extra) {
    if (extra > SIZE_MAX / sizeof(long long) - p->length) out_of_memory();
    size_t needed = p->length + extra;
    if (needed <= p->capacity) return;
    size_t capacity = p->capacity ? p->capacity : 8;
    while (capacity < needed) {
        if (capacity > SIZE_MAX / 2 / sizeof(long long)) { capacity = needed; break; }
        capacity *= 2;
    }
    long long *words = realloc(p->words, capacity * sizeof(long long));
    if (!words) out_of_memory();
    p->words = words;
    p->capacity = capacity;
}

static void rc_packet_word(RcPacket *p, long long word) {
    rc_packet_reserve(p, 1);
    p->words[p->length++] = word;
}

static void rc_packet_data(RcPacket *p, const unsigned char *bytes, long long length) {
    size_t words = ((size_t)length + 7) / 8;
    rc_packet_reserve(p, words);
    if (words) {
        p->words[p->length + words - 1] = 0;
        memcpy(p->words + p->length, bytes, (size_t)length);
    }
    p->length += words;
}

/* Copies one value; returns the descriptor after it. */
static const char *rc_packet_put(RcPacket *p, const char *d, long long slot) {
    if (*d == 'i') { rc_packet_word(p, slot); return d + 1; }
    const char *after = rc_descriptor_skip(d);
    void *value = (void *)(uintptr_t)slot;
    if (!value) { rc_packet_word(p, 0); return after; }
    rc_packet_word(p, 1);
    switch (*d) {
    case 't': case 'b': {
        const MinyarText *text = value;
        rc_packet_word(p, text->byte_length);
        rc_packet_word(p, *d == 't' ? text->character_length : 0);
        rc_packet_data(p, text->bytes, text->byte_length);
        break;
    }
    case 'h': {
        const RcThreadLeaf *leaf = value;
        rc_thread_control_retain(leaf->control);
        rc_packet_word(p, (long long)(uintptr_t)leaf->control);
        break;
    }
    case 'l': {
        const MinyarList *list = value;
        rc_packet_word(p, list->length);
        if (d[1] == 'i') {
            rc_packet_reserve(p, (size_t)list->length);
            if (list->length) memcpy(p->words + p->length, list->values, (size_t)list->length * sizeof(long long));
            p->length += (size_t)list->length;
        } else {
            for (long long i = 0; i < list->length; ++i) rc_packet_put(p, d + 1, list->values[i]);
        }
        break;
    }
    case 'r': {
        const MinyarRecord *record = value;
        long long n;
        const char *field = rc_descriptor_count(d + 1, &n);
        if (record->length != n) rc_transfer_invalid();
        for (long long i = 0; i < n; ++i) field = rc_packet_put(p, field, record->values[i]);
        break;
    }
    default: rc_transfer_invalid();
    }
    return after;
}

/* Rebuilds one value in the current domain as an owned reference. */
static const char *rc_packet_get(const long long **cursor, const char *d, long long *out) {
    const long long *w = *cursor;
    if (*d == 'i') { *out = *w++; *cursor = w; return d + 1; }
    const char *after = rc_descriptor_skip(d);
    if (!*w++) { *out = 0; *cursor = w; return after; }
    switch (*d) {
    case 't': case 'b': {
        long long length = *w++;
        long long characters = *w++;
        MinyarText *text = *d == 't' ? new_text_storage(length, characters) : minyar_bytes_new(length);
        if (length) memcpy((unsigned char *)text->bytes, w, (size_t)length);
        ((unsigned char *)text->bytes)[length] = 0;
        w += ((size_t)length + 7) / 8;
        *out = (long long)(uintptr_t)text;
        break;
    }
    case 'h': {
        void *control = (void *)(uintptr_t)*w++;
        *out = (long long)(uintptr_t)rc_thread_wrap(control);
        break;
    }
    case 'l': {
        long long length = *w++;
        MinyarList *list = minyar_list_new();
        if (rc_descriptor_reference(d + 1)) minyar_list_references(list);
        if (d[1] == 'i') {
            minyar_list_append_scalars(list, w, length);
            w += length;
        } else {
            for (long long i = 0; i < length; ++i) {
                long long item;
                *cursor = w;
                rc_packet_get(cursor, d + 1, &item);
                w = *cursor;
                minyar_list_add_take(list, item);
            }
        }
        *out = (long long)(uintptr_t)list;
        break;
    }
    case 'r': {
        long long n;
        const char *field = rc_descriptor_count(d + 1, &n);
        int references = 0;
        const char *scan = field;
        for (long long i = 0; i < n; ++i) { references |= rc_descriptor_reference(scan); scan = rc_descriptor_skip(scan); }
        MinyarRecord *record = references ? minyar_record_new(n) : minyar_record_new_scalar(n);
        for (long long i = 0; i < n; ++i) {
            long long value;
            int reference = rc_descriptor_reference(field);
            *cursor = w;
            field = rc_packet_get(cursor, field, &value);
            w = *cursor;
            if (reference && value) minyar_record_set_take(record, i, value);
            else minyar_record_set_scalar(record, i, value);
        }
        *out = (long long)(uintptr_t)record;
        break;
    }
    default: rc_transfer_invalid();
    }
    *cursor = w;
    return after;
}

/* Walks an unconsumed value only to return its handle shares. */
static const char *rc_packet_drop(const long long **cursor, const char *d) {
    const long long *w = *cursor;
    if (*d == 'i') { *cursor = w + 1; return d + 1; }
    const char *after = rc_descriptor_skip(d);
    if (!*w++) { *cursor = w; return after; }
    switch (*d) {
    case 't': case 'b': { long long length = *w; w += 2 + ((size_t)length + 7) / 8; break; }
    case 'h': rc_thread_control_release((void *)(uintptr_t)*w++); break;
    case 'l': {
        long long length = *w++;
        if (d[1] == 'i') w += length;
        else for (long long i = 0; i < length; ++i) { *cursor = w; rc_packet_drop(cursor, d + 1); w = *cursor; }
        break;
    }
    case 'r': {
        long long n;
        const char *field = rc_descriptor_count(d + 1, &n);
        for (long long i = 0; i < n; ++i) { *cursor = w; field = rc_packet_drop(cursor, field); w = *cursor; }
        break;
    }
    default: rc_transfer_invalid();
    }
    *cursor = w;
    return after;
}

static RcPacket *rc_packet_new(const char *descriptor) {
    RcPacket *p = rc_thread_native_allocate(sizeof(*p));
    memset(p, 0, sizeof(*p));
    p->descriptor = descriptor;
    return p;
}

static void rc_packet_free(RcPacket *p, int consumed) {
    if (!p) return;
    if (!consumed && !p->cursor) {
        const long long *w = p->words;
        rc_packet_drop(&w, p->descriptor);
    } else if (!consumed && p->cursor) {
        /* A partly built tuple: drop only the fields already copied. */
        long long n;
        const char *field = rc_descriptor_count(p->descriptor + 1, &n);
        const long long *w = p->words;
        while (field != p->cursor) field = rc_packet_drop(&w, field);
    }
    free(p->words);
    rc_thread_native_free(p, sizeof(*p));
}

static void rc_packet_require(const RcPacket *p, const char *descriptor) {
    if (p->descriptor != descriptor && strcmp(p->descriptor, descriptor) != 0)
        minyar_stop("a value of another type was sent on this channel.");
}

/* Tuples for thread entries: begin with an `rN.` descriptor, then put each field in order. */
void *minyar_transfer_begin(const char *descriptor) {
    if (descriptor[0] != 'r') rc_transfer_invalid();
    RcPacket *p = rc_packet_new(descriptor);
    p->cursor = rc_descriptor_count(descriptor + 1, &p->fields_left);
    return p;
}

void minyar_transfer_put(RcPacket *p, long long slot) {
    if (!p->cursor || p->fields_left <= 0) rc_transfer_invalid();
    p->cursor = rc_packet_put(p, p->cursor, slot);
    if (--p->fields_left == 0) p->cursor = NULL;
}

/* ---------------------------------------------------------------- typed queues */

typedef struct {
    RcThreadMutex mutex;
    RcThreadCondition wake;
    unsigned signaled;
} RcSelectWaiter;
/* One registration per selected queue, owned by the selecting thread's stack call. */
typedef struct RcSelectLink {
    struct RcSelectLink *next;
    RcSelectWaiter *waiter;
} RcSelectLink;

typedef struct {
    RcThreadControl owner;
    RcThreadMutex mutex;
    RcThreadCondition changed;
    RcPacket *head, *tail;
    size_t count, capacity; /* capacity 0: unbounded */
    unsigned closed;
    size_t waiting;
    RcSelectLink *selectors;
    int wake_read, wake_write;
    unsigned wake_signaled;
} RcValueQueue;

static void rc_value_queue_destroy(void *pointer) {
    RcValueQueue *q = pointer;
    while (q->head) {
        RcPacket *next = q->head->next;
        rc_packet_free(q->head, 0);
        q->head = next;
    }
#ifndef _WIN32
    if (q->wake_read >= 0) close(q->wake_read);
    if (q->wake_write >= 0) close(q->wake_write);
#endif
    rc_thread_condition_destroy(&q->changed);
    rc_thread_mutex_destroy(&q->mutex);
    rc_thread_native_free(q, sizeof(*q));
}

void *minyar_queue_new(long long capacity) {
    if (capacity < 0) minyar_stop("a channel capacity cannot be negative.");
    RcValueQueue *q = rc_thread_native_allocate(sizeof(*q));
    memset(q, 0, sizeof(*q));
    q->capacity = (size_t)capacity;
    q->wake_read = q->wake_write = -1;
    if (rc_thread_mutex_init(&q->mutex)) minyar_stop("a channel could not be initialized.");
    if (rc_thread_condition_init(&q->changed)) minyar_stop("a channel could not be initialized.");
    rc_thread_control_init(&q->owner, 1, rc_value_queue_destroy);
    return rc_thread_wrap(q);
}

/* Under q->mutex: keep the wake socket readable exactly while a receive would not wait. */
static void rc_queue_publish(RcValueQueue *q) {
    unsigned ready = q->count > 0 || q->closed;
#ifndef _WIN32
    if (q->wake_write >= 0 && ready != q->wake_signaled) {
        char byte = 1;
        ssize_t n;
        if (ready) { do { n = write(q->wake_write, &byte, 1); } while (n < 0 && errno == EINTR); }
        else { do { n = read(q->wake_read, &byte, 1); } while (n < 0 && errno == EINTR); }
        q->wake_signaled = ready;
    }
#endif
    if (ready) {
        for (RcSelectLink *link = q->selectors; link; link = link->next) {
            RcSelectWaiter *w = link->waiter;
            rc_thread_mutex_lock(&w->mutex);
            w->signaled = 1;
            rc_thread_condition_wake(&w->wake);
            rc_thread_mutex_unlock(&w->mutex);
        }
    }
}

/* Monotonic deadlines in nanoseconds; a negative timeout never expires. */
static long long rc_queue_now(void) {
#ifdef _WIN32
    return (long long)GetTickCount64() * 1000000LL;
#else
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (long long)now.tv_sec * 1000000000LL + now.tv_nsec;
#endif
}
static long long rc_queue_deadline(long long milliseconds) {
    if (milliseconds < 0) return -1;
    if (milliseconds > LLONG_MAX / 2000000LL) return -1;
    return rc_queue_now() + milliseconds * 1000000LL;
}
/* Waits until signaled or the deadline passes; returns 0 once the deadline passed. */
static int rc_condition_wait_until(RcThreadCondition *c, RcThreadMutex *m, long long deadline) {
    if (deadline < 0) { rc_thread_condition_wait(c, m); return 1; }
    long long left = deadline - rc_queue_now();
    if (left <= 0) return 0;
#ifdef _WIN32
    SleepConditionVariableSRW(c, m, (DWORD)(left / 1000000 + 1), 0);
#else
    /* Relative waits avoid wall-clock jumps; spurious early returns re-check the deadline. */
    struct timespec now;
    clock_gettime(CLOCK_REALTIME, &now);
    long long total = (long long)now.tv_nsec + left;
    struct timespec until = { now.tv_sec + (time_t)(total / 1000000000LL), (long)(total % 1000000000LL) };
    int status = pthread_cond_timedwait(c, m, &until);
    if (status && status != ETIMEDOUT) minyar_stop("a thread condition wait failed.");
#endif
    return rc_queue_now() < deadline;
}

/* 1 sent, 0 full (only without waiting), 2 closed. */
static long long rc_queue_send(const RcThreadLeaf *leaf, long long slot, const char *descriptor, int blocking) {
    RcValueQueue *q = leaf->control;
    RcPacket *p = rc_packet_new(descriptor);
    rc_packet_put(p, descriptor, slot);
    rc_thread_control_retain(q);
    rc_thread_domain_drain(); /* Never run a collector under the queue lock. */
    rc_thread_mutex_lock(&q->mutex);
    while (!q->closed && q->capacity && q->count >= q->capacity && blocking) {
        q->waiting++;
        rc_thread_condition_wait(&q->changed, &q->mutex);
        q->waiting--;
    }
    long long status = q->closed ? 2 : (q->capacity && q->count >= q->capacity) ? 0 : 1;
    if (status == 1) {
        if (q->tail) q->tail->next = p; else q->head = p;
        q->tail = p;
        q->count++;
        rc_thread_condition_wake(&q->changed);
        rc_queue_publish(q);
    }
    rc_thread_mutex_unlock(&q->mutex);
    if (status != 1) rc_packet_free(p, 0);
    rc_thread_control_release(q);
    return status;
}
_Bool minyar_queue_send(const RcThreadLeaf *q, long long slot, const char *descriptor) {
    return rc_queue_send(q, slot, descriptor, 1) == 1;
}
long long minyar_queue_try_send(const RcThreadLeaf *q, long long slot, const char *descriptor) {
    return rc_queue_send(q, slot, descriptor, 0);
}

/* 1 received (appended to `into`), 0 nothing before the deadline, 2 closed and empty. */
static long long rc_queue_receive(const RcThreadLeaf *leaf, MinyarList *into, const char *descriptor, long long deadline) {
    RcValueQueue *q = leaf->control;
    rc_thread_control_retain(q);
    rc_thread_domain_drain();
    rc_thread_mutex_lock(&q->mutex);
    int waiting = 1;
    while (!q->count && !q->closed && waiting) {
        if (deadline == -2) break;
        q->waiting++;
        waiting = rc_condition_wait_until(&q->changed, &q->mutex, deadline);
        q->waiting--;
    }
    RcPacket *p = NULL;
    long long status = q->count ? 1 : q->closed ? 2 : 0;
    if (status == 1) {
        p = q->head;
        q->head = p->next;
        if (!q->head) q->tail = NULL;
        q->count--;
        rc_thread_condition_wake(&q->changed);
        rc_queue_publish(q);
    }
    rc_thread_mutex_unlock(&q->mutex);
    if (p) {
        rc_packet_require(p, descriptor);
        const long long *w = p->words;
        long long value;
        rc_packet_get(&w, descriptor, &value);
        if (rc_descriptor_reference(descriptor)) {
            if (!into->length) minyar_list_references(into);
            minyar_list_add_take(into, value);
        } else {
            minyar_list_add(into, value);
        }
        rc_packet_free(p, 1);
    }
    rc_thread_control_release(q);
    return status;
}
_Bool minyar_queue_receive(const RcThreadLeaf *q, MinyarList *into, const char *descriptor) {
    return rc_queue_receive(q, into, descriptor, -1) == 1;
}
long long minyar_queue_try_receive(const RcThreadLeaf *q, MinyarList *into, const char *descriptor) {
    return rc_queue_receive(q, into, descriptor, -2);
}
long long minyar_queue_receive_for(const RcThreadLeaf *q, MinyarList *into, const char *descriptor, long long milliseconds) {
    return rc_queue_receive(q, into, descriptor, rc_queue_deadline(milliseconds));
}

void minyar_queue_close(const RcThreadLeaf *leaf) {
    RcValueQueue *q = leaf->control;
    rc_thread_mutex_lock(&q->mutex);
    q->closed = 1;
    rc_thread_condition_wake(&q->changed);
    rc_queue_publish(q);
    rc_thread_mutex_unlock(&q->mutex);
}

long long minyar_queue_length(const RcThreadLeaf *leaf) {
    RcValueQueue *q = leaf->control;
    rc_thread_mutex_lock(&q->mutex);
    long long count = (long long)q->count;
    rc_thread_mutex_unlock(&q->mutex);
    return count;
}

_Bool minyar_queue_closed(const RcThreadLeaf *leaf) {
    RcValueQueue *q = leaf->control;
    rc_thread_mutex_lock(&q->mutex);
    _Bool closed = q->closed != 0;
    rc_thread_mutex_unlock(&q->mutex);
    return closed;
}

/* A socket that is readable while a receive would not wait (a message or close),
 * for watching a queue in an event loop beside sockets and timers. */
long long minyar_queue_wake_socket(const RcThreadLeaf *leaf) {
#ifdef _WIN32
    (void)leaf;
    return -1;
#else
    RcValueQueue *q = leaf->control;
    rc_thread_mutex_lock(&q->mutex);
    if (q->wake_read < 0) {
        int pair[2];
        if (socketpair(AF_UNIX, SOCK_STREAM, 0, pair) != 0) {
            rc_thread_mutex_unlock(&q->mutex);
            return -1;
        }
        for (int i = 0; i < 2; ++i) {
            fcntl(pair[i], F_SETFD, FD_CLOEXEC);
            fcntl(pair[i], F_SETFL, fcntl(pair[i], F_GETFL) | O_NONBLOCK);
        }
        q->wake_read = pair[0];
        q->wake_write = pair[1];
        q->wake_signaled = 0;
        rc_queue_publish(q);
    }
    long long result = q->wake_read;
    rc_thread_mutex_unlock(&q->mutex);
    return result;
#endif
}

static int rc_queue_ready_locked(RcValueQueue *q) { return q->count > 0 || q->closed; }
static RcValueQueue *rc_selected_queue(const MinyarList *queues, long long i) {
    return ((RcThreadLeaf *)(uintptr_t)queues->values[i])->control;
}

/* The position of a queue whose receive would not wait (a message or close), or
 * -1 once `milliseconds` pass (negative waits forever, 0 only polls). With
 * several receivers another thread may take the message first: callers use a
 * non-waiting receive and select again. */
long long minyar_queue_select(const MinyarList *queues, long long milliseconds) {
    long long count = queues->length;
    long long deadline = rc_queue_deadline(milliseconds);
    rc_thread_domain_drain();
    for (long long i = 0; i < count; ++i) rc_thread_control_retain(rc_selected_queue(queues, i));
    RcSelectWaiter waiter;
    memset(&waiter, 0, sizeof(waiter));
    if (rc_thread_mutex_init(&waiter.mutex) || rc_thread_condition_init(&waiter.wake))
        minyar_stop("a channel selection could not be initialized.");
    RcSelectLink *links = rc_thread_native_allocate((size_t)(count ? count : 1) * sizeof(*links));
    long long found = -1;
    for (;;) {
        rc_thread_mutex_lock(&waiter.mutex);
        waiter.signaled = 0;
        rc_thread_mutex_unlock(&waiter.mutex);
        long long registered = 0;
        for (long long i = 0; i < count && found < 0; ++i) {
            RcValueQueue *q = rc_selected_queue(queues, i);
            rc_thread_mutex_lock(&q->mutex);
            if (rc_queue_ready_locked(q)) found = i;
            else {
                links[i].waiter = &waiter;
                links[i].next = q->selectors;
                q->selectors = &links[i];
                registered = i + 1;
            }
            rc_thread_mutex_unlock(&q->mutex);
        }
        int alive = found < 0 && deadline != -1 ? rc_queue_now() < deadline : 1;
        if (found < 0 && alive && milliseconds != 0) {
            rc_thread_mutex_lock(&waiter.mutex);
            while (!waiter.signaled && alive) alive = rc_condition_wait_until(&waiter.wake, &waiter.mutex, deadline);
            rc_thread_mutex_unlock(&waiter.mutex);
        }
        for (long long i = 0; i < registered; ++i) {
            RcValueQueue *q = rc_selected_queue(queues, i);
            rc_thread_mutex_lock(&q->mutex);
            RcSelectLink **link = &q->selectors;
            while (*link && *link != &links[i]) link = &(*link)->next;
            if (*link) *link = links[i].next;
            rc_thread_mutex_unlock(&q->mutex);
        }
        if (found >= 0 || milliseconds == 0 || (!alive && deadline != -1)) {
            if (found < 0 && milliseconds != 0) {
                /* One last look after the deadline, without registering. */
                for (long long i = 0; i < count && found < 0; ++i) {
                    RcValueQueue *q = rc_selected_queue(queues, i);
                    rc_thread_mutex_lock(&q->mutex);
                    if (rc_queue_ready_locked(q)) found = i;
                    rc_thread_mutex_unlock(&q->mutex);
                }
            }
            break;
        }
    }
    rc_thread_native_free(links, (size_t)(count ? count : 1) * sizeof(*links));
    rc_thread_condition_destroy(&waiter.wake);
    rc_thread_mutex_destroy(&waiter.mutex);
    for (long long i = 0; i < count; ++i) rc_thread_control_release(rc_selected_queue(queues, i));
    return found;
}

#endif
