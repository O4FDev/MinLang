/* Original runtime probes derived from Lua cleanup/formatting methodologies. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#include <assert.h>
#include <limits.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int deny_allocations;
static size_t denied_attempts;

static void *probe_malloc(size_t size) {
    if (deny_allocations) { denied_attempts++; return NULL; }
    return malloc(size);
}

static void *probe_calloc(size_t count, size_t size) {
    if (deny_allocations) { denied_attempts++; return NULL; }
    return calloc(count, size);
}

static void *probe_realloc(void *pointer, size_t size) {
    if (!size) { free(pointer); return NULL; }
    if (deny_allocations) { denied_attempts++; return NULL; }
    return realloc(pointer, size);
}

#define malloc probe_malloc
#define calloc probe_calloc
#define realloc probe_realloc
#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_RC_TESTING 1
#define MINYAR_INTEGER_TEXT_CACHE_LIMIT 0
#define MINYAR_FRAME_CACHE_BYTES 0
#include "../runtime/minyar_runtime.c"
#undef malloc
#undef calloc
#undef realloc

static void empty_owned_heap(void) {
    while (rc_pending_count) assert(minyar_rc_poll(32) > 0);
    assert(rc_frames == NULL);
    assert(rc_object_count == 0 && rc_immortal_object_count == 0);
    assert(rc_bytes == 0 && rc_heap_allocation_count == 0);
}

static void chain_cleanup(void) {
    /* One empty head followed by exactly200000 next links, as in gc.lua. */
    MinyarRecord *chain = minyar_record_new(0);
    for (size_t index = 0; index < 200000; index++) {
        MinyarRecord *next = minyar_record_new(1);
        minyar_record_set_reference(next, 0, (long long)(intptr_t)chain);
        minyar_rc_release(chain);
        chain = next;
    }
    assert(rc_object_count == 200001);
    deny_allocations = 1;
    /* Prove that the allocator control is armed before checking cleanup. */
    assert(probe_malloc(1) == NULL && denied_attempts == 1);
    denied_attempts = 0;
    minyar_rc_release(chain);
    empty_owned_heap();
    assert(denied_attempts == 0);
    puts("200001 objects released; zero allocation attempts, live objects, bytes and blocks");
}

static void integer_formatting(void) {
    /* Literal decimal oracles are independent of the runtime formatter. The
     * runner compiles this entire translation unit with zero and pattern
     * automatic-variable initialization, including its32-byte format buffer. */
    const struct { long long value; const char *text; } cases[] = {
        {LLONG_MIN, "-9223372036854775808"}, {LLONG_MIN + 1, "-9223372036854775807"},
        {-2147483648LL, "-2147483648"}, {-100, "-100"}, {-10, "-10"}, {-1, "-1"},
        {0, "0"}, {1, "1"}, {9, "9"}, {10, "10"}, {99, "99"}, {100, "100"},
        {2147483647LL, "2147483647"}, {2147483648LL, "2147483648"},
        {LLONG_MAX - 1, "9223372036854775806"}, {LLONG_MAX, "9223372036854775807"}
    };
    for (size_t index = 0; index < sizeof(cases) / sizeof(cases[0]); index++) {
        MinyarText *text = minyar_integer_text(cases[index].value);
        size_t length = strlen(cases[index].text);
        assert(text->byte_length == (long long)length);
        assert(minyar_text_length(text) == (long long)length);
        assert(memcmp(text->bytes, cases[index].text, length) == 0);
        assert(text->bytes[length] == 0);
        minyar_rc_release(text);
    }
    empty_owned_heap();
    puts("16 integer formatting boundary strings and terminators passed");
}

int main(int argc, char **argv) {
    assert(argc == 2);
    if (!strcmp(argv[1], "chain")) chain_cleanup();
    else { assert(!strcmp(argv[1], "format")); integer_formatting(); }
    return 0;
}
