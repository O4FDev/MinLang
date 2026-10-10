/* IEEE 754 binary16 conversion for compilers without a _Float16 type. */
#ifndef MINYAR_HALF_FLOAT_H
#define MINYAR_HALF_FLOAT_H
#include <stdint.h>
#include <string.h>

/* Round to nearest even. Values beyond the half range become infinity, as a
 * float conversion would, and NaN stays NaN. */
static inline uint16_t minyar_half_float(float value) {
    uint32_t bits;
    memcpy(&bits, &value, 4);
    uint32_t sign = (bits >> 16) & 0x8000u, exponent = (bits >> 23) & 0xffu, mantissa = bits & 0x7fffffu;
    if (exponent == 0xffu) return (uint16_t)(sign | 0x7c00u | (mantissa ? 0x200u : 0));
    int biased = (int)exponent - 127 + 15;
    if (biased >= 31) return (uint16_t)(sign | 0x7c00u);
    if (biased <= 0) {
        if (biased < -10) return (uint16_t)sign;
        mantissa |= 0x800000u;
        uint32_t shift = (uint32_t)(14 - biased), result = mantissa >> shift;
        uint32_t rest = mantissa & ((1u << shift) - 1), halfway = 1u << (shift - 1);
        if (rest > halfway || (rest == halfway && (result & 1u))) result++;
        return (uint16_t)(sign | result);
    }
    uint32_t result = sign | ((uint32_t)biased << 10) | (mantissa >> 13), rest = mantissa & 0x1fffu;
    if (rest > 0x1000u || (rest == 0x1000u && (result & 1u))) result++;
    return (uint16_t)result;
}
#endif
