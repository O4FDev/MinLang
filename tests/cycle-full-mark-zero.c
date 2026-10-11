/* Source-only TDD proposal for current joined key 00100001c0064e21.
 * Data construction, mutation, retain/release and phase service are real APIs;
 * no collector mark, tag, generation, pin or proof flag is written here. */
#define MINYAR_DETACHED_FIRST_INSERTION_HELPERS 1
#include "cycle-detached-first-insertion.c"

#ifdef MINYAR_BOUNDED_RC
static MinyarRecord *full_zero_owner(Churn c) {
    MinyarRecord *owner = minyar_record_new_traced(3);
    minyar_record_set_reference_traced(owner, 0, slot(c.g.interior));
    minyar_record_set_take_traced(owner, 1, slot(churn_branch(91001)));
    minyar_record_set_traced(owner, 2, 91002);
    return owner;
}
static MinyarRecord *full_zero_primary(Churn c) {
    /* The newest real outside owner is visited before the independent owner.
     * Its genuine owning edge certifies Core, never the unrelated owner. */
    MinyarRecord *primary = minyar_record_new_traced(1);
    minyar_record_set_reference_traced(primary, 0, slot(c.g.root));
    return primary;
}
static void full_zero_contract(MinyarRecord *primary, MinyarRecord *owner,
                               unsigned rescan) {
    RcCycle *cycle = rc_cycle_value(owner);
    assert(rc_cycle_phase == RC_CYCLE_MARK && !rc_cycle_local_job);
    assert(!rc_cycle_inside && !rc_cycle_proof_valid && rc_cycle_proof_build);
    assert(rc_cycle_rescan == rescan && rc_cycle_pending);
    assert(rc_cycle_proof_anchor == rc_cycle_value(primary));
    assert(rc_cycle_anchor_held() && !rc_cycle_proof_anchor->pinned);
    assert(cycle->registered && cycle->marked == 2 && cycle->gray_next == 0);
    assert(!cycle->incoming && !cycle->pinned && !cycle->cleared);
    assert(!rc_cycle_proven(cycle));
    assert(cycle != rc_cycle_proof_anchor && cycle != rc_cycle_proof_retry);
    assert(cycle != rc_cycle_temporary_anchor);
    assert(((RcObject *)owner - 1)->ownership == (8u | RC_TRACED));
}
static void full_zero(unsigned n, unsigned rescan) {
    Churn c = churn_graph(n);
    MinyarRecord *owner = full_zero_owner(c);
    MinyarRecord *primary = full_zero_primary(c);
    MinyarRecord *branch = (MinyarRecord *)(uintptr_t)owner->values[1];
    MinyarRecord *leaf = (MinyarRecord *)(uintptr_t)branch->values[0];
    drain();
    assert(rc_object_count == 11u + 2u * n);
    size_t epochs = rc_cycle_epochs, completed = rc_cycle_completed;
    full_phase(c, RC_CYCLE_MARK); /* Existing real replacement + borrow/drop. */
    RcCycle *cycle = rc_cycle_value(owner);
    size_t turns = 0;
    while (cycle->marked != 2) {
        assert(++turns < 4000000 && rc_cycle_pending);
        assert(rc_cycle_phase == RC_CYCLE_MARK);
        minyar_rc_poll(1);
    }
    full_zero_contract(primary, owner, 0);
    assert(owner->values[0] == slot(c.g.interior));
    assert(owner->values[2] == 91002 && leaf->values[0] == 91001);
    if (rescan) {
        /* This internally owned, unproven registered child loses a genuine
         * temporary root. Existing request_kind(1) leaves a full rescan debt.
         * The prospective zero-owner rule must not discharge that debt. */
        RcCycle *child = rc_cycle_value(branch);
        assert(child->registered && !rc_cycle_proven(child));
        assert(references(branch) == child->incoming && child->incoming == 1);
        minyar_rc_retain_traced(branch);
        assert(!rc_cycle_rescan && references(branch) == 2 && child->incoming == 1);
        assert(child->registered && !rc_cycle_snapshot_new(child));
        assert((child->marked == 1 || child->marked == 2) && !child->pinned && !child->cleared);
        assert(child != rc_cycle_proof_anchor && child != rc_cycle_proof_retry &&
               child != rc_cycle_temporary_anchor && !rc_cycle_proven(child));
        fprintf(stderr, "UNPAIRED_PRE n=%u rescan=%u references=%zu incoming=%zu phase=%u registered=%u snapshot_new=%u mark=%u pinned=%u cleared=%u proven=%u primary_held=%u\n",
                n, rc_cycle_rescan, references(branch), (size_t)child->incoming,
                rc_cycle_phase, (unsigned)child->registered,
                (unsigned)rc_cycle_snapshot_new(child), (unsigned)child->marked,
                (unsigned)child->pinned, (unsigned)child->cleared,
                (unsigned)rc_cycle_proven(child), (unsigned)rc_cycle_anchor_held());
        minyar_rc_release(branch); /* No incoming-edge removal accompanies this. */
        assert(rc_cycle_rescan && references(branch) == 1 && child->incoming == 1);
        assert(child->registered && !rc_cycle_snapshot_new(child));
        assert((child->marked == 1 || child->marked == 2) && !child->pinned && !child->cleared);
        assert(child != rc_cycle_proof_anchor && child != rc_cycle_proof_retry &&
               child != rc_cycle_temporary_anchor && !rc_cycle_proven(child));
        fprintf(stderr, "UNPAIRED_POST n=%u rescan=%u references=%zu incoming=%zu phase=%u registered=%u snapshot_new=%u mark=%u pinned=%u cleared=%u proven=%u primary_held=%u\n",
                n, rc_cycle_rescan, references(branch), (size_t)child->incoming,
                rc_cycle_phase, (unsigned)child->registered,
                (unsigned)rc_cycle_snapshot_new(child), (unsigned)child->marked,
                (unsigned)child->pinned, (unsigned)child->cleared,
                (unsigned)rc_cycle_proven(child), (unsigned)rc_cycle_anchor_held());
        full_zero_contract(primary, owner, 1);
    }
    /* Observe the same real decrement before unrelated bounded queue service.
     * This is the runtime drop used by public release, including before_drop
     * and gray deferral. The queue keeps metadata alive until drain below.
     * Never interpret the queued ownership word as an RC count. */
    fprintf(stderr, "FULL_ZERO_PRE n=%u rescan=%u phase=%u local=%u valid=%u build=%u held=%u mark=%u gray=%zu registered=%u incoming=%zu pinned=%u cleared=%u references=%zu\n",
            n, rescan, rc_cycle_phase, rc_cycle_local_job, rc_cycle_proof_valid,
            rc_cycle_proof_build, !!rc_cycle_anchor_held(), (unsigned)cycle->marked,
            (size_t)cycle->gray_next, (unsigned)cycle->registered,
            (size_t)cycle->incoming, (unsigned)cycle->pinned,
            (unsigned)cycle->cleared, references(owner));
    rc_drop(owner);
    assert(!cycle->registered && !cycle->pinned && !cycle->incoming);
    unsigned build_after_zero = rc_cycle_proof_build;
    unsigned valid_after_zero = rc_cycle_proof_valid;
    unsigned rescan_after_zero = rc_cycle_rescan;
    uintptr_t issued = cycle->gray_next;
    fprintf(stderr, "FULL_ZERO_AFTER n=%u rescan=%u build=%u valid=%u rescan_after=%u registered=%u incoming=%zu pinned=%u marker=%zu real_zero_no_gray_pin=1\n",
            n, rescan, build_after_zero, valid_after_zero, rescan_after_zero,
            (unsigned)cycle->registered, (size_t)cycle->incoming,
            (unsigned)cycle->pinned, (size_t)issued);
    drain();
    size_t full_epochs = rc_cycle_epochs - epochs;
    size_t full_completed = rc_cycle_completed - completed;
    core_payloads(c, n, 1, 0);
    assert(primary->values[0] == slot(c.g.root));

    /* Keep the same independently held primary for the locality measurement.
     * Releasing it here would require an unrelated replacement proof.
     * A full snapshot already in progress necessarily has its own finite work.
     * Count that captured completion separately; retain the exact established
     * 192-unit gate for eight subsequent borrow/drop requests after completion. */
    size_t units = rc_cycle_units;
    for (unsigned i = 0; i < 8; i++) {
        minyar_rc_retain_traced(c.g.interior);
        minyar_rc_release(c.g.interior);
        drain();
        core_payloads(c, n, 1, 0); /* The measured primary remains externally held. */
        assert(primary->values[0] == slot(c.g.root));
    }
    size_t borrowed_work = rc_cycle_units - units;
    minyar_rc_release(primary);
    drain();
    churn_check(c, n, 0);
    minyar_rc_release(c.g.root);
    empty(); /* Independent payload/count/root-drop oracle precedes locality. */
    fprintf(stderr, "FULL_ZERO n=%u k=%u rescan=%u build_after=%u valid_after=%u rescan_after=%u marker=%zu epochs=%zu completed=%zu borrowed_units=%zu reclaimed=1\n",
            n, MINYAR_RC_POLL_BUDGET, rescan, build_after_zero,
            valid_after_zero, rescan_after_zero, (size_t)issued, full_epochs,
            full_completed, borrowed_work);
    if (!rescan) assert(borrowed_work <= 16u * 8u + 64u); /* Unchanged 192. */
    assert(!valid_after_zero); /* A building job is never a completed proof. */
    if (rescan) {
        assert(!build_after_zero && rescan_after_zero);
    } else {
        assert(build_after_zero && !rescan_after_zero);
        assert(full_epochs == 1 && full_completed == 1);
    }
}
static void full_roots_registered_add(unsigned n) {
    Churn c = churn_graph(n);
    MinyarRecord *source = minyar_record_new_traced(3);
    minyar_record_set_reference_traced(source, 0, slot(c.g.interior));
    minyar_record_set_traced(source, 2, 92001);
    MinyarRecord *primary = full_zero_primary(c);
    drain();
    full_phase(c, RC_CYCLE_ROOTS);
    MinyarRecord *child = churn_branch(92002);
    RcCycle *s = rc_cycle_value(source), *p = rc_cycle_value(child);
    active(RC_CYCLE_ROOTS);
    assert(rc_cycle_proof_anchor == rc_cycle_value(primary));
    assert(rc_cycle_anchor_held() && !rc_cycle_proof_anchor->pinned);
    assert(s->registered && s->marked == 1 && !rc_cycle_proven(s));
    assert(!s->incoming && !s->pinned && !s->cleared);
    assert(!rc_cycle_snapshot_new(s) && references(source) == 1);
    assert(p->registered && p->marked == 3 && p->gray_next == 0);
    assert(!p->incoming && !p->pinned && !p->cleared);
    assert(rc_cycle_snapshot_new(p) && references(child) == 1);
    minyar_record_set_reference_traced(source, 1, slot(child));
    unsigned canceled = !rc_cycle_proof_build && rc_cycle_rescan;
    drain();
    core_payloads(c, n, 4, 0);
    assert(source->values[0] == slot(c.g.interior) && source->values[1] == slot(child));
    assert(source->values[2] == 92001);
    MinyarRecord *leaf = (MinyarRecord *)(uintptr_t)child->values[0];
    assert(leaf->values[0] == 92002);
    minyar_rc_release(child);
    minyar_rc_release(source);
    drain();
    core_payloads(c, n, 1, 0);
    minyar_rc_release(primary);
    drain();
    churn_check(c, n, 0);
    minyar_rc_release(c.g.root);
    empty();
    fprintf(stderr, "FULL_ROOTS_REGISTERED n=%u canceled=%u reclaimed=1\n", n, canceled);
    assert(canceled); /* Live registered graph discovery remains conservative. */
}
/* A captured unproven self-cycle loses its only external owning path when
 * this genuine scanned zero owner dies. Preserving the primary must not let
 * the idle shortcut discard its independent unknown-cohort collection debt. */
static void full_zero_private_cycle(unsigned n) {
    Churn c = churn_graph(n);
    MinyarRecord *private = minyar_record_new_traced(2);
    minyar_record_set_traced(private, 1, 94001);
    minyar_record_set_reference_traced(private, 0, slot(private));
    MinyarRecord *owner = minyar_record_new_traced(3);
    minyar_record_set_reference_traced(owner, 0, slot(c.g.interior));
    minyar_record_set_take_traced(owner, 1, slot(private));
    minyar_record_set_traced(owner, 2, 94002);
    MinyarRecord *primary = full_zero_primary(c);
    drain();
    full_phase(c, RC_CYCLE_MARK);
    RcCycle *source = rc_cycle_value(owner), *child = rc_cycle_value(private);
    size_t turns = 0;
    while (source->marked != 2) {
        assert(++turns < 4000000 && rc_cycle_phase == RC_CYCLE_MARK);
        minyar_rc_poll(1);
    }
    full_zero_contract(primary, owner, 0);
    assert(child->registered && !rc_cycle_snapshot_new(child));
    assert((child->marked == 1 || child->marked == 2) && !child->pinned && !child->cleared);
    assert(child != rc_cycle_proof_anchor && child != rc_cycle_proof_retry &&
           child != rc_cycle_temporary_anchor && !rc_cycle_proven(child));
    assert(references(private) == 2 && child->incoming == 2);
    assert(private->values[0] == slot(private) && private->values[1] == 94001);
    assert(owner->values[1] == slot(private) && owner->values[2] == 94002);
    core_payloads(c, n, 3, 0);
    fprintf(stderr, "PRIVATE_CYCLE_PRE n=%u phase=%u local=%u valid=%u build=%u rescan=%u private_refs=%zu private_incoming=%zu private_mark=%u private_proven=%u\n",
            n, rc_cycle_phase, rc_cycle_local_job, rc_cycle_proof_valid,
            rc_cycle_proof_build, rc_cycle_rescan, references(private),
            (size_t)child->incoming, (unsigned)child->marked, (unsigned)rc_cycle_proven(child));
    rc_drop(owner);
    /* Never read the private object or queued owner count after this point. */
    unsigned full_jobs = 1, local_jobs = 0;
    size_t local_units = 0;
    turns = 0;
    while (rc_pending_count) {
        assert(++turns < 4000000);
        size_t epochs = rc_cycle_epochs, units = rc_cycle_units;
        unsigned was_local = rc_cycle_local_job;
        minyar_rc_poll(1);
        assert(rc_cycle_epochs - epochs <= 1 && rc_cycle_units - units <= 1);
        if (rc_cycle_epochs != epochs) {
            if (rc_cycle_local_job) local_jobs++;
            else full_jobs++;
        }
        if (was_local || rc_cycle_local_job)
            local_units += rc_cycle_units - units;
    }
    /* Must reclaim the private cycle now, before changing any primary root.
     * A later anchor loss/full scan must not mask an idle cached-cycle leak. */
    core_payloads(c, n, 1, 0);
    assert(primary->values[0] == slot(c.g.root));
    unsigned held = rc_cycle_proof_valid && rc_cycle_anchor_held();
    size_t units = rc_cycle_units;
    for (unsigned i = 0; i < 8; i++) {
        minyar_rc_retain_traced(c.g.interior);
        minyar_rc_release(c.g.interior);
        drain();
        core_payloads(c, n, 1, 0);
    }
    size_t borrowed_units = rc_cycle_units - units;
    minyar_rc_release(primary);
    drain();
    churn_check(c, n, 0);
    minyar_rc_release(c.g.root);
    empty();
    fprintf(stderr, "PRIVATE_CYCLE n=%u k=%u full_jobs=%u local_jobs=%u local_units=%zu held=%u borrowed_units=%zu reclaimed=1\n",
            n, MINYAR_RC_POLL_BUDGET, full_jobs, local_jobs, local_units, held, borrowed_units);
    assert(held && full_jobs == 1 && local_jobs <= 1);
    assert(local_units <= 16u + 64u);
    assert(borrowed_units <= 16u * 8u + 64u); /* Unchanged 192. */
}
/* Authentic product observer interleavings, following the existing issued40
 * controls: construction and last-owner death are real; collector and object
 * units are scheduled separately while the queued dead fields remain parked.
 * No proof, phase, generation, reference count or incoming metadata is stamped. */
static void full_zero_cycle_phase(unsigned phase) {
    size_t steps = 0;
    while (rc_cycle_phase != phase) {
        assert(++steps < 4000000 && rc_cycle_pending);
        size_t units = rc_cycle_units;
        rc_cycle_unit();
        assert(rc_cycle_units == units + 1);
    }
}
static void full_zero_cycle_complete(void) {
    full_zero_cycle_phase(RC_CYCLE_IDLE);
}
static void full_zero_new_build(Churn c) {
    /* Real same-value owning-slot barriers and publication, before its poll.
     * There is no new permanent RC owner; the paired incoming updates balance. */
    rc_cycle_edge_add(c.callback, c.g.root);
    rc_cycle_edge_remove(c.g.root);
    c.callback->values[2] = slot(c.g.root);
    rc_cycle_request();
    full_zero_cycle_phase(RC_CYCLE_MARK);
    active(RC_CYCLE_MARK);
}
static void full_zero_queued(unsigned n, const char *mode) {
    Churn c = churn_graph(n);
    unsigned transfer = !strcmp(mode, "queued-anchor");
    MinyarRecord *receiver = transfer ? minyar_record_new_traced(1) : NULL;
    MinyarRecord *owner = full_zero_owner(c);
    MinyarRecord *primary = full_zero_primary(c);
    drain();
    full_phase(c, RC_CYCLE_MARK);
    RcCycle *cycle = rc_cycle_value(owner);
    size_t steps = 0;
    /* First field has an independently reached primary path. Its later drop
     * therefore does not itself request rescan for an unknown surviving child. */
    while (cycle->marked != 2 || !rc_cycle_proven(rc_cycle_value(c.g.interior))) {
        assert(++steps < 4000000 && rc_cycle_phase == RC_CYCLE_MARK);
        minyar_rc_poll(1);
    }
    full_zero_contract(primary, owner, 0);
    core_payloads(c, n, 4 + transfer, 0);
    MinyarRecord *branch = (MinyarRecord *)(uintptr_t)owner->values[1];
    MinyarRecord *leaf = (MinyarRecord *)(uintptr_t)branch->values[0];
    assert(leaf->values[0] == 91001 && owner->values[2] == 91002);
    size_t completed = rc_cycle_completed;
    unsigned generation = rc_cycle_generation;
    uintptr_t anchor_token = (uintptr_t)rc_cycle_proof_anchor;
    rc_drop(owner); /* Actual outside decrement to zero, before queue reuse. */
    assert(!cycle->registered && !cycle->pinned && !cycle->incoming);
    assert(cycle->gray_next == 72u); /* Newly issued full-MARK death, never stamped. */
    assert(rc_cycle_proof_build && !rc_cycle_rescan && !rc_cycle_proof_valid);
    rc_bounded_object_unit();
    assert(rc_bounded_active == (RcObject *)owner - 1 && rc_bounded_cursor == 1);
    assert(rc_cycle_proof_build && !rc_cycle_rescan && !rc_cycle_proof_valid);
    if (!strcmp(mode, "queued-rescan")) {
        rc_cycle_request(); /* Real pending-rescan request, not a state write. */
        assert(rc_cycle_rescan);
    } else if (!strcmp(mode, "queued-sweep")) {
        full_zero_cycle_phase(RC_CYCLE_SWEEP);
        assert(rc_cycle_completed == completed && rc_cycle_generation == generation);
        assert(rc_cycle_proof_build && !rc_cycle_proof_valid && !rc_cycle_rescan);
    } else if (!strcmp(mode, "queued-complete")) {
        full_zero_cycle_complete();
        assert(rc_cycle_completed == completed + 1);
        assert(rc_cycle_proof_valid && !rc_cycle_proof_build && rc_cycle_anchor_held());
        assert((uintptr_t)rc_cycle_proof_anchor == anchor_token);
    } else if (transfer) {
        /* Exact public take-store barriers/publication before its poll; the
         * primary's last outside owner moves into this independent receiver. */
        unsigned char *map = (unsigned char *)(receiver->values + receiver->length);
        map[0] = 1;
        rc_cycle_edge_insert(receiver, primary);
        receiver->values[0] = slot(primary);
        rc_cycle_commit_insert(receiver, primary);
        assert(!rc_cycle_anchor_held() && !rc_cycle_proof_build && rc_cycle_rescan);
        full_zero_cycle_complete();
        full_zero_new_build(c);
        assert(rc_cycle_anchor_held());
        assert(rc_cycle_proof_anchor == rc_cycle_value(receiver));
        assert((uintptr_t)rc_cycle_proof_anchor != anchor_token);
    } else {
        assert(!strcmp(mode, "queued-restart") || !strcmp(mode, "queued-generation-aba"));
        unsigned jobs = !strcmp(mode, "queued-generation-aba") ? 2u : 1u;
        full_zero_cycle_complete();
        for (unsigned i = 0; i < jobs; i++) {
            full_zero_new_build(c);
            assert(rc_cycle_anchor_held() && (uintptr_t)rc_cycle_proof_anchor == anchor_token);
            assert(rc_cycle_completed == completed + 1 + i);
            if (i + 1 < jobs)
                full_zero_cycle_complete();
        }
        assert((rc_cycle_generation == generation) == (jobs == 2));
        /* With two real jobs the one-bit generation and actual anchor match,
         * but completion identity differs. The counter must prevent this ABA. */
    }
    unsigned phase_at_field = rc_cycle_phase;
    unsigned generation_at_field = rc_cycle_generation;
    size_t completed_at_field = rc_cycle_completed;
    uintptr_t anchor_at_field = (uintptr_t)rc_cycle_proof_anchor;
    /* Do not interpret queued ownership as an RC count, or dereference the
     * private branch after this field: a real zero may free or gray-pin it. */
    rc_bounded_old_object_unit();
    assert(rc_bounded_active == (RcObject *)owner - 1 && rc_bounded_cursor == 2);
    unsigned fallback = !rc_cycle_proof_valid && !rc_cycle_proof_build && rc_cycle_rescan;
    drain();
    core_payloads(c, n, 1 + transfer, 0);
    assert(primary->values[0] == slot(c.g.root));
    if (transfer) {
        assert(receiver->values[0] == slot(primary));
        minyar_rc_release(receiver); /* The original primary owner was taken. */
    } else {
        minyar_rc_release(primary);
    }
    drain();
    churn_check(c, n, 0);
    minyar_rc_release(c.g.root);
    empty(); /* Independent values/count/root-drop before fallback assertion. */
    fprintf(stderr, "QUEUED_FULL_MARK n=%u k=%u mode=%s phase=%u old_completed=%zu field_completed=%zu old_generation=%u field_generation=%u same_anchor=%u fallback=%u reclaimed=1\n",
            n, MINYAR_RC_POLL_BUDGET, mode, phase_at_field, completed,
            completed_at_field, generation, generation_at_field,
            anchor_at_field == anchor_token, fallback);
    assert(fallback);
}
#endif
int main(int argc, char **argv) {
    assert(argc == 3);
    unsigned n = (unsigned)strtoul(argv[1], NULL, 10);
    assert(n >= 512 && n <= 2048);
    const char *mode = argv[2];
#ifdef MINYAR_BOUNDED_RC
    assert(MINYAR_RC_POLL_BUDGET <= 32);
    (void)detached; /* Reuse helpers without duplicating its completed matrix. */
    if (!strcmp(mode, "all") || !strcmp(mode, "registered-roots")) {
        negative(n, RC_CYCLE_ROOTS, "registered-descendant"); /* Existing oracle. */
        full_roots_registered_add(n);
    }
    if (!strcmp(mode, "all") || !strcmp(mode, "rescan"))
        full_zero(n, 1);
    if (!strcmp(mode, "all") || !strcmp(mode, "private-cycle"))
        full_zero_private_cycle(n);
    const char *queued_modes[] = { "queued-rescan", "queued-sweep", "queued-complete",
                                   "queued-restart", "queued-generation-aba", "queued-anchor" };
    for (size_t i = 0; i < sizeof(queued_modes) / sizeof(queued_modes[0]); i++)
        if (!strcmp(mode, "all") || !strcmp(mode, queued_modes[i]))
            full_zero_queued(n, queued_modes[i]);
    if (!strcmp(mode, "all") || !strcmp(mode, "positive"))
        full_zero(n, 0); /* Baseline locality RED must be last, after safety. */
#else
    (void)n; (void)mode;
    assert(!"full MARK retirement requires bounded cleanup");
#endif
    empty();
    return 0;
}
