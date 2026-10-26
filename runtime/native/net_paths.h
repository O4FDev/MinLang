/* Unix domain stream sockets named by a file system path, connected pairs, and
 * descriptor passing (SCM_RIGHTS). Included by net.c, whose helpers it uses.
 * Linux and macOS (any POSIX host); Windows reports EOPNOTSUPP for each call.
 *
 * Results that carry descriptors use net.c's owned encoding: u32 status, u32 OS
 * error, then (receive) i64 descriptor count, that many i64 descriptors, then the
 * data; (pair) the two i64 descriptors. Every received descriptor is close-on-exec. */
#include <stddef.h>
#ifndef _WIN32
#include <sys/un.h>
#endif

/* SCM_MAX_FD on Linux: the most descriptors one message may carry. */
enum { NET_MAX_HANDLES = 253 };

#ifdef _WIN32
long long minyar_net_listenPath(const MinyarText *path, long long backlog) {
    (void)path;
    (void)backlog;
    remember_code("listenPath", WSAEOPNOTSUPP);
    return -1;
}
long long minyar_net_connectPath(const MinyarText *path) {
    (void)path;
    remember_code("connectPath", WSAEOPNOTSUPP);
    return -1;
}
MinyarBytes *minyar_net_pairResult(void) {
    return connect_result(NET_FAILURE, WSAEOPNOTSUPP, 0);
}
MinyarBytes *minyar_net_sendHandlesResult(long long connection, const MinyarBytes *data,
                                          const MinyarBytes *handles) {
    (void)connection;
    (void)data;
    (void)handles;
    return connect_result(NET_FAILURE, WSAEOPNOTSUPP, -1);
}
MinyarBytes *minyar_net_receiveHandlesResult(long long connection, long long limit,
                                             long long maximum) {
    (void)connection;
    (void)limit;
    (void)maximum;
    MinyarBytes *result = minyar_bytes_new(16);
    result_status(result, NET_FAILURE, WSAEOPNOTSUPP);
    memset((unsigned char *)result->bytes + 8, 0, 8);
    return result;
}
#else
/* Fill `address` from a path; false (with the reason remembered) when the path
 * is empty, holds a zero byte or does not fit sun_path with its terminator. */
static bool path_address(const char *what, const MinyarText *path, struct sockaddr_un *address,
                         socklen_t *length) {
    memset(address, 0, sizeof(*address));
    address->sun_family = AF_UNIX;
    long long size = path->byte_length;
    if (size <= 0 || memchr(path->bytes, 0, (size_t)size)) {
        remember_code(what, EINVAL);
        return false;
    }
    if ((unsigned long long)size >= sizeof(address->sun_path)) {
        remember_code(what, ENAMETOOLONG);
        return false;
    }
    memcpy(address->sun_path, path->bytes, (size_t)size);
    *length = (socklen_t)(offsetof(struct sockaddr_un, sun_path) + (size_t)size + 1);
    return true;
}
long long minyar_net_listenPath(const MinyarText *path, long long backlog) {
    last_error[0] = 0;
    if (backlog <= 0 || backlog > INT_MAX) {
        remember_code("backlog", BAD_ARGUMENT);
        return -1;
    }
    struct sockaddr_un address;
    socklen_t length;
    if (!path_address("listenPath", path, &address, &length))
        return -1;
    socket_t handle = socket(AF_UNIX, SOCK_STREAM, 0);
    if (handle == BAD_SOCKET) {
        remember_code("socket", socket_error());
        return -1;
    }
    /* Like TCP listeners: non-blocking, so accept reports would-block. */
    if (!configure(handle, true) || bind(handle, (struct sockaddr *)&address, length) ||
        listen(handle, (int)backlog)) {
        remember_code("bind/listen", socket_error());
        close_socket(handle);
        return -1;
    }
    return (long long)handle;
}
long long minyar_net_connectPath(const MinyarText *path) {
    last_error[0] = 0;
    struct sockaddr_un address;
    socklen_t length;
    if (!path_address("connectPath", path, &address, &length))
        return -1;
    socket_t handle = socket(AF_UNIX, SOCK_STREAM, 0);
    if (handle == BAD_SOCKET) {
        remember_code("socket", socket_error());
        return -1;
    }
    int status = -1;
    if (configure(handle, false)) {
        do {
            status = connect(handle, (struct sockaddr *)&address, length);
        } while (status < 0 && interrupted(socket_error()));
    }
    if (status) {
        remember_code("connect", socket_error());
        close_socket(handle);
        return -1;
    }
    return (long long)handle;
}
MinyarBytes *minyar_net_pairResult(void) {
    last_error[0] = 0;
    int pair[2];
    if (socketpair(AF_UNIX, SOCK_STREAM, 0, pair)) {
        int code = socket_error();
        remember_code("socketpair", code);
        return connect_result(NET_FAILURE, code, 0);
    }
    if (!configure(pair[0], false) || !configure(pair[1], false)) {
        int code = socket_error();
        remember_code("socketpair configuration", code);
        close(pair[0]);
        close(pair[1]);
        return connect_result(NET_FAILURE, code, 0);
    }
    MinyarBytes *result = connect_result(NET_OK, 0, pair[0]);
    unsigned char *second = minyar_bytes_extend(result, 8);
    for (unsigned i = 0; i < 8; i++)
        second[i] = (unsigned char)((uint64_t)(long long)pair[1] >> (8 * i));
    return result;
}
static long long get64(const unsigned char *p) {
    uint64_t value = 0;
    for (unsigned i = 0; i < 8; i++)
        value |= (uint64_t)p[i] << (8 * i);
    return (long long)value;
}
/* Send data once with the descriptors in `handles` (i64 each) attached to its
 * first byte. Returns net.c's 16-byte write result; a partial count still
 * delivered every descriptor. */
MinyarBytes *minyar_net_sendHandlesResult(long long connection, const MinyarBytes *data,
                                          const MinyarBytes *handles) {
    last_error[0] = 0;
    long long count = handles->byte_length / 8;
    if (!valid_socket(connection) || data->byte_length < 1 || data->byte_length > INT_MAX ||
        handles->byte_length % 8 || count > NET_MAX_HANDLES) {
        remember_code("sendHandles", BAD_ARGUMENT);
        return connect_result(NET_FAILURE, BAD_ARGUMENT, -1);
    }
    int descriptors[NET_MAX_HANDLES];
    for (long long i = 0; i < count; i++) {
        long long handle = get64((const unsigned char *)handles->bytes + 8 * i);
        if (handle < 0 || handle > INT_MAX) {
            remember_code("sendHandles", EBADF);
            return connect_result(NET_FAILURE, EBADF, -1);
        }
        descriptors[i] = (int)handle;
    }
    union {
        struct cmsghdr header;
        unsigned char space[CMSG_SPACE(sizeof(int) * NET_MAX_HANDLES)];
    } control;
    memset(&control, 0, sizeof(control));
    struct iovec segment = {(void *)data->bytes, (size_t)data->byte_length};
    struct msghdr message = {0};
    message.msg_iov = &segment;
    message.msg_iovlen = 1;
    if (count > 0) {
        message.msg_control = control.space;
        message.msg_controllen = CMSG_SPACE(sizeof(int) * (size_t)count);
        struct cmsghdr *header = CMSG_FIRSTHDR(&message);
        header->cmsg_level = SOL_SOCKET;
        header->cmsg_type = SCM_RIGHTS;
        header->cmsg_len = CMSG_LEN(sizeof(int) * (size_t)count);
        memcpy(CMSG_DATA(header), descriptors, sizeof(int) * (size_t)count);
    }
    int flags = 0;
#ifdef MSG_NOSIGNAL
    flags = MSG_NOSIGNAL;
#endif
    long long sent;
    int code;
    do {
        sent = sendmsg((int)connection, &message, flags);
        code = sent < 0 ? socket_error() : 0;
    } while (sent < 0 && interrupted(code));
    if (sent < 0) {
        remember_code("sendHandles", code);
        return connect_result(would_block(code) ? NET_WOULD_BLOCK : NET_FAILURE, code, -1);
    }
    return connect_result(NET_OK, 0, sent);
}
/* Receive up to `limit` bytes and at most `maximum` descriptors. More
 * descriptors than that is a failure: every one that arrived is closed and the
 * data is kept as a readable prefix (status NET_TRUNCATED). */
MinyarBytes *minyar_net_receiveHandlesResult(long long connection, long long limit,
                                             long long maximum) {
    last_error[0] = 0;
    MinyarBytes *result = minyar_bytes_new(16);
    memset((unsigned char *)result->bytes + 8, 0, 8);
    if (!valid_socket(connection) || limit <= 0 || limit > NET_MAX_READ || maximum < 0 ||
        maximum > NET_MAX_HANDLES) {
        remember_code("receiveHandles", BAD_ARGUMENT);
        result_status(result, NET_FAILURE, BAD_ARGUMENT);
        return result;
    }
    union {
        struct cmsghdr header;
        unsigned char space[CMSG_SPACE(sizeof(int) * NET_MAX_HANDLES)];
    } control;
    unsigned char *data = (unsigned char *)minyar_native_bytes_append(result, limit);
    struct iovec segment = {data, (size_t)limit};
    struct msghdr message = {0};
    message.msg_iov = &segment;
    message.msg_iovlen = 1;
    /* Room for at least one descriptor even when none are wanted: without a
     * control buffer macOS discards passed descriptors without saying so. */
    message.msg_control = control.space;
    message.msg_controllen = CMSG_SPACE(sizeof(int) * (size_t)(maximum > 0 ? maximum : 1));
    int flags = 0;
#ifdef MSG_CMSG_CLOEXEC
    flags = MSG_CMSG_CLOEXEC;
#endif
    long long count;
    int code;
    do {
        count = recvmsg((int)connection, &message, flags);
        code = count < 0 ? socket_error() : 0;
    } while (count < 0 && interrupted(code));
    if (count < 0) {
        result->byte_length = 16;
        remember_code("receiveHandles", code);
        result_status(result, would_block(code) ? NET_WOULD_BLOCK : NET_FAILURE, code);
        return result;
    }
    /* Room for every descriptor the control buffer can hold, alignment padding
     * included, so none that arrived can be left unrecorded and open. */
    int received[sizeof(control) / sizeof(int)];
    const long long room = (long long)(sizeof(received) / sizeof(int));
    long long handles = 0;
    for (struct cmsghdr *header = CMSG_FIRSTHDR(&message); header;
         header = CMSG_NXTHDR(&message, header)) {
        if (header->cmsg_level != SOL_SOCKET || header->cmsg_type != SCM_RIGHTS)
            continue;
        size_t bytes = header->cmsg_len - CMSG_LEN(0);
        for (size_t at = 0; at + sizeof(int) <= bytes && handles < room; at += sizeof(int))
            memcpy(&received[handles++], CMSG_DATA(header) + at, sizeof(int));
    }
#ifndef MSG_CMSG_CLOEXEC
    for (long long i = 0; i < handles; i++) {
        int descriptorFlags = fcntl(received[i], F_GETFD);
        if (descriptorFlags >= 0)
            fcntl(received[i], F_SETFD, descriptorFlags | FD_CLOEXEC);
    }
#endif
    /* Alignment padding can admit one descriptor more than asked for. */
    if ((message.msg_flags & MSG_CTRUNC) || handles > maximum) {
        for (long long i = 0; i < handles; i++)
            close(received[i]);
        /* Data first, then the (empty) descriptor list: the prefix stays readable. */
        result->byte_length = 16 + count;
        remember_code("receiveHandles", EMSGSIZE);
        result_status(result, NET_TRUNCATED, EMSGSIZE);
        return result;
    }
    /* Move the data after the descriptor list. */
    long long table = handles * 8;
    if (table) {
        minyar_native_bytes_append(result, table);
        data = (unsigned char *)result->bytes + 16;
        memmove(data + table, data, (size_t)count);
        for (long long i = 0; i < handles; i++)
            for (unsigned b = 0; b < 8; b++)
                data[8 * i + b] = (unsigned char)((uint64_t)(long long)received[i] >> (8 * b));
    }
    for (unsigned b = 0; b < 8; b++)
        ((unsigned char *)result->bytes)[8 + b] = (unsigned char)((uint64_t)handles >> (8 * b));
    result->byte_length = 16 + table + count;
    result_status(result, !count && !handles ? NET_EOF : NET_OK, 0);
    return result;
}
#endif
