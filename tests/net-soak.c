/* Sustained real sockets, owned results and bounded registry reuse. The Python
 * driver records OS RSS independently; no per-sample process restart. */
#include "../runtime/native/net.c"
#include <assert.h>
#include <time.h>
#ifndef _WIN32
#include <sys/resource.h>
#endif
extern void minyar_rc_release(void *);
typedef struct {
    long long client, server, registration;
} SoakPeer;
static uint32_t word(const MinyarBytes *b, size_t at) {
    assert(at + 4 <= (size_t)b->byte_length);
    return batch_u32(b->bytes + at);
}
static long long value(MinyarBytes *b) {
    assert(b->byte_length == 16 && word(b, 0) == NET_OK);
    uint64_t n = word(b, 8) | (uint64_t)word(b, 12) << 32;
    minyar_rc_release(b);
    return (long long)n;
}
static MinyarText literal(const char *s) {
    return (MinyarText){(const unsigned char *)s, (long long)strlen(s), 0, NULL, NULL};
}
static void open_peer(SoakPeer *peer, long long listener, const MinyarText *host, long long port,
                      long long loop, long long token) {
    peer->client = minyar_net_connect(host, port);
    assert(peer->client >= 0);
    for (unsigned retry = 0;; retry++) {
        peer->server = minyar_net_accept(listener);
        if (peer->server >= 0)
            break;
        assert(retry < 10 && minyar_net_ready(listener, 1000));
    }
    assert(minyar_net_nonBlocking(peer->client, true));
    peer->registration = value(minyar_net_loopWatch(loop, peer->server, 1, token));
}
static void close_peer(SoakPeer *peer, long long loop) {
    assert(value(minyar_net_loopRemove(loop, peer->registration)) == 1);
    minyar_net_close(peer->server);
    minyar_net_close(peer->client);
}
int main(int argc, char **argv) {
    assert(argc == 3);
    unsigned seconds = (unsigned)strtoul(argv[1], NULL, 10),
             count = (unsigned)strtoul(argv[2], NULL, 10);
    assert(seconds >= 1 && seconds <= 86400 && count >= 1 && count <= 10000);
#ifndef _WIN32
    struct rlimit files;
    assert(!getrlimit(RLIMIT_NOFILE, &files));
    if (files.rlim_cur < (rlim_t)(count * 2 + 1024)) {
        files.rlim_cur = count * 2 + 1024;
        assert(!setrlimit(RLIMIT_NOFILE, &files));
    }
#endif
    MinyarText host = literal("127.0.0.1");
    long long loop = value(minyar_net_loopCreate()), listener = minyar_net_listen(&host, 0, 128);
    assert(listener >= 0);
    long long port = minyar_net_localPort(listener);
    SoakPeer *peers = calloc(count, sizeof(*peers));
    assert(peers);
    for (unsigned i = 0; i < count; i++)
        open_peer(&peers[i], listener, &host, port, loop, i);
    long long udp = minyar_net_udp(&host, 0), sender = minyar_net_udp(&host, 0);
    assert(udp >= 0 && sender >= 0);
    long long udp_watch = value(minyar_net_loopWatch(loop, udp, 1, -2));
    assert(minyar_net_udpConnect(sender, &host, minyar_net_localPort(udp)));
    long long timer = value(minyar_net_loopTimer(loop, 1000, 1000, -1));
    uint64_t start = net_loop_now();
    clock_t cpu_start = clock();
    unsigned rounds = 0;
    uint64_t bytes = 0;
    printf("{\"phase\":\"ready\",\"connections\":%u,\"sockets\":%u}\n", count, count * 2 + 3);
    fflush(stdout);
    while (net_loop_now() - start < (uint64_t)seconds * 1000) {
        MinyarBytes *events = minyar_net_loopWait(loop, 1000, 128);
        assert(word(events, 0) == NET_OK);
        for (long long at = 8; at < events->byte_length; at += 32) {
            long long token = (long long)(word(events, (size_t)at + 8) |
                                          (uint64_t)word(events, (size_t)at + 12) << 32);
            if (token >= 0) {
                MinyarBytes *read = minyar_net_readResult(peers[token].server, 65536, false);
                assert(word(read, 0) == NET_OK || word(read, 0) == NET_WOULD_BLOCK);
                if (word(read, 0) == NET_OK)
                    bytes += (uint64_t)read->byte_length - 8;
                minyar_rc_release(read);
            } else if (token == -2) {
                MinyarBytes *packets = minyar_net_receiveBatchResult(udp, 64, 4096);
                assert(word(packets, 0) == NET_OK || word(packets, 0) == NET_WOULD_BLOCK);
                minyar_rc_release(packets);
            } else if (token == -1) {
                rounds++;
                unsigned char payload[17] = {0};
                payload[0] = (unsigned char)rounds;
                MinyarBytes heartbeat = {payload, sizeof(payload), 0, NULL, NULL};
                for (unsigned i = 0; rounds % 15 == 0 && i < count; i++) {
                    MinyarBytes *sent = minyar_net_writeResult(peers[i].client, &heartbeat);
                    assert(word(sent, 0) == NET_OK && word(sent, 8) == sizeof(payload));
                    minyar_rc_release(sent);
                }
                /* Dropped/reordered input: send only odd sequence values,
                 * backwards. Periodically force truncation without a crash. */
                for (int seq = 15; seq >= 1; seq -= 2) {
                    payload[1] = (unsigned char)seq;
                    MinyarBytes *sent = minyar_net_writeResult(sender, &heartbeat);
                    assert(word(sent, 0) == NET_OK);
                    minyar_rc_release(sent);
                }
                if (rounds % 7 == 0) {
                    unsigned char huge[8192] = {0};
                    MinyarBytes packet = {huge, sizeof(huge), 0, NULL, NULL};
                    MinyarBytes *sent = minyar_net_writeResult(sender, &packet);
                    assert(word(sent, 0) == NET_OK);
                    minyar_rc_release(sent);
                }
                /* A half-close is an EOF outcome, then replace the peer and
                 * registration in bounded storage while other peers stay live. */
                unsigned chosen = rounds % count;
                assert(value(minyar_net_loopRemove(loop, peers[chosen].registration)) == 1);
                assert(!shutdown((socket_t)peers[chosen].client, 1));
                for (;;) {
                    MinyarBytes *read = minyar_net_readResult(peers[chosen].server, 65536, false);
                    unsigned status = word(read, 0);
                    minyar_rc_release(read);
                    if (status == NET_EOF)
                        break;
                    assert(status == NET_OK || status == NET_WOULD_BLOCK);
                    if (status == NET_WOULD_BLOCK)
                        assert(minyar_net_ready(peers[chosen].server, 1000));
                }
                minyar_net_close(peers[chosen].server);
                minyar_net_close(peers[chosen].client);
                open_peer(&peers[chosen], listener, &host, port, loop, chosen);
                NetLoop *state = net_loop_find(loop);
                assert(state->entry_count <= count + 2 && state->timer_count == 1);
                printf("{\"phase\":\"sample\",\"elapsed_ms\":%llu,\"cpu_seconds\":%.6f,\"rounds\":%"
                       "u,\"bytes\":%llu,\"registry_slots\":%zu}\n",
                       (unsigned long long)(net_loop_now() - start),
                       (double)(clock() - cpu_start) / CLOCKS_PER_SEC, rounds,
                       (unsigned long long)bytes, state->entry_count);
                fflush(stdout);
            }
        }
        minyar_rc_release(events);
    }
    for (unsigned i = 0; i < count; i++)
        close_peer(&peers[i], loop);
    free(peers);
    assert(value(minyar_net_loopRemove(loop, udp_watch)) == 1);
    assert(value(minyar_net_loopRemove(loop, timer)) == 1);
    assert(value(minyar_net_loopClose(loop)) == 1);
    minyar_net_close(udp);
    minyar_net_close(sender);
    minyar_net_close(listener);
    puts("{\"phase\":\"complete\"}");
    return 0;
}
