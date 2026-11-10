/* Shortest Float printing and short-decimal parsing by unrounded scaling;
 * included by minyar_numbers.h and minyar_decimal.h.
 *
 * Both directions compute x * 2^e * 10^p with one or two 64x64->128-bit
 * multiplications against a 128-bit power of ten, keeping the truncated
 * integer part plus a half bit and a sticky bit (an "unrounded" number), and
 * then round exactly. The algorithm and its correctness argument are Russ
 * Cox's "Floating-Point Printing and Parsing Can Be Simple And Fast"
 * (https://research.swtch.com/fp, January 2026), with the proof of the scaling
 * step in https://research.swtch.com/fp-proof. This is a C rendering of the Go
 * reference code in https://github.com/rsc/fpfmt (fpfmt.go), which carries the
 * notice below. Only integer arithmetic is used, so the host locale, the C
 * library and the floating-point rounding mode play no part; freestanding
 * targets get the same results as hosted ones.
 *
 * Copyright (c) 2009 The Go Authors. All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are
 * met:
 *
 *    * Redistributions of source code must retain the above copyright
 * notice, this list of conditions and the following disclaimer.
 *    * Redistributions in binary form must reproduce the above
 * copyright notice, this list of conditions and the following disclaimer
 * in the documentation and/or other materials provided with the
 * distribution.
 *    * Neither the name of Google Inc. nor the names of its
 * contributors may be used to endorse or promote products derived from
 * this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 * A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 * OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 * LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 * DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 * THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE. */
#ifndef MINYAR_FLOAT_SCALE_H
#define MINYAR_FLOAT_SCALE_H
#include "minyar_pow10_table.h"

/* An unrounded number: floor(4x) with bit 0 forced on when 4x is not an
 * integer. Bit 1 is the half bit, bit 0 the sticky bit. */
typedef uint64_t FloatUnrounded;
static inline uint64_t float_unrounded_floor(FloatUnrounded u) {
    return u >> 2;
}
static inline uint64_t float_unrounded_ceil(FloatUnrounded u) {
    return (u + 3) >> 2;
}
/* Nearest, ties to even. */
static inline uint64_t float_unrounded_round(FloatUnrounded u) {
    return (u + 1 + ((u >> 2) & 1)) >> 2;
}

/* floor(x * log10(2)) and floor(x * log2(10)), exact over the ranges used. */
static inline int float_log10_pow2(int x) {
    return (x * 78913) >> 18;
}
static inline int float_log2_pow10(int x) {
    return (x * 108853) >> 15;
}
/* floor(log10(3/4 * 2^e)): the decimal width of a power of two's skewed
 * rounding interval. */
static inline int float_skewed(int e) {
    return (e * 631305 - 261663) >> 21;
}

typedef struct {
    uint64_t hi, lo; /* hi * 2^64 - lo: ceil(10^p) scaled into [2^127, 2^128) */
    int shift;
} FloatScaler;

/* The scaling constants shared by every uscale of one (e, p) pair. The caller
 * keeps p in the table and checks that shift is in [0, 63]. */
static inline FloatScaler float_prescale(int e, int p, int lp) {
    FloatScaler scaler;
    scaler.hi = minyar_pow10_table[p - POW10_MIN][0];
    scaler.lo = minyar_pow10_table[p - POW10_MIN][1];
    scaler.shift = -(e + lp + 3);
    return scaler;
}

/* unrounded(x * 2^e * 10^p) for a left-justified x (top bit set). The high
 * word of x * hi is pm rounded up; when any bit shifted out of it is set, a
 * borrow from the low word cannot reach the kept bits and the value is
 * inexact, so one multiplication suffices. Otherwise subtract x * lo's high
 * word to learn the exact borrow and sticky bit. */
static inline FloatUnrounded float_uscale(uint64_t x, FloatScaler scaler) {
    __uint128_t product = (__uint128_t)x * scaler.hi;
    uint64_t hi = (uint64_t)(product >> 64), mid = (uint64_t)product;
    uint64_t sticky = 1;
    if ((hi & ((UINT64_C(1) << scaler.shift) - 1)) == 0) {
        uint64_t mid2 = (uint64_t)(((__uint128_t)x * scaler.lo) >> 64);
        sticky = mid - mid2 > 1;
        hi -= mid < mid2;
    }
    return (hi >> scaler.shift) | sticky;
}

/* Remove trailing decimal zeros from x * 10^*p: exact division by a power of
 * five is a multiply by its inverse modulo 2^64, and the rotate folds the
 * power-of-two remainder test into the range test. x has at most 17 digits. */
static inline uint64_t float_rotate_right(uint64_t x, unsigned s) {
    return (x >> s) | (x << (64 - s));
}
static inline uint64_t float_trim_zeros(uint64_t x, int *p) {
    uint64_t d;
    if ((d = float_rotate_right(x * UINT64_C(0xcccccccccccccccd), 1)) > UINT64_MAX / 10)
        return x;
    x = d;
    *p += 1;
    if ((d = float_rotate_right(x * UINT64_C(0xc767074b22e90e21), 8)) <= UINT64_MAX / 100000000) {
        x = d;
        *p += 8;
    }
    if ((d = float_rotate_right(x * UINT64_C(0xd288ce703afb7e91), 4)) <= UINT64_MAX / 10000) {
        x = d;
        *p += 4;
    }
    if ((d = float_rotate_right(x * UINT64_C(0x8f5c28f5c28f5c29), 2)) <= UINT64_MAX / 100) {
        x = d;
        *p += 2;
    }
    if ((d = float_rotate_right(x * UINT64_C(0xcccccccccccccccd), 1)) <= UINT64_MAX / 10) {
        x = d;
        *p += 1;
    }
    return x;
}

/* The shortest decimal d * 10^*p that reads back as the finite, nonzero
 * binary64 with these bits (sign ignored). Among shortest candidates it is
 * the one nearest the value, ties to even. d has no trailing zeros. */
static inline uint64_t float_shortest(uint64_t bits, int *p) {
    /* Left-justify the significand: value = m * 2^e with m's top bit set. */
    uint64_t m = (bits & ((UINT64_C(1) << 52) - 1)) << 11;
    int e = (int)((bits >> 52) & 0x7ff);
    if (e == 0) {
        int s = __builtin_clzll(m);
        m <<= s;
        e = -1085 - s;
    } else {
        m |= UINT64_C(1) << 63;
        e = e - 1 - 1085;
    }
    /* [low, high] are the midpoints to the neighbouring binary64 values,
     * scaled to a decimal power p whose unit fits 1 to 10 times inside. A
     * normal power of two has a nearer lower neighbour. */
    int z = 11, power;
    uint64_t low;
    if (m == UINT64_C(1) << 63 && e > -1085) {
        power = -float_skewed(e + z);
        low = m - (UINT64_C(1) << (z - 2));
    } else {
        if (e < -1085)
            z = 11 + (-1085 - e);
        power = -float_log10_pow2(e + z);
        low = m - (UINT64_C(1) << (z - 1));
    }
    uint64_t high = m + (UINT64_C(1) << (z - 1));
    unsigned odd = (unsigned)(m >> z) & 1; /* an odd significand excludes the midpoints */
    FloatScaler scaler = float_prescale(e, power, float_log2_pow10(power));
    uint64_t dmin = float_unrounded_ceil(float_uscale(low, scaler) + odd);
    uint64_t dmax = float_unrounded_floor(float_uscale(high, scaler) - odd);
    /* One fewer digit when a multiple of ten lies inside; else the only
     * candidate; else the correctly rounded one. */
    uint64_t d = dmax / 10;
    if (d * 10 >= dmin) {
        *p = -(power - 1);
        return float_trim_zeros(d, p);
    }
    d = dmin;
    if (d < dmax)
        d = float_unrounded_round(float_uscale(m, scaler));
    *p = -power;
    return d;
}

/* Round d * 10^p (0 < d < 10^19) to the nearest binary64 bits, ties to even.
 * Returns 0 when the result would overflow, or when p or the scale is outside
 * the range this fast path covers; the caller then uses its exact path. */
static inline _Bool float_parse_short(uint64_t d, int p, uint64_t *bits) {
    if (!d || p < POW10_MIN || p > POW10_MAX)
        return 0;
    int b = 64 - __builtin_clzll(d);
    int lp = float_log2_pow10(p);
    int e = 53 - b - lp;
    if (e > 1074)
        e = 1074; /* subnormal: round to fewer bits */
    FloatScaler scaler = float_prescale(e - (64 - b), p, lp);
    if (scaler.shift < 0 || scaler.shift > 63)
        return 0;
    FloatUnrounded u = float_uscale(d << (64 - b), scaler);
    /* log2(d) was estimated from its bit length: at most one extra bit. */
    unsigned extra = u >= (UINT64_C(1) << 55) - 2;
    u = (u >> extra) | (u & 1);
    e -= (int)extra;
    uint64_t m = float_unrounded_round(u);
    if (!(m & (UINT64_C(1) << 52))) {
        *bits = m; /* subnormal or zero; a carry into bit 52 is the smallest normal */
        return 1;
    }
    if (1075 - e > 2046)
        return 0; /* overflow */
    *bits = (m & ~(UINT64_C(1) << 52)) | ((uint64_t)(1075 - e) << 52);
    return 1;
}
#endif
