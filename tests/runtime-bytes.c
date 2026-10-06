/* Model Bytes independently, including recycled storage and native writers. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static size_t zeroed_bytes;
static void *counted_memset(void *target, int value, size_t size) {
    if (!value)
        zeroed_bytes += size;
    return memset(target, value, size);
}

#undef memset
#define memset counted_memset
#define MINYAR_RC_TESTING
#include "../runtime/minyar_runtime.c"
#undef memset

static uint32_t random_state = 0x93e716a5;
static uint32_t next_random(void) {
    random_state ^= random_state << 13;
    random_state ^= random_state >> 17;
    random_state ^= random_state << 5;
    return random_state;
}

static void model(void) {
    enum { CAPACITY = 8192, STEPS = 20000 };
    unsigned char expected[CAPACITY] = {0};
    size_t length = 0;
    minyar_rc_enter(0);
    MinyarBytes *bytes = minyar_bytes_new(0);
    for (int step = 0; step < STEPS; step++) {
        uint32_t random = next_random();
        size_t count = (random >> 8) % 33;
        unsigned action = random % 9;
        if (length + count + 8 >= CAPACITY || action == 0) {
            minyar_bytes_clear(bytes);
            length = 0;
        } else if (action == 1) {
            unsigned char value = (unsigned char)(random >> 16);
            minyar_bytes_add(bytes, value);
            expected[length++] = value;
        } else if (action == 2) {
            size_t requested = (random >> 12) % 1024;
            minyar_bytes_resize(bytes, (long long)requested);
            if (requested > length)
                memset(expected + length, 0, requested - length);
            length = requested;
        } else if (action == 3 && length) {
            size_t position = (random >> 16) % length;
            unsigned char value = (unsigned char)random;
            minyar_bytes_set(bytes, (long long)position, value);
            expected[position] = value;
        } else if (action == 4 && length * 2 < CAPACITY) {
            /* Self-append must survive both an in-place and relocating grow. */
            minyar_bytes_append(bytes, bytes);
            memcpy(expected + length, expected, length);
            length *= 2;
        } else if (action == 5) {
            unsigned char *appended = minyar_bytes_extend(bytes, (long long)count);
            for (size_t i = 0; i < count; i++) {
                assert(appended[i] == 0);
                appended[i] = (unsigned char)(random + i);
                expected[length++] = (unsigned char)(random + i);
            }
        } else if (action == 6) {
            uint64_t value = ((uint64_t)random << 32) | next_random();
            minyar_bytes_add_int64(bytes, (long long)value);
            for (size_t i = 0; i < 8; i++)
                expected[length++] = (unsigned char)(value >> (i * 8));
            assert((uint64_t)minyar_bytes_get_int64(bytes, (long long)length - 8) == value);
        } else if (action == 7 && length) {
            size_t start = (random >> 16) % length;
            size_t end = start + (random >> 20) % (length - start + 1);
            MinyarBytes *slice = minyar_bytes_slice(bytes, (long long)start, (long long)end);
            assert(slice->byte_length == (long long)(end - start));
            assert(!memcmp(slice->bytes, expected + start, end - start));
            minyar_rc_release(slice);
        } else if (action == 8 && length >= 8) {
            size_t position = (random >> 16) % (length - 7);
            uint64_t value = ((uint64_t)random << 32) | next_random();
            minyar_bytes_set_int64(bytes, (long long)position, (long long)value);
            for (size_t i = 0; i < 8; i++)
                expected[position + i] = (unsigned char)(value >> (i * 8));
        }
        assert(minyar_bytes_length(bytes) == (long long)length);
        assert(!memcmp(bytes->bytes, expected, length));
        minyar_rc_step();
    }
    minyar_rc_release(bytes);
    minyar_rc_leave();
}

static void work_bounds(void) {
    MinyarBytes *bytes = minyar_bytes_new(1024 * 1024);
    zeroed_bytes = 0;
    minyar_bytes_clear(bytes);
    assert(zeroed_bytes == 0 && "clearing Bytes must not scan discarded contents");
    minyar_bytes_resize(bytes, 64);
    assert(zeroed_bytes <= 65 && "resize must initialize only newly visible Bytes");
    memset(bytes_data(bytes), 0xa7, 64);
    zeroed_bytes = 0;
    minyar_bytes_resize(bytes, 3);
    assert(zeroed_bytes == 0 && "shrinking Bytes must not scan discarded contents");
    unsigned char *tail = minyar_bytes_extend(bytes, 61);
    for (int i = 0; i < 61; i++)
        assert(tail[i] == 0);
    for (int i = 0; i < 3; i++)
        assert(bytes->bytes[i] == 0xa7);
    minyar_rc_release(bytes);
}

static void measure(void) {
    /* Equivalent steady-state refill work before/after; setup is not timed. */
    MinyarBytes *bytes = minyar_bytes_new(1024 * 1024);
    MinyarBytes *source = minyar_bytes_new(1024 * 1024);
    clock_t started = clock();
    for (int iteration = 0; iteration < 20000; iteration++) {
        minyar_bytes_clear(bytes);
        minyar_bytes_set(source, 0, iteration & 255);
        minyar_bytes_append(bytes, source);
    }
    double seconds = (double)(clock() - started) / CLOCKS_PER_SEC;
    printf("{\"cpu_seconds\":%.9f,\"checksum\":%lld}\n", seconds, minyar_bytes_get(bytes, 0));
    minyar_rc_release(bytes);
    minyar_rc_release(source);
}

int main(int argc, char **argv) {
    if (argc == 2 && !strcmp(argv[1], "--measure")) {
        measure();
        return 0;
    }
    model();
    work_bounds();
    puts("Bytes model and work bounds passed");
    return 0;
}
