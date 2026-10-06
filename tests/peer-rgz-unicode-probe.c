/* Original runtime-ABI probes for exact pinned Zig UTF-8 value domains.
 * No private new_text symbol or substitute UTF-8 decoder is used. */
#include <assert.h>
#include <limits.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct MinyarText {
    const unsigned char *bytes;
    long long byte_length;
    long long character_length;
    void *character_offsets;
    struct MinyarText *backing;
} MinyarText;

MinyarText *minyar_read_text_file(const MinyarText *path);
long long minyar_text_length(MinyarText *text);
int minyar_text_character_at(MinyarText *text, long long position);
MinyarText *minyar_text_slice(MinyarText *text, long long first, long long end);
MinyarText *minyar_character_text(int character);
void minyar_rc_release(void *value);

static MinyarText *load(const char *path) {
    /* The file reader borrows this path header synchronously and returns an
     * actual owning runtime Text, including when its bytes are malformed. */
    MinyarText path_text = {(const unsigned char *)path, (long long)strlen(path), -1, NULL, NULL};
    MinyarText *text = minyar_read_text_file(&path_text);
    assert(text->character_length == -1 && text->character_offsets == NULL);
    return text;
}

static void bytes(const MinyarText *text) {
    printf("%lld\n", text->byte_length);
    for (long long i = 0; i < text->byte_length; ++i) printf("%u\n", text->bytes[i]);
}

typedef struct {
    MinyarText *text;
    long long character;
    long long byte;
} Cursor;

typedef struct {
    int present;
    MinyarText *value;
} OptionalSlice;

static OptionalSlice next_slice(Cursor *cursor) {
    if (cursor->character == minyar_text_length(cursor->text)) {
        OptionalSlice absent = {0, NULL};
        return absent;
    }
    MinyarText *value = minyar_text_slice(cursor->text, cursor->character, cursor->character + 1);
    ++cursor->character;
    cursor->byte += value->byte_length;
    OptionalSlice present = {1, value};
    return present;
}

static void next_slice_observation(Cursor *cursor) {
    OptionalSlice result = next_slice(cursor);
    printf("%d\n", result.present);
    if (result.present) {
        bytes(result.value);
        minyar_rc_release(result.value);
    }
    printf("%lld\n%lld\n", cursor->character, cursor->byte);
}

static void next_scalar_observation(Cursor *cursor) {
    OptionalSlice result = next_slice(cursor);
    printf("%d\n", result.present);
    if (result.present) {
        printf("%d\n", minyar_text_character_at(result.value, 0));
        minyar_rc_release(result.value);
    }
    printf("%lld\n%lld\n", cursor->character, cursor->byte);
}

static MinyarText *peek(Cursor *cursor, long long count) {
    Cursor lookahead = *cursor;
    for (long long i = 0; i < count; ++i) {
        OptionalSlice part = next_slice(&lookahead);
        if (!part.present) break;
        minyar_rc_release(part.value);
    }
    return minyar_text_slice(cursor->text, cursor->character, lookahead.character);
}

static void peek_observation(Cursor *cursor, long long count) {
    long long original_character = cursor->character, original_byte = cursor->byte;
    MinyarText *value = peek(cursor, count);
    assert(cursor->character == original_character && cursor->byte == original_byte);
    bytes(value);
    printf("%lld\n%lld\n", cursor->character, cursor->byte);
    minyar_rc_release(value);
}

int main(int argc, char **argv) {
    assert(argc >= 3);
    if (strcmp(argv[1], "decode") == 0) {
        assert(argc == 3);
        MinyarText *text = load(argv[2]);
        printf("%lld\n", text->byte_length);
        long long count = minyar_text_length(text);
        printf("%lld\n", count);
        for (long long i = 0; i < count; ++i) printf("%d\n", minyar_text_character_at(text, i));
        minyar_rc_release(text);
    } else if (strcmp(argv[1], "raw") == 0) {
        assert(argc == 3);
        MinyarText *text = load(argv[2]);
        /* Raw ingress is independently observable before any validating
         * character operation; malformed payloads must return successfully. */
        bytes(text);
        assert(text->character_length == -1 && text->character_offsets == NULL);
        minyar_rc_release(text);
    } else if (strcmp(argv[1], "encode") == 0) {
        assert(argc == 3);
        char *end = NULL;
        long scalar = strtol(argv[2], &end, 10);
        assert(*end == 0 && scalar >= 0 && scalar <= INT_MAX);
        MinyarText *text = minyar_character_text((int)scalar);
        bytes(text);
        printf("%lld\n%d\n", minyar_text_length(text), minyar_text_character_at(text, 0));
        minyar_rc_release(text);
    } else if (strcmp(argv[1], "encode-sequence") == 0) {
        assert(argc == 6);
        unsigned char shared_output[4] = {0, 0, 0, 0};
        for (int i = 2; i < argc; ++i) {
            MinyarText *input = load(argv[i]);
            assert(minyar_text_length(input) == 1);
            int scalar = minyar_text_character_at(input, 0);
            MinyarText *encoded = minyar_character_text(scalar);
            assert(encoded->byte_length >= 1 && encoded->byte_length <= 4);
            memcpy(shared_output, encoded->bytes, (size_t)encoded->byte_length);
            printf("%lld\n", encoded->byte_length);
            for (long long j = 0; j < encoded->byte_length; ++j) printf("%u\n", shared_output[j]);
            minyar_rc_release(encoded);
            minyar_rc_release(input);
        }
    } else if (strcmp(argv[1], "invalid") == 0) {
        assert(argc == 3);
        MinyarText *text = load(argv[2]);
        (void)minyar_text_length(text);
        minyar_rc_release(text);
        fputs("invalid UTF-8 unexpectedly accepted\n", stderr);
        return 99;
    } else if (strcmp(argv[1], "suffix") == 0) {
        assert(argc == 3);
        char *end = NULL;
        long offset = strtol(argv[2], &end, 10);
        assert(*end == 0 && offset >= 0 && offset < 548);
        unsigned char backing[551];
        memset(backing, 'a', 550);
        backing[550] = 0xc0;
        /* Every offset uses this complete551-byte original backing. No suffix
         * copy or precomputed character count can bypass strict validation. */
        MinyarText text = {backing + offset, 551 - offset, -1, NULL, NULL};
        assert(text.bytes == &backing[offset] && text.bytes[text.byte_length - 1] == 0xc0);
        (void)minyar_text_length(&text);
        fputs("invalid suffix unexpectedly accepted\n", stderr);
        return 99;
    } else if (strcmp(argv[1], "iterators") == 0) {
        assert(argc == 3);
        MinyarText *text = load(argv[2]);
        Cursor slice_cursor = {text, 0, 0};
        Cursor scalar_cursor = {text, 0, 0};
        for (int i = 0; i < 4; ++i) next_slice_observation(&slice_cursor);
        assert(scalar_cursor.character == 0 && scalar_cursor.byte == 0);
        for (int i = 0; i < 4; ++i) next_scalar_observation(&scalar_cursor);
        minyar_rc_release(text);
    } else if (strcmp(argv[1], "peek") == 0) {
        assert(argc == 3);
        MinyarText *text = load(argv[2]);
        Cursor cursor = {text, 0, 0};
        next_slice_observation(&cursor);
        const long long counts[] = {1, 2, 3, 4, 10};
        for (size_t i = 0; i < sizeof(counts) / sizeof(counts[0]); ++i) peek_observation(&cursor, counts[i]);
        next_slice_observation(&cursor);
        next_slice_observation(&cursor);
        next_slice_observation(&cursor);
        next_slice_observation(&cursor); /* absent; payload never observed */
        peek_observation(&cursor, 1);    /* exact empty slice */
        minyar_rc_release(text);
    } else {
        fputs("unknown Unicode probe mode\n", stderr);
        return 98;
    }
    return 0;
}
