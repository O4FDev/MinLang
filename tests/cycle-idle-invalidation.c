/* Test-only causal ledger for repeated collector work in a held component. */
#include <stddef.h>
#ifdef MINYAR_IDLE_LEDGER
static void idle_proof_event(unsigned line, unsigned valid, unsigned inside, unsigned phase,
                             unsigned pending, unsigned local, size_t units, size_t epochs);
#endif
#define main additive_fixture_main
#include "cycle-additive.c"
#undef main

#ifdef MINYAR_IDLE_LEDGER
typedef struct {
    size_t calls, valid_calls, outside_calls;
    unsigned first_phase, first_pending, first_local;
    size_t first_units, first_epochs;
} Invalidation;
static Invalidation invalidations[1024];
static void idle_proof_event(unsigned line, unsigned valid, unsigned inside, unsigned phase,
                             unsigned pending, unsigned local, size_t units, size_t epochs) {
    assert(line < 1024);
    Invalidation *entry = &invalidations[line];
    if (!entry->calls) {
        entry->first_phase = phase;
        entry->first_pending = pending;
        entry->first_local = local;
        entry->first_units = units;
        entry->first_epochs = epochs;
    }
    entry->calls++;
    entry->valid_calls += !!valid;
    entry->outside_calls += !inside;
}
static void clear_ledger(void) {
    memset(invalidations, 0, sizeof invalidations);
}
static void print_ledger(const char *label) {
    for (unsigned i = 0; i < 1024; i++) {
        Invalidation entry = invalidations[i];
        if (entry.calls)
            fprintf(stderr,
                    "CAUSE label=%s line=%u calls=%zu valid=%zu outside=%zu phase=%u pending=%u "
                    "local=%u first_units=%zu first_epochs=%zu\n",
                    label, i, entry.calls, entry.valid_calls, entry.outside_calls,
                    entry.first_phase, entry.first_pending, entry.first_local, entry.first_units,
                    entry.first_epochs);
    }
}
#else
static void clear_ledger(void) {
}
static void print_ledger(const char *label) {
    (void)label;
}
#endif

static MinyarRecord *branch(unsigned value) {
    MinyarRecord *owner = minyar_record_new_traced(1);
    MinyarRecord *leaf = minyar_record_new_traced(1);
    minyar_record_set_traced(leaf, 0, value);
    minyar_record_set_take_traced(owner, 0, slot(leaf));
    return owner;
}
static Graph held(unsigned n) {
    Graph g = graph();
    for (unsigned i = 0; i < n; i++)
        minyar_list_add_take_traced(g.list, slot(branch(10000 + i)));
    drain();
    assert(rc_object_count == 4u + 2u * n);
    assert(rc_cycle_phase == RC_CYCLE_IDLE && rc_cycle_proof_valid);
    assert(rc_cycle_proof_anchor == rc_cycle_value(g.root));
    assert(rc_cycle_anchor_held());
    return g;
}
static void check_held(Graph g, unsigned n, int replacement, unsigned extra) {
    assert(g.list->length == n + 1u + extra);
    assert(g.interior->values[1] == 19);
    for (unsigned i = 0; i < n; i++) {
        MinyarRecord *owner = (MinyarRecord *)(uintptr_t)g.list->values[i + 1];
        MinyarRecord *leaf = (MinyarRecord *)(uintptr_t)owner->values[0];
        assert(leaf->values[0] == (i == 0 && replacement ? 20000 + replacement - 1 : 10000 + i));
    }
}
static void borrow_held(Graph g) {
    minyar_rc_retain_traced(g.interior);
    minyar_rc_release(g.interior);
    drain();
}
static void scenario(unsigned n, const char *label, int assert_local) {
    Graph g = held(n);
    MinyarRecord *replays = NULL;
    if (!strcmp(label, "replacement")) {
        replays = minyar_record_new_traced(1);
        MinyarList *list = minyar_list_new_traced();
        minyar_list_references(list);
        minyar_record_set_take_traced(replays, 0, slot(list));
        minyar_list_add_take_traced(g.list, slot(replays));
        drain();
    }
    assert(rc_cycle_phase == RC_CYCLE_IDLE && rc_cycle_proof_valid);
    size_t units = rc_cycle_units, epochs = rc_cycle_epochs;
    size_t cached = rc_cycle_cached_requests, completed = rc_cycle_completed;
    clear_ledger();
    unsigned valid_after_drop = 0;
    const unsigned rounds = 8;
    for (unsigned i = 0; i < rounds; i++) {
        if (!strcmp(label, "fieldless")) {
            MinyarRecord *scalar = minyar_record_new_traced(1);
            minyar_record_set_traced(scalar, 0, 30000 + i);
            assert(!rc_cycle_value(scalar)->registered);
            minyar_rc_release(scalar);
        } else if (!strcmp(label, "private")) {
            MinyarRecord *private_owner = branch(30000 + i);
            assert(rc_cycle_value(private_owner)->registered);
            assert(!rc_cycle_proven(rc_cycle_value(private_owner)));
            assert(rc_cycle_value(private_owner)->incoming == 0);
            minyar_rc_release(private_owner);
        } else if (!strcmp(label, "replacement")) {
            MinyarList *list = minyar_list_new_traced();
            minyar_list_references(list);
            minyar_record_replace_traced(replays, 0, slot(list), 1);
        } else if (!strcmp(label, "remove-live")) {
            MinyarRecord *fresh = branch(20000 + i);
            minyar_list_set_traced(g.list, 1, slot(fresh));
            minyar_rc_release(fresh);
        } else {
            assert(!strcmp(label, "borrow"));
        }
        valid_after_drop += !!rc_cycle_proof_valid;
        borrow_held(g);
        assert(rc_cycle_proof_valid && rc_cycle_anchor_held());
        if (replays) {
            check_held(g, n, 0, 1);
            assert(((MinyarList *)(uintptr_t)replays->values[0])->length == 0);
            assert(rc_object_count == 6u + 2u * n);
        } else {
            check_held(g, n, !strcmp(label, "remove-live") ? i + 1 : 0, 0);
            assert(rc_object_count == 4u + 2u * n);
        }
    }
    size_t work = rc_cycle_units - units;
    print_ledger(label);
    fprintf(stderr,
            "IDLE label=%s n=%u rounds=%u units=%zu epochs=%zu cached=%zu completed=%zu "
            "valid_after_drop=%u final_valid=%u\n",
            label, n, rounds, work, rc_cycle_epochs - epochs, rc_cycle_cached_requests - cached,
            rc_cycle_completed - completed, valid_after_drop, rc_cycle_proof_valid);
    if (!strcmp(label, "borrow") || !strcmp(label, "fieldless") ||
        !strcmp(label, "replacement")) {
        assert(valid_after_drop == rounds);
        assert(rc_cycle_epochs == epochs);
        assert(work <= 16u * rounds + 64u);
    }
    if (!strcmp(label, "remove-live"))
        assert(rc_cycle_epochs > epochs);
    minyar_rc_release(g.root);
    empty();
    /* This proposed locality bound is tests-first, not an existing guarantee. */
    if (assert_local && !strcmp(label, "private"))
        assert(work <= 16u * rounds + 64u);
}

/* Positive controls use genuine external owners. No controlled retirement is
 * allowed to remove a live path, forget an unknown cycle, or bypass an active
 * finite cohort. The object-count and payload oracles are independent of marks. */
static void positive(unsigned n, const char *label) {
    Graph g = held(n);
    size_t units = rc_cycle_units, epochs = rc_cycle_epochs;
    clear_ledger();
    if (!strcmp(label, "new-child")) {
        MinyarRecord *fresh = branch(40000);
        minyar_list_add_take_traced(g.list, slot(fresh));
        borrow_held(g);
        check_held(g, n, 0, 1);
        assert(g.list->values[n + 1] == slot(fresh));
        MinyarRecord *leaf = (MinyarRecord *)(uintptr_t)fresh->values[0];
        assert(leaf->values[0] == 40000 && rc_object_count == 6u + 2u * n);
        assert(rc_cycle_epochs > epochs);
    } else if (!strcmp(label, "anchor-transfer")) {
        MinyarRecord *receiver = minyar_record_new_traced(1);
        /* A take publication consumes root's sole external owner. The new
         * receiver keeps every old field alive through a different root path. */
        assert(rc_cycle_anchor_held());
        minyar_record_set_take_traced(receiver, 0, slot(g.root));
        assert(!rc_cycle_proof_valid);
        borrow_held(g);
        check_held(g, n, 0, 0);
        assert(receiver->values[0] == slot(g.root));
        assert(rc_object_count == 5u + 2u * n);
        assert(rc_cycle_proof_anchor == rc_cycle_value(receiver));
        assert(rc_cycle_epochs > epochs);
        print_ledger(label);
        fprintf(stderr, "POSITIVE label=%s n=%u units=%zu epochs=%zu\n", label, n,
                rc_cycle_units - units, rc_cycle_epochs - epochs);
        minyar_rc_release(receiver);
        empty();
        return;
    } else if (!strcmp(label, "shared-child")) {
        MinyarRecord *private_owner = minyar_record_new_traced(1);
        minyar_record_set_reference_traced(private_owner, 0, slot(g.interior));
        assert(!rc_cycle_proven(rc_cycle_value(private_owner)));
        minyar_rc_release(private_owner);
        borrow_held(g);
        check_held(g, n, 0, 0);
        assert(rc_object_count == 4u + 2u * n);
    } else if (!strcmp(label, "cross-component")) {
        MinyarRecord *outside = branch(41000);
        /* The private dead owner shares a child held by an independent
         * external owner, without making that cohort an old anchor path. */
        MinyarRecord *private_owner = minyar_record_new_traced(2);
        minyar_record_set_reference_traced(private_owner, 0, slot(g.interior));
        minyar_record_set_reference_traced(private_owner, 1, slot(outside));
        minyar_rc_release(private_owner);
        borrow_held(g);
        check_held(g, n, 0, 0);
        MinyarRecord *leaf = (MinyarRecord *)(uintptr_t)outside->values[0];
        assert(leaf->values[0] == 41000 && rc_object_count == 6u + 2u * n);
        minyar_rc_release(outside);
        drain();
        check_held(g, n, 0, 0);
        assert(rc_object_count == 4u + 2u * n);
    } else {
        assert(!strcmp(label, "unknown-cycle"));
        MinyarRecord *outside = minyar_record_new_traced(2);
        minyar_record_set_reference_traced(outside, 0, slot(outside));
        minyar_record_set_reference_traced(outside, 1, slot(g.interior));
        assert(!rc_cycle_proven(rc_cycle_value(outside)));
        minyar_rc_release(outside);
        borrow_held(g);
        check_held(g, n, 0, 0);
        assert(rc_object_count == 4u + 2u * n);
        assert(rc_cycle_epochs > epochs);
    }
    print_ledger(label);
    fprintf(stderr, "POSITIVE label=%s n=%u units=%zu epochs=%zu final_valid=%u\n", label, n,
            rc_cycle_units - units, rc_cycle_epochs - epochs, rc_cycle_proof_valid);
    minyar_rc_release(g.root);
    empty();
}
static void active_retirement(unsigned n, unsigned phase, unsigned local) {
    Graph g = held(n);
    MinyarRecord *private_owner = branch(42000);
    MinyarRecord *outside = branch(43000);
    if (local)
        rc_cycle_request_local();
    else
        rc_cycle_request();
    force_phase(phase);
    assert(rc_cycle_local_job == local);
    assert(rc_cycle_phase == phase);
    size_t units = rc_cycle_units, epochs = rc_cycle_epochs;
    clear_ledger();
    minyar_rc_release(private_owner);
    drain();
    check_held(g, n, 0, 0);
    MinyarRecord *leaf = (MinyarRecord *)(uintptr_t)outside->values[0];
    assert(leaf->values[0] == 43000 && rc_object_count == 6u + 2u * n);
    assert(rc_cycle_phase == RC_CYCLE_IDLE && rc_cycle_proof_valid && rc_cycle_anchor_held());
    print_ledger(local ? "active-local" : "active-full");
    fprintf(stderr, "ACTIVE n=%u phase=%u local=%u units=%zu epochs=%zu\n", n, phase, local,
            rc_cycle_units - units, rc_cycle_epochs - epochs);
    minyar_rc_release(outside);
    drain();
    assert(rc_object_count == 4u + 2u * n);
    minyar_rc_release(g.root);
    empty();
}

#ifdef MINYAR_BOUNDED_RC
static void cycle_only_drain(void) {
    size_t steps = 0;
    while (rc_cycle_pending) {
        assert(++steps < 4000000);
        size_t before = rc_cycle_units;
        rc_cycle_unit();
        assert(rc_cycle_units - before == 1);
    }
}
static void queued_retirement(unsigned n, const char *mode, unsigned recent) {
    Graph g = held(n);
    MinyarRecord *outside = branch(51000);
    MinyarRecord *receiver = minyar_record_new_traced(1);
    MinyarRecord *owner = minyar_record_new_traced(4);
    minyar_record_set_take_traced(owner, 0, slot(branch(52000)));
    minyar_record_set_reference_traced(owner, 1, slot(g.interior));
    minyar_record_set_reference_traced(owner, 2, slot(outside));
    minyar_record_set_take_traced(owner, 3, slot(branch(53000)));
    assert(rc_cycle_phase == RC_CYCLE_IDLE && rc_cycle_proof_valid);
    assert(!rc_cycle_pending && rc_cycle_value(owner)->marked == 3);
    size_t units = rc_cycle_units, epochs = rc_cycle_epochs;
    clear_ledger();
    RcObject *object = (RcObject *)owner - 1;
    /* Real irreversible drop, without the public call's following poll. */
    rc_drop(owner);
    assert(!rc_cycle_value(owner)->registered && rc_bounded_recent_head == object);
    assert(rc_bounded_saved_cursor(object) == 0);
    if (recent) {
        rc_bounded_recent_object_unit();
        assert(rc_bounded_saved_cursor(object) == 1);
        assert(rc_bounded_recent_head != object); /* Newly dead first child preempts. */
    } else {
        rc_bounded_object_unit();
        assert(rc_bounded_active == object && rc_bounded_cursor == 1);
        assert(rc_bounded_recent_head); /* Child release occurred after cursor advance. */
    }
    int transferred = !strcmp(mode, "transfer");
    int dropped = !strcmp(mode, "drop");
    if (transferred) {
        minyar_record_set_take_traced(receiver, 0, slot(g.root));
        assert(!rc_cycle_proof_valid);
    } else if (dropped) {
        rc_drop(g.root);
        assert(!rc_cycle_proof_valid && !rc_cycle_proof_anchor);
    } else if (!strcmp(mode, "phase") || !strncmp(mode, "local-", 6) ||
               !strncmp(mode, "full-", 5)) {
        /* Rebuild current proof without draining object queues, then change
         * phase before the next dead field. The marker must not freeze old
         * eligibility across this boundary. */
        rc_cycle_request();
        cycle_only_drain();
        assert(rc_cycle_proof_valid && rc_cycle_anchor_held());
        unsigned local = !strncmp(mode, "local-", 6);
        unsigned phase = strstr(mode, "mark")    ? RC_CYCLE_MARK
                         : strstr(mode, "sweep") ? RC_CYCLE_SWEEP
                                                 : RC_CYCLE_ROOTS;
        if (local)
            rc_cycle_request_local();
        else
            rc_cycle_request();
        size_t phase_steps = 0;
        while (rc_cycle_phase != phase) {
            assert(++phase_steps < 4000000);
            rc_cycle_unit(); /* Collector only: dead cursor stays after field zero. */
        }
        assert(rc_cycle_local_job == local && rc_cycle_proof_valid);
        assert(rc_cycle_anchor_held());
        if (recent) {
            size_t steps = 0;
            while (rc_bounded_recent_head != object) {
                assert(++steps < 32 && rc_bounded_recent_head);
                rc_bounded_recent_object_unit();
            }
            rc_bounded_recent_object_unit();
            assert(rc_bounded_saved_cursor(object) == 2);
        } else {
            rc_bounded_old_object_unit();
            assert(rc_bounded_active == object && rc_bounded_cursor == 2);
        }
        assert(!rc_cycle_proof_valid); /* Remaining field uses active-job fallback. */
    } else {
        assert(!strcmp(mode, "rebuild"));
        /* Genuine live owning-edge replacement remains conservative, even
         * with identical pointer bits. Rebuild only the collector queue while
         * the dead owner's cleanup cursor remains parked after its first slot. */
        minyar_rc_retain_traced((void *)(uintptr_t)g.list->values[1]);
        rc_cycle_edge_add(g.list, (void *)(uintptr_t)g.list->values[1]);
        rc_cycle_edge_remove((void *)(uintptr_t)g.list->values[1]);
        rc_drop((void *)(uintptr_t)g.list->values[1]);
        assert(!rc_cycle_proof_valid);
        rc_cycle_request();
        cycle_only_drain();
        assert(rc_cycle_proof_valid && rc_cycle_anchor_held());
        if (recent)
            assert(rc_bounded_saved_cursor(object) == 1);
        else
            assert(rc_bounded_active == object && rc_bounded_cursor == 1);
    }
    drain();
    MinyarRecord *leaf = (MinyarRecord *)(uintptr_t)outside->values[0];
    assert(leaf->values[0] == 51000);
    if (dropped) {
        assert(rc_object_count == 3);
    } else {
        borrow_held(g);
        check_held(g, n, 0, 0);
        assert(rc_object_count == 7u + 2u * n);
        if (transferred) {
            assert(receiver->values[0] == slot(g.root));
            assert(rc_cycle_proof_anchor == rc_cycle_value(receiver));
        }
    }
    print_ledger(mode);
    fprintf(stderr, "QUEUED n=%u mode=%s recent=%u units=%zu epochs=%zu\n", n, mode, recent,
            rc_cycle_units - units, rc_cycle_epochs - epochs);
    minyar_rc_release(outside);
    minyar_rc_release(receiver);
    if (!dropped && !transferred)
        minyar_rc_release(g.root);
    empty();
}
static void certificate_exclusion(unsigned n, unsigned temporary) {
    Graph g = held(n);
    MinyarRecord *owner = branch(54000);
    RcCycle *cycle = rc_cycle_value(owner);
    assert(cycle->marked == 3 && cycle->incoming == 0 && !cycle->pinned);
    /* Guard fault injection: these tags are deliberately not evidence that
     * this private owner is reached from an anchor. ANY tag must reject the
     * fast retirement predicate, including stale/opposite temporary tags. */
    unsigned generation = temporary ? rc_cycle_proof_generation ^ 1 : rc_cycle_proof_generation;
    cycle->gray_next |= 1 | ((uintptr_t)generation << 1);
    clear_ledger();
    rc_drop(owner);
    assert(!rc_cycle_proof_valid);
    drain();
    borrow_held(g);
    check_held(g, n, 0, 0);
    assert(rc_object_count == 4u + 2u * n);
    print_ledger(temporary ? "opposite-certificate" : "primary-certificate");
    minyar_rc_release(g.root);
    empty();
}

static void unknown_after_drop(unsigned n) {
    /* Allocate the unrelated cyclic root first, so the later held graph is
     * the actual primary anchor. Full capture keeps this child alive through
     * its own external owner, without certifying it from the primary anchor. */
    MinyarRecord *child = minyar_record_new_traced(2);
    minyar_record_set_reference_traced(child, 0, slot(child));
    minyar_record_set_traced(child, 1, 56000);
    Graph g = graph();
    for (unsigned i = 0; i < n; i++)
        minyar_list_add_take_traced(g.list, slot(branch(10000 + i)));
    drain();
    assert(rc_object_count == 5u + 2u * n);
    assert(rc_cycle_proof_anchor == rc_cycle_value(g.root));
    assert(rc_cycle_proof_valid && !rc_cycle_proven(rc_cycle_value(child)));
    MinyarRecord *owner = minyar_record_new_traced(1);
    minyar_record_set_take_traced(owner, 0, slot(child));
    assert(rc_cycle_proof_valid && rc_cycle_value(owner)->marked == 3);
    clear_ledger();
    rc_drop(owner);
    unsigned preserved = rc_cycle_proof_valid;
    rc_bounded_object_unit(); /* Paired incoming removal then ordinary child drop. */
    assert(rc_cycle_pending);
    if (preserved)
        assert(rc_cycle_local_requested && !rc_cycle_rescan);
    else
        assert(rc_cycle_rescan);
    drain();
    check_held(g, n, 0, 0);
    assert(rc_object_count == 4u + 2u * n);
    print_ledger("unknown-after-drop");
    fprintf(stderr, "UNKNOWN_AFTER_DROP n=%u primary_preserved=%u child_reclaimed=1\n", n,
            preserved);
    minyar_rc_release(g.root);
    empty();
}

static void metadata_reuse(unsigned n) {
    Graph g = held(n);
    uintptr_t previous = 0, addresses[128];
    unsigned reused = 0, any_reused = 0;
    for (unsigned i = 0; i < 128; i++) {
        MinyarRecord *owner = minyar_record_new_traced(1);
        RcCycle *cycle = rc_cycle_value(owner);
        /* Every allocation starts a new lifetime, including pool/libc reuse.
         * Do not infer reuse from allocator type; record actual address reuse. */
        assert(!cycle->registered && !cycle->marked && !cycle->gray_next && !cycle->incoming &&
               !cycle->pinned && !cycle->cleared);
        reused += previous == (uintptr_t)owner;
        unsigned seen = 0;
        for (unsigned j = 0; j < i; j++)
            seen |= addresses[j] == (uintptr_t)owner;
        any_reused += seen;
        addresses[i] = previous = (uintptr_t)owner;
        MinyarRecord *leaf = minyar_record_new_traced(1);
        minyar_record_set_traced(leaf, 0, 55000 + i);
        minyar_record_set_take_traced(owner, 0, slot(leaf));
        minyar_rc_release(owner);
        borrow_held(g);
        check_held(g, n, 0, 0);
        assert(rc_object_count == 4u + 2u * n);
    }
    fprintf(stderr, "REUSE n=%u rounds=128 observed_consecutive=%u observed_any_prior=%u\n", n,
            reused, any_reused);
#ifdef MINYAR_BOUNDED_HEAP
    assert(any_reused > 0); /* Actual supported pool reuse, not allocator inference. */
#endif
    minyar_rc_release(g.root);
    empty();
}
#endif

int main(int argc, char **argv) {
    assert(argc >= 3);
    unsigned n = (unsigned)strtoul(argv[1], NULL, 10);
    assert(n >= 1 && n <= 4096);
#ifdef MINYAR_BOUNDED_RC
    if (!strcmp(argv[2], "queued")) {
        assert(argc == 5);
        queued_retirement(n, argv[3], (unsigned)strtoul(argv[4], NULL, 10));
    } else if (!strcmp(argv[2], "certificate")) {
        assert(argc == 4);
        certificate_exclusion(n, (unsigned)strtoul(argv[3], NULL, 10));
    } else if (!strcmp(argv[2], "unknown-after-drop"))
        unknown_after_drop(n);
    else if (!strcmp(argv[2], "reuse"))
        metadata_reuse(n);
    else
#endif
        if (!strcmp(argv[2], "active-local") || !strcmp(argv[2], "active-full")) {
        assert(argc == 4);
        unsigned phase = (unsigned)strtoul(argv[3], NULL, 10);
        assert(phase >= RC_CYCLE_ROOTS && phase <= RC_CYCLE_SWEEP);
        active_retirement(n, phase, !strcmp(argv[2], "active-local"));
    } else if (!strcmp(argv[2], "new-child") || !strcmp(argv[2], "anchor-transfer") ||
               !strcmp(argv[2], "shared-child") || !strcmp(argv[2], "cross-component") ||
               !strcmp(argv[2], "unknown-cycle"))
        positive(n, argv[2]);
    else
        scenario(n, argv[2], argc > 3 && !strcmp(argv[3], "assert-local"));
    assert(rc_object_count == 0 && rc_bytes == 0 && !pending());
    return 0;
}
