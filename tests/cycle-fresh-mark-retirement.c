/* Real fresh-owner retirement during a finite local MARK pass. */
#define MINYAR_LEAF_CHURN_HELPERS 1
#include "cycle-leaf-churn.c"

#ifdef MINYAR_BOUNDED_RC
static void fresh_mark_phase(void) {
    size_t steps = 0;
    while (rc_cycle_phase != RC_CYCLE_MARK) {
        assert(++steps < 4000000 && rc_cycle_pending);
        rc_cycle_unit();
    }
}
static MinyarRecord *fresh_carrier(unsigned fields, unsigned value) {
    /* Its captured fields supply real MARK work for each public store's poll.
     * The measured retirement starts after those stores; no metadata is stamped. */
    MinyarRecord *carrier = minyar_record_new_traced(fields * MINYAR_RC_POLL_BUDGET);
    MinyarRecord *leaf = minyar_record_new_traced(1);
    minyar_record_set_traced(leaf, 0, value);
    minyar_record_set_take_traced(carrier, 0, slot(leaf));
    return carrier;
}
static void fresh_mark_contract(Churn c, MinyarRecord *owner) {
    RcCycle *cycle = rc_cycle_value(owner);
    assert(rc_cycle_phase == RC_CYCLE_MARK && rc_cycle_local_job);
    assert(!rc_cycle_inside && rc_cycle_proof_valid && !rc_cycle_proof_build);
    assert(rc_cycle_anchor_held() && !rc_cycle_proof_anchor->pinned);
    assert(rc_cycle_proof_anchor == rc_cycle_value(c.g.root) && !rc_cycle_rescan);
    assert(cycle->registered && cycle->marked == 3 && cycle->gray_next == 4);
    assert(cycle->incoming == 0 && !cycle->pinned && !cycle->cleared);
    assert(!rc_cycle_proven(cycle) && cycle != rc_cycle_proof_anchor);
    assert(cycle != rc_cycle_proof_retry && cycle != rc_cycle_temporary_anchor);
    assert(((RcObject *)owner - 1)->ownership == (8u | RC_TRACED));
}
static void fresh_payload(Churn c, MinyarRecord *carrier, unsigned value) {
    MinyarRecord *leaf = (MinyarRecord *)(uintptr_t)carrier->values[0];
    assert(leaf->values[0] == value);
    assert(c.g.interior->values[1] == 19);
    assert(c.callback->values[0] == 101 && c.callback->values[1] == 202);
    assert(c.callback->values[2] == slot(c.g.root));
}
static void fresh_mark_retirement(unsigned n) {
    const unsigned rounds = 8;
    size_t work = 0, growth = 0;
    unsigned preserved = 0;
    for (unsigned i = 0; i < rounds; i++) {
        Churn c = churn_graph(n);
        MinyarRecord *carrier = fresh_carrier(1, 80000 + i);
        MinyarRecord *owner = minyar_record_new_traced(1);
        MinyarRecord *leaf = minyar_record_new_traced(1);
        minyar_record_set_traced(leaf, 0, 81000 + i);
        assert(!rc_cycle_value(owner)->registered);
        rc_cycle_request_local();
        fresh_mark_phase();
        assert(rc_cycle_local_job && rc_cycle_proof_valid && !rc_cycle_proof_build);
        minyar_record_set_take_traced(owner, 0, slot(leaf));
        fresh_mark_contract(c, owner);
        RcCycle *cycle = rc_cycle_value(owner);
        assert(owner->values[0] == slot(leaf) && leaf->values[0] == 81000 + (long long)i);
        size_t units = rc_cycle_units, epochs = rc_cycle_epochs;
        rc_drop(owner); /* Genuine last-owner decrement, including gray deferral. */
        assert(!cycle->registered && !cycle->pinned && cycle->incoming == 0);
        preserved += !!rc_cycle_proof_valid;
        drain();
        work += rc_cycle_units - units;
        growth += rc_cycle_epochs - epochs;
        assert(rc_object_count == 9u + 2u * n); /* Both dead objects are gone. */
        fresh_payload(c, carrier, 80000 + i);
        minyar_rc_release(carrier);
        drain();
        churn_check(c, n, 0);
        minyar_rc_release(c.g.root);
        empty(); /* Actual root drop reclaims every object before the bound. */
    }
    fprintf(stderr, "FRESH_MARK n=%u k=%u rounds=%u real_zero=%u units=%zu epochs=%zu preserved=%u\n",
            n, MINYAR_RC_POLL_BUDGET, rounds, rounds, work, growth, preserved);
    assert(work <= 16u * rounds + 64u);
    assert(preserved == rounds);
}
static void fresh_queued(unsigned n, unsigned transfer) {
    Churn c = churn_graph(n);
    MinyarRecord *carrier = fresh_carrier(2, 82000);
    MinyarRecord *owner = minyar_record_new_traced(2);
    MinyarRecord *leaf = minyar_record_new_traced(1);
    MinyarRecord *receiver = transfer ? minyar_record_new_traced(1) : NULL;
    minyar_record_set_traced(leaf, 0, 83000);
    rc_cycle_request_local();
    fresh_mark_phase();
    minyar_record_set_take_traced(owner, 0, slot(leaf));
    minyar_record_set_reference_traced(owner, 1, slot(c.g.root));
    fresh_mark_contract(c, owner);
    RcCycle *cycle = rc_cycle_value(owner);
    assert(leaf->values[0] == 83000 && owner->values[1] == slot(c.g.root));
    rc_drop(owner);
    assert(!cycle->registered && !cycle->pinned && cycle->incoming == 0);
    assert(cycle->gray_next == (RC_CYCLE_PRIVATE_DEAD | RC_CYCLE_FRESH_MARK_DEAD));
    assert(rc_cycle_proof_valid && !rc_cycle_proof_build);
    rc_bounded_object_unit(); /* First field qualifies under the issued marker. */
    assert(rc_bounded_active == (RcObject *)owner - 1 && rc_bounded_cursor == 1);
    assert(rc_cycle_proof_valid);
    if (transfer) {
        /* Exact public take-store barriers and publication, before its poll,
         * keep the zero-owner cursor parked while consuming the root's actual
         * last external reference. This changes ownership, not metadata. */
        unsigned char *map = (unsigned char *)(receiver->values + receiver->length);
        map[0] = 1;
        rc_cycle_edge_insert(receiver, c.g.root);
        receiver->values[0] = slot(c.g.root);
        rc_cycle_commit_insert(receiver, c.g.root);
        assert(!rc_cycle_proof_valid && !rc_cycle_anchor_held());
    } else {
        rc_cycle_request();
    }
    /* Both real changes schedule a full rebuild. Starting that job gives the
     * remaining-field fallback an independent observable transition: the
     * building proof must be canceled, not merely remain already invalid. */
    size_t steps = 0;
    while (!(rc_cycle_proof_build && !rc_cycle_local_job &&
             rc_cycle_phase == RC_CYCLE_ROOTS)) {
        assert(++steps < 4000000 && rc_cycle_pending);
        rc_cycle_unit(); /* Object cleanup remains parked throughout. */
    }
    assert(rc_cycle_proof_build && !rc_cycle_local_job);
    size_t incoming = rc_cycle_value(c.g.root)->incoming;
    rc_bounded_old_object_unit(); /* Issued40 must recheck its remaining field. */
    assert(rc_bounded_active == (RcObject *)owner - 1 && rc_bounded_cursor == 2);
    assert(rc_cycle_value(c.g.root)->incoming + 1 == incoming);
    assert(!rc_cycle_proof_valid && !rc_cycle_proof_build);
    assert(rc_cycle_rescan); /* Ordinary edge removal conservatively cancels. */
    drain();
    assert(rc_object_count == 9u + 2u * n + transfer);
    fresh_payload(c, carrier, 82000);
    if (transfer) {
        assert(receiver->values[0] == slot(c.g.root));
        minyar_rc_retain_traced((void *)(uintptr_t)receiver->values[0]);
        minyar_rc_release(receiver); /* Root reacquired before receiver dies. */
    }
    minyar_rc_release(carrier);
    drain();
    churn_check(c, n, 0);
    minyar_rc_release(c.g.root);
    empty();
    fprintf(stderr, "QUEUED_FRESH_MARK n=%u k=%u transfer=%u fallback=1 reclaimed=1\n",
            n, MINYAR_RC_POLL_BUDGET, transfer);
}
#endif
int main(int argc, char **argv) {
    assert(argc == 2 || argc == 3);
    unsigned n = (unsigned)strtoul(argv[1], NULL, 10);
    assert(n >= 32 && n <= 2048);
#ifdef MINYAR_BOUNDED_RC
    const char *mode = argc == 3 ? argv[2] : "positive";
    if (!strcmp(mode, "all") || !strcmp(mode, "positive"))
        fresh_mark_retirement(n);
    if (!strcmp(mode, "all") || !strcmp(mode, "queued-full"))
        fresh_queued(n, 0);
    if (!strcmp(mode, "all") || !strcmp(mode, "queued-anchor"))
        fresh_queued(n, 1);
#else
    (void)n;
    assert(!"fresh MARK retirement requires bounded cleanup");
#endif
    empty();
    return 0;
}
