/* Bounds only the visible plaintext handshake framing. Authentication and
 * record decryption remain entirely with SChannel. State uses constant space
 * across arbitrary receive and TLS record boundaries. */
#ifndef MINYAR_SCHANNEL_FRAMING_H
#define MINYAR_SCHANNEL_FRAMING_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
typedef struct {
    unsigned char record[5], handshake[4];
    size_t record_at, record_left, handshake_at, handshake_left;
    bool encrypted;
} SchannelFraming;
static bool schannel_plaintext_feed(SchannelFraming *framing, const unsigned char *data,
                                    size_t length, size_t maximum) {
    while (length && !framing->encrypted) {
        if (!framing->record_left) {
            while (length && framing->record_at < 5) {
                framing->record[framing->record_at++] = *data++;
                length--;
            }
            if (framing->record_at < 5)
                return true;
            unsigned type = framing->record[0];
            size_t size = (size_t)framing->record[3] << 8 | framing->record[4];
            if (type < 20 || type > 23 || framing->record[1] != 3 || framing->record[2] > 3 ||
                !framing->record[2] || size > (type == 22 ? 16384u : 18432u))
                return false;
            framing->record_at = 0;
            framing->record_left = size;
            /* TLS 1.2 encrypts handshake records after ChangeCipherSpec;
             * TLS 1.3 ciphertext has outer application_data content type. */
            if (type == 20 || type == 23) {
                framing->encrypted = true;
                return true;
            }
            if (!size)
                continue;
        }
        size_t part = length < framing->record_left ? length : framing->record_left;
        if (framing->record[0] == 22) {
            for (size_t at = 0; at < part; at++) {
                if (framing->handshake_left) {
                    framing->handshake_left--;
                } else {
                    framing->handshake[framing->handshake_at++] = data[at];
                    if (framing->handshake_at == 4) {
                        size_t size = (size_t)framing->handshake[1] << 16 |
                                      (size_t)framing->handshake[2] << 8 | framing->handshake[3];
                        if (maximum < 4 || size > maximum - 4)
                            return false;
                        framing->handshake_left = size;
                        framing->handshake_at = 0;
                    }
                }
            }
        }
        data += part;
        length -= part;
        framing->record_left -= part;
    }
    return true;
}
#endif
