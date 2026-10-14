#define _GNU_SOURCE
#include "../runtime/minyar_native.h"
#include <dlfcn.h>
#include <openssl/crypto.h>
#include <openssl/evp.h>
#include <openssl/hmac.h>

static MinyarBytes *owned(const unsigned char *data, size_t length) {
    MinyarBytes *result = minyar_bytes_new((long long)length);
    if (length) memcpy((unsigned char *)result->bytes, data, length);
    return result;
}

MinyarBytes *minyar_quicledger_hmacNative(long long bits, const MinyarBytes *key, const MinyarBytes *data) {
    unsigned char out[EVP_MAX_MD_SIZE];
    unsigned int length = 0;
    static const unsigned char empty[1];
    const unsigned char *material = key->byte_length ? key->bytes : empty;
    if (!HMAC(bits == 384 ? EVP_sha384() : EVP_sha256(), material, (int)key->byte_length, data->bytes, (size_t)data->byte_length, out, &length))
        minyar_native_stop("independent HMAC failed");
    return owned(out, length);
}

MinyarBytes *minyar_quicledger_block(const MinyarBytes *key, const MinyarBytes *input) {
    const EVP_CIPHER *cipher = key->byte_length == 32 ? EVP_aes_256_ecb() : key->byte_length == 16 ? EVP_aes_128_ecb() : NULL;
    if (!cipher || input->byte_length != 16) minyar_native_stop("independent AES block requires a 16 or 32 byte key and one block");
    unsigned char out[32];
    int written = 0, tail = 0;
    EVP_CIPHER_CTX *context = EVP_CIPHER_CTX_new();
    int ok = context && EVP_EncryptInit_ex(context, cipher, NULL, key->bytes, NULL) == 1 && EVP_CIPHER_CTX_set_padding(context, 0) == 1 &&
        EVP_EncryptUpdate(context, out, &written, input->bytes, 16) == 1 && EVP_EncryptFinal_ex(context, out + written, &tail) == 1 && written + tail == 16;
    EVP_CIPHER_CTX_free(context);
    if (!ok) minyar_native_stop("independent AES block failed");
    return owned(out, 16);
}

MinyarBytes *minyar_quicledger_chacha(const MinyarBytes *key, const MinyarBytes *iv, long long length) {
    if (key->byte_length != 32 || iv->byte_length != 16 || length < 0 || length > 64) minyar_native_stop("independent ChaCha20 requires a 32 byte key and 16 byte IV");
    unsigned char zero[64] = {0}, out[64];
    int written = 0, tail = 0;
    EVP_CIPHER_CTX *context = EVP_CIPHER_CTX_new();
    int ok = context && EVP_EncryptInit_ex(context, EVP_chacha20(), NULL, key->bytes, iv->bytes) == 1 &&
        EVP_EncryptUpdate(context, out, &written, zero, (int)length) == 1 && EVP_EncryptFinal_ex(context, out + written, &tail) == 1;
    EVP_CIPHER_CTX_free(context);
    if (!ok) minyar_native_stop("independent ChaCha20 failed");
    return owned(out, (size_t)length);
}

static const EVP_CIPHER *aead(bool chacha, long long key) {
    if (chacha) return key == 32 ? EVP_chacha20_poly1305() : NULL;
    return key == 16 ? EVP_aes_128_gcm() : key == 32 ? EVP_aes_256_gcm() : NULL;
}

MinyarBytes *minyar_quicledger_seal(bool chacha, const MinyarBytes *key, const MinyarBytes *nonce, const MinyarBytes *additional, const MinyarBytes *plaintext) {
    const EVP_CIPHER *cipher = aead(chacha, key->byte_length);
    if (!cipher || nonce->byte_length != 12) minyar_native_stop("independent AEAD key or nonce size");
    size_t length = (size_t)plaintext->byte_length;
    unsigned char *out = malloc(length + 16);
    if (!out) abort();
    int written = 0, tail = 0, ignored = 0;
    EVP_CIPHER_CTX *context = EVP_CIPHER_CTX_new();
    int ok = context && EVP_EncryptInit_ex(context, cipher, NULL, NULL, NULL) == 1 && EVP_CIPHER_CTX_ctrl(context, EVP_CTRL_AEAD_SET_IVLEN, 12, NULL) == 1 &&
        EVP_EncryptInit_ex(context, NULL, NULL, key->bytes, nonce->bytes) == 1 &&
        EVP_EncryptUpdate(context, NULL, &ignored, additional->bytes, (int)additional->byte_length) == 1 &&
        EVP_EncryptUpdate(context, out, &written, plaintext->bytes, (int)length) == 1 && EVP_EncryptFinal_ex(context, out + written, &tail) == 1 &&
        EVP_CIPHER_CTX_ctrl(context, EVP_CTRL_AEAD_GET_TAG, 16, out + length) == 1;
    EVP_CIPHER_CTX_free(context);
    if (!ok) { free(out); minyar_native_stop("independent AEAD seal failed"); }
    MinyarBytes *result = owned(out, length + 16);
    free(out);
    return result;
}

MinyarBytes *minyar_quicledger_openNative(bool chacha, const MinyarBytes *key, const MinyarBytes *nonce, const MinyarBytes *additional, const MinyarBytes *sealed) {
    const EVP_CIPHER *cipher = aead(chacha, key->byte_length);
    if (!cipher || nonce->byte_length != 12) minyar_native_stop("independent AEAD key or nonce size");
    if (sealed->byte_length < 16) return owned((const unsigned char *)"\0", 1);
    size_t length = (size_t)sealed->byte_length - 16;
    unsigned char *out = malloc(length + 1);
    if (!out) abort();
    out[0] = 1;
    int written = 0, tail = 0, ignored = 0;
    EVP_CIPHER_CTX *context = EVP_CIPHER_CTX_new();
    int ok = context && EVP_DecryptInit_ex(context, cipher, NULL, NULL, NULL) == 1 && EVP_CIPHER_CTX_ctrl(context, EVP_CTRL_AEAD_SET_IVLEN, 12, NULL) == 1 &&
        EVP_DecryptInit_ex(context, NULL, NULL, key->bytes, nonce->bytes) == 1 &&
        EVP_DecryptUpdate(context, NULL, &ignored, additional->bytes, (int)additional->byte_length) == 1 &&
        EVP_DecryptUpdate(context, out + 1, &written, sealed->bytes, (int)length) == 1 &&
        EVP_CIPHER_CTX_ctrl(context, EVP_CTRL_AEAD_SET_TAG, 16, (void *)(sealed->bytes + length)) == 1 &&
        EVP_DecryptFinal_ex(context, out + 1 + written, &tail) == 1;
    EVP_CIPHER_CTX_free(context);
    MinyarBytes *result = ok ? owned(out, length + 1) : owned((const unsigned char *)"\0", 1);
    free(out);
    return result;
}

MinyarText *minyar_quicledger_providerVersion(void) {
    const char *version = OpenSSL_version(OPENSSL_VERSION);
    return minyar_native_copy_text((const unsigned char *)version, (long long)strlen(version));
}

MinyarText *minyar_quicledger_providerLibrary(void) {
    Dl_info info;
    void *symbol = dlsym(RTLD_DEFAULT, "EVP_aes_128_gcm");
    if (!symbol || !dladdr(symbol, &info) || !info.dli_fname) return minyar_native_copy_text((const unsigned char *)"", 0);
    return minyar_native_copy_text((const unsigned char *)info.dli_fname, (long long)strlen(info.dli_fname));
}
