/* Compiler-arena-only Text cache: exact identity, eviction and immutable bytes. */
#define MINYAR_COMPILER_ARENA
#include "../runtime/minyar_runtime.c"
#include <assert.h>

int main(void) {
    MinyarText *first = copy_c_text("left identifier right");
    MinyarText *second = copy_c_text("identifier");
    MinyarText *a = minyar_text_slice(first, 5, 15);
    MinyarText *b = minyar_text_slice(second, 0, 10);
    assert(a == b); /* TDD: repeated byte-equal slices must avoid another header. */
    assert(a->byte_length == 10 && !memcmp(a->bytes, "identifier", 10));
    MinyarText *held = a;
    for (int i = 0; i < 20000; ++i) {
        char bytes[40];
        int n = snprintf(bytes, sizeof(bytes), "key%08d_value", i);
        MinyarText *source = copy_c_text(bytes);
        MinyarText *value = minyar_text_slice(source, 0, n);
        assert(value->byte_length == n && !memcmp(value->bytes, bytes, n));
    }
    assert(held->byte_length == 10 && !memcmp(held->bytes, "identifier", 10));
    /* Identical sampled bytes, different unsampled byte: a hash match is never equality. */
    MinyarText *collision1 = minyar_text_slice(copy_c_text("ab0defghij"), 0, 10);
    MinyarText *collision2 = minyar_text_slice(copy_c_text("ab1defghij"), 0, 10);
    assert(collision1 != collision2);
    assert(!memcmp(collision1->bytes, "ab0defghij", 10));
    assert(!memcmp(collision2->bytes, "ab1defghij", 10));
    MinyarText *unicode = copy_c_text("aé🙂z");
    MinyarText *u = minyar_text_slice(unicode, 1, 3);
    MinyarText *v = minyar_text_slice(copy_c_text("é🙂"), 0, 2);
    assert(u == v && minyar_text_length(u) == 2);
    assert(minyar_text_character_at(u, 0) == 0xe9);
    assert(minyar_text_character_at(v, 1) == 0x1f642);
    const unsigned char embedded[] = {'a', 0, 'b'};
    MinyarText *nul = minyar_text_slice(new_text(embedded, 3, 3), 0, 3);
    assert(nul->byte_length == 3 && !memcmp(nul->bytes, embedded, 3));
    MinyarText *base = copy_c_text("cat");
    MinyarText *slice = minyar_text_slice(base, 0, 3);
    MinyarText *joined = minyar_join_text(slice, copy_c_text("apult"));
    assert(joined->byte_length == 8 && !memcmp(joined->bytes, "catapult", 8));
    assert(slice->byte_length == 3 && !memcmp(slice->bytes, "cat", 3));
    /* Force an in-place join while a cached slice still denotes its prefix. */
    MinyarText suffix = {(const unsigned char *)"matic", 5, 5, NULL, NULL};
    MinyarText *dog = copy_c_text("dog");
    MinyarText *prefix = minyar_text_slice(dog, 0, 3);
    MinyarText *extended = minyar_join_text(prefix, &suffix);
    assert(extended->bytes == prefix->bytes);
    assert(extended->byte_length == 8 && !memcmp(extended->bytes, "dogmatic", 8));
    assert(prefix->byte_length == 3 && !memcmp(prefix->bytes, "dog", 3));
    assert(minyar_text_slice(copy_c_text("dog"), 0, 3) == prefix);
    char boundary_bytes[66];
    memset(boundary_bytes, 'q', 65);
    boundary_bytes[65] = 0;
    MinyarText *boundary = copy_c_text(boundary_bytes);
    assert(minyar_text_slice(boundary, 0, 64) == minyar_text_slice(boundary, 0, 64));
    assert(minyar_text_slice(boundary, 0, 65) != minyar_text_slice(boundary, 0, 65));
    assert(minyar_text_slice(boundary, 65, 65)->byte_length == 0);
    MinyarText *empty = minyar_text_slice(base, 1, 1);
    assert(empty->byte_length == 0);
    puts("compiler slice cache contracts pass");
    return 0;
}
