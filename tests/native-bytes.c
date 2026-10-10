/* minyar_native_bytes_append, from the native header, against the real
 * runtime: it appends in place while capacity lasts, grows through
 * minyar_bytes_extend beyond it, and keeps Bytes equal to a simple model.
 * With the argument "negative" it must stop like minyar_bytes_extend. */
#include <assert.h>
#include <stdint.h>
#include "../runtime/minyar_native.h"

void minyar_bytes_clear(MinyarBytes *bytes);
long long minyar_bytes_get(const MinyarBytes *bytes, long long position);

static uint32_t random_state = 0x6d2b79f5;
static uint32_t next_random(void) {
    random_state ^= random_state << 13;
    random_state ^= random_state >> 17;
    random_state ^= random_state << 5;
    return random_state;
}

int main(int argc, char **argv) {
    MinyarBytes *bytes = minyar_bytes_new(0);
    if (argc == 2 && !strcmp(argv[1], "negative")) {
        minyar_native_bytes_append(bytes, -1);
        return 0;
    }

    /* Within capacity: no reallocation, the new bytes follow the old ones. */
    unsigned char *first = minyar_native_bytes_append(bytes, 32);
    memset(first, 0xa1, 32);
    assert(bytes->byte_length == 32 && bytes->character_length >= 32);
    const unsigned char *storage = bytes->bytes;
    long long room = bytes->character_length - bytes->byte_length;
    if (room > 0) {
        unsigned char *next = minyar_native_bytes_append(bytes, room);
        assert(next == storage + 32 && bytes->bytes == storage);
        memset(next, 0xb2, (size_t)room);
    }
    assert(minyar_native_bytes_append(bytes, 0) == storage + bytes->byte_length);

    /* Beyond capacity: grows and keeps the earlier contents. */
    long long before = bytes->byte_length;
    unsigned char *grown = minyar_native_bytes_append(bytes, 1);
    *grown = 0xc3;
    assert(bytes->byte_length == before + 1 && bytes->character_length > before);
    for (long long i = 0; i < 32; i++)
        assert(minyar_bytes_get(bytes, i) == 0xa1);
    for (long long i = 32; i < before; i++)
        assert(minyar_bytes_get(bytes, i) == 0xb2);
    assert(minyar_bytes_get(bytes, before) == 0xc3);

    /* Clearing keeps the capacity, so refilling writes from the start in place. */
    storage = bytes->bytes;
    minyar_bytes_clear(bytes);
    assert(minyar_native_bytes_append(bytes, 16) == storage && bytes->byte_length == 16);

    /* Random appends match a model, across many reallocations. */
    enum { CAPACITY = 1 << 16 };
    static unsigned char expected[CAPACITY];
    minyar_bytes_clear(bytes);
    long long length = 0;
    while (length < CAPACITY - 64) {
        uint32_t random = next_random();
        long long count = random % 41;
        unsigned char *target = minyar_native_bytes_append(bytes, count);
        for (long long i = 0; i < count; i++)
            target[i] = expected[length + i] = (unsigned char)(random >> 8) + (unsigned char)i;
        length += count;
        assert(bytes->byte_length == length && bytes->character_length >= length);
    }
    assert(!memcmp(bytes->bytes, expected, (size_t)length));
    puts("native bytes append ok");
    return 0;
}
