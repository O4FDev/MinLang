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

/* KMP avoids quadratic scans of repeated prefixes. One table is reused for
 * all split matches; one-byte separators take the allocation-free path, and
 * needles of up to TEXT_SEARCH_SMALL bytes use the caller's stack table. */
enum { TEXT_SEARCH_SMALL = 32 };
static long long *text_search_table(const MinyarText *needle, long long available,
                                    long long small[TEXT_SEARCH_SMALL]) {
    long long length = needle->byte_length;
    if (length <= 1 || length > available) return NULL;
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
static void text_search_free(long long *table, const long long *small) {
    if (table == small)
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
    return byte < 0 ? -1 : text_scalar_count(text->bytes, byte);
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
        /* Size the List once; this count loop vectorises. */
        unsigned char wanted = separator->bytes[0];
        long long pieces = 1;
        for (long long i = 0; i < text->byte_length; i++) pieces += text->bytes[i] == wanted;
        list_reserve(parts, pieces);
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
static _Bool text_white_space(unsigned int scalar) {
    return (scalar >= 0x09 && scalar <= 0x0d) || scalar == 0x20 || scalar == 0x85 ||
           scalar == 0xa0 || scalar == 0x1680 || (scalar >= 0x2000 && scalar <= 0x200a) ||
           scalar == 0x2028 || scalar == 0x2029 || scalar == 0x202f || scalar == 0x205f || scalar == 0x3000;
}
/* Scans bytes from both ends: ASCII bytes are tested directly and other
 * scalars are decoded in place, so trimming never builds the offset index. */
MinyarText *minyar_text_trim(MinyarText *text) {
    ensure_text_index(text);
    const unsigned char *bytes = text->bytes;
    long long first = 0, last = text->byte_length, dropped = 0;
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
    return text_slice_bytes(text, first, last, text->character_length - dropped);
}
static _Bool integer_ascii_space(unsigned char byte) {
    return byte == ' ' || (byte >= '\t' && byte <= '\r');
}
long long minyar_text_integer(MinyarText *text) {
    ensure_text_index(text);
    long long start = 0, end = text->byte_length;
    while (start < end && integer_ascii_space(text->bytes[start])) start++;
    while (end > start && integer_ascii_space(text->bytes[end - 1])) end--;
    _Bool negative = start < end && text->bytes[start] == '-';
    if (start < end && (text->bytes[start] == '-' || text->bytes[start] == '+')) start++;
    if (start == end) minyar_stop_program("Integer(Text) requires a signed decimal ASCII integer.");
    unsigned long long value = 0, limit = (unsigned long long)LLONG_MAX + negative;
    for (long long i = start; i < end; i++) {
        unsigned char byte = text->bytes[i];
        if (byte < '0' || byte > '9') minyar_stop_program("Integer(Text) requires a signed decimal ASCII integer.");
        unsigned digit = byte - '0';
        if (value > (limit - digit) / 10) minyar_stop_program("Integer(Text) is outside the signed 64-bit range.");
        value = value * 10 + digit;
    }
    if (negative && value == (unsigned long long)LLONG_MAX + 1) return LLONG_MIN;
    return negative ? -(long long)value : (long long)value;
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
long long minyar_runtime_jsonSpaceEnd(MinyarText *text, long long position) {
    long long start = json_scan_start(text, position), i = start, length = text->byte_length;
    const unsigned char *bytes = text->bytes;
    while (i < length && (bytes[i] == ' ' || bytes[i] == '\n' || bytes[i] == '\r' || bytes[i] == '\t')) i++;
    return position + (i - start);
}

