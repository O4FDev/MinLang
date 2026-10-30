// Serial C++ peer for main.min: 64 loopback connections, one event loop
// (epoll on Linux, poll elsewhere) serving "GET /item/<key>\n" requests and
// driving the clients that send them, one request in flight per connection.
#include <arpa/inet.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <array>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include <sys/socket.h>
#include <unistd.h>
#ifdef __linux__
#include <sys/epoll.h>
#else
#include <poll.h>
#endif

constexpr int CONNECTIONS = 64;
constexpr int64_t KEYS = 65536, MODULUS = 1000000007;
struct Connection { int64_t id, sent, received; int client, server, client_len, server_len; char client_in[4096], server_in[4096]; };

static int64_t mix(int64_t value) {
    for (int64_t round = 0; round < 3; ++round) {
        value ^= value >> 31;
        value = (int64_t)((uint64_t)value * 0x2545F4914F6CDD1DULL);
        value ^= value >> 29;
        value = (int64_t)((uint64_t)value + (uint64_t)round);
    }
    return value & 0x7FFFFFFFFFFFFFFFLL;
}
static int64_t number(const char *data, int length, int at) {
    int64_t value = 0;
    for (int i = at; i < length && data[i] >= '0' && data[i] <= '9'; ++i) value = value * 10 + data[i] - '0';
    return value;
}
static void send_all(int fd, const char *data, int length) {
    while (length > 0) {
        ssize_t sent = write(fd, data, (size_t)length);
        if (sent > 0) { data += sent; length -= (int)sent; }
        else if (sent < 0 && (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR)) continue;
        else { perror("write"); exit(1); }
    }
}
static void request(Connection *c) {
    char line[64];
    int n = snprintf(line, sizeof line, "GET /item/%lld\n", (long long)(mix(c->id * 1000003 + c->sent) % KEYS));
    send_all(c->client, line, n);
    c->sent++;
}
static void setup(int fd) {
    int one = 1;
    fcntl(fd, F_SETFL, fcntl(fd, F_GETFL) | O_NONBLOCK);
    setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &one, sizeof one);
}

int main(int argc, char **argv) {
    int64_t per_connection = atoll(argv[1]);
    std::vector<int64_t> table(static_cast<size_t>(KEYS));
    for (int64_t key = 0; key < KEYS; ++key) table[size_t(key)] = mix(key + 99991) % 1000000;
    int listener = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in address = {};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    socklen_t length = sizeof address;
    if (bind(listener, (struct sockaddr *)&address, sizeof address) || listen(listener, 128)) { perror("listen"); return 1; }
    getsockname(listener, (struct sockaddr *)&address, &length);
    static std::array<Connection, CONNECTIONS> connections;
#ifdef __linux__
    int loop = epoll_create1(0);
#else
    struct pollfd fds[2 * CONNECTIONS];
#endif
    for (int i = 0; i < CONNECTIONS; ++i) {
        Connection *c = &connections[i];
        c->id = i;
        c->client = socket(AF_INET, SOCK_STREAM, 0);
        if (connect(c->client, (struct sockaddr *)&address, sizeof address)) { perror("connect"); return 1; }
        c->server = accept(listener, NULL, NULL);
        setup(c->client);
        setup(c->server);
#ifdef __linux__
        struct epoll_event ev = {.events = EPOLLIN, .data.u64 = (uint64_t)(2 * i)};
        epoll_ctl(loop, EPOLL_CTL_ADD, c->client, &ev);
        ev.data.u64 = (uint64_t)(2 * i + 1);
        epoll_ctl(loop, EPOLL_CTL_ADD, c->server, &ev);
#else
        fds[2 * i] = (struct pollfd){.fd = c->client, .events = POLLIN};
        fds[2 * i + 1] = (struct pollfd){.fd = c->server, .events = POLLIN};
#endif
    }
    for (int i = 0; i < CONNECTIONS; ++i) request(&connections[i]);
    int open = CONNECTIONS;
    int64_t checksum = 0;
    while (open > 0) {
#ifdef __linux__
        struct epoll_event events[256];
        int count = epoll_wait(loop, events, 256, -1);
        if (count < 0) { if (errno == EINTR) continue; perror("epoll_wait"); return 1; }
        for (int e = 0; e < count; ++e) {
            uint64_t token = events[e].data.u64;
#else
        int ready = poll(fds, 2 * CONNECTIONS, -1);
        if (ready < 0) { if (errno == EINTR) continue; perror("poll"); return 1; }
        for (int e = 0; e < 2 * CONNECTIONS; ++e) {
            if (!(fds[e].revents & (POLLIN | POLLHUP | POLLERR))) continue;
            uint64_t token = (uint64_t)e;
#endif
            Connection *c = &connections[token / 2];
            if (token % 2 == 1) {
                ssize_t got = read(c->server, c->server_in + c->server_len, sizeof c->server_in - (size_t)c->server_len);
                if (got < 0 && errno == EAGAIN) continue;
                if (got <= 0) { perror("server read"); return 1; }
                c->server_len += (int)got;
                if (c->server_in[c->server_len - 1] == '\n') {
                    int64_t key = number(c->server_in, c->server_len, 10);
                    char line[64];
                    int n = snprintf(line, sizeof line, "OK %lld %lld\n", (long long)key, (long long)table[size_t(key)]);
                    send_all(c->server, line, n);
                    c->server_len = 0;
                }
            } else {
                ssize_t got = read(c->client, c->client_in + c->client_len, sizeof c->client_in - (size_t)c->client_len);
                if (got < 0 && errno == EAGAIN) continue;
                if (got <= 0) { perror("client read"); return 1; }
                c->client_len += (int)got;
                if (c->client_in[c->client_len - 1] == '\n') {
                    int64_t key = number(c->client_in, c->client_len, 3);
                    int digits = 3;
                    while (c->client_in[digits] != ' ') ++digits;
                    int64_t value = number(c->client_in, c->client_len, digits + 1);
                    if (key != mix(c->id * 1000003 + c->received) % KEYS) { fprintf(stderr, "wrong key\n"); return 1; }
                    checksum = (checksum + value * (c->id + 1)) % MODULUS;
                    c->received++;
                    c->client_len = 0;
                    if (c->sent < per_connection) request(c); else --open;
                }
            }
        }
    }
    for (int i = 0; i < CONNECTIONS; ++i) { close(connections[i].client); close(connections[i].server); }
    close(listener);
    printf("requests %lld\n", (long long)(CONNECTIONS * per_connection));
    printf("checksum %lld\n", (long long)checksum);
    return 0;
}
