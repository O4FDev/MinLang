/* Numeric formatting probes: counted libc work, bounded writes and raw IEEE bits. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#include <assert.h>
#include <math.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static unsigned long long format_calls, parse_calls;
static int counted_snprintf(char *out, size_t capacity, const char *format, ...) {
    va_list arguments;
    va_start(arguments, format);
    format_calls++;
    int result = vsnprintf(out, capacity, format, arguments);
    va_end(arguments);
    return result;
}
static double counted_strtod(const char *text, char **end) {
    parse_calls++;
    return strtod(text, end);
}
#undef snprintf
#define snprintf counted_snprintf
#define strtod counted_strtod
#include "../runtime/minyar_runtime.c"
#undef snprintf
#undef strtod

static double from_bits(uint64_t bits) {
    double value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

static void bounded_output(void) {
    struct {
        const char *text;
        double value;
        int direction;
        const char *expected;
    } decimal_transitions[] = {{"9.9e+0", 10.0, 1, "1.0e+1"},
                               {"1.0e+1", 9.9, -1, "9.9e+0"},
                               {"-9.9e+0", -10.0, 1, "-1.0e+1"},
                               {"-1.00e+0", -0.999, -1, "-9.99e-1"}};
    for (size_t index = 0; index < sizeof(decimal_transitions) / sizeof(*decimal_transitions);
         index++) {
        char scientific[40];
        strcpy(scientific, decimal_transitions[index].text);
        assert(adjacent_float_decimal(scientific, decimal_transitions[index].value,
                                      decimal_transitions[index].direction));
        assert(!strcmp(scientific, decimal_transitions[index].expected));
    }
    const double values[] = {
        0.0, -0.0, 42.0, -42.0, 0.1, 1e-8, 1e21, from_bits(UINT64_C(1)), INFINITY, -INFINITY, NAN};
    for (size_t index = 0; index < sizeof(values) / sizeof(*values); index++) {
        char full[48];
        size_t length = format_float(values[index], full, sizeof(full));
        assert(length == strlen(full) && length < sizeof(full));
        for (size_t capacity = 0; capacity <= length + 2; capacity++) {
            unsigned char storage[64];
            memset(storage, 0xa5, sizeof(storage));
            size_t result = format_float(values[index], (char *)storage + 8, capacity);
            assert(result == length);
            for (size_t i = 0; i < 8; i++)
                assert(storage[i] == 0xa5);
            for (size_t i = 8 + capacity; i < sizeof(storage); i++)
                assert(storage[i] == 0xa5);
            if (capacity) {
                size_t copied = length < capacity ? length : capacity - 1;
                assert(memcmp(storage + 8, full, copied) == 0);
                assert(storage[8 + copied] == 0);
            }
        }
        assert(format_float(values[index], NULL, 0) == length);
    }
    puts("numeric buffer bounds passed");
}

static void exact_integer_budget(void) {
    format_calls = parse_calls = 0;
    for (long long value = -1000; value <= 1000; value++) {
        char text[48];
        format_float((double)value, text, sizeof(text));
    }
    printf("{\"formatted\":2001,\"snprintf_calls\":%llu,\"strtod_calls\":%llu}\n", format_calls,
           parse_calls);
    fflush(stdout);
    assert(parse_calls == 0);
    assert(format_calls <= 2001);
}

static void benchmark(const char *kind, unsigned repetitions) {
    char text[48];
    volatile unsigned long long checksum = 0;
    clock_t start = clock();
    for (unsigned index = 0; index < repetitions; index++) {
        double value;
        if (!strcmp(kind, "integer"))
            value = (double)((long long)(index * UINT64_C(15485863) % UINT64_C(9007199254740991)) -
                             INT64_C(4503599627370495));
        else if (!strcmp(kind, "mixed"))
            value = index % 2 ? (double)(index % 10000) : (double)(index % 10000) / 7.0;
        else
            value = (double)(index % 10000) / 7.0 + 0.1;
        size_t length = format_float(value, text, sizeof(text));
        checksum += length + (unsigned char)text[index % length];
    }
    double seconds = (double)(clock() - start) / CLOCKS_PER_SEC;
    printf("{\"kind\":\"%s\",\"iterations\":%u,\"cpu_seconds\":%.9f,\"checksum\":%llu,"
           "\"snprintf_calls\":%llu,\"strtod_calls\":%llu}\n",
           kind, repetitions, seconds, checksum, format_calls, parse_calls);
}

int main(int argc, char **argv) {
    if (argc > 1 && !strcmp(argv[1], "--bounds")) {
        bounded_output();
    } else if (argc > 1 && !strcmp(argv[1], "--budget")) {
        exact_integer_budget();
    } else if (argc > 1 && !strcmp(argv[1], "--bench")) {
        benchmark(argv[2], (unsigned)strtoul(argv[3], NULL, 10));
    } else {
        unsigned long long bits;
        while (scanf("%llx", &bits) == 1) {
            char text[48];
            size_t length = format_float(from_bits(bits), text, sizeof(text));
            assert(length == strlen(text) && length < sizeof(text));
            puts(text);
        }
    }
    return 0;
}
