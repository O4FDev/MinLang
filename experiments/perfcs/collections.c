/* Actual default system/K32 runtime, included unchanged. The driver snapshots
 * its complete source tree and supplies an absolute MINYAR_RUNTIME_SOURCE.
 * All reported counters cover setup, validation and complete cleanup too.
 */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_RC_TESTING 1
#define MINYAR_INTEGER_TEXT_CACHE_LIMIT 0
#ifndef MINYAR_RUNTIME_SOURCE
#define MINYAR_RUNTIME_SOURCE "../../runtime/minyar_runtime.c"
#endif
#include MINYAR_RUNTIME_SOURCE
#include <assert.h>
#include <errno.h>
#include <inttypes.h>

static uint64_t number(const char *text) {
    char *after;
    errno = 0;
    unsigned long long value = strtoull(text, &after, 10);
    assert(!errno && text[0] && text[0] != '-' && !*after && value && value <= 65536);
    return value;
}

/* Keep repeated API calls observable to the optimizer without generating a
 * runtime instruction or changing the runtime implementation. In particular,
 * the compiler must not hoist a pure hash/length read out of a measured loop.
 */
static inline void memory_observation(void) {
#if defined(__GNUC__) || defined(__clang__)
    __asm__ __volatile__("" ::: "memory");
#else
#error this benchmark needs a compiler memory barrier
#endif
}

static void drain(void) {
    while (rc_pending_count) {
        size_t work = minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
        assert(work && work <= MINYAR_RC_POLL_BUDGET);
    }
    assert(!rc_frames && !map_active_reads);
    assert(!rc_object_count && !rc_bytes && !rc_immortal_object_count);
    assert(!rc_heap_allocation_count);
}

static uint64_t map_hashing(uint64_t bytes, uint64_t queries, int set) {
    unsigned char *storage = new_bytes((long long)bytes);
    for (uint64_t i = 0; i < bytes; i++) storage[i] = (unsigned char)('a' + i % 23);
    storage[bytes] = 0;
    MinyarText *key = new_text(storage, (long long)bytes, (long long)bytes);
    MinyarRecord *map = minyar_map_new(2, 0);
    minyar_map_set(map, (long long)(uintptr_t)key, set ? 1 : 11);
    MinyarRecord *alias = map;
    minyar_rc_retain(alias);
    MinyarText *equal_key = minyar_native_copy_text(storage, (long long)bytes);
    assert(equal_key != key && minyar_map_has(alias, (long long)(uintptr_t)equal_key));
    assert(minyar_map_get(alias, (long long)(uintptr_t)equal_key) == (set ? 1 : 11));
    minyar_rc_release(equal_key);
    uint64_t sum = 0;
    for (uint64_t i = 0; i < queries; i++) {
        memory_observation();
        if (set) {
            _Bool present = minyar_map_has(map, (long long)(uintptr_t)key);
            assert(present);
            sum += present;
        } else {
            long long value = minyar_map_get(map, (long long)(uintptr_t)key);
            assert(value == 11);
            sum += (uint64_t)value;
        }
    }
    assert(minyar_map_length(alias) == 1 && key->byte_length == (long long)bytes);
    for (uint64_t i = 0; i < bytes; i++) assert(key->bytes[i] == 'a' + i % 23);
    minyar_rc_release(alias);
    minyar_rc_release(map);
    minyar_rc_release(key);
    drain();
    assert(sum == queries * (set ? 1 : 11));
    return sum;
}

static uint64_t sparse_map(uint64_t count, uint64_t repeats, int empty,
                           uint64_t *peak_capacity) {
    MinyarRecord *map = minyar_map_new(1, 0), *peer = minyar_map_new(1, 0);
    MinyarRecord *alias = map;
    minyar_rc_retain(alias);
    for (uint64_t i = 0; i < count; i++) minyar_map_set(map, (long long)i, (long long)i + 5);
    *peak_capacity = (uint64_t)map_array(map, MAP_HASHES)->length;
    assert(*peak_capacity >= count);
    for (uint64_t i = empty ? 0 : 1; i < count; i++) assert(minyar_map_remove(alias, (long long)i));
    if (!empty) minyar_map_set(peer, 0, 5);
    assert(minyar_map_length(alias) == !empty);
    assert((uint64_t)map_array(map, MAP_HASHES)->length == *peak_capacity);
    uint64_t sum = 0;
    for (uint64_t i = 0; i < repeats; i++) {
        memory_observation();
        MinyarList *keys = minyar_map_keys(map);
        assert(minyar_list_length(keys) == !empty);
        if (!empty) {
            assert(minyar_list_get(keys, 0) == 0);
            assert(minyar_map_get(alias, 0) == 5);
        }
        _Bool equal = minyar_maps_are_equal(map, peer, 1);
        assert(equal);
        sum += (uint64_t)minyar_list_length(keys) + equal;
        minyar_rc_release(keys);
    }
    minyar_rc_release(peer);
    minyar_rc_release(alias);
    minyar_rc_release(map);
    drain();
    assert(sum == repeats * (empty ? 1 : 2));
    return sum;
}

static long long list_value(uint64_t index) { return (long long)(index * 17 + 3); }

static uint64_t list_build(uint64_t count, uint64_t repeats, int mode,
                           int full_check, uint64_t *peak_capacity) {
    uint64_t sum = 0;
    for (uint64_t repetition = 0; repetition < repeats; repetition++) {
        MinyarList *list = minyar_list_new();
        for (uint64_t i = 0; i < count; i++) {
            memory_observation();
            if (mode == 0) minyar_list_add(list, list_value(i));
            else if (mode == 1) {
                MinyarList *previous = list;
                list = minyar_list_appended_take(list, list_value(i), 0, 0);
                assert(list == previous);
            } else {
                MinyarList *alias = list;
                minyar_rc_retain(alias);
                list = minyar_list_appended_take(list, list_value(i), 0, 0);
                assert(list != alias && alias->length == (long long)i);
                if (i) {
                    assert(minyar_list_get(alias, 0) == list_value(0));
                    assert(minyar_list_get(alias, (long long)i - 1) == list_value(i - 1));
                }
                /* Exhaustive previous-prefix checking runs in the small
                 * correctness campaign, not in retained scaling samples. */
                if (full_check)
                    for (uint64_t j = 0; j < i; j++) assert(minyar_list_get(alias, (long long)j) == list_value(j));
                minyar_rc_release(alias);
            }
        }
        MinyarList *alias = list;
        minyar_rc_retain(alias);
        assert(alias->length == (long long)count && alias->capacity >= alias->length);
        if ((uint64_t)alias->capacity > *peak_capacity) *peak_capacity = (uint64_t)alias->capacity;
        for (uint64_t i = 0; i < count; i++) {
            long long value = minyar_list_get(alias, (long long)i);
            assert(value == list_value(i));
            sum += (uint64_t)value;
        }
        minyar_rc_release(list);
        assert(alias->length == (long long)count && minyar_list_get(alias, (long long)count - 1) == list_value(count - 1));
        minyar_rc_release(alias);
        drain();
    }
    assert(sum == repeats * (17 * count * (count - 1) / 2 + 3 * count));
    return sum;
}

static uint64_t text_build(uint64_t count, uint64_t repeats, int mode,
                           uint64_t *observed_scalar_sum) {
    static const unsigned char piece_bytes[] = {0xc3, 0xa9, 0xf0, 0x9f, 0x99, 0x82}; /* é🙂 */
    uint64_t sum = 0;
    for (uint64_t repetition = 0; repetition < repeats; repetition++) {
        MinyarText *piece = minyar_native_copy_text(piece_bytes, sizeof(piece_bytes));
        MinyarText *text;
        if (mode == 2) {
            MinyarList *parts = minyar_list_new();
            minyar_list_references(parts);
            for (uint64_t i = 0; i < count; i++) minyar_list_add(parts, (long long)(uintptr_t)piece);
            text = minyar_join_texts(parts);
            minyar_rc_release(parts);
        } else {
            unsigned char *bytes = new_bytes(0);
            bytes[0] = 0;
            text = new_text(bytes, 0, 0);
            for (uint64_t i = 0; i < count; i++) {
                memory_observation();
                MinyarText *previous = text;
                text = minyar_join_text_take_left(text, piece);
                assert(text == previous);
                if (mode == 1) {
                    long long length = minyar_text_length(text);
                    assert(length == (long long)(2 * (i + 1)));
                    *observed_scalar_sum += (uint64_t)length;
                }
            }
        }
        MinyarText *alias = text;
        minyar_rc_retain(alias);
        assert(text->byte_length == (long long)(6 * count));
        assert(minyar_text_length(text) == (long long)(2 * count));
        for (uint64_t i = 0; i < count; i++) {
            assert(!memcmp(text->bytes + 6 * i, piece_bytes, sizeof(piece_bytes)));
            assert(minyar_text_character_at(text, (long long)(2 * i)) == 0xe9);
            assert(minyar_text_character_at(text, (long long)(2 * i + 1)) == 0x1f642);
            for (unsigned j = 0; j < sizeof(piece_bytes); j++) sum += text->bytes[6 * i + j];
        }
        minyar_rc_release(text);
        assert(alias->byte_length == (long long)(6 * count) && minyar_text_length(alias) == (long long)(2 * count));
        minyar_rc_release(alias);
        minyar_rc_release(piece);
        drain();
    }
    assert(sum == repeats * count * 1046);
    assert(*observed_scalar_sum == (mode == 1 ? repeats * count * (count + 1) : 0));
    return sum;
}

int main(int argc, char **argv) {
    assert(argc == 4 || (argc == 5 && !strcmp(argv[4], "--full-check")));
    const char *kernel = argv[1];
    uint64_t count = number(argv[2]), repeats = number(argv[3]);
    uint64_t checksum = 0, peak = 0, observed = 0;
    int full_check = argc == 5;
    if (!strcmp(kernel, "map-hash")) checksum = map_hashing(count, repeats, 0);
    else if (!strcmp(kernel, "set-hash")) checksum = map_hashing(count, repeats, 1);
    else if (!strcmp(kernel, "map-sparse")) checksum = sparse_map(count, repeats, 0, &peak);
    else if (!strcmp(kernel, "map-empty")) checksum = sparse_map(count, repeats, 1, &peak);
    else if (!strcmp(kernel, "list-add")) checksum = list_build(count, repeats, 0, full_check, &peak);
    else if (!strcmp(kernel, "list-unique-appended")) checksum = list_build(count, repeats, 1, full_check, &peak);
    else if (!strcmp(kernel, "list-aliased-appended")) checksum = list_build(count, repeats, 2, full_check, &peak);
    else if (!strcmp(kernel, "text-append")) checksum = text_build(count, repeats, 0, &observed);
    else if (!strcmp(kernel, "text-append-length")) checksum = text_build(count, repeats, 1, &observed);
    else if (!strcmp(kernel, "text-join")) checksum = text_build(count, repeats, 2, &observed);
    else { fprintf(stderr, "unknown collections kernel: %s\n", kernel); return 2; }
    drain();
    printf("{\"kernel\":\"%s\",\"size\":%" PRIu64 ",\"repeats\":%" PRIu64
           ",\"checksum\":%" PRIu64 ",\"peak_capacity\":%" PRIu64
           ",\"observed_scalar_sum\":%" PRIu64 ",\"live_objects\":0,\"live_bytes\":0,\"pending\":0}\n",
           kernel, count, repeats, checksum, peak, observed);
    return 0;
}
