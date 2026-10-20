/* Optional Unicode provider. Ordinary Text never links the property tables.
 * All inputs are length-delimited, including embedded U+0000. */
#include "../minyar_native.h"
#include <stdint.h>
#include <limits.h>
#define UTF8PROC_STATIC
#include "../../vendor/utf8proc/utf8proc.h"
#include "unicode_case_data.h"

static utf8proc_ssize_t unicode_length(const MinyarText *source) {
    if (source->byte_length < 0 || (uint64_t)source->byte_length > PTRDIFF_MAX)
        minyar_native_stop("the Text is too large for Unicode processing.");
    return (utf8proc_ssize_t)source->byte_length;
}

static utf8proc_int32_t unicode_next(const MinyarText *source, utf8proc_ssize_t *position) {
    utf8proc_int32_t scalar;
    utf8proc_ssize_t width = utf8proc_iterate(source->bytes + *position,
                                             unicode_length(source) - *position, &scalar);
    if (width <= 0) minyar_native_stop("Text contained invalid UTF-8.");
    *position += width;
    return scalar;
}

MinyarText *minyar_unicode_unicodeVersion(void) {
    const char *version = utf8proc_unicode_version();
    return minyar_native_copy_text((const unsigned char *)version, (long long)strlen(version));
}

/* Used twice for the bitmap: first to size it, then to fill it. Count-only
 * callers allocate nothing and do not populate Text's scalar index cache. */
static long long unicode_clusters(const MinyarText *source, unsigned char *marks,
                                  long long *scalar_count) {
    utf8proc_ssize_t position = 0, length = unicode_length(source);
    utf8proc_int32_t previous = 0, state = 0;
    long long count = 0, scalars = 0;
    while (position < length) {
        utf8proc_int32_t current = unicode_next(source, &position);
        bool boundary = scalars == 0 || utf8proc_grapheme_break_stateful(previous, current, &state);
        if (boundary) count++;
        if (marks) marks[scalars] = (unsigned char)boundary;
        previous = current;
        scalars++;
    }
    if (marks) marks[scalars] = 1;
    if (scalar_count) *scalar_count = scalars;
    return count;
}

long long minyar_unicode_graphemeCount(const MinyarText *source) {
    return unicode_clusters(source, NULL, NULL);
}

MinyarBytes *minyar_unicode_unicodeBoundaries(const MinyarText *source) {
    long long scalars;
    unicode_clusters(source, NULL, &scalars);
    if (scalars == LLONG_MAX) minyar_native_stop("the Text has too many grapheme boundaries.");
    MinyarBytes *marks = minyar_bytes_new(scalars + 1);
    unicode_clusters(source, (unsigned char *)marks->bytes, NULL);
    return marks;
}

static utf8proc_ssize_t unicode_map(const unsigned char *source, utf8proc_ssize_t length,
                                   unsigned char **output, unsigned int options) {
    utf8proc_ssize_t result = utf8proc_map(source, length, output, options | UTF8PROC_STABLE);
    if (result < 0) minyar_native_stop(utf8proc_errmsg(result));
    return result;
}

MinyarText *minyar_unicode_normalized(const MinyarText *source) {
    unsigned char *output;
    utf8proc_ssize_t length = unicode_map(source->bytes, unicode_length(source), &output, UTF8PROC_COMPOSE);
    MinyarText *result = minyar_native_copy_text(output, (long long)length);
    utf8proc_free(output);
    return result;
}

MinyarText *minyar_unicode_caseFold(const MinyarText *source) {
    /* Unicode canonical caseless matching requires decomposition BEFORE
     * folding too (D145). In particular U+0345 must be reordered before it
     * becomes a spacing iota. A single CASEFOLD|COMPOSE pass is insufficient. */
    unsigned char *decomposed, *output;
    utf8proc_ssize_t length = unicode_map(source->bytes, unicode_length(source), &decomposed, UTF8PROC_DECOMPOSE);
    length = unicode_map(decomposed, length, &output, UTF8PROC_CASEFOLD | UTF8PROC_COMPOSE);
    utf8proc_free(decomposed);
    MinyarText *result = minyar_native_copy_text(output, (long long)length);
    utf8proc_free(output);
    return result;
}

static bool unicode_case_property(uint32_t scalar, const UnicodeCaseRange *ranges, size_t count) {
    size_t first = 0, after = count;
    while (first < after) {
        size_t middle = first + (after - first) / 2;
        if (scalar < ranges[middle].first) after = middle;
        else if (scalar > ranges[middle].last) first = middle + 1;
        else return true;
    }
    return false;
}

#define UNICODE_CASE_PROPERTY(scalar, name) \
    unicode_case_property((uint32_t)(scalar), unicode_##name##_ranges, \
                          sizeof(unicode_##name##_ranges) / sizeof(unicode_##name##_ranges[0]))

static const UnicodeCaseMapping *unicode_case_mapping(uint32_t scalar) {
    size_t first = 0, after = sizeof(unicode_case_mappings) / sizeof(unicode_case_mappings[0]);
    while (first < after) {
        size_t middle = first + (after - first) / 2;
        if (scalar < unicode_case_mappings[middle].scalar) after = middle;
        else if (scalar > unicode_case_mappings[middle].scalar) first = middle + 1;
        else return &unicode_case_mappings[middle];
    }
    return NULL;
}

static bool unicode_following_cased(const MinyarText *source, utf8proc_ssize_t position) {
    while (position < unicode_length(source)) {
        utf8proc_int32_t scalar = unicode_next(source, &position);
        // Case_Ignorable takes precedence: U+0345 also has the Cased property.
        if (!UNICODE_CASE_PROPERTY(scalar, case_ignorable))
            return UNICODE_CASE_PROPERTY(scalar, cased);
    }
    return false;
}

/* Preserve the original scalar order: display casing does not normalize.
 * Only sigma needs lookahead. Its ignorable run ends before the next sigma,
 * so the lookahead runs do not overlap and each pass remains linear. */
static size_t unicode_case_pass(const MinyarText *source, bool upper, unsigned char *output) {
    utf8proc_ssize_t position = 0, length = unicode_length(source);
    size_t used = 0;
    bool preceding_cased = false;
    while (position < length) {
        utf8proc_int32_t scalar = unicode_next(source, &position);
        const UnicodeCaseMapping *special = unicode_case_mapping((uint32_t)scalar);
        uint32_t simple;
        const uint32_t *mapping;
        size_t count = 1;
        if (!upper && scalar == 0x3A3 && preceding_cased && !unicode_following_cased(source, position)) {
            simple = 0x3C2;
            mapping = &simple;
        } else if (special) {
            mapping = upper ? special->upper : special->lower;
            count = upper ? special->upper_count : special->lower_count;
        } else {
            simple = (uint32_t)(upper ? utf8proc_toupper(scalar) : utf8proc_tolower(scalar));
            mapping = &simple;
        }
        for (size_t index = 0; index < count; index++) {
            unsigned char bytes[4];
            size_t width = (size_t)utf8proc_encode_char((utf8proc_int32_t)mapping[index], bytes);
            if (width == 0 || used > (size_t)PTRDIFF_MAX - width)
                minyar_native_stop("the cased Text is too large.");
            if (output) memcpy(output + used, bytes, width);
            used += width;
        }
        if (!upper && !UNICODE_CASE_PROPERTY(scalar, case_ignorable))
            preceding_cased = UNICODE_CASE_PROPERTY(scalar, cased);
    }
    return used;
}

static MinyarText *unicode_case(const MinyarText *source, bool upper) {
    size_t length = unicode_case_pass(source, upper, NULL);
    unsigned char *output = malloc(length + 1);
    if (!output) minyar_native_stop("there is not enough memory for cased Text.");
    unicode_case_pass(source, upper, output);
    MinyarText *result = minyar_native_copy_text(output, (long long)length);
    free(output);
    return result;
}

MinyarText *minyar_unicode_uppercased(const MinyarText *source) { return unicode_case(source, true); }
MinyarText *minyar_unicode_lowercased(const MinyarText *source) { return unicode_case(source, false); }
#undef UNICODE_CASE_PROPERTY
