#define MINYAR_RC_TESTING 1
#ifndef MINYAR_MAP_TEST_ENGINE
#define MINYAR_MAP_TEST_ENGINE "../runtime/minyar_runtime.c"
#endif
#include MINYAR_MAP_TEST_ENGINE
#include <assert.h>

static long long slot(void *p) { return (long long)(uintptr_t)p; }
static void drain(void) {
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count) assert(minyar_rc_poll(1) == 1);
#endif
}
static MinyarText *text(const char *s) {
    return minyar_native_copy_text((const unsigned char *)s, (long long)strlen(s));
}
int main(int argc, char **argv) {
    MinyarRecord *map = minyar_map_new(1, 0);
    if (argc > 1 && !strcmp(argv[1], "missing")) return (int)minyar_map_get(map, 99);
    /* Independent dense-array oracle, including negative keys and replacement. */
    long long values[512] = {0}; unsigned char present[512] = {0};
    uint64_t rng = 71;
    for (int i = 0; i < 12000; i++) {
        rng = rng * UINT64_C(6364136223846793005) + 1;
        unsigned k = (unsigned)(rng >> 32) % 512;
        long long key = (long long)k - 256;
        switch ((rng >> 24) % 4) {
        case 0: case 1:
            minyar_map_set(map, key, i); values[k] = i; present[k] = 1; break;
        case 2:
            assert(minyar_map_remove(map, key) == !!present[k]); present[k] = 0; break;
        default:
            assert(minyar_map_has(map, key) == !!present[k]);
            if (present[k]) assert(minyar_map_get(map, key) == values[k]);
        }
        if (i % 127 == 0) {
            long long count = 0;
            for (int j = 0; j < 512; j++) {
                assert(minyar_map_has(map, j - 256) == !!present[j]);
                if (present[j]) { count++; assert(minyar_map_get(map, j - 256) == values[j]); }
            }
            assert(minyar_map_length(map) == count);
        }
    }
    /* Force a wrapped collision cluster; deleting any position must keep all others. */
    minyar_map_clear(map);
    long long collision[24]; int n = 0;
    for (long long k = 0; n < 24; k++) if ((minyar_map_hash(1, k) & 63) == 63) collision[n++] = k;
    for (int i = 0; i < n; i++) minyar_map_set(map, collision[i], i);
    for (int i = 0; i < n; i++) {
        assert(minyar_map_remove(map, collision[i]));
        for (int j = i + 1; j < n; j++) assert(minyar_map_get(map, collision[j]) == j);
    }
    assert(minyar_map_length(map) == 0);
    minyar_rc_release(map); drain();

    /* Equal independently allocated UTF-8 Text keys, aliases, and managed values. */
    map = minyar_map_new(2, 1);
    MinyarText *key = text("κλειδί"), *equal = text("κλειδί"), *old = text("old"), *new = text("new");
    minyar_rc_retain(map); MinyarRecord *alias = map;
    minyar_map_set(map, slot(key), slot(old));
    assert(minyar_map_get(alias, slot(equal)) == slot(old));
    minyar_rc_retain(old); /* Saved indexed result remains alive after replacement/clear. */
    minyar_map_set(alias, slot(equal), slot(new));
    assert(minyar_map_length(map) == 1);
    assert(minyar_map_get(map, slot(key)) == slot(new));
    minyar_rc_release(key); minyar_rc_release(equal); minyar_rc_release(new);
    minyar_map_clear(alias); drain();
    assert(minyar_map_length(map) == 0 && old->byte_length == 3);
    minyar_rc_release(old); minyar_rc_release(old);
    minyar_rc_release(alias); minyar_rc_release(map); drain();
#if defined(MINYAR_MAP_CYCLE_RUNTIME) && !defined(MINYAR_COMPILER_ARENA)
    /* An untraced bucket still owns traced children. Exercise both replacement
     * and ownership transfer during growth with an active snapshot. */
    map = minyar_map_new(1, 1);
    MinyarRecord *child = minyar_record_new_traced(2);
    minyar_record_set_traced(child, 0, 73);
    minyar_record_set_reference_traced(child, 1, slot(child));
    for (int i = 0; i < 80; i++) minyar_map_set(map, i, slot(child));
    assert((((RcObject *)child - 1)->ownership >> 3) == 82);
    minyar_rc_enable_cycles();
    MinyarRecord *sentinel = minyar_record_new_traced(1);
    minyar_record_set_reference_traced(sentinel, 0, slot(sentinel));
    drain();
    while (rc_cycle_pending) rc_cycle_unit();
    rc_cycle_request();
    rc_cycle_unit();
    assert(rc_cycle_phase == RC_CYCLE_ROOTS && rc_cycle_cursor != rc_cycle_value(child));
    minyar_map_set(map, 1000, slot(child));
#if defined(MINYAR_BOUNDED_RC) && MINYAR_RC_POLL_BUDGET == 1
    assert(rc_cycle_value(child)->marked == 1);
#endif
    assert((((RcObject *)child - 1)->ownership >> 3) == 83);
    minyar_rc_release(child);
    for (int i = 0; i < 40; i++) assert(minyar_map_remove(map, i));
    drain();
    assert(((MinyarRecord *)(uintptr_t)minyar_map_get(map, 79))->values[0] == 73);
    minyar_map_clear(map);
    minyar_rc_release(map);
    minyar_rc_release(sentinel); drain();
    while (rc_cycle_pending) rc_cycle_unit();
#endif
#ifndef MINYAR_COMPILER_ARENA
    assert(rc_object_count == 0 && rc_bytes == 0);
#endif
    puts("map runtime: model, wrapped collisions, growth, removal, UTF-8 aliases and RC recovery");
}
