/* Adapted from port/astra-cycles-v2 at 976a75a8c51518006cb654d6e6304f425e2eab91.
 * Selected only by the separate cycle runtime; ordinary runtime files retain
 * their original implementation. See docs/managed-graphs.md. */
/* Single-threaded snapshot cycle collector. See research/cycles/README.md.
 * RC remains authoritative: incoming counts describe traced aggregate slots
 * only; count - incoming includes locals, temporaries, C owners, retired
 * frames and slots of untraced aggregates.
 * Only RC_TRACED objects carry metadata, before their eight-byte header. The
 * compiler allocates them for List and record types that can reach
 * themselves; every other object keeps the untraced layout and no barrier
 * touches it. An untraced aggregate cannot lie on a cycle, so treating its
 * slots as external owners is complete as well as safe.
 * No tracing queue, barrier, or registry operation allocates or scans. */
/* The gray queue is singly linked: only its head is ever removed. A gray
 * object cannot be unregistered, because a zero count during roots/mark pins
 * it (rc_cycle_defer_zero) and the queue is empty outside those phases.
 * incoming counts owning aggregate slots, so it never exceeds the number of
 * eight-byte slots that fit in the address space; 58 bits cover 2^61 bytes. */
typedef struct RcCycle {
    struct RcCycle *previous, *next;
    uintptr_t gray_next; /* Aligned link, with bits0/1 holding proof validity/generation. */
    size_t generation : 1, marked : 2, registered : 1, pinned : 1, cleared : 1, record : 1,
        incoming : 57;
} RcCycle;
_Static_assert(sizeof(RcCycle) == 32, "cycle metadata must stay four words");
_Static_assert(_Alignof(RcCycle) >= 8, "cycle links require eight-byte alignment");
enum { RC_CYCLE_IDLE, RC_CYCLE_ROOTS, RC_CYCLE_MARK, RC_CYCLE_SWEEP };
static RcCycle *rc_cycle_head, *rc_cycle_cohort, *rc_cycle_cursor;
static RcCycle *rc_cycle_gray_head, *rc_cycle_gray_tail, *rc_cycle_active;
static size_t rc_cycle_index, rc_cycle_limit;
static unsigned rc_cycle_generation, rc_cycle_phase, rc_cycle_requested;
static unsigned rc_cycle_pending, rc_cycle_inside;
/* A proof certifies only nodes reached from this still-external anchor.
 * Any owning traced-edge change invalidates it before the store. A failed
 * temporary anchor advances selection through the finite registry. */
static RcCycle *rc_cycle_proof_anchor, *rc_cycle_proof_retry;
static unsigned rc_cycle_proof_valid, rc_cycle_proof_build, rc_cycle_proof_generation;
static unsigned rc_cycle_proof_preserve, rc_cycle_proof_after_retry, rc_cycle_rescan;

/* Completed finite cohorts let reactors distinguish old snapshot work
 * from requests created by their own transient borrowed owners. */
static size_t rc_cycle_completed;
/* Nonzero exactly in the roots and mark phases, when barriers shade. Hot
 * ownership paths test this one global before touching any object metadata. */
static unsigned rc_cycle_shading;
/* Set by the first RC_TRACED allocation; until then no cycle job can exist. */
static unsigned rc_cycle_present;
/* Raw native clients conservatively trace. Generated main opts into complete
 * compiler mutation hints, before constructing any graph. */
static unsigned rc_cycle_enabled = 1;
void minyar_rc_cycle_policy(void) {
    if (!rc_cycle_head && !rc_cycle_pending)
        rc_cycle_enabled = 0;
}
void minyar_rc_enable_cycles(void) {
    rc_cycle_enabled = 1;
#ifdef MINYAR_BOUNDED_RC
    /* A potentially cyclic source mutation is also a service point. It runs
     * before the store, while the compiler's receiver/argument owners protect
     * both values, and services exactly one ordinary bounded batch. */
    rc_service_pending(MINYAR_RC_POLL_BUDGET);
#endif
}
#ifdef MINYAR_RC_TESTING
static size_t rc_cycle_units, rc_cycle_epochs, rc_cycle_cached_requests;
#endif
static MINYAR_NOINLINE void rc_cycle_unit(void);
#ifndef MINYAR_BOUNDED_RC
static void rc_cycle_eager_service(size_t budget);
#endif
static inline RcCycle *rc_cycle_metadata(RcObject *object) {
    return (RcCycle *)object - 1;
}
/* The layout kind of any object: a traced List behaves as RC_REFERENCES and a
 * traced record as RC_RECORD. Dead bounded objects keep their low kind bits. */
static inline unsigned rc_kind(RcObject *object) {
    unsigned kind = object->ownership & 7;
    if (kind != RC_TRACED)
        return kind;
    return rc_cycle_metadata(object)->record ? RC_RECORD : RC_REFERENCES;
}
static inline int rc_traced(RcObject *object) {
    return (object->ownership & 7) == RC_TRACED;
}
static RcObject *rc_cycle_object(RcCycle *cycle) {
    return (RcObject *)(cycle + 1);
}
static inline RcCycle *rc_cycle_value(void *value) {
    if (!value || !rc_traced((RcObject *)value - 1))
        return NULL;
    return rc_cycle_metadata((RcObject *)value - 1);
}
static void rc_cycle_register(RcCycle *cycle) {
    if ((uintptr_t)cycle & 7)
        minyar_stop("cycle metadata is not eight-byte aligned.");
    cycle->gray_next = 0;
    cycle->registered = 1;
    cycle->generation = rc_cycle_generation;
    cycle->next = rc_cycle_head;
    if (rc_cycle_head)
        rc_cycle_head->previous = cycle;
    rc_cycle_head = cycle;
}
static inline void rc_cycle_proof_invalidate(void) {
    if (rc_cycle_inside)
        return;
    rc_cycle_proof_valid = rc_cycle_proof_build = 0;
    if (rc_cycle_pending)
        rc_cycle_rescan = 1;
}
static inline int rc_cycle_anchor_held(void) {
    /* Unregister clears the pointer before either allocator can recycle it. */
    return rc_cycle_proof_anchor && (rc_cycle_object(rc_cycle_proof_anchor)->ownership >> 3) >
                                        rc_cycle_proof_anchor->incoming;
}
static inline int rc_cycle_proven(RcCycle *cycle) {
    if (!(cycle->gray_next & 1))
        return 0;
    unsigned generation = (unsigned)((cycle->gray_next >> 1) & 1);
    return (rc_cycle_proof_valid && generation == rc_cycle_proof_generation) ||
           (rc_cycle_proof_build && generation == rc_cycle_generation);
}
static MINYAR_COLD void rc_cycle_request_kind(unsigned rescan) {
    if (rc_cycle_inside)
        return;
    rc_cycle_rescan |= rescan;
    rc_cycle_requested = 1;
    if (!rc_cycle_pending) {
        rc_cycle_pending = 1;
#ifdef MINYAR_BOUNDED_RC
        rc_pending_count++;
#endif
    }
}
static MINYAR_COLD void rc_cycle_request(void) {
    rc_cycle_request_kind(1);
}
static RcCycle *rc_cycle_gray_pop(void) {
    RcCycle *cycle = rc_cycle_gray_head;
    rc_cycle_gray_head = (RcCycle *)(cycle->gray_next & ~(uintptr_t)3);
    if (!rc_cycle_gray_head)
        rc_cycle_gray_tail = NULL;
    cycle->gray_next &= 3;
    return cycle;
}
static void rc_cycle_unlink(RcCycle *cycle) {
    cycle->registered = 0;
    /* Collector cursors are all null between epochs. */
    if (rc_cycle_phase != RC_CYCLE_IDLE) {
        if (rc_cycle_cohort == cycle)
            rc_cycle_cohort = cycle->next;
        if (rc_cycle_cursor == cycle)
            rc_cycle_cursor = cycle->next;
        if (rc_cycle_active == cycle)
            rc_cycle_active = NULL;
    }
    if (cycle->previous)
        cycle->previous->next = cycle->next;
    else
        rc_cycle_head = cycle->next;
    if (cycle->next)
        cycle->next->previous = cycle->previous;
}
static inline void rc_cycle_unregister(RcObject *object) {
    RcCycle *cycle = rc_cycle_metadata(object);
    if (rc_cycle_proof_anchor == cycle) {
        rc_cycle_proof_valid = rc_cycle_proof_build = 0;
        rc_cycle_proof_anchor = NULL;
        if (rc_cycle_pending)
            rc_cycle_rescan = 1;
    }
    if (rc_cycle_proof_retry == cycle)
        rc_cycle_proof_retry = NULL;
    if (cycle->registered)
        rc_cycle_unlink(cycle);
    cycle->gray_next = 0;
}
static MINYAR_COLD void rc_cycle_shade_slow(RcCycle *cycle) {
    if (!cycle || !cycle->registered || cycle->generation == rc_cycle_generation || cycle->marked)
        return;
    cycle->marked = 1;
    cycle->gray_next &= 3;
    if (rc_cycle_gray_tail)
        rc_cycle_gray_tail->gray_next = (uintptr_t)cycle | (rc_cycle_gray_tail->gray_next & 3);
    else
        rc_cycle_gray_head = cycle;
    rc_cycle_gray_tail = cycle;
}
/* Root-witness propagation is distinct from conservative snapshot shading.
 * A node already scanned from a temporary is queued once more when first
 * reached from the anchor. Each scan still visits only one field per unit. */
static void rc_cycle_shade_proven(RcCycle *cycle) {
    if (!cycle || !cycle->registered || cycle->generation == rc_cycle_generation)
        return;
    if (!(cycle->gray_next & 1) || ((cycle->gray_next >> 1) & 1) != rc_cycle_generation) {
        cycle->gray_next =
            (cycle->gray_next & ~(uintptr_t)3) | 1 | ((uintptr_t)rc_cycle_generation << 1);
        if (cycle->marked == 2)
            cycle->marked = 0;
    }
    rc_cycle_shade_slow(cycle);
}
static inline void rc_cycle_shade(RcCycle *cycle) {
    if (rc_cycle_shading)
        rc_cycle_shade_slow(cycle);
}
/* Hot ownership paths only test a global flag inline; keeping their bodies
 * small lets link-time optimization still inline them into generated code. */
static MINYAR_COLD void rc_cycle_shade_value(void *value) {
    rc_cycle_shade_slow(rc_cycle_value(value));
}
/* A count decrement may remove a root. A take-store removes an external
 * owner without decrementing its total count. Both must preserve the snapshot. */
static inline void rc_cycle_before_drop(RcObject *object) {
    if (rc_cycle_shading)
        rc_cycle_shade_value(object + 1);
}
/* A gray object still carries snapshot edges. If its real count reaches zero,
 * keep one collector pin until its bounded scan finishes. Dropping it from the
 * gray queue now would silently discard an arbitrary number of snapshot edges. */
static MINYAR_COLD int rc_cycle_pin_gray(RcObject *object) {
    RcCycle *cycle = rc_cycle_value(object + 1);
    if (!cycle || !cycle->registered || cycle->marked != 1)
        return 0;
    cycle->pinned = 1;
    object->ownership += 8;
    return 1;
}
static inline int rc_cycle_defer_zero(RcObject *object) {
    return rc_cycle_shading && rc_cycle_pin_gray(object);
}
static MINYAR_COLD void rc_cycle_check_external(RcObject *object) {
    RcCycle *cycle = rc_cycle_value(object + 1);
    if (!cycle || !cycle->registered || (object->ownership >> 3) != cycle->incoming)
        return;
    if (cycle == rc_cycle_proof_anchor) {
        rc_cycle_proof_retry = cycle;
        rc_cycle_proof_invalidate();
    }
    /* Do not discard the last temporary's request. Its queued unit validates
     * an unchanged owning path to an independently held root, or rescans. */
    unsigned proven = rc_cycle_proven(cycle) && rc_cycle_anchor_held();
    rc_cycle_request_kind(!proven);
}
/* While tracing is dormant no cycle can exist, so no request is needed. */
static inline void rc_cycle_after_drop(RcObject *object) {
    if (rc_cycle_enabled)
        rc_cycle_check_external(object);
}
static MINYAR_NOINLINE void rc_cycle_add_incoming(RcObject *parent, RcCycle *cycle,
                                                unsigned additive) {
    RcCycle *source = rc_cycle_metadata(parent);
    if (!source->registered)
        rc_cycle_register(source);
    /* A committed proof certifies existing paths, not all registry objects.
     * Insertion removes no such path, even while a fresh owner is constructed.
     * Unknown registered children retain conservative invalidation: they may
     * contain cycles or require a new cohort. Never infer new descendants. */
    unsigned preserve = additive && rc_cycle_phase == RC_CYCLE_IDLE &&
                        rc_cycle_proof_valid && !rc_cycle_proof_build &&
                        rc_cycle_anchor_held() && !rc_cycle_proof_anchor->pinned &&
                        (!cycle->registered || rc_cycle_proven(cycle));
    if (!preserve)
        rc_cycle_proof_invalidate();
    rc_cycle_shade(cycle);
    cycle->incoming++;
    /* A take-store can consume the anchor's sole external owner without an
     * RC decrement. Recheck AFTER incoming changes, before store/poll/reuse. */
    if (preserve && !rc_cycle_anchor_held())
        rc_cycle_proof_invalidate();
    if (rc_cycle_enabled && cycle->registered &&
        (rc_cycle_object(cycle)->ownership >> 3) == cycle->incoming &&
        (parent->ownership >> 3) == source->incoming)
        rc_cycle_request();
}
static inline void rc_cycle_edge_add(void *owner, void *value) {
    RcCycle *cycle = rc_cycle_value(value);
    if (cycle)
        rc_cycle_add_incoming((RcObject *)owner - 1, cycle, 0);
}
/* Append or initial field insertion only. Replacements use edge_add above. */
static inline void rc_cycle_edge_insert(void *owner, void *value) {
    RcCycle *cycle = rc_cycle_value(value);
    if (cycle)
        rc_cycle_add_incoming((RcObject *)owner - 1, cycle, 1);
}
static inline void rc_cycle_edge_remove(void *value) {
    RcCycle *cycle = rc_cycle_value(value);
    if (!cycle)
        return;
    rc_cycle_proof_invalidate();
    rc_cycle_shade(cycle);
    cycle->incoming--;
}
#ifndef MINYAR_BOUNDED_RC
/* Eager profile helpers; the bounded profile has separate traced paths. */
static void rc_cycle_free_object(RcObject *object) {
    if (rc_traced(object)) {
        RC_ACCOUNT(rc_bytes -= sizeof(RcCycle));
        RC_DEALLOCATE(rc_cycle_metadata(object));
    } else
        RC_DEALLOCATE(object);
}
/* Remove a dead parent's slot. Only traced parents counted it as incoming. */
static inline void rc_cycle_drop_slot(int traced, void *value) {
    if (traced)
        rc_cycle_edge_remove(value);
}
#endif
