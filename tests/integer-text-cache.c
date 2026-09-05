#define MINYAR_RC_TESTING
#include "../runtime/minyar_runtime.c"
#include <assert.h>
#ifndef EXPECTED_CACHE_LIMIT
#error test requires EXPECTED_CACHE_LIMIT
#endif
static void drain(void) {
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count) minyar_rc_poll(1024);
#endif
}
static void convert(long long value) {
    char expected[32];
    int length = snprintf(expected, sizeof(expected), "%lld", value);
    MinyarText *text = minyar_integer_text(value);
    assert(text->byte_length == length);
    assert(!memcmp(text->bytes, expected, (size_t)length));
    MinyarText *second = minyar_integer_text(value);
    if ((unsigned long long)value < EXPECTED_CACHE_LIMIT) assert(second == text);
    else assert(second != text);
    minyar_rc_release(second);
    minyar_rc_retain(text);
    minyar_rc_release(text);
    assert(!memcmp(text->bytes, expected, (size_t)length));
    minyar_rc_release(text);
    drain();
}
static void replace_cached_with_owned(void) {
    MinyarList *values = minyar_list_new();
    minyar_list_references(values);
    MinyarText *first = minyar_integer_text(0);
    minyar_list_add_take(values, (long long)(intptr_t)first);
    minyar_rc_retain(first);
    MinyarText *last = minyar_integer_text(32768);
    minyar_list_set(values, 0, (long long)(intptr_t)last);
    minyar_rc_release(last);
    minyar_rc_release(values);
    drain();
    assert(first->byte_length == 1 && first->bytes[0] == '0');
    minyar_rc_release(first);
    drain();
}
int main(void) {
    for (int pass = 0; pass < 2; pass++) {
        for (int value = 0; value <= 32768; value++) convert(value);
        convert(-1); convert(LLONG_MIN); convert(LLONG_MAX);
        replace_cached_with_owned();
        assert(rc_object_count == EXPECTED_CACHE_LIMIT);
        assert(rc_immortal_object_count == EXPECTED_CACHE_LIMIT);
        size_t expected_bytes = 0;
        for (int value = 0; value < EXPECTED_CACHE_LIMIT; value++) {
            char buffer[32];
            int length = snprintf(buffer, sizeof(buffer), "%d", value);
            expected_bytes += sizeof(RcObject) + sizeof(MinyarText) + sizeof(RcData) + (size_t)length + 1;
        }
        assert(rc_bytes == expected_bytes);
#ifdef MINYAR_BOUNDED_HEAP
        assert(minyar_pool_used == (size_t)EXPECTED_CACHE_LIMIT * 96);
#endif
    }
    printf("cache limit %d: values, aliases and retained storage passed\n", EXPECTED_CACHE_LIMIT);
}
