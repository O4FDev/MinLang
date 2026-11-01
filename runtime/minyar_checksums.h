/* CRC-32, CRC-64/NVME, MD5 and Base64 for the checksum, digest and encoding packages.
 *
 * Every entry point reads borrowed Bytes only, writes into freshly allocated results and keeps no mutable
 * global state, so the CRC loops are usable from `parallel function` bodies.
 *
 * CRC-32 is CRC-32/ISO-HDLC (reflected 0xEDB88320, init and xorout 0xFFFFFFFF; zip, gzip, PNG). It chains:
 * crc32(crc32(0, a), b) == crc32(0, a ++ b), and crc32(0, "123456789") == 0xCBF43926.
 * CRC-64 is CRC-64/NVME (reflected 0x9A6C9329AC4BC9B5, init and xorout all ones), the variant
 * minyar-objstore's src/crc64.c implements: crc64("123456789") == 0xAE8B14860A799888, returned as eight
 * big-endian bytes (the form S3's CRC64NVME checksums carry).
 * MD5 is RFC 1321 verified against the RFC's test suite; it is legacy interoperability, not a security hash.
 * Base64 is RFC 4648: the standard alphabet with mandatory padding, or the URL-safe alphabet with or without
 * padding. Decoding rejects non-canonical padding and non-zero trailing bits. */

#include <errno.h>
#include <stdint.h>
#include <string.h>

#include "minyar_crc_tables.h"

/* ---------------------------------------------------------------- CRC */

static uint32_t crc32_load32(const unsigned char *p) {
    uint32_t value;
    memcpy(&value, p, sizeof(value));
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
    value = __builtin_bswap32(value);
#endif
    return value;
}

static uint64_t crc64_load64(const unsigned char *p) {
    uint64_t value;
    memcpy(&value, p, sizeof(value));
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
    value = __builtin_bswap64(value);
#endif
    return value;
}

/* Slicing-by-8: eight input bytes per stride, then the byte table for the tail. */
static uint32_t crc32_bytes(uint32_t crc, const unsigned char *p, size_t n) {
    crc = ~crc;
    while (n >= 8) {
        crc ^= crc32_load32(p);
        crc = crc32_slices[7][crc & 0xFF] ^ crc32_slices[6][(crc >> 8) & 0xFF] ^
              crc32_slices[5][(crc >> 16) & 0xFF] ^ crc32_slices[4][crc >> 24] ^
              crc32_slices[3][p[4]] ^ crc32_slices[2][p[5]] ^
              crc32_slices[1][p[6]] ^ crc32_slices[0][p[7]];
        p += 8;
        n -= 8;
    }
    while (n--)
        crc = crc32_slices[0][(crc ^ *p++) & 0xFF] ^ (crc >> 8);
    return ~crc;
}

static uint64_t crc64_bytes(uint64_t crc, const unsigned char *p, size_t n) {
    crc = ~crc;
    while (n >= 8) {
        crc ^= crc64_load64(p);
        crc = crc64_slices[7][crc & 0xFF] ^ crc64_slices[6][(crc >> 8) & 0xFF] ^
              crc64_slices[5][(crc >> 16) & 0xFF] ^ crc64_slices[4][(crc >> 24) & 0xFF] ^
              crc64_slices[3][(crc >> 32) & 0xFF] ^ crc64_slices[2][(crc >> 40) & 0xFF] ^
              crc64_slices[1][(crc >> 48) & 0xFF] ^ crc64_slices[0][crc >> 56];
        p += 8;
        n -= 8;
    }
    while (n--)
        crc = crc64_slices[0][(crc ^ *p++) & 0xFF] ^ (crc >> 8);
    return ~crc;
}

/* checksum.crc32(crc, data, offset, length): the CRC-32 of data[offset, offset + length) continuing crc (the
 * low 32 bits; 0 starts a new checksum). An out-of-range request stops like a Bytes getter. */
long long minyar_runtime_crc32(long long crc, const MinyarBytes *data, long long offset, long long length) {
    if (offset < 0 || length < 0 || offset > data->byte_length || length > data->byte_length - offset) {
        char message[160];
        snprintf(message, sizeof(message),
                 "a CRC32 range of %lld bytes at position %lld does not fit in Bytes of length %lld.",
                 length, offset, data->byte_length);
        minyar_stop_program(message);
    }
    return (long long)crc32_bytes((uint32_t)crc, data->bytes + offset, (size_t)length);
}

/* checksum.crc64(data): CRC-64/NVME of the whole range as eight big-endian bytes. */
MinyarBytes *minyar_runtime_crc64(const MinyarBytes *data) {
    uint64_t crc = crc64_bytes(0, data->bytes, (size_t)data->byte_length);
    MinyarBytes *result = minyar_bytes_new(8);
    unsigned char *output = (unsigned char *)result->bytes;
    for (unsigned int position = 0; position < 8; position++)
        output[position] = (unsigned char)(crc >> (56u - position * 8u));
    return result;
}

/* ---------------------------------------------------------------- MD5 (RFC 1321) */

static uint32_t md5_load32(const unsigned char *p) {
    uint32_t value;
    memcpy(&value, p, sizeof(value));
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
    value = __builtin_bswap32(value);
#endif
    return value;
}

static void md5_store32(unsigned char *p, uint32_t value) {
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
    value = __builtin_bswap32(value);
#endif
    memcpy(p, &value, sizeof(value));
}

static const uint32_t md5_constants[64] = {
    UINT32_C(0xd76aa478), UINT32_C(0xe8c7b756), UINT32_C(0x242070db), UINT32_C(0xc1bdceee),
    UINT32_C(0xf57c0faf), UINT32_C(0x4787c62a), UINT32_C(0xa8304613), UINT32_C(0xfd469501),
    UINT32_C(0x698098d8), UINT32_C(0x8b44f7af), UINT32_C(0xffff5bb1), UINT32_C(0x895cd7be),
    UINT32_C(0x6b901122), UINT32_C(0xfd987193), UINT32_C(0xa679438e), UINT32_C(0x49b40821),
    UINT32_C(0xf61e2562), UINT32_C(0xc040b340), UINT32_C(0x265e5a51), UINT32_C(0xe9b6c7aa),
    UINT32_C(0xd62f105d), UINT32_C(0x02441453), UINT32_C(0xd8a1e681), UINT32_C(0xe7d3fbc8),
    UINT32_C(0x21e1cde6), UINT32_C(0xc33707d6), UINT32_C(0xf4d50d87), UINT32_C(0x455a14ed),
    UINT32_C(0xa9e3e905), UINT32_C(0xfcefa3f8), UINT32_C(0x676f02d9), UINT32_C(0x8d2a4c8a),
    UINT32_C(0xfffa3942), UINT32_C(0x8771f681), UINT32_C(0x6d9d6122), UINT32_C(0xfde5380c),
    UINT32_C(0xa4beea44), UINT32_C(0x4bdecfa9), UINT32_C(0xf6bb4b60), UINT32_C(0xbebfbc70),
    UINT32_C(0x289b7ec6), UINT32_C(0xeaa127fa), UINT32_C(0xd4ef3085), UINT32_C(0x04881d05),
    UINT32_C(0xd9d4d039), UINT32_C(0xe6db99e5), UINT32_C(0x1fa27cf8), UINT32_C(0xc4ac5665),
    UINT32_C(0xf4292244), UINT32_C(0x432aff97), UINT32_C(0xab9423a7), UINT32_C(0xfc93a039),
    UINT32_C(0x655b59c3), UINT32_C(0x8f0ccc92), UINT32_C(0xffeff47d), UINT32_C(0x85845dd1),
    UINT32_C(0x6fa87e4f), UINT32_C(0xfe2ce6e0), UINT32_C(0xa3014314), UINT32_C(0x4e0811a1),
    UINT32_C(0xf7537e82), UINT32_C(0xbd3af235), UINT32_C(0x2ad7d2bb), UINT32_C(0xeb86d391)
};

static const unsigned char md5_shifts[4][4] = {
    { 7, 12, 17, 22 }, { 5, 9, 14, 20 }, { 4, 11, 16, 23 }, { 6, 10, 15, 21 }
};

static uint32_t md5_rotate(uint32_t value, unsigned int count) {
    return (value << count) | (value >> (32u - count));
}

static void md5_block(uint32_t state[4], const unsigned char block[64]) {
    uint32_t words[16];
    for (unsigned int index = 0; index < 16; index++) words[index] = md5_load32(block + index * 4);
    uint32_t a = state[0], b = state[1], c = state[2], d = state[3];
    for (unsigned int round = 0; round < 4; round++) {
        for (unsigned int step = 0; step < 16; step++) {
            uint32_t mixed;
            unsigned int index;
            if (round == 0) { mixed = (b & c) | (~b & d); index = step; }
            else if (round == 1) { mixed = (d & b) | (~d & c); index = (5 * step + 1) % 16; }
            else if (round == 2) { mixed = b ^ c ^ d; index = (3 * step + 5) % 16; }
            else { mixed = c ^ (b | ~d); index = (7 * step) % 16; }
            uint32_t next = d;
            d = c;
            c = b;
            b = b + md5_rotate(a + mixed + md5_constants[round * 16 + step] + words[index],
                               md5_shifts[round][step % 4]);
            a = next;
        }
    }
    state[0] += a;
    state[1] += b;
    state[2] += c;
    state[3] += d;
}

/* digest.md5(data): the 16-byte RFC 1321 message digest. */
MinyarBytes *minyar_runtime_md5(const MinyarBytes *data) {
    uint32_t state[4] = { UINT32_C(0x67452301), UINT32_C(0xefcdab89), UINT32_C(0x98badcfe), UINT32_C(0x10325476) };
    const unsigned char *input = data->bytes;
    size_t remaining = (size_t)data->byte_length;
    /* Whole blocks are hashed in place; at most one padded block is built here. */
    while (remaining >= 64) {
        md5_block(state, input);
        input += 64;
        remaining -= 64;
    }
    unsigned char tail[128];
    size_t length = remaining;
    memcpy(tail, input, length);
    tail[length++] = 0x80;
    size_t padded = length <= 56 ? 64 : 128;
    memset(tail + length, 0, padded - length);
    uint64_t bits = (uint64_t)data->byte_length * 8u;
    for (unsigned int index = 0; index < 8; index++) tail[padded - 8 + index] = (unsigned char)(bits >> (8u * index));
    md5_block(state, tail);
    if (padded == 128) md5_block(state, tail + 64);
    MinyarBytes *result = minyar_bytes_new(16);
    for (unsigned int index = 0; index < 4; index++) md5_store32((unsigned char *)result->bytes + index * 4, state[index]);
    return result;
}

/* ---------------------------------------------------------------- Base64 (RFC 4648) */

/* No length cap: the output is 4/3 of the input, allocated once. */
MinyarText *minyar_runtime_base64EncodeNative(const MinyarBytes *data, long long url_safe) {
    static const char standard[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    static const char web[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    const char *alphabet = url_safe ? web : standard;
    size_t length = (size_t)data->byte_length;
    size_t written = (length + 2) / 3 * 4;
    if (url_safe && length % 3) written -= 3 - length % 3;
    MinyarText *result = new_text_storage((long long)written, (long long)written);
    unsigned char *out = (unsigned char *)result->bytes;
    size_t at = 0, position = 0;
    while (position + 3 <= length) {
        uint32_t chunk = ((uint32_t)data->bytes[position] << 16) | ((uint32_t)data->bytes[position + 1] << 8) |
                         data->bytes[position + 2];
        out[at++] = (unsigned char)alphabet[(chunk >> 18) & 63];
        out[at++] = (unsigned char)alphabet[(chunk >> 12) & 63];
        out[at++] = (unsigned char)alphabet[(chunk >> 6) & 63];
        out[at++] = (unsigned char)alphabet[chunk & 63];
        position += 3;
    }
    size_t final = length - position;
    if (final == 1) {
        uint32_t chunk = (uint32_t)data->bytes[position] << 16;
        out[at++] = (unsigned char)alphabet[(chunk >> 18) & 63];
        out[at++] = (unsigned char)alphabet[(chunk >> 12) & 63];
        if (!url_safe) { out[at++] = '='; out[at++] = '='; }
    } else if (final == 2) {
        uint32_t chunk = ((uint32_t)data->bytes[position] << 16) | ((uint32_t)data->bytes[position + 1] << 8);
        out[at++] = (unsigned char)alphabet[(chunk >> 18) & 63];
        out[at++] = (unsigned char)alphabet[(chunk >> 12) & 63];
        out[at++] = (unsigned char)alphabet[(chunk >> 6) & 63];
        if (!url_safe) out[at++] = '=';
    }
    out[at] = 0;
    result->byte_length = (long long)at;
    result->character_length = (long long)at;
    return result;
}

static int base64_digit(unsigned char byte, long long url_safe) {
    if (byte >= 'A' && byte <= 'Z') return byte - 'A';
    if (byte >= 'a' && byte <= 'z') return byte - 'a' + 26;
    if (byte >= '0' && byte <= '9') return byte - '0' + 52;
    if (byte == (url_safe ? '-' : '+')) return 62;
    if (byte == (url_safe ? '_' : '/')) return 63;
    return -1;
}

/* encoding.decodeNative(bytes, urlSafe): record { data: Bytes; code: Integer }. The code is zero on success
 * and EINVAL for a non-canonical spelling (bad alphabet, misplaced or missing padding, non-zero trailing bits).
 * Decoding allocates at most 3/4 of the input once. */
MinyarRecord *minyar_runtime_base64DecodeNative(const MinyarBytes *data, long long url_safe) {
    MinyarBytes *result = minyar_bytes_new((long long)((size_t)data->byte_length / 4 * 3 + 3));
    int code = 0;
    size_t length = (size_t)data->byte_length;
    size_t padding = 0;
    while (padding < 2 && padding < length && data->bytes[length - 1 - padding] == '=') padding++;
    if (url_safe) {
        /* URL-safe input may omit padding, but a length of 1 modulo 4 is never a whole number of bytes. */
        if ((length - padding) % 4 == 1) code = EINVAL;
        else if (padding && (length % 4) != 0) code = EINVAL;
    } else if (length % 4 != 0) {
        code = EINVAL;
    }
    size_t digits = length - padding;
    if (!code && padding == 1 && digits % 4 != 3) code = EINVAL;
    if (!code && padding == 2 && digits % 4 != 2) code = EINVAL;
    if (!code) {
        size_t out = 0, position = 0;
        uint64_t accumulator = 0;
        unsigned bits = 0;
        for (; position < digits; position++) {
            int digit = base64_digit(data->bytes[position], url_safe);
            if (digit < 0) { code = EINVAL; break; }
            accumulator = (accumulator << 6) | (unsigned)digit;
            bits += 6;
            if (bits >= 8) {
                bits -= 8;
                ((unsigned char *)result->bytes)[out++] = (unsigned char)((accumulator >> bits) & 0xFF);
            }
        }
        /* Canonical: the bits left over in the last partial group must be zero. */
        if (!code && (accumulator & ((UINT64_C(1) << bits) - 1)) != 0) code = EINVAL;
        if (!code) result->byte_length = (long long)out;
    }
    if (code) {
        result->byte_length = 0;
        ((unsigned char *)result->bytes)[0] = 0;
    }
    MinyarRecord *record = minyar_record_new(2);
    minyar_record_set_take(record, 0, (long long)(intptr_t)result);
    minyar_record_set(record, 1, code);
    return record;
}
