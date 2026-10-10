/* Single-owner readiness reactor. Included by net.c after its socket helpers.
 * Local RC/closures never cross threads. Owned LE result envelopes replace
 * error side channels. Readiness is a hint: operations may still would-block.
 * Timers use an indexed heap: cancellation cannot accumulate tombstones. */
#ifndef MINYAR_NET_LOOP_H
#define MINYAR_NET_LOOP_H
#include <time.h>
#ifdef __linux__
#include <sys/epoll.h>
#elif defined(__APPLE__) || defined(__FreeBSD__) || defined(__OpenBSD__) || defined(__NetBSD__)
#include <sys/event.h>
#else
#ifndef _WIN32
#error The hosted network loop requires epoll, kqueue or Windows WSAPoll.
#endif
#endif

enum {
    NET_LOOP_READ = 1,
    NET_LOOP_WRITE = 2,
    NET_LOOP_CLOSED = 4,
    NET_LOOP_ERROR = 8,
    NET_LOOP_TIMER = 16,
    NET_LOOP_MAX_BATCH = 65536
};
typedef struct {
    socket_t socket;
    uint64_t deadline, period;
    long long token;
    uint32_t generation, next_free;
    size_t heap_index;
    unsigned interest, active, timer;
} NetLoopEntry;
typedef struct {
    uint64_t socket;
    uint32_t slot;
    unsigned state;
} NetLoopHash;
typedef struct {
    NetLoopEntry *entries;
    size_t entry_count, entry_capacity;
    uint32_t free_entry;
    uint32_t *timers;
    size_t timer_count, timer_capacity;
    NetLoopHash *hash;
    size_t hash_capacity, hash_count, hash_deleted;
    unsigned timer_turn;
#ifdef _WIN32
    WSAPOLLFD *poll_events;
    uint32_t *poll_slots;
    size_t poll_capacity, windows_cursor;
#elif defined(__linux__)
    int selector;
    struct epoll_event *poll_events;
    size_t poll_capacity;
#else
    int selector;
    struct kevent *poll_events;
    size_t poll_capacity;
#endif
} NetLoop;
typedef struct {
    NetLoop *loop;
    uint32_t generation;
} NetLoopSlot;
static NetLoopSlot *net_loop_slots;
static size_t net_loop_slot_count, net_loop_slot_capacity;
static uint32_t net_loop_registration_generation;

static uint64_t net_loop_now(void) {
#ifdef _WIN32
    return GetTickCount64();
#else
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now))
        minyar_native_stop("the monotonic clock is unavailable.");
    return (uint64_t)now.tv_sec * 1000 + (uint64_t)now.tv_nsec / 1000000;
#endif
}
static uint64_t net_loop_handle(uint32_t slot, uint32_t generation) {
    return ((uint64_t)generation << 32) | ((uint64_t)slot + 1);
}
static uint32_t net_loop_next_generation(uint32_t previous) {
    /* Never wrap: retiring an exhausted slot avoids resurrecting an old ID. */
    return previous < INT32_MAX ? previous + 1 : 0;
}
static NetLoop *net_loop_find(long long handle) {
    uint64_t value = (uint64_t)handle;
    uint32_t low = (uint32_t)value;
    if (handle <= 0 || !low || low > net_loop_slot_count)
        return NULL;
    NetLoopSlot *slot = &net_loop_slots[low - 1];
    return slot->generation == (uint32_t)(value >> 32) ? slot->loop : NULL;
}
static NetLoopEntry *net_loop_entry(NetLoop *loop, long long handle, uint32_t *index) {
    uint64_t value = (uint64_t)handle;
    uint32_t low = (uint32_t)value;
    if (handle <= 0 || !low || low > loop->entry_count)
        return NULL;
    NetLoopEntry *entry = &loop->entries[low - 1];
    if (!entry->active || entry->generation != (uint32_t)(value >> 32))
        return NULL;
    *index = low - 1;
    return entry;
}
static void net_loop_put64(unsigned char *p, uint64_t value) {
    put32(p, (uint32_t)value);
    put32(p + 4, (uint32_t)(value >> 32));
}
static MinyarBytes *net_loop_result(int code, long long value) {
    MinyarBytes *result = minyar_bytes_new(16);
    result_status(result, code ? NET_FAILURE : NET_OK, code);
    net_loop_put64((unsigned char *)result->bytes + 8, (uint64_t)value);
    return result;
}
static int net_loop_memory_error(void) {
#ifdef _WIN32
    return WSAENOBUFS;
#else
    return ENOMEM;
#endif
}
static int net_loop_bad_handle(void) {
#ifdef _WIN32
    return WSAEBADF;
#else
    return EBADF;
#endif
}
static uint64_t net_loop_hash_key(socket_t socket) {
    uint64_t value = (uint64_t)socket;
    value ^= value >> 33;
    value *= UINT64_C(0xff51afd7ed558ccd);
    value ^= value >> 33;
    return value;
}
static bool net_loop_rehash(NetLoop *loop, size_t capacity) {
    NetLoopHash *table = calloc(capacity, sizeof(*table));
    if (!table)
        return false;
    for (size_t i = 0; i < loop->hash_capacity; i++) {
        NetLoopHash item = loop->hash[i];
        if (item.state != 1)
            continue;
        size_t slot = (size_t)net_loop_hash_key((socket_t)item.socket) & (capacity - 1);
        while (table[slot].state)
            slot = (slot + 1) & (capacity - 1);
        table[slot] = item;
    }
    free(loop->hash);
    loop->hash = table;
    loop->hash_capacity = capacity;
    loop->hash_deleted = 0;
    return true;
}
static NetLoopHash *net_loop_hash_find(NetLoop *loop, socket_t socket) {
    if (!loop->hash_capacity)
        return NULL;
    size_t at = (size_t)net_loop_hash_key(socket) & (loop->hash_capacity - 1);
    for (size_t i = 0; i < loop->hash_capacity; i++) {
        NetLoopHash *item = &loop->hash[at];
        if (!item->state)
            return NULL;
        if (item->state == 1 && item->socket == (uint64_t)socket)
            return item;
        at = (at + 1) & (loop->hash_capacity - 1);
    }
    return NULL;
}
static bool net_loop_hash_reserve(NetLoop *loop) {
    if (!loop->hash_capacity)
        return net_loop_rehash(loop, 16);
    if ((loop->hash_count + loop->hash_deleted + 1) * 2 >= loop->hash_capacity) {
        size_t capacity = loop->hash_count * 3 >= loop->hash_capacity ? loop->hash_capacity * 2
                                                                      : loop->hash_capacity;
        if (capacity < loop->hash_capacity)
            return false;
        return net_loop_rehash(loop, capacity);
    }
    return true;
}
static void net_loop_hash_insert(NetLoop *loop, socket_t socket, uint32_t slot) {
    size_t at = (size_t)net_loop_hash_key(socket) & (loop->hash_capacity - 1);
    while (loop->hash[at].state == 1)
        at = (at + 1) & (loop->hash_capacity - 1);
    if (loop->hash[at].state == 2)
        loop->hash_deleted--;
    loop->hash[at] = (NetLoopHash){(uint64_t)socket, slot, 1};
    loop->hash_count++;
}
static bool net_loop_allocate_entry(NetLoop *loop, uint32_t *index) {
    if (net_loop_registration_generation == INT32_MAX)
        return false;
    if (loop->free_entry) {
        *index = loop->free_entry - 1;
        NetLoopEntry *entry = &loop->entries[*index];
        loop->free_entry = entry->next_free;
        uint32_t generation = ++net_loop_registration_generation;
        memset(entry, 0, sizeof(*entry));
        entry->generation = generation;
        entry->active = 1;
        return true;
    }
    if (loop->entry_count == UINT32_MAX)
        return false;
    if (loop->entry_count == loop->entry_capacity) {
        size_t capacity = loop->entry_capacity ? loop->entry_capacity * 2 : 16;
        if (capacity > UINT32_MAX || capacity > SIZE_MAX / sizeof(NetLoopEntry))
            return false;
        NetLoopEntry *entries = realloc(loop->entries, capacity * sizeof(*entries));
        if (!entries)
            return false;
        loop->entries = entries;
        loop->entry_capacity = capacity;
    }
    *index = (uint32_t)loop->entry_count++;
    memset(&loop->entries[*index], 0, sizeof(loop->entries[*index]));
    loop->entries[*index].generation = ++net_loop_registration_generation;
    loop->entries[*index].active = 1;
    return true;
}
static void net_loop_retire_entry(NetLoop *loop, uint32_t index) {
    NetLoopEntry *entry = &loop->entries[index];
    entry->active = 0;
    if (entry->generation < INT32_MAX) {
        entry->next_free = loop->free_entry;
        loop->free_entry = index + 1;
    }
}
static bool net_loop_timer_less(NetLoop *loop, uint32_t left, uint32_t right) {
    NetLoopEntry *a = &loop->entries[left], *b = &loop->entries[right];
    return a->deadline < b->deadline ||
           (a->deadline == b->deadline && a->generation < b->generation);
}
static void net_loop_heap_swap(NetLoop *loop, size_t a, size_t b) {
    uint32_t saved = loop->timers[a];
    loop->timers[a] = loop->timers[b];
    loop->timers[b] = saved;
    loop->entries[loop->timers[a]].heap_index = a;
    loop->entries[loop->timers[b]].heap_index = b;
}
static void net_loop_heap_up(NetLoop *loop, size_t at) {
    while (at) {
        size_t parent = (at - 1) / 2;
        if (!net_loop_timer_less(loop, loop->timers[at], loop->timers[parent]))
            break;
        net_loop_heap_swap(loop, at, parent);
        at = parent;
    }
}
static void net_loop_heap_down(NetLoop *loop, size_t at) {
    while (at < loop->timer_count / 2 ||
           (loop->timer_count > 1 && at == (loop->timer_count - 2) / 2)) {
        size_t child = at * 2 + 1;
        if (child + 1 < loop->timer_count &&
            net_loop_timer_less(loop, loop->timers[child + 1], loop->timers[child]))
            child++;
        if (!net_loop_timer_less(loop, loop->timers[child], loop->timers[at]))
            break;
        net_loop_heap_swap(loop, at, child);
        at = child;
    }
}
static void net_loop_heap_remove(NetLoop *loop, size_t at) {
    loop->timer_count--;
    if (at == loop->timer_count)
        return;
    loop->timers[at] = loop->timers[loop->timer_count];
    loop->entries[loop->timers[at]].heap_index = at;
    if (at && net_loop_timer_less(loop, loop->timers[at], loop->timers[(at - 1) / 2]))
        net_loop_heap_up(loop, at);
    else
        net_loop_heap_down(loop, at);
}
static int net_loop_selector_update(NetLoop *loop, uint32_t index, unsigned interest, bool add) {
    NetLoopEntry *entry = &loop->entries[index];
#ifdef _WIN32
    (void)loop;
    (void)interest;
    (void)add;
    int type;
    int length = sizeof(type);
    return getsockopt(entry->socket, SOL_SOCKET, SO_TYPE, (char *)&type, &length) ? socket_error()
                                                                                  : 0;
#elif defined(__linux__)
    struct epoll_event event = {0};
    event.events = EPOLLRDHUP;
    if (interest & NET_LOOP_READ)
        event.events |= EPOLLIN;
    if (interest & NET_LOOP_WRITE)
        event.events |= EPOLLOUT;
    event.data.u64 = net_loop_handle(index, entry->generation);
    return epoll_ctl(loop->selector, add ? EPOLL_CTL_ADD : EPOLL_CTL_MOD, entry->socket, &event)
               ? errno
               : 0;
#else
    (void)add;
    struct kevent changes[2];
    void *identity = (void *)(uintptr_t)net_loop_handle(index, entry->generation);
    EV_SET(&changes[0], (uintptr_t)entry->socket, EVFILT_READ,
           EV_ADD | (interest & NET_LOOP_READ ? EV_ENABLE : EV_DISABLE), 0, 0, identity);
    EV_SET(&changes[1], (uintptr_t)entry->socket, EVFILT_WRITE,
           EV_ADD | (interest & NET_LOOP_WRITE ? EV_ENABLE : EV_DISABLE), 0, 0, identity);
    return kevent(loop->selector, changes, 2, NULL, 0, NULL) < 0 ? errno : 0;
#endif
}
static int net_loop_selector_remove(NetLoop *loop, NetLoopEntry *entry) {
#ifdef _WIN32
    (void)loop;
    (void)entry;
    return 0;
#elif defined(__linux__)
    if (!epoll_ctl(loop->selector, EPOLL_CTL_DEL, entry->socket, NULL))
        return 0;
    return errno == ENOENT || errno == EBADF ? 0 : errno;
#else
    struct kevent change;
    const short filters[] = {EVFILT_READ, EVFILT_WRITE};
    for (unsigned i = 0; i < 2; i++) {
        EV_SET(&change, (uintptr_t)entry->socket, filters[i], EV_DELETE, 0, 0, NULL);
        if (kevent(loop->selector, &change, 1, NULL, 0, NULL) < 0 && errno != ENOENT &&
            errno != EBADF)
            return errno;
    }
    return 0;
#endif
}
static int net_loop_nonblocking(socket_t socket) {
#ifdef _WIN32
    u_long enabled = 1;
    return ioctlsocket(socket, FIONBIO, &enabled) ? socket_error() : 0;
#else
    int flags = fcntl(socket, F_GETFL);
    if (flags < 0)
        return errno;
    return fcntl(socket, F_SETFL, flags | O_NONBLOCK) ? errno : 0;
#endif
}
MinyarBytes *minyar_net_loopCreate(void) {
    if (!initialize())
        return net_loop_result(BAD_ARGUMENT, -1);
    NetLoop *loop = calloc(1, sizeof(*loop));
    if (!loop)
        return net_loop_result(net_loop_memory_error(), -1);
#ifndef _WIN32
#ifdef __linux__
    loop->selector = epoll_create1(EPOLL_CLOEXEC);
#else
    loop->selector = kqueue();
    if (loop->selector >= 0 && fcntl(loop->selector, F_SETFD, FD_CLOEXEC) < 0) {
        int code = errno;
        close(loop->selector);
        free(loop);
        return net_loop_result(code, -1);
    }
#endif
    if (loop->selector < 0) {
        int code = errno;
        free(loop);
        return net_loop_result(code, -1);
    }
#endif
    size_t index = 0;
    while (index < net_loop_slot_count &&
           (net_loop_slots[index].loop || net_loop_slots[index].generation == INT32_MAX))
        index++;
    if (index == net_loop_slot_count) {
        if (net_loop_slot_count == net_loop_slot_capacity) {
            size_t capacity = net_loop_slot_capacity ? net_loop_slot_capacity * 2 : 8;
            NetLoopSlot *slots = capacity <= UINT32_MAX && capacity <= SIZE_MAX / sizeof(*slots)
                                     ? realloc(net_loop_slots, capacity * sizeof(*slots))
                                     : NULL;
            if (!slots) {
#ifndef _WIN32
                close(loop->selector);
#endif
                free(loop);
                return net_loop_result(net_loop_memory_error(), -1);
            }
            memset(slots + net_loop_slot_capacity, 0,
                   (capacity - net_loop_slot_capacity) * sizeof(*slots));
            net_loop_slots = slots;
            net_loop_slot_capacity = capacity;
        }
        net_loop_slot_count++;
    }
    NetLoopSlot *slot = &net_loop_slots[index];
    slot->generation = net_loop_next_generation(slot->generation);
    slot->loop = loop;
    return net_loop_result(0, (long long)net_loop_handle((uint32_t)index, slot->generation));
}
MinyarBytes *minyar_net_loopWatch(long long handle, long long connection, long long interest,
                                  long long token) {
    NetLoop *loop = net_loop_find(handle);
    if (!loop)
        return net_loop_result(net_loop_bad_handle(), -1);
    if (connection < 0 || interest < 0 || interest > 3)
        return net_loop_result(BAD_ARGUMENT, -1);
    socket_t socket = (socket_t)connection;
#ifndef _WIN32
    if (connection > INT_MAX)
        return net_loop_result(BAD_ARGUMENT, -1);
#endif
    if (net_loop_hash_find(loop, socket))
        return net_loop_result(BAD_ARGUMENT, -1);
    int code = net_loop_nonblocking(socket);
    if (code)
        return net_loop_result(code, -1);
    if (!net_loop_hash_reserve(loop))
        return net_loop_result(net_loop_memory_error(), -1);
    uint32_t index;
    if (!net_loop_allocate_entry(loop, &index))
        return net_loop_result(net_loop_memory_error(), -1);
    NetLoopEntry *entry = &loop->entries[index];
    entry->socket = socket;
    entry->interest = (unsigned)interest;
    entry->token = token;
    code = net_loop_selector_update(loop, index, (unsigned)interest, true);
    if (code) {
        (void)net_loop_selector_remove(loop, entry);
        net_loop_retire_entry(loop, index);
        return net_loop_result(code, -1);
    }
    net_loop_hash_insert(loop, socket, index);
    return net_loop_result(0, (long long)net_loop_handle(index, entry->generation));
}
MinyarBytes *minyar_net_loopUpdate(long long handle, long long registration, long long interest,
                                   long long token) {
    NetLoop *loop = net_loop_find(handle);
    uint32_t index;
    NetLoopEntry *entry = loop ? net_loop_entry(loop, registration, &index) : NULL;
    if (!entry)
        return net_loop_result(net_loop_bad_handle(), 0);
    if (entry->timer || interest < 0 || interest > 3)
        return net_loop_result(BAD_ARGUMENT, 0);
    int code = net_loop_selector_update(loop, index, (unsigned)interest, false);
    if (code) {
        (void)net_loop_selector_update(loop, index, entry->interest, false);
        return net_loop_result(code, 0);
    }
    entry->interest = (unsigned)interest;
    entry->token = token;
    return net_loop_result(0, 1);
}
MinyarBytes *minyar_net_loopRemove(long long handle, long long registration) {
    NetLoop *loop = net_loop_find(handle);
    uint32_t index;
    NetLoopEntry *entry = loop ? net_loop_entry(loop, registration, &index) : NULL;
    if (!entry)
        return net_loop_result(net_loop_bad_handle(), 0);
    if (entry->timer)
        net_loop_heap_remove(loop, entry->heap_index);
    else {
        int code = net_loop_selector_remove(loop, entry);
        if (code)
            return net_loop_result(code, 0);
        NetLoopHash *item = net_loop_hash_find(loop, entry->socket);
        if (item) {
            item->state = 2;
            loop->hash_count--;
            loop->hash_deleted++;
        }
    }
    net_loop_retire_entry(loop, index);
    return net_loop_result(0, 1);
}
MinyarBytes *minyar_net_loopTimer(long long handle, long long delay, long long period,
                                  long long token) {
    NetLoop *loop = net_loop_find(handle);
    if (!loop)
        return net_loop_result(net_loop_bad_handle(), -1);
    if (delay < 0 || period < 0)
        return net_loop_result(BAD_ARGUMENT, -1);
    uint64_t now = net_loop_now();
    if ((uint64_t)delay > UINT64_MAX - now)
        return net_loop_result(BAD_ARGUMENT, -1);
    if (loop->timer_count == loop->timer_capacity) {
        size_t capacity = loop->timer_capacity ? loop->timer_capacity * 2 : 16;
        uint32_t *timers = capacity <= UINT32_MAX && capacity <= SIZE_MAX / sizeof(*timers)
                               ? realloc(loop->timers, capacity * sizeof(*timers))
                               : NULL;
        if (!timers)
            return net_loop_result(net_loop_memory_error(), -1);
        loop->timers = timers;
        loop->timer_capacity = capacity;
    }
    uint32_t index;
    if (!net_loop_allocate_entry(loop, &index))
        return net_loop_result(net_loop_memory_error(), -1);
    NetLoopEntry *entry = &loop->entries[index];
    entry->timer = 1;
    entry->deadline = now + (uint64_t)delay;
    entry->period = (uint64_t)period;
    entry->token = token;
    entry->heap_index = loop->timer_count;
    loop->timers[loop->timer_count++] = index;
    net_loop_heap_up(loop, entry->heap_index);
    return net_loop_result(0, (long long)net_loop_handle(index, entry->generation));
}
static void net_loop_event(MinyarBytes *result, uint64_t identity, long long token, unsigned flags,
                           int code, unsigned kind) {
    unsigned char *bytes = minyar_bytes_extend(result, 32);
    net_loop_put64(bytes, identity);
    net_loop_put64(bytes + 8, (uint64_t)token);
    put32(bytes + 16, flags);
    put32(bytes + 20, (uint32_t)code);
    put32(bytes + 24, kind);
    put32(bytes + 28, 0);
}
static size_t net_loop_emit_timers(NetLoop *loop, MinyarBytes *result, size_t limit, uint64_t now) {
    size_t count = 0;
    while (count < limit && loop->timer_count) {
        uint32_t index = loop->timers[0];
        NetLoopEntry *entry = &loop->entries[index];
        if (entry->deadline > now)
            break;
        net_loop_event(result, net_loop_handle(index, entry->generation), entry->token,
                       NET_LOOP_TIMER, 0, 1);
        count++;
        if (entry->period) {
            /* Rearm from the current monotonic time, skipping missed periods.
             * At most one emission per repeating timer in a single batch. */
            entry->deadline = entry->period > UINT64_MAX - now ? UINT64_MAX : now + entry->period;
            net_loop_heap_down(loop, 0);
        } else {
            net_loop_heap_remove(loop, 0);
            net_loop_retire_entry(loop, index);
        }
    }
    return count;
}
static bool net_loop_poll_reserve(NetLoop *loop, size_t capacity) {
    if (capacity <= loop->poll_capacity)
        return true;
    if (capacity > SIZE_MAX / sizeof(*loop->poll_events))
        return false;
    void *events = realloc(loop->poll_events, capacity * sizeof(*loop->poll_events));
    if (!events)
        return false;
    loop->poll_events = events;
#ifdef _WIN32
    uint32_t *slots = realloc(loop->poll_slots, capacity * sizeof(*slots));
    if (!slots)
        return false;
    loop->poll_slots = slots;
#endif
    loop->poll_capacity = capacity;
    return true;
}
/* Count only validated registrations. Kernel-queued stale identities cannot
 * alias a reused slot because the generation is included in kernel user data. */
static int net_loop_poll(NetLoop *loop, MinyarBytes *result, size_t limit, int timeout) {
#ifdef _WIN32
    if (!net_loop_poll_reserve(loop, loop->hash_count ? loop->hash_count : 1))
        return net_loop_memory_error();
    size_t count = 0;
    for (size_t n = 0; n < loop->entry_count; n++) {
        size_t index = (loop->windows_cursor + n) % loop->entry_count;
        NetLoopEntry *entry = &loop->entries[index];
        if (!entry->active || entry->timer)
            continue;
        short interest = 0;
        if (entry->interest & NET_LOOP_READ)
            interest |= POLLRDNORM;
        if (entry->interest & NET_LOOP_WRITE)
            interest |= POLLWRNORM;
        loop->poll_events[count] = (WSAPOLLFD){entry->socket, interest, 0};
        loop->poll_slots[count++] = (uint32_t)index;
    }
    if (!count) {
        Sleep(timeout < 0 ? INFINITE : (DWORD)timeout);
        return 0;
    }
    int polled = WSAPoll(loop->poll_events, (ULONG)count, timeout);
    if (polled < 0)
        return socket_error();
    size_t emitted = 0;
    for (size_t i = 0; i < count && emitted < limit; i++) {
        short ready = loop->poll_events[i].revents;
        if (!ready)
            continue;
        uint32_t index = loop->poll_slots[i];
        NetLoopEntry *entry = &loop->entries[index];
        unsigned flags = 0;
        if (ready & (POLLRDNORM | POLLRDBAND | POLLIN))
            flags |= NET_LOOP_READ;
        if (ready & (POLLWRNORM | POLLOUT))
            flags |= NET_LOOP_WRITE;
        if (ready & POLLHUP)
            flags |= NET_LOOP_CLOSED | NET_LOOP_READ;
        if (ready & (POLLERR | POLLNVAL))
            flags |= NET_LOOP_ERROR;
        net_loop_event(result, net_loop_handle(index, entry->generation), entry->token, flags,
                       ready & POLLNVAL ? WSAEBADF : 0, 0);
        emitted++;
        loop->windows_cursor = (index + 1) % loop->entry_count;
    }
#elif defined(__linux__)
    if (!net_loop_poll_reserve(loop, limit))
        return net_loop_memory_error();
    int count = epoll_wait(loop->selector, loop->poll_events, (int)limit, timeout);
    if (count < 0)
        return errno;
    for (int i = 0; i < count; i++) {
        struct epoll_event *event = &loop->poll_events[i];
        uint32_t index;
        NetLoopEntry *entry = net_loop_entry(loop, (long long)event->data.u64, &index);
        if (!entry || entry->timer)
            continue;
        unsigned flags = 0;
        if (event->events & EPOLLIN)
            flags |= NET_LOOP_READ;
        if (event->events & EPOLLOUT)
            flags |= NET_LOOP_WRITE;
        if (event->events & (EPOLLHUP | EPOLLRDHUP))
            flags |= NET_LOOP_CLOSED | NET_LOOP_READ;
        if (event->events & EPOLLERR)
            flags |= NET_LOOP_ERROR;
        net_loop_event(result, event->data.u64, entry->token, flags, 0, 0);
    }
#else
    if (!net_loop_poll_reserve(loop, limit))
        return net_loop_memory_error();
    struct timespec delay = {timeout < 0 ? 0 : timeout / 1000,
                             timeout < 0 ? 0 : (timeout % 1000) * 1000000};
    int count =
        kevent(loop->selector, NULL, 0, loop->poll_events, (int)limit, timeout < 0 ? NULL : &delay);
    if (count < 0)
        return errno;
    for (int i = 0; i < count; i++) {
        struct kevent *event = &loop->poll_events[i];
        uint64_t identity = (uint64_t)(uintptr_t)event->udata;
        uint32_t index;
        NetLoopEntry *entry = net_loop_entry(loop, (long long)identity, &index);
        if (!entry || entry->timer)
            continue;
        unsigned flags = event->filter == EVFILT_READ ? NET_LOOP_READ : NET_LOOP_WRITE;
        if (event->flags & EV_EOF)
            flags |= NET_LOOP_CLOSED;
        if (event->flags & EV_ERROR)
            flags |= NET_LOOP_ERROR;
        net_loop_event(result, identity, entry->token, flags,
                       event->flags & EV_ERROR ? (int)event->data : 0, 0);
    }
#endif
    return 0;
}
MinyarBytes *minyar_net_loopWait(long long handle, long long milliseconds, long long maximum) {
    MinyarBytes *result = minyar_bytes_new(8);
    NetLoop *loop = net_loop_find(handle);
    if (!loop || milliseconds < -1 || milliseconds > INT_MAX || maximum <= 0 ||
        maximum > NET_LOOP_MAX_BATCH) {
        result_status(result, NET_FAILURE, !loop ? net_loop_bad_handle() : BAD_ARGUMENT);
        return result;
    }
    result_status(result, NET_OK, 0);
    uint64_t now = net_loop_now();
    uint64_t deadline = milliseconds < 0 ? UINT64_MAX : now + (uint64_t)milliseconds;
    size_t limit = (size_t)maximum;
    while (true) {
        now = net_loop_now();
        bool due = loop->timer_count && loop->entries[loop->timers[0]].deadline <= now;
        size_t timer_limit = due ? (limit == 1 ? loop->timer_turn : (limit + 1) / 2) : 0;
        int timeout = 0;
        if (!due) {
            uint64_t wake = deadline;
            if (loop->timer_count && loop->entries[loop->timers[0]].deadline < wake)
                wake = loop->entries[loop->timers[0]].deadline;
            timeout = wake == UINT64_MAX     ? -1
                      : wake <= now          ? 0
                      : wake - now > INT_MAX ? INT_MAX
                                             : (int)(wake - now);
        }
        /* Reserve part of a due batch for timers, but poll before consuming
         * them: a failed selector/allocation must not lose one-shot timers. */
        int code =
            limit > timer_limit ? net_loop_poll(loop, result, limit - timer_limit, timeout) : 0;
        if (code && !interrupted(code)) {
            result->byte_length = 8;
            result_status(result, NET_FAILURE, code);
            return result;
        }
        size_t emitted = (size_t)(result->byte_length - 8) / 32;
        if (emitted < limit)
            emitted += net_loop_emit_timers(loop, result, limit - emitted, net_loop_now());
        if (emitted) {
            loop->timer_turn ^= 1;
            return result;
        }
        if (net_loop_now() >= deadline)
            return result;
        /* Interrupted waits retain the absolute deadline. Readiness containing
         * only stale registrations also cannot extend the caller's timeout. */
    }
}
MinyarBytes *minyar_net_loopClose(long long handle) {
    NetLoop *loop = net_loop_find(handle);
    if (!loop)
        return net_loop_result(net_loop_bad_handle(), 0);
#ifndef _WIN32
    if (close(loop->selector))
        return net_loop_result(errno, 0);
#endif
    net_loop_slots[(uint32_t)(uint64_t)handle - 1].loop = NULL;
    free(loop->entries);
    free(loop->timers);
    free(loop->hash);
    free(loop->poll_events);
#ifdef _WIN32
    free(loop->poll_slots);
#endif
    free(loop);
    return net_loop_result(0, 1);
}
#endif
