/* Exact Unicode normalization regressions and deterministic ordering budgets.
 * Link this test with unicode.c and unicode_data.c, defining the test macro
 * for all three translation units. Large inputs never use the slow oracle. */
#ifndef MINYAR_UNICODE_NORMALIZATION_TESTING
#error "compile the normalization probe and provider with MINYAR_UNICODE_NORMALIZATION_TESTING"
#endif
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <assert.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../runtime/minyar_native.h"
#define UTF8PROC_STATIC
#include "../vendor/utf8proc/utf8proc.h"

MinyarText *minyar_unicode_normalized(const MinyarText *source);
MinyarText *minyar_unicode_caseFold(const MinyarText *source);
void minyar_unicode_normalization_reset_work(void);
unsigned long long minyar_unicode_normalization_ordering_work(void);

static size_t live_texts;

/* The probe owns these copies explicitly; the existing Minyar fixtures retain
 * responsibility for runtime ownership contracts. Unused provider references
 * need only this small ABI, so no full runtime or heap profile is linked. */
MinyarBytes *minyar_bytes_new(long long length) {
    (void)length;
    fputs("normalization unexpectedly requested a Bytes result\n", stderr);
    abort();
}

MinyarText *minyar_native_copy_text(const unsigned char *bytes, long long length) {
    assert(length >= 0 && (uint64_t)length < SIZE_MAX);
    assert(bytes || length == 0);
    MinyarText *text = malloc(sizeof(*text));
    unsigned char *copy = malloc((size_t)length + 1);
    assert(text && copy);
    if (length) memcpy(copy, bytes, (size_t)length);
    copy[length] = 0;
    *text = (MinyarText){copy, length, -1, NULL, NULL};
    live_texts++;
    return text;
}

static void release_text(MinyarText *text) {
    assert(text && live_texts > 0);
    free((void *)text->bytes);
    free(text);
    live_texts--;
}

typedef struct {
    unsigned char *bytes;
    size_t length, capacity;
} Buffer;

static Buffer buffer_new(size_t scalars) {
    assert(scalars <= (SIZE_MAX - 1) / 4);
    size_t capacity = scalars * 4 + 1;
    unsigned char *bytes = malloc(capacity);
    assert(bytes);
    bytes[0] = 0;
    return (Buffer){bytes, 0, capacity};
}

static void buffer_add(Buffer *buffer, uint32_t scalar) {
    unsigned char bytes[4];
    utf8proc_ssize_t width = utf8proc_encode_char((utf8proc_int32_t)scalar, bytes);
    assert(width > 0 && width <= 4);
    assert(buffer->length + (size_t)width < buffer->capacity);
    memcpy(buffer->bytes + buffer->length, bytes, (size_t)width);
    buffer->length += (size_t)width;
    buffer->bytes[buffer->length] = 0;
}

static Buffer from_scalars(const uint32_t *scalars, size_t count) {
    Buffer result = buffer_new(count);
    for (size_t index = 0; index < count; index++) buffer_add(&result, scalars[index]);
    return result;
}

static MinyarText borrowed(const Buffer *buffer) {
    assert(buffer->length <= LLONG_MAX);
    return (MinyarText){buffer->bytes, (long long)buffer->length, -1, NULL, NULL};
}

static void matches(const char *name, const MinyarText *actual,
                    const unsigned char *expected, size_t length) {
    assert(actual && actual->byte_length >= 0);
    if ((uint64_t)actual->byte_length != length || memcmp(actual->bytes, expected, length)) {
        size_t first = 0;
        while (first < length && first < (size_t)actual->byte_length &&
               actual->bytes[first] == expected[first]) first++;
        fprintf(stderr, "%s: expected %zu bytes, got %lld; first difference at byte %zu\n",
                name, length, actual->byte_length, first);
        abort();
    }
    assert(actual->bytes[length] == 0);
}

static size_t exact_count;
static void exact(const char *name, const uint32_t *input, size_t input_count,
                  const uint32_t *nfc, size_t nfc_count,
                  const uint32_t *fold, size_t fold_count) {
    Buffer source = from_scalars(input, input_count);
    Buffer expected_nfc = from_scalars(nfc, nfc_count);
    Buffer expected_fold = from_scalars(fold, fold_count);
    MinyarText source_text = borrowed(&source);
    MinyarText *normalized = minyar_unicode_normalized(&source_text);
    MinyarText *folded = minyar_unicode_caseFold(&source_text);
    matches(name, normalized, expected_nfc.bytes, expected_nfc.length);
    matches(name, folded, expected_fold.bytes, expected_fold.length);
    MinyarText *again = minyar_unicode_normalized(normalized);
    matches("NFC idempotence", again, expected_nfc.bytes, expected_nfc.length);
    release_text(again);
    again = minyar_unicode_caseFold(folded);
    matches("fold idempotence", again, expected_fold.bytes, expected_fold.length);
    release_text(again);
    release_text(normalized);
    release_text(folded);
    free(source.bytes);
    free(expected_nfc.bytes);
    free(expected_fold.bytes);
    assert(live_texts == 0);
    exact_count++;
}

#define SCALARS(...) (const uint32_t[]){__VA_ARGS__}, \
    sizeof((const uint32_t[]){__VA_ARGS__}) / sizeof(uint32_t)

static void exact_regressions(void) {
    exact("empty", NULL, 0, NULL, 0, NULL, 0);
    /* q has no canonical composite with these marks. Classes 220, 230 and
     * 232 must sort ascending while distinct equal-class marks stay stable. */
    exact("stable equal classes",
          SCALARS(0x71, 0x315, 0x301, 0x31A, 0x300, 0x305, 0x323, 0x324),
          SCALARS(0x71, 0x323, 0x324, 0x301, 0x300, 0x305, 0x315, 0x31A),
          SCALARS(0x71, 0x323, 0x324, 0x301, 0x300, 0x305, 0x315, 0x31A));
    exact("leading marks have no starter",
          SCALARS(0x315, 0x301, 0x31A, 0x323, 0x300),
          SCALARS(0x323, 0x301, 0x300, 0x315, 0x31A),
          SCALARS(0x323, 0x301, 0x300, 0x315, 0x31A));
    exact("NUL and CGJ are zero-class barriers",
          SCALARS(0x71, 0x315, 0x300, 0, 0x315, 0x323, 0x34F, 0x315, 0x301),
          SCALARS(0x71, 0x300, 0x315, 0, 0x323, 0x315, 0x34F, 0x301, 0x315),
          SCALARS(0x71, 0x300, 0x315, 0, 0x323, 0x315, 0x34F, 0x301, 0x315));
    exact("equal class blocks composition",
          SCALARS(0x41, 0x305, 0x301), SCALARS(0x41, 0x305, 0x301),
          SCALARS(0x61, 0x305, 0x301));
    exact("CGJ blocks Latin composition",
          SCALARS(0x41, 0x34F, 0x30A), SCALARS(0x41, 0x34F, 0x30A),
          SCALARS(0x61, 0x34F, 0x30A));
    exact("Hangul composition", SCALARS(0x1100, 0x1161, 0x11A8),
          SCALARS(0xAC01), SCALARS(0xAC01));
    exact("two zero-class Bengali vowel signs compose",
          SCALARS(0x9C7, 0x9BE), SCALARS(0x9CB), SCALARS(0x9CB));
    exact("NUL blocks Hangul trailing composition",
          SCALARS(0x1100, 0x1161, 0, 0x11A8),
          SCALARS(0xAC00, 0, 0x11A8), SCALARS(0xAC00, 0, 0x11A8));
    exact("CGJ blocks Hangul vowel composition",
          SCALARS(0x1100, 0x34F, 0x1161, 0x11A8),
          SCALARS(0x1100, 0x34F, 0x1161, 0x11A8),
          SCALARS(0x1100, 0x34F, 0x1161, 0x11A8));
    exact("composition exclusion", SCALARS(0x344),
          SCALARS(0x308, 0x301), SCALARS(0x308, 0x301));
    exact("decomposition expands before ordering",
          SCALARS(0x71, 0x344, 0x323),
          SCALARS(0x71, 0x323, 0x308, 0x301),
          SCALARS(0x71, 0x323, 0x308, 0x301));
    exact("pre-fold ordering of ypogegrammeni",
          SCALARS(0x61, 0x345, 0x300),
          SCALARS(0xE0, 0x345), SCALARS(0xE0, 0x3B9));
    exact("recursive composition", SCALARS(0x41, 0x30A, 0x301),
          SCALARS(0x1FA), SCALARS(0x1FB));
    exact("canonical singleton decomposition", SCALARS(0x212B),
          SCALARS(0xC5), SCALARS(0xE5));
}
#undef SCALARS

static uint32_t random_state = UINT32_C(0x6d2b79f5);
static uint32_t next_random(void) {
    random_state ^= random_state << 13;
    random_state ^= random_state >> 17;
    random_state ^= random_state << 5;
    return random_state;
}

static void bounded_differential(void) {
    static const uint32_t pool[] = {
        0, 0x41, 0x71, 0x53, 0x65, 0xDF, 0x130, 0x3A3, 0x3C2,
        0x300, 0x301, 0x305, 0x315, 0x31A, 0x323, 0x324, 0x334, 0x344,
        0x345, 0x34F, 0x5B0, 0x5B1, 0x5B4, 0x5C4, 0x64B, 0x651,
        0x93C, 0x94D, 0x9C7, 0x9BE, 0x9CB, 0x1F88, 0x1E9B, 0x212B, 0xFB03, 0x1100,
        0x1161, 0x11A8, 0xAC00, 0x1F469, 0x200D, 0x1D165, 0x1D15E,
        0xFDD0, 0x10FFFF};
    for (unsigned iteration = 0; iteration < 2048; iteration++) {
        size_t count = next_random() % 97;
        Buffer source = buffer_new(count);
        for (size_t index = 0; index < count; index++) {
            uint32_t scalar;
            if (next_random() % 4) scalar = pool[next_random() % (sizeof(pool) / sizeof(*pool))];
            else {
                do { scalar = next_random() % UINT32_C(0x110000); }
                while (scalar >= 0xD800 && scalar <= 0xDFFF);
            }
            buffer_add(&source, scalar);
        }
        unsigned char original[96 * 4 + 1];
        memcpy(original, source.bytes, source.length + 1);
        unsigned char *expected_nfc, *decomposed, *expected_fold;
        utf8proc_ssize_t nfc_length = utf8proc_map(source.bytes, (utf8proc_ssize_t)source.length,
            &expected_nfc, UTF8PROC_COMPOSE | UTF8PROC_STABLE);
        utf8proc_ssize_t nfd_length = utf8proc_map(source.bytes, (utf8proc_ssize_t)source.length,
            &decomposed, UTF8PROC_DECOMPOSE | UTF8PROC_STABLE);
        assert(nfc_length >= 0 && nfd_length >= 0);
        utf8proc_ssize_t fold_length = utf8proc_map(decomposed, nfd_length, &expected_fold,
            UTF8PROC_CASEFOLD | UTF8PROC_COMPOSE | UTF8PROC_STABLE);
        assert(fold_length >= 0);
        MinyarText input = borrowed(&source);
        MinyarText *normalized = minyar_unicode_normalized(&input);
        MinyarText *folded = minyar_unicode_caseFold(&input);
        char name[64];
        snprintf(name, sizeof(name), "random NFC vector %u", iteration);
        matches(name, normalized, expected_nfc, (size_t)nfc_length);
        snprintf(name, sizeof(name), "random fold vector %u", iteration);
        matches(name, folded, expected_fold, (size_t)fold_length);
        assert(!memcmp(source.bytes, original, source.length + 1));
        release_text(normalized);
        release_text(folded);
        utf8proc_free(expected_nfc);
        utf8proc_free(decomposed);
        utf8proc_free(expected_fold);
        free(source.bytes);
        assert(live_texts == 0);
    }
}

typedef MinyarText *(*Transform)(const MinyarText *);
static unsigned long long measured(const char *name, const Buffer *source,
                                   const Buffer *expected, Transform transform,
                                   unsigned long long minimum, unsigned long long maximum) {
    unsigned char *original = malloc(source->length + 1);
    assert(original);
    memcpy(original, source->bytes, source->length + 1);
    MinyarText input = borrowed(source);
    minyar_unicode_normalization_reset_work();
    MinyarText *result = transform(&input);
    unsigned long long work = minyar_unicode_normalization_ordering_work();
    matches(name, result, expected->bytes, expected->length);
    assert(!memcmp(source->bytes, original, source->length + 1));
    free(original);
    if (work < minimum || work > maximum) {
        fprintf(stderr, "%s: ordering work %llu outside [%llu, %llu]\n", name, work,
                minimum, maximum);
        abort();
    }
    release_text(result);
    return work;
}

static void adversarial_marks(Buffer *source, Buffer *expected, size_t marks) {
    size_t high = marks / 2, low = marks - high;
    /* Alternation within each class makes the stability oracle observable.
     * This input has quadratic inversion count but only one ordering run. */
    for (size_t index = 0; index < high; index++) buffer_add(source, index % 2 ? 0x31A : 0x315);
    for (size_t index = 0; index < low; index++) buffer_add(source, index % 2 ? 0x324 : 0x323);
    for (size_t index = 0; index < low; index++) buffer_add(expected, index % 2 ? 0x324 : 0x323);
    for (size_t index = 0; index < high; index++) buffer_add(expected, index % 2 ? 0x31A : 0x315);
}

static void long_adversarial(size_t marks) {
    Buffer source = buffer_new(marks + 1), expected = buffer_new(marks + 1);
    buffer_add(&source, 0x71);
    buffer_add(&expected, 0x71);
    adversarial_marks(&source, &expected, marks);
    unsigned long long scalars = (unsigned long long)marks + 1;
    unsigned long long normal_work = measured("long NFC", &source, &expected,
        minyar_unicode_normalized, marks, 12 * scalars + 1024);
    unsigned long long fold_work = measured("long fold", &source, &expected,
        minyar_unicode_caseFold, 2 * (unsigned long long)marks, 24 * scalars + 2048);
    printf("{\"marks\":%zu,\"runs\":1,\"nfc_ordering_work\":%llu,\"fold_ordering_work\":%llu}\n",
           marks, normal_work, fold_work);
    free(source.bytes);
    free(expected.bytes);
}

static void many_short_runs(size_t runs) {
    Buffer source = buffer_new(runs * 5), expected = buffer_new(runs * 5);
    for (size_t index = 0; index < runs; index++) {
        uint32_t barrier = index % 3 == 0 ? 0 : index % 3 == 1 ? 0x34F : 0x71;
        buffer_add(&source, barrier);
        buffer_add(&source, 0x315);
        buffer_add(&source, 0x301);
        buffer_add(&source, 0x31A);
        buffer_add(&source, 0x323);
        buffer_add(&expected, barrier);
        buffer_add(&expected, 0x323);
        buffer_add(&expected, 0x301);
        buffer_add(&expected, 0x315);
        buffer_add(&expected, 0x31A);
    }
    unsigned long long scalars = 5 * (unsigned long long)runs;
    unsigned long long budget = 36 * scalars + 2;
    unsigned long long normal_work = measured("short-run NFC", &source, &expected,
        minyar_unicode_normalized, 4 * (unsigned long long)runs, budget);
    unsigned long long fold_work = measured("short-run fold", &source, &expected,
        minyar_unicode_caseFold, 8 * (unsigned long long)runs, 2 * budget);
    printf("{\"scalars\":%llu,\"runs\":%zu,\"nfc_ordering_work\":%llu,\"fold_ordering_work\":%llu}\n",
           scalars, runs, normal_work, fold_work);
    free(source.bytes);
    free(expected.bytes);
}

static void mixed_runs(void) {
    static const size_t lengths[] = {3, 16, 17, 128, 2};
    static const uint32_t barriers[] = {0x71, 0, 0x34F, 0x71, 0};
    size_t runs = sizeof(lengths) / sizeof(*lengths), marks = 0;
    assert(runs == sizeof(barriers) / sizeof(*barriers));
    for (size_t index = 0; index < runs; index++) marks += lengths[index];
    Buffer source = buffer_new(marks + runs), expected = buffer_new(marks + runs);
    for (size_t index = 0; index < runs; index++) {
        buffer_add(&source, barriers[index]);
        buffer_add(&expected, barriers[index]);
        adversarial_marks(&source, &expected, lengths[index]);
    }
    /* One map shares the large-run scratch between 17 and 128 marks while
     * insertion sorting smaller runs before and after those counting sorts. */
    unsigned long long scalars = (unsigned long long)marks + runs;
    unsigned long long budget = 36 * scalars + 2;
    unsigned long long normal_work = measured("mixed-run NFC", &source, &expected,
        minyar_unicode_normalized, marks, budget);
    unsigned long long fold_work = measured("mixed-run fold", &source, &expected,
        minyar_unicode_caseFold, 2 * (unsigned long long)marks, 2 * budget);
    printf("{\"mixed\":true,\"scalars\":%llu,\"runs\":%zu,\"nfc_ordering_work\":%llu,\"fold_ordering_work\":%llu}\n",
           scalars, runs, normal_work, fold_work);
    free(source.bytes);
    free(expected.bytes);
}

int main(void) {
    exact_regressions();
    bounded_differential();
    static const size_t sizes[] = {14, 15, 16, 17, 18, 32, 1024, 4096, 16384, 65536, 131072};
    for (size_t index = 0; index < sizeof(sizes) / sizeof(*sizes); index++) long_adversarial(sizes[index]);
    many_short_runs(2048);
    mixed_runs();
    assert(live_texts == 0);
    printf("Unicode normalization: %zu exact and 2048 bounded differential vectors; linear ordering budgets passed\n",
           exact_count);
    return 0;
}
