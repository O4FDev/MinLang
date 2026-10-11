/* Independent framing boundaries; no Windows security provider is mocked. */
#include "../runtime/native/schannel_framing.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static void boundary(size_t declared, bool accepted) {
    unsigned char record[] = {22, 3, 3, 0, 4, 11, 0, 0, 0};
    record[6] = (unsigned char)(declared >> 16);
    record[7] = (unsigned char)(declared >> 8);
    record[8] = (unsigned char)declared;
    for (size_t split = 1; split <= sizeof(record); split++) {
        SchannelFraming framing = {0};
        bool valid = true;
        for (size_t at = 0; at < sizeof(record) && valid; at += split) {
            size_t count = sizeof(record) - at;
            if (count > split)
                count = split;
            valid = schannel_plaintext_feed(&framing, record + at, count, 1024 * 1024);
        }
        assert(valid == accepted);
    }
}
int main(void) {
    boundary(1024 * 1024 - 4, true);
    boundary(1024 * 1024 - 3, false);
    boundary(0xffffff, false);
    /* The four-byte handshake header is split across three TLS records. */
    unsigned char fragmented[] = {22, 3, 3, 0, 1, 11, 22, 3, 3, 0, 2, 0,  0, 22, 3, 3,
                                  0,  4, 3, 1, 2, 3,  22, 3, 3, 0, 4, 14, 0, 0,  0};
    for (size_t split = 1; split <= sizeof(fragmented); split++) {
        SchannelFraming framing = {0};
        for (size_t at = 0; at < sizeof(fragmented); at += split) {
            size_t count = sizeof(fragmented) - at;
            if (count > split)
                count = split;
            assert(schannel_plaintext_feed(&framing, fragmented + at, count, 1024 * 1024));
        }
        assert(!framing.record_left && !framing.handshake_left && !framing.handshake_at);
    }
    /* Encrypted TLS 1.2/1.3 bytes are not mistaken for plaintext headers. */
    for (unsigned type = 20; type <= 23; type += 3) {
        unsigned char encrypted[] = {0, 3, 3, 0, 4, 255, 255, 255, 255};
        encrypted[0] = (unsigned char)type;
        SchannelFraming framing = {0};
        for (size_t at = 0; at < sizeof(encrypted); at++)
            assert(schannel_plaintext_feed(&framing, encrypted + at, 1, 1024 * 1024));
        assert(framing.encrypted);
    }
    unsigned char oversize[] = {22, 3, 3, 64, 1};
    SchannelFraming framing = {0};
    assert(!schannel_plaintext_feed(&framing, oversize, sizeof(oversize), 1024 * 1024));
    puts("SChannel visible handshake bounds verified");
}
