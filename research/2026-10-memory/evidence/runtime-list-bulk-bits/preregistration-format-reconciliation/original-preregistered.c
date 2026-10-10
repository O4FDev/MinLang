/* Explicit bit transport and independent scalar storage; no FP arithmetic. */
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>

static struct {
    RcObject owner;
    MinyarText text;
} immortal = {{RC_TEXT}, {(const unsigned char *)"i", 1, 1, NULL, NULL}};

static void recover(void) {
    while (rc_pending_count)
        assert(minyar_rc_poll(1) == 1);
    assert(!rc_object_count && !rc_bytes);
#ifdef MINYAR_BOUNDED_HEAP
    assert(!minyar_pool_used);
#else
    assert(!rc_heap_allocation_count);
#endif
}

int main(void) {
    static const uint64_t bits[] = {
        UINT64_C(0x0000000000000000), UINT64_C(0x8000000000000000),
        UINT64_C(0x0000000000000001), UINT64_C(0x8000000000000001),
        UINT64_C(0x7ff0000000000000), UINT64_C(0xfff0000000000000),
        UINT64_C(0x7ff8123456789abc), UINT64_C(0xfff8fedcba987654),
        UINT64_C(0x7ff0123456789abc), UINT64_C(0xfff0123456789abc)};
    MinyarList *source = minyar_list_new();
    for (size_t i = 0; i < sizeof(bits) / sizeof(*bits); i++) {
        long long word;
        memcpy(&word, &bits[i], sizeof(word));
        minyar_list_add(source, word);
    }
    minyar_rc_retain(source);
    MinyarList *result = minyar_list_appended(source, 19, 0, 0);
    assert(result != source && result->values != source->values);
    assert(!memcmp(source->values, bits, sizeof(bits)) && !memcmp(result->values, bits, sizeof(bits)));
    minyar_list_set(source, 0, 31);
    assert(result->values[0] == 0);
    minyar_list_set(result, 1, 37);
    uint64_t untouched;
    memcpy(&untouched, &source->values[1], sizeof(untouched));
    assert(untouched == UINT64_C(0x8000000000000000));
    minyar_rc_release(source);
    assert(source->values[0] == 31 && result->values[1] == 37);
    minyar_rc_release(source);
    minyar_rc_release(result);
    recover();

    source = minyar_list_new();
    minyar_list_add(source, 41);
    /* Valid scalar truncation: no element owners to release; retain allocation. */
    source->length = 0;
    assert(source->values && source->capacity > 0);
    result = minyar_list_appended(source, 43, 0, 0);
    assert(!source->length && result->length == 1 && result->values[0] == 43);
    minyar_rc_release(source);
    minyar_rc_release(result);
    recover();

    for (int populated = 0; populated < 2; populated++) {
        source = minyar_list_new();
        minyar_list_references(source);
        if (populated) {
            minyar_list_add(source, (long long)(uintptr_t)&immortal.text);
            minyar_list_add(source, 0);
        }
        result = minyar_list_appended(source, (long long)(uintptr_t)&immortal.text, 1, 0);
        assert(result->length == source->length + 1);
        for (long long i = 0; i < source->length; i++)
            assert(result->values[i] == source->values[i]);
        assert(result->values[source->length] == (long long)(uintptr_t)&immortal.text);
        assert(immortal.owner.ownership == RC_TEXT);
        minyar_rc_release(source);
        minyar_rc_release(result);
        recover();
    }
    puts("10 raw words, mutation independence, empty backed scalar, empty and immortal/null reference controls recovered");
    return 0;
}
