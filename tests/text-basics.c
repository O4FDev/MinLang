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
