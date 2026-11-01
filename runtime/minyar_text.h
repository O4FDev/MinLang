#if defined(__SSE2__)
#include <emmintrin.h>
#endif
/* Text operations use validated UTF-8 and scalar positions. Every public
 * entry validates all Text operands before taking empty/length shortcuts. */
static long long text_scalar_count(const unsigned char *bytes, long long length) {
    long long count = 0, i = 0;
    /* Eight bytes at a time: a continuation byte has its top bits 10, so it
       has bit 7 set and bit 6 (shifted into bit 7) clear. */
    for (; length - i >= 8; i += 8) {
        uint64_t word;
        memcpy(&word, bytes + i, sizeof(word));
        count += 8 - __builtin_popcountll(word & ~(word << 1) & 0x8080808080808080ULL);
    }
    for (; i < length; i++) count += (bytes[i] & 0xc0) != 0x80;
    return count;
}

/* The first `wanted` byte at or after `start`, or `length`. Split pieces are
 * usually short: one eight-byte test finds most separators before the call
 * to memchr. Only the lowest flagged byte is exact, and it is the one used. */
static inline long long text_byte_find(const unsigned char *bytes, long long start, long long length,
                                       unsigned char wanted) {
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    if (length - start >= 8) {
        uint64_t word;
        memcpy(&word, bytes + start, sizeof(word));
        word ^= 0x0101010101010101ULL * wanted;
        uint64_t found = (word - 0x0101010101010101ULL) & ~word & 0x8080808080808080ULL;
        if (found) return start + (__builtin_ctzll(found) >> 3);
        start += 8;
    }
#endif
    const unsigned char *hit = memchr(bytes + start, wanted, (size_t)(length - start));
    return hit ? hit - bytes : length;
}
/* text_byte_find for a caller that walks a whole Text: the eight-byte search
 * stays where the last piece ended instead of restarting at each piece, so a
 * line of a few fields costs one word test per field and never a library
 * call. *cursor is the byte to search from and is left just past the byte
 * returned; the answer is `length` when no byte is left. */
static inline long long text_byte_scan(const unsigned char *bytes, long long length,
                                       unsigned char wanted, long long *cursor) {
    long long at = *cursor;
#if defined(__SSE2__)
    /* Sixteen bytes per test: a line of a few fields is two or three of them,
     * and the mask names the first separator directly. */
    __m128i wanted_vector = _mm_set1_epi8((char)wanted);
    while (length - at >= 16) {
        __m128i chunk = _mm_loadu_si128((const __m128i *)(const void *)(bytes + at));
        unsigned mask = (unsigned)_mm_movemask_epi8(_mm_cmpeq_epi8(chunk, wanted_vector));
        if (mask) {
            long long hit = at + (long long)__builtin_ctz(mask);
            *cursor = hit + 1;
            return hit;
        }
        at += 16;
    }
#endif
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    uint64_t spread = 0x0101010101010101ULL * wanted;
    while (length - at >= 8) {
        uint64_t word;
        memcpy(&word, bytes + at, sizeof(word));
        word ^= spread;
        uint64_t found = (word - 0x0101010101010101ULL) & ~word & 0x8080808080808080ULL;
        if (found) {
            long long hit = at + (__builtin_ctzll(found) >> 3);
            *cursor = hit < length ? hit + 1 : length;
            return hit;
        }
        at += 8;
    }
#endif
    /* At most seven bytes are left: testing them one at a time is cheaper
       than the call into the C library that text_byte_find would make. */
    while (at < length) {
        if (bytes[at] == wanted) {
            *cursor = at + 1;
            return at;
        }
        at++;
    }
    *cursor = length;
    return length;
}
/* KMP avoids quadratic scans of repeated prefixes. One table is reused for
 * all split matches; one-byte separators take the allocation-free path, and
 * needles of up to TEXT_SEARCH_SMALL bytes use the caller's stack table.
 * Needles of up to TEXT_SEARCH_SHORT bytes need no table at all: candidates
 * are found by their first byte and compared in place, at most that many
 * byte comparisons per text byte, so the search stays linear. */
enum { TEXT_SEARCH_SMALL = 32, TEXT_SEARCH_SHORT = 16 };
/* The table for a long needle. Nearly every search has a short needle, so
 * text_search_table decides that inline and only this build stays out of
 * line. */
static MINYAR_COLD long long *text_search_table_build(const MinyarText *needle,
                                                      long long small[TEXT_SEARCH_SMALL]) {
    long long length = needle->byte_length;
    if ((unsigned long long)length > SIZE_MAX / sizeof(long long))
        minyar_stop("the Text search pattern is too large.");
    long long *table = small;
    if (length > TEXT_SEARCH_SMALL) {
#ifdef MINYAR_COMPILER_ARENA
        /* The arena never frees, and the compiler searches Text constantly;
         * the table lives only for one search, so it comes from malloc. */
        table = malloc((size_t)length * sizeof(*table));
        if (!table)
            out_of_memory();
#else
        table = data_allocate((size_t)length * sizeof(*table), sizeof(*table));
#endif
    }
    table[0] = 0;
    for (long long i = 1, matched = 0; i < length; i++) {
        while (matched && needle->bytes[i] != needle->bytes[matched]) matched = table[matched - 1];
        if (needle->bytes[i] == needle->bytes[matched]) matched++;
        table[i] = matched;
    }
    return table;
}
static inline long long *text_search_table(const MinyarText *needle, long long available,
                                           long long small[TEXT_SEARCH_SMALL]) {
    long long length = needle->byte_length;
    if (length <= TEXT_SEARCH_SHORT || length > available) return NULL;
#if defined(__linux__) && defined(MINYAR_COMPILER_ARENA)
    /* text_search_next searches these with the C library's memmem, which
     * needs no table; building one for every search of an IR line was the
     * larger half of a self-compile's Text search time. */
    (void)small;
    return NULL;
#else
    return text_search_table_build(needle, small);
#endif
}
static inline void text_search_free(long long *table, const long long *small) {
    if (!table || table == small)
        return;
#ifndef MINYAR_COMPILER_ARENA
    rc_free_data(table);
#else
    free(table);
#endif
}
static long long text_search_next(const MinyarText *text, const MinyarText *needle,
                                  long long start, const long long *table) {
    if (needle->byte_length > text->byte_length - start) return -1;
    if (needle->byte_length == 1) {
        const unsigned char *found = memchr(text->bytes + start, needle->bytes[0],
                                           (size_t)(text->byte_length - start));
        return found ? found - text->bytes : -1;
    }
    if (needle->byte_length <= TEXT_SEARCH_SHORT) {
        const unsigned char *bytes = text->bytes, *wanted = needle->bytes;
        long long rest = needle->byte_length - 1, last = text->byte_length - needle->byte_length;
        for (long long i = start; i <= last;) {
            long long at = text_byte_find(bytes, i, last + 1, wanted[0]);
            if (at > last) return -1;
            if (bytes_are_equal(bytes + at + 1, wanted + 1, (size_t)rest)) return at;
            i = at + 1;
        }
        return -1;
    }
#if defined(__linux__) && defined(MINYAR_COMPILER_ARENA)
    /* The C library's memmem is vectorised and needs no table. The compiler
     * searches a few hundred thousand short IR lines for fixed patterns, and
     * building a table for each of those searches was a visible share of a
     * compile; its module-wide searches over tens of megabytes gain more than
     * the table search does. Programs keep the table search: their runtime
     * must stay the same code, and a long search over a long text is where
     * the table wins. */
    {
        const unsigned char *found =
            memmem(text->bytes + start, (size_t)(text->byte_length - start),
                   needle->bytes, (size_t)needle->byte_length);
        return found ? found - text->bytes : -1;
    }
#endif
    for (long long i = start, matched = 0; i < text->byte_length; i++) {
        while (matched && text->bytes[i] != needle->bytes[matched]) matched = table[matched - 1];
        if (text->bytes[i] == needle->bytes[matched]) {
            matched++;
        } else {
            /* No partial match remains: skip to the next possible first byte. */
            const unsigned char *next = memchr(text->bytes + i + 1, needle->bytes[0],
                                               (size_t)(text->byte_length - i - 1));
            if (!next) return -1;
            i = next - text->bytes - 1;
            continue;
        }
        if (matched == needle->byte_length) return i + 1 - matched;
    }
    return -1;
}

long long minyar_text_find(MinyarText *text, MinyarText *needle) {
    ensure_text_index(text);
    ensure_text_index(needle);
    if (!needle->byte_length) return 0;
    long long small[TEXT_SEARCH_SMALL];
    long long *table = text_search_table(needle, text->byte_length, small);
    long long byte = text_search_next(text, needle, 0, table);
    text_search_free(table, small);
    if (byte < 0) return -1;
    /* A counted Text without offsets is ASCII: the byte is the position. */
    return text->character_offsets ? text_scalar_count(text->bytes, byte) : byte;
}
_Bool minyar_text_starts_with(MinyarText *text, MinyarText *needle) {
    ensure_text_index(text);
    ensure_text_index(needle);
    return needle->byte_length <= text->byte_length &&
           bytes_are_equal(text->bytes, needle->bytes, (size_t)needle->byte_length);
}
_Bool minyar_text_ends_with(MinyarText *text, MinyarText *needle) {
    ensure_text_index(text);
    ensure_text_index(needle);
    return needle->byte_length <= text->byte_length &&
           bytes_are_equal(text->bytes + text->byte_length - needle->byte_length,
                           needle->bytes, (size_t)needle->byte_length);
}
MinyarList *minyar_text_split(MinyarText *text, MinyarText *separator) {
    ensure_text_index(text);
    ensure_text_index(separator);
    MinyarList *parts = minyar_list_new();
    minyar_list_references(parts);
    if (!separator->byte_length) {
        for (long long i = 0; i < text->character_length; i++)
            minyar_list_add_take(parts, (long long)(uintptr_t)minyar_text_slice(text, i, i + 1));
        return parts;
    }
    /* Pieces are byte ranges between matches. Every piece of ASCII Text is
     * ASCII; other pieces count their scalars once, as their slices record. */
    if (separator->byte_length == 1) {
        /* Find up to SPLIT_BATCH piece ends, reserve them at once, then cut
         * those pieces: one pass over the bytes, and a line of a few fields
         * grows its List once. */
        enum { SPLIT_BATCH = 64 };
        long long ends[SPLIT_BATCH];
        const unsigned char *bytes = text->bytes;
        unsigned char wanted = separator->bytes[0];
        long long length = text->byte_length, start = 0;
        _Bool ascii = !text->character_offsets;
        for (;;) {
            long long count = 0, scan = start;
            _Bool finished = 0;
            while (count < SPLIT_BATCH) {
                long long end = text_byte_scan(bytes, length, wanted, &scan);
                ends[count++] = end;
                if (end >= length) { finished = 1; break; }
            }
            list_reserve(parts, parts->length + count);
            for (long long piece = 0; piece < count; piece++) {
                long long end = ends[piece];
                long long characters = ascii ? end - start : text_scalar_count(bytes + start, end - start);
                minyar_list_add_take(parts, (long long)(uintptr_t)text_slice_bytes(text, start, end, characters));
                start = end + 1;
            }
            if (finished) return parts;
        }
    }
    long long small[TEXT_SEARCH_SMALL];
    long long *table = text_search_table(separator, text->byte_length, small);
    _Bool ascii = !text->character_offsets;
    long long start_byte = 0, match;
    while ((match = text_search_next(text, separator, start_byte, table)) >= 0) {
        long long characters = ascii ? match - start_byte : text_scalar_count(text->bytes + start_byte, match - start_byte);
        minyar_list_add_take(parts, (long long)(uintptr_t)text_slice_bytes(text, start_byte, match, characters));
        start_byte = match + separator->byte_length;
    }
    long long rest = text->byte_length - start_byte;
    long long characters = ascii ? rest : text_scalar_count(text->bytes + start_byte, rest);
    minyar_list_add_take(parts, (long long)(uintptr_t)text_slice_bytes(text, start_byte, text->byte_length, characters));
    text_search_free(table, small);
    return parts;
}
#ifndef MINYAR_COMPILER_ARENA
/* A piece kept past its loop iteration that is a small part (under 1/8) of a
 * large Text (over 4 KiB) gets its own bytes, so keeping a word does not keep
 * a whole file alive: the rule text_slice_bytes applies when it creates a
 * slice. Text is immutable, so every owner sees the same contents. */
static void text_compact_kept_piece(MinyarText *piece) {
    MinyarText *root = piece->backing;
#if MINYAR_THREADED
    /* A piece of shared frozen storage keeps the shared buffer, never an
     * owning Text it could copy out of. */
    if (!root || text_backing_shared(piece) || root->byte_length <= 4096 ||
        (unsigned long long)piece->byte_length * 8 >= (unsigned long long)root->byte_length)
        return;
#else
    if (!root || root->byte_length <= 4096 ||
        (unsigned long long)piece->byte_length * 8 >= (unsigned long long)root->byte_length)
        return;
#endif
    long long length = piece->byte_length;
    unsigned char *bytes = new_bytes(length);
    memcpy(bytes, piece->bytes, (size_t)length);
    bytes[length] = 0;
    piece->bytes = bytes;
    piece->backing = NULL;
    minyar_rc_release(root);
}
#endif

/* One step of `for piece in text.split(separator)`, which the compiler lowers
 * without building the List. *cursor is the byte where the next piece starts
 * (0 at first) or -1 after the last one. `previous` is the loop's own reference
 * to the piece it produced last, or NULL. Returns one owned reference to the
 * next piece, or NULL when none is left; NULL leaves `previous` to the loop.
 *
 * Pieces are zero-copy views of the source's owning Text. When the loop holds
 * the only count of `previous`, nothing can observe that view any more, so it
 * is re-pointed at the next piece instead of allocating another. A piece the
 * body kept is left to its owners, compacted as above when the loop moves past
 * it or finishes. The pieces and their order are exactly those of split. */
MinyarText *minyar_text_split_next(MinyarText *text, MinyarText *separator, long long *cursor,
                                   MinyarText *previous) {
    long long start = *cursor;
    ensure_text_index(text);
    ensure_text_index(separator);
    const unsigned char *bytes = text->bytes;
    long long length = text->byte_length, end, next;
    if (start < 0 || (!separator->byte_length && start >= length)) {
        *cursor = -1;
#ifndef MINYAR_COMPILER_ARENA
        if (previous && ((RcObject *)previous - 1)->ownership != (8 | RC_TEXT))
            text_compact_kept_piece(previous);
#endif
        return NULL;
    }
    if (!separator->byte_length) {
        /* One piece per scalar; Text is valid UTF-8, so the lead byte gives its width. */
        unsigned char lead = bytes[start];
        end = start + (lead < 0x80 ? 1 : lead < 0xe0 ? 2 : lead < 0xf0 ? 3 : 4);
        next = end;
    } else if (separator->byte_length == 1) {
        long long scan = start;
        end = text_byte_scan(bytes, length, separator->bytes[0], &scan);
        next = end < length ? end + 1 : -1;
    } else {
        long long small[TEXT_SEARCH_SMALL];
        long long *table = text_search_table(separator, length - start, small);
        long long match = text_search_next(text, separator, start, table);
        text_search_free(table, small);
        end = match >= 0 ? match : length;
        next = match >= 0 ? match + separator->byte_length : -1;
    }
    *cursor = next;
    long long piece = end - start;
    long long characters = text->character_offsets ? text_scalar_count(bytes + start, piece) : piece;
#ifdef MINYAR_COMPILER_ARENA
    (void)previous;
    return text_slice_bytes(text, start, end, characters);
#else
    MinyarText *root = text->backing ? text->backing : text;
    long long known = piece == characters ? characters : -1;
    if (previous) {
        RcObject *object = (RcObject *)previous - 1;
        if (object->ownership == (8 | RC_TEXT) && previous->backing == root) {
            rc_free_data(previous->character_offsets);
            previous->bytes = bytes + start;
            previous->byte_length = piece;
            previous->character_length = known;
            previous->character_offsets = NULL;
            object->ownership += 8;
            return previous;
        }
        text_compact_kept_piece(previous);
    }
    MinyarText *view = new_text(bytes + start, piece, known);
    view->backing = root;
    minyar_rc_retain(root);
    return view;
#endif
}

static _Bool text_white_space(unsigned int scalar) {
    /* ASCII first: most trimming tests one of these fifteen scalars. */
    if (scalar < 0x80) return (scalar >= 0x09 && scalar <= 0x0d) || scalar == 0x20;
    return scalar == 0x85 || scalar == 0xa0 || scalar == 0x1680 ||
           (scalar >= 0x2000 && scalar <= 0x200a) ||
           scalar == 0x2028 || scalar == 0x2029 || scalar == 0x202f || scalar == 0x205f || scalar == 0x3000;
}
/* Scans bytes from both ends: ASCII bytes are tested directly and other
 * scalars are decoded in place, so trimming never builds the offset index.
 * Returns the scalar count of the trimmed range. */
static long long text_trim_range(MinyarText *text, long long *first_byte, long long *last_byte) {
    ensure_text_index(text);
    const unsigned char *bytes = text->bytes;
    long long first = 0, last = text->byte_length, dropped = 0;
    /* Neither end is ASCII whitespace: no trimming, no scans. */
    if (!last || (bytes[0] > 0x20 && bytes[0] < 0x80 && bytes[last - 1] > 0x20 && bytes[last - 1] < 0x80)) {
        *first_byte = 0;
        *last_byte = last;
        return text->character_length;
    }
    while (first < last) {
        long long width = 1;
        unsigned scalar = bytes[first];
        if (scalar >= 0x80) scalar = decode_character(bytes + first, last - first, &width);
        if (!text_white_space(scalar)) break;
        first += width;
        dropped++;
    }
    while (last > first) {
        long long start = last - 1;
        while (start > first && (bytes[start] & 0xc0) == 0x80) start--;
        long long width = last - start;
        unsigned scalar = bytes[start];
        if (scalar >= 0x80) scalar = decode_character(bytes + start, width, &width);
        if (!text_white_space(scalar)) break;
        last = start;
        dropped++;
    }
    *first_byte = first;
    *last_byte = last;
    return text->character_length - dropped;
}
MinyarText *minyar_text_trim(MinyarText *text) {
    long long first, last;
    long long characters = text_trim_range(text, &first, &last);
    return text_slice_bytes(text, first, last, characters);
}
/* trim of an owned receiver (a fresh slice, a call result, a local at its
 * last use) consumes that count. A view nothing else holds is re-pointed at
 * its trimmed bytes instead of allocating another view, unless that would
 * make it a small part of a large root, which slices copy. */
MinyarText *minyar_text_trim_take(MinyarText *text) {
    long long first, last;
    long long characters = text_trim_range(text, &first, &last);
    if (first == 0 && last == text->byte_length) return text;
#ifndef MINYAR_COMPILER_ARENA
    MinyarText *root = text->backing;
    long long length = last - first;
#if MINYAR_THREADED
    _Bool shared = text_backing_shared(text);
    long long root_length = shared ? text->byte_length : (root ? root->byte_length : 0);
#else
    long long root_length = root ? root->byte_length : 0;
#endif
    if (((RcObject *)text - 1)->ownership == (8 | RC_TEXT) && root &&
        (root_length <= 4096 || (unsigned long long)length * 8 >= (unsigned long long)root_length)) {
        rc_free_data(text->character_offsets);
        text->bytes += first;
        text->byte_length = length;
        text->character_length = length == characters ? characters : -1;
        text->character_offsets = NULL;
        return text;
    }
#endif
    MinyarText *result = text_slice_bytes(text, first, last, characters);
    minyar_rc_release(text);
    return result;
}
static _Bool integer_ascii_space(unsigned char byte) {
    return byte == ' ' || (byte >= '\t' && byte <= '\r');
}
/* Integer(Text) over bytes [start, end) of `bytes`. */
static long long text_integer_bytes(const unsigned char *bytes, long long start, long long end) {
    while (start < end && integer_ascii_space(bytes[start])) start++;
    while (end > start && integer_ascii_space(bytes[end - 1])) end--;
    _Bool negative = start < end && bytes[start] == '-';
    if (start < end && (bytes[start] == '-' || bytes[start] == '+')) start++;
    if (start == end) minyar_stop_program("Integer(Text) requires a signed decimal ASCII integer.");
    unsigned long long value = 0, limit = (unsigned long long)LLONG_MAX + negative;
    /* Eighteen digits always fit, so only later digits need the range check. */
    long long i = start, unchecked = end - start > 18 ? start + 18 : end;
    for (; i < unchecked; i++) {
        unsigned digit = (unsigned)bytes[i] - '0';
        if (digit > 9) minyar_stop_program("Integer(Text) requires a signed decimal ASCII integer.");
        value = value * 10 + digit;
    }
    for (; i < end; i++) {
        unsigned digit = (unsigned)bytes[i] - '0';
        if (digit > 9) minyar_stop_program("Integer(Text) requires a signed decimal ASCII integer.");
        if (value > (limit - digit) / 10) minyar_stop_program("Integer(Text) is outside the signed 64-bit range.");
        value = value * 10 + digit;
    }
    if (negative && value == (unsigned long long)LLONG_MAX + 1) return LLONG_MIN;
    return negative ? -(long long)value : (long long)value;
}
long long minyar_text_integer(MinyarText *text) {
    ensure_text_index(text);
    return text_integer_bytes(text->bytes, 0, text->byte_length);
}
/* Integer(text.slice(start, end)) without the slice: the same bounds check
 * and stop as the slice, then the same parse over its bytes. */
long long minyar_text_integer_range(MinyarText *text, long long start, long long end) {
    ensure_text_index(text);
    if (start < 0 || end < start || end > text->character_length)
        slice_outside_text();
    if (text->character_offsets) {
        long long first = indexed_byte_offset(text, start);
        return text_integer_bytes(text->bytes, first, indexed_byte_offset(text, end));
    }
    return text_integer_bytes(text->bytes, start, end);
}

/* The byte range a slice of scalar positions covers: the slice's own bounds
 * check and stop. Readers that only need the bytes use this instead of the
 * slice, so a range costs no Text. */
static void text_range_bytes(MinyarText *text, long long start, long long end,
                             long long *first, long long *last) {
    ensure_text_index(text);
    if (start < 0 || end < start || end > text->character_length)
        slice_outside_text();
    *first = start;
    *last = end;
    if (text->character_offsets) {
        *first = indexed_byte_offset(text, start);
        *last = indexed_byte_offset(text, end);
    }
}

/* text.slice(start, end) == other without the slice: the slice's bounds
 * check and stop, then the byte comparison of minyar_texts_are_equal. */
_Bool minyar_text_range_equals(MinyarText *text, long long start, long long end, const MinyarText *other) {
    long long first, last;
    text_range_bytes(text, start, end, &first, &last);
    return other->byte_length == last - first &&
           bytes_are_equal(text->bytes + first, other->bytes, (size_t)(last - first));
}

/* One piece of text.split(separator) without the List: the same pieces, in
 * the same order, found from the receiver's start. A reader that takes one or
 * two pieces this way is cheaper than building the range index (below), which
 * is why both exist: the compiler picks by how many reads it sees. */
static void text_split_range(MinyarText *text, MinyarText *separator, long long index,
                             long long *start, long long *end) {
    ensure_text_index(text);
    ensure_text_index(separator);
    if (index < 0) list_position_stop(index, 0);
    const unsigned char *bytes = text->bytes;
    long long length = text->byte_length, from = 0, piece = 0;
    if (!separator->byte_length) {
        long long at = 0;
        while (at < length) {
            unsigned char lead = bytes[at];
            long long width = lead < 0x80 ? 1 : lead < 0xe0 ? 2 : lead < 0xf0 ? 3 : 4;
            if (piece == index) { *start = at; *end = at + width; return; }
            at += width;
            piece++;
        }
        list_position_stop(index, piece);
    }
    if (separator->byte_length == 1) {
        long long scan = 0;
        for (;;) {
            long long at = text_byte_scan(bytes, length, separator->bytes[0], &scan);
            if (piece == index) { *start = from; *end = at; return; }
            if (at >= length) break;
            from = at + 1;
            piece++;
        }
        list_position_stop(index, piece + 1);
    }
    long long small[TEXT_SEARCH_SMALL];
    long long *table = text_search_table(separator, length, small);
    for (;;) {
        long long match = text_search_next(text, separator, from, table);
        if (piece == index) {
            *start = from;
            *end = match < 0 ? length : match;
            text_search_free(table, small);
            return;
        }
        if (match < 0) break;
        from = match + separator->byte_length;
        piece++;
    }
    text_search_free(table, small);
    list_position_stop(index, piece + 1);
}
static long long text_piece_characters(MinyarText *text, long long start, long long end) {
    return text->character_offsets ? text_scalar_count(text->bytes + start, end - start) : end - start;
}
long long minyar_text_split_count(MinyarText *text, MinyarText *separator) {
    ensure_text_index(text);
    ensure_text_index(separator);
    if (!separator->byte_length) return text->character_length;
    long long pieces = 1, from = 0;
    if (separator->byte_length == 1) {
        const unsigned char *bytes = text->bytes;
        long long length = text->byte_length;
        long long cursor = 0;
        for (;;) {
            long long at = text_byte_scan(bytes, length, separator->bytes[0], &cursor);
            if (at >= length) return pieces;
            pieces++;
        }
    }
    long long small[TEXT_SEARCH_SMALL];
    long long *table = text_search_table(separator, text->byte_length, small);
    for (;;) {
        long long match = text_search_next(text, separator, from, table);
        if (match < 0) break;
        pieces++;
        from = match + separator->byte_length;
    }
    text_search_free(table, small);
    return pieces;
}
MinyarText *minyar_text_split_at(MinyarText *text, MinyarText *separator, long long index) {
    long long start, end;
    text_split_range(text, separator, index, &start, &end);
    return text_slice_bytes(text, start, end, text_piece_characters(text, start, end));
}
long long minyar_text_split_integer(MinyarText *text, MinyarText *separator, long long index) {
    long long start, end;
    text_split_range(text, separator, index, &start, &end);
    return text_integer_bytes(text->bytes, start, end);
}
long long minyar_text_split_length(MinyarText *text, MinyarText *separator, long long index) {
    long long start, end;
    text_split_range(text, separator, index, &start, &end);
    return text_piece_characters(text, start, end);
}
_Bool minyar_text_split_equals(MinyarText *text, MinyarText *separator, long long index,
                               const MinyarText *other) {
    long long start, end;
    text_split_range(text, separator, index, &start, &end);
    return other->byte_length == end - start &&
           bytes_are_equal(text->bytes + start, other->bytes, (size_t)(end - start));
}

/*
 * text.split(separator) as an index of piece ranges, for readers that only
 * need pieces by position: `let fields = text.split(",")` then `fields[i]`
 * scans the receiver once instead of once per read, and a reader that parses,
 * compares or measures a field never builds the piece at all.
 *
 * The index is shaped like a Text so its lifetime is an ordinary owning count
 * (the runtime frees `character_offsets` and drops `backing` when the last
 * owner goes): `bytes` is the receiver's first byte, `byte_length` the piece
 * count, `character_length` 1 when the receiver is ASCII (its pieces then are),
 * and `character_offsets` the pairs of byte offsets.
 */
static long long *split_index_ranges(const MinyarText *index) {
    return (long long *)index->character_offsets;
}
static void text_index_range(const MinyarText *index, long long position, long long *start, long long *end) {
    long long count = index->byte_length;
    if ((unsigned long long)position >= (unsigned long long)count)
        list_position_stop(position, count);
    const long long *ranges = split_index_ranges(index);
    *start = ranges[2 * position];
    *end = ranges[2 * position + 1];
}
static long long text_index_characters(const MinyarText *index, long long start, long long end) {
    return index->character_length ? end - start : text_scalar_count(index->bytes + start, end - start);
}
/* One piece of the index, with the slice rules: a tiny piece of a large root
 * gets its own bytes, and a view keeps the flattened root alive. */
static MinyarText *text_index_piece(MinyarText *index, long long start, long long end) {
    long long length = end - start;
    long long characters = text_index_characters(index, start, end);
    long long known = length == characters ? characters : -1;
    const unsigned char *bytes = index->bytes + start;
#ifdef MINYAR_COMPILER_ARENA
    /* The arena never frees, so a piece shares the receiver's bytes. */
    return new_text(bytes, length, known);
#else
    MinyarText *root = index->backing;
#if MINYAR_THREADED
    /* A piece of shared frozen storage keeps sharing: there is no owning Text
     * to measure, as text_slice_bytes says. */
    _Bool shared = text_backing_shared(index);
#else
    _Bool shared = 0;
#endif
    if (!shared && root->byte_length > 4096 &&
        (unsigned long long)length * 8 < (unsigned long long)root->byte_length) {
        MinyarText *copy = new_text_storage(length, known);
        unsigned char *target = (unsigned char *)copy->bytes;
        copy_bytes(target, bytes, (size_t)length);
        target[length] = 0;
        return copy;
    }
    MinyarText *view = new_text(bytes, length, known);
    view->backing = root;
    minyar_rc_retain(root);
    return view;
#endif
}
/* text.split(separator), as the piece ranges. One pass over the receiver. */
/* One more piece of room in the range buffer; the stack buffer serves the
 * first pieces, and every later size doubles. */
static long long *split_ranges_grow(long long *ranges, const long long *small, long long count,
                                    long long *capacity) {
    long long grown_capacity = *capacity * 2;
    long long *grown = data_allocate((size_t)(2 * grown_capacity) * sizeof(long long),
                                     sizeof(long long));
    memcpy(grown, ranges, (size_t)(2 * count) * sizeof(long long));
#ifndef MINYAR_COMPILER_ARENA
    if (ranges != small) rc_free_data(ranges);
#else
    (void)small;
#endif
    *capacity = grown_capacity;
    return grown;
}
MinyarText *minyar_text_split_index(MinyarText *text, MinyarText *separator) {
    ensure_text_index(text);
    ensure_text_index(separator);
    long long small[2 * 32];
    long long *ranges = small;
    long long capacity = 32, count = 0;
    const unsigned char *bytes = text->bytes;
    long long length = text->byte_length, from = 0;
    long long separator_length = separator->byte_length;
    if (separator_length == 1) {
        /* The usual separator: one byte, so the cursor that text_byte_scan
         * keeps makes the whole receiver one pass of eight-byte tests. */
        unsigned char wanted = separator->bytes[0];
        long long scan = 0;
        for (;;) {
            long long end = text_byte_scan(bytes, length, wanted, &scan);
            if (count == capacity) ranges = split_ranges_grow(ranges, small, count, &capacity);
            ranges[2 * count] = from;
            ranges[2 * count + 1] = end;
            count++;
            if (end >= length) break;
            from = end + 1;
        }
    } else if (!separator_length) {
        while (from < length) {
            unsigned char lead = bytes[from];
            long long end = from + (lead < 0x80 ? 1 : lead < 0xe0 ? 2 : lead < 0xf0 ? 3 : 4);
            if (count == capacity) ranges = split_ranges_grow(ranges, small, count, &capacity);
            ranges[2 * count] = from;
            ranges[2 * count + 1] = end;
            count++;
            from = end;
        }
    } else {
        long long small_table[TEXT_SEARCH_SMALL];
        long long *table = text_search_table(separator, length, small_table);
        for (;;) {
            long long match = text_search_next(text, separator, from, table);
            long long end = match < 0 ? length : match;
            if (count == capacity) ranges = split_ranges_grow(ranges, small, count, &capacity);
            ranges[2 * count] = from;
            ranges[2 * count + 1] = end;
            count++;
            if (match < 0) break;
            from = match + separator_length;
        }
        if (table) text_search_free(table, small_table);
    }
    MinyarText *index = new_text(bytes, count, !text->character_offsets ? 1 : 0);
    index->character_offsets = NULL;
    if (count) {
        index->character_offsets = data_allocate((size_t)(2 * count) * sizeof(long long),
                                                 sizeof(long long));
        memcpy(index->character_offsets, ranges, (size_t)(2 * count) * sizeof(long long));
    }
#ifndef MINYAR_COMPILER_ARENA
    index->backing = text->backing ? text->backing : text;
    minyar_rc_retain(index->backing);
#endif
#ifndef MINYAR_COMPILER_ARENA
    if (ranges != small) rc_free_data(ranges);
#endif
    return index;
}
long long minyar_text_split_index_count(MinyarText *index) {
    return index->byte_length;
}
MinyarText *minyar_text_split_index_at(MinyarText *index, long long position) {
    long long start, end;
    text_index_range(index, position, &start, &end);
    return text_index_piece(index, start, end);
}
/* Integer(fields[position]) without the piece. */
long long minyar_text_split_index_integer(MinyarText *index, long long position) {
    long long start, end;
    text_index_range(index, position, &start, &end);
    return text_integer_bytes(index->bytes, start, end);
}
/* fields[position].length without the piece. */
long long minyar_text_split_index_length(MinyarText *index, long long position) {
    long long start, end;
    text_index_range(index, position, &start, &end);
    return text_index_characters(index, start, end);
}
/* fields[position] == other without the piece. */
_Bool minyar_text_split_index_equals(MinyarText *index, long long position, const MinyarText *other) {
    long long start, end;
    text_index_range(index, position, &start, &end);
    return other->byte_length == end - start &&
           bytes_are_equal(index->bytes + start, other->bytes, (size_t)(end - start));
}
/* fields[position].startsWith / endsWith(needle) without the piece. */
_Bool minyar_text_split_index_starts_with(MinyarText *index, long long position, MinyarText *needle) {
    long long start, end;
    text_index_range(index, position, &start, &end);
    ensure_text_index(needle);
    return needle->byte_length <= end - start &&
           bytes_are_equal(index->bytes + start, needle->bytes, (size_t)needle->byte_length);
}
_Bool minyar_text_split_index_ends_with(MinyarText *index, long long position, MinyarText *needle) {
    long long start, end;
    text_index_range(index, position, &start, &end);
    ensure_text_index(needle);
    return needle->byte_length <= end - start &&
           bytes_are_equal(index->bytes + end - needle->byte_length, needle->bytes,
                           (size_t)needle->byte_length);
}
/* The pieces as the List text.split makes, for a use that needs the whole
 * split (a mutation, a whole-List call, an escape). */
MinyarList *minyar_text_split_index_list(MinyarText *index) {
    MinyarList *parts = minyar_list_new();
    minyar_list_references(parts);
    long long count = index->byte_length;
    list_reserve(parts, count);
    long long piece = 0;
    while (piece < count) {
        long long start, end;
        text_index_range(index, piece, &start, &end);
        minyar_list_add_take(parts, (long long)(uintptr_t)text_index_piece(index, start, end));
        piece = piece + 1;
    }
    return parts;
}

/* JSON scanning helpers for library/json.min. Positions are scalar offsets.
 * jsonStringEnd returns the first position at or after `position` holding a
 * quote, a backslash or a control below U+0020 (the Text's length if none);
 * jsonSpaceEnd returns the first position that is not JSON whitespace. Both
 * scan bytes: every byte they stop on or skip within ASCII is one scalar. */
static long long json_scan_start(MinyarText *text, long long position) {
    ensure_text_index(text);
    if (position < 0 || position > text->character_length) slice_outside_text();
    return text->character_offsets ? indexed_byte_offset(text, position) : position;
}
long long minyar_runtime_jsonStringEnd(MinyarText *text, long long position) {
    long long start = json_scan_start(text, position), i = start, length = text->byte_length;
    const unsigned char *bytes = text->bytes;
    const uint64_t ones = 0x0101010101010101ULL, highs = 0x8080808080808080ULL;
    for (; length - i >= 8; i += 8) {
        uint64_t word;
        memcpy(&word, bytes + i, sizeof(word));
        uint64_t quote = word ^ (ones * '"'), slash = word ^ (ones * '\\');
        uint64_t stop = ((quote - ones) & ~quote) | ((slash - ones) & ~slash) | ((word - ones * 0x20) & ~word);
        if (stop & highs) break;
    }
    for (; i < length; i++) {
        unsigned char byte = bytes[i];
        if (byte == '"' || byte == '\\' || byte < 0x20) break;
    }
    return position + (text->character_offsets ? text_scalar_count(bytes + start, i - start) : i - start);
}
/* JSON number grammar: -?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)? */
long long minyar_runtime_jsonNumberEnd(MinyarText *text, long long position) {
    long long start = json_scan_start(text, position), i = start, length = text->byte_length;
    const unsigned char *bytes = text->bytes;
#define JSON_DIGIT(at) ((at) < length && (unsigned char)(bytes[at] - '0') < 10)
    if (i < length && bytes[i] == '-') i++;
    long long digits = i;
    while (JSON_DIGIT(i)) i++;
    if (i == digits || (i - digits > 1 && bytes[digits] == '0')) return -1;
    if (i < length && bytes[i] == '.') {
        long long fraction = ++i;
        while (JSON_DIGIT(i)) i++;
        if (i == fraction) return -1;
    }
    if (i < length && (bytes[i] == 'e' || bytes[i] == 'E')) {
        i++;
        if (i < length && (bytes[i] == '-' || bytes[i] == '+')) i++;
        long long exponent = i;
        while (JSON_DIGIT(i)) i++;
        if (i == exponent) return -1;
    }
#undef JSON_DIGIT
    return position + (i - start);
}
long long minyar_runtime_jsonSpaceEnd(MinyarText *text, long long position) {
    long long start = json_scan_start(text, position), i = start, length = text->byte_length;
    const unsigned char *bytes = text->bytes;
    while (i < length && (bytes[i] == ' ' || bytes[i] == '\n' || bytes[i] == '\r' || bytes[i] == '\t')) i++;
    return position + (i - start);
}
/* An integral spelling of one to eighteen digits fits an Integer exactly, so
 * it needs no decimal conversion. `jsonInteger` reads it in place; anything
 * else (fraction, exponent, sign other than '-', longer, empty) returns
 * LLONG_MIN, which no such spelling can produce. */
long long minyar_runtime_jsonInteger(MinyarText *text) {
    const unsigned char *bytes = (const unsigned char *)text->bytes;
    long long length = text->byte_length, i = 0, digits = 0, magnitude = 0;
    _Bool negative = length > 0 && bytes[0] == '-';
    if (negative) i = 1;
    for (; i < length; i++, digits++) {
        if (digits >= 18 || (unsigned char)(bytes[i] - '0') >= 10) return -9223372036854775807LL - 1;
        magnitude = magnitude * 10 + (bytes[i] - '0');
    }
    if (digits == 0) return -9223372036854775807LL - 1;
    return negative ? -magnitude : magnitude;
}

/* Everyday Text operations. Positions and lengths count Unicode scalars; all
 * searching and copying works on bytes. A result whose scalar count equals its
 * byte count is recorded as ASCII, as every other Text constructor does. */
static long long text_byte_of(MinyarText *text, long long position) {
    return text->character_offsets ? indexed_byte_offset(text, position) : position;
}
static MinyarText *text_build(long long length, _Bool ascii, unsigned char **bytes) {
    MinyarText *text = new_text_storage(length, ascii ? length : -1);
    *bytes = (unsigned char *)text->bytes;
    (*bytes)[length] = 0;
    return text;
}
static MinyarText *text_same(MinyarText *text) {
    minyar_rc_retain(text);
    return text;
}
static long long text_checked_product(long long left, long long right) {
    if (left && right > LLONG_MAX / left) join_too_large();
    return left * right;
}
static long long text_checked_sum(long long left, long long right) {
    if (right > LLONG_MAX - left) join_too_large();
    return left + right;
}

_Bool minyar_text_contains(MinyarText *text, MinyarText *needle) {
    ensure_text_index(text);
    ensure_text_index(needle);
    if (!needle->byte_length) return 1;
    long long small[TEXT_SEARCH_SMALL];
    long long *table = text_search_table(needle, text->byte_length, small);
    long long byte = text_search_next(text, needle, 0, table);
    text_search_free(table, small);
    return byte >= 0;
}

/* The first match starting at or after scalar position `start`, or -1. */
long long minyar_text_find_from(MinyarText *text, MinyarText *needle, long long start) {
    ensure_text_index(text);
    ensure_text_index(needle);
    if (start < 0) negative_text_position();
    if (start > text->character_length) position_outside_text();
    if (!needle->byte_length) return start;
    long long first = text_byte_of(text, start);
    long long small[TEXT_SEARCH_SMALL];
    long long *table = text_search_table(needle, text->byte_length - first, small);
    long long byte = text_search_next(text, needle, first, table);
    text_search_free(table, small);
    if (byte < 0) return -1;
    return text->character_offsets ? start + text_scalar_count(text->bytes + first, byte - first) : byte;
}

/* Every non-overlapping occurrence, left to right. An empty pattern matches
 * before every scalar and at the end, so "ab" becomes "-a-b-". */
MinyarText *minyar_text_replace(MinyarText *text, MinyarText *pattern, MinyarText *replacement) {
    ensure_text_index(text);
    ensure_text_index(pattern);
    ensure_text_index(replacement);
    _Bool ascii = !text->character_offsets && !replacement->character_offsets;
    unsigned char *out;
    if (!pattern->byte_length) {
        long long slots = text->character_length + 1;
        long long length = text_checked_sum(text->byte_length, text_checked_product(slots, replacement->byte_length));
        MinyarText *result = text_build(length, ascii, &out);
        long long offset = 0;
        for (long long i = 0; i <= text->byte_length; i++) {
            if (i == text->byte_length || (text->bytes[i] & 0xc0) != 0x80) {
                copy_bytes(out + offset, replacement->bytes, (size_t)replacement->byte_length);
                offset += replacement->byte_length;
            }
            if (i < text->byte_length) out[offset++] = text->bytes[i];
        }
        return result;
    }
    long long small[TEXT_SEARCH_SMALL];
    long long *table = text_search_table(pattern, text->byte_length, small);
    long long count = 0;
    for (long long at = text_search_next(text, pattern, 0, table); at >= 0;
         at = text_search_next(text, pattern, at + pattern->byte_length, table))
        count++;
    if (!count) {
        text_search_free(table, small);
        return text_same(text);
    }
    long long removed = text_checked_product(count, pattern->byte_length);
    long long length = text_checked_sum(text->byte_length - removed, text_checked_product(count, replacement->byte_length));
    MinyarText *result = text_build(length, ascii, &out);
    long long offset = 0, from = 0;
    for (long long at = text_search_next(text, pattern, 0, table); at >= 0;
         at = text_search_next(text, pattern, from, table)) {
        copy_bytes(out + offset, text->bytes + from, (size_t)(at - from));
        offset += at - from;
        copy_bytes(out + offset, replacement->bytes, (size_t)replacement->byte_length);
        offset += replacement->byte_length;
        from = at + pattern->byte_length;
    }
    copy_bytes(out + offset, text->bytes + from, (size_t)(text->byte_length - from));
    text_search_free(table, small);
    return result;
}

MinyarText *minyar_text_repeat(MinyarText *text, long long count) {
    ensure_text_index(text);
    if (count < 0) minyar_stop_program("Text.repeat needs a count of zero or more.");
    if (count == 1) return text_same(text);
    long long length = text_checked_product(text->byte_length, count);
    unsigned char *out;
    MinyarText *result = text_build(length, !text->character_offsets, &out);
    if (!length) return result;
    copy_bytes(out, text->bytes, (size_t)text->byte_length);
    for (long long filled = text->byte_length; filled < length;) {
        long long piece = filled < length - filled ? filled : length - filled;
        copy_bytes(out + filled, out, (size_t)piece);
        filled += piece;
    }
    return result;
}

/* Pad to `length` scalars with copies of `pad`, the last one cut short at a
 * scalar boundary. Text already that long, or an empty pad, is unchanged. */
static MinyarText *text_pad(MinyarText *text, long long length, MinyarText *pad, _Bool at_start) {
    ensure_text_index(text);
    ensure_text_index(pad);
    if (length <= text->character_length || !pad->byte_length) return text_same(text);
    long long missing = length - text->character_length;
    long long copies = missing / pad->character_length, rest = missing % pad->character_length;
    long long rest_bytes = text_byte_of(pad, rest);
    long long fill = text_checked_sum(text_checked_product(copies, pad->byte_length), rest_bytes);
    long long total = text_checked_sum(fill, text->byte_length);
    unsigned char *out;
    MinyarText *result = text_build(total, !text->character_offsets && !pad->character_offsets, &out);
    unsigned char *filler = at_start ? out : out + text->byte_length;
    copy_bytes(at_start ? out + fill : out, text->bytes, (size_t)text->byte_length);
    for (long long i = 0; i < copies; i++)
        copy_bytes(filler + i * pad->byte_length, pad->bytes, (size_t)pad->byte_length);
    copy_bytes(filler + copies * pad->byte_length, pad->bytes, (size_t)rest_bytes);
    return result;
}
MinyarText *minyar_text_pad_start(MinyarText *text, long long length, MinyarText *pad) {
    return text_pad(text, length, pad, 1);
}
MinyarText *minyar_text_pad_end(MinyarText *text, long long length, MinyarText *pad) {
    return text_pad(text, length, pad, 0);
}

/* Map only A-Z or a-z; every other byte, including all non-ASCII, is kept. */
static MinyarText *text_ascii_case(MinyarText *text, _Bool upper) {
    ensure_text_index(text);
    unsigned char *out;
    MinyarText *result = text_build(text->byte_length, !text->character_offsets, &out);
    unsigned char first = upper ? 'a' : 'A';
    for (long long i = 0; i < text->byte_length; i++) {
        unsigned char byte = text->bytes[i];
        out[i] = (unsigned char)(byte - first) < 26 ? byte ^ 0x20 : byte;
    }
    return result;
}
MinyarText *minyar_text_ascii_lowercased(MinyarText *text) { return text_ascii_case(text, 0); }
MinyarText *minyar_text_ascii_uppercased(MinyarText *text) { return text_ascii_case(text, 1); }

/* joinText(parts, separator): one exactly sized copy. */
MinyarText *minyar_join_texts_with(const MinyarList *parts, MinyarText *separator) {
    long long length = 0, offset = 0;
    long long count = parts->length, separator_length = separator->byte_length;
    _Bool ascii = separator->character_length == separator_length;
    for (long long index = 0; index < count; index++) {
        const MinyarText *part = (const MinyarText *)(intptr_t)parts->values[index];
        length = text_checked_sum(length, part->byte_length);
        if (part->character_length != part->byte_length) ascii = 0;
    }
    /* Every separator but the one after the last part goes between them. */
    if (count > 1 && separator_length) length = text_checked_sum(length, text_checked_product(count - 1, separator_length));
    unsigned char *out;
    MinyarText *text = text_build(length, ascii, &out);
    const unsigned char *separator_bytes = separator->bytes;
    for (long long index = 0; index < count; index++) {
        const MinyarText *part = (const MinyarText *)(intptr_t)parts->values[index];
        if (index) {
            copy_bytes(out + offset, separator_bytes, (size_t)separator_length);
            offset += separator_length;
        }
        copy_bytes(out + offset, part->bytes, (size_t)part->byte_length);
        offset += part->byte_length;
    }
    return text;
}
