/* A separately rooted JSON owner must not cancel an unrelated primary proof. */
#define MINYAR_LEAF_CHURN_HELPERS 1
#include "cycle-leaf-churn.c"

#ifdef MINYAR_BOUNDED_RC
static void captured_cycle_drain(void) {
    size_t steps = 0;
    while (rc_cycle_pending) {
        assert(++steps < 4000000);
        size_t before = rc_cycle_units;
        rc_cycle_unit();
        assert(rc_cycle_units - before == 1);
    }
}
static void captured_phase(unsigned phase) {
    size_t steps = 0;
    while (rc_cycle_phase != phase) {
        assert(++steps < 4000000 && rc_cycle_pending);
        rc_cycle_unit();
    }
}
static MinyarRecord *captured_owner(Churn c, unsigned value) {
    MinyarRecord *owner = minyar_record_new_traced(3);
    minyar_record_set_reference_traced(owner, 0, slot(c.g.interior));
    minyar_record_set_take_traced(owner, 1, slot(churn_branch(value)));
    minyar_record_set_traced(owner, 2, value + 1u);
    assert(rc_cycle_value(owner)->registered);
    assert(!rc_cycle_proven(rc_cycle_value(owner)));
    assert(rc_cycle_value(owner)->incoming == 0);
    return owner;
}
static void captured_retirement(unsigned n, unsigned phase) {
    Churn c = churn_graph(n);
    const unsigned rounds = 8;
    size_t work = 0, growth = 0;
    unsigned preserved = 0;
    for (unsigned i = 0; i < rounds; i++) {
        MinyarRecord *owner = captured_owner(c, 70000 + i);
        RcCycle *cycle = rc_cycle_value(owner);
        rc_cycle_request_local();
        captured_cycle_drain();
        assert(rc_cycle_phase == RC_CYCLE_IDLE && rc_cycle_proof_valid);
        assert(rc_cycle_proof_anchor == rc_cycle_value(c.g.root));
        assert(cycle->marked == 0 && !rc_cycle_proven(cycle));
        assert(owner->values[0] == slot(c.g.interior));
        MinyarRecord *branch = (MinyarRecord *)(uintptr_t)owner->values[1];
        MinyarRecord *leaf = (MinyarRecord *)(uintptr_t)branch->values[0];
        assert(leaf->values[0] == 70000 + (long long)i);
        if (phase) {
            /* A real leaf-slot store cancels the completed temporary witness
             * without changing any primary path. The new local job must run. */
            minyar_record_replace_traced(branch, 0, slot(leaf), 0);
            assert(rc_cycle_proof_valid && !rc_cycle_temporary_valid);
            rc_cycle_request_local();
            captured_phase(phase);
            if (phase == RC_CYCLE_MARK) {
                size_t steps = 0;
                while (cycle->marked != 2) {
                    assert(++steps < 4000000 && rc_cycle_phase == RC_CYCLE_MARK);
                    rc_cycle_unit();
                }
            }
            assert(rc_cycle_local_job && rc_cycle_proof_valid && !rc_cycle_proof_build);
            assert(!rc_cycle_proven(cycle));
        }
        /* A genuine last-owner decrement, not a manufactured metadata tag. */
        assert(((RcObject *)owner - 1)->ownership == (8u | RC_TRACED));
        size_t units = rc_cycle_units, epochs = rc_cycle_epochs;
        rc_drop(owner);
        if (phase == RC_CYCLE_ROOTS) {
            /* before_drop must shade and pin this not-yet-scanned gray node. */
            assert(cycle->registered && cycle->pinned && cycle->marked == 1);
            assert(((RcObject *)owner - 1)->ownership >> 3 == 1);
        }
        preserved += !!rc_cycle_proof_valid;
        drain();
        work += rc_cycle_units - units;
        growth += rc_cycle_epochs - epochs;
        churn_check(c, n, 0);
        assert(rc_cycle_proof_valid && rc_cycle_anchor_held());
    }
    fprintf(stderr, "CAPTURED n=%u phase=%u rounds=%u units=%zu epochs=%zu preserved=%u\n",
            n, phase, rounds, work, growth, preserved);
    minyar_rc_release(c.g.root);
    empty(); /* Independent reclamation oracle precedes performance assertions. */
    assert(preserved == rounds);
    if (phase == RC_CYCLE_ROOTS) {
        /* This owner was gray-pinned, rather than actually retired outside
         * collector service. Keep that existing conservative path unchanged. */
        assert(growth > 0);
    } else {
        assert(work <= 16u * rounds + 64u);
    }
}
static void captured_full(unsigned n, unsigned phase) {
    Churn c = churn_graph(n);
    MinyarRecord *owner = captured_owner(c, 72000);
    RcCycle *cycle = rc_cycle_value(owner);
    rc_cycle_request_local();
    captured_cycle_drain();
    assert(cycle->marked == 0 && !rc_cycle_proven(cycle));
    rc_cycle_request();
    captured_phase(phase);
    if (phase == RC_CYCLE_MARK) {
        size_t steps = 0;
        while (cycle->marked != 2) {
            assert(++steps < 4000000 && rc_cycle_phase == RC_CYCLE_MARK);
            rc_cycle_unit();
        }
    }
    assert(!rc_cycle_local_job && rc_cycle_proof_build);
    rc_drop(owner);
    if (cycle->pinned) {
        assert(cycle->registered && cycle->marked == 1);
        assert(((RcObject *)owner - 1)->ownership >> 3 == 1);
    } else {
        assert(!rc_cycle_proof_valid);
    }
    drain();
    churn_check(c, n, 0);
    minyar_rc_release(c.g.root);
    empty();
    fprintf(stderr, "FULL n=%u phase=%u reclaimed=1\n", n, phase);
}
static void captured_queued(unsigned n, unsigned phase, unsigned transfer) {
    Churn c = churn_graph(n);
    MinyarRecord *owner = captured_owner(c, 73000);
    RcCycle *cycle = rc_cycle_value(owner);
    MinyarRecord *receiver = minyar_record_new_traced(1);
    rc_cycle_request_local();
    captured_cycle_drain();
    assert(cycle->marked == 0 && !rc_cycle_proven(cycle));
    assert(((RcObject *)owner - 1)->ownership == (8u | RC_TRACED));
    rc_drop(owner);
    assert(!cycle->registered);
    /* Product-independent fact: the last outside owner has died, fields remain. */
    assert(((RcObject *)owner - 1)->ownership & 7);
    rc_bounded_object_unit();
    assert(rc_bounded_active == (RcObject *)owner - 1 && rc_bounded_cursor == 1);
    if (transfer) {
        /* The real take-store barriers and field publication, before the
         * public helper's poll, keep the dead cursor parked for this check. */
        unsigned char *map = (unsigned char *)(receiver->values + receiver->length);
        map[0] = 1;
        rc_cycle_edge_insert(receiver, c.g.root);
        receiver->values[0] = slot(c.g.root);
        rc_cycle_commit_insert(receiver, c.g.root);
        assert(!rc_cycle_proof_valid);
    } else {
        rc_cycle_request();
        captured_phase(phase);
        assert(rc_cycle_proof_build && !rc_cycle_local_job);
    }
    rc_bounded_old_object_unit();
    assert(rc_bounded_active == (RcObject *)owner - 1 && rc_bounded_cursor == 2);
    assert(!rc_cycle_proof_valid); /* Certificate must not freeze old eligibility. */
    drain();
    assert(rc_object_count == 8u + 2u * n); /* Includes the independent receiver. */
    if (transfer) {
        assert(receiver->values[0] == slot(c.g.root));
        /* Reacquire an actual external owner through the receiver before its
         * last drop, so every graph payload can still be inspected safely. */
        minyar_rc_retain_traced((void *)(uintptr_t)receiver->values[0]);
    }
    minyar_rc_release(receiver);
    drain();
    churn_check(c, n, 0);
    minyar_rc_release(c.g.root);
    empty();
    fprintf(stderr, "QUEUED_CAPTURED n=%u phase=%u transfer=%u reclaimed=1\n",
            n, phase, transfer);
}
#endif
int main(int argc, char **argv) {
    assert(argc == 3);
    unsigned n = (unsigned)strtoul(argv[1], NULL, 10);
    unsigned phase = (unsigned)strtoul(argv[2], NULL, 10);
    assert(n >= 32 && n <= 2048 && phase <= RC_CYCLE_SWEEP);
#ifdef MINYAR_BOUNDED_RC
    if (!strcmp(argv[2], "all")) {
        for (unsigned p = RC_CYCLE_IDLE; p <= RC_CYCLE_SWEEP; p++)
            captured_retirement(n, p);
        for (unsigned p = RC_CYCLE_ROOTS; p <= RC_CYCLE_SWEEP; p++) {
            captured_full(n, p);
            captured_queued(n, p, 0);
        }
        captured_queued(n, RC_CYCLE_IDLE, 1);
    } else {
        captured_retirement(n, phase);
    }
#else
    (void)n; (void)phase;
    assert(!"captured-retirement requires a bounded profile");
#endif
    empty();
    return 0;
}
