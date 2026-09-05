/* Independent TEST-ONLY physical ownership oracle for deferred destruction.
 * Traversal/count reconstruction live here, never in the shipping runtime.
 * Build: clang -O1 -g -fsanitize=address,undefined this-file.c -o /tmp/oracle
 * Run with ASAN_OPTIONS=detect_leaks=0 on platforms without LeakSanitizer. */
#ifndef MINYAR_SYSTEM_HEAP
#define MINYAR_BOUNDED_HEAP 1
#define MINYAR_BOUNDED_HEAP_BYTES (8u * 1024u * 1024u)
#endif
#define MINYAR_RC_TESTING 1
#ifndef MINYAR_RUNTIME_SOURCE
#define MINYAR_RUNTIME_SOURCE "../../runtime/minyar_runtime.c"
#endif
#include MINYAR_RUNTIME_SOURCE
#include <assert.h>
#ifndef PRODUCTION_EXTRA_OWNER_SCAN
#define PRODUCTION_EXTRA_OWNER_SCAN() 0
#endif

enum { ROOTS = 12, LIMIT = 8192 };
typedef struct { RcObject *object; size_t expected; unsigned dead; } Entry;
static Entry entries[LIMIT];
static size_t entry_count;

static void assert_backend_empty(void) {
#ifdef MINYAR_SYSTEM_HEAP
    assert(!rc_heap_allocation_count);
#else
    assert(!minyar_pool_used);
#endif
}

/* Records are immutable in Minyar; their runtime setters initialize fields.
 * This fixture explicitly balances replaced ownership to explore a larger DAG
 * state space than source construction alone, without assuming setter mutation. */
static void replace_edge(MinyarRecord *record, size_t slot, MinyarRecord *value) {
    minyar_rc_retain(value);
    void *old = (void *)(uintptr_t)record->values[slot];
    minyar_record_set_take(record, (long long)slot, (long long)(uintptr_t)value);
    minyar_rc_release(old);
}

static size_t entry(RcObject *object) {
    for (size_t i = 0; i < entry_count; i++) if (entries[i].object == object) return i;
    assert(entry_count < LIMIT);
    entries[entry_count] = (Entry){object, 0, 0};
    return entry_count++;
}

static size_t saved_record_cursor(MinyarRecord *record) {
#ifdef MINYAR_RC_RECENT_OBJECTS
    unsigned char *map = (unsigned char *)(record->values + record->length);
    size_t cursor = 0;
    /* Decode individual bits independently of the runtime's digit encoding.
     * Bit zero of every map byte remains the ownership flag. */
    for (size_t bit = 0; bit < sizeof(size_t) * CHAR_BIT && bit / 7 < (size_t)record->length; bit++)
        if (map[bit / 7] & (1u << (1 + bit % 7))) cursor |= (size_t)1 << bit;
    assert(cursor <= (size_t)record->length);
    return cursor;
#else
    (void)record;
    return 0;
#endif
}

static void verify(MinyarRecord **roots) {
    entry_count = 0;
    size_t pending = 0;
    for (RcObject *p = rc_bounded_head; p;
         p = (RcObject *)(uintptr_t)(p->ownership & ~(size_t)7)) {
        size_t i = entry(p);
        assert(!entries[i].dead && ++pending < LIMIT);
        entries[i].dead = 1;
    }
#ifdef MINYAR_RC_RECENT_OBJECTS
    for (RcObject *p = rc_bounded_recent_head; p;
         p = (RcObject *)(uintptr_t)(p->ownership & ~(size_t)7)) {
        size_t i = entry(p);
        assert(!entries[i].dead && ++pending < LIMIT);
        entries[i].dead = 1;
    }
#endif
    if (rc_bounded_active) {
        size_t i = entry(rc_bounded_active);
        assert(!entries[i].dead);
        entries[i].dead = 1;
        pending++;
    }
    pending += PRODUCTION_EXTRA_OWNER_SCAN();
    assert(pending == rc_pending_count);
    for (size_t i = 0; i < ROOTS; i++) if (roots[i])
        entries[entry((RcObject *)roots[i] - 1)].expected++;
    /* Include retained edges from dead parents, except those already visited
     * by the suspended active cursor. This independently reconstructs the
     * ownership counts that deferment intentionally preserves. */
    for (size_t i = 0; i < entry_count; i++) {
        RcObject *object = entries[i].object;
        assert((object->ownership & 7) == RC_RECORD);
        MinyarRecord *record = (MinyarRecord *)(object + 1);
        assert(record->length == 4);
        unsigned char *map = (unsigned char *)(record->values + 4);
        size_t first = object == rc_bounded_active ? rc_bounded_cursor
                     : entries[i].dead ? saved_record_cursor(record) : 0;
        for (size_t slot = first; slot < 4; slot++) if ((map[slot] & 1) && record->values[slot])
            entries[entry((RcObject *)(uintptr_t)record->values[slot] - 1)].expected++;
    }
    assert(entry_count == rc_object_count); /* Detect lost pending subgraphs. */
    for (size_t i = 0; i < entry_count; i++) {
        if (entries[i].dead) assert(entries[i].expected == 0);
        else assert(entries[i].expected > 0 &&
                    entries[i].expected == entries[i].object->ownership >> 3);
    }
}

int main(void) {
    MinyarRecord *roots[ROOTS] = {0};
    unsigned random = 318191;
    long long serial = 0;
    for (size_t step = 0; step < 10000; step++) {
        random = random * 1664525u + 1013904223u;
        size_t a = (random >> 8) % ROOTS, b = (random >> 16) % ROOTS;
        size_t slot = 1 + (random >> 24) % 3;
        switch (random % 6) {
        case 0: {
            MinyarRecord *fresh = minyar_record_new(4);
            minyar_record_set(fresh, 0, ++serial);
            minyar_record_set_reference(fresh, slot, (long long)(uintptr_t)roots[b]);
            minyar_rc_release(roots[a]); roots[a] = fresh;
            break;
        }
        case 1:
            minyar_rc_retain(roots[b]); minyar_rc_release(roots[a]); roots[a] = roots[b]; break;
        case 2:
            if (roots[a] && (!roots[b] || roots[a]->values[0] > roots[b]->values[0]))
                replace_edge(roots[a], slot, roots[b]);
            break;
        case 3:
            if (roots[a]) replace_edge(roots[a], slot, (MinyarRecord *)(uintptr_t)roots[a]->values[slot]);
            break;
        case 4:
            minyar_rc_release(roots[a]); roots[a] = NULL; break;
        default:
            assert(minyar_rc_poll((random >> 8) % 64) <= MINYAR_RC_POLL_BUDGET);
        }
        verify(roots);
    }
    for (size_t i = 0; i < ROOTS; i++) { minyar_rc_release(roots[i]); roots[i] = NULL; }
    while (rc_pending_count) { verify(roots); assert(minyar_rc_poll(1) <= 1); }
    verify(roots);
    assert(!rc_object_count && !rc_bytes);
    assert_backend_empty();
    puts("10000 deferred ownership transitions independently reconstructed; no lost objects or backend storage");
    return 0;
}
