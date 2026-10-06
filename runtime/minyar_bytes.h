/* Runtime implementation fragment; included once by minyar_runtime.c. */

/*
 * Bytes are packed, growable buffers. They reuse the leaf Text object, so every
 * ownership profile releases them exactly like Text: `bytes` points at
 * capacity + 1 bytes, byte_length is the initialized visible length, and
 * character_length holds the capacity. Spare capacity is private; growth
 * initializes every newly visible byte. The compiler keeps Bytes and Text distinct.
 * Multi-byte accessors are little-endian at any byte offset.
 */
typedef MinyarText MinyarBytes;

static MINYAR_COLD MINYAR_NORETURN void bytes_position_stop(long long position, long long size,
                                                            long long length) {
    char message[160];
    if (size == 1)
        snprintf(message, sizeof(message), "Bytes position %lld is outside its length of %lld.",
                 position, length);
    else
        snprintf(message, sizeof(message),
                 "a %lld-byte value at position %lld does not fit in Bytes of length %lld.", size,
                 position, length);
    minyar_stop(message);
}

static MINYAR_COLD MINYAR_NORETURN void bytes_value_stop(long long value, const char *kind) {
    char message[160];
    snprintf(message, sizeof(message), "%lld does not fit in %s.", value, kind);
    minyar_stop(message);
}

static unsigned char *bytes_data(const MinyarBytes *bytes) {
    return (unsigned char *)bytes->bytes;
}

static void bytes_check(const MinyarBytes *bytes, long long position, long long size) {
    if (position < 0 || position > bytes->byte_length - size)
        bytes_position_stop(position, size, bytes->byte_length);
}

MinyarBytes *minyar_bytes_new(long long length) {
    if (length < 0)
        minyar_stop("Bytes cannot have a negative length.");
    if ((unsigned long long)length >= SIZE_MAX / 2)
        minyar_stop("these Bytes are too large.");
    unsigned char *data = new_bytes(length);
    memset(data, 0, (size_t)length + 1);
    return new_text(data, length, length);
}

long long minyar_bytes_length(const MinyarBytes *bytes) {
    return bytes->byte_length;
}

static void bytes_reserve(MinyarBytes *bytes, long long extra) {
    long long capacity = bytes->character_length;
    if (extra > LLONG_MAX / 4 - bytes->byte_length)
        minyar_stop("these Bytes are too large.");
    long long needed = bytes->byte_length + extra;
    if (needed <= capacity)
        return;
    long long grown = capacity < 16 ? 16 : capacity * 2;
    if (grown < needed)
        grown = needed;
    if ((unsigned long long)grown >= SIZE_MAX / 2)
        minyar_stop("these Bytes are too large.");
#ifdef MINYAR_COMPILER_ARENA
    unsigned char *data = data_allocate((size_t)grown + 1, 1);
    memcpy(data, bytes->bytes, (size_t)bytes->byte_length);
#else
    unsigned char *data = rc_reallocate_data(bytes_data(bytes), (size_t)grown + 1);
#endif
    /* Spare capacity is private. Writers initialize their own appended range;
     * eagerly clearing it duplicates work and makes refill-heavy code scan the
     * same storage twice. Keep only the allocation's trailing sentinel. */
    data[grown] = 0;
    bytes->bytes = data;
    bytes->character_length = grown;
}

void minyar_bytes_resize(MinyarBytes *bytes, long long length) {
    if (length < 0)
        minyar_stop("Bytes cannot have a negative length.");
    if (length > bytes->byte_length) {
        bytes_reserve(bytes, length - bytes->byte_length);
        memset(bytes_data(bytes) + bytes->byte_length, 0, (size_t)(length - bytes->byte_length));
    }
    bytes->byte_length = length;
}

void minyar_bytes_clear(MinyarBytes *bytes) {
    minyar_bytes_resize(bytes, 0);
}

long long minyar_bytes_get(const MinyarBytes *bytes, long long position) {
    if ((unsigned long long)position >= (unsigned long long)bytes->byte_length)
        bytes_position_stop(position, 1, bytes->byte_length);
    return bytes->bytes[position];
}

void minyar_bytes_set(MinyarBytes *bytes, long long position, long long value) {
    if ((unsigned long long)position >= (unsigned long long)bytes->byte_length)
        bytes_position_stop(position, 1, bytes->byte_length);
    if ((unsigned long long)value > 255)
        bytes_value_stop(value, "a byte (0 to 255)");
    bytes_data(bytes)[position] = (unsigned char)value;
}

static void bytes_store(unsigned char *target, unsigned long long value, int size) {
    for (int i = 0; i < size; i++)
        target[i] = (unsigned char)(value >> (8 * i));
}

static unsigned long long bytes_load(const unsigned char *source, int size) {
    unsigned long long value = 0;
    for (int i = 0; i < size; i++)
        value |= (unsigned long long)source[i] << (8 * i);
    return value;
}

static void bytes_check_integer(long long value, int size, int is_signed) {
    static const char *const kinds[2][5] = {
        {"", "", "an unsigned 16-bit Integer", "", "an unsigned 32-bit Integer"},
        {"", "", "a signed 16-bit Integer", "", "a signed 32-bit Integer"},
    };
    long long bits = 8LL * size;
    if (is_signed) {
        if (value < -(1LL << (bits - 1)) || value >= (1LL << (bits - 1)))
            bytes_value_stop(value, kinds[1][size]);
    } else if (value < 0 || value >= (1LL << bits)) {
        bytes_value_stop(value, kinds[0][size]);
    }
}

#define MINYAR_BYTES_INTEGER(Name, size, is_signed, cast)                                          \
    void minyar_bytes_add_##Name(MinyarBytes *bytes, long long value) {                            \
        bytes_check_integer(value, size, is_signed);                                               \
        bytes_reserve(bytes, size);                                                                \
        bytes_store(bytes_data(bytes) + bytes->byte_length, (unsigned long long)value, size);      \
        bytes->byte_length += size;                                                                \
    }                                                                                              \
    void minyar_bytes_set_##Name(MinyarBytes *bytes, long long position, long long value) {        \
        bytes_check(bytes, position, size);                                                        \
        bytes_check_integer(value, size, is_signed);                                               \
        bytes_store(bytes_data(bytes) + position, (unsigned long long)value, size);                \
    }                                                                                              \
    long long minyar_bytes_get_##Name(const MinyarBytes *bytes, long long position) {              \
        bytes_check(bytes, position, size);                                                        \
        return (long long)(cast)bytes_load(bytes->bytes + position, size);                         \
    }
MINYAR_BYTES_INTEGER(int16, 2, 1, int16_t)
MINYAR_BYTES_INTEGER(uint16, 2, 0, uint16_t)
MINYAR_BYTES_INTEGER(int32, 4, 1, int32_t)
MINYAR_BYTES_INTEGER(uint32, 4, 0, uint32_t)
#undef MINYAR_BYTES_INTEGER

void minyar_bytes_add_int64(MinyarBytes *bytes, long long value) {
    bytes_reserve(bytes, 8);
    bytes_store(bytes_data(bytes) + bytes->byte_length, (unsigned long long)value, 8);
    bytes->byte_length += 8;
}
void minyar_bytes_set_int64(MinyarBytes *bytes, long long position, long long value) {
    bytes_check(bytes, position, 8);
    bytes_store(bytes_data(bytes) + position, (unsigned long long)value, 8);
}
long long minyar_bytes_get_int64(const MinyarBytes *bytes, long long position) {
    bytes_check(bytes, position, 8);
    return (long long)bytes_load(bytes->bytes + position, 8);
}

void minyar_bytes_add(MinyarBytes *bytes, long long value) {
    if ((unsigned long long)value > 255)
        bytes_value_stop(value, "a byte (0 to 255)");
    bytes_reserve(bytes, 1);
    bytes_data(bytes)[bytes->byte_length++] = (unsigned char)value;
}

static uint32_t float32_bits(double value) {
    float narrowed = (float)value;
    uint32_t bits;
    memcpy(&bits, &narrowed, sizeof(bits));
    return bits;
}

static double float32_value(uint32_t bits) {
    float narrowed;
    memcpy(&narrowed, &bits, sizeof(narrowed));
    return (double)narrowed;
}

void minyar_bytes_add_float32(MinyarBytes *bytes, double value) {
    bytes_reserve(bytes, 4);
    bytes_store(bytes_data(bytes) + bytes->byte_length, float32_bits(value), 4);
    bytes->byte_length += 4;
}
void minyar_bytes_set_float32(MinyarBytes *bytes, long long position, double value) {
    bytes_check(bytes, position, 4);
    bytes_store(bytes_data(bytes) + position, float32_bits(value), 4);
}
double minyar_bytes_get_float32(const MinyarBytes *bytes, long long position) {
    bytes_check(bytes, position, 4);
    return float32_value((uint32_t)bytes_load(bytes->bytes + position, 4));
}

void minyar_bytes_add_float64(MinyarBytes *bytes, double value) {
    uint64_t bits;
    memcpy(&bits, &value, sizeof(bits));
    bytes_reserve(bytes, 8);
    bytes_store(bytes_data(bytes) + bytes->byte_length, bits, 8);
    bytes->byte_length += 8;
}
void minyar_bytes_set_float64(MinyarBytes *bytes, long long position, double value) {
    uint64_t bits;
    memcpy(&bits, &value, sizeof(bits));
    bytes_check(bytes, position, 8);
    bytes_store(bytes_data(bytes) + position, bits, 8);
}
double minyar_bytes_get_float64(const MinyarBytes *bytes, long long position) {
    bytes_check(bytes, position, 8);
    uint64_t bits = bytes_load(bytes->bytes + position, 8);
    double value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

MinyarBytes *minyar_bytes_slice(const MinyarBytes *bytes, long long start, long long end) {
    if (start < 0 || end < start || end > bytes->byte_length) {
        char message[160];
        snprintf(message, sizeof(message),
                 "Bytes range %lld to %lld is outside its length of %lld.", start, end,
                 bytes->byte_length);
        minyar_stop(message);
    }
    MinyarBytes *result = minyar_bytes_new(end - start);
    memcpy(bytes_data(result), bytes->bytes + start, (size_t)(end - start));
    return result;
}

void minyar_bytes_append(MinyarBytes *bytes, const MinyarBytes *other) {
    long long length = other->byte_length;
    bytes_reserve(bytes, length);
    memmove(bytes_data(bytes) + bytes->byte_length, other->bytes, (size_t)length);
    bytes->byte_length += length;
}

MinyarBytes *minyar_read_bytes_file(const MinyarText *path_text) {
    char *path = text_as_path(path_text);
    FILE *file = fopen(path, "rb");
    if (!file) {
        fprintf(stderr, "Minyar stopped: the file '%s' could not be opened.\n", path);
        exit(1);
    }
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    rc_heap_deallocate(path);
#else
    free(path);
#endif
    long long length = text_file_length(file);
    MinyarBytes *bytes = minyar_bytes_new(length);
    if (fread(bytes_data(bytes), 1, (size_t)length, file) != (size_t)length)
        minyar_stop("a requested file could not be read.");
    fclose(file);
    return bytes;
}

void minyar_write_bytes_file(const MinyarText *path_text, const MinyarBytes *contents) {
    char *path = text_as_path(path_text);
    FILE *file = fopen(path, "wb");
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    rc_heap_deallocate(path);
#else
    free(path);
#endif
    if (!file)
        minyar_stop("a requested file could not be created.");
    if (fwrite(contents->bytes, 1, (size_t)contents->byte_length, file) !=
            (size_t)contents->byte_length ||
        fclose(file) != 0)
        minyar_stop("a requested file could not be written.");
}

_Bool minyar_file_exists(const MinyarText *path_text) {
    char *path = text_as_path(path_text);
    FILE *file = fopen(path, "rb");
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    rc_heap_deallocate(path);
#else
    free(path);
#endif
    if (!file)
        return 0;
    fclose(file);
    return 1;
}

/* Grow Bytes by `count` zeroed bytes and return where they start, for native
 * library code that writes packed data directly. */
unsigned char *minyar_bytes_extend(MinyarBytes *bytes, long long count) {
    if (count < 0)
        minyar_stop("Bytes cannot shrink by a negative amount.");
    bytes_reserve(bytes, count);
    unsigned char *start = bytes_data(bytes) + bytes->byte_length;
    memset(start, 0, (size_t)count);
    bytes->byte_length += count;
    return start;
}
