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
    uintptr_t original_header = (uintptr_t)left;
    MinyarText *result =
        consume ? minyar_join_text_take_left(left, right) : minyar_join_text(left, right);
    assert(((uintptr_t)result == original_header) == (consume && !alias && !view));
    if (prime_left && prime_right && left_count + right_count == strlen(expected))
        assert(result->character_length == (long long)(left_count + right_count) &&
               !result->character_offsets);
    if (!consume)
        minyar_rc_release(left);
    if (!strcmp(label, "slice-first-indexed-unicode")) {
        MinyarText *first = minyar_text_slice(result, 0, (long long)left_count);
        verify(first, left_bytes, characters, left_count);
        minyar_rc_release(first);
    }
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

static void breadcrumb_boundaries(void) {
    enum { COUNT = 130 };
    char unicode_bytes[COUNT * 4 + 1], expected_bytes[COUNT * 8 + 1];
    int unicode_characters[COUNT * 2], expected_characters[COUNT * 2];
    size_t bytes = 0;
    for (size_t i = 0; i < COUNT; i++) {
        const char *character = i % 2 ? "🙂" : "é";
        size_t width = strlen(character);
        memcpy(unicode_bytes + bytes, character, width);
        bytes += width;
        unicode_characters[i] = i % 2 ? 0x1f642 : 0xe9;
        unicode_characters[i + COUNT] = unicode_characters[i];
    }
    unicode_bytes[bytes] = 0;
    memcpy(expected_bytes, unicode_bytes, bytes);
    expected_bytes[bytes] = 'x';
    expected_bytes[bytes + 1] = 0;
    memcpy(expected_characters, unicode_characters, COUNT * sizeof(*expected_characters));
    expected_characters[COUNT] = 'x';
    experiment("unicode-breadcrumb-left-130", unicode_bytes, "x", expected_bytes,
               expected_characters, COUNT, 1, 1, 1, 0, 0, 0, 0, 1);

    memcpy(expected_bytes, unicode_bytes, bytes);
    memcpy(expected_bytes + bytes, unicode_bytes, bytes + 1);
    experiment("unicode-breadcrumb-self-260", unicode_bytes, unicode_bytes, expected_bytes,
               unicode_characters, COUNT, COUNT, 1, 1, 0, 0, 0, 1, 1);

    expected_bytes[0] = 'x';
    memcpy(expected_bytes + 1, unicode_bytes, bytes + 1);
    expected_characters[0] = 'x';
    memcpy(expected_characters + 1, unicode_characters, COUNT * sizeof(*expected_characters));
    experiment("unicode-breadcrumb-right-130", "x", unicode_bytes, expected_bytes,
               expected_characters, 1, COUNT, 1, 1, 0, 0, 0, 0, 1);
}

static void aggregate_metadata_controls(void) {
    const unsigned char ascii_bytes[] = {'a', 0, 'b', 0};
    for (unsigned mode = 0; mode < 4; mode++) {
        unsigned char *storage = new_bytes(3);
        memcpy(storage, ascii_bytes, sizeof(ascii_bytes));
        MinyarText *source = new_text(storage, 3, mode == 1 ? -1 : 3);
        if (mode == 2) {
            minyar_rc_release(source);
            source = owning("é🙂", 0);
            assert(minyar_text_length(source) == 2);
        }
        if (mode == 3)
            minyar_rc_retain(source);
        MinyarList *parts = minyar_list_new();
        minyar_list_references(parts);
        MinyarText *empty = NULL;
        if (mode == 0) {
            empty = new_text(new_bytes(0), 0, 0);
            minyar_list_add(parts, (long long)(intptr_t)empty);
        }
        minyar_list_add(parts, (long long)(intptr_t)source);
        MinyarText *joined = minyar_join_texts(parts);
        assert(joined != source);
        /* Count regression: a certified ASCII aggregate needs no cold index. */
        assert(joined->character_length == ((mode == 0 || mode == 3) ? 3 : -1));
        if (mode == 2) {
            const int characters[] = {0xe9, 0x1f642};
            verify(joined, "é🙂", characters, 2);
        } else {
            assert(joined->byte_length == 3 && !memcmp(joined->bytes, ascii_bytes, 3));
            assert(minyar_text_length(joined) == 3);
            assert(minyar_text_character_at(joined, 0) == 'a');
            assert(minyar_text_character_at(joined, 1) == 0);
            assert(minyar_text_character_at(joined, 2) == 'b');
        }
        assert(source->byte_length == (mode == 2 ? 6 : 3));
        assert(!memcmp(source->bytes, mode == 2 ? (const void *)"é🙂" : ascii_bytes,
                       (size_t)source->byte_length));
        assert(source->character_length == (mode == 1 ? -1 : mode == 2 ? 2 : 3));
        if (mode == 3)
            minyar_rc_release(source);
        minyar_rc_release(parts);
        if (empty)
            minyar_rc_release(empty);
        minyar_rc_release(source);
        minyar_rc_release(joined);
#ifdef MINYAR_BOUNDED_RC
        while (rc_pending_count)
            assert(minyar_rc_poll(MINYAR_RC_POLL_BUDGET) > 0);
#endif
        assert(!rc_object_count && !rc_bytes);
    }
}

int main(int argc, char **argv) {
    if (argc == 2 && !strcmp(argv[1], "--invalid-utf8")) {
        MinyarText *left = owning("\xc3(", 0);
        MinyarText *right = owning("x", 0);
        assert(minyar_text_length(right) == 1);
        MinyarText *joined = minyar_join_text_take_left(left, right);
        minyar_text_length(joined);
        assert(0 && "invalid UTF-8 must still trap when the joined Text is indexed");
    }
    const int mixed[] = {0xe9, 0x1f642, 'x', 'y'};
    const int reversed[] = {'x', 'y', 0xe9, 0x1f642};
    const int unicode[] = {0xe9, 0x1f642, 0xe9, 0x1f642};
    const int ascii[] = {'a', 'b', 'x', 'y'};
    experiment("indexed-unicode-left-realloc", "é🙂", "xy", "é🙂xy", mixed, 2, 2, 1, 1, 0, 0, 0, 0,
               1);
    experiment("indexed-unicode-left-spare", "é🙂", "xy", "é🙂xy", mixed, 2, 2, 1, 1, 1, 0, 0, 0,
               1);
    experiment("slice-first-indexed-unicode", "é🙂", "xy", "é🙂xy", mixed, 2, 2, 1, 1, 1, 0, 0, 0,
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
    experiment("borrowed-known-ascii", "ab", "xy", "abxy", ascii, 2, 2, 1, 1, 0, 0, 0, 0, 0);
    breadcrumb_boundaries();
    aggregate_metadata_controls();
    return 0;
}
