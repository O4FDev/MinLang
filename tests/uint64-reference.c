// C uint64_t reference for tests/uint64.min: the values under test and the
// expected results, computed with the C compiler's unsigned arithmetic.
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static uint64_t mix(uint64_t x) {
    x += 0x9e3779b97f4a7c15ull;
    x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ull;
    x = (x ^ (x >> 27)) * 0x94d049bb133111ebull;
    return x ^ (x >> 31);
}
// Uniform bits, small values, values near 2^63 and 2^64, powers of two and of
// ten with small offsets, and narrow random widths, so carries, the sign bit
// and the divisor > 2^63 path are all common.
long long minyar_u64ref_value(long long seed) {
    uint64_t r = mix((uint64_t)seed), s = mix(r);
    uint64_t offset = (s >> 8) % 2049;
    int sign = (s & 1) != 0;
    uint64_t base;
    switch (r % 8) {
    case 0: case 1: return (long long)s;
    case 2: return (long long)(s % 1000);
    case 3: base = 1ull << 63; break;
    case 4: base = 0; sign = 1; break;
    case 5: base = 1ull << (s % 64); break;
    case 6: { base = 1; for (uint64_t k = s % 20; k > 0; k--) base *= 10; break; }
    default: return (long long)(s >> (s % 64));
    }
    return (long long)(sign ? base - offset : base + offset);
}
long long minyar_u64ref_referenceCompare(long long a, long long b) {
    uint64_t x = (uint64_t)a, y = (uint64_t)b;
    return x < y ? -1 : x > y ? 1 : 0;
}
long long minyar_u64ref_referenceDivide(long long a, long long b) { return (long long)((uint64_t)a / (uint64_t)b); }
long long minyar_u64ref_referenceRemainder(long long a, long long b) { return (long long)((uint64_t)a % (uint64_t)b); }
// Byte `index` of the decimal form, or -1 past its end.
long long minyar_u64ref_digit(long long value, long long index) {
    char text[32];
    int length = snprintf(text, sizeof text, "%llu", (unsigned long long)value);
    return index < length ? text[index] : -1;
}
// A digit string of 1 to 22 digits for parse checks, byte `index` or -1.
long long minyar_u64ref_parseByte(long long seed, long long index) {
    uint64_t r = mix((uint64_t)seed ^ 0x5bd1e995ull);
    long long length = 1 + (long long)(r % 22);
    if (index >= length) return -1;
    if (index == 0 && length >= 19 && (r >> 40) % 2 == 0) return (r >> 41) % 2 ? '1' : '0';
    return '0' + (long long)(mix(r + (uint64_t)index) % 10);
}
// The parsed value of that string, and whether it exceeds 2^64-1.
static int parseCase(long long seed, uint64_t *value) {
    uint64_t v = 0;
    for (long long i = 0;; i++) {
        long long byte = minyar_u64ref_parseByte(seed, i);
        if (byte < 0) break;
        uint64_t digit = (uint64_t)(byte - '0');
        if (v > (UINT64_MAX - digit) / 10) return 1;
        v = v * 10 + digit;
    }
    *value = v;
    return 0;
}
long long minyar_u64ref_parseOverflows(long long seed) { uint64_t v; return parseCase(seed, &v); }
long long minyar_u64ref_parseValue(long long seed) { uint64_t v = 0; parseCase(seed, &v); return (long long)v; }
