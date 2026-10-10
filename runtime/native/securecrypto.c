/* Narrow X25519 / RFC8439 provider. No TLS/QUIC protocol offload.
 * Monocypher 4.0.3 is pinned and unmodified; see vendor/README.md. */
#include "../minyar_native.h"
#include "../../vendor/monocypher/monocypher.h"
#include <stdint.h>
#define CRYPTO_MAX_BYTES (16 * 1024 * 1024)
static bool bounded(const MinyarBytes *bytes) {
    return bytes->byte_length >= 0 && bytes->byte_length <= CRYPTO_MAX_BYTES;
}
static MinyarBytes *copy(const uint8_t *data, size_t size) {
    MinyarBytes *result = minyar_bytes_new((long long)size);
    if (size)
        memcpy((void *)result->bytes, data, size);
    return result;
}
bool minyar_securecrypto_equal(const MinyarBytes *left, const MinyarBytes *right) {
    if (!bounded(left) || left->byte_length != right->byte_length)
        return false;
    if (left->byte_length == 16)
        return crypto_verify16(left->bytes, right->bytes) == 0;
    if (left->byte_length == 32)
        return crypto_verify32(left->bytes, right->bytes) == 0;
    if (left->byte_length == 64)
        return crypto_verify64(left->bytes, right->bytes) == 0;
    volatile uint8_t different = 0;
    for (long long i = 0; i < left->byte_length; i++)
        different |= left->bytes[i] ^ right->bytes[i];
    return different == 0;
}
MinyarBytes *minyar_securecrypto_x25519(const MinyarBytes *private_key,
                                        const MinyarBytes *public_key) {
    if (private_key->byte_length != 32 || public_key->byte_length != 32)
        return minyar_bytes_new(0);
    uint8_t secret[32], zero[32] = {0};
    crypto_x25519(secret, private_key->bytes, public_key->bytes);
    bool valid = crypto_verify32(secret, zero) != 0;
    MinyarBytes *result = copy(secret, valid ? 32 : 0);
    crypto_wipe(secret, sizeof(secret));
    return result;
}
MinyarBytes *minyar_securecrypto_chacha20(const MinyarBytes *key, long long counter,
                                          const MinyarBytes *nonce, const MinyarBytes *input) {
    if (key->byte_length != 32 || nonce->byte_length != 12 || !bounded(input) || counter < 0 ||
        (uint64_t)counter > UINT32_MAX ||
        ((uint64_t)input->byte_length + 63) / 64 > UINT64_C(0x100000000) - (uint64_t)counter)
        return minyar_bytes_new(0);
    MinyarBytes *result = minyar_bytes_new(input->byte_length);
    crypto_chacha20_ietf((uint8_t *)result->bytes, input->bytes, (size_t)input->byte_length,
                         key->bytes, nonce->bytes, (uint32_t)counter);
    return result;
}
MinyarBytes *minyar_securecrypto_poly1305(const MinyarBytes *key, const MinyarBytes *message) {
    if (key->byte_length != 32 || !bounded(message))
        return minyar_bytes_new(0);
    uint8_t mac[16];
    crypto_poly1305(mac, message->bytes, (size_t)message->byte_length, key->bytes);
    MinyarBytes *result = copy(mac, 16);
    crypto_wipe(mac, sizeof(mac));
    return result;
}
static bool valid_aead(const MinyarBytes *key, const MinyarBytes *nonce,
                       const MinyarBytes *additional, const MinyarBytes *message) {
    return key->byte_length == 32 && nonce->byte_length == 12 && bounded(additional) &&
           bounded(message);
}
MinyarBytes *minyar_securecrypto_seal(const MinyarBytes *key, const MinyarBytes *nonce,
                                      const MinyarBytes *additional, const MinyarBytes *plaintext) {
    if (!valid_aead(key, nonce, additional, plaintext))
        return minyar_bytes_new(0);
    MinyarBytes *result = minyar_bytes_new(plaintext->byte_length + 16);
    crypto_aead_ctx context;
    crypto_aead_init_ietf(&context, key->bytes, nonce->bytes);
    crypto_aead_write(&context, (uint8_t *)result->bytes,
                      (uint8_t *)result->bytes + plaintext->byte_length, additional->bytes,
                      (size_t)additional->byte_length, plaintext->bytes,
                      (size_t)plaintext->byte_length);
    crypto_wipe(&context, sizeof(context));
    return result;
}
MinyarBytes *minyar_securecrypto_open(const MinyarBytes *key, const MinyarBytes *nonce,
                                      const MinyarBytes *additional, const MinyarBytes *sealed) {
    if (!valid_aead(key, nonce, additional, sealed) || sealed->byte_length < 16)
        return minyar_bytes_new(0);
    size_t size = (size_t)sealed->byte_length - 16;
    uint8_t *temporary = malloc(size + 1);
    if (!temporary)
        return minyar_bytes_new(0);
    crypto_aead_ctx context;
    crypto_aead_init_ietf(&context, key->bytes, nonce->bytes);
    int invalid = crypto_aead_read(&context, temporary + 1, sealed->bytes + size, additional->bytes,
                                   (size_t)additional->byte_length, sealed->bytes, size);
    temporary[0] = 1;
    MinyarBytes *result = copy(temporary, invalid ? 0 : size + 1);
    crypto_wipe(&context, sizeof(context));
    crypto_wipe(temporary, size + 1);
    free(temporary);
    return result;
}
