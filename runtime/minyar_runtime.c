#if defined(MINYAR_LAZY_HEAP) && !defined(MINYAR_COMPILER_ARENA) && defined(__linux__) && !defined(_DEFAULT_SOURCE)
#define _DEFAULT_SOURCE 1
#endif
#if defined(MINYAR_LAZY_HEAP) && !defined(MINYAR_COMPILER_ARENA) && defined(_WIN32)
#error The lazy heap profile requires a POSIX mmap backend; Windows is not supported.
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <stddef.h>
#include <stdint.h>

/*
 * Every operation the generated code calls is split into a small hot path
 * and a separately compiled cold path. The compiler links this file as LLVM
 * IR with link-time optimisation, so the hot paths inline into generated
 * code as a few instructions while the error reporting stays out of line.
 */
#if defined(__GNUC__) || defined(__clang__)
#define MINYAR_COLD __attribute__((noinline, cold))
#define MINYAR_NORETURN __attribute__((noreturn))
#define MINYAR_HOT static inline __attribute__((always_inline))
#else
#define MINYAR_COLD
#define MINYAR_NORETURN
#define MINYAR_HOT static inline
#endif

typedef struct {
    const unsigned char *bytes;
    long long byte_length;
    long long character_length;
    long long *character_offsets;
} MinyarText;

typedef struct {
    long long *values;
    long long length;
    long long capacity;
} MinyarList;

#ifdef MINYAR_COMPILER_ARENA
typedef MinyarList MinyarRecord;
#else
/* Records never grow. Store fields directly after their length, without a
 * List's capacity and pointer. Generated LLVM treats them as opaque pointers. */
typedef struct {
    long long length;
    long long values[];
} MinyarRecord;
#endif

static int saved_argument_count;
static char **saved_argument_values;

#ifdef MINYAR_COMPILER_ARENA
/* Keep interleaved token/output buffers from copying at the same boundaries. */
enum { LARGE_LIST_CAPACITY = 2048 };
#else
enum { LARGE_LIST_CAPACITY = 4096 };
#endif

static MINYAR_COLD MINYAR_NORETURN void minyar_stop(const char *message) {
    fprintf(stderr, "Minyar stopped: %s\n", message);
    exit(1);
}

static MINYAR_COLD MINYAR_NORETURN void out_of_memory(void) {
    minyar_stop("the computer ran out of memory.");
}

#include "minyar_rc.h"

#ifdef MINYAR_COMPILER_ARENA
/*
 * The compiler never frees memory: the operating system reclaims everything
 * when it exits. Bump arenas serve it. The object arena holds fixed-size Text
 * and List headers, the data arena holds Text bytes, and List storage lives
 * in the list arena, or in the large-list arena once a List passes a few
 * thousand elements. The newest allocation in an arena can grow in place, so
 * a chain of Text joins extends one buffer instead of copying it each time,
 * and a large List such as the compiler's output keeps growing in place
 * instead of copying at every doubling while short-lived small Lists come
 * and go in their own arena.
 */
typedef struct MinyarArenaBlock {
    struct MinyarArenaBlock *next;
    size_t used;
    size_t capacity;
    max_align_t data[];
} MinyarArenaBlock;

typedef struct {
    MinyarArenaBlock *block;
    size_t block_size;
} MinyarArena;

static MinyarArena object_arena = {NULL, 1024 * 1024};
static MinyarArena data_arena = {NULL, 1024 * 1024};
static MinyarArena list_arena = {NULL, 1024 * 1024};
static MinyarArena large_list_arena = {NULL, 4 * 1024 * 1024};

static MINYAR_COLD void *arena_grow(MinyarArena *arena, size_t size, size_t alignment) {
    size_t capacity = size > arena->block_size ? size : arena->block_size;
    MinyarArenaBlock *block;
    if (capacity > SIZE_MAX - sizeof(*block) - alignment)
        out_of_memory();
    block = malloc(sizeof(*block) + capacity);
    if (!block)
        out_of_memory();
    block->next = arena->block;
    block->used = size;
    block->capacity = capacity;
    arena->block = block;
    return block->data;
}

MINYAR_HOT void *arena_allocate(MinyarArena *arena, size_t size, size_t alignment) {
    MinyarArenaBlock *block = arena->block;
    size_t start;
    if (size > SIZE_MAX - alignment)
        out_of_memory();
    if (block) {
        start = (block->used + alignment - 1) & ~(alignment - 1);
        if (start <= block->capacity && size <= block->capacity - start) {
            block->used = start + size;
            return (unsigned char *)block->data + start;
        }
    }
    return arena_grow(arena, size, alignment);
}

/* Extends the newest allocation in place when it ends at the arena top. */
MINYAR_HOT int arena_extend(MinyarArena *arena, const void *pointer, size_t old_size, size_t extra) {
    MinyarArenaBlock *block = arena->block;
    if (!block || extra > block->capacity - block->used)
        return 0;
    if ((const unsigned char *)pointer + old_size != (unsigned char *)block->data + block->used)
        return 0;
    block->used += extra;
    return 1;
}

MINYAR_HOT void *object_allocate(size_t size, unsigned kind) {
    (void)kind;
    return arena_allocate(&object_arena, size, sizeof(void *));
}

MINYAR_HOT void *data_allocate(size_t size, size_t alignment) {
    return arena_allocate(&data_arena, size, alignment);
}

MINYAR_HOT MinyarArena *list_arena_for(long long capacity) {
    return capacity >= LARGE_LIST_CAPACITY ? &large_list_arena : &list_arena;
}

MINYAR_HOT void *list_allocate(long long capacity, size_t size) {
    return arena_allocate(list_arena_for(capacity), size, sizeof(long long));
}
#else
MINYAR_HOT void *object_allocate(size_t size, unsigned kind) {
    return rc_allocate_object(size, kind);
}

MINYAR_HOT void *data_allocate(size_t size, size_t alignment) {
    (void)alignment;
    return rc_allocate_data(size);
}

#endif

void minyar_exit(long long status) {
    exit((int)status);
}

MINYAR_HOT MinyarText *new_text(const unsigned char *bytes, long long byte_length, long long character_length) {
    MinyarText *text = object_allocate(sizeof(*text), 1);
    text->bytes = bytes;
    text->byte_length = byte_length;
    text->character_length = character_length;
    text->character_offsets = NULL;
    return text;
}

/* Text pieces are mostly a few bytes long; copying them with overlapping
   fixed-width loads avoids a library call and never reads past the source. */
MINYAR_HOT void copy_bytes(unsigned char *target, const unsigned char *source, size_t length) {
    if (length > 16) {
        memcpy(target, source, length);
    } else if (length >= 8) {
        uint64_t head, tail;
        memcpy(&head, source, 8);
        memcpy(&tail, source + length - 8, 8);
        memcpy(target, &head, 8);
        memcpy(target + length - 8, &tail, 8);
    } else if (length >= 4) {
        uint32_t head, tail;
        memcpy(&head, source, 4);
        memcpy(&tail, source + length - 4, 4);
        memcpy(target, &head, 4);
        memcpy(target + length - 4, &tail, 4);
    } else if (length >= 2) {
        uint16_t head, tail;
        memcpy(&head, source, 2);
        memcpy(&tail, source + length - 2, 2);
        memcpy(target, &head, 2);
        memcpy(target + length - 2, &tail, 2);
    } else if (length == 1) {
        target[0] = source[0];
    }
}

MINYAR_HOT unsigned char *new_bytes(long long length) {
    return data_allocate((size_t)length + 1, 1);
}

MinyarList *minyar_list_new(void) {
    MinyarList *list = object_allocate(sizeof(*list), 2);
    list->values = NULL;
    list->length = 0;
    list->capacity = 0;
    return list;
}

/* Called once, while an inferred empty List is still empty. */
void minyar_list_references(MinyarList *list) {
#ifndef MINYAR_COMPILER_ARENA
    RcObject *object = (RcObject *)list - 1;
    #ifdef MINYAR_BOUNDED_RC
    unsigned kind = object->ownership & 7;
    if (kind == RC_REFERENCES || kind == RC_REFERENCES_IMMORTAL) return;
    object->ownership = (object->ownership & ~(size_t)7) |
                        (list->length ? RC_REFERENCES : RC_REFERENCES_IMMORTAL);
#else
    object->ownership = (object->ownership & ~(size_t)7) | RC_REFERENCES;
#endif
#else
    (void)list;
#endif
}

static MINYAR_COLD void list_grow(MinyarList *list) {
#if defined(MINYAR_BOUNDED_HEAP) && !defined(MINYAR_COMPILER_ARENA)
    /* Leave room for RcData inside each power-of-two backing block. A capacity
       of 2^n entries plus a header would waste almost half the finite pool. */
    _Static_assert(sizeof(RcData) == sizeof(long long), "bounded List header layout");
    if (list->capacity > (LLONG_MAX - 1) / 2)
        minyar_stop("this List became too large.");
    long long capacity = list->capacity == 0 ? 3 : list->capacity * 2 + 1;
#else
    /* Most Lists stay tiny, so they start small; large ones grow fast enough
       that the copies made before they settle in the large-list arena stay
       a fraction of their final size. */
    long long capacity = list->capacity == 0 ? 2
                       : list->capacity >= LARGE_LIST_CAPACITY ? list->capacity * 4
                       : list->capacity * 2;
#endif
    long long *values;
    if (capacity < list->capacity ||
        (unsigned long long)capacity > SIZE_MAX / sizeof(*values))
        minyar_stop("this List became too large.");
#ifdef MINYAR_COMPILER_ARENA
    if (list->values && list_arena_for(list->capacity) == list_arena_for(capacity) &&
        arena_extend(list_arena_for(capacity), list->values, (size_t)list->capacity * sizeof(*values),
                     (size_t)(capacity - list->capacity) * sizeof(*values))) {
        list->capacity = capacity;
        return;
    }
    values = list_allocate(capacity, (size_t)capacity * sizeof(*values));
    if (list->values)
        memcpy(values, list->values, (size_t)list->length * sizeof(*values));
#else
    values = rc_reallocate_data(list->values, (size_t)capacity * sizeof(*values));
    if (!values)
        out_of_memory();
#endif
    list->values = values;
    list->capacity = capacity;
}

#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
/* The first mortal member permanently promotes an immortal-only List. Service
 * during preceding appends still pays potential scan work if promotion happens
 * later; when no work is pending this is only one cheap count test. */
static inline unsigned list_store_kind(MinyarList *list, long long value, unsigned kind) {
    RcObject *object = (RcObject *)list - 1;
    if (kind == RC_REFERENCES_IMMORTAL && value &&
        (((RcObject *)(uintptr_t)value - 1)->ownership >> 3)) {
        object->ownership = (object->ownership & ~(size_t)7) | RC_REFERENCES;
        kind = RC_REFERENCES;
    }
    return kind;
}
#endif

void minyar_list_add(MinyarList *list, long long value) {
    if (list->length == list->capacity)
        list_grow(list);
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    unsigned kind = ((RcObject *)list - 1)->ownership & 7;
    if (kind == RC_LIST) {
        list->values[list->length++] = value;
        return;
    }
    kind = list_store_kind(list, value, kind);
    if (kind == RC_REFERENCES) minyar_rc_retain((void *)(uintptr_t)value);
    list->values[list->length++] = value;
    if (rc_pending_count) minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
#else
#ifndef MINYAR_COMPILER_ARENA
    if ((((RcObject *)list - 1)->ownership & 7) == RC_REFERENCES)
        minyar_rc_retain((void *)(uintptr_t)value);
#endif
    list->values[list->length++] = value;
#endif
}

/* The compiler transfers an existing owned reference into this new slot. */
void minyar_list_add_take(MinyarList *list, long long value) {
    if (list->length == list->capacity)
        list_grow(list);
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    unsigned kind = ((RcObject *)list - 1)->ownership & 7;
    if (kind == RC_LIST) {
        list->values[list->length++] = value;
        return;
    }
    kind = list_store_kind(list, value, kind);
#endif
    list->values[list->length++] = value;
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    if (rc_pending_count) minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
#endif
}

long long minyar_list_length(const MinyarList *list) {
    return list->length;
}

static MINYAR_COLD MINYAR_NORETURN void list_position_stop(long long position, long long length) {
    char message[128];
    snprintf(message, sizeof(message),
             "List position %lld is outside its length of %lld.",
             position, length);
    minyar_stop(message);
}

long long minyar_list_get(const MinyarList *list, long long position) {
    if ((unsigned long long)position >= (unsigned long long)list->length)
        list_position_stop(position, list->length);
    return list->values[position];
}

void minyar_list_set(MinyarList *list, long long position, long long value) {
    if ((unsigned long long)position >= (unsigned long long)list->length)
        list_position_stop(position, list->length);
#ifndef MINYAR_COMPILER_ARENA
#ifdef MINYAR_BOUNDED_RC
    unsigned kind = list_store_kind(list, value, ((RcObject *)list - 1)->ownership & 7);
    if (kind == RC_REFERENCES) {
#else
    if ((((RcObject *)list - 1)->ownership & 7) == RC_REFERENCES) {
#endif
        minyar_rc_retain((void *)(uintptr_t)value);
        long long previous = list->values[position];
        list->values[position] = value;
        minyar_rc_release((void *)(uintptr_t)previous);
        return;
    }
#endif
    list->values[position] = value;
}

#ifdef MINYAR_BOUNDED_RC
MINYAR_HOT
#else
static
#endif
MinyarRecord *record_allocate(long long field_count, int references) {
    MinyarRecord *record;
    if (field_count < 0 ||
        (unsigned long long)field_count > SIZE_MAX / sizeof(long long))
        minyar_stop("this record has too many fields.");
#ifdef MINYAR_COMPILER_ARENA
    (void)references;
    record = minyar_list_new();
    if (field_count > 0) {
        record->values = list_allocate(field_count, (size_t)field_count * sizeof(*record->values));
        memset(record->values, 0, (size_t)field_count * sizeof(*record->values));
    }
#else
    size_t field_size = sizeof(long long) + (references ? 1 : 0);
    if ((unsigned long long)field_count >
        (SIZE_MAX - sizeof(RcObject) - sizeof(*record)) / field_size)
        out_of_memory();
    record = rc_allocate_object(sizeof(*record) + (size_t)field_count * field_size,
                                references ? RC_RECORD : RC_SCALAR_RECORD);
    memset(record->values, 0, (size_t)field_count * field_size);
#endif
    record->length = field_count;
#ifdef MINYAR_COMPILER_ARENA
    record->capacity = field_count;
#endif
    return record;
}

MinyarRecord *minyar_record_new(long long field_count) {
    return record_allocate(field_count, 1);
}

MinyarRecord *minyar_record_new_scalar(long long field_count) {
    return record_allocate(field_count, 0);
}

long long minyar_record_get(const MinyarRecord *record, long long field) {
    if ((unsigned long long)field >= (unsigned long long)record->length)
        list_position_stop(field, record->length);
    return record->values[field];
}

/* Compiler-selected entry point for scalar-only record fields. */
void minyar_record_set_scalar(MinyarRecord *record, long long field, long long value) {
    if ((unsigned long long)field >= (unsigned long long)record->length)
        list_position_stop(field, record->length);
    record->values[field] = value;
}

void minyar_record_set(MinyarRecord *record, long long field, long long value) {
    if ((unsigned long long)field >= (unsigned long long)record->length)
        list_position_stop(field, record->length);
    record->values[field] = value;
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    if ((((RcObject *)record - 1)->ownership & 7) == RC_RECORD)
        minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
#endif
}

void minyar_record_set_take(MinyarRecord *record, long long field, long long value) {
    if ((unsigned long long)field >= (unsigned long long)record->length)
        list_position_stop(field, record->length);
#ifndef MINYAR_COMPILER_ARENA
    unsigned char *references = (unsigned char *)(record->values + record->length);
    references[field] = 1;
#endif
    minyar_record_set(record, field, value);
}

void minyar_record_set_reference(MinyarRecord *record, long long field, long long value) {
    minyar_rc_retain((void *)(uintptr_t)value);
    minyar_record_set_take(record, field, value);
}

static MinyarText *copy_c_text(const char *source) {
    size_t length = strlen(source);
    unsigned char *bytes = new_bytes((long long)length);
    memcpy(bytes, source, length + 1);
    return new_text(bytes, (long long)length, -1);
}

static char *text_as_path(const MinyarText *text) {
    char *path;
    if (memchr(text->bytes, 0, (size_t)text->byte_length))
        minyar_stop("a file path cannot contain a zero byte.");
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    path = rc_heap_allocate((size_t)text->byte_length + 1);
#else
    path = malloc((size_t)text->byte_length + 1);
#endif
    if (!path)
        out_of_memory();
    memcpy(path, text->bytes, (size_t)text->byte_length);
    path[text->byte_length] = 0;
    return path;
}

void minyar_print_text(const MinyarText *text) {
    fwrite(text->bytes, 1, (size_t)text->byte_length, stdout);
    putchar('\n');
    fflush(stdout);
}

void minyar_fail(const MinyarText *message) {
    fputs("Minyar stopped: ", stderr);
    fwrite(message->bytes, 1, (size_t)message->byte_length, stderr);
    fputc('\n', stderr);
    exit(1);
}

void minyar_print_integer(long long integer) {
    printf("%lld\n", integer);
}

static long long encode_character(int character, unsigned char *bytes);

void minyar_print_character(int character) {
    unsigned char bytes[4];
    long long length = encode_character(character, bytes);
    fwrite(bytes, 1, (size_t)length, stdout);
    putchar('\n');
    fflush(stdout);
}

void minyar_print_boolean(_Bool boolean) {
    puts(boolean ? "true" : "false");
}

/* Names and operators are short; comparing them with overlapping fixed-width
   loads avoids a library call and never reads past either Text. */
MINYAR_HOT int bytes_are_equal(const unsigned char *left, const unsigned char *right, size_t length) {
    if (length > 16)
        return memcmp(left, right, length) == 0;
    if (length >= 8) {
        uint64_t a, b, c, d;
        memcpy(&a, left, 8);
        memcpy(&b, right, 8);
        memcpy(&c, left + length - 8, 8);
        memcpy(&d, right + length - 8, 8);
        return a == b && c == d;
    }
    if (length >= 4) {
        uint32_t a, b, c, d;
        memcpy(&a, left, 4);
        memcpy(&b, right, 4);
        memcpy(&c, left + length - 4, 4);
        memcpy(&d, right + length - 4, 4);
        return a == b && c == d;
    }
    if (length >= 2) {
        uint16_t a, b, c, d;
        memcpy(&a, left, 2);
        memcpy(&b, right, 2);
        memcpy(&c, left + length - 2, 2);
        memcpy(&d, right + length - 2, 2);
        return a == b && c == d;
    }
    return length == 0 || left[0] == right[0];
}

_Bool minyar_texts_are_equal(const MinyarText *left, const MinyarText *right) {
    if (left == right)
        return 1;
    return left->byte_length == right->byte_length &&
           bytes_are_equal(left->bytes, right->bytes, (size_t)left->byte_length);
}

static MINYAR_COLD MINYAR_NORETURN void join_too_large(void) {
    minyar_stop("the joined Text would be too large.");
}

static MinyarText *join_by_copying(const MinyarText *left, const MinyarText *right) {
    long long length = left->byte_length + right->byte_length;
    unsigned char *bytes = new_bytes(length);
    copy_bytes(bytes, left->bytes, (size_t)left->byte_length);
    copy_bytes(bytes + left->byte_length, right->bytes, (size_t)right->byte_length);
    bytes[length] = 0;
    return new_text(bytes, length, -1);
}

MinyarText *minyar_join_text(const MinyarText *left, const MinyarText *right) {
    if (left->byte_length > LLONG_MAX - right->byte_length)
        join_too_large();
#ifdef MINYAR_COMPILER_ARENA
    /* Growing the left Text in place keeps a chain of joins linear. Its
       bytes stay untouched; only the terminator beyond them is overwritten. */
    if (arena_extend(&data_arena, left->bytes, (size_t)left->byte_length + 1, (size_t)right->byte_length)) {
        unsigned char *bytes = (unsigned char *)left->bytes;
        long long length = left->byte_length + right->byte_length;
        copy_bytes(bytes + left->byte_length, right->bytes, (size_t)right->byte_length);
        bytes[length] = 0;
        return new_text(bytes, length, -1);
    }
#endif
    return join_by_copying(left, right);
}

MinyarText *minyar_join_texts(const MinyarList *parts) {
    long long index;
    long long length = 0;
    long long offset = 0;
    unsigned char *bytes;

    for (index = 0; index < parts->length; index++) {
        const MinyarText *part = (const MinyarText *)(intptr_t)parts->values[index];
        if (part->byte_length > LLONG_MAX - length)
            join_too_large();
        length += part->byte_length;
    }
    bytes = new_bytes(length);
    for (index = 0; index < parts->length; index++) {
        const MinyarText *part = (const MinyarText *)(intptr_t)parts->values[index];
        copy_bytes(bytes + offset, part->bytes, (size_t)part->byte_length);
        offset += part->byte_length;
    }
    bytes[length] = 0;
    return new_text(bytes, length, -1);
}

static MINYAR_COLD MINYAR_NORETURN void invalid_utf8(void) {
    minyar_stop("Text contained invalid UTF-8.");
}

static MINYAR_COLD MINYAR_NORETURN void position_outside_text(void) {
    minyar_stop("a Text position was outside the Text.");
}

static unsigned int decode_character(const unsigned char *bytes, long long remaining,
                                     long long *width) {
    unsigned int first;
    if (remaining <= 0)
        position_outside_text();
    first = bytes[0];
    if (first < 0x80) {
        *width = 1;
        return first;
    }
    if (first >= 0xc2 && first <= 0xdf && remaining >= 2 &&
        (bytes[1] & 0xc0) == 0x80) {
        *width = 2;
        return ((first & 0x1f) << 6) | (bytes[1] & 0x3f);
    }
    if ((first & 0xf0) == 0xe0 && remaining >= 3 &&
        (bytes[1] & 0xc0) == 0x80 && (bytes[2] & 0xc0) == 0x80 &&
        (first != 0xe0 || bytes[1] >= 0xa0) &&
        (first != 0xed || bytes[1] < 0xa0)) {
        *width = 3;
        return ((first & 0x0f) << 12) | ((bytes[1] & 0x3f) << 6) |
               (bytes[2] & 0x3f);
    }
    if (first >= 0xf0 && first <= 0xf4 && remaining >= 4 &&
        (bytes[1] & 0xc0) == 0x80 && (bytes[2] & 0xc0) == 0x80 &&
        (bytes[3] & 0xc0) == 0x80 &&
        (first != 0xf0 || bytes[1] >= 0x90) &&
        (first != 0xf4 || bytes[1] < 0x90)) {
        *width = 4;
        return ((first & 0x07) << 18) | ((bytes[1] & 0x3f) << 12) |
               ((bytes[2] & 0x3f) << 6) | (bytes[3] & 0x3f);
    }
    invalid_utf8();
    return 0;
}

static MINYAR_COLD void build_text_index(MinyarText *text) {
    long long byte = 0;
    long long characters = 0;
    long long *offsets;
    while (text->byte_length - byte >= (long long)sizeof(size_t)) {
        const size_t high_bits = (SIZE_MAX / 255) * 128;
        size_t word;
        memcpy(&word, text->bytes + byte, sizeof(word));
        if (word & high_bits)
            break;
        byte += (long long)sizeof(word);
        characters += (long long)sizeof(word);
    }
    while (byte < text->byte_length && text->bytes[byte] < 0x80) {
        byte++;
        characters++;
    }
    while (byte < text->byte_length) {
        long long width;
        decode_character(text->bytes + byte, text->byte_length - byte, &width);
        byte += width;
        characters++;
    }
    if (characters == text->byte_length) {
        text->character_length = characters;
        return;
    }
    if ((unsigned long long)characters >= SIZE_MAX / sizeof(*offsets))
        minyar_stop("this Text is too large to index.");
    offsets = data_allocate((size_t)(characters + 1) * sizeof(*offsets), sizeof(*offsets));
    byte = 0;
    characters = 0;
    while (byte < text->byte_length) {
        long long width;
        offsets[characters++] = byte;
        decode_character(text->bytes + byte, text->byte_length - byte, &width);
        byte += width;
    }
    offsets[characters] = byte;
    text->character_offsets = offsets;
    text->character_length = characters;
}

MINYAR_HOT void ensure_text_index(MinyarText *text) {
    if (text->character_length < 0)
        build_text_index(text);
}

long long minyar_text_length(MinyarText *text) {
    ensure_text_index(text);
    return text->character_length;
}

long long minyar_text_byte_length(const MinyarText *text) {
    return text->byte_length;
}

static MINYAR_COLD int indexed_character_at(const MinyarText *text, long long position) {
    long long byte = text->character_offsets[position];
    long long width;
    return (int)decode_character(text->bytes + byte, text->byte_length - byte, &width);
}

static MINYAR_COLD MINYAR_NORETURN void negative_text_position(void) {
    minyar_stop("a Text position cannot be negative.");
}

static MINYAR_COLD int character_at_slowly(MinyarText *text, long long position) {
    if (position < 0)
        negative_text_position();
    ensure_text_index(text);
    if (position >= text->character_length)
        position_outside_text();
    if (!text->character_offsets)
        return text->bytes[position];
    return indexed_character_at(text, position);
}

int minyar_text_character_at(MinyarText *text, long long position) {
    /* The negative length sentinel must be handled before the unsigned
       bounds check; converting -1 to unsigned would make every index fit. */
    if (text->character_length < 0 ||
        (unsigned long long)position >= (unsigned long long)text->character_length)
        return character_at_slowly(text, position);
    if (text->character_offsets)
        return indexed_character_at(text, position);
    return text->bytes[position];
}

static MINYAR_COLD MINYAR_NORETURN void slice_outside_text(void) {
    minyar_stop("a Text slice must stay within the Text and end after it starts.");
}

MinyarText *minyar_text_slice(MinyarText *text, long long start, long long end) {
    long long first_byte;
    long long last_byte;
    ensure_text_index(text);
    if (start < 0 || end < start || end > text->character_length)
        slice_outside_text();
    if (text->character_offsets) {
        first_byte = text->character_offsets[start];
        last_byte = text->character_offsets[end];
    } else {
        first_byte = start;
        last_byte = end;
    }
#ifdef MINYAR_COMPILER_ARENA
    /* Text is immutable, so a slice can share its source's bytes. A slice of
       ASCII Text is ASCII, so its character count is already known. */
    {
        /* Repeated token slices share headers as well as bytes. This bounded,
           direct-mapped cache never determines equality from its hash: exact
           byte comparison handles collisions. Arena lifetimes retain every
           source; Text joins preserve the original byte range. */
        enum { SLICE_CACHE_SIZE = 1024, SLICE_CACHE_BYTES = 64 };
        static MinyarText *slice_cache[SLICE_CACHE_SIZE];
        long long length = last_byte - first_byte;
        const unsigned char *bytes = text->bytes + first_byte;
        if (length > 0 && length <= SLICE_CACHE_BYTES) {
            unsigned hash = (unsigned)length * 37u + (unsigned)bytes[0] * 101u
                + (unsigned)bytes[length / 2] * 257u + (unsigned)bytes[length - 1] * 65537u;
            unsigned slot = (hash ^ (hash >> 10)) & (SLICE_CACHE_SIZE - 1);
            MinyarText *cached = slice_cache[slot];
            if (cached && cached->byte_length == length &&
                !memcmp(cached->bytes, bytes, (size_t)length))
                return cached;
            cached = new_text(bytes, length, text->character_offsets ? -1 : end - start);
            slice_cache[slot] = cached;
            return cached;
        }
        return new_text(bytes, length, text->character_offsets ? -1 : end - start);
    }
#else
    {
        long long length = last_byte - first_byte;
        unsigned char *bytes = new_bytes(length);
        memcpy(bytes, text->bytes + first_byte, (size_t)length);
        bytes[length] = 0;
        return new_text(bytes, length, text->character_offsets ? -1 : length);
    }
#endif
}

static MINYAR_COLD MinyarText *format_integer_text(long long integer) {
    char buffer[32];
    char *end = buffer + sizeof(buffer);
    char *cursor = end;
    unsigned long long magnitude = integer < 0 ? 0 - (unsigned long long)integer : (unsigned long long)integer;
    do {
        *--cursor = (char)('0' + magnitude % 10);
        magnitude /= 10;
    } while (magnitude);
    if (integer < 0)
        *--cursor = '-';
    {
        long long length = end - cursor;
        unsigned char *bytes = new_bytes(length);
        memcpy(bytes, cursor, (size_t)length);
        bytes[length] = 0;
        return new_text(bytes, length, length);
    }
}

#ifndef MINYAR_INTEGER_TEXT_CACHE_LIMIT
#define MINYAR_INTEGER_TEXT_CACHE_LIMIT 32768
#endif
_Static_assert(MINYAR_INTEGER_TEXT_CACHE_LIMIT >= 0 && MINYAR_INTEGER_TEXT_CACHE_LIMIT <= 32768,
               "Integer Text cache limit must be between 0 and 32768");

MinyarText *minyar_integer_text(long long integer) {
#if MINYAR_INTEGER_TEXT_CACHE_LIMIT > 0
    enum { CACHE_LIMIT = MINYAR_INTEGER_TEXT_CACHE_LIMIT };
    static MinyarText *integer_cache[CACHE_LIMIT];
    if ((unsigned long long)integer < CACHE_LIMIT) {
        if (!integer_cache[integer]) {
            integer_cache[integer] = format_integer_text(integer);
#ifndef MINYAR_COMPILER_ARENA
            ((RcObject *)integer_cache[integer] - 1)->ownership = RC_TEXT;
            RC_ACCOUNT(rc_immortal_object_count++);
#endif
        }
        return integer_cache[integer];
    }
#endif
    return format_integer_text(integer);
}

static long long encode_character(int character, unsigned char *bytes) {
    long long length;
    if (character < 0 || character > 0x10ffff ||
        (character >= 0xd800 && character <= 0xdfff))
        minyar_stop("this Character is not valid Unicode.");
    if (character < 0x80) {
        bytes[0] = (unsigned char)character;
        length = 1;
    } else if (character < 0x800) {
        bytes[0] = 0xc0 | (character >> 6);
        bytes[1] = 0x80 | (character & 0x3f);
        length = 2;
    } else if (character < 0x10000) {
        bytes[0] = 0xe0 | (character >> 12);
        bytes[1] = 0x80 | ((character >> 6) & 0x3f);
        bytes[2] = 0x80 | (character & 0x3f);
        length = 3;
    } else if (character <= 0x10ffff) {
        bytes[0] = 0xf0 | (character >> 18);
        bytes[1] = 0x80 | ((character >> 12) & 0x3f);
        bytes[2] = 0x80 | ((character >> 6) & 0x3f);
        bytes[3] = 0x80 | (character & 0x3f);
        length = 4;
    } else {
        minyar_stop("this Character is not valid Unicode.");
        return 0;
    }
    return length;
}

static MINYAR_COLD MinyarText *encode_character_text(int character) {
    unsigned char encoded[4];
    long long length = encode_character(character, encoded);
    unsigned char *bytes = new_bytes(length);
    memcpy(bytes, encoded, (size_t)length);
    bytes[length] = 0;
    /* A non-ASCII Text needs its offsets built before indexed access. */
    return new_text(bytes, length, -1);
}

MinyarText *minyar_character_text(int character) {
    static struct { size_t ownership; MinyarText text; } ascii_texts[128];
    static unsigned char ascii_bytes[128][2];
    if ((unsigned int)character < 128) {
        MinyarText *text = &ascii_texts[character].text;
        if (text->byte_length == 0) {
            ascii_bytes[character][0] = (unsigned char)character;
            text->bytes = ascii_bytes[character];
            text->byte_length = 1;
            text->character_length = 1;
            text->character_offsets = NULL;
        }
        return text;
    }
    return encode_character_text(character);
}

MinyarText *minyar_boolean_text(_Bool boolean) {
    return copy_c_text(boolean ? "true" : "false");
}

void minyar_initialize_arguments(int count, char **values) {
    saved_argument_count = count;
    saved_argument_values = values;
}

long long minyar_argument_count(void) {
    return saved_argument_count > 0 ? saved_argument_count - 1 : 0;
}

MinyarText *minyar_argument(long long position) {
    if (position < 0 || position >= minyar_argument_count())
        minyar_stop("a program argument position was outside the argument list.");
    return copy_c_text(saved_argument_values[position + 1]);
}

MinyarText *minyar_read_text_file(const MinyarText *path_text) {
    char *path = text_as_path(path_text);
    FILE *file = fopen(path, "rb");
    long length;
    unsigned char *bytes;
    if (!file) {
        fprintf(stderr, "Minyar stopped: the file '%s' could not be opened.\n", path);
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
        rc_heap_deallocate(path);
#else
        free(path);
#endif
        exit(1);
    }
    if (fseek(file, 0, SEEK_END) != 0 || (length = ftell(file)) < 0 ||
        fseek(file, 0, SEEK_SET) != 0)
        minyar_stop("a requested text file could not be read.");
    bytes = new_bytes(length);
    if (fread(bytes, 1, (size_t)length, file) != (size_t)length)
        minyar_stop("a requested text file could not be read.");
    fclose(file);
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    rc_heap_deallocate(path);
#else
    free(path);
#endif
    bytes[length] = 0;
    return new_text(bytes, length, -1);
}

void minyar_write_text_file(const MinyarText *path_text, const MinyarText *contents) {
    char *path = text_as_path(path_text);
    FILE *file = fopen(path, "wb");
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    rc_heap_deallocate(path);
#else
    free(path);
#endif
    if (!file)
        minyar_stop("a requested text file could not be created.");
    if (fwrite(contents->bytes, 1, (size_t)contents->byte_length, file) !=
        (size_t)contents->byte_length || fclose(file) != 0)
        minyar_stop("a requested text file could not be written.");
}

static MINYAR_COLD MINYAR_NORETURN void integer_overflow_stop(void) {
    fputs("Minyar stopped: this Integer calculation is outside the supported range.\n",
          stderr);
    exit(1);
}

void minyar_check_integer_overflow(_Bool overflowed) {
    if (overflowed)
        integer_overflow_stop();
}

static MINYAR_COLD MINYAR_NORETURN void integer_division_stop(const char *message) {
    fputs("Minyar stopped: ", stderr);
    fputs(message, stderr);
    fputc('\n', stderr);
    exit(1);
}

void minyar_check_integer_division(long long left, long long right) {
    if (right == 0)
        integer_division_stop("an Integer cannot be divided by zero.");
    if (left == LLONG_MIN && right == -1)
        integer_division_stop("this Integer division is outside the supported range.");
}
