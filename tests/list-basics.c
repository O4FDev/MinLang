#define MINYAR_RC_TESTING 1
#ifdef MINYAR_LIST_TEST_ENGINE
#include MINYAR_LIST_TEST_ENGINE
#else
#include "../runtime/minyar_runtime.c"
#endif
#include <assert.h>

static void drain(void) {
#ifndef MINYAR_COMPILER_ARENA
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count) assert(minyar_rc_poll(32) > 0);
#endif
#ifdef MINYAR_MAP_CYCLE_RUNTIME
    while (rc_cycle_pending) rc_cycle_unit();
#endif
#endif
}

int main(int argc, char **argv) {
    MinyarList *values = minyar_list_new();
    minyar_list_add(values, 11);
    minyar_list_add(values, 22);
    if (argc > 1) {
        if (!strcmp(argv[1], "empty-pop")) { minyar_list_clear(values); minyar_list_pop(values); }
        if (!strcmp(argv[1], "negative-truncate")) minyar_list_truncate(values, LLONG_MIN);
        if (!strcmp(argv[1], "long-truncate")) minyar_list_truncate(values, LLONG_MAX);
        if (!strcmp(argv[1], "negative-slice")) minyar_list_slice(values, LLONG_MIN, 0, 0);
        if (!strcmp(argv[1], "reversed-slice")) minyar_list_slice(values, 2, 1, 0);
        if (!strcmp(argv[1], "long-slice")) minyar_list_slice(values, 0, LLONG_MAX, 0);
        return 2;
    }
    long long *storage = values->values;
    long long capacity = values->capacity;
    MinyarList *copy = minyar_list_slice(values, 0, 2, 0);
    assert(copy != values && copy->values != storage);
    minyar_list_set(copy, 0, 99);
    assert(minyar_list_get(values, 0) == 11);
    assert(minyar_list_pop(values) == 22 && values->length == 1);
    minyar_list_truncate(values, 1);
    minyar_list_truncate(values, 0);
    assert(values->values == storage && values->capacity == capacity);
    minyar_list_add(values, LLONG_MIN);
    assert(minyar_list_pop(values) == LLONG_MIN);
    MinyarList *empty = minyar_list_slice(values, 0, 0, 0);
    assert(empty->length == 0 && empty->values == NULL);
    minyar_rc_release(empty);
    minyar_rc_release(values);
    minyar_rc_release(copy);

#ifdef MINYAR_MAP_CYCLE_RUNTIME
    values = minyar_list_new_traced();
#else
    values = minyar_list_new();
#endif
    minyar_list_references(values);
    MinyarRecord *first = minyar_record_new(1), *last = minyar_record_new(1);
    minyar_record_set(first, 0, 123);
    minyar_record_set(last, 0, 456);
#ifdef MINYAR_MAP_CYCLE_RUNTIME
    minyar_list_add_traced(values, (long long)(uintptr_t)first);
    minyar_list_add_traced(values, (long long)(uintptr_t)last);
#else
    minyar_list_add(values, (long long)(uintptr_t)first);
    minyar_list_add(values, (long long)(uintptr_t)last);
#endif
    minyar_rc_release(first);
    minyar_rc_release(last);
    copy = minyar_list_slice(values, 0, 2, 1);
    MinyarRecord *removed = (MinyarRecord *)(uintptr_t)minyar_list_pop(values);
    assert(removed == last && removed->values[0] == 456);
    assert(values->values[1] == 0);
    minyar_list_truncate(values, 0);
    assert(values->values[0] == 0);
    minyar_rc_release(values);
    drain();
    assert(((MinyarRecord *)(uintptr_t)copy->values[0])->values[0] == 123);
    minyar_rc_release(copy);
    drain();
    assert(removed->values[0] == 456);
    minyar_rc_release(removed);
    drain();
    MinyarRecord *map = minyar_map_new(2, 1), *other = minyar_map_new(2, 1);
    MinyarText *key = minyar_native_copy_text((const unsigned char *)"100", 3);
    MinyarText *value = minyar_native_copy_text((const unsigned char *)"200", 3);
    minyar_map_set(map, (long long)(uintptr_t)key, (long long)(uintptr_t)value);
    minyar_map_set(other, (long long)(uintptr_t)key, (long long)(uintptr_t)value);
    minyar_rc_release(key); minyar_rc_release(value);
    assert(minyar_maps_are_equal(map, other, 2));
    MinyarList *keys = minyar_map_keys(map);
    assert(keys->length == 1);
    minyar_map_clear(map);
    assert(!minyar_maps_are_equal(map, other, 2));
    minyar_rc_release(map); minyar_rc_release(other); drain();
    key = (MinyarText *)(uintptr_t)keys->values[0];
    assert(key->byte_length == 3 && !memcmp(key->bytes, "100", 3));
    minyar_rc_release(keys); drain();
    map = minyar_map_new(1, 0); other = minyar_map_new(1, 0);
    double positive = 0.0, negative = -0.0, nan = NAN;
    long long a, b, n;
    memcpy(&a, &positive, sizeof(a)); memcpy(&b, &negative, sizeof(b)); memcpy(&n, &nan, sizeof(n));
    minyar_map_set(map, 1, a); minyar_map_set(other, 1, b);
    assert(minyar_maps_are_equal(map, other, 7));
    minyar_map_set(map, 1, n); minyar_map_set(other, 1, n);
    assert(!minyar_maps_are_equal(map, other, 7));
    minyar_rc_release(map); minyar_rc_release(other); drain();
#ifndef MINYAR_COMPILER_ARENA
    assert(rc_object_count == 0 && rc_bytes == 0 && rc_frames == NULL);
#ifdef MINYAR_BOUNDED_HEAP
    assert(minyar_pool_used == 0);
#endif
#endif
    puts("list basics ownership passed");
}
