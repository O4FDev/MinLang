/* Small native contract fixtures avoid building the compiler/runtime. */
#include "../runtime/minyar_native.h"
#include <assert.h>
#include <stdint.h>
static MinyarText test_text(const char *value) {
    MinyarText text = {(const unsigned char *)value, (long long)strlen(value), 0, NULL, NULL};
    return text;
}
MinyarBytes *minyar_bytes_new(long long length) {
    assert(length >= 0);
    MinyarBytes *value = calloc(1, sizeof(*value));
    assert(value);
    value->bytes = calloc((size_t)length + 1, 1);
    assert(value->bytes);
    value->byte_length = value->character_length = length;
    return value;
}
MinyarText *minyar_native_copy_text(const unsigned char *bytes, long long length) {
    MinyarText *value = minyar_bytes_new(length);
    if (length) memcpy((void *)value->bytes, bytes, (size_t)length);
    return value;
}
unsigned char *minyar_bytes_extend(MinyarBytes *value, long long count) {
    long long before = value->byte_length;
    unsigned char *bytes = realloc((void *)value->bytes, (size_t)(before + count) + 1);
    assert(bytes);
    memset(bytes + before, 0, (size_t)count + 1);
    value->bytes = bytes;
    value->byte_length = value->character_length = before + count;
    return bytes + before;
}
static void test_release(MinyarText *value) { free((void *)value->bytes); free(value); }
