/* Independent RFC 3629 oracle for the imported Minyar text validator.
 * Decode a scalar, then enforce its width minimum and scalar domain; do not
 * mirror the production validator's restricted second-byte branches. */
#include <stdint.h>
#include "../runtime/minyar_native.h"

static _Bool scalar_at(const MinyarBytes *source, long long *position, uint32_t *decoded) {
    if (*position >= source->byte_length) return 0;
    uint32_t lead = source->bytes[(*position)++], scalar, minimum;
    unsigned int width;
    if ((lead & 0x80) == 0) {
        width = 1;
        scalar = lead;
        minimum = 0;
    } else if ((lead & 0xE0) == 0xC0) {
        /* C0/C1 are rejected below as overlong decoded values. */
        width = 2;
        scalar = lead & 0x1F;
        minimum = 0x80;
    } else if ((lead & 0xF0) == 0xE0) {
        width = 3;
        scalar = lead & 0x0F;
        minimum = 0x800;
    } else if ((lead & 0xF8) == 0xF0) {
        /* F5..F7 are rejected below as scalars above U+10FFFF. */
        width = 4;
        scalar = lead & 0x07;
        minimum = 0x10000;
    } else return 0;
    if ((long long)(width - 1) > source->byte_length - *position) return 0;
    for (unsigned int index = 1; index < width; index++) {
        uint32_t next = source->bytes[(*position)++];
        if ((next & 0xC0) != 0x80) return 0;
        scalar = (scalar << 6) | (next & 0x3F);
    }
    if (scalar < minimum || scalar > 0x10FFFF ||
        (scalar >= 0xD800 && scalar <= 0xDFFF)) return 0;
    *decoded = scalar;
    return 1;
}

_Bool minyar_utf8oracle_reference(const MinyarBytes *source) {
    if (!source || source->byte_length < 0 ||
        (!source->bytes && source->byte_length != 0)) return 0;
    long long position = 0;
    while (position < source->byte_length) {
        uint32_t decoded;
        if (!scalar_at(source, &position, &decoded)) return 0;
    }
    return 1;
}

long long minyar_utf8oracle_scalarValue(const MinyarBytes *source) {
    if (!source || source->byte_length <= 0 || !source->bytes) return -1;
    long long position = 0;
    uint32_t decoded;
    if (!scalar_at(source, &position, &decoded) || position != source->byte_length) return -1;
    return (long long)decoded;
}
