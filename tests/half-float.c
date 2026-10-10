/* The software half-float conversion matches the compiler's _Float16
 * conversion (round to nearest even). The suite checks one float32 bit pattern
 * in 13 plus every exactly representable half; pass "all" to check all 2^32. */
#include "../runtime/native/half-float.h"
#include <stdio.h>

static unsigned long long mismatches;

static void check(uint32_t pattern) {
#ifdef __FLT16_MAX__
    float value;
    memcpy(&value, &pattern, 4);
    _Float16 half = (_Float16)value;
    uint16_t expected;
    memcpy(&expected, &half, 2);
    uint16_t actual = minyar_half_float(value);
    int nan = (expected & 0x7c00u) == 0x7c00u && (expected & 0x3ffu);
    if (nan ? !((actual & 0x7c00u) == 0x7c00u && (actual & 0x3ffu) && (actual & 0x8000u) == (expected & 0x8000u))
            : actual != expected) {
        if (mismatches++ < 5) fprintf(stderr, "mismatch for 0x%08x: 0x%04x != 0x%04x\n", pattern, actual, expected);
    }
#else
    (void)pattern;
#endif
}

int main(int argc, char **argv) {
#ifdef __FLT16_MAX__
    uint64_t step = argc > 1 && !strcmp(argv[1], "all") ? 1 : 13;
    for (uint64_t bits = 0; bits <= 0xffffffffull; bits += step) check((uint32_t)bits);
    for (uint32_t half = 0; half <= 0xffffu; half++) {
        _Float16 exact;
        uint16_t pattern16 = (uint16_t)half;
        memcpy(&exact, &pattern16, 2);
        float value = (float)exact;
        uint32_t pattern;
        memcpy(&pattern, &value, 4);
        check(pattern);
    }
    if (mismatches) { fprintf(stderr, "%llu mismatches\n", mismatches); return 1; }
    printf("software half-float conversion matches _Float16 (%s)\n", step == 1 ? "all 2^32 float32 values" : "1 in 13 float32 values and every half");
#else
    (void)argc; (void)argv;
    puts("half-float comparison skipped: this compiler has no _Float16");
#endif
    return 0;
}
