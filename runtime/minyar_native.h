/*
 * Shared definitions for standard library packages implemented in C.
 * Minyar programs never include this header: a library function whose body is
 * `native "name"` calls minyar_<name>_<function>. Integer is long long, Float is
 * double, Boolean is bool, Character is int, and Text and Bytes arrive as
 * borrowed pointers. Returned Text and Bytes must be owned references created
 * through the runtime, for example with minyar_bytes_new.
 */
#ifndef MINYAR_NATIVE_H
#define MINYAR_NATIVE_H

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Must match MinyarText in minyar_runtime.c. Bytes share the layout. */
typedef struct MinyarText {
    const unsigned char *bytes;
    long long byte_length;
    long long character_length;
    void *character_offsets;
    struct MinyarText *backing;
} MinyarText;
typedef MinyarText MinyarBytes;

MinyarBytes *minyar_bytes_new(long long length);

static inline void minyar_native_stop(const char *message) {
    fprintf(stderr, "Minyar stopped: %s\n", message);
    exit(1);
}

/* Copy Text into a caller-provided C string, truncating if necessary. */
static inline void minyar_native_text(const MinyarText *text, char *out, size_t capacity) {
    size_t length = (size_t)text->byte_length;
    if (length >= capacity) length = capacity - 1;
    memcpy(out, text->bytes, length);
    out[length] = 0;
}

#endif
