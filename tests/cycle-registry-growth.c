/* Registered owner/callback growth, with an independent explicit-edge oracle. */
#define main additive_fixture_main
#define empty additive_empty
#include "cycle-additive.c"
#undef empty
#undef main
static void empty(void) {
    additive_empty();
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
    assert(!rc_cycle_known_head && !rc_cycle_known_tail && !rc_cycle_tail);
    assert(!rc_cycle_local_requested && !rc_cycle_temporary_anchor);
#endif
}

static void borrow_old(Graph g, unsigned calls) {
    minyar_rc_retain_traced(g.interior);
    for (unsigned j = 0; j < calls; j++) poll_one();
    rc_drop(g.interior);
    assert(rc_cycle_pending);
}
static void registered_work(unsigned n, int copied) {
    Graph g = graph();
    size_t before = rc_cycle_units, epochs = rc_cycle_epochs;
    for (unsigned i = 0; i < n; i++) {
        MinyarRecord *branch = minyar_record_new_traced(1);
        MinyarRecord *leaf = minyar_record_new_traced(1);
        minyar_record_set_traced(leaf, 0, 3000 + i);
        if (copied) {
            minyar_record_set_reference_traced(branch, 0, slot(leaf));
            minyar_rc_release(leaf);
            minyar_list_add_traced(g.list, slot(branch));
            minyar_rc_release(branch);
        } else {
            minyar_record_set_take_traced(branch, 0, slot(leaf));
            minyar_list_add_take_traced(g.list, slot(branch));
        }
        assert(rc_cycle_value(branch)->registered);
        borrow_old(g, 64);
        drain();
        assert(rc_object_count == 4u + 2u * (i + 1));
        assert(branch->values[0] == slot(leaf));
        assert(leaf->values[0] == 3000 + (long long)i);
    }
    size_t units = rc_cycle_units - before;
    fprintf(stderr, "registered owners n=%u copied=%d units=%zu epochs=%zu\n",
            n, copied, units, rc_cycle_epochs - epochs);
    assert(units <= 32u * n + 256u);
    minyar_rc_release(g.root);
    empty();
}
static MinyarRecord *captured_peer(MinyarRecord *core, unsigned id) {
    MinyarRecord *p = minyar_record_new_traced(2);
    MinyarRecord *env = minyar_record_new_traced(3);
    MinyarRecord *cb = minyar_record_new_traced(3);
    MinyarRecord *details = minyar_record_new_traced(16);
    minyar_record_set_traced(env, 0, minyar_callback_domain());
    minyar_record_set_reference_traced(env, 1, slot(core));
    minyar_record_set_reference_traced(env, 2, slot(p));
    minyar_record_set_traced(cb, 0, 0);
    minyar_record_set_reference_traced(cb, 1, slot(env));
    minyar_record_set_traced(cb, 2, minyar_callback_domain());
    minyar_record_set_reference_traced(details, 0, slot(core));
    minyar_record_set_reference_traced(details, 1, slot(cb));
    minyar_record_set_traced(details, 15, id);
    minyar_record_set_reference_traced(p, 0, slot(cb));
    minyar_record_set_reference_traced(p, 1, slot(details));
    minyar_rc_release(env);
    minyar_rc_release(cb);
    minyar_rc_release(details);
    return p;
}
static void check_peer(MinyarRecord *p, MinyarRecord *core, unsigned id) {
    MinyarRecord *cb = (MinyarRecord *)(uintptr_t)p->values[0];
    MinyarRecord *details = (MinyarRecord *)(uintptr_t)p->values[1];
    MinyarRecord *env = (MinyarRecord *)(uintptr_t)cb->values[1];
    minyar_callback_check(cb);
    minyar_callback_check_environment(env);
    assert(env->values[1] == slot(core) && env->values[2] == slot(p));
    assert(details->values[0] == slot(core));
    assert(details->values[1] == slot(cb) && details->values[15] == id);
}
static void callback_work(unsigned n, int streaming) {
    Graph g = graph();
    size_t before = rc_cycle_units, epochs = rc_cycle_epochs;
    for (unsigned i = 0; i < n; i++) {
        MinyarRecord *p = captured_peer(g.root, i);
        if (i & 1) {
            minyar_list_add_traced(g.list, slot(p));
            minyar_rc_release(p);
        } else {
            minyar_list_add_take_traced(g.list, slot(p));
        }
        borrow_old(g, streaming ? 1 : 64);
        if (!streaming || (i & 31) == 31) drain();
        assert(rc_object_count == 4u + 4u * (i + 1));
        check_peer(p, g.root, i);
        if (i) {
            MinyarRecord *old = (MinyarRecord *)(uintptr_t)g.list->values[1];
            check_peer(old, g.root, 0);
        }
    }
    drain();
    size_t units = rc_cycle_units - before;
    fprintf(stderr, "captured callback growth n=%u streaming=%d units=%zu epochs=%zu\n",
            n, streaming, units, rc_cycle_epochs - epochs);
    assert(units <= (streaming ? 256u : 128u) * n + 512u);
    for (unsigned i = 0; i < n; i++) {
        MinyarRecord *p = (MinyarRecord *)(uintptr_t)g.list->values[i + 1];
        check_peer(p, g.root, i);
    }
    /* Actual removal and capture replacement are deliberately outside the
     * additive performance interval and retain conservative collector work. */
    for (unsigned i = 0; i < n; i += 2)
        minyar_list_set_traced(g.list, i + 1, 0);
    drain();
    assert(rc_object_count == 4u + 4u * (n / 2));
    minyar_rc_release(g.root);
    empty();
}
static void conservative_mix(void) {
    Graph g = graph();
    size_t before = rc_cycle_units, epochs = rc_cycle_epochs;
    for (unsigned i = 0; i < 32; i++) {
        MinyarRecord *child = minyar_record_new_traced(2);
        minyar_record_set_reference_traced(child, 0, slot(child));
        minyar_record_set_reference_traced(child, 1, slot(g.root));
        minyar_list_add_take_traced(g.list, slot(child));
        borrow_old(g, 64);
        drain();
        assert(rc_object_count == 5u + i);
    }
    fprintf(stderr, "fresh self cycles n=32 units=%zu epochs=%zu\n",
            rc_cycle_units - before, rc_cycle_epochs - epochs);
    assert(rc_cycle_epochs > epochs);
    for (unsigned i = 0; i < 32; i += 2)
        minyar_list_set_traced(g.list, i + 1, 0);
    drain();
    assert(rc_object_count == 20);
    minyar_rc_release(g.root);
    empty();
}

#ifdef MINYAR_CYCLE_LOCAL_PROOFS
static size_t registry_list(RcCycle *head, RcCycle *tail) {
    size_t count = 0; RcCycle *previous = NULL;
    for (RcCycle *c = head; c; c = c->next) {
        assert(++count <= rc_object_count);
        assert(c->registered && c->previous == previous);
        previous = c;
    }
    assert(previous == tail);
    return count;
}
static size_t check_registry(void) {
    size_t unknown = registry_list(rc_cycle_head, rc_cycle_tail);
    size_t known = registry_list(rc_cycle_known_head, rc_cycle_known_tail);
    for (RcCycle *a = rc_cycle_head; a; a = a->next)
        for (RcCycle *b = rc_cycle_known_head; b; b = b->next) assert(a != b);
    return unknown + known;
}
static Graph local_batch(void) {
    Graph g = graph();
    MinyarRecord *branches[96];
    for (unsigned i = 0; i < 96; i++) {
        branches[i] = minyar_record_new_traced(1);
        MinyarRecord *leaf = minyar_record_new_traced(1);
        minyar_record_set_traced(leaf, 0, 5000 + i);
        minyar_record_set_take_traced(branches[i], 0, slot(leaf));
    }
    list_reserve(g.list, 128);
    /* Exact take-store ordering without its service point, so each phase is
     * deliberately interruptible even for budget1024 and eager profiles. */
    for (unsigned i = 0; i < 96; i++) {
        rc_cycle_edge_insert(g.list, branches[i]);
        g.list->values[g.list->length++] = slot(branches[i]);
        rc_cycle_commit_insert(g.list, branches[i]);
    }
    assert(rc_cycle_proof_valid && rc_cycle_local_requested);
    assert(check_registry() == 99);
    return g;
}
static void local_phase(unsigned target) {
    size_t units = 0;
    while (rc_cycle_phase != target) {
        assert(rc_cycle_pending && ++units < 100000);
        rc_cycle_unit();
    }
    assert(rc_cycle_local_job && rc_cycle_proof_valid && !rc_cycle_proof_build);
}
static void local_cancellations(void) {
    for (unsigned phase = RC_CYCLE_ROOTS; phase <= RC_CYCLE_SWEEP; phase++) {
        for (unsigned action = 0; action < 3; action++) {
            Graph g = local_batch();
            local_phase(phase);
            if (phase == RC_CYCLE_SWEEP) {
                size_t before = registry_list(rc_cycle_known_head, rc_cycle_known_tail);
                while (registry_list(rc_cycle_known_head, rc_cycle_known_tail) == before)
                    rc_cycle_unit();
                assert(rc_cycle_phase == RC_CYCLE_SWEEP && rc_cycle_local_job);
            }
            check_registry();
            if (action == 0) {
                rc_drop(g.root); /* Sole anchor release cancels partial promotion. */
                assert(!rc_cycle_proof_anchor && !rc_cycle_proof_valid);
#ifndef MINYAR_BOUNDED_RC
                minyar_rc_release(NULL);
#endif
                empty();
            } else if (action == 1) {
                minyar_list_set_traced(g.list, 17, 0);
                drain();
                fprintf(stderr,"cancel phase=%u action=%u objects=%zu\n",phase,action,rc_object_count);
                assert(rc_object_count == 194);
                check_registry();
                minyar_rc_release(g.root); empty();
            } else {
                /* Take sole root into a rooted interior owner: incoming must
                 * invalidate before the publication or any collector unit. */
                rc_cycle_edge_insert(g.list, g.root);
                assert(!rc_cycle_anchor_held() && !rc_cycle_proof_valid);
                g.list->values[g.list->length++] = slot(g.root);
                rc_cycle_commit_insert(g.list, g.root);
                empty();
            }
            assert(!rc_cycle_known_head && !rc_cycle_known_tail && !rc_cycle_tail);
        }
    }
}



static void controlled_unit(void) {
    if (!rc_cycle_pending) return;
    size_t units = rc_cycle_units;
    rc_cycle_unit();
    assert(rc_cycle_units == units + 1);
}
static void controlled_reference(MinyarRecord *record, unsigned field, void *child) {
    unsigned char *map = (unsigned char *)(record->values + record->length);
    assert(!map[field] && !record->values[field]);
    minyar_rc_retain_traced(child);
    map[field] = 1;
    rc_cycle_edge_insert(record, child);
    record->values[field] = slot(child);
    rc_cycle_commit_insert(record, child);
    controlled_unit();
}
static void controlled_callbacks(void) {
    Graph g = graph();
    for (unsigned i = 0; i < 32; i++) {
        MinyarRecord *p = minyar_record_new_traced(2);
        MinyarRecord *env = minyar_record_new_traced(3);
        MinyarRecord *cb = minyar_record_new_traced(3);
        MinyarRecord *details = minyar_record_new_traced(16);
        minyar_record_set_traced(env, 0, minyar_callback_domain());
        controlled_reference(env, 1, g.root);
        controlled_reference(env, 2, p);
        controlled_reference(cb, 1, env);
        minyar_record_set_traced(cb, 2, minyar_callback_domain());
        controlled_reference(details, 0, g.root);
        controlled_reference(details, 1, cb);
        minyar_record_set_traced(details, 15, i);
        controlled_reference(p, 0, cb);
        controlled_reference(p, 1, details);
        rc_drop(env); controlled_unit();
        rc_drop(cb); controlled_unit();
        rc_drop(details); controlled_unit();
        if (g.list->length == g.list->capacity) list_grow(g.list);
        rc_cycle_edge_insert(g.list, p);
        g.list->values[g.list->length++] = slot(p);
        rc_cycle_commit_insert(g.list, p);
        controlled_unit();
        minyar_rc_retain_traced(g.interior);
        for (unsigned j = 0; j < 64; j++) controlled_unit();
        rc_drop(g.interior);
        drain();
        assert(rc_object_count == 4u + 4u * (i + 1));
        check_peer(p, g.root, i);
    }
    minyar_rc_release(g.root); empty();
}

static void active_publication(unsigned offset, int copied, int repeated) {
    Graph g = graph();
    if (repeated) list_reserve(g.list, 16);
    MinyarRecord *c = minyar_record_new_traced(1);
    MinyarRecord *d = minyar_record_new_traced(1);
    MinyarRecord *left = minyar_record_new_traced(1);
    MinyarRecord *right = minyar_record_new_traced(1);
    MinyarRecord *p = minyar_record_new_traced(8);
    minyar_record_set_traced(left, 0, 8101);
    minyar_record_set_traced(right, 0, 8102);
    minyar_record_set_take_traced(c, 0, slot(left));
    minyar_record_set_take_traced(d, 0, slot(right));
    minyar_record_set_reference_traced(p, 0, slot(c));
    minyar_record_set_reference_traced(p, 7, slot(d));
    rc_drop(c); rc_drop(d);
    rc_cycle_request_local();
    local_phase(RC_CYCLE_MARK);
    size_t turns = 0;
    while (rc_cycle_active != rc_cycle_value(p) || rc_cycle_index != offset) {
        assert(++turns < 100000); rc_cycle_unit();
    }
    assert(rc_cycle_limit == 8);
    assert(!rc_cycle_proven(rc_cycle_value(p)) && !rc_cycle_proven(rc_cycle_value(c)));
    if (repeated) {
        rc_cycle_edge_insert(g.list, p);
        g.list->values[g.list->length++] = slot(p);
        rc_cycle_commit_insert(g.list, p);
        assert(rc_cycle_index == 0 && rc_cycle_limit == 8);
        while (rc_cycle_active == rc_cycle_value(p)) {
            size_t previous = rc_cycle_index, units = rc_cycle_units;
            minyar_rc_retain_traced(p);
            rc_cycle_edge_insert(g.list, p);
            g.list->values[g.list->length++] = slot(p);
            rc_cycle_commit_insert(g.list, p);
            assert(rc_cycle_index == previous && rc_cycle_limit == 8);
            rc_cycle_unit();
            assert(rc_cycle_units == units + 1);
        }
    } else if (copied) {
        minyar_list_add_traced(g.list, slot(p));
        minyar_rc_release(p);
    } else
        minyar_list_add_take_traced(g.list, slot(p));
    assert(rc_cycle_proven(rc_cycle_value(p)));
    drain();
    assert(rc_object_count == 9);
    assert(p->values[0] == slot(c) && p->values[7] == slot(d));
    assert(c->values[0] == slot(left) && left->values[0] == 8101);
    assert(d->values[0] == slot(right) && right->values[0] == 8102);
    minyar_rc_release(g.root); empty();
}

static void temporary_contracts(void) {
    for (unsigned action = 0; action < 4; action++) {
        Graph g = graph();
        MinyarRecord *p = captured_peer(g.root, action);
        drain();
        assert(rc_object_count == 8);
        assert(rc_cycle_temporary_valid && rc_cycle_temporary_held());
        assert(rc_cycle_temporary_anchor == rc_cycle_value(p));
        assert(!rc_cycle_proven(rc_cycle_value(p)));
        assert(rc_cycle_proof_anchor == rc_cycle_value(g.root));
        size_t units = rc_cycle_units;
        rc_cycle_request_local(); drain();
        assert(rc_cycle_units - units == 1);
        if (action == 0) {
            /* Opposite temporary tags must not alias a newly started full
             * proof before this unknown node's ROOTS unit has cleared them. */
            rc_cycle_request(); rc_cycle_unit();
            assert(rc_cycle_phase == RC_CYCLE_ROOTS && rc_cycle_proof_build);
            assert(!rc_cycle_proven(rc_cycle_value(p)));
            drain();
            minyar_rc_release(p);
            drain();
            assert(rc_object_count == 4);
        } else if (action == 1) {
            MinyarRecord *owner = minyar_record_new_traced(1);
            minyar_record_set_take_traced(owner, 0, slot(p));
            assert(!rc_cycle_temporary_valid && !rc_cycle_temporary_build);
            minyar_rc_release(owner); drain();
            assert(rc_object_count == 4);
        } else if (action == 2) {
            /* Copying preserves p's external owner; future release still
             * must not retain a stale temporary certificate after reuse. */
            MinyarRecord *owner = minyar_record_new_traced(1);
            minyar_record_set_reference_traced(owner, 0, slot(p));
            minyar_rc_release(owner); drain();
            assert(rc_object_count == 8);
            minyar_rc_release(p); drain();
            assert(rc_object_count == 4);
        } else {
            /* Two unknown roots cannot both inherit the first root witness. */
            MinyarRecord *second = captured_peer(g.root, 10);
            drain();
            assert(rc_object_count == 12);
            assert(!rc_cycle_temporary_valid);
            minyar_rc_release(p); drain();
            assert(rc_object_count == 8);
            check_peer(second, g.root, 10);
            minyar_rc_release(second); drain();
            assert(rc_object_count == 4);
        }
        minyar_rc_release(g.root); empty();
        assert(!rc_cycle_temporary_anchor);
    }
    for (unsigned phase = RC_CYCLE_ROOTS; phase <= RC_CYCLE_SWEEP; phase++) {
        MinyarRecord *outside = minyar_record_new_traced(1);
        Graph g = local_batch();
        local_phase(phase);
        minyar_rc_retain_traced(outside);
        rc_cycle_edge_insert(outside, outside);
        assert(!rc_cycle_proof_valid && rc_cycle_rescan);
        outside->values[0] = slot(outside);
        ((unsigned char *)(outside->values + outside->length))[0] = 1;
        rc_cycle_commit_insert(outside, outside);
        rc_drop(outside);
        /* A forced full request survives cancellation of the local job. */
        while (rc_cycle_local_job) rc_cycle_unit();
        assert(rc_cycle_phase == RC_CYCLE_IDLE && rc_cycle_pending);
        unsigned generation = rc_cycle_generation;
        rc_cycle_unit();
        assert(rc_cycle_phase == RC_CYCLE_ROOTS && !rc_cycle_local_job &&
               rc_cycle_proof_build && rc_cycle_generation != generation);
#ifndef MINYAR_BOUNDED_RC
        minyar_rc_release(NULL);
#endif
        drain();
        assert(rc_object_count == 196);
        check_registry();
        minyar_rc_release(g.root); empty();
    }
}

static void stale_jobs_and_reuse(void) {
    for (unsigned turn = 0; turn < 32; turn++) {
        Graph g = local_batch();
        local_phase(RC_CYCLE_ROOTS);
        /* Unregister captured tail and a new prefix, then re-register one
         * live allocation. This stresses both namespace bits and finite tail. */
        RcCycle *tail = rc_cycle_tail;
        RcObject *object = rc_cycle_object(tail);
        rc_cycle_unregister(object);
        assert(!tail->registered);
        rc_cycle_register(tail);
        assert(tail->registered && tail == rc_cycle_head);
        rc_cycle_request(); /* Mandatory full request survives local cancel. */
        drain();
        assert(rc_object_count == 196);
        check_registry();
        for (unsigned flip = 0; flip < 3; flip++) { rc_cycle_request(); drain(); }
        MinyarRecord *lost = minyar_record_new_traced(2);
        minyar_record_set_reference_traced(lost, 0, slot(lost));
        minyar_record_set_reference_traced(lost, 1, slot(g.root));
        minyar_rc_release(lost);
        drain();
        assert(rc_object_count == 196);
        minyar_rc_release(g.root); empty();
        assert(!rc_cycle_local_requested);
    }
}
#endif

int main(int argc, char **argv) {
    unsigned n = argc > 1 ? (unsigned)strtoul(argv[1], NULL, 10) : 256;
    const char *mode = argc > 2 ? argv[2] : "all";
    assert(n == 32 || n == 256 || n == 2048);
    if (!strcmp(mode, "registered") || !strcmp(mode, "all")) {
        registered_work(n, 0);
        registered_work(n, 1);
    }
    if (!strcmp(mode, "callbacks") || !strcmp(mode, "all")) callback_work(n, 0);
    if (!strcmp(mode, "streaming") || !strcmp(mode, "all")) callback_work(n, 1);
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
    if (!strcmp(mode, "active") || !strcmp(mode, "all")) {
        controlled_callbacks();
        active_publication(1, 0, 0);
        active_publication(1, 1, 0);
        active_publication(7, 0, 0);
        active_publication(7, 1, 0);
        active_publication(7, 0, 1);
    }
#endif
    if (!strcmp(mode, "safety") || !strcmp(mode, "all")) {
        char *old[] = {(char *)"additive", (char *)"32", NULL};
        additive_fixture_main(2, old);
        conservative_mix();
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
        local_cancellations();
        stale_jobs_and_reuse();
        temporary_contracts();
#endif
    }
    printf("registered graph growth n=%u mode=%s objects=0 bytes=0\n", n, mode);
    return 0;
}
