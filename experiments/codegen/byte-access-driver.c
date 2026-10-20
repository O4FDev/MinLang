/* Standalone timing driver; runtime is a separate, matching object file.
 * These prefixes are compiler-private ABI, as in tests/llvm_symbols.h.
 */
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "llvm_symbols.h"

typedef struct {
    const unsigned char *bytes;
    long long length, capacity;
    void *offsets, *backing;
} Bytes;
typedef struct {
    long long *values;
    long long length, capacity;
} IntegerList;
typedef long long (*Kernel)(void *, void *);

extern Bytes *minyar_bytes_new(long long);
extern IntegerList *minyar_list_new(void);
extern void minyar_list_add(IntegerList *, long long);
extern void minyar_rc_release(void *);
extern void codegen_probe_drain(void);
extern size_t codegen_probe_live(void);
extern long long codegenByteSum(void *, void *) MINYAR_TEST_LANGUAGE_SYMBOL(codegenByteSum);
extern long long codegenByteCopy(void *, void *) MINYAR_TEST_LANGUAGE_SYMBOL(codegenByteCopy);
extern long long codegenIntegerListSum(void *, void *) MINYAR_TEST_LANGUAGE_SYMBOL(codegenIntegerListSum);

static long long checked_add(long long a, long long b) {
    long long result;
    if (__builtin_add_overflow(a, b, &result)) abort();
    return result;
}
static unsigned char checked_byte(const Bytes *source, long long index) {
    if ((unsigned long long)index >= (unsigned long long)source->length) abort();
    return source->bytes[index];
}
static long long checked_integer(const IntegerList *source, long long index) {
    if ((unsigned long long)index >= (unsigned long long)source->length) abort();
    return source->values[index];
}
/* No restrict, unchecked addition, volatile data, or vectorization switches:
 * C may eliminate checks only with the same loop/value facts as Minyar.
 */
static long long reference_sum(void *owner, void *ignored) {
    (void)ignored;
    const Bytes *source = owner;
    long long total = 0;
    for (long long index = 0; index < source->length; index = checked_add(index, 1))
        total = checked_add(total, checked_byte(source, index));
    return total;
}
static long long reference_copy(void *owner, void *destination) {
    const Bytes *source = owner;
    Bytes *target = destination;
    if (source->length != target->length) abort();
    for (long long index = 0; index < source->length; index = checked_add(index, 1)) {
        long long value = checked_byte(source, index);
        if ((unsigned long long)index >= (unsigned long long)target->length ||
            (unsigned long long)value > 255) abort();
        ((unsigned char *)target->bytes)[index] = (unsigned char)value;
    }
    return target->length;
}
static long long reference_list_sum(void *owner, void *ignored) {
    (void)ignored;
    const IntegerList *source = owner;
    long long total = 0;
    for (long long index = 0; index < source->length; index = checked_add(index, 1))
        total = checked_add(total, checked_integer(source, index));
    return total;
}
static uint64_t ticks(clockid_t clock) {
    struct timespec value;
    if (clock_gettime(clock, &value)) abort();
    return (uint64_t)value.tv_sec * UINT64_C(1000000000) + (uint64_t)value.tv_nsec;
}
static long long argument(const char *text, long long maximum) {
    char *end;
    errno = 0;
    long long value = strtoll(text, &end, 10);
    if (errno || !*text || *end || value < 0 || value > maximum) abort();
    return value;
}
int main(int argc, char **argv) {
    if (argc != 5) return 2;
    _Static_assert(sizeof(void *) == 8 && sizeof(long long) == 8, "64-bit probe ABI");
    int candidate = !strcmp(argv[1], "minyar");
    if (!candidate && strcmp(argv[1], "c")) return 2;
    int copying = !strcmp(argv[2], "copy"), list = !strcmp(argv[2], "list-sum");
    if (!copying && !list && strcmp(argv[2], "sum")) return 2;
    long long length = argument(argv[3], 16777216), repeats = argument(argv[4], 1073741824);
    if (!repeats) return 2;
    void *source, *target;
    long long expected_sum = 0;
    if (list) {
        IntegerList *values = minyar_list_new(), *unused = minyar_list_new();
        source = values;
        target = unused;
        for (long long index = 0; index < length; ++index) {
            long long value = (index * 17 + 13) & 255;
            minyar_list_add(values, value);
            expected_sum += value;
        }
    } else {
        Bytes *values = minyar_bytes_new(length);
        source = values;
        target = minyar_bytes_new(length);
        for (long long index = 0; index < length; ++index) {
            unsigned char value = (unsigned char)((index * 17 + 13) & 255);
            ((unsigned char *)values->bytes)[index] = value;
            expected_sum += value;
        }
    }
    /* Volatile dispatch retains one equal indirect call per invocation in both
     * implementations, including ThinLTO; input itself is ordinary memory.
     */
    Kernel volatile function = list ? (candidate ? codegenIntegerListSum : reference_list_sum) :
        copying ? (candidate ? codegenByteCopy : reference_copy) :
        (candidate ? codegenByteSum : reference_sum);
    long long expected = copying ? length : expected_sum;
    if (function(source, target) != expected) abort(); /* untimed warmup */
    codegen_probe_drain();
    size_t live_before = codegen_probe_live();
    if (copying) memset((void *)((Bytes *)target)->bytes, 0xa5, (size_t)length);
    uint64_t cpu_start = ticks(CLOCK_THREAD_CPUTIME_ID), wall_start = ticks(CLOCK_MONOTONIC);
    long long checksum = 0;
    for (long long repetition = 0; repetition < repeats; ++repetition)
        checksum = checked_add(checksum, function(source, target));
    uint64_t wall = ticks(CLOCK_MONOTONIC) - wall_start;
    uint64_t cpu = ticks(CLOCK_THREAD_CPUTIME_ID) - cpu_start;
    if (checksum != expected * repeats) abort();
    /* Validate complete storage and ownership outside the measured interval. */
    for (long long index = 0; index < length; ++index) {
        long long value = (index * 17 + 13) & 255;
        if (list) { if (((IntegerList *)source)->values[index] != value) abort(); }
        else {
            if (((Bytes *)source)->bytes[index] != value) abort();
            if (copying && ((Bytes *)target)->bytes[index] != value) abort();
        }
    }
    codegen_probe_drain();
    if (codegen_probe_live() != live_before) abort();
    minyar_rc_release(target);
    minyar_rc_release(source);
    codegen_probe_drain();
    if (codegen_probe_live()) abort();
    printf("{\"checksum\":%lld,\"cpu_ns\":%llu,\"wall_ns\":%llu,"
           "\"elements\":%lld,\"repeats\":%lld,\"warmup_calls\":1,"
           "\"live_before\":%zu,\"live_after\":0}\n", checksum,
           (unsigned long long)cpu, (unsigned long long)wall, length, repeats, live_before);
    return 0;
}
