/* Real kernel oracle: raw POSIX peers never call the runtime's sender,
 * receiver or batch encoder. Including net.c also permits hostile ancillary
 * fixtures that an unprivileged UDP peer cannot synthesize. */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE 1
#endif
#if defined(__linux__) && !defined(MINYAR_DISABLE_UDP_OFFLOAD)
#include <sys/socket.h>
static ssize_t oracle_recvmsg(int, struct msghdr *, int);
static ssize_t oracle_sendmsg(int, const struct msghdr *, int);
#define recvmsg oracle_recvmsg
#define sendmsg oracle_sendmsg
#endif
#include "../runtime/native/net.c"
#if defined(__linux__) && !defined(MINYAR_DISABLE_UDP_OFFLOAD)
#undef recvmsg
#undef sendmsg
#endif
#include <assert.h>
#ifdef __linux__
#include <netinet/udp.h>
#include <sys/time.h>
#endif
void minyar_rc_release(void *);
static uint32_t u32(const MinyarBytes *b, size_t at) {
    assert(at + 4 <= (size_t)b->byte_length);
    return (uint32_t)b->bytes[at] | (uint32_t)b->bytes[at + 1] << 8 |
           (uint32_t)b->bytes[at + 2] << 16 | (uint32_t)b->bytes[at + 3] << 24;
}
static long long value(const MinyarBytes *b) {
    uint64_t n = 0;
    for (unsigned i = 0; i < 8; i++)
        n |= (uint64_t)b->bytes[8 + i] << (8 * i);
    return (long long)n;
}
#if defined(__linux__) && !defined(MINYAR_DISABLE_UDP_OFFLOAD)
static unsigned send_fixture, send_calls;
static int raw_udp(struct sockaddr_in *address) {
    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    assert(fd >= 0);
    *address =
        (struct sockaddr_in){.sin_family = AF_INET, .sin_addr.s_addr = htonl(INADDR_LOOPBACK)};
    assert(!bind(fd, (struct sockaddr *)address, sizeof(*address)));
    socklen_t n = sizeof(*address);
    assert(!getsockname(fd, (struct sockaddr *)address, &n));
    struct timeval timeout = {1, 0};
    assert(!setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)));
    return fd;
}
static void raw_segment(int fd, const struct sockaddr_in *destination, const unsigned char *bytes,
                        size_t n, uint16_t segment) {
    union {
        struct cmsghdr align;
        unsigned char bytes[CMSG_SPACE(sizeof(uint16_t))];
    } control = {0};
    struct iovec iov = {(void *)bytes, n};
    struct msghdr message = {0};
    message.msg_name = (void *)destination;
    message.msg_namelen = sizeof(*destination);
    message.msg_iov = &iov;
    message.msg_iovlen = 1;
    message.msg_control = control.bytes;
    message.msg_controllen = sizeof(control.bytes);
    struct cmsghdr *c = CMSG_FIRSTHDR(&message);
    c->cmsg_level = IPPROTO_UDP;
    c->cmsg_type = UDP_SEGMENT;
    c->cmsg_len = CMSG_LEN(sizeof(segment));
    memcpy(CMSG_DATA(c), &segment, sizeof(segment));
    assert(sendmsg(fd, &message, 0) == (ssize_t)n);
}
static size_t packet(const MinyarBytes *b, size_t at, const unsigned char *want, unsigned length,
                     unsigned status, unsigned port) {
    assert(u32(b, at) == length && u32(b, at + 4) == status);
    assert(u32(b, at + 8) == port && u32(b, at + 12) == 9);
    assert(!memcmp(b->bytes + at + 16, "127.0.0.1", 9));
    if (length)
        assert(!memcmp(b->bytes + at + 25, want, length));
    return at + 25 + length;
}
static void send_oracle(void) {
    MinyarText host = {(const unsigned char *)"127.0.0.1", 9, 0, NULL, NULL};
    struct sockaddr_in address;
    int peer = raw_udp(&address);
    long long sender = minyar_net_udp(&host, 0);
    assert(sender >= 0 && minyar_net_udpConnect(sender, &host, ntohs(address.sin_port)));
    unsigned char payload[65508];
    uint32_t seed = 0x59d31;
    for (size_t i = 0; i < sizeof(payload); i++) {
        seed ^= seed << 13;
        seed ^= seed >> 17;
        seed ^= seed << 5;
        payload[i] = (unsigned char)seed;
    }
    /* Different segment sizes/counts, a short tail and a real empty packet. */
    const unsigned sizes[] = {1, 7, 257, 1023};
    const unsigned counts[] = {1, 2, 7, 64};
    unsigned runs = 0;
    for (unsigned s = 0; s < 4; s++)
        for (unsigned c = 0; c < 4; c++) {
            unsigned length = sizes[s] * counts[c];
            if (length > 65507)
                continue;
            if (counts[c] > 1)
                length -= sizes[s] > 1 ? sizes[s] / 2 : 0;
            MinyarBytes data = {payload, length, 0, NULL, NULL};
            MinyarBytes *r = minyar_net_sendOffloadResult(sender, &data, sizes[s]);
            assert(u32(r, 0) == NET_OK && u32(r, 8) == counts[c]);
            minyar_rc_release(r);
            unsigned at = 0;
            for (unsigned i = 0; i < counts[c]; i++) {
                unsigned char got[65535];
                ssize_t n = recv(peer, got, sizeof(got), 0);
                unsigned expected = length - at < sizes[s] ? length - at : sizes[s];
                assert(n == expected && !memcmp(got, payload + at, expected));
                at += expected;
            }
            assert(recv(peer, payload + 65507, 1, MSG_DONTWAIT) < 0 && would_block(errno));
            runs++;
        }
    for (unsigned sample = 0; sample < 128; sample++) {
        seed ^= seed << 13;
        seed ^= seed >> 17;
        seed ^= seed << 5;
        unsigned segment = 1 + seed % 1000, count = 1 + (seed >> 12) % 64;
        unsigned length = segment * (count - 1) + 1 + (seed >> 24) % segment;
        MinyarBytes data = {payload, length, 0, NULL, NULL};
        MinyarBytes *random = minyar_net_sendOffloadResult(sender, &data, segment);
        assert(u32(random, 0) == NET_OK && u32(random, 8) == count);
        minyar_rc_release(random);
        unsigned offset = 0;
        for (unsigned i = 0; i < count; i++) {
            unsigned char bytes[1024];
            unsigned part = length - offset < segment ? length - offset : segment;
            assert(recv(peer, bytes, sizeof(bytes), 0) == part &&
                   !memcmp(bytes, payload + offset, part));
            offset += part;
        }
        assert(offset == length);
        runs++;
    }
    MinyarBytes small = {payload, 3, 0, NULL, NULL};
    MinyarBytes *single = minyar_net_sendOffloadResult(sender, &small, 65507);
    assert(u32(single, 0) == NET_OK && u32(single, 8) == 1);
    minyar_rc_release(single);
    unsigned char small_got[8];
    assert(recv(peer, small_got, sizeof(small_got), 0) == 3 && !memcmp(small_got, payload, 3));
    MinyarBytes empty = {NULL, 0, 0, NULL, NULL};
    MinyarBytes *r = minyar_net_sendOffloadResult(sender, &empty, 1200);
    assert(u32(r, 0) == NET_OK && u32(r, 8) == 1);
    minyar_rc_release(r);
    unsigned char got;
    assert(recv(peer, &got, 1, 0) == 0);
    const long long bad_sizes[] = {-1, 0, 65508, LLONG_MAX};
    MinyarBytes one = {payload, 1, 0, NULL, NULL};
    for (unsigned i = 0; i < 4; i++) {
        r = minyar_net_sendOffloadResult(sender, &one, bad_sizes[i]);
        assert(u32(r, 0) == NET_FAILURE);
        minyar_rc_release(r);
    }
    MinyarBytes bad[] = {{payload, 65, 0, NULL, NULL},
                         {payload, 65508, 0, NULL, NULL},
                         {payload, -1, 0, NULL, NULL},
                         {payload, LLONG_MAX, 0, NULL, NULL}};
    for (unsigned i = 0; i < 4; i++) {
        r = minyar_net_sendOffloadResult(sender, &bad[i], 1);
        assert(u32(r, 0) == NET_FAILURE);
        minyar_rc_release(r);
    }
    int tcp = socket(AF_INET, SOCK_STREAM, 0);
    assert(tcp >= 0);
    r = minyar_net_sendOffloadResult(tcp, &one, 1);
    assert(u32(r, 0) == NET_FAILURE);
    minyar_rc_release(r);
    close(tcp);
    assert(recv(peer, &got, 1, MSG_DONTWAIT) < 0 && would_block(errno));
    struct sockaddr_in other_address;
    int other = raw_udp(&other_address);
    MinyarBytes triple = {payload, 9, 0, NULL, NULL};
    r = minyar_net_sendOffloadToResult(sender, &host, ntohs(other_address.sin_port), &triple, 3);
    assert(u32(r, 0) == NET_OK && u32(r, 8) == 3);
    minyar_rc_release(r);
    for (unsigned i = 0; i < 3; i++) {
        unsigned char actual[32];
        assert(recv(other, actual, sizeof(actual), 0) == 3 && !memcmp(actual, payload + i * 3, 3));
    }
    const char *invalid_hosts[] = {"localhost", "", "127.0.0.1.invalid", "[::1]", "127.0.0.1\n"};
    for (unsigned i = 0; i < sizeof(invalid_hosts) / sizeof(*invalid_hosts); i++) {
        MinyarText bad = {(const unsigned char *)invalid_hosts[i],
                          (long long)strlen(invalid_hosts[i]), 0, NULL, NULL};
        r = minyar_net_sendOffloadToResult(sender, &bad, ntohs(other_address.sin_port), &triple, 3);
        assert(u32(r, 0) == NET_FAILURE);
        minyar_rc_release(r);
    }
    assert(recv(other, &got, 1, MSG_DONTWAIT) < 0 && would_block(errno));
    close(other);
    /* The provider accepts arbitrary counts, so an invalid request must
     * be rejected in userspace even on kernels allowing >64 segments. */
    send_fixture = 1;
    send_calls = 0;
    MinyarBytes sixty_five = {payload, 65, 0, NULL, NULL};
    r = minyar_net_sendOffloadResult(sender, &sixty_five, 1);
    assert(u32(r, 0) == NET_FAILURE && send_calls == 0);
    minyar_rc_release(r);
    r = minyar_net_sendOffloadResult(sender, &one, 0);
    assert(u32(r, 0) == NET_FAILURE && send_calls == 0);
    minyar_rc_release(r);
    r = minyar_net_sendOffloadResult(sender, &small, 1);
    assert(u32(r, 0) == NET_OK && u32(r, 8) == 3 && send_calls == 1);
    minyar_rc_release(r);
    send_fixture = 0;
    minyar_net_close(sender);
    close(peer);
    printf("kernel UDP_SEGMENT raw-peer oracle: %u shapes plus empty and guards\n", runs);
}
static void recv_oracle(void) {
    MinyarText host = {(const unsigned char *)"127.0.0.1", 9, 0, NULL, NULL};
    MinyarBytes *r = minyar_net_offloadOpenResult(&host, 0);
    assert(u32(r, 0) == NET_OK);
    long long id = value(r);
    assert(id < -1);
    minyar_rc_release(r);
    NetUdpOffload *slot = udp_offload_find(id);
    assert(slot);
    int enabled = 0;
    socklen_t size = sizeof(enabled);
    assert(!getsockopt(slot->socket, IPPROTO_UDP, UDP_GRO, &enabled, &size) && enabled == 1);
    struct sockaddr_in source,
        destination = {.sin_family = AF_INET, .sin_addr.s_addr = htonl(INADDR_LOOPBACK)};
    int peer = raw_udp(&source);
    r = minyar_net_offloadPortResult(id);
    assert(u32(r, 0) == NET_OK);
    destination.sin_port = htons((unsigned short)value(r));
    minyar_rc_release(r);
    unsigned char payload[64000];
    for (unsigned i = 0; i < sizeof(payload); i++)
        payload[i] = (unsigned char)(i * 31 + i / 997);
    raw_segment(peer, &destination, payload, 63017, 1000);
    assert(minyar_net_ready(slot->socket, 1000));
    /* Prove real kernel aggregation before the runtime consumes the queue. */
    unsigned char peek[65535];
    union {
        struct cmsghdr align;
        unsigned char bytes[128];
    } control = {0};
    struct iovec iov = {peek, sizeof(peek)};
    struct msghdr message = {0};
    message.msg_iov = &iov;
    message.msg_iovlen = 1;
    message.msg_control = control.bytes;
    message.msg_controllen = sizeof(control.bytes);
    assert(recvmsg(slot->socket, &message, MSG_PEEK) == 63017);
    bool gro = false;
    for (struct cmsghdr *c = CMSG_FIRSTHDR(&message); c; c = CMSG_NXTHDR(&message, c)) {
        if (c->cmsg_level == IPPROTO_UDP && c->cmsg_type == UDP_GRO) {
            int segment = 0;
            assert(c->cmsg_len == CMSG_LEN(sizeof(segment)));
            memcpy(&segment, CMSG_DATA(c), sizeof(segment));
            assert(segment == 1000);
            gro = true;
        }
    }
    assert(gro && !(message.msg_flags & (MSG_CTRUNC | MSG_TRUNC)));
    unsigned consumed = 0, offset = 0;
    while (consumed < 64) {
        r = minyar_net_offloadReceiveResult(id, 3, 511);
        assert(u32(r, 0) == NET_OK && u32(r, 8) > 0 && u32(r, 8) <= 3);
        size_t at = 12;
        for (unsigned i = 0; i < u32(r, 8); i++) {
            unsigned full = consumed == 63 ? 17 : 1000;
            unsigned prefix = full < 511 ? full : 511;
            at = packet(r, at, payload + offset, prefix, full > 511 ? NET_TRUNCATED : NET_OK,
                        ntohs(source.sin_port));
            consumed++;
            offset += full;
        }
        assert(at == (size_t)r->byte_length);
        minyar_rc_release(r);
        r = minyar_net_offloadReadyResult(id, 0);
        assert(u32(r, 0) == NET_OK && value(r) == (consumed < 64));
        minyar_rc_release(r);
    }
    assert(offset == 63017);
    r = minyar_net_offloadReceiveResult(id, 64, 65507);
    assert(u32(r, 0) == NET_WOULD_BLOCK && u32(r, 8) == 0);
    minyar_rc_release(r);
    assert(sendto(peer, "", 0, 0, (struct sockaddr *)&destination, sizeof(destination)) == 0);
    assert(minyar_net_ready(slot->socket, 1000));
    r = minyar_net_offloadReceiveResult(id, 1, 1);
    assert(u32(r, 0) == NET_OK && u32(r, 8) == 1);
    assert(packet(r, 12, NULL, 0, NET_OK, ntohs(source.sin_port)) == (size_t)r->byte_length);
    minyar_rc_release(r);
    /* Opaque IDs cannot pass through ordinary reads, writes or closes. */
    r = minyar_net_readResult(id, 1024, true);
    assert(u32(r, 0) == NET_FAILURE);
    minyar_rc_release(r);
    r = minyar_net_receiveBatchResult(id, 1, 1024);
    assert(u32(r, 0) == NET_FAILURE);
    minyar_rc_release(r);
    minyar_net_close(id);
    assert(udp_offload_find(id));
    MinyarBytes *loop = minyar_net_loopCreate();
    assert(u32(loop, 0) == NET_OK);
    long long loop_id = value(loop);
    minyar_rc_release(loop);
    r = minyar_net_offloadWatchResult(loop_id, id, 1, 867);
    assert(u32(r, 0) == NET_OK);
    long long watch = value(r);
    minyar_rc_release(r);
    assert(sendto(peer, "ready", 5, 0, (struct sockaddr *)&destination, sizeof(destination)) == 5);
    r = minyar_net_loopWait(loop_id, 1000, 1);
    assert(u32(r, 0) == NET_OK && r->byte_length == 40);
    assert(u32(r, 16) == 867 && u32(r, 24) & 1);
    minyar_rc_release(r);
    r = minyar_net_offloadReceiveResult(id, 1, 20);
    assert(u32(r, 8) == 1);
    minyar_rc_release(r);
    r = minyar_net_loopRemove(loop_id, watch);
    assert(u32(r, 0) == NET_OK);
    minyar_rc_release(r);
    r = minyar_net_loopClose(loop_id);
    minyar_rc_release(r);
    MinyarBytes reply = {payload, 7, 0, NULL, NULL};
    r = minyar_net_offloadSendToResult(id, &host, ntohs(source.sin_port), &reply, 3);
    assert(u32(r, 0) == NET_OK && u32(r, 8) == 3);
    minyar_rc_release(r);
    for (unsigned i = 0; i < 3; i++) {
        unsigned char got[16];
        struct sockaddr_in from;
        socklen_t n = sizeof(from);
        unsigned length = i == 2 ? 1 : 3;
        assert(recvfrom(peer, got, sizeof(got), 0, (struct sockaddr *)&from, &n) == length);
        assert(from.sin_port == destination.sin_port && !memcmp(got, payload + i * 3, length));
    }
    r = minyar_net_offloadCloseResult(id);
    assert(u32(r, 0) == NET_OK);
    minyar_rc_release(r);
    assert(!udp_offload_find(id));
    const long long bad_maximum[] = {0, 65, LLONG_MAX};
    for (unsigned i = 0; i < 3; i++) {
        r = minyar_net_offloadReceiveResult(id, bad_maximum[i], 1);
        assert(u32(r, 0) == NET_FAILURE && u32(r, 8) == 0);
        minyar_rc_release(r);
    }
    errno = EIO;
    MinyarText invalid = {(const unsigned char *)"localhost", 9, 0, NULL, NULL};
    r = minyar_net_offloadOpenResult(&invalid, 0);
    assert(u32(r, 0) == NET_FAILURE && u32(r, 4) == EINVAL);
    minyar_rc_release(r);
    r = minyar_net_offloadOpenResult(&host, 0);
    assert(u32(r, 0) == NET_OK && value(r) != id);
    long long next = value(r);
    minyar_rc_release(r);
    r = minyar_net_offloadReceiveResult(id, 1, 1);
    assert(u32(r, 0) == NET_FAILURE);
    minyar_rc_release(r);
    r = minyar_net_offloadReceiveResult(next, 1, 65508);
    assert(u32(r, 0) == NET_FAILURE);
    minyar_rc_release(r);
    r = minyar_net_offloadCloseResult(next);
    minyar_rc_release(r);
    close(peer);
    puts("kernel UDP_GRO cmsg observed: 64 boundaries, prefixes, pending drain, empty, opaque IDs, "
         "epoll");
}
static void ipv6_oracle(void) {
    MinyarText host = {(const unsigned char *)"::1", 3, 0, NULL, NULL};
    int peer = socket(AF_INET6, SOCK_DGRAM, 0);
    assert(peer >= 0);
    struct sockaddr_in6 peer_address = {.sin6_family = AF_INET6,
                                        .sin6_addr = IN6ADDR_LOOPBACK_INIT};
    assert(!bind(peer, (struct sockaddr *)&peer_address, sizeof(peer_address)));
    socklen_t n = sizeof(peer_address);
    assert(!getsockname(peer, (struct sockaddr *)&peer_address, &n));
    struct timeval timeout = {1, 0};
    assert(!setsockopt(peer, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)));
    long long sender = minyar_net_udp(&host, 0);
    assert(sender >= 0 && minyar_net_udpConnect(sender, &host, ntohs(peer_address.sin6_port)));
    unsigned char bytes[] = "abcdefghij";
    MinyarBytes payload = {bytes, 10, 0, NULL, NULL};
    MinyarBytes *r = minyar_net_sendOffloadResult(sender, &payload, 3);
    assert(u32(r, 0) == NET_OK && u32(r, 8) == 4);
    minyar_rc_release(r);
    for (unsigned i = 0; i < 4; i++) {
        unsigned char got[16];
        unsigned length = i == 3 ? 1 : 3;
        assert(recv(peer, got, sizeof(got), 0) == length && !memcmp(got, bytes + 3 * i, length));
    }
    r = minyar_net_offloadOpenResult(&host, 0);
    assert(u32(r, 0) == NET_OK);
    long long id = value(r);
    minyar_rc_release(r);
    r = minyar_net_offloadPortResult(id);
    assert(u32(r, 0) == NET_OK);
    struct sockaddr_in6 destination = {.sin6_family = AF_INET6,
                                       .sin6_addr = IN6ADDR_LOOPBACK_INIT,
                                       .sin6_port = htons((unsigned short)value(r))};
    minyar_rc_release(r);
    union {
        struct cmsghdr alignment;
        unsigned char bytes[CMSG_SPACE(sizeof(uint16_t))];
    } control = {0};
    struct iovec iov = {bytes, 10};
    struct msghdr message = {0};
    message.msg_name = &destination;
    message.msg_namelen = sizeof(destination);
    message.msg_iov = &iov;
    message.msg_iovlen = 1;
    message.msg_control = control.bytes;
    message.msg_controllen = sizeof(control.bytes);
    struct cmsghdr *c = CMSG_FIRSTHDR(&message);
    c->cmsg_level = IPPROTO_UDP;
    c->cmsg_type = UDP_SEGMENT;
    c->cmsg_len = CMSG_LEN(sizeof(uint16_t));
    uint16_t segment = 3;
    memcpy(CMSG_DATA(c), &segment, sizeof(segment));
    assert(sendmsg(peer, &message, 0) == 10);
    assert(minyar_net_ready(udp_offload_find(id)->socket, 1000));
    r = minyar_net_offloadReceiveResult(id, 64, 65507);
    assert(u32(r, 0) == NET_OK && u32(r, 8) == 4);
    size_t offset = 12;
    for (unsigned i = 0; i < 4; i++) {
        unsigned length = i == 3 ? 1 : 3;
        assert(u32(r, offset) == length && u32(r, offset + 4) == NET_OK &&
               u32(r, offset + 8) == ntohs(peer_address.sin6_port) && u32(r, offset + 12) == 3);
        assert(!memcmp(r->bytes + offset + 16, "::1", 3));
        assert(!memcmp(r->bytes + offset + 19, bytes + 3 * i, length));
        offset += 19 + length;
    }
    assert(offset == (size_t)r->byte_length);
    minyar_rc_release(r);
    r = minyar_net_offloadSendToResult(id, &host, ntohs(peer_address.sin6_port), &payload, 3);
    assert(u32(r, 0) == NET_OK && u32(r, 8) == 4);
    minyar_rc_release(r);
    for (unsigned i = 0; i < 4; i++) {
        unsigned char got[16];
        unsigned length = i == 3 ? 1 : 3;
        struct sockaddr_in6 from;
        n = sizeof(from);
        assert(recvfrom(peer, got, sizeof(got), 0, (struct sockaddr *)&from, &n) == length);
        assert(from.sin6_port == destination.sin6_port && !memcmp(got, bytes + 3 * i, length));
    }
    r = minyar_net_offloadCloseResult(id);
    minyar_rc_release(r);
    minyar_net_close(sender);
    close(peer);
    puts("kernel IPv6 raw-peer oracle: segmented send, GRO boundaries and numeric reply source");
}
static void kernel_truncation(void) {
    struct sockaddr_in destination, source;
    int receiver = raw_udp(&destination), sender = raw_udp(&source), enabled = 1;
    assert(!setsockopt(receiver, IPPROTO_UDP, UDP_GRO, &enabled, sizeof(enabled)));
    unsigned char bytes[9000];
    for (unsigned i = 0; i < sizeof(bytes); i++)
        bytes[i] = (unsigned char)i;
    raw_segment(sender, &destination, bytes, sizeof(bytes), 1000);
    unsigned char prefix[17], control[1];
    struct iovec iov = {prefix, sizeof(prefix)};
    struct msghdr message = {0};
    message.msg_iov = &iov;
    message.msg_iovlen = 1;
    message.msg_control = control;
    message.msg_controllen = sizeof(control);
    assert(recvmsg(receiver, &message, MSG_TRUNC) == (ssize_t)sizeof(bytes));
    assert((message.msg_flags & (MSG_TRUNC | MSG_CTRUNC)) == (MSG_TRUNC | MSG_CTRUNC));
    assert(!memcmp(prefix, bytes, sizeof(prefix)));
    close(sender);
    close(receiver);
    puts("kernel MSG_TRUNC original length and MSG_CTRUNC confirmed with raw GRO peer");
}
static unsigned syscall_fixture;
static int syscall_socket;
static unsigned char fixture_payload[65535];
static ssize_t oracle_sendmsg(int socket, const struct msghdr *message, int flags) {
    if (!send_fixture)
        return sendmsg(socket, message, flags);
    send_calls++;
    assert(message->msg_iovlen == 1 && message->msg_controllen == CMSG_SPACE(sizeof(uint16_t)));
    const struct cmsghdr *control = CMSG_FIRSTHDR(message);
    assert(control && control->cmsg_level == IPPROTO_UDP && control->cmsg_type == UDP_SEGMENT &&
           control->cmsg_len == CMSG_LEN(sizeof(uint16_t)));
    return (ssize_t)message->msg_iov[0].iov_len;
}
static ssize_t oracle_recvmsg(int socket, struct msghdr *message, int flags) {
    if (!syscall_fixture || socket != syscall_socket)
        return recvmsg(socket, message, flags);
    assert((flags & (MSG_DONTWAIT | MSG_TRUNC)) == (MSG_DONTWAIT | MSG_TRUNC));
    assert(message->msg_iovlen == 1 && message->msg_iov[0].iov_len == 65535);
    struct sockaddr_in source = {
        .sin_family = AF_INET, .sin_port = htons(1357), .sin_addr.s_addr = htonl(INADDR_LOOPBACK)};
    memcpy(message->msg_name, &source, sizeof(source));
    message->msg_namelen = sizeof(source);
    message->msg_flags = 0;
    message->msg_controllen = 0;
    unsigned fixture = syscall_fixture;
    if (fixture == 1) {
        memcpy(message->msg_iov[0].iov_base, "abc", 3);
        syscall_fixture = 2;
        return 3;
    }
    int segment = fixture == 3 ? 22000 : 1000;
    struct cmsghdr *control = message->msg_control;
    control->cmsg_level = IPPROTO_UDP;
    control->cmsg_type = UDP_GRO;
    control->cmsg_len = fixture == 2 ? CMSG_LEN(sizeof(uint16_t)) : CMSG_LEN(sizeof(int));
    memcpy(CMSG_DATA(control), &segment, sizeof(segment));
    message->msg_controllen = CMSG_SPACE(sizeof(int));
    syscall_fixture = 0;
    if (fixture == 2)
        return 3;
    for (unsigned i = 0; i < sizeof(fixture_payload); i++)
        fixture_payload[i] = (unsigned char)(i * 17 + 23);
    memcpy(message->msg_iov[0].iov_base, fixture_payload, sizeof(fixture_payload));
    if (fixture == 3) {
        message->msg_flags = MSG_TRUNC;
        return 66000;
    }
    assert(fixture == 4);
    return 65000;
}
static void syscall_prefixes(void) {
    MinyarText host = {(const unsigned char *)"127.0.0.1", 9, 0, NULL, NULL};
    MinyarBytes *r = minyar_net_offloadOpenResult(&host, 0);
    assert(u32(r, 0) == NET_OK);
    long long id = value(r);
    minyar_rc_release(r);
    syscall_socket = udp_offload_find(id)->socket;
    syscall_fixture = 1;
    r = minyar_net_offloadReceiveResult(id, 64, 65507);
    assert(u32(r, 0) == NET_FAILURE && u32(r, 8) == 1);
    assert(packet(r, 12, (const unsigned char *)"abc", 3, NET_OK, 1357) == (size_t)r->byte_length);
    minyar_rc_release(r);
    syscall_fixture = 3;
    r = minyar_net_offloadReceiveResult(id, 64, 65507);
    assert(u32(r, 0) == NET_TRUNCATED && u32(r, 4) == EMSGSIZE && u32(r, 8) == 3);
    size_t at = packet(r, 12, fixture_payload, 22000, NET_OK, 1357);
    at = packet(r, at, fixture_payload + 22000, 22000, NET_OK, 1357);
    at = packet(r, at, fixture_payload + 44000, 21535, NET_TRUNCATED, 1357);
    assert(at == (size_t)r->byte_length);
    minyar_rc_release(r);
    syscall_fixture = 3;
    for (unsigned i = 0; i < 3; i++) {
        r = minyar_net_offloadReceiveResult(id, 1, 65507);
        assert(u32(r, 0) == (i < 2 ? NET_OK : NET_TRUNCATED) && u32(r, 8) == 1);
        unsigned part = i < 2 ? 22000 : 21535;
        assert(packet(r, 12, fixture_payload + i * 22000, part, i < 2 ? NET_OK : NET_TRUNCATED,
                      1357) == (size_t)r->byte_length);
        minyar_rc_release(r);
    }
    syscall_fixture = 4;
    r = minyar_net_offloadReceiveResult(id, 64, 65507);
    assert(u32(r, 0) == NET_FAILURE && u32(r, 4) == EOVERFLOW && u32(r, 8) == 0);
    minyar_rc_release(r);
    syscall_fixture = 3;
    r = minyar_net_offloadReceiveResult(id, 1, 65507);
    assert(u32(r, 8) == 1);
    minyar_rc_release(r);
    r = minyar_net_offloadCloseResult(id);
    minyar_rc_release(r);
    r = minyar_net_offloadOpenResult(&host, 0);
    assert(u32(r, 0) == NET_OK);
    long long fresh = value(r);
    minyar_rc_release(r);
    r = minyar_net_offloadReceiveResult(fresh, 1, 65507);
    assert(u32(r, 0) == NET_WOULD_BLOCK && u32(r, 8) == 0);
    minyar_rc_release(r);
    r = minyar_net_offloadCloseResult(fresh);
    minyar_rc_release(r);
    puts(
        "public receive syscall oracle: retained batch prefix, oversized GRO prefix and count cap");
}
static void controls(void) {
    union {
        struct cmsghdr align;
        unsigned char bytes[256];
    } control = {0};
    struct msghdr message = {0};
    message.msg_control = control.bytes;
    message.msg_controllen = CMSG_SPACE(sizeof(int));
    struct cmsghdr *c = (struct cmsghdr *)control.bytes;
    c->cmsg_level = IPPROTO_UDP;
    c->cmsg_type = UDP_GRO;
    c->cmsg_len = CMSG_LEN(sizeof(int));
    int n = 3;
    memcpy(CMSG_DATA(c), &n, sizeof(n));
    unsigned segment = 0;
    assert(!udp_offload_control(&message, sizeof(control.bytes), &segment) && segment == 3);
    const size_t bad_lengths[] = {
        0, 1, CMSG_LEN(0) - 1, CMSG_LEN(sizeof(int)) - 1, CMSG_LEN(sizeof(int)) + 1, SIZE_MAX};
    for (unsigned i = 0; i < 6; i++) {
        c->cmsg_len = bad_lengths[i];
        segment = 19;
        assert(udp_offload_control(&message, sizeof(control.bytes), &segment));
    }
    c->cmsg_len = CMSG_LEN(sizeof(int));
    const int bad_sizes[] = {-1, 0, 65508, INT_MAX};
    for (unsigned i = 0; i < 4; i++) {
        memcpy(CMSG_DATA(c), &bad_sizes[i], sizeof(int));
        assert(udp_offload_control(&message, sizeof(control.bytes), &segment));
    }
    memcpy(CMSG_DATA(c), &n, sizeof(n));
    message.msg_flags = MSG_CTRUNC;
    assert(udp_offload_control(&message, sizeof(control.bytes), &segment));
    message.msg_flags = 0;
    memcpy(control.bytes + CMSG_SPACE(sizeof(int)), control.bytes, CMSG_SPACE(sizeof(int)));
    message.msg_controllen *= 2;
    assert(udp_offload_control(&message, sizeof(control.bytes), &segment));
    message.msg_controllen = sizeof(control.bytes) + 1;
    assert(udp_offload_control(&message, sizeof(control.bytes), &segment));
    message.msg_control = NULL;
    message.msg_controllen = 1;
    assert(udp_offload_control(&message, sizeof(control.bytes), &segment));
    message.msg_controllen = 0;
    assert(!udp_offload_control(&message, sizeof(control.bytes), &segment) && !segment);

    c->cmsg_level = SOL_SOCKET;
    c->cmsg_type = SO_RCVBUF;
    c->cmsg_len = CMSG_LEN(sizeof(int));
    message.msg_control = control.bytes;
    message.msg_controllen = CMSG_SPACE(sizeof(int));
    assert(!udp_offload_control(&message, sizeof(control.bytes), &segment) && !segment);
    c->cmsg_level = IPPROTO_UDP;
    c->cmsg_type = UDP_GRO;
    uint32_t seed = 0x931eb;
    for (unsigned sample = 0; sample < 2048; sample++) {
        for (unsigned i = 0; i < sizeof(control.bytes); i++) {
            seed ^= seed << 13;
            seed ^= seed >> 17;
            seed ^= seed << 5;
            control.bytes[i] = (unsigned char)seed;
        }
        message.msg_controllen = sample % (sizeof(control.bytes) + 2);
        int code = udp_offload_control(&message, sizeof(control.bytes), &segment);
        assert(code == 0 || code == EINVAL || code == EMSGSIZE);
    }
    memset(control.bytes, 0, sizeof(control.bytes));
    c->cmsg_level = IPPROTO_UDP;
    c->cmsg_type = UDP_GRO;
    c->cmsg_len = CMSG_LEN(sizeof(int));
    n = 3;
    memcpy(CMSG_DATA(c), &n, sizeof(n));

    /* Valid prefix + an invalid next aggregate remains inspectable. A
     * truncated valid aggregate retains complete and incomplete prefixes. */
    NetUdpOffload state = {0};
    unsigned char data[] = {10, 11, 12, 13, 14, 15, 16, 17};
    state.storage = data;
    struct sockaddr_in source = {
        .sin_family = AF_INET, .sin_port = htons(1357), .sin_addr.s_addr = htonl(INADDR_LOOPBACK)};
    message.msg_name = &source;
    message.msg_namelen = sizeof(source);
    message.msg_control = control.bytes;
    message.msg_controllen = CMSG_SPACE(sizeof(int));
    message.msg_flags = MSG_TRUNC;
    assert(!udp_offload_ingest(&state, &message, 8, 5));
    MinyarBytes *r = minyar_bytes_new(12);
    unsigned count = 0;
    assert(udp_offload_drain(&state, r, 64, 65507, &count) == EMSGSIZE && count == 2);
    size_t at = packet(r, 12, data, 3, NET_OK, 1357);
    at = packet(r, at, data + 3, 2, NET_TRUNCATED, 1357);
    assert(at == (size_t)r->byte_length);
    minyar_rc_release(r);
    message.msg_flags = 0;
    n = 1;
    memcpy(CMSG_DATA(c), &n, sizeof(n));
    assert(udp_offload_ingest(&state, &message, 65, 65) == EOVERFLOW);
    n = 3;
    memcpy(CMSG_DATA(c), &n, sizeof(n));
    message.msg_controllen = CMSG_SPACE(sizeof(int));
    assert(!udp_offload_ingest(&state, &message, 8, 8));
    r = minyar_bytes_new(12);
    count = 0;
    assert(!udp_offload_drain(&state, r, 1, 65507, &count) && count == 1);
    size_t prefix = (size_t)r->byte_length;
    c->cmsg_len = 1;
    assert(udp_offload_ingest(&state, &message, 8, 8));
    assert((size_t)r->byte_length == prefix);
    minyar_rc_release(r);
    puts("hostile ancillary lengths, duplicates, flags, overflow and retained prefixes verified");
}
#endif
int main(void) {
#if defined(__linux__) && !defined(MINYAR_DISABLE_UDP_OFFLOAD)
    send_oracle();
    recv_oracle();
    ipv6_oracle();
    kernel_truncation();
    controls();
    syscall_prefixes();
#else
    MinyarText host = {(const unsigned char *)"127.0.0.1", 9, 0, NULL, NULL};
    MinyarBytes *r = minyar_net_offloadOpenResult(&host, 0);
    assert(u32(r, 0) == NET_UDP_UNAVAILABLE && u32(r, 4) != 0 && value(r) == -1);
    minyar_rc_release(r);
    MinyarBytes empty = {NULL, 0, 0, NULL, NULL};
    long long socket = minyar_net_udp(&host, 0);
    assert(socket >= 0);
    r = minyar_net_sendOffloadResult(socket, &empty, 1200);
    assert(u32(r, 0) == NET_UDP_UNAVAILABLE && u32(r, 4) != 0);
    minyar_rc_release(r);
    minyar_net_close(socket);
    puts("UDP offload explicitly unavailable on this OS");
#endif
    return 0;
}
