/* The `net` package: TCP connections over the host's sockets. */
#include "../minyar_native.h"
#include <errno.h>
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
typedef SOCKET socket_t;
#define close_socket closesocket
#else
#include <netdb.h>
#include <poll.h>
#include <sys/socket.h>
#include <unistd.h>
typedef int socket_t;
#define close_socket close
#endif

static char last_error[256] = "";

static void remember(const char *what, const char *detail) {
    snprintf(last_error, sizeof(last_error), "%s: %s", what, detail);
}

long long minyar_net_connect(const MinyarText *host, long long port) {
    char name[256], service[16];
    minyar_native_text(host, name, sizeof(name));
    snprintf(service, sizeof(service), "%lld", port);
#ifdef _WIN32
    static int started;
    if (!started) {
        WSADATA data;
        WSAStartup(MAKEWORD(2, 2), &data);
        started = 1;
    }
#endif
    struct addrinfo hints = {0}, *found = NULL;
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    int status = getaddrinfo(name, service, &hints, &found);
    if (status != 0) {
        remember(name, gai_strerror(status));
        return -1;
    }
    long long handle = -1;
    for (struct addrinfo *option = found; option; option = option->ai_next) {
        socket_t socket_handle = socket(option->ai_family, option->ai_socktype, option->ai_protocol);
        if ((long long)socket_handle < 0) continue;
        if (connect(socket_handle, option->ai_addr, (socklen_t)option->ai_addrlen) == 0) {
            handle = (long long)socket_handle;
            break;
        }
        remember(name, strerror(errno));
        close_socket(socket_handle);
    }
    freeaddrinfo(found);
    return handle;
}

long long minyar_net_send(long long connection, const MinyarBytes *data) {
    long long sent = 0;
    while (sent < data->byte_length) {
        long long count = (long long)send((socket_t)connection, (const char *)data->bytes + sent,
                                          (size_t)(data->byte_length - sent), 0);
        if (count <= 0) {
            remember("send", strerror(errno));
            break;
        }
        sent += count;
    }
    return sent;
}

MinyarBytes *minyar_net_receive(long long connection, long long limit) {
    MinyarBytes *result = minyar_bytes_new(0);
    if (limit <= 0) return result;
    unsigned char *buffer = malloc((size_t)limit);
    if (!buffer) minyar_native_stop("the computer ran out of memory.");
    long long count = (long long)recv((socket_t)connection, (char *)buffer, (size_t)limit, 0);
    if (count < 0) remember("receive", strerror(errno));
    if (count > 0) memcpy(minyar_bytes_extend(result, count), buffer, (size_t)count);
    free(buffer);
    return result;
}

bool minyar_net_ready(long long connection, long long milliseconds) {
#ifdef _WIN32
    fd_set set;
    FD_ZERO(&set);
    FD_SET((socket_t)connection, &set);
    struct timeval wait = {(long)(milliseconds / 1000), (long)(milliseconds % 1000) * 1000};
    return select(0, &set, NULL, NULL, &wait) > 0;
#else
    struct pollfd entry = {(int)connection, POLLIN, 0};
    return poll(&entry, 1, (int)milliseconds) > 0;
#endif
}

void minyar_net_close(long long connection) {
    close_socket((socket_t)connection);
}

MinyarText *minyar_net_lastError(void) {
    return minyar_native_copy_text((const unsigned char *)last_error, (long long)strlen(last_error));
}
