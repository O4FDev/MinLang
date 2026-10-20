/* Optional Unicode provider. Ordinary Text never links the property tables.
 * All inputs are length-delimited, including embedded U+0000. */
#include "../minyar_native.h"
#include <stdint.h>
#include <limits.h>
#define UTF8PROC_STATIC
#include "../../vendor/utf8proc/utf8proc.c"

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
