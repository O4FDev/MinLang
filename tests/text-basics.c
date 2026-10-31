/* Public contracts and ownership, independent of the implementation helpers. */
#define MINYAR_RC_TESTING 1
#define MINYAR_INTEGER_TEXT_CACHE_LIMIT 0
#ifdef TEXT_TEST_CYCLES
#include "../build/managed-graphs-engine.c"
#else
#include "../runtime/minyar_runtime.c"
#endif
#include <assert.h>

static void drain(void) {
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count) minyar_rc_poll(1024);
#endif
#if defined(TEXT_TEST_CYCLES) && !defined(MINYAR_COMPILER_ARENA) && !defined(MINYAR_BOUNDED_RC)
    while (rc_cycle_pending) rc_cycle_eager_service(1024);
#endif
}
static long long slot(void *p) { return (long long)(uintptr_t)p; }
static MinyarText *hex_text(const char *hex) {
    size_t n = strlen(hex);
    assert(n % 2 == 0);
    unsigned char *bytes = new_bytes((long long)n / 2);
    for (size_t i = 0; i < n; i += 2) {
        unsigned value;
        assert(sscanf(hex + i, "%2x", &value) == 1);
        bytes[i / 2] = (unsigned char)value;
    }
    bytes[n / 2] = 0;
    return new_text(bytes, (long long)n / 2, -1);
}
static void print_hex(const MinyarText *text) {
    for (long long i = 0; i < text->byte_length; i++) printf("%02x", text->bytes[i]);
}
static void ownership(void) {
    MinyarList *values = minyar_list_new(), *alias = values;
    minyar_rc_retain(alias);
    for (int i = 0; i < 200; i++) minyar_list_add(values, i);
    long long capacity = values->capacity;
    long long *storage = values->values;
    minyar_list_clear(values);
    assert(alias->length == 0 && values->capacity == capacity && values->values == storage);
    minyar_list_clear(values);
    minyar_list_add(values, 42);
    assert(minyar_list_get(alias, 0) == 42);
    minyar_rc_release(alias);
    minyar_rc_release(values);
    drain();
    /* Mutable Bytes conversions and slices retain their copying contract. */
    MinyarBytes *raw = minyar_bytes_new(3);
    memcpy((void *)raw->bytes, "a:b", 3);
    MinyarText *text = minyar_bytes_text(raw);
    MinyarBytes *copied = minyar_bytes_slice(raw, 0, 3);
    ((unsigned char *)raw->bytes)[0] = 'z';
    assert(text->bytes[0] == 'a' && copied->bytes[0] == 'a');
    minyar_rc_release(raw);
    minyar_rc_release(copied);
    MinyarText *colon = copy_c_text(":");
    MinyarList *parts = minyar_text_split(text, colon);
    MinyarText *first = (MinyarText *)(uintptr_t)parts->values[0];
    assert(first->byte_length == 1 && first->bytes[0] == 'a');
    minyar_rc_release(text); minyar_rc_release(colon); minyar_rc_release(parts);
    drain();
    values = minyar_list_new();
    minyar_list_references(values);
    text = copy_c_text("owned");
    minyar_list_add(values, slot(text));
    minyar_list_add(values, slot(text));
    minyar_list_add(values, 0);
    minyar_list_clear(values);
    drain();
    assert(text->byte_length == 5 && !memcmp(text->bytes, "owned", 5));
    minyar_rc_release(text);
    /* Clear also releases transferred references and nested Lists. */
    MinyarList *inner = minyar_list_new();
    minyar_list_references(inner);
    minyar_list_add_take(inner, slot(copy_c_text("nested")));
    minyar_list_add_take(values, slot(inner));
    minyar_list_clear(values);
    minyar_list_add_take(values, slot(copy_c_text("reuse")));
    minyar_list_clear(values);
    minyar_rc_release(values);
    drain();
#ifdef TEXT_TEST_CYCLES
    values = minyar_list_new_traced();
    MinyarList *other = minyar_list_new_traced();
    minyar_list_add_traced(values, slot(other));
    minyar_list_add_traced(other, slot(values));
    minyar_rc_release(other);
    minyar_list_clear(values);
    assert(values->length == 0);
    minyar_list_add_traced(values, slot(values));
    minyar_list_clear(values);
    minyar_rc_release(values);
    drain();
    /* Clear a wide traced graph while K1/K32 service interleaves scans with
     * edge removals. An externally retained child must survive intact. */
    values = minyar_list_new_traced();
    MinyarList *survivor = NULL;
    minyar_rc_enable_cycles();
    for (int i = 0; i < 257; i++) {
        other = minyar_list_new_traced();
        minyar_list_add_traced(other, slot(other));
        minyar_list_add_take_traced(values, slot(other));
        if (i == 128) { survivor = other; minyar_rc_retain_traced(survivor); }
    }
    capacity = values->capacity;
    storage = values->values;
    minyar_list_clear(values);
    drain();
    assert(values->length == 0 && values->capacity == capacity && values->values == storage);
    assert(survivor->length == 1 && survivor->values[0] == slot(survivor));
    minyar_list_clear(survivor);
    minyar_rc_release(survivor);
    minyar_rc_release(values);
    drain();
#endif
#ifndef MINYAR_COMPILER_ARENA
    assert(rc_object_count == 0 && rc_bytes == 0);
#endif
}
/* The List-free `for piece in text.split(needle)` step yields exactly split's
 * pieces. With nothing kept the loop's view is re-pointed in place; kept
 * pieces stay intact after the loop moves past them. */
static void check_split_iteration(MinyarText *text, MinyarText *needle, const MinyarList *parts) {
    for (int keep = 0; keep < 2; keep++) {
        MinyarList *kept = minyar_list_new();
        minyar_list_references(kept);
        MinyarText *previous = NULL, *piece;
        long long cursor = 0, count = 0;
        while ((piece = minyar_text_split_next(text, needle, &cursor, previous))) {
            assert(count < parts->length);
            const MinyarText *expected = (const MinyarText *)(uintptr_t)parts->values[count];
            assert(piece->byte_length == expected->byte_length &&
                   !memcmp(piece->bytes, expected->bytes, (size_t)piece->byte_length));
            assert(minyar_text_length(piece) == minyar_text_length((MinyarText *)expected));
#ifndef MINYAR_COMPILER_ARENA
            assert(keep || !previous || piece == previous);
#endif
            if (keep) minyar_list_add(kept, slot(piece));
            minyar_rc_release(previous);
            previous = piece;
            count++;
        }
        assert(count == parts->length && cursor == -1);
        assert(!minyar_text_split_next(text, needle, &cursor, previous));
        minyar_rc_release(previous);
        for (long long i = 0; i < kept->length; i++) {
            const MinyarText *expected = (const MinyarText *)(uintptr_t)parts->values[i];
            const MinyarText *held = (const MinyarText *)(uintptr_t)kept->values[i];
            assert(held->byte_length == expected->byte_length &&
                   !memcmp(held->bytes, expected->bytes, (size_t)held->byte_length));
        }
        minyar_rc_release(kept);
    }
}
#ifndef MINYAR_COMPILER_ARENA
/* Kept tiny pieces of a large Text get their own bytes once the loop moves
 * past them or finishes, so they do not keep the whole source alive. */
static void split_iteration_compaction(void) {
    enum { WORDS = 2000 };
    unsigned char *bytes = new_bytes(WORDS * 4);
    for (int i = 0; i < WORDS; i++) memcpy(bytes + i * 4, "abc,", 4);
    bytes[WORDS * 4] = 0;
    MinyarText *text = new_text(bytes, WORDS * 4, WORDS * 4), *comma = copy_c_text(",");
    MinyarList *kept = minyar_list_new();
    minyar_list_references(kept);
    MinyarText *previous = NULL, *piece;
    long long cursor = 0;
    while ((piece = minyar_text_split_next(text, comma, &cursor, previous))) {
        if (piece->byte_length) minyar_list_add(kept, slot(piece));
        minyar_rc_release(previous);
        previous = piece;
    }
    minyar_rc_release(previous);
    assert(kept->length == WORDS);
    for (long long i = 0; i < kept->length; i++) {
        const MinyarText *held = (const MinyarText *)(uintptr_t)kept->values[i];
        assert(!held->backing && held->byte_length == 3 && !memcmp(held->bytes, "abc", 3));
    }
    /* The source dies with its last owner: no kept piece still retains it. */
    assert(((RcObject *)text - 1)->ownership == (8 | RC_TEXT));
    minyar_rc_release(text);
    minyar_rc_release(comma);
    minyar_rc_release(kept);
    drain();
}
#endif
/* Short needles (no table) and long ones (KMP) find the same first match,
 * including overlapping prefixes, matches at either end and the size limit. */
static void search_lengths(void) {
    char text[200], needle[40];
    for (int size = 2; size <= 20; size++) {
        int length = 3 * size + 7;
        for (int i = 0; i < length; i++) text[i] = 'a';
        text[length] = 0;
        for (int i = 0; i < size; i++) needle[i] = 'a';
        needle[size - 1] = 'b';
        needle[size] = 0;
        for (int at = 0; at + size <= length; at += size + 1) {
            text[at + size - 1] = 'b';
            MinyarText *haystack = copy_c_text(text), *wanted = copy_c_text(needle);
            assert(minyar_text_find(haystack, wanted) == at);
            assert(minyar_text_contains(haystack, wanted));
            MinyarList *parts = minyar_text_split(haystack, wanted);
            assert(parts->length == 2);
            minyar_rc_release(parts);
            minyar_rc_release(haystack);
            minyar_rc_release(wanted);
            text[at + size - 1] = 'a';
        }
        MinyarText *haystack = copy_c_text(text), *wanted = copy_c_text(needle);
        assert(minyar_text_find(haystack, wanted) == -1);
        minyar_rc_release(haystack);
        minyar_rc_release(wanted);
        drain();
    }
}
int main(int argc, char **argv) {
    if (argc == 4) {
        MinyarText *text = hex_text(argv[2]), *needle = hex_text(argv[3]);
        if (!strcmp(argv[1], "integer")) printf("%lld\n", minyar_text_integer(text));
        else if (!strcmp(argv[1], "find")) printf("%lld\n", minyar_text_find(text, needle));
        else if (!strcmp(argv[1], "starts")) printf("%d\n", minyar_text_starts_with(text, needle));
        else if (!strcmp(argv[1], "ends")) printf("%d\n", minyar_text_ends_with(text, needle));
        else if (!strcmp(argv[1], "trim")) minyar_rc_release(minyar_text_trim(text));
        else if (!strcmp(argv[1], "split")) minyar_rc_release(minyar_text_split(text, needle));
        else assert(0);
        minyar_rc_release(text); minyar_rc_release(needle);
        drain();
        return 0;
    }
    ownership();
    search_lengths();
#ifndef MINYAR_COMPILER_ARENA
    split_iteration_compaction();
    assert(rc_object_count == 0 && rc_bytes == 0);
#endif
    /* Streaming model protocol avoids process startup for each random case. */
    char line[8192], left[4096], right[4096];
    while (fgets(line, sizeof(line), stdin)) {
        assert(sscanf(line, "%4095s %4095s", left, right) == 2);
        MinyarText *text = hex_text(!strcmp(left, "-") ? "" : left);
        MinyarText *needle = hex_text(!strcmp(right, "-") ? "" : right);
        printf("%lld %d %d ", minyar_text_find(text, needle),
               minyar_text_starts_with(text, needle), minyar_text_ends_with(text, needle));
        MinyarText *trimmed = minyar_text_trim(text);
        print_hex(trimmed); printf("|");
        MinyarList *parts = minyar_text_split(text, needle);
        check_split_iteration(text, needle, parts);
        /* Keep pieces alive after releasing their receiver and separator. */
        minyar_rc_release(text); minyar_rc_release(needle);
        printf("%lld", parts->length);
        for (long long i = 0; i < parts->length; i++) {
            printf("|"); print_hex((MinyarText *)(uintptr_t)parts->values[i]);
        }
        printf("\n");
        minyar_rc_release(trimmed); minyar_rc_release(parts); drain();
#ifndef MINYAR_COMPILER_ARENA
        assert(rc_object_count == 0 && rc_bytes == 0);
#endif
    }
}
