/* Independent loopback peers exercise observable socket outcomes. Cases were
 * inspired by mio/tests/udp_socket.rs and libuv/test/test-udp-send-and-recv.c;
 * no peer source is copied. This links the real Minyar ownership runtime. */
#include "../runtime/minyar_native.h"
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stdint.h>
#ifdef _WIN32
#include <winsock2.h>
#else
#include <sys/socket.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#endif

long long minyar_net_connect(const MinyarText *, long long);
long long minyar_net_listen(const MinyarText *, long long, long long);
long long minyar_net_accept(long long);
long long minyar_net_udp(const MinyarText *, long long);
long long minyar_net_localPort(long long);
bool minyar_net_nonBlocking(long long, bool);
MinyarBytes *minyar_net_setNoDelayResult(long long, bool);
bool minyar_net_udpConnect(long long, const MinyarText *, long long);
bool minyar_net_ready(long long, long long);
MinyarBytes *minyar_net_readResult(long long, long long, bool);
MinyarBytes *minyar_net_writeResult(long long, const MinyarBytes *);
long long minyar_net_readInto(long long, MinyarBytes *, long long);
long long minyar_net_writeRange(long long, const MinyarBytes *, long long, long long);
long long minyar_net_lastErrorCode(void);
void minyar_net_close(long long);
void minyar_rc_release(void *);

static uint32_t word(const MinyarBytes *b, size_t at) {
    assert(at + 4 <= (size_t)b->byte_length);
    return (uint32_t)b->bytes[at] | (uint32_t)b->bytes[at + 1] << 8 |
           (uint32_t)b->bytes[at + 2] << 16 | (uint32_t)b->bytes[at + 3] << 24;
}

static MinyarText literal(const char *s) {
    MinyarText t = {(const unsigned char *)s, (long long)strlen(s), 0, NULL, NULL};
    return t;
}

static void expect_status(MinyarBytes *b, unsigned status) {
    assert(b->byte_length >= 8);
    assert(word(b, 0) == status);
    if (status == 0 || status == 2)
        assert(word(b, 4) == 0);
    minyar_rc_release(b);
}

static void udp_outcomes(void) {
    MinyarText host = literal("127.0.0.1");
    long long receiver = minyar_net_udp(&host, 0);
    long long sender = minyar_net_udp(&host, 0);
    assert(receiver >= 0 && sender >= 0);
    long long port = minyar_net_localPort(receiver);
    assert(port > 0 && port <= 65535);
    assert(minyar_net_udpConnect(sender, &host, port));
    expect_status(minyar_net_readResult(receiver, 1024, true), 1);

    /* A successful empty datagram is data, never TCP EOF or would-block. */
    MinyarBytes empty = literal("");
    expect_status(minyar_net_writeResult(sender, &empty), 0);
    assert(minyar_net_ready(receiver, 1000));
    MinyarBytes *zero = minyar_net_readResult(receiver, 32, true);
    assert(word(zero, 0) == 0 && zero->byte_length == 8);
    minyar_rc_release(zero);
    expect_status(minyar_net_readResult(receiver, 32, true), 1);

    /* A seeded range of payloads catches accidental packet coalescing,
     * dropped zeros, short reads, stale error state and binary corruption. */
    unsigned char storage[4096];
    for (unsigned test = 0; test < 97; test++) {
        size_t length = (test * 43) % sizeof(storage);
        for (size_t i = 0; i < length; i++)
            storage[i] = (unsigned char)(i ^ test);
        MinyarBytes payload = {storage, (long long)length, 0, NULL, NULL};
        expect_status(minyar_net_writeResult(sender, &payload), 0);
        assert(minyar_net_ready(receiver, 1000));
        MinyarBytes *read = minyar_net_readResult(receiver, sizeof(storage), true);
        assert(word(read, 0) == 0 && word(read, 4) == 0);
        assert(read->byte_length == (long long)length + 8);
        assert(!memcmp(read->bytes + 8, storage, length));
        minyar_rc_release(read);
    }

    MinyarBytes oversized = {storage, sizeof(storage), 0, NULL, NULL};
    expect_status(minyar_net_writeResult(sender, &oversized), 0);
    assert(minyar_net_ready(receiver, 1000));
    expect_status(minyar_net_readResult(receiver, 7, true), 4);
    expect_status(minyar_net_readResult(receiver, 7, true), 1);
    minyar_net_close(sender);
    minyar_net_close(receiver);
}

static void tcp_outcomes(void) {
    MinyarText host = literal("127.0.0.1");
    long long listener = minyar_net_listen(&host, 0, 16);
    assert(listener >= 0);
    assert(minyar_net_accept(listener) == -1);
    long long client = minyar_net_connect(&host, minyar_net_localPort(listener));
    assert(client >= 0);
    assert(minyar_net_ready(listener, 1000));
    long long server = minyar_net_accept(listener);
    assert(server >= 0 && minyar_net_nonBlocking(server, true));
    /* The requested low-latency policy is observable in the actual OS
     * socket. Invalid/UDP/stale handles report owned errors and never stop
     * a later TCP operation. Enabling it does not change blocking policy. */
    for (int enabled = 0; enabled < 4; enabled++) {
        expect_status(minyar_net_setNoDelayResult(server, (enabled & 1) != 0), 0);
        /* Winsock returns one byte for Boolean options. Poison the low byte
         * without leaving stale high bytes when that byte is replaced. */
        int value = 255;
#ifdef _WIN32
        int size = sizeof(value);
        assert(!getsockopt((SOCKET)server, IPPROTO_TCP, TCP_NODELAY, (char *)&value, &size));
        assert(size == 1 || size == sizeof(value));
#else
        socklen_t size = sizeof(value);
        assert(!getsockopt((int)server, IPPROTO_TCP, TCP_NODELAY, &value, &size));
        assert(size == sizeof(value));
#endif
#ifdef __APPLE__
        /* XNU exposes its TF_NODELAY bit (0x4), rather than normalized 1. */
        assert(value == ((enabled & 1) ? 4 : 0));
#else
        assert(value == (enabled & 1));
#endif
    }
    MinyarBytes *option_failure = minyar_net_setNoDelayResult(-1, true);
    assert(word(option_failure, 0) == 3 && word(option_failure, 4));
    long long datagram = minyar_net_udp(&host, 0);
    assert(datagram >= 0);
    expect_status(minyar_net_setNoDelayResult(datagram, true), 3);
    minyar_net_close(datagram);
    expect_status(minyar_net_setNoDelayResult((1LL << 32) + server, true), 3);
    expect_status(minyar_net_setNoDelayResult(client, true), 0);
    assert(word(option_failure, 0) == 3 && word(option_failure, 4));
    minyar_rc_release(option_failure);
    expect_status(minyar_net_readResult(server, 64, false), 1);
    MinyarBytes packet = literal("hello\xff");
    expect_status(minyar_net_writeResult(client, &packet), 0);
    assert(minyar_net_ready(server, 1000));
    MinyarBytes *reply = minyar_net_readResult(server, 64, false);
    assert(word(reply, 0) == 0 && reply->byte_length == packet.byte_length + 8);
    assert(!memcmp(reply->bytes + 8, packet.bytes, (size_t)packet.byte_length));
    minyar_rc_release(reply);
    minyar_net_close(client);
    assert(minyar_net_ready(server, 1000));
    expect_status(minyar_net_readResult(server, 64, false), 2);
    minyar_net_close(server);
    expect_status(minyar_net_setNoDelayResult(server, true), 3);
    minyar_net_close(listener);
}

static void failures_are_values(void) {
    MinyarText host = literal("127.0.0.1");
    assert(minyar_net_connect(&host, -1) == -1);
    assert(minyar_net_udp(&host, 65536) == -1);
    MinyarText embedded = literal("127.0.0.1\0other");
    embedded.byte_length = 15;
    assert(minyar_net_udp(&embedded, 0) == -1);
    MinyarBytes *failure = minyar_net_readResult(-1, 100, false);
    assert(word(failure, 0) == 3 && word(failure, 4) != 0);
    expect_status(minyar_net_readResult(-1, LLONG_MAX, false), 3);
    expect_status(minyar_net_readResult(-1, 0, false), 3);
    /* A later operation must not mutate an earlier operation's error. */
    long long udp = minyar_net_udp(&host, 0);
    assert(udp >= 0);
    /* An out-of-range Integer must not wrap to a live native descriptor. */
    long long wrapped = (1LL << 32) + udp;
    expect_status(minyar_net_readResult(wrapped, 16, true), 3);
    assert(!minyar_net_nonBlocking(wrapped, true));
    minyar_net_close(wrapped);
    assert(minyar_net_localPort(udp) > 0);
    expect_status(minyar_net_readResult(udp, 16, true), 1);
    assert(word(failure, 0) == 3 && word(failure, 4) != 0);
    minyar_rc_release(failure);
    minyar_net_close(udp);
}

#ifndef _WIN32
static void reuse_address_boolean_contract(void) {
    int raw = socket(AF_INET, SOCK_STREAM, 0);
    assert(raw >= 0);
    int value = -1;
    socklen_t size = sizeof(value);
    assert(!getsockopt(raw, SOL_SOCKET, SO_REUSEADDR, &value, &size));
    assert(size == sizeof(value) && value == 0);
    int enabled = 1;
    assert(!setsockopt(raw, SOL_SOCKET, SO_REUSEADDR, &enabled, sizeof(enabled)));
    size = sizeof(value);
    assert(!getsockopt(raw, SOL_SOCKET, SO_REUSEADDR, &value, &size));
    assert(size == sizeof(value) && value != 0);
    int disabled = 0;
    assert(!setsockopt(raw, SOL_SOCKET, SO_REUSEADDR, &disabled, sizeof(disabled)));
    size = sizeof(value);
    assert(!getsockopt(raw, SOL_SOCKET, SO_REUSEADDR, &value, &size));
    assert(size == sizeof(value) && value == 0);
    minyar_net_close(raw);
}
#endif

static void reusable_stream_buffers(void) {
    MinyarText host = literal("127.0.0.1");
    long long listener = minyar_net_listen(&host, 0, 16);
    assert(listener >= 0);
    long long port = minyar_net_localPort(listener);
#ifndef _WIN32
    int reuse = 0;
    socklen_t size = sizeof(reuse);
    assert(!getsockopt((int)listener, SOL_SOCKET, SO_REUSEADDR, &reuse, &size));
    assert(size == sizeof(reuse));
    int disabled = 0;
    assert(!setsockopt((int)listener, SOL_SOCKET, SO_REUSEADDR, &disabled, sizeof(disabled)));
    int off = -1;
    size = sizeof(off);
    assert(!getsockopt((int)listener, SOL_SOCKET, SO_REUSEADDR, &off, &size));
    assert(size == sizeof(off) && off == 0);
    int enabled = 1;
    assert(!setsockopt((int)listener, SOL_SOCKET, SO_REUSEADDR, &enabled, sizeof(enabled)));
    int restored = 0;
    size = sizeof(restored);
    assert(!getsockopt((int)listener, SOL_SOCKET, SO_REUSEADDR, &restored, &size));
    assert(size == sizeof(restored) && restored != 0);
    /* Boolean socket options report zero or a platform-specific nonzero bit. */
    assert(reuse != 0);
#endif
    long long client = minyar_net_connect(&host, port);
    assert(client >= 0 && minyar_net_ready(listener, 1000));
    long long server = minyar_net_accept(listener);
    assert(server >= 0 && minyar_net_nonBlocking(server, true));
    MinyarBytes message = literal("xxhello worldyy");
    MinyarBytes *buffer = minyar_bytes_new(256);
    buffer->byte_length = 1;
    ((unsigned char *)buffer->bytes)[0] = 42;
    const unsigned char *storage = buffer->bytes;
    long long capacity = buffer->character_length;
    assert(minyar_net_readInto(server, buffer, 64) == -1);
    assert(buffer->byte_length == 1 && minyar_net_lastErrorCode() == 0);
    assert(minyar_net_writeRange(client, &message, 2, 11) == 11);
    while (buffer->byte_length < 12) {
        assert(minyar_net_ready(server, 1000));
        assert(minyar_net_readInto(server, buffer, 64) > 0);
    }
    assert(buffer->bytes == storage && buffer->character_length == capacity);
    assert(buffer->byte_length == 12 && buffer->bytes[0] == 42);
    assert(!memcmp(buffer->bytes + 1, "hello world", 11));
    assert(minyar_net_writeRange(client, &message, 10, 100) == -2);
#ifdef _WIN32
    assert(minyar_net_lastErrorCode() == -WSAEINVAL);
#else
    assert(minyar_net_lastErrorCode() == -EINVAL);
#endif
    assert(minyar_net_writeRange(client, &message, 0, 0) == 0);
    assert(minyar_net_lastErrorCode() == 0);
    assert(minyar_net_readInto(-1, buffer, 64) == -2);
    assert(buffer->byte_length == 12 && buffer->bytes == storage);
    minyar_net_close(server);
    assert(minyar_net_ready(client, 1000));
    assert(minyar_net_readInto(client, buffer, 64) == 0);
    assert(buffer->byte_length == 12 && minyar_net_lastErrorCode() == 0);
    minyar_rc_release(buffer);
    minyar_net_close(client);
    minyar_net_close(listener);
#ifndef _WIN32
    /* Reading the server FIN before client close establishes server-side
     * TIME_WAIT, rather than merely closing both sockets simultaneously. */
    listener = minyar_net_listen(&host, port, 16);
    assert(listener >= 0);
    minyar_net_close(listener);
#endif
}

int main(void) {
#ifndef _WIN32
    reuse_address_boolean_contract();
#endif
    failures_are_values();
    udp_outcomes();
    tcp_outcomes();
    reusable_stream_buffers();
    puts("native network outcomes verified");
    return 0;
}
