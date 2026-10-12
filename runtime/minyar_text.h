/* Text operations use validated UTF-8 and scalar positions. Every public
 * entry validates all Text operands before taking empty/length shortcuts. */
static long long text_scalar_count(const unsigned char *bytes, long long length) {
    long long count = 0;
    for (long long i = 0; i < length; i++) count += (bytes[i] & 0xc0) != 0x80;
    return count;
}

/* KMP avoids quadratic scans of repeated prefixes. One table is reused for
 * all split matches; one-byte separators take the allocation-free path. */
static long long *text_search_table(const MinyarText *needle, long long available) {
    long long length = needle->byte_length;
    if (length <= 1 || length > available) return NULL;
    if ((unsigned long long)length > SIZE_MAX / sizeof(long long))
        minyar_stop("the Text search pattern is too large.");
    long long *table = data_allocate((size_t)length * sizeof(*table), sizeof(*table));
    table[0] = 0;
    for (long long i = 1, matched = 0; i < length; i++) {
        while (matched && needle->bytes[i] != needle->bytes[matched]) matched = table[matched - 1];
        if (needle->bytes[i] == needle->bytes[matched]) matched++;
        table[i] = matched;
    }
    return table;
}
static void text_search_free(long long *table) {
#ifndef MINYAR_COMPILER_ARENA
    rc_free_data(table);
#else
    (void)table;
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
        if (text->bytes[i] == needle->bytes[matched]) matched++;
        if (matched == needle->byte_length) return i + 1 - matched;
    }
    return -1;
}

long long minyar_text_find(MinyarText *text, MinyarText *needle) {
    ensure_text_index(text);
    ensure_text_index(needle);
    if (!needle->byte_length) return 0;
    long long *table = text_search_table(needle, text->byte_length);
    long long byte = text_search_next(text, needle, 0, table);
    text_search_free(table);
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
    long long *table = text_search_table(separator, text->byte_length);
    long long start_byte = 0, start_scalar = 0, match;
    while ((match = text_search_next(text, separator, start_byte, table)) >= 0) {
        long long end_scalar = start_scalar + text_scalar_count(text->bytes + start_byte, match - start_byte);
        minyar_list_add_take(parts, (long long)(uintptr_t)minyar_text_slice(text, start_scalar, end_scalar));
        start_byte = match + separator->byte_length;
        start_scalar = end_scalar + separator->character_length;
    }
    minyar_list_add_take(parts, (long long)(uintptr_t)minyar_text_slice(text, start_scalar, text->character_length));
    text_search_free(table);
    return parts;
}
static _Bool text_white_space(unsigned int scalar) {
    return (scalar >= 0x09 && scalar <= 0x0d) || scalar == 0x20 || scalar == 0x85 ||
           scalar == 0xa0 || scalar == 0x1680 || (scalar >= 0x2000 && scalar <= 0x200a) ||
           scalar == 0x2028 || scalar == 0x2029 || scalar == 0x202f || scalar == 0x205f || scalar == 0x3000;
}
MinyarText *minyar_text_trim(MinyarText *text) {
    ensure_text_index(text);
    long long first = 0, last = text->character_length;
    while (first < last && text_white_space((unsigned)minyar_text_character_at(text, first))) first++;
    while (last > first && text_white_space((unsigned)minyar_text_character_at(text, last - 1))) last--;
    return minyar_text_slice(text, first, last);
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
    if (start == end) minyar_stop("Integer(Text) requires a signed decimal ASCII integer.");
    unsigned long long value = 0, limit = (unsigned long long)LLONG_MAX + negative;
    for (long long i = start; i < end; i++) {
        unsigned char byte = text->bytes[i];
        if (byte < '0' || byte > '9') minyar_stop("Integer(Text) requires a signed decimal ASCII integer.");
        unsigned digit = byte - '0';
        if (value > (limit - digit) / 10) minyar_stop("Integer(Text) is outside the signed 64-bit range.");
        value = value * 10 + digit;
    }
    if (negative && value == (unsigned long long)LLONG_MAX + 1) return LLONG_MIN;
    return negative ? -(long long)value : (long long)value;
}
