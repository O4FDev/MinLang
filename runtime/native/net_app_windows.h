/* Optional UI wake observer. Threadpool callbacks hold stable native nodes and
 * only signal one aggregate event; managed envelopes stay on the owner thread.
 * No WSAPoll worker, periodic timer, or MAXIMUM_WAIT_OBJECTS-sized socket cap. */
#ifndef MINYAR_NET_APP_WINDOWS_H
#define MINYAR_NET_APP_WINDOWS_H
struct NetAppWindowsSocket {
    SOCKET socket;
    HANDLE event, wake;
    PTP_WAIT wait;
    long interests;
    uint32_t generation;
    volatile LONG signaled;
    bool polled, ready;
};
static void CALLBACK net_app_windows_ready(PTP_CALLBACK_INSTANCE instance, void *context,
                                           PTP_WAIT wait, TP_WAIT_RESULT status) {
    (void)instance;
    (void)wait;
    (void)status;
    NetAppWindowsSocket *node = context;
    InterlockedExchange(&node->signaled, 1);
    SetEvent(node->wake);
}
static long net_app_windows_interests(unsigned interest) {
    return FD_CLOSE | (interest & NET_LOOP_READ ? (FD_READ | FD_ACCEPT) : 0) |
           (interest & NET_LOOP_WRITE ? (FD_WRITE | FD_CONNECT) : 0);
}
static void net_app_windows_destroy(NetAppWindowsSocket *node) {
    SetThreadpoolWait(node->wait, NULL, NULL);
    WaitForThreadpoolWaitCallbacks(node->wait, TRUE);
    CloseThreadpoolWait(node->wait);
    /* A caller must remove before close; a closed socket cannot retain an event. */
    (void)WSAEventSelect(node->socket, NULL, 0);
    CloseHandle(node->event);
    free(node);
}
static void net_app_windows_remove(NetLoop *loop, size_t index) {
    if (index >= loop->app_socket_capacity || !loop->app_sockets[index])
        return;
    net_app_windows_destroy(loop->app_sockets[index]);
    loop->app_sockets[index] = NULL;
}
static int net_app_windows_update(NetLoop *loop, uint32_t index, unsigned interest) {
    if (!loop->app_event)
        return 0;
    if (index >= loop->app_socket_capacity) {
        size_t capacity = loop->entry_capacity;
        NetAppWindowsSocket **nodes = realloc(loop->app_sockets, capacity * sizeof(*nodes));
        if (!nodes)
            return WSAENOBUFS;
        memset(nodes + loop->app_socket_capacity, 0,
               (capacity - loop->app_socket_capacity) * sizeof(*nodes));
        loop->app_sockets = nodes;
        loop->app_socket_capacity = capacity;
    }
    NetAppWindowsSocket *node = loop->app_sockets[index];
    bool fresh = !node;
    if (fresh) {
        node = calloc(1, sizeof(*node));
        if (!node)
            return WSAENOBUFS;
        node->socket = loop->entries[index].socket;
        node->wake = loop->app_event;
        node->generation = loop->entries[index].generation;
        node->event = CreateEventW(NULL, TRUE, FALSE, NULL);
        node->wait = node->event ? CreateThreadpoolWait(net_app_windows_ready, node, NULL) : NULL;
        if (!node->wait) {
            if (node->event)
                CloseHandle(node->event);
            free(node);
            return WSAENOBUFS;
        }
    }
    long mask = net_app_windows_interests(interest);
    if (WSAEventSelect(node->socket, node->event, mask)) {
        int code = WSAGetLastError();
        if (fresh)
            net_app_windows_destroy(node);
        return code;
    }
    node->interests = mask;
    loop->app_sockets[index] = node;
    SetThreadpoolWait(node->wait, node->event, NULL);
    return 0;
}
void minyar_net_appLoopWindowsDetach(long long handle) {
    NetLoop *loop = net_loop_find(handle);
    if (!loop || !loop->app_event)
        return;
    /* Cancel and join every callback before closing the shared wake handle. */
    for (size_t i = 0; i < loop->app_socket_capacity; i++)
        net_app_windows_remove(loop, i);
    free(loop->app_sockets);
    loop->app_sockets = NULL;
    loop->app_socket_capacity = 0;
    CloseHandle(loop->app_event);
    loop->app_event = NULL;
}
bool minyar_net_appLoopWindowsValid(long long handle) {
    return net_loop_find(handle) != NULL;
}
void *minyar_net_appLoopWindowsAttach(long long handle, int *error) {
    NetLoop *loop = net_loop_find(handle);
    *error = 0;
    if (!loop) {
        *error = WSAEBADF;
        return NULL;
    }
    if (loop->app_event)
        return loop->app_event;
    loop->app_event = CreateEventW(NULL, TRUE, FALSE, NULL);
    if (!loop->app_event) {
        *error = WSAENOBUFS;
        return NULL;
    }
    for (size_t i = 0; i < loop->entry_count; i++)
        if (loop->entries[i].active && !loop->entries[i].timer) {
            *error = net_app_windows_update(loop, (uint32_t)i, loop->entries[i].interest);
            if (*error) {
                minyar_net_appLoopWindowsDetach(handle);
                return NULL;
            }
        }
    SetEvent(loop->app_event);
    return loop->app_event;
}
static uint32_t net_app_windows_word(const unsigned char *p) {
    return p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}
static void net_app_windows_polled(NetLoop *loop, const MinyarBytes *result) {
    if (!loop || !loop->app_event)
        return;
    ResetEvent(loop->app_event);
    if (loop->app_socket_snapshot)
        for (size_t i = 0; i < loop->app_poll_count; i++) {
            uint32_t index = loop->poll_slots[i];
            if (index < loop->app_socket_capacity && loop->app_sockets[index])
                loop->app_sockets[index]->ready = loop->poll_events[i].revents != 0;
        }
    /* Re-enable only emitted socket records. Unemitted ready nodes retain
     * their signalled event, so bounded batches cannot lose other sockets. */
    if (result->byte_length >= 8 && !net_app_windows_word(result->bytes))
        for (long long at = 8; at + 32 <= result->byte_length; at += 32) {
            uint32_t index = net_app_windows_word(result->bytes + at),
                     generation = net_app_windows_word(result->bytes + at + 4);
            if (!net_app_windows_word(result->bytes + at + 24) && index &&
                index <= loop->app_socket_capacity) {
                NetAppWindowsSocket *node = loop->app_sockets[index - 1];
                if (node && node->generation == generation)
                    node->polled = true;
            }
        }
    for (size_t i = 0; i < loop->app_socket_capacity; i++) {
        NetAppWindowsSocket *node = loop->app_sockets[i];
        if (!node)
            continue;
        LONG signaled = InterlockedExchange(&node->signaled, 0);
        /* recv/send may clear readiness after the batch was produced. Reset
         * stale records on an empty later poll, retaining unemitted ready nodes. */
        if (node->polled || (loop->app_socket_snapshot && !node->ready && signaled)) {
            node->polled = false;
            if (WSAEventSelect(node->socket, node->event, node->interests))
                SetEvent(loop->app_event);
        }
        SetThreadpoolWait(node->wait, node->event, NULL);
    }
}
#endif
