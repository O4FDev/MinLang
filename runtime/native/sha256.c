/* Standalone SHA-256 provider. OpenSSL supplies its maintained CPU dispatch.
 * The context is value storage owned by a Minyar Bytes, never a pointer handle.
 * Copy through aligned C locals, so Bytes alignment is not an ABI assumption.
 * OpenSSL's SHA256_* compatibility API is required (not a no-deprecated build).
 */
#define OPENSSL_SUPPRESS_DEPRECATED
#include "../minyar_native.h"
#include <openssl/sha.h>
#include <stdint.h>
#include <limits.h>

_Static_assert(sizeof(size_t) == 8, "SHA-256 raw API requires a 64-bit target");
#define SHA256_MAX_BYTES INT64_C(2305843009213693951)

static bool read_context(const MinyarBytes *storage, SHA256_CTX *context) {
    if (storage->byte_length != (long long)sizeof(*context)) return false;
    memcpy(context, storage->bytes, sizeof(*context));
    return context->num < SHA256_CBLOCK && context->md_len == SHA256_DIGEST_LENGTH;
}

MinyarBytes *minyar_sha256_initContext(void) {
    SHA256_CTX context;
    memset(&context, 0, sizeof(context));
    if (!SHA256_Init(&context)) return minyar_bytes_new(0);
    MinyarBytes *result = minyar_bytes_new(sizeof(context));
    memcpy((void *)result->bytes, &context, sizeof(context));
    return result;
}

MinyarBytes *minyar_sha256_cloneContext(const MinyarBytes *storage) {
    SHA256_CTX context;
    if (!read_context(storage, &context)) return minyar_bytes_new(0);
    MinyarBytes *result = minyar_bytes_new(sizeof(context));
    memcpy((void *)result->bytes, &context, sizeof(context));
    return result;
}

bool minyar_sha256_updateContext(MinyarBytes *storage, long long address,
                                 long long length, long long count) {
    /* All arithmetic checks precede input reads and context mutation. This
     * duplicates the Minyar guard for native callers of the internal bridge. */
    if (count < 0 || count > SHA256_MAX_BYTES || length < 0 ||
        length > SHA256_MAX_BYTES - count || address < 0) return false;
    if (length && (address == 0 || length - 1 > LLONG_MAX - address)) return false;
    SHA256_CTX context;
    if (!read_context(storage, &context)) return false;
    if (length && !SHA256_Update(&context, (const void *)(uintptr_t)address, (size_t)length)) return false;
    memcpy((void *)storage->bytes, &context, sizeof(context));
    return true;
}

MinyarBytes *minyar_sha256_finalizeContext(const MinyarBytes *storage, long long count) {
    SHA256_CTX context;
    if (count < 0 || count > SHA256_MAX_BYTES || !read_context(storage, &context)) return minyar_bytes_new(0);
    /* Express the bit count using shifts and unsigned words, avoiding signed
     * multiplication overflow even when the encoded bit length has bit 63 set. */
    context.Nl = (SHA_LONG)(((uint64_t)count & UINT64_C(0x1fffffff)) << 3);
    context.Nh = (SHA_LONG)((uint64_t)count >> 29);
    unsigned char digest[SHA256_DIGEST_LENGTH];
    if (!SHA256_Final(digest, &context)) return minyar_bytes_new(0);
    MinyarBytes *result = minyar_bytes_new(sizeof(digest));
    memcpy((void *)result->bytes, digest, sizeof(digest));
    return result;
}
