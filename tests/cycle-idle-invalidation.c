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
    if (!strcmp(label, "borrow") || !strcmp(label, "fieldless")) {
        assert(valid_after_drop == rounds);
        assert(rc_cycle_epochs == epochs);
        assert(work <= 16u * rounds + 64u);
    }
    if (!strcmp(label, "remove-live") || !strcmp(label, "replacement"))
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

int main(int argc, char **argv) {
    assert(argc >= 3);
    unsigned n = (unsigned)strtoul(argv[1], NULL, 10);
    assert(n >= 1 && n <= 4096);
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
