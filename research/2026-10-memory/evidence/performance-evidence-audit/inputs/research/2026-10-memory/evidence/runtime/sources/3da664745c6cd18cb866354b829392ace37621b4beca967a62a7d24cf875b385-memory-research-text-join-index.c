/* A joined Text must preserve Unicode character access and slicing after its
 * old lazy indexes are discarded. Expected characters are independent data. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>

static void verify(MinyarText *text, const char *bytes, const int *characters, size_t count) {
    assert(text->byte_length == (long long)strlen(bytes));
    assert(!memcmp(text->bytes, bytes, strlen(bytes)));
    assert(minyar_text_length(text) == (long long)count);
    for (size_t i = 0; i < count; i++) {
        int actual = minyar_text_character_at(text, (long long)i);
        if (actual != characters[i])
            fprintf(stderr, "character %zu: expected U+%04X, observed U+%04X\n", i, characters[i],
                    actual);
        assert(actual == characters[i]);
    }
}

static MinyarText *owning(const char *bytes, int spare) {
    size_t length = strlen(bytes);
    size_t capacity = spare ? 128 : length + 1;
    unsigned char *storage = new_bytes((long long)capacity - 1);
    memcpy(storage, bytes, length + 1);
    return new_text(storage, (long long)length, -1);
}

static void experiment(const char *label, const char *left_bytes, const char *right_bytes,
                       const char *expected, const int *characters, size_t left_count,
                       size_t right_count, int prime_left, int prime_right, int spare, int alias,
                       int view, int self, int consume) {
    fprintf(stderr, "case: %s\n", label);
    MinyarText *root = NULL;
    MinyarText *left;
    if (view) {
        const int original[] = {'p', 'a', 'd', 0xe9, 0x1f642, 't', 'a', 'i', 'l'};
        root = owning("padé🙂tail", 0);
        left = minyar_text_slice(root, 3, 5);
        verify(root, "padé🙂tail", original, sizeof(original) / sizeof(*original));
    } else {
        left = owning(left_bytes, spare);
    }
    MinyarText *right = self ? left : owning(right_bytes, 0);
    if (prime_left)
        verify(left, left_bytes, characters, left_count);
    if (prime_right)
        verify(right, right_bytes, characters + left_count, right_count);
    if (alias)
        minyar_rc_retain(left);
    MinyarText *result =
        consume ? minyar_join_text_take_left(left, right) : minyar_join_text(left, right);
    if (!consume)
        minyar_rc_release(left);
    verify(result, expected, characters, left_count + right_count);
    /* Slicing also relies on the known-count/index representation invariant. */
    MinyarText *slice = minyar_text_slice(result, 0, (long long)left_count);
    verify(slice, left_bytes, characters, left_count);
    minyar_rc_release(slice);
    if (alias) {
        verify(left, left_bytes, characters, left_count);
        minyar_rc_release(left);
    }
    if (root) {
        const int original[] = {'p', 'a', 'd', 0xe9, 0x1f642, 't', 'a', 'i', 'l'};
        verify(root, "padé🙂tail", original, sizeof(original) / sizeof(*original));
        minyar_rc_release(root);
    }
    if (!self)
        minyar_rc_release(right);
    minyar_rc_release(result);
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count)
        assert(minyar_rc_poll(MINYAR_RC_POLL_BUDGET) > 0);
#endif
    assert(!rc_object_count && !rc_bytes);
#ifdef MINYAR_SYSTEM_HEAP
    assert(!rc_heap_allocation_count);
#elif defined(MINYAR_BOUNDED_HEAP)
    assert(!minyar_pool_used);
#endif
    printf("PASS %s\n", label);
}

int main(void) {
    const int mixed[] = {0xe9, 0x1f642, 'x', 'y'};
    const int reversed[] = {'x', 'y', 0xe9, 0x1f642};
    const int unicode[] = {0xe9, 0x1f642, 0xe9, 0x1f642};
    const int ascii[] = {'a', 'b', 'x', 'y'};
    experiment("indexed-unicode-left-realloc", "é🙂", "xy", "é🙂xy", mixed, 2, 2, 1, 1, 0, 0, 0, 0,
               1);
    experiment("indexed-unicode-left-spare", "é🙂", "xy", "é🙂xy", mixed, 2, 2, 1, 1, 1, 0, 0, 0,
               1);
    experiment("indexed-unicode-right", "xy", "é🙂", "xyé🙂", reversed, 2, 2, 1, 1, 0, 0, 0, 0, 1);
    experiment("indexed-unicode-both", "é🙂", "é🙂", "é🙂é🙂", unicode, 2, 2, 1, 1, 0, 0, 0, 0, 1);
    experiment("indexed-unicode-empty-right", "é🙂", "", "é🙂", mixed, 2, 0, 1, 1, 1, 0, 0, 0, 1);
    experiment("indexed-self-realloc", "é🙂", "é🙂", "é🙂é🙂", unicode, 2, 2, 1, 1, 0, 0, 0, 1, 1);
    experiment("indexed-self-spare", "é🙂", "é🙂", "é🙂é🙂", unicode, 2, 2, 1, 1, 1, 0, 0, 1, 1);
    experiment("unknown-unicode-left", "é🙂", "xy", "é🙂xy", mixed, 2, 2, 0, 1, 0, 0, 0, 0, 1);
    experiment("unknown-unicode-right", "xy", "é🙂", "xyé🙂", reversed, 2, 2, 1, 0, 0, 0, 0, 0, 1);
    experiment("known-ascii", "ab", "xy", "abxy", ascii, 2, 2, 1, 1, 0, 0, 0, 0, 1);
    experiment("live-alias", "é🙂", "xy", "é🙂xy", mixed, 2, 2, 1, 1, 0, 1, 0, 0, 1);
    experiment("flattened-view", "é🙂", "xy", "é🙂xy", mixed, 2, 2, 1, 1, 0, 0, 1, 0, 1);
    experiment("borrowed-join", "é🙂", "xy", "é🙂xy", mixed, 2, 2, 1, 1, 0, 0, 0, 0, 0);
    return 0;
}
