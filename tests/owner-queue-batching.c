/* Compare this fixture's logical transcript with the generic scheduler.
 * Queue construction deliberately avoids public service points: every owner
 * is protected before a task is published, just as after frame detachment.
 * The Python runner changes only the marked batching block in its reference. */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE 1
#endif
#define MINYAR_RC_TESTING 1
#define MINYAR_INTEGER_TEXT_CACHE_LIMIT 0
#ifndef MINYAR_RUNTIME_SOURCE
#define MINYAR_RUNTIME_SOURCE "../runtime/minyar_runtime.c"
#endif
#include MINYAR_RUNTIME_SOURCE
#include <assert.h>

static const void *identities[4096];
static size_t identity_count, observation;
static MinyarRecord *survivor;
static RcObject immortal = { RC_TEXT };
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
static MinyarRecord *cycle_root, *cycle_child;
#endif

static void *remember(void *pointer) {
    assert(pointer && identity_count < sizeof(identities) / sizeof(*identities));
    identities[identity_count++] = pointer;
    return pointer;
}
static size_t identity(const void *pointer) {
    if (!pointer) return 0;
    /* A completed task's address may be reused during a later allocation. */
    for (size_t i = identity_count; i; i--)
        if (identities[i - 1] == pointer) return i;
    assert(!"unregistered fixture identity");
    return 0;
}
static size_t object_identity(RcObject *object) {
    return identity(object ? object + 1 : NULL);
}
static void object_chain(const char *label, RcObject *head) {
    printf(" %s[", label);
    size_t limit = 0;
    for (RcObject *object = head; object;
         object = (RcObject *)(uintptr_t)(object->ownership & ~(size_t)7)) {
        assert(++limit < 4096);
        printf("%zu/%zu/%zu,", object_identity(object), (size_t)(object->ownership & 7),
               rc_bounded_saved_cursor(object));
    }
    putchar(']');
}
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
static size_t cycle_identity(RcCycle *cycle) {
    return object_identity(cycle ? rc_cycle_object(cycle) : NULL);
}
static void registry(const char *label, RcCycle *head) {
    printf(" %s[", label);
    size_t limit = 0;
    for (RcCycle *cycle = head; cycle; cycle = cycle->next) {
        assert(++limit < 4096);
        printf("%zu/%zu/%zu/%u/%u/%u/%zu,", cycle_identity(cycle),
               (size_t)(rc_cycle_object(cycle)->ownership >> 3), (size_t)cycle->incoming,
               (unsigned)cycle->marked, (unsigned)cycle->pinned,
               (unsigned)cycle->cleared, (size_t)(cycle->gray_next & 7));
    }
    putchar(']');
}
#endif
static void snapshot(const char *label, size_t requested, size_t work) {
    assert(work <= MINYAR_RC_POLL_BUDGET && work <= requested);
    assert(rc_bounded_last_work == work);
    printf("%s:%zu request=%zu work=%zu pending=%zu live=%zu bytes=%zu next=%u "
           "parity=%u active=%zu cursor=%zu tail=%zu recent-tail=%zu cache=%zu",
           label, observation++, requested, work, rc_pending_count,
           rc_object_count, rc_bytes, rc_bounded_next_queue,
           rc_bounded_recent_turn, object_identity(rc_bounded_active),
           rc_bounded_cursor, object_identity(rc_bounded_tail),
           object_identity(rc_bounded_recent_tail), rc_bounded_cached_frame_bytes);
    object_chain("old", rc_bounded_head);
    object_chain("recent", rc_bounded_recent_head);
    printf(" frames[");
    size_t limit = 0;
    for (RcFrame *frame = rc_bounded_frame_head; frame; frame = frame->previous) {
        assert(++limit < 4096);
        printf("%zu/%zu/", identity(frame), frame->local_count);
        for (size_t i = 0; i < frame->local_count; i++)
            printf("%zu,", identity(rc_bounded_pending_local_value(frame, i)));
        putchar(';');
    }
    printf("] chunks[");
    limit = 0;
    for (RcTemporaryChunk *chunk = rc_bounded_chunk_head; chunk; chunk = chunk->next) {
        assert(++limit < 4096);
        printf("%zu/%zu/", identity(chunk), chunk->count);
        for (size_t i = 0; i < chunk->count; i++)
            printf("%zu,", identity(chunk->values[i]));
        putchar(';');
    }
    printf("] free[");
    for (RcFrame *frame = rc_free_frames; frame; frame = frame->previous)
        printf("%zu/%zu,", identity(frame), frame->local_capacity);
    printf("] survivor=%zu", (size_t)(survivor ? ((RcObject *)survivor - 1)->ownership >> 3 : 0));
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
    printf(" cycle=%u/%u/%zu/%zu/%zu/%u/%u/%zu/%zu/%zu/%zu",
           rc_cycle_pending, rc_cycle_phase, rc_cycle_units, rc_cycle_epochs,
           rc_cycle_completed, rc_cycle_requested, rc_cycle_shading,
           cycle_identity(rc_cycle_active), rc_cycle_index, rc_cycle_limit,
           cycle_identity(rc_cycle_gray_head));
    registry("unknown", rc_cycle_head);
    registry("known", rc_cycle_known_head);
    if (cycle_root) {
        assert(cycle_child && cycle_root->values[0] == (long long)(uintptr_t)cycle_child);
        assert(cycle_child->values[0] == (long long)(uintptr_t)cycle_root);
        assert(cycle_root->values[1] == 73 && cycle_child->values[1] == 91);
        printf(" roots=%zu/%zu/%zu/%zu", (size_t)(((RcObject *)cycle_root - 1)->ownership >> 3),
               (size_t)(((RcObject *)cycle_child - 1)->ownership >> 3),
               (size_t)rc_cycle_metadata((RcObject *)cycle_root - 1)->incoming,
               (size_t)rc_cycle_metadata((RcObject *)cycle_child - 1)->incoming);
    }
#endif
    putchar('\n');
}
static void poll_recorded(const char *label, size_t budget) {
    size_t work = minyar_rc_poll(budget);
    snapshot(label, budget, work);
}
static void drain(const char *label) {
    size_t turns = 0;
    while (rc_pending_count) {
        assert(++turns < 100000);
        poll_recorded(label, SIZE_MAX);
    }
}
static void recover(void) {
    assert(!rc_frames && !rc_bounded_frame_head && !rc_bounded_frame_tail);
    assert(!rc_bounded_chunk_head && !rc_bounded_chunk_tail);
    assert(!rc_bounded_active && !rc_bounded_head && !rc_bounded_tail);
    assert(!rc_bounded_recent_head && !rc_bounded_recent_tail && !rc_pending_count);
    assert(!rc_object_count && !rc_bytes);
#ifdef MINYAR_BOUNDED_OWNER_CACHE
    rc_bounded_chunk_cache_clear();
#endif
    while (rc_free_frames) {
        RcFrame *frame = rc_free_frames;
        rc_free_frames = frame->previous;
        rc_heap_deallocate(frame->locals);
        rc_heap_deallocate(frame);
    }
    rc_bounded_cached_frame_bytes = 0;
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
    assert(!rc_cycle_head && !rc_cycle_known_head && !rc_cycle_pending);
    assert(!rc_cycle_active && !rc_cycle_gray_head && !rc_cycle_gray_tail);
#endif
#ifdef MINYAR_SYSTEM_HEAP
    assert(!rc_heap_allocation_count);
#else
    assert(!minyar_pool_used);
    void *whole = minyar_pool_try_allocate(MINYAR_POOL_BYTES);
    assert(whole == minyar_pool);
    minyar_pool_deallocate(whole);
    assert(!minyar_pool_used);
#endif
}

/* Every returned mortal pointer owns exactly one new task reference. */
static void *owner(unsigned kind) {
    if (kind == 0) return NULL;
    if (kind == 1) return &immortal + 1;
    if (kind == 2) { minyar_rc_retain(survivor); return survivor; }
    if (kind == 3) return remember(minyar_record_new_scalar(1));
    if (kind == 4) return remember(copy_c_text("queue owner"));
    if (kind == 5) {
        MinyarRecord *record = remember(minyar_record_new(3));
        MinyarRecord *leaf = remember(minyar_record_new_scalar(1));
        minyar_record_set_take(record, 0, (long long)(uintptr_t)leaf);
        minyar_record_set(record, 1, 123);
        return record;
    }
    if (kind == 6) {
        MinyarText *root = remember(copy_c_text("abcdefgh"));
        MinyarText *view = remember(minyar_text_slice(root, 1, 7));
        assert(view->backing == root);
        assert(rc_drop(root) == 0);
        return view;
    }
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
    assert(kind == 7 && cycle_child);
    minyar_rc_retain_traced(cycle_child);
    return cycle_child;
#else
    assert(!"unsupported owner kind");
    return NULL;
#endif
}
typedef struct {
    RcFrame *first_frame, *last_frame;
    RcTemporaryChunk *first_chunk, *last_chunk;
    size_t count;
} Tasks;
static unsigned owner_kind(unsigned flavor, unsigned index) {
    if (flavor == 0) return index % 5; /* No drop can enqueue object work. */
    if (flavor == 1) return index % 7;
    if (flavor == 2) return 6; /* Text view queues a separate root unit. */
    if (flavor == 3) return 2;
    return 7;
}
static void frame_task(Tasks *tasks, size_t count, unsigned flavor) {
    /* Populate before publication, so setup cannot accidentally poll a task. */
    void *values[32];
    assert(count <= sizeof(values) / sizeof(*values));
    for (size_t i = 0; i < count; i++) values[i] = owner(owner_kind(flavor, (unsigned)i));
    RcFrame *frame = remember(rc_heap_allocate(sizeof(*frame)));
    memset(frame, 0, sizeof(*frame));
    if (count) {
        frame->locals = rc_heap_allocate(count * (sizeof(void *) + sizeof(size_t)));
        frame->local_capacity = count;
        frame->local_count = frame->written_count = count;
        for (size_t i = 0; i < count; i++) {
            /* Tag-only values model written slots subsequently cleared. */
            frame->locals[i] = (void *)((uintptr_t)values[i] | 1);
            rc_bounded_local_indices(frame)[i] = i;
        }
    }
    if (tasks->last_frame) tasks->last_frame->previous = frame;
    else tasks->first_frame = frame;
    tasks->last_frame = frame;
    tasks->count++;
}
static void chunk_task(Tasks *tasks, size_t count, unsigned flavor) {
    void *values[RC_TEMPORARY_CHUNK_SLOTS];
    assert(count <= RC_TEMPORARY_CHUNK_SLOTS);
    for (size_t i = 0; i < count; i++) values[i] = owner(owner_kind(flavor, (unsigned)i));
    RcTemporaryChunk *chunk = remember(rc_heap_allocate(sizeof(*chunk)));
    chunk->next = NULL;
    chunk->count = count;
    for (size_t i = 0; i < count; i++) chunk->values[i] = values[i];
    if (tasks->last_chunk) tasks->last_chunk->next = chunk;
    else tasks->first_chunk = chunk;
    tasks->last_chunk = chunk;
    tasks->count++;
}
static Tasks tasks_for(unsigned shape, unsigned flavor) {
    Tasks tasks = {0};
    if (shape != 1) {
        frame_task(&tasks, 13, flavor);
        frame_task(&tasks, 0, flavor);
        frame_task(&tasks, 9, flavor);
    }
    if (shape != 0) {
        chunk_task(&tasks, 8, flavor);
        chunk_task(&tasks, 0, flavor);
        chunk_task(&tasks, 3, flavor);
        chunk_task(&tasks, 8, flavor);
    }
    return tasks;
}
static void publish(Tasks tasks) {
    assert(!rc_bounded_frame_head && !rc_bounded_chunk_head);
    rc_bounded_frame_head = tasks.first_frame;
    rc_bounded_frame_tail = tasks.last_frame;
    rc_bounded_chunk_head = tasks.first_chunk;
    rc_bounded_chunk_tail = tasks.last_chunk;
    rc_pending_count += tasks.count;
}
static void run_polls(const char *label, unsigned seed) {
    /* First positive budgets vary, including boundaries within a batch. */
    static const size_t budgets[] = {2, 7, 1, 3, 8, 9, 31, 32, 33, 1024, SIZE_MAX};
    poll_recorded(label, 0);
    for (size_t i = 0; i < sizeof(budgets) / sizeof(*budgets); i++)
        poll_recorded(label, budgets[(i + seed) % (sizeof(budgets) / sizeof(*budgets))]);
    unsigned random = seed + 1;
    for (unsigned i = 0; i < 13; i++) {
        random = random * 1664525u + 1013904223u;
        poll_recorded(label, (random >> 8) % 19);
    }
    drain(label);
    poll_recorded(label, 0);
    poll_recorded(label, SIZE_MAX);
    assert(((RcObject *)survivor - 1)->ownership == (8 | RC_SCALAR_RECORD));
}
static void begin_case(void) {
    recover();
    identity_count = observation = 0;
    remember(&immortal + 1);
    survivor = remember(minyar_record_new_scalar(1));
    minyar_record_set(survivor, 0, 57);
}
static void finish_case(const char *label) {
    assert(survivor->values[0] == 57);
    rc_drop(survivor);
    survivor = NULL;
    drain(label);
    recover();
    puts("recovered all managed objects, tasks, caches and backing allocations");
}
static void ordinary_cases(void) {
    for (unsigned turn = 0; turn < 3; turn++) {
        for (unsigned scenario = 0; scenario < 12; scenario++) {
            begin_case();
            unsigned shape = scenario % 3, flavor = scenario / 3;
            Tasks tasks = tasks_for(shape, flavor);
            void *extra = scenario == 5 ? owner(5) : NULL;
            publish(tasks);
            if (extra) rc_drop(extra);
            rc_bounded_next_queue = turn;
            rc_bounded_recent_turn = scenario & 1;
            char label[80];
            snprintf(label, sizeof(label), "ordinary-%u-turn-%u", scenario, turn);
            run_polls(label, scenario);
            finish_case(label);
        }
    }
}
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
static void make_cycle(void) {
    cycle_root = remember(minyar_record_new_traced(2));
    cycle_child = remember(minyar_record_new_traced(2));
    minyar_record_set_traced(cycle_root, 1, 73);
    minyar_record_set_traced(cycle_child, 1, 91);
    minyar_record_set_reference_traced(cycle_root, 0, (long long)(uintptr_t)cycle_child);
    minyar_record_set_reference_traced(cycle_child, 0, (long long)(uintptr_t)cycle_root);
    rc_drop(cycle_child); /* Only root has an independent lasting C owner. */
    drain("cycle-setup");
    assert(rc_cycle_phase == RC_CYCLE_IDLE);
}
static void cycle_cases(void) {
    for (unsigned phase = RC_CYCLE_IDLE; phase <= RC_CYCLE_SWEEP; phase++) {
        for (unsigned turn = 0; turn < 4; turn++) {
            for (unsigned shape = 0; shape < 3; shape++) {
                begin_case();
                make_cycle();
                Tasks tasks = tasks_for(shape, 4);
                if (phase != RC_CYCLE_IDLE) {
                    rc_cycle_request();
                    size_t turns = 0;
                    while (rc_cycle_phase != phase) {
                        assert(++turns < 100000);
                        poll_recorded("force-phase", 1);
                    }
                    assert(rc_cycle_pending);
                }
                publish(tasks);
                rc_bounded_next_queue = turn;
                rc_bounded_recent_turn = turn & 1;
                char label[80];
                snprintf(label, sizeof(label), "cycle-phase-%u-shape-%u-turn-%u", phase, shape, turn);
                run_polls(label, phase + shape);
                assert(((RcObject *)cycle_child - 1)->ownership >> 3 ==
                       rc_cycle_metadata((RcObject *)cycle_child - 1)->incoming);
                MinyarRecord *root = cycle_root;
                cycle_root = cycle_child = NULL;
                rc_drop(root);
                drain("cycle-unrooted");
                finish_case(label);
            }
        }
    }
}
#endif
int main(void) {
    ordinary_cases();
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
    cycle_cases();
    /* The activation bit remains set after every traced graph is reclaimed.
     * Repeat nonleaf/Text-view arrivals in the optimized four-queue runtime. */
    assert(rc_cycle_present == 1);
    ordinary_cases();

    /* Independent first-competitor oracle: source0 is a frame, source1 a
     * chunk. Vary the arrival's owner index and its kind. A nonleaf's next
     * unit visits field0; a Text view's root needs a separate finalization.
     * Neither permits the next owner visit before that object unit. */
    for (unsigned source = 0; source < 2; source++) {
        for (unsigned kind = 5; kind <= 6; kind++) {
            for (unsigned position = 0; position < 3; position++) {
                begin_case();
                assert(rc_cycle_present == 1 && !rc_cycle_pending);
                Tasks tasks = {0};
                if (source == 0) frame_task(&tasks, 3, 0);
                else chunk_task(&tasks, 3, 0);
                size_t slot = 2 - position;
                void *previous = source == 0 ?
                    rc_bounded_local_value(tasks.first_frame, slot) :
                    tasks.first_chunk->values[slot];
                rc_drop(previous);
                void *incoming = owner(kind);
                RcObject *target = kind == 5 ? (RcObject *)incoming - 1 :
                    (RcObject *)((MinyarText *)incoming)->backing - 1;
                if (source == 0)
                    tasks.first_frame->locals[slot] = (void *)((uintptr_t)incoming | 1);
                else tasks.first_chunk->values[slot] = incoming;
                assert(!rc_pending_count);
                publish(tasks);
                rc_bounded_next_queue = source == 0 ? 1 : 2;
                char label[96];
                snprintf(label, sizeof(label), "activated-source-%u-kind-%u-position-%u",
                         source, kind, position);
                for (unsigned index = 0; index < position; index++) {
                    poll_recorded(label, 1);
                    assert(!rc_bounded_active && !rc_bounded_head && !rc_bounded_recent_head);
                }
                size_t work = minyar_rc_poll(2);
                snapshot(label, 2, work);
                assert(work == (MINYAR_RC_POLL_BUDGET == 1 ? 1u : 2u));
                /* A distinct owner remains untouched even with budget left. */
                assert((source == 0 ? tasks.first_frame->local_count :
                        tasks.first_chunk->count) == 2 - position);
                if (work == 1) {
                    assert(rc_bounded_recent_head == target && rc_pending_count == 2);
                } else if (kind == 5) {
                    assert(rc_bounded_active == target && rc_bounded_cursor == 1);
                    assert(rc_pending_count == 2);
                } else {
                    assert(!rc_bounded_active && !rc_bounded_head && !rc_bounded_recent_head);
                    assert(rc_pending_count == 1);
                }
                drain(label);
                finish_case(label);
            }
        }
    }
#endif
    recover();
    puts("owner queue scheduler transcript complete");
    return 0;
}
