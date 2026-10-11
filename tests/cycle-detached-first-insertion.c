/* Source-only proposal: no collector state writes and no split store barriers.
 * Compile against a frozen maintained engine with -I tests; construction,
 * insertion, ownership changes, and service use the public runtime APIs. */
#define MINYAR_LEAF_CHURN_HELPERS 1
#include "cycle-leaf-churn.c"

#ifdef MINYAR_BOUNDED_RC
static size_t references(void *value) {
    return ((RcObject *)value - 1)->ownership >> 3;
}
static void core_payloads(Churn c, unsigned n, unsigned extra, unsigned suffix) {
    if (!extra && !suffix)
        churn_check(c, n, 0);
    assert(rc_object_count == 7u + 2u * n + extra);
    assert(c.g.list->length == n + 3u + suffix);
    assert(c.g.interior->values[1] == 19);
    assert(c.callback->values[0] == 101 && c.callback->values[1] == 202);
    assert(c.callback->values[2] == slot(c.g.root));
    assert(churn_buffer(c)->length == 0);
    for (unsigned i = 0; i < n; i++) {
        MinyarRecord *branch = (MinyarRecord *)(uintptr_t)c.g.list->values[i + 1];
        MinyarRecord *leaf = (MinyarRecord *)(uintptr_t)branch->values[0];
        assert(leaf->values[0] == 10000 + (long long)i);
    }
}
static void full_phase(Churn c, unsigned phase) {
    /* A real same-value replacement cancels the old certificate. A normal
     * borrow/drop of an internally owned Core field then requests full work;
     * neither operation changes a permanent owning edge or external root. */
    size_t epochs = rc_cycle_epochs;
    minyar_record_replace_traced(c.callback, 2, slot(c.g.root), 0);
    minyar_rc_retain_traced(c.g.interior);
    minyar_rc_release(c.g.interior);
    size_t turns = 0;
    while (rc_cycle_phase != phase) {
        assert(++turns < 4000000 && rc_cycle_pending);
        minyar_rc_poll(1);
    }
    assert(rc_cycle_epochs == epochs + 1);
    assert(!rc_cycle_local_job && rc_cycle_proof_build && !rc_cycle_rescan);
    assert(!rc_cycle_proof_valid); /* No completed proof may be manufactured. */
}
static MinyarRecord *empty_owner(void) {
    MinyarRecord *owner = minyar_record_new_traced(2);
    minyar_record_set_traced(owner, 1, 61003);
    return owner;
}
static MinyarRecord *scalar_leaf(void) {
    MinyarRecord *leaf = minyar_record_new_traced(1);
    minyar_record_set_traced(leaf, 0, 61001);
    return leaf;
}
static void active(unsigned phase) {
    assert(rc_cycle_phase == phase && !rc_cycle_local_job);
    assert(rc_cycle_proof_build && !rc_cycle_rescan && !rc_cycle_proof_valid);
}
static void detached(unsigned n, unsigned phase, unsigned copied) {
    Churn c = churn_graph(n);
    size_t epochs = rc_cycle_epochs, completed = rc_cycle_completed;
    full_phase(c, phase);
    /* Both real outside owners are constructed while this full job runs. */
    MinyarRecord *owner = empty_owner(), *leaf = scalar_leaf();
    RcCycle *source = rc_cycle_value(owner), *child = rc_cycle_value(leaf);
    active(phase);
    assert(!source->registered && !child->registered);
    assert(!source->incoming && !child->incoming);
    assert(!source->gray_next && !child->gray_next);
    assert(!source->pinned && !child->pinned && !source->cleared && !child->cleared);
    assert(references(owner) == 1 && references(leaf) == 1);
    unsigned generation = rc_cycle_generation;
    if (copied)
        minyar_record_set_reference_traced(owner, 0, slot(leaf));
    else
        minyar_record_set_take_traced(owner, 0, slot(leaf));
    /* Capture locality facts, but do not assert them before real safety and
     * root-drop checks. An old conservative rebuild must finish those checks. */
    unsigned preserved = rc_cycle_proof_build && !rc_cycle_rescan && !rc_cycle_local_job;
    unsigned falsely_certified = rc_cycle_proof_valid || (source->gray_next & 1) ||
                                 (child->gray_next & 1);
    unsigned same_generation = rc_cycle_generation == generation;
    assert(owner->values[0] == slot(leaf) && owner->values[1] == 61003);
    assert(leaf->values[0] == 61001);
    assert(source->registered && source->incoming == 0 && source->marked == 3);
    assert(!child->registered && child->incoming == 1);
    assert(references(owner) == 1 && references(leaf) == 1u + copied);
    drain();
    size_t full_epochs = rc_cycle_epochs - epochs;
    size_t full_completed = rc_cycle_completed - completed;
    core_payloads(c, n, 2, 0);
    assert(owner->values[0] == slot(leaf) && leaf->values[0] == 61001);
    minyar_rc_release(owner);
    drain();
    if (copied) {
        assert(leaf->values[0] == 61001 && references(leaf) == 1);
        assert(rc_cycle_value(leaf)->incoming == 0);
        minyar_rc_release(leaf);
        drain();
    }
    core_payloads(c, n, 0, 0);
    minyar_rc_release(c.g.root);
    empty(); /* Object/byte/registry exact zero before the locality oracle. */
    fprintf(stderr, "DETACHED_FIRST n=%u phase=%u copied=%u preserved=%u epochs=%zu completed=%zu generation=%u false_proof=%u reclaimed=1\n",
            n, phase, copied, preserved, full_epochs, full_completed,
            same_generation, falsely_certified);
    assert(preserved && same_generation && !falsely_certified);
    assert(full_epochs == 1 && full_completed == 1);
}
static void negative(unsigned n, unsigned phase, const char *mode) {
    Churn c = churn_graph(n);
    MinyarRecord *owner = NULL, *holder = NULL, *branch = NULL;
    unsigned exposed = !strcmp(mode, "exposed");
    unsigned internal = !strcmp(mode, "internal") || exposed;
    unsigned registered = !strcmp(mode, "registered-descendant");
    unsigned self = !strcmp(mode, "self-cycle");
    unsigned anchor = !strcmp(mode, "anchor-take");
    assert(internal || registered || self || anchor);
    if (internal) {
        owner = empty_owner();
        if (exposed) {
            minyar_list_add_take_traced(c.g.list, slot(owner));
            drain();
            assert(rc_cycle_value(owner)->gray_next & 4);
        } else {
            holder = minyar_record_new_traced(1);
            minyar_record_set_take_traced(holder, 0, slot(owner));
            assert(!(rc_cycle_value(owner)->gray_next & 4));
        }
        minyar_rc_retain_traced(owner); /* Genuine temporary receiver owner. */
        assert(!rc_cycle_value(owner)->registered && rc_cycle_value(owner)->incoming == 1);
    }
    if (registered) {
        branch = churn_branch(61001);
        assert(rc_cycle_value(branch)->registered);
    }
    full_phase(c, phase);
    if (!owner)
        owner = empty_owner();
    MinyarRecord *leaf = !registered && !self && !anchor ? scalar_leaf() : NULL;
    active(phase);
    if (internal)
        assert(rc_cycle_value(owner)->incoming == 1 && references(owner) == 2);
    else
        assert(!rc_cycle_value(owner)->incoming && references(owner) == 1);
    if (exposed)
        assert(rc_cycle_value(owner)->gray_next & 4);
    if (anchor) {
        assert(phase >= RC_CYCLE_MARK && rc_cycle_anchor_held());
        assert(rc_cycle_proof_anchor == rc_cycle_value(c.g.root));
        minyar_record_set_take_traced(owner, 0, slot(c.g.root));
    } else {
        void *value = self ? (void *)owner : registered ? (void *)branch : (void *)leaf;
        minyar_record_set_reference_traced(owner, 0, slot(value));
    }
    unsigned canceled = !rc_cycle_proof_build && rc_cycle_rescan;
    if (anchor)
        assert(references(c.g.root) == rc_cycle_value(c.g.root)->incoming);
    drain();
    unsigned extra = internal ? (exposed ? 2 : 3) : registered ? 3 : 1;
    core_payloads(c, n, extra, exposed);
    assert(owner->values[1] == 61003);
    if (leaf) {
        assert(owner->values[0] == slot(leaf) && leaf->values[0] == 61001);
        assert(references(leaf) == 2 && rc_cycle_value(leaf)->incoming == 1);
        minyar_rc_release(leaf);
    } else if (registered) {
        MinyarRecord *descendant = (MinyarRecord *)(uintptr_t)branch->values[0];
        assert(owner->values[0] == slot(branch) && descendant->values[0] == 61001);
        minyar_rc_release(branch);
    } else if (self) {
        assert(owner->values[0] == slot(owner));
        assert(references(owner) == 2 && rc_cycle_value(owner)->incoming == 1);
    } else {
        assert(owner->values[0] == slot(c.g.root));
    }
    minyar_rc_release(owner); /* Temporary or sole real outside owner. */
    if (holder)
        minyar_rc_release(holder);
    if (!anchor)
        minyar_rc_release(c.g.root);
    empty(); /* Includes self-cycle and consumed-anchor graph reclamation. */
    fprintf(stderr, "DETACHED_NEGATIVE n=%u phase=%u mode=%s canceled=%u reclaimed=1\n",
            n, phase, mode, canceled);
    assert(canceled);
}
#endif
int main(int argc, char **argv) {
    assert(argc == 5);
    unsigned n = (unsigned)strtoul(argv[1], NULL, 10);
    unsigned phase = (unsigned)strtoul(argv[3], NULL, 10);
    unsigned copied = (unsigned)strtoul(argv[4], NULL, 10);
    assert(n >= 512 && n <= 2048 && phase >= RC_CYCLE_ROOTS && phase <= RC_CYCLE_SWEEP);
    assert(copied <= 1);
#ifdef MINYAR_BOUNDED_RC
    assert(MINYAR_RC_POLL_BUDGET <= 32); /* k1/k32 are existing profile values. */
    if (!strcmp(argv[2], "detached"))
        detached(n, phase, copied);
    else
        negative(n, phase, argv[2]);
#else
    assert(!"full-build insertion fixture requires a bounded profile");
#endif
    return 0;
}
