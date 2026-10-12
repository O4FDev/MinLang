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
    /* Registry links are unused after irreversible zero-count unlink. Only
     * issued full-MARK dead owners reuse them for exact job/anchor identity. */
    union { struct RcCycle *previous; size_t retired_completed; };
    union { struct RcCycle *next; uintptr_t retired_anchor_token; };
    uintptr_t gray_next; /* Registered: aligned link, bits0/1 proof tags, bit2 local namespace.
                          * Unregistered: bit2 retains captured incoming-path exposure; bit3
                          * marks private bounded zero-count cleanup; bit4 distinguishes captured
                          * dead owners; bit5 distinguishes fresh local-MARK retirement. None is a
                          * live certificate. Bit6 distinguishes scanned full-MARK retirement. */
    size_t generation : 1, marked : 2, registered : 1, pinned : 1, cleared : 1, record : 1,
        incoming : 57;
} RcCycle;
_Static_assert(sizeof(RcCycle) == 32, "cycle metadata must stay four words");
_Static_assert(_Alignof(RcCycle) >= 8, "cycle links require eight-byte alignment");
enum { RC_CYCLE_IDLE, RC_CYCLE_ROOTS, RC_CYCLE_MARK, RC_CYCLE_SWEEP };
#define MINYAR_CYCLE_LOCAL_PROOFS 1
/* The unknown prefix is scanned; completed certificates wait on a separate
 * list. Cancellation joins both lists in constant time, before any reuse. */
static RcCycle *rc_cycle_head, *rc_cycle_tail, *rc_cycle_known_head, *rc_cycle_known_tail;
static RcCycle *rc_cycle_cohort, *rc_cycle_cursor, *rc_cycle_last;
static unsigned rc_cycle_local_job, rc_cycle_local_requested, rc_cycle_local_generation;
/* An unchanged unknown cohort may also have one temporary external witness.
 * Its tags use the opposite certificate bit, never the completed anchor's
 * namespace. Every registry/owning-edge change cancels this temporary proof. */
static RcCycle *rc_cycle_temporary_anchor;
static unsigned rc_cycle_temporary_valid, rc_cycle_temporary_build, rc_cycle_temporary_covered;

static RcCycle *rc_cycle_gray_head, *rc_cycle_gray_tail, *rc_cycle_active;
static size_t rc_cycle_index, rc_cycle_limit;
static unsigned rc_cycle_generation, rc_cycle_phase, rc_cycle_requested;
static unsigned rc_cycle_pending, rc_cycle_inside;
static inline void rc_cycle_temporary_changed(void) {
    if (!rc_cycle_inside)
        rc_cycle_temporary_valid = rc_cycle_temporary_build = 0;
}
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
    if (!rc_cycle_head && !rc_cycle_known_head && !rc_cycle_pending)
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
    rc_cycle_temporary_changed();
    if ((uintptr_t)cycle & 7)
        minyar_stop("cycle metadata is not eight-byte aligned.");
    cycle->gray_next = 0;
    cycle->registered = 1;
    /* Fresh registry nodes stay outside completed cohorts until ROOTS or
     * real snapshot shading exposes them. Value 3 is never a gray mark. */
    cycle->marked = 3;
    unsigned local = rc_cycle_local_job || (rc_cycle_proof_valid && !rc_cycle_proof_build);
    cycle->gray_next = local ? 4 : 0;
    cycle->generation = local ? rc_cycle_local_generation : rc_cycle_generation;
    cycle->previous = NULL;
    cycle->next = rc_cycle_head;
    if (!rc_cycle_head)
        rc_cycle_tail = cycle;
    if (rc_cycle_head)
        rc_cycle_head->previous = cycle;
    rc_cycle_head = cycle;
}
static void rc_cycle_join_known(void) {
    if (!rc_cycle_known_head)
        return;
    if (rc_cycle_tail) {
        rc_cycle_tail->next = rc_cycle_known_head;
        rc_cycle_known_head->previous = rc_cycle_tail;
    } else
        rc_cycle_head = rc_cycle_known_head;
    rc_cycle_tail = rc_cycle_known_tail;
    rc_cycle_known_head = rc_cycle_known_tail = NULL;
}
static inline void rc_cycle_proof_invalidate(void) {
    if (rc_cycle_inside)
        return;
    rc_cycle_proof_valid = rc_cycle_proof_build = 0;
    rc_cycle_temporary_changed();
    rc_cycle_join_known();
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
           (rc_cycle_proof_build && !(cycle->gray_next & 4) &&
            generation == rc_cycle_generation);
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
static inline int rc_cycle_temporary_held(void) {
    return rc_cycle_temporary_anchor &&
           (rc_cycle_object(rc_cycle_temporary_anchor)->ownership >> 3) >
               rc_cycle_temporary_anchor->incoming && !rc_cycle_temporary_anchor->pinned;
}
static inline int rc_cycle_temporary_proven(RcCycle *cycle) {
    return (cycle->gray_next & 1) &&
           ((cycle->gray_next >> 1) & 1) != rc_cycle_proof_generation;
}
static void rc_cycle_request_local(void) {
    if (rc_cycle_inside)
        return;
    if (!(rc_cycle_temporary_valid && rc_cycle_temporary_held() &&
          rc_cycle_proof_valid && rc_cycle_anchor_held()))
        rc_cycle_local_requested = 1;
    rc_cycle_request_kind(0);
}
static RcCycle *rc_cycle_cohort_next(RcCycle *cycle) {
    return cycle == rc_cycle_last ? NULL : cycle->next;
}
static RcCycle *rc_cycle_gray_pop(void) {
    RcCycle *cycle = rc_cycle_gray_head;
    rc_cycle_gray_head = (RcCycle *)(cycle->gray_next & ~(uintptr_t)7);
    if (!rc_cycle_gray_head)
        rc_cycle_gray_tail = NULL;
    cycle->gray_next &= 7;
    return cycle;
}
static void rc_cycle_unlink(RcCycle *cycle) {
    cycle->registered = 0;
    if (rc_cycle_phase != RC_CYCLE_IDLE) {
        RcCycle *next = rc_cycle_cohort_next(cycle);
        if (rc_cycle_last == cycle)
            rc_cycle_last = cycle == rc_cycle_cohort ? NULL : cycle->previous;
        if (rc_cycle_cohort == cycle)
            rc_cycle_cohort = next;
        if (rc_cycle_cursor == cycle)
            rc_cycle_cursor = next;
        if (rc_cycle_active == cycle)
            rc_cycle_active = NULL;
    }
    if (cycle->previous)
        cycle->previous->next = cycle->next;
    else if (rc_cycle_known_head == cycle)
        rc_cycle_known_head = cycle->next;
    else
        rc_cycle_head = cycle->next;
    if (cycle->next)
        cycle->next->previous = cycle->previous;
    if (rc_cycle_tail == cycle)
        rc_cycle_tail = cycle->previous;
    if (rc_cycle_known_tail == cycle)
        rc_cycle_known_tail = cycle->previous;
}
static void rc_cycle_promote(RcCycle *cycle) {
    rc_cycle_unlink(cycle);
    cycle->registered = 1;
    cycle->previous = rc_cycle_known_tail;
    cycle->next = NULL;
    if (rc_cycle_known_tail)
        rc_cycle_known_tail->next = cycle;
    else
        rc_cycle_known_head = cycle;
    rc_cycle_known_tail = cycle;
    cycle->gray_next &= ~(uintptr_t)4;
    cycle->generation = rc_cycle_generation;
}
static inline void rc_cycle_unregister(RcObject *object) {
    RcCycle *cycle = rc_cycle_metadata(object);
    rc_cycle_temporary_changed();
    if (cycle->registered)
        rc_cycle_proof_invalidate();
    if (rc_cycle_temporary_anchor == cycle) {
        rc_cycle_temporary_valid = rc_cycle_temporary_build = 0;
        rc_cycle_temporary_anchor = NULL;
    }
    if (rc_cycle_proof_anchor == cycle) {
        rc_cycle_proof_valid = rc_cycle_proof_build = 0;
        rc_cycle_proof_anchor = NULL;
        rc_cycle_join_known();
        if (rc_cycle_pending)
            rc_cycle_rescan = rc_cycle_requested = 1;
    }
    if (rc_cycle_proof_retry == cycle)
        rc_cycle_proof_retry = NULL;
    if (cycle->registered)
        rc_cycle_unlink(cycle);
    cycle->gray_next = 0;
}
static inline int rc_cycle_primary_idle(void) {
    return !rc_cycle_inside && rc_cycle_phase == RC_CYCLE_IDLE && !rc_cycle_pending &&
           !rc_cycle_requested && !rc_cycle_rescan && !rc_cycle_local_requested &&
           rc_cycle_proof_valid && !rc_cycle_proof_build && rc_cycle_anchor_held() &&
           !rc_cycle_proof_anchor->pinned;
}
/* A live unregistered object has no outgoing traced edge: the first such
 * edge registers its source. Bit 2 may remember exposure by a captured parent;
 * later registration must still invalidate that parent's completed proof. */
static inline int rc_cycle_unregistered_leaf(RcCycle *cycle) {
    return !cycle->registered && !cycle->pinned && !cycle->cleared &&
           !(cycle->gray_next & ~(uintptr_t)4) &&
           (rc_cycle_object(cycle)->ownership >> 3) != 0;
}
#ifdef MINYAR_BOUNDED_RC
/* Only an irreversibly dead, unregistered object may carry this bit. It is
 * separate from live proof/exposure tags; allocation and registration reset it. */
enum { RC_CYCLE_PRIVATE_DEAD = 8, RC_CYCLE_CAPTURED_DEAD = 16,
       RC_CYCLE_FRESH_MARK_DEAD = 32, RC_CYCLE_FULL_MARK_DEAD = 64 };
/* Actual-zero owners are outside every current owning path. A previously
 * captured owner may retire during a local job without canceling the primary;
 * this completed-primary helper never admits full-building work. */
static inline int rc_cycle_primary_retirement(void) {
    return !rc_cycle_inside && !rc_cycle_rescan &&
           (rc_cycle_phase == RC_CYCLE_IDLE ||
            (rc_cycle_local_job && rc_cycle_phase >= RC_CYCLE_ROOTS &&
             rc_cycle_phase <= RC_CYCLE_SWEEP)) &&
           rc_cycle_proof_valid && !rc_cycle_proof_build && rc_cycle_anchor_held() &&
           !rc_cycle_proof_anchor->pinned;
}
/* Full MARK has already scanned this dead owner's fields. It cannot remain
 * on an owning path; no gray pin/active field may be discarded. Keep this
 * separate from completed-primary retirement and recheck it for every field. */
static inline int rc_cycle_full_mark_retirement(void) {
    return !rc_cycle_inside && !rc_cycle_local_job && !rc_cycle_rescan &&
           rc_cycle_phase == RC_CYCLE_MARK && !rc_cycle_proof_valid &&
           rc_cycle_proof_build && rc_cycle_anchor_held() &&
           !rc_cycle_proof_anchor->pinned;
}
/* Only MARK's completed scan issues this local final-pin context, after
 * rc_cycle_active is cleared. Queued field cleanup retains its separate
 * unchanged outside-only retirement predicate. */
static inline int rc_cycle_final_mark_pin_zero(void) {
    return rc_cycle_inside && !rc_cycle_active && !rc_cycle_local_job &&
           !rc_cycle_rescan && rc_cycle_phase == RC_CYCLE_MARK &&
           !rc_cycle_proof_valid && rc_cycle_proof_build &&
           rc_cycle_anchor_held() && !rc_cycle_proof_anchor->pinned;
}
/* Called only after an actual RC decrement reached zero, before
 * the bounded queue reuses ownership as its link. A fresh uncaptured owner has
 * never contributed an anchor path; retiring it cannot remove a proven edge. */
static inline void rc_cycle_unregister_zero(RcObject *object, unsigned mark_pin) {
    RcCycle *cycle = rc_cycle_metadata(object);
    unsigned fresh = cycle->marked == 3 && !(cycle->gray_next & ~(uintptr_t)4) &&
                     cycle != rc_cycle_temporary_anchor && rc_cycle_primary_idle();
    unsigned captured = (cycle->marked == 0 || cycle->marked == 2) &&
                        !(cycle->gray_next & ~(uintptr_t)7) && !rc_cycle_proven(cycle) &&
                        rc_cycle_primary_retirement();
    /* Issued only at genuine RC zero for a node registered after this local
     * cohort began. Its fresh tag is not itself a live reachability proof. */
    unsigned fresh_mark = cycle->marked == 3 && cycle->gray_next == 4 &&
                          cycle != rc_cycle_temporary_anchor && rc_cycle_local_job &&
                          rc_cycle_phase == RC_CYCLE_MARK && rc_cycle_primary_retirement();
    unsigned full_mark = cycle->marked == 2 && !cycle->gray_next &&
                         !rc_cycle_proven(cycle) && cycle != rc_cycle_temporary_anchor &&
                          (rc_cycle_full_mark_retirement() ||
                           (mark_pin && rc_cycle_final_mark_pin_zero()));
    if (object->ownership != RC_TRACED || cycle->incoming || !cycle->registered ||
        cycle->pinned || cycle->cleared || cycle == rc_cycle_proof_anchor ||
        cycle == rc_cycle_proof_retry || (!fresh && !captured && !fresh_mark && !full_mark)) {
        rc_cycle_unregister(object);
        return;
    }
    rc_cycle_temporary_changed();
    if (rc_cycle_temporary_anchor == cycle)
        rc_cycle_temporary_anchor = NULL;
    rc_cycle_unlink(cycle);
    if (full_mark) {
        cycle->retired_completed = rc_cycle_completed;
        cycle->retired_anchor_token = (uintptr_t)rc_cycle_proof_anchor;
        cycle->generation = rc_cycle_generation;
    }
    /* Distinct issued bits certify irreversible zero-count retirement. The
     * older fresh-private marker retains its original idle-only field rules. */
    cycle->gray_next = RC_CYCLE_PRIVATE_DEAD | (captured ? RC_CYCLE_CAPTURED_DEAD : 0) |
                      (fresh_mark ? RC_CYCLE_FRESH_MARK_DEAD : 0) |
                      (full_mark ? RC_CYCLE_FULL_MARK_DEAD : 0);
}
#endif

static int rc_cycle_snapshot_new(RcCycle *cycle) {
    if (rc_cycle_local_job)
        return cycle->generation == rc_cycle_local_generation;
    return !(cycle->gray_next & 4) && cycle->generation == rc_cycle_generation;
}
static MINYAR_COLD void rc_cycle_shade_slow(RcCycle *cycle) {
    if (!cycle || !cycle->registered)
        return;
    /* Before full MARK begins, completed marks belong to an old job.
     * A take/drop barrier can run before this root's own ROOTS visit. */
    if (rc_cycle_phase == RC_CYCLE_ROOTS && !rc_cycle_local_job && cycle->marked == 2)
        cycle->marked = 0;
    if (cycle->marked == 3 && !rc_cycle_snapshot_new(cycle))
        cycle->marked = 0;
    if (cycle->marked ||
        (rc_cycle_local_job && !(cycle->gray_next & 4) && rc_cycle_proof_valid &&
         rc_cycle_anchor_held() && rc_cycle_proven(cycle)) ||
        rc_cycle_snapshot_new(cycle))
        return;
    cycle->marked = 1;
    cycle->gray_next &= 7;
    if (rc_cycle_gray_tail)
        rc_cycle_gray_tail->gray_next = (uintptr_t)cycle | (rc_cycle_gray_tail->gray_next & 7);
    else
        rc_cycle_gray_head = cycle;
    rc_cycle_gray_tail = cycle;
}
/* Root-witness propagation is distinct from conservative snapshot shading.
 * A node already scanned from a temporary is queued once more when first
 * reached from the anchor. Each scan still visits only one field per unit. */
static void rc_cycle_shade_proven(RcCycle *cycle) {
    if (!cycle || !cycle->registered || rc_cycle_snapshot_new(cycle) ||
        (rc_cycle_local_job && !(cycle->gray_next & 4) && rc_cycle_proven(cycle)))
        return;
    unsigned generation = rc_cycle_local_job ? rc_cycle_proof_generation : rc_cycle_generation;
    if (!rc_cycle_local_job) {
        cycle->gray_next &= ~(uintptr_t)4;
        cycle->generation = rc_cycle_generation ^ 1;
    }
    if (!(cycle->gray_next & 1) || ((cycle->gray_next >> 1) & 1) != generation) {
        cycle->gray_next =
            (cycle->gray_next & ~(uintptr_t)3) | 1 | ((uintptr_t)generation << 1);
        if (cycle == rc_cycle_active && rc_cycle_phase == RC_CYCLE_MARK)
            rc_cycle_index = 0;
        else if (cycle->marked == 2)
            cycle->marked = 0;
    }
    rc_cycle_shade_slow(cycle);
}
static void rc_cycle_shade_temporary(RcCycle *cycle) {
    if (!cycle || !cycle->registered || rc_cycle_snapshot_new(cycle))
        return;
    if (rc_cycle_proven(cycle)) {
        rc_cycle_shade_proven(cycle);
        return;
    }
    if (!rc_cycle_temporary_proven(cycle)) {
        cycle->gray_next = (cycle->gray_next & ~(uintptr_t)3) | 1 |
                          ((uintptr_t)(rc_cycle_proof_generation ^ 1) << 1);
        if (cycle == rc_cycle_active && rc_cycle_phase == RC_CYCLE_MARK)
            rc_cycle_index = 0;
        else if (cycle->marked == 2)
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
    if (cycle == rc_cycle_temporary_anchor) {
        rc_cycle_temporary_valid = rc_cycle_temporary_build = 0;
    }
    if (cycle == rc_cycle_proof_anchor) {
        rc_cycle_proof_retry = cycle;
        rc_cycle_proof_invalidate();
    }
    /* Do not discard the last temporary's request. Its queued unit validates
     * an unchanged owning path to an independently held root, or rescans. */
    unsigned proven = rc_cycle_proven(cycle) && rc_cycle_anchor_held();
    if (!proven && rc_cycle_proof_valid && !rc_cycle_proof_build && rc_cycle_anchor_held())
        rc_cycle_request_local();
    else
        rc_cycle_request_kind(!proven);
}
/* While tracing is dormant no cycle can exist, so no request is needed. */
static inline void rc_cycle_after_drop(RcObject *object) {
    if (rc_cycle_enabled)
        rc_cycle_check_external(object);
}
#ifdef MINYAR_BOUNDED_RC
/* Only the matching decrement of one certified dead-owner slot may use this.
 * Incoming and real count both fell by one: outside ownership did not change.
 * A captured gray/scanned child is already covered by this finite full MARK;
 * preserve this full build, but retain a local unknown-cohort debt: a private
 * cycle may have lost its last external path even though count-incoming did
 * not change. Completion discards that debt only when no unknown registry
 * remains. No live proof is issued; ordinary unpaired drops stay unchanged. */
static inline void rc_cycle_after_paired_drop(RcObject *object) {
    RcCycle *cycle = rc_cycle_value(object + 1);
    if (rc_cycle_enabled && cycle && cycle->registered &&
        (cycle->marked == 1 || cycle->marked == 2) && !rc_cycle_snapshot_new(cycle) &&
        !cycle->pinned && !cycle->cleared && !rc_cycle_proven(cycle) &&
        cycle != rc_cycle_proof_anchor && cycle != rc_cycle_proof_retry &&
        cycle != rc_cycle_temporary_anchor &&
        (object->ownership >> 3) == cycle->incoming && rc_cycle_full_mark_retirement()) {
        rc_cycle_request_local();
        return;
    }
    rc_cycle_after_drop(object);
}
#endif
static MINYAR_NOINLINE void rc_cycle_add_incoming(RcObject *parent, RcCycle *cycle,
                                                  unsigned additive) {
    RcCycle *source = rc_cycle_metadata(parent);
    rc_cycle_temporary_changed();
    unsigned was_registered = source->registered;
    /* Bit 2 is sticky exposure while unregistered, not a certificate tag.
     * Read it before registration assigns the snapshot namespace. */
    unsigned exposed = !was_registered && (source->gray_next & 4);
    /* First insertion into two independently held, unexposed leaves cannot
     * change a captured full cohort. Classify before registration resets tags;
     * ordinary registration/shading/publication never certifies these nodes. */
    unsigned detached =
        additive && !was_registered && source != cycle &&
        !source->incoming && !source->gray_next && !source->pinned && !source->cleared &&
        !cycle->registered && !cycle->incoming && !cycle->gray_next &&
        !cycle->pinned && !cycle->cleared &&
        (parent->ownership >> 3) && (rc_cycle_object(cycle)->ownership >> 3) &&
        !rc_cycle_inside && !rc_cycle_local_job && !rc_cycle_rescan &&
        rc_cycle_proof_build && !rc_cycle_proof_valid &&
        rc_cycle_phase >= RC_CYCLE_ROOTS && rc_cycle_phase <= RC_CYCLE_SWEEP;
    if (!was_registered)
        rc_cycle_register(source);
    if (!cycle->registered && was_registered && source->marked != 3)
        cycle->gray_next |= 4;
    /* A committed proof certifies existing paths, not all registry objects.
     * Insertion removes no such path, even while a fresh owner is constructed.
     * Unknown children request separate bounded work after publication.
     * Unknown self-insertion retains the strict full-cohort scheduling rule.
     * Never infer new descendants from the incoming-count update. */
    /* An exposed internally owned container may have been skipped by an
     * earlier captured-parent scan. Rejoin those parents on registration,
     * even when a temporary borrower makes its count external. Unexposed
     * inbound parents remain in the finite unknown cohort and cannot have
     * been omitted as completed known parents. */
    /* Replacing a leaf cannot remove a path to any registered descendant.
     * Restrict this exception to a completed idle proof. Exposure above remains
     * sticky so a leaf gaining its first traced child rejoins captured parents. */
    unsigned leaf = rc_cycle_unregistered_leaf(cycle) && rc_cycle_primary_idle();
    unsigned preserve =
        (additive || leaf) && (was_registered || !source->incoming || !exposed) &&
        (rc_cycle_phase == RC_CYCLE_IDLE ||
         (rc_cycle_local_job && (rc_cycle_phase != RC_CYCLE_SWEEP || !cycle->registered ||
                                 rc_cycle_proven(cycle) || rc_cycle_snapshot_new(cycle)))) &&
        rc_cycle_proof_valid && !rc_cycle_proof_build && rc_cycle_anchor_held() &&
        !rc_cycle_proof_anchor->pinned &&
        (!cycle->registered || rc_cycle_proven(cycle) || source != cycle);
    if (!preserve && !detached)
        rc_cycle_proof_invalidate();
    rc_cycle_shade(cycle);
    cycle->incoming++;
    /* A take-store can consume the anchor's sole external owner without an
     * RC decrement. Recheck AFTER incoming changes, before store/poll/reuse. */
    if (preserve && !rc_cycle_anchor_held())
        rc_cycle_proof_invalidate();
    if (rc_cycle_enabled && cycle->registered &&
        (rc_cycle_object(cycle)->ownership >> 3) == cycle->incoming &&
        (parent->ownership >> 3) == source->incoming) {
        if (preserve && rc_cycle_proof_valid) {
            if (rc_cycle_proven(source) && rc_cycle_proven(cycle))
                rc_cycle_request_kind(0);
            else
                rc_cycle_request_local();
        } else
            rc_cycle_request();
    }
}
/* Called only after publishing an additive owning slot, before its poll.
 * The edge proves the direct child. Descendants need bounded field work. */
static void rc_cycle_commit_insert(void *owner, void *value) {
    RcCycle *source = rc_cycle_value(owner), *child = rc_cycle_value(value);
    if (!source || !child || !child->registered || !rc_cycle_proven(source) ||
        !rc_cycle_proof_valid || rc_cycle_proof_build || !rc_cycle_anchor_held() ||
        rc_cycle_proof_anchor->pinned ||
        (rc_cycle_phase != RC_CYCLE_IDLE && !rc_cycle_local_job))
        return;
    if (!(child->gray_next & 4) && rc_cycle_proven(child))
        return;
    unsigned first_proof = !rc_cycle_proven(child);
    /* First proving an active List restarts its index, not its captured
     * limit. An appended suffix still needs a joined finite scan before
     * that parent may move into the known registry. */
    if (first_proof && child == rc_cycle_active && rc_cycle_phase == RC_CYCLE_MARK &&
        !child->record &&
        (size_t)((MinyarList *)(rc_cycle_object(child) + 1))->length > rc_cycle_limit) {
        rc_cycle_proof_invalidate();
        return;
    }
    child->gray_next =
        (child->gray_next & ~(uintptr_t)3) | 1 | ((uintptr_t)rc_cycle_proof_generation << 1);
    if (first_proof && child == rc_cycle_active && rc_cycle_phase == RC_CYCLE_MARK)
        rc_cycle_index = 0;
    else if (first_proof && rc_cycle_shading && child->marked == 2) {
        child->marked = 0;
        rc_cycle_shade(child);
    }
    rc_cycle_request_local();
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
    rc_cycle_temporary_changed();
    /* Removing a live leaf changes no proven path to a registered object.
     * Active finite cohorts and registered removals remain conservative. */
    if (!rc_cycle_unregistered_leaf(cycle) || !rc_cycle_primary_idle())
        rc_cycle_proof_invalidate();
    rc_cycle_shade(cycle);
    cycle->incoming--;
}
#ifdef MINYAR_BOUNDED_RC
/* The parent's ownership word is already a cleanup link/cursor. Its private
 * marker was established at true RC zero; each field rechecks current proof
 * state, because application calls may run between bounded cleanup units. */
static inline unsigned rc_cycle_dead_edge_remove(RcObject *parent, void *value) {
    RcCycle *child = rc_cycle_value(value);
    if (!child)
        return 0;
    RcCycle *owner = rc_cycle_metadata(parent);
    unsigned captured = owner->gray_next == (RC_CYCLE_PRIVATE_DEAD | RC_CYCLE_CAPTURED_DEAD);
    unsigned fresh_mark = owner->gray_next == (RC_CYCLE_PRIVATE_DEAD | RC_CYCLE_FRESH_MARK_DEAD);
    unsigned full_mark = owner->gray_next == (RC_CYCLE_PRIVATE_DEAD | RC_CYCLE_FULL_MARK_DEAD);
    unsigned eligible = full_mark ?
        (rc_cycle_full_mark_retirement() && owner->retired_completed == rc_cycle_completed &&
         owner->generation == rc_cycle_generation && owner->retired_anchor_token == (uintptr_t)rc_cycle_proof_anchor) :
        ((captured || fresh_mark) ? rc_cycle_primary_retirement() : rc_cycle_primary_idle());
    if (owner->registered ||
        (!captured && !fresh_mark && !full_mark && owner->gray_next != RC_CYCLE_PRIVATE_DEAD) ||
        owner->pinned ||
        owner->cleared || owner->incoming || !eligible) {
        rc_cycle_edge_remove(value);
        return 0;
    }
    /* This excluded dead owner is not an anchor-to-child path. The paired
     * incoming decrement and ordinary child RC drop preserve external owners;
     * an unknown surviving child still requests its own bounded work. */
    rc_cycle_temporary_changed();
    child->incoming--;
    return full_mark; /* Local certificate for only this paired child drop. */
}
#endif

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
