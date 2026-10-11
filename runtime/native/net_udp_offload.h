/* Optional Linux UDP offload. Included after net_datagrams.h's wire helpers.
 * GRO sockets have generation-checked negative IDs, never public OS handles.
 * Ordinary APIs reject these IDs without adding work to their packet paths.
 * Like NetLoop, this registry and each socket belong to one owner thread. */
#ifndef MINYAR_NET_UDP_OFFLOAD_H
#define MINYAR_NET_UDP_OFFLOAD_H
enum { NET_UDP_UNAVAILABLE = 5, NET_UDP_CONTROL_LIMIT = 256, NET_UDP_STORAGE_LIMIT = 65535 };
#if !defined(__linux__) || defined(MINYAR_DISABLE_UDP_OFFLOAD)
static int udp_offload_unavailable(void) {
#ifdef _WIN32
    return WSAEOPNOTSUPP;
#else
    return EOPNOTSUPP;
#endif
}
#endif
#if defined(__linux__) && !defined(MINYAR_DISABLE_UDP_OFFLOAD)
#include <netinet/udp.h>
#include <time.h>
#ifndef UDP_SEGMENT
#define UDP_SEGMENT 103
#endif
#ifndef UDP_GRO
#define UDP_GRO 104
#endif
typedef struct {
    socket_t socket;
    uint32_t generation;
    bool active;
    unsigned char *storage;
    size_t copied, wire_length, position;
    unsigned segment;
    int receive_error;
    struct sockaddr_storage source;
    socklen_t source_length;
} NetUdpOffload;
static NetUdpOffload *udp_offload_slots;
static size_t udp_offload_count, udp_offload_capacity;
static NetUdpOffload *udp_offload_find(long long handle) {
    if (handle >= -1 || handle == LLONG_MIN)
        return NULL;
    uint64_t value = (uint64_t)(-handle);
    uint32_t low = (uint32_t)value;
    if (!low || low > udp_offload_count)
        return NULL;
    NetUdpOffload *slot = &udp_offload_slots[low - 1];
    return slot->active && slot->generation == (uint32_t)(value >> 32) ? slot : NULL;
}
/* Only positive, kernel-backed waits need a clock. Keep one absolute
 * deadline across EINTR; clock failures remain recoverable native results. */
static int udp_offload_clock(uint64_t *nanoseconds) {
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now))
        return errno;
    if (now.tv_sec < 0 || now.tv_nsec < 0 || now.tv_nsec >= 1000000000 ||
        (uint64_t)now.tv_sec > (UINT64_MAX - (uint64_t)now.tv_nsec) / 1000000000)
        return EOVERFLOW;
    *nanoseconds = (uint64_t)now.tv_sec * 1000000000 + (uint64_t)now.tv_nsec;
    return 0;
}
static bool udp_offload_unsupported(int code) {
    return code == ENOPROTOOPT || code == EOPNOTSUPP || code == ENOSYS;
}
static MinyarBytes *udp_offload_error(int code, long long value) {
    return connect_result(udp_offload_unsupported(code) ? NET_UDP_UNAVAILABLE : NET_FAILURE, code,
                          value);
}
/* Validate the whole ancillary chain before exposing any aggregate bytes.
 * memcpy avoids assuming cmsg header/data alignment in hostile fixtures.
 * The final cmsg may omit alignment padding. Other well-formed cmsgs are
 * ignored; duplicate, truncated or wrongly sized UDP_GRO is never accepted. */
static int udp_offload_control(const struct msghdr *message, size_t capacity, unsigned *segment) {
    *segment = 0;
    if (message->msg_flags & MSG_CTRUNC)
        return EMSGSIZE;
    size_t length = message->msg_controllen, at = 0;
    if (length > capacity || (length && !message->msg_control))
        return EINVAL;
    const unsigned char *bytes = message->msg_control;
    while (at < length) {
        size_t remaining = length - at;
        if (remaining < sizeof(struct cmsghdr))
            return EINVAL;
        struct cmsghdr control;
        memcpy(&control, bytes + at, sizeof(control));
        if (control.cmsg_len < CMSG_LEN(0) || control.cmsg_len > remaining)
            return EINVAL;
        if (control.cmsg_level == IPPROTO_UDP && control.cmsg_type == UDP_GRO) {
            if (*segment || control.cmsg_len != CMSG_LEN(sizeof(int)))
                return EINVAL;
            int value;
            memcpy(&value, bytes + at + CMSG_LEN(0), sizeof(value));
            if (value <= 0 || value > NET_DATAGRAM_LIMIT)
                return EINVAL;
            *segment = (unsigned)value;
        }
        if (control.cmsg_len == remaining)
            break;
        size_t next = CMSG_ALIGN(control.cmsg_len);
        if (next < control.cmsg_len)
            return EINVAL;
        if (next >= remaining)
            break;
        at += next;
    }
    return 0;
}
static int udp_offload_ingest(NetUdpOffload *slot, const struct msghdr *message, size_t wire_length,
                              size_t copied) {
    unsigned segment;
    int code = udp_offload_control(message, NET_UDP_CONTROL_LIMIT, &segment);
    if (code)
        return code;
    if (wire_length > (size_t)NET_BATCH_LIMIT * NET_DATAGRAM_LIMIT || copied > wire_length ||
        copied > NET_UDP_STORAGE_LIMIT || (!segment && wire_length > NET_UDP_STORAGE_LIMIT))
        return EOVERFLOW;
    if (message->msg_namelen > sizeof(slot->source) || !message->msg_name)
        return EINVAL;
    struct sockaddr_storage source = {0};
    memcpy(&source, message->msg_name, message->msg_namelen);
    if ((source.ss_family != AF_INET || message->msg_namelen != sizeof(struct sockaddr_in)) &&
        (source.ss_family != AF_INET6 || message->msg_namelen != sizeof(struct sockaddr_in6)))
        return EINVAL;
    if (segment && (!wire_length || (wire_length + segment - 1) / segment > NET_BATCH_LIMIT))
        return EOVERFLOW;
    if (copied != wire_length && !(message->msg_flags & MSG_TRUNC))
        return EINVAL;
    slot->copied = copied;
    slot->wire_length = wire_length;
    slot->position = 0;
    slot->segment = segment ? segment : (unsigned)wire_length;
    slot->receive_error = message->msg_flags & MSG_TRUNC ? EMSGSIZE : 0;
    memcpy(&slot->source, message->msg_name, message->msg_namelen);
    slot->source_length = message->msg_namelen;
    return 0;
}
/* maximum counts public datagrams, not kernel aggregates. Unconsumed
 * segments remain bounded in this socket's storage for the next call. */
static int udp_offload_drain(NetUdpOffload *slot, MinyarBytes *result, unsigned maximum,
                             unsigned limit, unsigned *count) {
    while (*count < maximum) {
        if (slot->position >= slot->copied && slot->wire_length) {
            int code = slot->receive_error;
            slot->copied = slot->wire_length = slot->position = 0;
            slot->receive_error = 0;
            return code;
        }
        unsigned whole = (unsigned)(slot->wire_length - slot->position);
        if (slot->segment && whole > slot->segment)
            whole = slot->segment;
        unsigned available = (unsigned)(slot->copied - slot->position);
        if (available > whole)
            available = whole;
        unsigned prefix = available > limit ? limit : available;
        append_datagram(result, slot->storage + slot->position, prefix, &slot->source,
                        slot->source_length,
                        prefix < whole || (!slot->wire_length && slot->receive_error));
        (*count)++;
        slot->position += whole;
        /* Zero-byte datagrams are real packets; clear explicitly so they
         * cannot be mistaken for a still-pending empty aggregate. */
        if (!slot->wire_length || slot->position >= slot->wire_length ||
            slot->position >= slot->copied) {
            int code = slot->receive_error;
            slot->copied = slot->wire_length = slot->position = 0;
            slot->receive_error = 0;
            return code;
        }
    }
    return 0;
}
#endif

static MinyarBytes *udp_offload_send(long long connection, const MinyarBytes *data,
                                     long long segment_size, const struct sockaddr *destination,
                                     socklen_t destination_length) {
    if (!valid_socket(connection) || segment_size <= 0 || segment_size > NET_DATAGRAM_LIMIT ||
        data->byte_length < 0 || data->byte_length > NET_DATAGRAM_LIMIT ||
        (data->byte_length && !data->bytes))
        return batch_send_result(NET_FAILURE, BAD_ARGUMENT, 0);
    unsigned packets =
        data->byte_length
            ? ((unsigned)data->byte_length + (unsigned)segment_size - 1) / (unsigned)segment_size
            : 1;
    if (packets > NET_BATCH_LIMIT)
        return batch_send_result(NET_FAILURE, BAD_ARGUMENT, 0);
#if defined(__linux__) && !defined(MINYAR_DISABLE_UDP_OFFLOAD)
    int type = 0;
    socklen_t type_length = sizeof(type);
    if (getsockopt((socket_t)connection, SOL_SOCKET, SO_TYPE, &type, &type_length))
        return udp_offload_error(socket_error(), 0);
    if (type != SOCK_DGRAM)
        return batch_send_result(NET_FAILURE, BAD_ARGUMENT, 0);
    /* Old kernels reject unknown UDP cmsgs with EINVAL too. An explicit
     * option probe distinguishes unavailable GSO from invalid send data. */
    int configured = 0;
    socklen_t configured_length = sizeof(configured);
    if (getsockopt((socket_t)connection, IPPROTO_UDP, UDP_SEGMENT, &configured, &configured_length))
        return udp_offload_error(socket_error(), 0);
    union {
        struct cmsghdr alignment;
        unsigned char bytes[CMSG_SPACE(sizeof(uint16_t))];
    } control = {0};
    uint16_t size = (uint16_t)segment_size;
    struct iovec payload = {(void *)data->bytes, (size_t)data->byte_length};
    struct msghdr message = {0};
    message.msg_name = (void *)destination;
    message.msg_namelen = destination_length;
    message.msg_iov = &payload;
    message.msg_iovlen = 1;
    message.msg_control = control.bytes;
    message.msg_controllen = sizeof(control.bytes);
    struct cmsghdr *cmsg = CMSG_FIRSTHDR(&message);
    cmsg->cmsg_level = IPPROTO_UDP;
    cmsg->cmsg_type = UDP_SEGMENT;
    cmsg->cmsg_len = CMSG_LEN(sizeof(size));
    memcpy(CMSG_DATA(cmsg), &size, sizeof(size));
    ssize_t sent;
    int code;
    do {
        sent = sendmsg((socket_t)connection, &message, MSG_DONTWAIT | MSG_NOSIGNAL);
        code = sent < 0 ? socket_error() : 0;
    } while (sent < 0 && interrupted(code));
    if (sent < 0) {
        if (would_block(code))
            return batch_send_result(NET_WOULD_BLOCK, code, 0);
        return udp_offload_error(code, 0);
    }
    if (sent != data->byte_length)
        return batch_send_result(NET_FAILURE, EIO, 0);
    return batch_send_result(NET_OK, 0, packets);
#else
    (void)destination;
    (void)destination_length;
    return batch_send_result(NET_UDP_UNAVAILABLE, udp_offload_unavailable(), 0);
#endif
}
MinyarBytes *minyar_net_sendOffloadResult(long long connection, const MinyarBytes *data,
                                          long long segment_size) {
    return udp_offload_send(connection, data, segment_size, NULL, 0);
}
MinyarBytes *minyar_net_sendOffloadToResult(long long connection, const MinyarText *host,
                                            long long port, const MinyarBytes *data,
                                            long long segment_size) {
    if (host->byte_length < 1 || host->byte_length > 255 || port < 1 || port > 65535)
        return batch_send_result(NET_FAILURE, BAD_ARGUMENT, 0);
    for (long long i = 0; i < host->byte_length; i++)
        if (host->bytes[i] < 33 || host->bytes[i] > 126)
            return batch_send_result(NET_FAILURE, BAD_ARGUMENT, 0);
    char name[256], service[6];
    memcpy(name, host->bytes, (size_t)host->byte_length);
    name[host->byte_length] = 0;
    snprintf(service, sizeof(service), "%lld", port);
    struct addrinfo hints = {0}, *found = NULL;
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_DGRAM;
    hints.ai_flags = AI_NUMERICHOST | AI_NUMERICSERV;
    if (getaddrinfo(name, service, &hints, &found))
        return batch_send_result(NET_FAILURE, BAD_ARGUMENT, 0);
    MinyarBytes *result = udp_offload_send(connection, data, segment_size, found->ai_addr,
                                           (socklen_t)found->ai_addrlen);
    freeaddrinfo(found);
    return result;
}
MinyarBytes *minyar_net_offloadOpenResult(const MinyarText *host, long long port) {
#if defined(__linux__) && !defined(MINYAR_DISABLE_UDP_OFFLOAD)
    if (host->byte_length < 1 || host->byte_length > 255 || port < 0 || port > 65535)
        return connect_result(NET_FAILURE, BAD_ARGUMENT, -1);
    for (long long i = 0; i < host->byte_length; i++)
        if (host->bytes[i] < 33 || host->bytes[i] > 126)
            return connect_result(NET_FAILURE, BAD_ARGUMENT, -1);
    char name[256], service[6];
    memcpy(name, host->bytes, (size_t)host->byte_length);
    name[host->byte_length] = 0;
    snprintf(service, sizeof(service), "%lld", port);
    struct addrinfo hints = {0}, *found = NULL;
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_DGRAM;
    hints.ai_flags = AI_NUMERICHOST | AI_NUMERICSERV;
    if (getaddrinfo(name, service, &hints, &found))
        return connect_result(NET_FAILURE, BAD_ARGUMENT, -1);
    socket_t handle = BAD_SOCKET;
    int code = BAD_ARGUMENT, enabled = 1;
    for (struct addrinfo *peer = found; peer; peer = peer->ai_next) {
        socket_t candidate = (socket_t)socket(peer->ai_family, SOCK_DGRAM, peer->ai_protocol);
        if (candidate == BAD_SOCKET) {
            code = socket_error();
            continue;
        }
        if (!configure(candidate, true) ||
            setsockopt(candidate, IPPROTO_UDP, UDP_GRO, &enabled, sizeof(enabled)) ||
            bind(candidate, peer->ai_addr, (socklen_t)peer->ai_addrlen)) {
            code = socket_error();
            close_socket(candidate);
            continue;
        }
        handle = candidate;
        break;
    }
    freeaddrinfo(found);
    if (handle == BAD_SOCKET)
        return udp_offload_error(code, -1);
    size_t index;
    for (index = 0; index < udp_offload_count; index++)
        if (!udp_offload_slots[index].active && udp_offload_slots[index].generation < INT32_MAX)
            break;
    if (index == udp_offload_count) {
        if (udp_offload_count == udp_offload_capacity) {
            size_t capacity = udp_offload_capacity ? udp_offload_capacity * 2 : 8;
            NetUdpOffload *slots = capacity > udp_offload_capacity && capacity < UINT32_MAX &&
                                           capacity <= SIZE_MAX / sizeof(*slots)
                                       ? realloc(udp_offload_slots, capacity * sizeof(*slots))
                                       : NULL;
            if (!slots) {
                close_socket(handle);
                return connect_result(NET_FAILURE, ENOMEM, -1);
            }
            memset(slots + udp_offload_capacity, 0,
                   (capacity - udp_offload_capacity) * sizeof(*slots));
            udp_offload_slots = slots;
            udp_offload_capacity = capacity;
        }
        udp_offload_count++;
    }
    NetUdpOffload *slot = &udp_offload_slots[index];
    slot->generation++;
    slot->socket = handle;
    slot->active = true;
    uint64_t id = (uint64_t)slot->generation << 32 | (uint64_t)(index + 1);
    return connect_result(NET_OK, 0, -(long long)id);
#else
    (void)host;
    (void)port;
    return connect_result(NET_UDP_UNAVAILABLE, udp_offload_unavailable(), -1);
#endif
}
MinyarBytes *minyar_net_offloadReceiveResult(long long handle, long long maximum, long long limit) {
    MinyarBytes *result = minyar_bytes_new(12);
#if defined(__linux__) && !defined(MINYAR_DISABLE_UDP_OFFLOAD)
    NetUdpOffload *slot = udp_offload_find(handle);
    if (!slot || maximum < 1 || maximum > NET_BATCH_LIMIT || limit < 1 ||
        limit > NET_DATAGRAM_LIMIT) {
        result_status(result, NET_FAILURE, slot ? EINVAL : EBADF);
        return result;
    }
    if (!slot->storage) {
        slot->storage = malloc(NET_UDP_STORAGE_LIMIT);
        if (!slot->storage) {
            result_status(result, NET_FAILURE, ENOMEM);
            return result;
        }
    }
    unsigned count = 0;
    int code = 0;
    unsigned status = NET_OK;
    while (count < (unsigned)maximum) {
        if (!slot->wire_length) {
            union {
                struct cmsghdr alignment;
                unsigned char bytes[NET_UDP_CONTROL_LIMIT];
            } control = {0};
            struct sockaddr_storage source;
            struct iovec payload = {slot->storage, NET_UDP_STORAGE_LIMIT};
            struct msghdr message = {0};
            message.msg_iov = &payload;
            message.msg_iovlen = 1;
            message.msg_name = &source;
            message.msg_namelen = sizeof(source);
            message.msg_control = control.bytes;
            message.msg_controllen = sizeof(control.bytes);
            ssize_t received;
            do {
                received = recvmsg(slot->socket, &message, MSG_DONTWAIT | MSG_TRUNC);
                code = received < 0 ? socket_error() : 0;
            } while (received < 0 && interrupted(code));
            if (received < 0) {
                if (!would_block(code) || !count)
                    status = would_block(code) ? NET_WOULD_BLOCK : NET_FAILURE;
                else
                    code = 0;
                break;
            }
            size_t copied =
                (size_t)received > NET_UDP_STORAGE_LIMIT ? NET_UDP_STORAGE_LIMIT : (size_t)received;
            code = udp_offload_ingest(slot, &message, (size_t)received, copied);
            if (code) {
                status = code == EMSGSIZE ? NET_TRUNCATED : NET_FAILURE;
                break;
            }
        }
        code = udp_offload_drain(slot, result, (unsigned)maximum, (unsigned)limit, &count);
        if (code) {
            status = NET_TRUNCATED;
            break;
        }
    }
    result_status(result, status, code);
    put32((unsigned char *)result->bytes + 8, count);
#else
    (void)handle;
    (void)maximum;
    (void)limit;
    result_status(result, NET_UDP_UNAVAILABLE, udp_offload_unavailable());
#endif
    return result;
}
MinyarBytes *minyar_net_offloadPortResult(long long handle) {
#if defined(__linux__) && !defined(MINYAR_DISABLE_UDP_OFFLOAD)
    NetUdpOffload *slot = udp_offload_find(handle);
    if (!slot)
        return connect_result(NET_FAILURE, EBADF, -1);
    long long port = minyar_net_localPort(slot->socket);
    return connect_result(port >= 0 ? NET_OK : NET_FAILURE, port >= 0 ? 0 : socket_error(), port);
#else
    (void)handle;
    return connect_result(NET_UDP_UNAVAILABLE, udp_offload_unavailable(), -1);
#endif
}
MinyarBytes *minyar_net_offloadReadyResult(long long handle, long long milliseconds) {
#if defined(__linux__) && !defined(MINYAR_DISABLE_UDP_OFFLOAD)
    NetUdpOffload *slot = udp_offload_find(handle);
    if (!slot || milliseconds < 0 || milliseconds > INT_MAX)
        return connect_result(NET_FAILURE, slot ? EINVAL : EBADF, 0);
    if (slot->wire_length)
        return connect_result(NET_OK, 0, 1);
    uint64_t deadline = 0;
    if (milliseconds) {
        int code = udp_offload_clock(&deadline);
        uint64_t duration = (uint64_t)milliseconds * 1000000;
        if (code || deadline > UINT64_MAX - duration)
            return connect_result(NET_FAILURE, code ? code : EOVERFLOW, 0);
        deadline += duration;
    }
    struct pollfd entry = {slot->socket, POLLIN, 0};
    int ready, remaining = (int)milliseconds;
    for (;;) {
        ready = poll(&entry, 1, remaining);
        if (ready >= 0 || !interrupted(errno))
            break;
        uint64_t now = 0;
        int code = milliseconds ? udp_offload_clock(&now) : 0;
        if (code)
            return connect_result(NET_FAILURE, code, 0);
        if (!milliseconds || now >= deadline) {
            ready = 0;
            break;
        }
        uint64_t left = deadline - now;
        uint64_t rounded = left / 1000000 + (left % 1000000 != 0);
        remaining = rounded > INT_MAX ? INT_MAX : (int)rounded;
    }
    if (ready > 0 && (entry.revents & POLLNVAL))
        return connect_result(NET_FAILURE, EBADF, 0);
    return connect_result(ready < 0 ? NET_FAILURE : NET_OK, ready < 0 ? errno : 0, ready > 0);
#else
    (void)handle;
    (void)milliseconds;
    return connect_result(NET_UDP_UNAVAILABLE, udp_offload_unavailable(), 0);
#endif
}
/* Forward declaration: net_loop.h is included after this header by net.c. */
MinyarBytes *minyar_net_loopWatch(long long, long long, long long, long long);
MinyarBytes *minyar_net_offloadWatchResult(long long loop, long long handle, long long interest,
                                           long long token) {
#if defined(__linux__) && !defined(MINYAR_DISABLE_UDP_OFFLOAD)
    NetUdpOffload *slot = udp_offload_find(handle);
    if (!slot)
        return connect_result(NET_FAILURE, EBADF, -1);
    return minyar_net_loopWatch(loop, slot->socket, interest, token);
#else
    (void)loop;
    (void)handle;
    (void)interest;
    (void)token;
    return connect_result(NET_UDP_UNAVAILABLE, udp_offload_unavailable(), -1);
#endif
}
MinyarBytes *minyar_net_offloadSendToResult(long long handle, const MinyarText *host,
                                            long long port, const MinyarBytes *data,
                                            long long segment_size) {
#if defined(__linux__) && !defined(MINYAR_DISABLE_UDP_OFFLOAD)
    NetUdpOffload *slot = udp_offload_find(handle);
    if (!slot)
        return connect_result(NET_FAILURE, EBADF, 0);
    return minyar_net_sendOffloadToResult(slot->socket, host, port, data, segment_size);
#else
    (void)handle;
    (void)host;
    (void)port;
    (void)data;
    (void)segment_size;
    return connect_result(NET_UDP_UNAVAILABLE, udp_offload_unavailable(), 0);
#endif
}
MinyarBytes *minyar_net_offloadCloseResult(long long handle) {
#if defined(__linux__) && !defined(MINYAR_DISABLE_UDP_OFFLOAD)
    NetUdpOffload *slot = udp_offload_find(handle);
    if (!slot)
        return connect_result(NET_FAILURE, EBADF, 0);
    int status = close_socket(slot->socket), code = status ? socket_error() : 0;
    /* close may consume an fd even on error; never let a stale ID retry it. */
    slot->active = false;
    free(slot->storage);
    slot->storage = NULL;
    slot->copied = slot->wire_length = slot->position = 0;
    slot->receive_error = 0;
    return connect_result(status ? NET_FAILURE : NET_OK, code, status ? 0 : 1);
#else
    (void)handle;
    return connect_result(NET_UDP_UNAVAILABLE, udp_offload_unavailable(), 0);
#endif
}
#endif
