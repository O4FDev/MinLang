/* Hosted sockets. Owned results encode u32 status, u32 OS error, then data
 * (reads) or i64 count (writes), all little endian. UDP empty data != TCP EOF. */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE 1
#endif
#include "../minyar_native.h"
#include <errno.h>
#include <limits.h>
#include <stdint.h>
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
typedef SOCKET socket_t;
#define close_socket closesocket
#define socket_error() WSAGetLastError()
#define BAD_SOCKET INVALID_SOCKET
#define BAD_ARGUMENT WSAEINVAL
#else
#include <fcntl.h>
#include <netdb.h>
#include <poll.h>
#include <sys/socket.h>
#include <unistd.h>
typedef int socket_t;
#define close_socket close
#define socket_error() errno
#define BAD_SOCKET (-1)
#define BAD_ARGUMENT EINVAL
#endif

enum { NET_OK, NET_WOULD_BLOCK, NET_EOF, NET_FAILURE, NET_TRUNCATED };
enum { NET_MAX_READ = 16 * 1024 * 1024 };
static _Thread_local char last_error[256];

static bool valid_socket(long long connection) {
#ifdef _WIN32
    return connection >= 0 && (unsigned long long)connection <= UINTPTR_MAX;
#else
    return connection >= 0 && connection <= INT_MAX;
#endif
}

static void remember(const char *what, const char *detail) {
    snprintf(last_error, sizeof(last_error), "%s: %s", what, detail);
}
static void remember_code(const char *what, int code) {
#ifdef _WIN32
    char detail[48];
    snprintf(detail, sizeof(detail), "Winsock error %d", code);
    remember(what, detail);
#else
    remember(what, strerror(code));
#endif
}
static bool interrupted(int code) {
#ifdef _WIN32
    return code == WSAEINTR;
#else
    return code == EINTR;
#endif
}
static bool would_block(int code) {
#ifdef _WIN32
    return code == WSAEWOULDBLOCK;
#else
    return code == EAGAIN || code == EWOULDBLOCK;
#endif
}
#ifdef _WIN32
static INIT_ONCE winsock_once = INIT_ONCE_STATIC_INIT;
static int winsock_status;
static BOOL CALLBACK start_winsock(PINIT_ONCE once, PVOID parameter, PVOID *context) {
    (void)once;
    (void)parameter;
    (void)context;
    WSADATA data;
    winsock_status = WSAStartup(MAKEWORD(2, 2), &data);
    return TRUE;
}
#endif
static bool initialize(void) {
    last_error[0] = 0;
#ifdef _WIN32
    if (!InitOnceExecuteOnce(&winsock_once, start_winsock, NULL, NULL) || winsock_status) {
        remember_code("initialize", winsock_status ? winsock_status : BAD_ARGUMENT);
        return false;
    }
#endif
    return true;
}
static bool address(const MinyarText *host, long long port, int type, struct addrinfo **found) {
    char name[256], service[16];
    if (port < 0 || port > 65535 || host->byte_length <= 0 ||
        host->byte_length >= (long long)sizeof(name) ||
        memchr(host->bytes, 0, (size_t)host->byte_length)) {
        remember_code("address", BAD_ARGUMENT);
        return false;
    }
    minyar_native_text(host, name, sizeof(name));
    snprintf(service, sizeof(service), "%lld", port);
    struct addrinfo hints = {0};
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = type;
    int code = getaddrinfo(name, service, &hints, found);
    if (code) {
        remember("resolve", gai_strerror(code));
        return false;
    }
    return true;
}
bool minyar_net_nonBlocking(long long connection, bool enabled) {
    last_error[0] = 0;
    if (!valid_socket(connection)) {
        remember_code("nonBlocking", BAD_ARGUMENT);
        return false;
    }
#ifdef _WIN32
    u_long value = enabled ? 1 : 0;
    int status = ioctlsocket((socket_t)connection, FIONBIO, &value);
#else
    int flags = fcntl((socket_t)connection, F_GETFL);
    int status = flags < 0 ? -1
                           : fcntl((socket_t)connection, F_SETFL,
                                   enabled ? flags | O_NONBLOCK : flags & ~O_NONBLOCK);
#endif
    if (status)
        remember_code("nonBlocking", socket_error());
    return status == 0;
}
static bool configure(socket_t handle, bool nonblocking) {
#ifdef _WIN32
    if (!SetHandleInformation((HANDLE)handle, HANDLE_FLAG_INHERIT, 0))
        return false;
#else
    int flags = fcntl(handle, F_GETFD);
    if (flags < 0 || fcntl(handle, F_SETFD, flags | FD_CLOEXEC) < 0)
        return false;
#ifdef SO_NOSIGPIPE
    int enabled = 1;
    if (setsockopt(handle, SOL_SOCKET, SO_NOSIGPIPE, &enabled, sizeof(enabled)))
        return false;
#endif
#endif
    return !nonblocking || minyar_net_nonBlocking((long long)handle, true);
}
static long long open_socket(const MinyarText *host, long long port, int type, bool binding,
                             long long backlog) {
    if (!initialize())
        return -1;
    struct addrinfo *found = NULL;
    if (!address(host, port, type, &found))
        return -1;
    long long handle = -1;
    for (struct addrinfo *option = found; option; option = option->ai_next) {
        socket_t candidate = socket(option->ai_family, option->ai_socktype, option->ai_protocol);
        if (candidate == BAD_SOCKET) {
            remember_code("socket", socket_error());
            continue;
        }
        int status = -1;
        if (configure(candidate, binding)) {
            if (binding) {
                status = bind(candidate, option->ai_addr, (socklen_t)option->ai_addrlen);
                if (!status && type == SOCK_STREAM)
                    status = listen(candidate, (int)backlog);
            } else {
                do {
                    status = connect(candidate, option->ai_addr, (socklen_t)option->ai_addrlen);
                } while (status < 0 && interrupted(socket_error()));
            }
        }
        if (!status) {
            handle = (long long)candidate;
            last_error[0] = 0;
            break;
        }
        remember_code(binding ? "bind/listen" : "connect", socket_error());
        close_socket(candidate);
    }
    freeaddrinfo(found);
    return handle;
}
long long minyar_net_connect(const MinyarText *host, long long port) {
    return open_socket(host, port, SOCK_STREAM, false, 0);
}
long long minyar_net_listen(const MinyarText *host, long long port, long long backlog) {
    if (backlog <= 0 || backlog > INT_MAX) {
        remember_code("backlog", BAD_ARGUMENT);
        return -1;
    }
    return open_socket(host, port, SOCK_STREAM, true, backlog);
}
long long minyar_net_udp(const MinyarText *host, long long port) {
    return open_socket(host, port, SOCK_DGRAM, true, 0);
}
long long minyar_net_accept(long long listener) {
    last_error[0] = 0;
    if (!valid_socket(listener)) {
        remember_code("accept", BAD_ARGUMENT);
        return -1;
    }
    socket_t result;
    do {
        result = accept((socket_t)listener, NULL, NULL);
    } while (result == BAD_SOCKET && interrupted(socket_error()));
    if (result == BAD_SOCKET) {
        remember_code("accept", socket_error());
        return -1;
    }
    if (!configure(result, true)) {
        remember_code("accept configuration", socket_error());
        close_socket(result);
        return -1;
    }
    return (long long)result;
}
long long minyar_net_localPort(long long connection) {
    struct sockaddr_storage address;
    socklen_t length = sizeof(address);
    last_error[0] = 0;
    if (!valid_socket(connection)) {
        remember_code("localPort", BAD_ARGUMENT);
        return -1;
    }
    if (getsockname((socket_t)connection, (struct sockaddr *)&address, &length)) {
        remember_code("localPort", socket_error());
        return -1;
    }
    if (address.ss_family == AF_INET)
        return ntohs(((struct sockaddr_in *)&address)->sin_port);
    if (address.ss_family == AF_INET6)
        return ntohs(((struct sockaddr_in6 *)&address)->sin6_port);
    remember_code("localPort", BAD_ARGUMENT);
    return -1;
}
bool minyar_net_udpConnect(long long connection, const MinyarText *host, long long port) {
    if (!initialize())
        return false;
    if (!valid_socket(connection)) {
        remember_code("udpConnect", BAD_ARGUMENT);
        return false;
    }
    struct addrinfo *found = NULL;
    if (!address(host, port, SOCK_DGRAM, &found))
        return false;
    bool success = false;
    for (struct addrinfo *option = found; option; option = option->ai_next) {
        if (!connect((socket_t)connection, option->ai_addr, (socklen_t)option->ai_addrlen)) {
            success = true;
            last_error[0] = 0;
            break;
        }
        remember_code("udpConnect", socket_error());
    }
    freeaddrinfo(found);
    return success;
}
static void put32(unsigned char *p, uint32_t value) {
    for (unsigned i = 0; i < 4; i++)
        p[i] = (unsigned char)(value >> (8 * i));
}
static void result_status(MinyarBytes *b, unsigned status, int code) {
    put32((unsigned char *)b->bytes, status);
    put32((unsigned char *)b->bytes + 4, (uint32_t)code);
}
static MinyarBytes *connect_result(unsigned status, int code, long long value) {
    MinyarBytes *result = minyar_bytes_new(16);
    result_status(result, status, code);
    for (unsigned i = 0; i < 8; i++)
        ((unsigned char *)result->bytes)[8 + i] = (unsigned char)((uint64_t)value >> (8 * i));
    return result;
}
/* Literal-address connect never invokes DNS or waits for a remote peer. */
MinyarBytes *minyar_net_connectStartResult(const MinyarText *host, long long port) {
    if (!initialize() || port <= 0 || port > 65535 || host->byte_length <= 0 ||
        host->byte_length >= 256 || memchr(host->bytes, 0, (size_t)host->byte_length))
        return connect_result(NET_FAILURE, BAD_ARGUMENT, -1);
    char name[256], service[16];
    memcpy(name, host->bytes, (size_t)host->byte_length);
    name[host->byte_length] = 0;
    snprintf(service, sizeof(service), "%lld", port);
    struct addrinfo hints = {0}, *found = NULL;
    hints.ai_socktype = SOCK_STREAM;
    hints.ai_flags = AI_NUMERICHOST | AI_NUMERICSERV;
    int resolved = getaddrinfo(name, service, &hints, &found);
    if (resolved)
        return connect_result(NET_FAILURE, resolved, -1);
    int code = BAD_ARGUMENT;
    socket_t handle = BAD_SOCKET;
    for (struct addrinfo *option = found; option; option = option->ai_next) {
        socket_t candidate = socket(option->ai_family, option->ai_socktype, option->ai_protocol);
        if (candidate == BAD_SOCKET) {
            code = socket_error();
            continue;
        }
        if (!configure(candidate, true)) {
            code = socket_error();
            close_socket(candidate);
            continue;
        }
        int status = connect(candidate, option->ai_addr, (socklen_t)option->ai_addrlen);
        code = status ? socket_error() : 0;
        bool pending = would_block(code) || interrupted(code);
#ifndef _WIN32
        pending = pending || code == EINPROGRESS || code == EALREADY;
#endif
        if (!status || pending) {
            handle = candidate;
            break;
        }
        close_socket(candidate);
    }
    freeaddrinfo(found);
    if (handle == BAD_SOCKET)
        return connect_result(NET_FAILURE, code, -1);
    return connect_result(NET_OK, 0, (long long)handle);
}
MinyarBytes *minyar_net_connectFinishResult(long long connection) {
    if (!valid_socket(connection))
        return connect_result(NET_FAILURE, BAD_ARGUMENT, 0);
#ifdef _WIN32
    WSAPOLLFD entry = {(socket_t)connection, POLLOUT, 0};
    int ready = WSAPoll(&entry, 1, 0);
    int blocked = WSAEWOULDBLOCK;
#else
    struct pollfd entry = {(int)connection, POLLOUT, 0};
    int ready = poll(&entry, 1, 0);
    int blocked = EAGAIN;
#endif
    if (ready < 0)
        return connect_result(NET_FAILURE, socket_error(), 0);
    if (!ready)
        return connect_result(NET_WOULD_BLOCK, blocked, 0);
    if (entry.revents & POLLNVAL)
        return connect_result(NET_FAILURE, BAD_ARGUMENT, 0);
    int code = 0;
    socklen_t length = sizeof(code);
    if (getsockopt((socket_t)connection, SOL_SOCKET, SO_ERROR, (void *)&code, &length))
        return connect_result(NET_FAILURE, socket_error(), 0);
    if (code)
        return connect_result(NET_FAILURE, code, 0);
    if (!(entry.revents & POLLOUT))
        return connect_result(NET_WOULD_BLOCK, blocked, 0);
    return connect_result(NET_OK, 0, 1);
}
MinyarBytes *minyar_net_readResult(long long connection, long long limit, bool datagram) {
    MinyarBytes *result = minyar_bytes_new(8);
    last_error[0] = 0;
    if (!valid_socket(connection) || limit <= 0 || limit > NET_MAX_READ ||
        (datagram && limit > 65535)) {
        remember_code("read", BAD_ARGUMENT);
        result_status(result, NET_FAILURE, BAD_ARGUMENT);
        return result;
    }
    unsigned char *buffer = minyar_bytes_extend(result, limit);
    long long count;
    bool truncated = false;
    int code;
    do {
#ifdef _WIN32
        count = recv((socket_t)connection, (char *)buffer, (int)limit, 0);
        code = count < 0 ? socket_error() : 0;
        if (datagram && code == WSAEMSGSIZE) {
            count = limit;
            truncated = true;
            code = 0;
        }
#else
        if (datagram) {
            struct iovec segment = {buffer, (size_t)limit};
            struct msghdr message = {0};
            message.msg_iov = &segment;
            message.msg_iovlen = 1;
            count = recvmsg((socket_t)connection, &message, 0);
            truncated = (message.msg_flags & MSG_TRUNC) != 0;
        } else {
            count = recv((socket_t)connection, buffer, (size_t)limit, 0);
        }
        code = count < 0 ? socket_error() : 0;
#endif
    } while (count < 0 && interrupted(code));
    result->byte_length = 8 + (count > 0 ? count : 0);
    if (count < 0) {
        remember_code("read", code);
        result_status(result, would_block(code) ? NET_WOULD_BLOCK : NET_FAILURE, code);
    } else if (truncated) {
        result_status(result, NET_TRUNCATED, 0);
    } else {
        result_status(result, !count && !datagram ? NET_EOF : NET_OK, 0);
    }
    return result;
}
static long long write_once(long long connection, const MinyarBytes *data, int *code) {
    int flags = 0;
#ifdef MSG_NOSIGNAL
    flags = MSG_NOSIGNAL;
#endif
    long long count;
    do {
        count =
            send((socket_t)connection, (const char *)data->bytes, (int)data->byte_length, flags);
        *code = count < 0 ? socket_error() : 0;
    } while (count < 0 && interrupted(*code));
    return count;
}
MinyarBytes *minyar_net_writeResult(long long connection, const MinyarBytes *data) {
    MinyarBytes *result = minyar_bytes_new(16);
    last_error[0] = 0;
    int code = BAD_ARGUMENT;
    long long count = -1;
    if (valid_socket(connection) && data->byte_length >= 0 && data->byte_length <= INT_MAX)
        count = write_once(connection, data, &code);
    if (count < 0)
        remember_code("write", code);
    result_status(result, count < 0 ? (would_block(code) ? NET_WOULD_BLOCK : NET_FAILURE) : NET_OK,
                  code);
    for (unsigned i = 0; i < 8; i++)
        ((unsigned char *)result->bytes)[8 + i] = (unsigned char)((uint64_t)count >> (8 * i));
    return result;
}
/* Compatibility operations retain their old API, but suppress SIGPIPE and
 * report errors from Winsock rather than unrelated C errno on Windows. */
long long minyar_net_send(long long connection, const MinyarBytes *data) {
    last_error[0] = 0;
    if (!valid_socket(connection)) {
        remember_code("send", BAD_ARGUMENT);
        return 0;
    }
    long long sent = 0;
    while (sent < data->byte_length) {
        MinyarBytes remaining = *data;
        remaining.bytes += sent;
        remaining.byte_length = data->byte_length - sent;
        if (remaining.byte_length > INT_MAX)
            remaining.byte_length = INT_MAX;
        int code;
        long long count = write_once(connection, &remaining, &code);
        if (count <= 0) {
            remember_code("send", count < 0 ? code : BAD_ARGUMENT);
            break;
        }
        sent += count;
    }
    return sent;
}
MinyarBytes *minyar_net_receive(long long connection, long long limit) {
    MinyarBytes *result = minyar_bytes_new(0);
    last_error[0] = 0;
    if (!valid_socket(connection) || limit <= 0 || limit > NET_MAX_READ) {
        remember_code("receive limit", BAD_ARGUMENT);
        return result;
    }
    unsigned char *buffer = minyar_bytes_extend(result, limit);
    long long count;
    int code;
    do {
        count = recv((socket_t)connection, (char *)buffer, (int)limit, 0);
        code = count < 0 ? socket_error() : 0;
    } while (count < 0 && interrupted(code));
    result->byte_length = count > 0 ? count : 0;
    if (count < 0)
        remember_code("receive", code);
    return result;
}
bool minyar_net_ready(long long connection, long long milliseconds) {
    last_error[0] = 0;
    if (!valid_socket(connection) || milliseconds < 0 || milliseconds > INT_MAX) {
        remember_code("ready", BAD_ARGUMENT);
        return false;
    }
#ifdef _WIN32
    WSAPOLLFD entry = {(socket_t)connection, POLLRDNORM, 0};
    int result = WSAPoll(&entry, 1, (int)milliseconds);
#else
    struct pollfd entry = {(int)connection, POLLIN, 0};
    int result = poll(&entry, 1, (int)milliseconds);
#endif
    if (result < 0)
        remember_code("ready", socket_error());
    return result > 0;
}
void minyar_net_close(long long connection) {
    last_error[0] = 0;
    if (!valid_socket(connection)) {
        remember_code("close", BAD_ARGUMENT);
        return;
    }
    if (close_socket((socket_t)connection))
        remember_code("close", socket_error());
}
MinyarText *minyar_net_lastError(void) {
    return minyar_native_copy_text((const unsigned char *)last_error,
                                   (long long)strlen(last_error));
}

#include "net_datagrams.h"
#include "net_loop.h"
