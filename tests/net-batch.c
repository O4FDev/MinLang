/* Datagram batches retain packet boundaries and reject malformed input
 * before transmitting anything. Inspired by libuv's UDP and sendmmsg tests;
 * no upstream code copied. Links the production runtime and OS sockets. */
#include "../runtime/minyar_native.h"
#include <assert.h>
#include <stdint.h>

long long minyar_net_udp(const MinyarText *, long long);
long long minyar_net_localPort(long long);
bool minyar_net_udpConnect(long long, const MinyarText *, long long);
bool minyar_net_ready(long long, long long);
MinyarBytes *minyar_net_sendBatchResult(long long, const MinyarBytes *);
MinyarBytes *minyar_net_receiveBatchResult(long long, long long, long long);
void minyar_net_close(long long);
void minyar_rc_release(void *);

static uint32_t read32(const MinyarBytes *b, size_t at) {
    assert(at + 4 <= (size_t)b->byte_length);
    return (uint32_t)b->bytes[at] | (uint32_t)b->bytes[at + 1] << 8 |
           (uint32_t)b->bytes[at + 2] << 16 | (uint32_t)b->bytes[at + 3] << 24;
}
static void append32(MinyarBytes *b, uint32_t value) {
    unsigned char *p = minyar_bytes_extend(b, 4);
    for (unsigned i = 0; i < 4; i++)
        p[i] = (unsigned char)(value >> (8 * i));
}

int main(void) {
    MinyarText host = {(const unsigned char *)"127.0.0.1", 9, 0, NULL, NULL};
    long long receiver = minyar_net_udp(&host, 0), sender = minyar_net_udp(&host, 0);
    assert(receiver >= 0 && sender >= 0);
    long long sender_port = minyar_net_localPort(sender);
    assert(minyar_net_udpConnect(sender, &host, minyar_net_localPort(receiver)));
    MinyarBytes *packets = minyar_bytes_new(0);
    append32(packets, 64);
    for (unsigned packet = 0; packet < 64; packet++) {
        unsigned length = packet * 13;
        append32(packets, length);
        unsigned char *p = minyar_bytes_extend(packets, length);
        for (unsigned i = 0; i < length; i++)
            p[i] = (unsigned char)(packet + i);
    }
    MinyarBytes *sent = minyar_net_sendBatchResult(sender, packets);
    assert(read32(sent, 0) == 0 && read32(sent, 8) == 64);
    minyar_rc_release(sent);
    minyar_rc_release(packets);
    unsigned received = 0;
    while (received < 64) {
        assert(minyar_net_ready(receiver, 1000));
        MinyarBytes *batch = minyar_net_receiveBatchResult(receiver, 7, 2048);
        assert(read32(batch, 0) == 0 && read32(batch, 8) > 0 && read32(batch, 8) <= 7);
        size_t at = 12;
        for (unsigned packet = 0; packet < read32(batch, 8); packet++) {
            unsigned length = read32(batch, at), status = read32(batch, at + 4);
            unsigned port = read32(batch, at + 8), name_length = read32(batch, at + 12);
            assert(status == 0 && port == (unsigned)sender_port && name_length == 9);
            assert(length == received * 13 && !memcmp(batch->bytes + at + 16, host.bytes, 9));
            const unsigned char *p = batch->bytes + at + 16 + name_length;
            for (unsigned i = 0; i < length; i++)
                assert(p[i] == (unsigned char)(received + i));
            at += 16 + name_length + length;
            received++;
        }
        assert(at == (size_t)batch->byte_length);
        minyar_rc_release(batch);
    }
    MinyarBytes *pending = minyar_net_receiveBatchResult(receiver, 7, 2048);
    assert(read32(pending, 0) == 1 && pending->byte_length == 12);
    minyar_rc_release(pending);

    /* Every truncated encoding, absurd count and length, and trailing bytes
     * must fail without committing the valid first packet. */
    unsigned char valid[] = {2, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 42};
    for (size_t length = 0; length < sizeof(valid); length++) {
        MinyarBytes malformed = {valid, (long long)length, 0, NULL, NULL};
        MinyarBytes *failed = minyar_net_sendBatchResult(sender, &malformed);
        assert(read32(failed, 0) == 3);
        minyar_rc_release(failed);
        assert(!minyar_net_ready(receiver, 0));
    }
    uint32_t seed = 0x7817d;
    unsigned char fuzz[93];
    for (unsigned sample = 0; sample < 2048; sample++) {
        for (size_t i = 0; i < sizeof(fuzz); i++) {
            seed ^= seed << 13;
            seed ^= seed >> 17;
            seed ^= seed << 5;
            fuzz[i] = (unsigned char)seed;
        }
        /* Reach the packet-length parser instead of rejecting almost every
         * sample at an enormous random batch count. */
        unsigned count = 1 + sample % 64;
        fuzz[0] = (unsigned char)count;
        fuzz[1] = fuzz[2] = fuzz[3] = 0;
        fuzz[7] = 255;
        MinyarBytes malformed = {fuzz, (long long)(sample % sizeof(fuzz)), 0, NULL, NULL};
        MinyarBytes *failed = minyar_net_sendBatchResult(sender, &malformed);
        assert(read32(failed, 0) == 3);
        minyar_rc_release(failed);
        assert(!minyar_net_ready(receiver, 0));
    }
    minyar_net_close(sender);
    minyar_net_close(receiver);
    puts("UDP batch boundaries and parser rejection verified");
    return 0;
}
