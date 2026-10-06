/* Independent consuming Text oracle: original expectations, not a copied
 * implementation of UTF-8 indexing. One explicit runtime snapshot per build. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#define MINYAR_RC_TESTING 1
#ifndef MINYAR_RESEARCH_RUNTIME
#define MINYAR_RESEARCH_RUNTIME "../runtime/minyar_runtime.c"
#endif
#include MINYAR_RESEARCH_RUNTIME
#include <assert.h>

static MinyarText *owned(const char *value, int spare) {
    size_t length = strlen(value);
    unsigned char *bytes = new_bytes((long long)(spare ? length + 127 : length));
    memcpy(bytes, value, length + 1);
    return new_text(bytes, (long long)length, -1);
}

static void invariant(const MinyarText *value) {
    if (value->character_length >= 0 && !value->character_offsets)
        assert(value->character_length == value->byte_length);
}

static void check(MinyarText *value, const char *bytes, const int *points, size_t count) {
    assert(value->byte_length == (long long)strlen(bytes));
    assert(!memcmp(value->bytes, bytes, strlen(bytes)));
    invariant(value);
    assert(minyar_text_length(value) == (long long)count);
    for (size_t i = 0; i < count; i++)
        assert(minyar_text_character_at(value, (long long)i) == points[i]);
    invariant(value);
}

static void drain(void) {
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count) {
        size_t objects = rc_object_count;
        size_t work = minyar_rc_poll(1);
        assert(work == 1 && objects - rc_object_count <= work);
    }
#endif
    assert(!rc_object_count && !rc_bytes);
#ifdef MINYAR_SYSTEM_HEAP
    assert(!rc_heap_allocation_count);
#endif
}

static void run(const char *label, const char *left_bytes, const char *right_bytes,
                const char *joined_bytes, const int *points, size_t left_count,
                size_t right_count, int prime_left, int prime_right, int spare,
                int shared, int self, int view) {
    fprintf(stderr, "case: %s\n", label);
    MinyarText *root = NULL;
    MinyarText *left;
    if (view) {
        root = owned("zé🙂z", 0);
        left = minyar_text_slice(root, 1, 3);
    } else {
        left = owned(left_bytes, spare);
    }
    MinyarText *right = self ? left : owned(right_bytes, 0);
    if (prime_left)
        check(left, left_bytes, points, left_count);
    if (prime_right)
        check(right, right_bytes, points + left_count, right_count);
    if (shared)
        minyar_rc_retain(left);
    uintptr_t old_header = (uintptr_t)left;
    MinyarText *joined = minyar_join_text_take_left(left, right);
    assert(((uintptr_t)joined == old_header) == (!shared && !view));
    /* Slice before any length/Character query of the joined value. */
    MinyarText *prefix = minyar_text_slice(joined, 0, (long long)left_count);
    check(prefix, left_bytes, points, left_count);
    check(joined, joined_bytes, points, left_count + right_count);
    minyar_rc_release(prefix);
    if (shared) {
        check(left, left_bytes, points, left_count);
        minyar_rc_release(left);
    }
    if (root) {
        const int root_points[] = {'z', 0xe9, 0x1f642, 'z'};
        check(root, "zé🙂z", root_points, 4);
        minyar_rc_release(root);
    }
    if (!self)
        minyar_rc_release(right);
    minyar_rc_release(joined);
    drain();
}

static void long_breadcrumb_boundary(void) {
    const int expected[] = {0xe9, 0x1f642};
    unsigned char *bytes = new_bytes(128 + 6);
    memset(bytes, 'a', 128);
    memcpy(bytes + 128, "é🙂", 7);
    MinyarText *left = new_text(bytes, 134, -1);
    assert(minyar_text_length(left) == 130);
    MinyarText *right = owned("!", 0);
    assert(minyar_text_length(right) == 1);
    MinyarText *joined = minyar_join_text_take_left(left, right);
    assert(joined == left);
    invariant(joined);
    MinyarText *tail = minyar_text_slice(joined, 128, 130);
    check(tail, "é🙂", expected, 2);
    assert(minyar_text_character_at(joined, 127) == 'a');
    assert(minyar_text_character_at(joined, 128) == 0xe9);
    assert(minyar_text_character_at(joined, 129) == 0x1f642);
    assert(minyar_text_character_at(joined, 130) == '!');
    minyar_rc_release(tail);
    minyar_rc_release(right);
    minyar_rc_release(joined);
    drain();
}

static int review_invalid_utf8(void) {
    MinyarText *left = owned("a", 0);
    assert(minyar_text_length(left) == 1);
    unsigned char *bytes = new_bytes(1);
    bytes[0] = 0xff;
    bytes[1] = 0;
    MinyarText *right = new_text(bytes, 1, -1);
    MinyarText *joined = minyar_join_text_take_left(left, right);
    /* Concatenation preserves lazy validation; Character lookup validates
     * the whole unknown index and must reject the later malformed byte. */
    invariant(joined);
    (void)minyar_text_character_at(joined, 0);
    fprintf(stderr, "ERROR: malformed UTF-8 was silently accepted\n");
    return 2;
}

int main(int argc, char **argv) {
    if (argc == 2 && !strcmp(argv[1], "--invalid-utf8"))
        return review_invalid_utf8();
    const int mixed[] = {0xe9, 0x1f642, 'x', 'y'};
    const int reverse[] = {'x', 'y', 0xe9, 0x1f642};
    const int twice[] = {0xe9, 0x1f642, 0xe9, 0x1f642};
    const int ascii[] = {'a', 'b', 'x', 'y'};
    run("Unicode-indexed-growth", "é🙂", "xy", "é🙂xy", mixed, 2, 2, 1, 1, 0, 0, 0, 0);
    run("Unicode-indexed-spare", "é🙂", "xy", "é🙂xy", mixed, 2, 2, 1, 1, 1, 0, 0, 0);
    run("Unicode-on-right", "xy", "é🙂", "xyé🙂", reverse, 2, 2, 1, 1, 0, 0, 0, 0);
    run("Unicode-both", "é🙂", "é🙂", "é🙂é🙂", twice, 2, 2, 1, 1, 0, 0, 0, 0);
    run("known-empty-right", "é🙂", "", "é🙂", mixed, 2, 0, 1, 1, 1, 0, 0, 0);
    run("self-growth", "é🙂", "é🙂", "é🙂é🙂", twice, 2, 2, 1, 1, 0, 0, 1, 0);
    run("self-spare", "é🙂", "é🙂", "é🙂é🙂", twice, 2, 2, 1, 1, 1, 0, 1, 0);
    run("unknown-left", "é🙂", "xy", "é🙂xy", mixed, 2, 2, 0, 1, 0, 0, 0, 0);
    run("unknown-right", "xy", "é🙂", "xyé🙂", reverse, 2, 2, 1, 0, 0, 0, 0, 0);
    run("known-ASCII", "ab", "xy", "abxy", ascii, 2, 2, 1, 1, 0, 0, 0, 0);
    run("shared-fallback", "é🙂", "xy", "é🙂xy", mixed, 2, 2, 1, 1, 0, 1, 0, 0);
    run("view-fallback", "é🙂", "xy", "é🙂xy", mixed, 2, 2, 1, 1, 0, 0, 0, 1);
    long_breadcrumb_boundary();
    puts("PASS independent slice-first Unicode/ownership/index-boundary controls");
    return 0;
}
