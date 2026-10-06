/* Original adaptation of the common Zig allocator zero/shrink/regrow cases.
 * RcData tracks payload length separately from its nonzero backing header.
 * It promises native scalar alignment, not Zig's arbitrary alignedAlloc API.
 */
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>
#ifndef _WIN32
#include <unistd.h>
#endif

static void length_and_alignment(void *payload, size_t bytes, size_t alignment) {
    assert(payload != NULL);
    assert(((RcData *)payload)[-1].size == bytes);
    assert((uintptr_t)payload % alignment == 0);
    assert(rc_bytes == sizeof(RcData) + bytes);
}

static void exact_prefix(unsigned char *payload, size_t bytes, unsigned char value) {
    for (size_t i = 0; i < bytes; ++i) assert(payload[i] == value);
}

int main(void) {
    assert(rc_bytes == 0 && rc_object_count == 0);
    /* Execute the source's optional-shrink branch when resize is supported.
     * Minyar's data API returns the successful replacement instead of bool.
     * Element count is pointer-width, as in the source *i32 buffer.
     */
    unsigned char *payload = rc_allocate_data(20000 * sizeof(void *));
    memset(payload, 0x5a, 50 * sizeof(void *));
    payload = rc_reallocate_data(payload, 50 * sizeof(void *));
    length_and_alignment(payload, 50 * sizeof(void *), _Alignof(void *));
    exact_prefix(payload, 50 * sizeof(void *), 0x5a);
    payload = rc_reallocate_data(payload, 25 * sizeof(void *));
    length_and_alignment(payload, 25 * sizeof(void *), _Alignof(void *));
    exact_prefix(payload, 25 * sizeof(void *), 0x5a);
    payload = rc_reallocate_data(payload, 0);
    length_and_alignment(payload, 0, _Alignof(void *));
    payload = rc_reallocate_data(payload, 10 * sizeof(void *));
    length_and_alignment(payload, 10 * sizeof(void *), _Alignof(void *));
    memset(payload, 0x36, 10 * sizeof(void *));
    exact_prefix(payload, 10 * sizeof(void *), 0x36);
    rc_free_data(payload);
    assert(rc_bytes == 0);

    payload = rc_allocate_data(0);
    length_and_alignment(payload, 0, 1);
    rc_free_data(payload);
    assert(rc_bytes == 0);

    for (size_t alignment = 1; alignment <= 8; alignment *= 2) {
        payload = rc_allocate_data(10);
        length_and_alignment(payload, 10, alignment);
        memset(payload, 0x71, 10);
        payload = rc_reallocate_data(payload, 100);
        length_and_alignment(payload, 100, alignment);
        exact_prefix(payload, 10, 0x71);
        payload = rc_reallocate_data(payload, 10);
        length_and_alignment(payload, 10, alignment);
        exact_prefix(payload, 10, 0x71);
        payload = rc_reallocate_data(payload, 0);
        length_and_alignment(payload, 0, alignment);
        payload = rc_reallocate_data(payload, 100);
        length_and_alignment(payload, 100, alignment);
        memset(payload, 0x42, 100);
        payload = rc_reallocate_data(payload, 10);
        length_and_alignment(payload, 10, alignment);
        exact_prefix(payload, 10, 0x42);
        payload = rc_reallocate_data(payload, 0);
        length_and_alignment(payload, 0, alignment);
        rc_free_data(payload);
        assert(rc_bytes == 0);
    }
#ifdef _WIN32
    SYSTEM_INFO info;
    GetSystemInfo(&info);
    size_t page = info.dwPageSize;
#else
    long raw_page = sysconf(_SC_PAGESIZE);
    assert(raw_page > 0);
    size_t page = (size_t)raw_page;
#endif
    payload = rc_allocate_data(page + 1);
    payload[0] = 0xa3;
    payload[page] = 0xb4;
    payload = rc_reallocate_data(payload, 1);
    length_and_alignment(payload, 1, 1);
    assert(payload[0] == 0xa3);
    rc_free_data(payload);
    assert(rc_bytes == 0 && rc_object_count == 0 && rc_frames == NULL);
#ifdef MINYAR_BOUNDED_HEAP
    assert(minyar_pool_used == 0);
#endif
    puts("resize-zero-regrow; empty; align1,2,4,8; page-plus-one-shrink; zero-live-bytes");
    return 0;
}
