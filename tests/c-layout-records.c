#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <string.h>

typedef struct {
    uint8_t tag;
    int16_t delta;
    uint32_t count;
    uint64_t mask;
    float narrow;
    double wide;
    bool enabled;
    uint8_t bytes[3];
} Mixed;
typedef struct __attribute__((packed)) {
    uint32_t events;
    uint64_t data;
} Event;
typedef struct {
    uint16_t selector;
    uint64_t base;
} Segment;
typedef struct {
    uint8_t tag;
    Segment segment;
    uint32_t limit;
} Outer;

long long minyar_layout_verify(Mixed *value) {
    unsigned char *bytes = (unsigned char *)value;
    if (sizeof(Mixed) != 40 || _Alignof(Mixed) != 8 || offsetof(Mixed, wide) != 24 ||
        offsetof(Mixed, mask) != 8 || offsetof(Mixed, enabled) != 32)
        return -1;
    if (value->tag != 255 || value->delta != -32768 || value->count != UINT32_MAX ||
        value->mask != UINT64_MAX || value->narrow != 1.25f || value->wide != -3.5 ||
        !value->enabled || value->bytes[0] != 7 || value->bytes[1] != 8 || value->bytes[2] != 9)
        return -2;
    if (bytes[1] || bytes[20] || bytes[21] || bytes[22] || bytes[23] || bytes[36] || bytes[37] ||
        bytes[38] || bytes[39])
        return -3;
    value->delta = 32767;
    value->count = 42;
    return 1;
}

const Mixed *minyar_layout_echo(Mixed *value) {
    return value;
}
const Mixed *minyar_layout_null(void) {
    return NULL;
}
long long minyar_layout_event(Event *event) {
    if (sizeof(Event) != 12 || _Alignof(Event) != 1 || offsetof(Event, data) != 4)
        return -1;
    return event->events == UINT32_MAX && event->data == UINT64_MAX;
}
long long minyar_layout_outer(Outer *value) {
    if (sizeof(Outer) != 32 || offsetof(Outer, segment) != 8 || sizeof(Segment) != 16 ||
        offsetof(Segment, base) != 8)
        return -1;
    return value->tag == 3 && value->segment.selector == 65535 && value->segment.base == 42 &&
           value->limit == 99;
}
long long minyar_layout_address(void) {
    static Segment segment = {10, 42};
    return (long long)(uintptr_t)&segment;
}

typedef struct {
    uint64_t bits;
    double value;
} Pair;
typedef struct {
    double x, y, z;
} HFA;
typedef struct {
    float x, y, z, w;
} FloatHFA;
typedef struct {
    int64_t first, second;
} IntPair;

Pair minyar_layout_pair(Pair value, long long add, double scale) {
    value.bits += (uint64_t)add;
    value.value *= scale;
    return value;
}
HFA minyar_layout_hfa(HFA value) {
    return (HFA){value.z + 1, value.x + 2, value.y + 3};
}
FloatHFA minyar_layout_floatHfa(FloatHFA value) {
    return (FloatHFA){value.w, value.z, value.y, value.x};
}
IntPair minyar_layout_many(long long a, long long b, long long c, long long d, long long e,
                           long long f, IntPair pair, long long g, long long h) {
    return (IntPair){pair.first + a + b + c + d, pair.second + e + f + g + h};
}
Event minyar_layout_packedValue(Event value) {
    value.events += 2;
    value.data ^= UINT64_MAX;
    return value;
}
Mixed minyar_layout_large(Mixed value) {
    value.tag = 1;
    value.delta = -7;
    value.count += 1;
    value.wide += value.narrow;
    value.enabled = !value.enabled;
    return value;
}
Pair minyar_layout_zero(void) {
    return (Pair){UINT64_MAX, 4.5};
}
Outer minyar_layout_nestedValue(Outer value) {
    value.segment.base += value.limit;
    return value;
}

#include "minyar_native.h"
long long minyar_c_answer(void) {
    return 7;
}
long long minyar_layout_appendZero(MinyarBytes *bytes) {
    const unsigned char *address = bytes->bytes;
    long long length = bytes->byte_length;
    unsigned char *result = minyar_native_bytes_append(bytes, 0);
    return result == address + length && bytes->bytes == address && bytes->byte_length == length;
}
long long minyar_layout_append(MinyarBytes *bytes) {
    *minyar_native_bytes_append(bytes, 1) = 7;
    return bytes->byte_length;
}

typedef struct {
    int8_t s8;
    uint8_t u8;
    int16_t s16;
    uint16_t u16;
    int32_t s32;
    uint32_t u32;
    int64_t s64;
    uint64_t u64;
    void *pointer;
    int64_t integer;
    double floating;
    uint32_t character;
} Widths;
long long minyar_layout_widths(Widths *value) {
    if (value->s8 != INT8_MIN || value->u8 != UINT8_MAX || value->s16 != INT16_MIN ||
        value->u16 != UINT16_MAX || value->s32 != INT32_MIN || value->u32 != UINT32_MAX ||
        value->s64 != INT64_MIN || value->u64 != UINT64_MAX || value->pointer ||
        value->integer != 42 || value->floating != 1.5 || value->character != 0x1f642)
        return -1;
    value->s8 = INT8_MAX;
    value->s16 = INT16_MAX;
    value->s32 = INT32_MAX;
    return 1;
}
long long minyar_layout_widthsSize(void) {
    return sizeof(Widths);
}

typedef struct {
    uint64_t bits;
} Single;
long long minyar_layout_nominal(Single *value) {
    return value->bits == 42;
}

extern int minyar_recovery_enter(void);
extern void minyar_stack_leave(void);
static void exhaust_scope(void) {
    unsigned entered = 0;
    while (minyar_recovery_enter())
        entered++;
    while (entered--)
        minyar_stack_leave();
}
const Single *minyar_layout_pendingPointer(void) {
    exhaust_scope();
    return NULL;
}
Single minyar_layout_pendingValue(void) {
    exhaust_scope();
    return (Single){0};
}
