/* AES-128-GCM and ECB blocks only. No TLS or QUIC protocol offload.
 * The OS crypto provider selects hardware AES when the CPU supports it.
 * Apple's public CommonCrypto exposes ECB; GCM authentication below is a
 * branchless scalar GHASH. Windows and Unix use provider GCM directly. */
#include "../minyar_native.h"
#include <stdint.h>

#define AES_MAX_BYTES 65535
static bool valid(const MinyarBytes *key, const MinyarBytes *nonce,
                  const MinyarBytes *aad, const MinyarBytes *data, bool decrypt) {
    return key->byte_length == 16 && nonce->byte_length == 12 &&
           aad->byte_length >= 0 && aad->byte_length <= AES_MAX_BYTES &&
           data->byte_length >= (decrypt ? 16 : 0) &&
           data->byte_length <= AES_MAX_BYTES + (decrypt ? 16 : 0);
}
static MinyarBytes *copy(const unsigned char *source, size_t length) {
    MinyarBytes *result = minyar_bytes_new((long long)length);
    if (length) memcpy((unsigned char *)result->bytes, source, length);
    return result;
}

#ifdef __APPLE__
#include <CommonCrypto/CommonCryptor.h>
typedef CCCryptorRef Aes;
static bool aes_create(const MinyarBytes *key, Aes *aes) {
    return CCCryptorCreate(kCCEncrypt, kCCAlgorithmAES, kCCOptionECBMode,
                           key->bytes, 16, NULL, aes) == kCCSuccess;
}
static bool aes_block(Aes aes, const unsigned char *in, unsigned char *out) {
    size_t written = 0;
    return CCCryptorUpdate(aes, in, 16, out, 16, &written) == kCCSuccess && written == 16;
}
static uint64_t read64(const unsigned char *p) {
    uint64_t value = 0;
    for (int i = 0; i < 8; i++) value = (value << 8) | p[i];
    return value;
}
static void write64(unsigned char *p, uint64_t value) {
    for (int i = 7; i >= 0; i--) { p[i] = (unsigned char)value; value >>= 8; }
}
static void multiply(unsigned char x[16], const unsigned char h[16]) {
    uint64_t x0 = read64(x), x1 = read64(x + 8), v0 = read64(h), v1 = read64(h + 8);
    uint64_t z0 = 0, z1 = 0;
    for (int i = 0; i < 128; i++) {
        uint64_t mask = 0 - (x0 >> 63);
        z0 ^= v0 & mask; z1 ^= v1 & mask;
        x0 = (x0 << 1) | (x1 >> 63); x1 <<= 1;
        mask = 0 - (v1 & 1);
        v1 = (v1 >> 1) | (v0 << 63);
        v0 = (v0 >> 1) ^ (UINT64_C(0xe100000000000000) & mask);
    }
    write64(x, z0); write64(x + 8, z1);
}
static void ghash(unsigned char state[16], const unsigned char h[16],
                  const unsigned char *bytes, size_t length) {
    while (length) {
        size_t count = length < 16 ? length : 16;
        for (size_t i = 0; i < count; i++) state[i] ^= bytes[i];
        multiply(state, h); bytes += count; length -= count;
    }
}
static bool gcm(Aes aes, const MinyarBytes *nonce, const MinyarBytes *aad,
                const MinyarBytes *data, bool decrypt, unsigned char *out) {
    unsigned char h[16] = {0}, j[16] = {0}, counter[16], tag[16] = {0}, mask[16];
    if (!aes_block(aes, h, h)) return false;
    memcpy(j, nonce->bytes, 12); j[15] = 1;
    memcpy(counter, j, 16);
    size_t length = (size_t)data->byte_length - (decrypt ? 16 : 0);
    if (!decrypt) {
        for (size_t at = 0; at < length; at += 16) {
            for (int i = 15; i >= 12; i--) if (++counter[i]) break;
            if (!aes_block(aes, counter, mask)) return false;
            size_t count = length - at < 16 ? length - at : 16;
            for (size_t i = 0; i < count; i++) out[at + i] = data->bytes[at + i] ^ mask[i];
        }
    }
    ghash(tag, h, aad->bytes, (size_t)aad->byte_length);
    ghash(tag, h, decrypt ? data->bytes : out, length);
    unsigned char lengths[16];
    write64(lengths, (uint64_t)aad->byte_length * 8); write64(lengths + 8, (uint64_t)length * 8);
    ghash(tag, h, lengths, 16);
    if (!aes_block(aes, j, mask)) return false;
    for (int i = 0; i < 16; i++) tag[i] ^= mask[i];
    if (!decrypt) { memcpy(out + length, tag, 16); return true; }
    unsigned char different = 0;
    for (int i = 0; i < 16; i++) different |= tag[i] ^ data->bytes[length + (size_t)i];
    if (different) return false;
    for (size_t at = 0; at < length; at += 16) {
        for (int i = 15; i >= 12; i--) if (++counter[i]) break;
        if (!aes_block(aes, counter, mask)) return false;
        size_t count = length - at < 16 ? length - at : 16;
        for (size_t i = 0; i < count; i++) out[at + i] = data->bytes[at + i] ^ mask[i];
    }
    return true;
}
static bool transform(const MinyarBytes *key, const MinyarBytes *nonce, const MinyarBytes *aad,
                      const MinyarBytes *data, bool decrypt, unsigned char *out) {
    Aes aes = NULL;
    bool ok = aes_create(key, &aes) && gcm(aes, nonce, aad, data, decrypt, out);
    if (aes) CCCryptorRelease(aes);
    return ok;
}

#elif defined(_WIN32)
#include <windows.h>
#include <bcrypt.h>
static bool transform(const MinyarBytes *key, const MinyarBytes *nonce, const MinyarBytes *aad,
                      const MinyarBytes *data, bool decrypt, unsigned char *out) {
    BCRYPT_ALG_HANDLE algorithm = NULL;
    BCRYPT_KEY_HANDLE handle = NULL;
    bool ok = BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_AES_ALGORITHM, NULL, 0) == 0 &&
              BCryptSetProperty(algorithm, BCRYPT_CHAINING_MODE, (PUCHAR)BCRYPT_CHAIN_MODE_GCM,
                                 sizeof(BCRYPT_CHAIN_MODE_GCM), 0) == 0 &&
              BCryptGenerateSymmetricKey(algorithm, &handle, NULL, 0, (PUCHAR)key->bytes, 16, 0) == 0;
    unsigned char tag[16];
    ULONG length = (ULONG)data->byte_length - (decrypt ? 16 : 0), written = 0;
    if (decrypt) memcpy(tag, data->bytes + length, 16);
    BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO info;
    BCRYPT_INIT_AUTH_MODE_INFO(info);
    info.pbNonce = (PUCHAR)nonce->bytes; info.cbNonce = 12;
    info.pbAuthData = (PUCHAR)aad->bytes; info.cbAuthData = (ULONG)aad->byte_length;
    info.pbTag = tag; info.cbTag = 16;
    if (ok) {
        NTSTATUS status = decrypt ? BCryptDecrypt(handle, (PUCHAR)data->bytes, length, &info,
                                                    NULL, 0, out, length, &written, 0)
                                  : BCryptEncrypt(handle, (PUCHAR)data->bytes, length, &info,
                                                    NULL, 0, out, length, &written, 0);
        ok = status == 0 && written == length;
        if (ok && !decrypt) memcpy(out + length, tag, 16);
    }
    if (handle) BCryptDestroyKey(handle);
    if (algorithm) BCryptCloseAlgorithmProvider(algorithm, 0);
    return ok;
}

#else
#include <openssl/evp.h>
static bool transform(const MinyarBytes *key, const MinyarBytes *nonce, const MinyarBytes *aad,
                      const MinyarBytes *data, bool decrypt, unsigned char *out) {
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    int length = (int)data->byte_length - (decrypt ? 16 : 0), written = 0, tail = 0;
    bool ok = ctx && EVP_CipherInit_ex(ctx, EVP_aes_128_gcm(), NULL, key->bytes, nonce->bytes, !decrypt) == 1 &&
              EVP_CipherUpdate(ctx, NULL, &written, aad->bytes, (int)aad->byte_length) == 1 &&
              EVP_CipherUpdate(ctx, out, &written, data->bytes, length) == 1 && written == length;
    if (ok && decrypt)
        ok = EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_TAG, 16, (void *)(data->bytes + length)) == 1;
    if (ok) ok = EVP_CipherFinal_ex(ctx, out + length, &tail) == 1 && tail == 0;
    if (ok && !decrypt) ok = EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_GET_TAG, 16, out + length) == 1;
    EVP_CIPHER_CTX_free(ctx);
    return ok;
}
#endif

MinyarBytes *minyar_aes_encrypt(const MinyarBytes *key, const MinyarBytes *nonce,
                               const MinyarBytes *aad, const MinyarBytes *plaintext) {
    if (!valid(key, nonce, aad, plaintext, false)) return minyar_bytes_new(0);
    size_t length = (size_t)plaintext->byte_length + 16;
    unsigned char *buffer = malloc(length);
    if (!buffer) return minyar_bytes_new(0);
    bool ok = transform(key, nonce, aad, plaintext, false, buffer);
    MinyarBytes *result = copy(buffer, ok ? length : 0);
    free(buffer); return result;
}
MinyarBytes *minyar_aes_decrypt(const MinyarBytes *key, const MinyarBytes *nonce,
                               const MinyarBytes *aad, const MinyarBytes *ciphertext) {
    if (!valid(key, nonce, aad, ciphertext, true)) return minyar_bytes_new(0);
    size_t length = (size_t)ciphertext->byte_length - 16;
    unsigned char *buffer = malloc(length + 1);
    if (!buffer) return minyar_bytes_new(0);
    buffer[0] = 1;
    bool ok = transform(key, nonce, aad, ciphertext, true, buffer + 1);
    MinyarBytes *result = copy(buffer, ok ? length + 1 : 0);
    volatile unsigned char *wipe = buffer;
    for (size_t i = 0; i <= length; i++) wipe[i] = 0;
    free(buffer); return result;
}
MinyarBytes *minyar_aes_block(const MinyarBytes *key, const MinyarBytes *plaintext) {
    if (key->byte_length != 16 || plaintext->byte_length != 16) return minyar_bytes_new(0);
    unsigned char out[16];
    bool ok = false;
#ifdef __APPLE__
    Aes aes = NULL;
    ok = aes_create(key, &aes) && aes_block(aes, plaintext->bytes, out);
    if (aes) CCCryptorRelease(aes);
#elif defined(_WIN32)
    BCRYPT_ALG_HANDLE algorithm = NULL;
    BCRYPT_KEY_HANDLE handle = NULL;
    ULONG written = 0;
    ok = BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_AES_ALGORITHM, NULL, 0) == 0 &&
         BCryptSetProperty(algorithm, BCRYPT_CHAINING_MODE, (PUCHAR)BCRYPT_CHAIN_MODE_ECB,
                            sizeof(BCRYPT_CHAIN_MODE_ECB), 0) == 0 &&
         BCryptGenerateSymmetricKey(algorithm, &handle, NULL, 0, (PUCHAR)key->bytes, 16, 0) == 0 &&
         BCryptEncrypt(handle, (PUCHAR)plaintext->bytes, 16, NULL, NULL, 0, out, 16, &written, 0) == 0 && written == 16;
    if (handle) BCryptDestroyKey(handle);
    if (algorithm) BCryptCloseAlgorithmProvider(algorithm, 0);
#else
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    int written = 0, tail = 0;
    ok = ctx && EVP_EncryptInit_ex(ctx, EVP_aes_128_ecb(), NULL, key->bytes, NULL) == 1 &&
         EVP_CIPHER_CTX_set_padding(ctx, 0) == 1 &&
         EVP_EncryptUpdate(ctx, out, &written, plaintext->bytes, 16) == 1 && written == 16 &&
         EVP_EncryptFinal_ex(ctx, out + written, &tail) == 1 && tail == 0;
    EVP_CIPHER_CTX_free(ctx);
#endif
    return copy(out, ok ? 16 : 0);
}
