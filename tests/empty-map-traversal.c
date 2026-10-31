/* Private differential fixture; only the parent may build/run it through BX. */
#include <stddef.h>
static void fixture_guard(int phase);
static void fixture_poll(size_t budget, size_t work);
#define MINYAR_RC_TESTING 1
#define MINYAR_INTEGER_TEXT_CACHE_LIMIT 0
#include MINYAR_RUNTIME_SOURCE
#include <assert.h>

static int observing, mutate_callback, recover_callback;
static size_t hashes_called, equals_called, copies_called, guards, ends, polls, expected_polls, guard_depth;
static struct { const MinyarMapReadGuard *guard; size_t first, second; } guard_stack[16];
static const MinyarRecord *watch_first, *watch_second;
static size_t first_count, second_count;
static MinyarMapReadGuard *outer_guard;
static MinyarRecord *mutation_map;
static long long slot(const void *p) { return (long long)(uintptr_t)p; }
static size_t refs(const void *p) {
#ifndef MINYAR_COMPILER_ARENA
    return p ? ((const RcObject *)p - 1)->ownership >> 3 : 0;
#else
    (void)p; return 0;
#endif
}
static void fixture_poll(size_t budget, size_t work) {
    if (!observing) return;
    polls++;
#ifdef MINYAR_BOUNDED_RC
    assert(work <= budget && work <= MINYAR_RC_POLL_BUDGET);
    assert(work == rc_bounded_last_work);
    assert(!rc_bounded_frame_head && !rc_bounded_chunk_head);
    printf("poll %zu/%zu pending=%zu live=%zu bytes=%zu next=%u parity=%u active=%u/%zu",
           budget, work, rc_pending_count, rc_object_count, rc_bytes,
           rc_bounded_next_queue, rc_bounded_recent_turn, !!rc_bounded_active, rc_bounded_cursor);
    RcObject *heads[2] = {rc_bounded_head, rc_bounded_recent_head};
    for (unsigned q = 0; q < 2; q++) {
        printf(" queue%u[", q);
        for (RcObject *o = heads[q]; o; o = (RcObject *)(uintptr_t)(o->ownership & ~(size_t)7))
            printf("%zu/%zu,", o->ownership & 7, rc_bounded_saved_cursor(o));
        putchar(']');
    }
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
    printf(" cycle=%u/%u/%zu/%zu/%zu/%zu", rc_cycle_pending, rc_cycle_phase,
           rc_cycle_index, rc_cycle_limit, rc_cycle_units, rc_cycle_completed);
#endif
    putchar('\n');
#else
    (void)budget; (void)work;
#endif
}
static void fixture_guard(int phase) {
    if (!observing) return;
    if (phase == 1) {
        assert(map_active_reads && guard_depth < 16);
        if (!guard_depth) {
            assert(map_active_reads->first == watch_first && map_active_reads->second == watch_second);
            assert(map_active_reads->previous == outer_guard);
#ifndef MINYAR_COMPILER_ARENA
            assert(refs(watch_first) == first_count + 1);
            if (watch_second) assert(refs(watch_second) == second_count + 1);
#endif
        }
        guard_stack[guard_depth].guard = map_active_reads;
        guard_stack[guard_depth].first = refs(map_active_reads->first);
        guard_stack[guard_depth++].second = refs(map_active_reads->second);
        expected_polls += 1 + !!map_active_reads->second; guards++;
    }
    assert(guard_depth);
    const MinyarMapReadGuard *guard = guard_stack[guard_depth - 1].guard;
    assert(map_active_reads == (phase < 0 ? guard->previous : guard));
#ifndef MINYAR_COMPILER_ARENA
    assert(refs(guard->first) == guard_stack[guard_depth - 1].first - (phase < 0));
    assert(refs(guard->second) == guard_stack[guard_depth - 1].second - (phase < 0 && !!guard->second));
#endif
    printf("guard %d depth=%zu refs=%zu/%zu nested=%u\n", phase, guard_depth,
           refs(guard->first), refs(guard->second), !!guard->previous);
    if (phase < 0) { guard_depth--; ends++; }
}
static uint64_t key_hash(const MinyarRecord *key) {
    hashes_called++;
    if (mutate_callback) minyar_map_clear(mutation_map);
    return (uint64_t)key->values[0] + 1;
}
static _Bool key_equal(const MinyarRecord *a, const MinyarRecord *b) {
    equals_called++;
    assert(map_active_reads);
    if (recover_callback) assert(!minyar_recovery_enter());
    return a->values[0] == b->values[0];
}
static MinyarRecord *key_copy(const MinyarRecord *key) {
    copies_called++;
    MinyarRecord *copy = minyar_record_new_scalar(1);
    minyar_record_set(copy, 0, key->values[0]); return copy;
}
static MinyarRecord *new_map(long long kind, int references) {
    return kind == 1000 ? minyar_map_new_record(kind, references, key_hash, key_equal, key_copy)
                        : minyar_map_new(kind, references);
}
static long long key_new(long long kind, int i) {
    if (kind == 1) return i;
    if (kind == 1000) { MinyarRecord *k = minyar_record_new_scalar(1); minyar_record_set(k, 0, i); return slot(k); }
    char bytes[32]; int n = snprintf(bytes, sizeof(bytes), "key-%d-κ", i);
    return slot(minyar_native_copy_text((const unsigned char *)bytes, n));
}
static void release_key(long long kind, long long key) {
    if (kind != 1) minyar_rc_release((void *)(uintptr_t)key);
}
static void drain(void) {
#ifdef MINYAR_BOUNDED_RC
    size_t turns = 0;
    while (rc_pending_count) { assert(++turns < 100000); assert(minyar_rc_poll(1) == 1); }
#else
    minyar_rc_release(NULL);
#endif
}
static void debt(void) {
    drain();
#ifdef MINYAR_BOUNDED_RC
    MinyarRecord *record = minyar_record_new(513);
    minyar_rc_release(record); assert(rc_pending_count);
#endif
}
static void equal_case(const char *name, MinyarRecord *a, MinyarRecord *b, long long type, int expected) {
    debt(); watch_first = a; watch_second = b != a ? b : NULL;
    first_count = refs(a); second_count = refs(watch_second);
    guards = ends = polls = expected_polls = hashes_called = equals_called = copies_called = 0;
    observing = 1; int result = minyar_maps_are_equal(a, b, type); observing = 0;
    assert(result == expected && map_active_reads == outer_guard);
    assert(refs(a) == first_count && refs(watch_second) == second_count);
    int enters = !minyar_recovery_pending() && a && b && a->values[MAP_LENGTH] == b->values[MAP_LENGTH]
        && a->values[MAP_KEY_KIND] == b->values[MAP_KEY_KIND];
    /* A callback may create recovery after guard entry. */
    if (recover_callback) enters = 1;
    if (enters && !guards) {
        fputs("empty-map guard invariant: missing equality read guard\n", stderr); abort();
    }
    assert((enters ? guards >= 1 : guards == 0) && ends == guards && !guard_depth);
    if (enters && !a->values[MAP_LENGTH]) assert(guards == 1);
#ifdef MINYAR_BOUNDED_RC
    /* A unit retires a whole small subtree, so one service point can finish
     * what the guard released: never more service points than released
     * references, but possibly fewer. */
    assert(polls <= expected_polls);
#endif
    if (a && !a->values[MAP_LENGTH]) assert(!hashes_called && !equals_called && !copies_called);
    printf("equal %s type=%lld result=%d guards=%zu polls=%zu calls=%zu/%zu/%zu\n",
           name, type, result, guards, polls, hashes_called, equals_called, copies_called);
    drain();
}
static void keys_case(MinyarRecord *map) {
    debt(); hashes_called = equals_called = copies_called = polls = 0;
    observing = 1; MinyarList *keys = minyar_map_keys(map); observing = 0;
    assert(keys && (void *)keys != (void *)map_entries(map) && !keys->length && !keys->capacity && !keys->values);
#ifndef MINYAR_COMPILER_ARENA
    size_t kind = ((RcObject *)keys - 1)->ownership & 7;
    size_t expected_kind = (size_t)(map_key_references(map->values[MAP_KEY_KIND]) ?
#ifdef MINYAR_BOUNDED_RC
                          RC_REFERENCES_IMMORTAL : RC_LIST);
#else
                          RC_REFERENCES : RC_LIST);
#endif
    if (kind != expected_kind) {
        fputs("empty-map kind invariant: wrong empty result reference kind\n", stderr); abort();
    }
    assert(kind == expected_kind);
#endif
    assert(!hashes_called && !equals_called && !copies_called);
#ifdef MINYAR_BOUNDED_RC
    assert(polls == 1);
#endif
    printf("keys kind=%lld capacity=%lld polls=%zu\n", map->values[MAP_KEY_KIND], (long long)map_capacity(map), polls);
    minyar_rc_release(keys); drain();
}
int main(int argc, char **argv) {
    (void)argv; fixture_poll(0, 0);
    if (argc > 1) {
        mutation_map = new_map(1000, 0); long long k = key_new(1000, 1);
        mutate_callback = 1; (void)minyar_map_has(mutation_map, k); assert(!"mutation guard accepted write");
    }
#if defined(MINYAR_CYCLE_LOCAL_PROOFS)
    MinyarRecord *cycle = minyar_record_new_traced(1);
    minyar_record_set_reference_traced(cycle, 0, slot(cycle)); drain(); assert(rc_cycle_present);
#endif
    const long long kinds[] = {1, 2, 1000}, types[] = {1, 2, 7, -17, 32};
    for (size_t k = 0; k < 3; k++) for (int history = 0; history < 2; history++) {
        MinyarRecord *a = new_map(kinds[k], 1), *b = new_map(kinds[k], 1);
        for (int i = 0; history && i < 16; i++) {
            long long key = key_new(kinds[k], i); MinyarRecord *value = minyar_map_new(1, 0);
            minyar_map_set(a, key, slot(value)); minyar_map_set(b, key, slot(value));
            release_key(kinds[k], key); minyar_rc_release(value);
        }
        for (int i = 0; history && i < 16; i++) {
            long long key = key_new(kinds[k], i);
            assert(minyar_map_remove(a, key) && minyar_map_remove(b, key)); release_key(kinds[k], key);
        }
        assert(!a->values[MAP_LENGTH] && !b->values[MAP_LENGTH]);
        assert((map_capacity(a) > 0) == history);
        for (size_t i = 0; i < map_capacity(a); i++) assert(!MAP_HASH(map_entries(a), i));
        minyar_rc_retain(a); keys_case(a);
        MinyarMapReadGuard outer; map_read_begin(&outer, a, NULL); outer_guard = &outer;
        for (size_t t = 0; t < 5; t++) equal_case("empty-distinct", a, b, types[t], 1);
        equal_case("empty-alias", a, a, 7, 1);
        MinyarDepthScope scope; minyar_calldepth_begin(&scope, 0); assert(!minyar_recovery_enter());
        equal_case("pending-recovery", a, b, 1, 0); assert(minyar_calldepth_end(&scope) == 1);
        outer_guard = NULL; map_read_end(&outer);
        minyar_rc_release(a); minyar_rc_release(a); minyar_rc_release(b); drain();
    }
    MinyarRecord *a = new_map(1, 1), *b = new_map(1, 1), *x = new_map(1, 0), *y = new_map(1, 0);
    minyar_map_set(x, 1, 8); minyar_map_set(y, 1, 8);
    minyar_map_set(a, 3, slot(x)); minyar_map_set(b, 3, slot(y)); equal_case("nested", a, b, -17, 1);
    minyar_map_set(y, 1, 9); equal_case("nested-different", a, b, -17, 0);
    minyar_rc_release(a); minyar_rc_release(b); minyar_rc_release(x); minyar_rc_release(y);
    a = new_map(1, 0); b = new_map(2, 0); equal_case("kind", a, b, 1, 0);
    minyar_rc_release(b); b = new_map(1, 0); minyar_map_set(a, 1, INT64_C(0x7ff8000000000001));
    equal_case("length", a, b, 7, 0); equal_case("nan-alias", a, a, 7, 0);
    minyar_rc_release(a); minyar_rc_release(b);
    a = new_map(1000, 0); b = new_map(1000, 0); long long key = key_new(1000, 7);
    minyar_map_set(a, key, 8); minyar_map_set(b, key, 8); release_key(1000, key);
    MinyarDepthScope scope; minyar_calldepth_begin(&scope, 0); recover_callback = 1;
    equal_case("callback-recovery", a, b, 1, 0); recover_callback = 0;
    assert(minyar_calldepth_end(&scope) == 1 && !map_active_reads);
    minyar_rc_release(a); minyar_rc_release(b); equal_case("null", NULL, NULL, 1, 1);
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
    /* Construction setters do not release an old owning edge. */
    minyar_record_replace_traced(cycle, 0, 0, 0); minyar_rc_release(cycle);
#endif
    drain(); assert(!map_active_reads && !minyar_recovery_pending());
#ifndef MINYAR_COMPILER_ARENA
    assert(!rc_object_count && !rc_bytes && !rc_frames && !rc_free_frames);
#ifdef MINYAR_BOUNDED_RC
    rc_bounded_chunk_cache_clear(); assert(!rc_bounded_cached_frame_bytes);
#ifdef MINYAR_SYSTEM_HEAP
    assert(!rc_heap_allocation_count);
#else
    assert(!minyar_pool_used); void *whole = minyar_pool_try_allocate(MINYAR_POOL_BYTES);
    assert(whole == minyar_pool); minyar_pool_deallocate(whole);
#endif
#else
    free(rc_pending);
#endif
#else
    /* The compiler arena keeps its memory in regions, so it returns them as
     * one unit. */
    minyar_arena_release();
#endif
    puts("empty Map traversal: exact results, callbacks, guards, cleanup and full recovery");
}
