/* Direct frame-exit and statement-cleanup service must match the scheduler.
 * Build once with the default runtime and once with -DMINYAR_RC_DIRECT_SERVICE=0
 * (frames, temporaries and statements always go through the queues), at the
 * same MINYAR_RC_POLL_BUDGET; the two transcripts must be identical. Random
 * programs mix frames with written slots, overwritten slots, borrowed and kept
 * temporaries, statement ends, nested calls, shared and fresh graphs, and old
 * backlogs, so every service point is reached with and without backlog credit
 * due and with releases that queue objects part way through. */
#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_RC_TESTING 1
static void transcript_freed(void *object);
#define MINYAR_RC_OBJECT_RELEASE_OBSERVER transcript_freed
#include "../runtime/minyar_runtime.c"
#include <assert.h>

enum { IDS = 1 << 16 };
static void *id_pointer[IDS];
static unsigned id_value[IDS];
static unsigned next_id = 1;
static unsigned long long freed_hash;
static size_t freed_count;

static size_t id_slot(void *pointer) {
    size_t slot = ((uintptr_t)pointer >> 4) & (IDS - 1);
    while (id_pointer[slot] && id_pointer[slot] != pointer) slot = (slot + 1) & (IDS - 1);
    return slot;
}
static void *named(void *value) {
    RcObject *object = (RcObject *)value - 1;
    size_t slot = id_slot(object);
    assert(!id_pointer[slot]);
    id_pointer[slot] = object;
    id_value[slot] = next_id++;
    return value;
}
static void transcript_freed(void *pointer) {
    size_t slot = id_slot(pointer);
    assert(id_pointer[slot] == pointer);
    freed_hash = freed_hash * 1000003u + id_value[slot];
    freed_count++;
    /* Reinsert the probe run after this slot so later lookups stay exact. */
    id_pointer[slot] = NULL;
    for (size_t next = (slot + 1) & (IDS - 1); id_pointer[next]; next = (next + 1) & (IDS - 1)) {
        void *moved = id_pointer[next];
        unsigned value = id_value[next];
        id_pointer[next] = NULL;
        size_t target = id_slot(moved);
        id_pointer[target] = moved;
        id_value[target] = value;
    }
}

static unsigned random_state;
static unsigned rnd(unsigned bound) {
    random_state = random_state * 1664525u + 1013904223u;
    return (random_state >> 8) % bound;
}

enum { POOL = 12 };
static void *pool[POOL];

static void *make(unsigned depth);
static void *make_child(unsigned depth) {
    if (depth == 0 || rnd(4) == 0) {
        void *shared = pool[rnd(POOL)];
        if (!shared) return named(copy_c_text("leaf"));
        minyar_rc_retain(shared);
        return shared;
    }
    return make(depth - 1);
}
/* One owned reference to a new random object. */
static void *make(unsigned depth) {
    switch (rnd(depth ? 6 : 3)) {
    case 0: {
        MinyarRecord *leaf = named(minyar_record_new_scalar(1));
        minyar_record_set(leaf, 0, 7);
        return leaf;
    }
    case 1: return named(copy_c_text("transcript text"));
    case 2: return named(minyar_list_new());
    case 3: {
        MinyarRecord *record = named(minyar_record_new(1));
        minyar_record_set_take(record, 0, (long long)(uintptr_t)make_child(depth));
        return record;
    }
    case 4: {
        MinyarList *list = named(minyar_list_new());
        minyar_list_references(list);
        for (unsigned i = rnd(7); i; i--) minyar_list_add_take(list, (long long)(uintptr_t)make_child(depth));
        return list;
    }
    default: {
        MinyarRecord *record = named(minyar_record_new(3));
        minyar_record_set_take(record, 0, (long long)(uintptr_t)make_child(depth));
        minyar_record_set(record, 1, 11);
        minyar_record_set_take(record, 2, (long long)(uintptr_t)make_child(depth));
        return record;
    }
    }
}
static void *wide(unsigned count) {
    MinyarList *list = named(minyar_list_new());
    minyar_list_references(list);
    for (unsigned i = 0; i < count; i++) minyar_list_add_take(list, (long long)(uintptr_t)make(2));
    return list;
}

static void line(const char *operation) {
    printf("%s w%zu p%zu b%zu c%zu o%zu q%u f%zu h%llx\n", operation, rc_bounded_last_work, rc_pending_count,
           rc_backlog_count, rc_backlog_credit, rc_bounded_owner_tasks, rc_bounded_next_queue, freed_count,
           freed_hash);
}

static void call(unsigned depth) {
    unsigned locals = rnd(10);
    minyar_rc_enter(locals);
    line("enter");
    for (unsigned statements = rnd(5) + 1; statements; statements--) {
        for (unsigned operations = rnd(4); operations; operations--) {
            unsigned choice = rnd(6);
            if (choice <= 1 && locals) {
                minyar_rc_local_take((long long)rnd(locals), make(3));
                line("local");
            } else if (choice == 2) {
                minyar_rc_keep(make(3));
                line("keep");
            } else if (choice == 3) {
                minyar_rc_borrow(pool[rnd(POOL)]);
                line("borrow");
            } else if (choice == 4 && depth < 3) {
                call(depth + 1);
            } else if (rnd(3) == 0) {
                for (unsigned keeps = rnd(12); keeps; keeps--) minyar_rc_keep(make(1));
                line("keeps");
            }
        }
        if (rnd(3)) {
            minyar_rc_step();
            line("step");
        }
    }
    minyar_rc_leave();
    line("leave");
}

int main(void) {
    for (unsigned trial = 0; trial < 400; trial++) {
        random_state = 0x9e3779b9u ^ (trial * 2654435761u);
        printf("TRIAL %u\n", trial);
        for (unsigned i = 0; i < POOL; i++) pool[i] = NULL;
        for (unsigned i = 0; i < POOL; i++) pool[i] = make(2);
        line("pool");
        unsigned shape = trial % 4;
        if (shape == 1 || shape == 3) {
            minyar_rc_release(wide(rnd(300) + 20));
            line("drop");
        }
        for (unsigned calls = rnd(6) + 1; calls; calls--) {
            call(0);
            if (shape >= 2 && rnd(3) == 0) {
                minyar_rc_release(wide(rnd(80) + 1));
                line("drop");
            }
            if (rnd(4) == 0) {
                minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
                line("poll");
            }
        }
        for (unsigned i = 0; i < POOL; i++) minyar_rc_release(pool[i]);
        line("pool-release");
        size_t polls = 0;
        while (rc_pending_count) {
            minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
            assert(++polls < 10000000);
        }
        line("drained");
        assert(!rc_object_count && !rc_bytes && !rc_backlog_count && !rc_bounded_owner_tasks);
    }
    puts("direct service transcript complete");
    return 0;
}
