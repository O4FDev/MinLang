/* Single-threaded snapshot cycle collector. See research/cycles/README.md.
 * RC remains authoritative: incoming counts describe aggregate slots only;
 * count - incoming includes locals, temporaries, C owners and retired frames.
 * Metadata precedes the ordinary eight-byte header of Lists/mixed records.
 * No tracing queue, barrier, or registry operation allocates or scans. */
typedef struct RcCycle {
    struct RcCycle *previous, *next, *gray_previous, *gray_next;
    size_t incoming;
    unsigned generation : 1, marked : 2, registered : 1, pinned : 1, cleared : 1;
} RcCycle;
enum { RC_CYCLE_IDLE, RC_CYCLE_ROOTS, RC_CYCLE_MARK, RC_CYCLE_SWEEP };
static RcCycle *rc_cycle_head, *rc_cycle_cohort, *rc_cycle_cursor;
static RcCycle *rc_cycle_gray_head, *rc_cycle_gray_tail, *rc_cycle_active;
static size_t rc_cycle_index, rc_cycle_limit;
static unsigned rc_cycle_generation, rc_cycle_phase, rc_cycle_requested;
static unsigned rc_cycle_pending, rc_cycle_inside;
/* Raw native clients conservatively trace. Generated main opts into complete
 * compiler mutation hints, before constructing any graph. */
static unsigned rc_cycle_enabled = 1;
void minyar_rc_cycle_policy(void) {
    if (!rc_cycle_head && !rc_cycle_pending) rc_cycle_enabled = 0;
}
void minyar_rc_enable_cycles(void) { rc_cycle_enabled = 1; }
#ifdef MINYAR_RC_TESTING
static size_t rc_cycle_units, rc_cycle_epochs;
#endif
static void rc_cycle_unit(void);
#ifndef MINYAR_BOUNDED_RC
static void rc_cycle_eager_service(size_t budget);
#endif
static int rc_cycle_storage(unsigned kind) {
    return kind == RC_LIST || kind == RC_REFERENCES ||
           kind == RC_REFERENCES_IMMORTAL || kind == RC_RECORD;
}
static RcCycle *rc_cycle_metadata(RcObject *object) {
    return (RcCycle *)object - 1;
}
static RcObject *rc_cycle_object(RcCycle *cycle) {
    return (RcObject *)(cycle + 1);
}
static RcCycle *rc_cycle_value(void *value) {
    if (!value) return NULL;
    RcObject *object = (RcObject *)value - 1;
    unsigned kind = object->ownership & 7;
    if (kind != RC_RECORD && kind != RC_REFERENCES && kind != RC_REFERENCES_IMMORTAL)
        return NULL;
    return rc_cycle_metadata(object);
}
static void rc_cycle_register(RcObject *object) {
    RcCycle *cycle = rc_cycle_metadata(object);
    if (cycle->registered) return;
    cycle->registered = 1;
    cycle->generation = rc_cycle_generation;
    cycle->next = rc_cycle_head;
    if (rc_cycle_head) rc_cycle_head->previous = cycle;
    rc_cycle_head = cycle;
}
static void rc_cycle_request(void) {
    if (rc_cycle_inside || !rc_cycle_enabled) return;
    rc_cycle_requested = 1;
    if (!rc_cycle_pending) {
        rc_cycle_pending = 1;
#ifdef MINYAR_BOUNDED_RC
        rc_pending_count++;
#endif
    }
}
static void rc_cycle_gray_remove(RcCycle *cycle) {
    if (cycle->gray_previous) cycle->gray_previous->gray_next = cycle->gray_next;
    else if (rc_cycle_gray_head == cycle) rc_cycle_gray_head = cycle->gray_next;
    if (cycle->gray_next) cycle->gray_next->gray_previous = cycle->gray_previous;
    else if (rc_cycle_gray_tail == cycle) rc_cycle_gray_tail = cycle->gray_previous;
    cycle->gray_previous = cycle->gray_next = NULL;
}
static void rc_cycle_unregister(RcObject *object) {
    RcCycle *cycle = rc_cycle_metadata(object);
    if (!cycle->registered) return;
    cycle->registered = 0;
    if (rc_cycle_cohort == cycle) rc_cycle_cohort = cycle->next;
    if (rc_cycle_cursor == cycle) rc_cycle_cursor = cycle->next;
    if (rc_cycle_active == cycle) rc_cycle_active = NULL;
    rc_cycle_gray_remove(cycle);
    if (cycle->previous) cycle->previous->next = cycle->next;
    else rc_cycle_head = cycle->next;
    if (cycle->next) cycle->next->previous = cycle->previous;
}
static void rc_cycle_shade(RcCycle *cycle) {
    if (!cycle || !cycle->registered || (rc_cycle_phase != RC_CYCLE_ROOTS && rc_cycle_phase != RC_CYCLE_MARK) ||
        cycle->generation == rc_cycle_generation || cycle->marked) return;
    cycle->marked = 1;
    cycle->gray_previous = rc_cycle_gray_tail;
    cycle->gray_next = NULL;
    if (rc_cycle_gray_tail) rc_cycle_gray_tail->gray_next = cycle;
    else rc_cycle_gray_head = cycle;
    rc_cycle_gray_tail = cycle;
}
/* A count decrement may remove a root. A take-store removes an external
 * owner without decrementing its total count. Both must preserve the snapshot. */
static void rc_cycle_before_drop(RcObject *object) {
    unsigned kind = object->ownership & 7;
    if (kind == RC_RECORD || kind == RC_REFERENCES || kind == RC_REFERENCES_IMMORTAL)
        rc_cycle_shade(rc_cycle_metadata(object));
}
/* A gray object still carries snapshot edges. If its real count reaches zero,
 * keep one collector pin until its bounded scan finishes. Dropping it from the
 * gray queue now would silently discard an arbitrary number of snapshot edges. */
static int rc_cycle_defer_zero(RcObject *object) {
    RcCycle *cycle = rc_cycle_value(object + 1);
    if (!cycle || !cycle->registered || cycle->marked != 1 ||
        (rc_cycle_phase != RC_CYCLE_ROOTS && rc_cycle_phase != RC_CYCLE_MARK)) return 0;
    cycle->pinned = 1;
    object->ownership += 8;
    return 1;
}
static void rc_cycle_after_drop(RcObject *object) {
    unsigned kind = object->ownership & 7;
    if (kind == RC_RECORD || kind == RC_REFERENCES || kind == RC_REFERENCES_IMMORTAL) {
        RcCycle *cycle = rc_cycle_metadata(object);
        if (cycle->registered && (object->ownership >> 3) == cycle->incoming) rc_cycle_request();
    }
}
static void rc_cycle_edge_add(void *owner, void *value) {
    RcCycle *cycle = rc_cycle_value(value);
    if (!cycle) return;
    rc_cycle_register((RcObject *)owner - 1);
    rc_cycle_shade(cycle);
    cycle->incoming++;
    RcObject *parent = (RcObject *)owner - 1;
    if (cycle->registered && (rc_cycle_object(cycle)->ownership >> 3) == cycle->incoming &&
        (parent->ownership >> 3) == rc_cycle_metadata(parent)->incoming) rc_cycle_request();
}
static void rc_cycle_edge_remove(void *value) {
    RcCycle *cycle = rc_cycle_value(value);
    if (!cycle) return;
    rc_cycle_shade(cycle);
    cycle->incoming--;
}
static void rc_cycle_free_object(RcObject *object, unsigned kind) {
    if (rc_cycle_storage(kind)) {
        RC_ACCOUNT(rc_bytes -= sizeof(RcCycle));
        RC_DEALLOCATE(rc_cycle_metadata(object));
    } else RC_DEALLOCATE(object);
}
