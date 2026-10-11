/* Independent rooted-graph growth and ownership-transfer contracts. */
#define MINYAR_RC_TESTING 1
#define MINYAR_INTEGER_TEXT_CACHE_LIMIT 0
#include "../build/managed-graphs-engine.c"
#include <assert.h>

static long long slot(void *p) { return (long long)(uintptr_t)p; }
static int pending(void) {
#ifdef MINYAR_BOUNDED_RC
    return rc_pending_count != 0;
#else
    return rc_cycle_pending != 0;
#endif
}
static void poll_one(void) {
    size_t before = rc_cycle_units;
#ifdef MINYAR_BOUNDED_RC
    size_t work = minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
    assert(work <= MINYAR_RC_POLL_BUDGET);
    assert(rc_cycle_units - before <= work);
#else
    minyar_callbackruntime_service();
    assert(rc_cycle_units - before <= 32);
#endif
}
static void drain(void) {
    size_t turns = 0;
    while (pending()) { assert(++turns < 4000000); poll_one(); }
}
static void empty(void) {
    drain();
    assert(!rc_object_count && !rc_bytes && !rc_cycle_head && !rc_cycle_pending);
    assert(!rc_cycle_proof_anchor && !rc_cycle_proof_retry);
}
typedef struct { MinyarRecord *root, *interior; MinyarList *list; } Graph;
/* Acyclic: root -> list -> interior -> scalar leaf. Only root has an external
 * owner after setup. The oracle is these explicit owning edges, not marks. */
static Graph graph(void) {
    size_t existing = rc_object_count;
    Graph g;
    g.root = minyar_record_new_traced(1);
    g.list = minyar_list_new_traced();
    minyar_list_references(g.list);
    g.interior = minyar_record_new_traced(2);
    MinyarRecord *leaf = minyar_record_new_traced(1);
    minyar_record_set_traced(leaf, 0, 71);
    minyar_record_set_reference_traced(g.interior, 0, slot(leaf));
    minyar_record_set_traced(g.interior, 1, 19);
    minyar_record_set_reference_traced(g.root, 0, slot(g.list));
    minyar_list_add_take_traced(g.list, slot(g.interior));
    minyar_rc_release(leaf);
    minyar_rc_release(g.list);
    rc_cycle_request();
    drain();
    assert(rc_object_count == existing + 4 && rc_cycle_proof_valid);
    if (!existing) {
        assert(rc_cycle_proof_anchor == rc_cycle_value(g.root));
        assert(rc_cycle_proven(rc_cycle_value(g.interior)));
    }
    return g;
}
static void growth(unsigned n, int retained) {
    Graph g = graph();
    size_t before = rc_cycle_units, epochs = rc_cycle_epochs;
    for (unsigned i = 0; i < n; i++) {
        MinyarRecord *leaf = minyar_record_new_traced(1);
        minyar_record_set_traced(leaf, 0, 1000 + i);
        if (retained) {
            minyar_list_add_traced(g.list, slot(leaf));
            minyar_rc_release(leaf);
        } else {
            minyar_list_add_take_traced(g.list, slot(leaf));
        }
        /* Generated calls poll with a borrowed managed argument still owned. */
        minyar_rc_retain_traced(g.interior);
        for (unsigned call = 0; call < 64; call++) poll_one();
        rc_drop(g.interior);
        assert(rc_cycle_pending);
        drain();
        assert(rc_object_count == 4u + i + 1);
        assert(g.interior->values[1] == 19);
        MinyarRecord *stored = (MinyarRecord *)(uintptr_t)g.list->values[i + 1];
        assert(stored->values[0] == 1000 + (long long)i);
    }
    size_t units = rc_cycle_units - before;
    fprintf(stderr, "additive growth n=%u retained=%d units=%zu epochs=%zu\n",
            n, retained, units, rc_cycle_epochs - epochs);
    /* A pure append must not rescan every already-owned list slot after each
     * old interior borrow. This work bound is independent of CPU/toolchain. */
    assert(units <= 8u * n + 64u);
    for (unsigned i = 0; i < n; i += 2) {
        minyar_list_set_traced(g.list, i + 1, 0);
        drain();
    }
    assert(rc_object_count == 4u + n / 2u);
    minyar_rc_release(g.root);
    empty();
}
static void registered_growth(void) {
    Graph g = graph();
    size_t before = rc_cycle_units, epochs = rc_cycle_epochs;
    for (unsigned i = 0; i < 32; i++) {
        /* Still acyclic, but the new owner's traced outgoing edge registers
         * it. This remains deliberately conservative; it is a measured
         * limitation rather than evidence of general linear graph growth. */
        MinyarRecord *branch = minyar_record_new_traced(1);
        MinyarRecord *leaf = minyar_record_new_traced(1);
        minyar_record_set_traced(leaf, 0, 2000 + i);
        minyar_record_set_take_traced(branch, 0, slot(leaf));
        assert(rc_cycle_value(branch)->registered);
        assert(!rc_cycle_proven(rc_cycle_value(branch)));
        minyar_list_add_take_traced(g.list, slot(branch));
        minyar_rc_retain_traced(g.interior);
        for (unsigned call = 0; call < 64; call++) poll_one();
        rc_drop(g.interior);
        drain();
        assert(rc_object_count == 4u + 2u * (i + 1));
        assert(leaf->values[0] == 2000 + (long long)i);
    }
    fprintf(stderr, "registered acyclic growth n=32 units=%zu epochs=%zu\n",
            rc_cycle_units - before, rc_cycle_epochs - epochs);
    assert(rc_cycle_epochs > epochs); /* Unknown registered targets do rescan. */
    minyar_rc_release(g.root);
    empty();
}
static void fresh_owners(void) {
    Graph g = graph();
    /* A new owner's edge points TOWARDS the old root. That cannot certify
     * the new owner or its other descendants as reachable FROM the root. */
    MinyarRecord *outside = minyar_record_new_traced(2);
    minyar_record_set_reference_traced(outside, 1, slot(g.root));
    assert(rc_cycle_proof_valid);
    assert(!rc_cycle_proven(rc_cycle_value(outside)));
    /* A later unknown self-cycle keeps the old conservative cohort boundary. */
    minyar_record_set_reference_traced(outside, 0, slot(outside));
    assert(!rc_cycle_proof_valid);
    minyar_rc_release(outside);
    drain();
    assert(rc_object_count == 4);
    minyar_rc_release(g.root);
    empty();
}
static void unknown_children(void) {
    Graph g = graph();
    MinyarRecord *child = minyar_record_new_traced(2);
    minyar_record_set_reference_traced(child, 0, slot(child));
    minyar_record_set_reference_traced(child, 1, slot(g.root));
    assert(!rc_cycle_proven(rc_cycle_value(child)));
    minyar_list_add_take_traced(g.list, slot(child));
    drain();
    assert(rc_object_count == 5 && child->values[0] == slot(child));
    assert(child->values[1] == slot(g.root));
    minyar_list_set_traced(g.list, 1, 0);
    drain();
    assert(rc_object_count == 4);
    minyar_rc_release(g.root);
    empty();
}
static void copied_anchor(void) {
    Graph g = graph();
    /* The real copying API retains BEFORE incoming changes. The root's one
     * external owner must therefore survive creating a new back edge. */
    assert(rc_cycle_proof_valid);
    minyar_list_add_traced(g.list, slot(g.root));
    assert(rc_cycle_anchor_held() && rc_cycle_proof_valid);
    assert((((RcObject *)g.root - 1)->ownership >> 3) ==
           rc_cycle_value(g.root)->incoming + 1);
    size_t before = rc_cycle_units, epochs = rc_cycle_epochs;
    minyar_rc_retain_traced(g.interior);
    for (unsigned i = 0; i < 64; i++) poll_one();
    rc_drop(g.interior);
    assert(rc_cycle_pending);
    drain();
    assert(rc_cycle_units - before == 1 && rc_cycle_epochs == epochs);
    assert(rc_object_count == 4);
    minyar_list_set_traced(g.list, 1, 0);
    drain();
    minyar_rc_release(g.root);
    empty();
}
static void moved_anchor(void) {
    Graph g = graph();
    /* Prefix of the real list_store_traced take ordering: there is no retain,
     * incoming changes, then the slot is stored, then polling may run. */
    if (g.list->length == g.list->capacity) list_grow(g.list);
    assert(rc_cycle_proof_valid);
    rc_cycle_edge_insert(g.list, g.root);
    assert(!rc_cycle_anchor_held());
    assert(!rc_cycle_proof_valid);
    g.list->values[g.list->length++] = slot(g.root);
    /* Model external roots is now empty: root -> list -> root is garbage. */
    empty();
}
static void replacement_and_reuse(void) {
    Graph g = graph();
    MinyarRecord *captured = minyar_record_new_traced(3);
    minyar_record_set_traced(captured, 0, minyar_callback_domain());
    minyar_record_set_reference_traced(captured, 1, slot(g.root));
    minyar_record_set_reference_traced(captured, 2, slot(captured));
    minyar_list_add_take_traced(g.list, slot(captured));
    drain();
    assert(rc_object_count == 5);
    /* Existing replacement barrier remains conservative before the removal
     * or final store, even when the replacement value is the same pointer. */
    minyar_rc_retain_traced(g.root);
    rc_cycle_edge_add(captured, g.root);
    assert(!rc_cycle_proof_valid);
    rc_cycle_edge_remove(g.root);
    captured->values[1] = slot(g.root);
    rc_drop(g.root);
    rc_cycle_request();
    drain();
    minyar_list_set_traced(g.list, 1, 0);
    drain();
    assert(rc_object_count == 4);
    minyar_rc_release(g.root);
    empty();
    /* Fixed/eager allocators can recycle anchor addresses; no certificate,
     * retry cursor or stale generation may survive either lifetime. */
    for (unsigned i = 0; i < 128; i++) {
        Graph next = graph();
        minyar_rc_release(next.root);
        empty();
    }
}
static void anchor_boundary(void) {
    MinyarRecord *outside = minyar_record_new_traced(1);
    minyar_record_set_reference_traced(outside, 0, slot(outside));
    MinyarRecord *anchor = minyar_record_new_traced(1);
    minyar_record_set_reference_traced(anchor, 0, slot(outside));
    minyar_rc_release(outside);
    drain();
    assert(rc_object_count == 2);
    assert(rc_cycle_proof_anchor == rc_cycle_value(anchor));
    /* Before any cleanup poll can obscure the allocator-reuse boundary. */
    rc_drop(anchor);
    assert(!rc_cycle_proof_anchor);
#ifndef MINYAR_BOUNDED_RC
    minyar_rc_release(NULL); /* Service the eager destructor after its boundary. */
#endif
    empty();
}
static void force_phase(unsigned phase) {
    size_t turns = 0;
    while (rc_cycle_phase != phase) {
        assert(++turns < 100000);
#ifdef MINYAR_BOUNDED_RC
        minyar_rc_poll(1);
#else
        rc_cycle_eager_service(1);
#endif
    }
}
static void phases(void) {
    for (unsigned phase = RC_CYCLE_ROOTS; phase <= RC_CYCLE_SWEEP; phase++) {
        Graph g = graph();
        MinyarRecord *other = minyar_record_new_traced(1);
        minyar_record_set_traced(other, 0, 123);
        assert(rc_cycle_proof_valid);
        rc_cycle_request();
        force_phase(phase);
        assert(rc_cycle_proof_valid && rc_cycle_proof_build);
        /* New allocation and list expansion may service work themselves.
         * Use an already live child and barrier prefix at the chosen phase. */
        minyar_rc_retain_traced(g.interior);
        rc_cycle_edge_insert(g.list, g.interior);
        assert(!rc_cycle_proof_valid && !rc_cycle_proof_build);
        if (g.list->length == g.list->capacity) list_grow(g.list);
        g.list->values[g.list->length++] = slot(g.interior);
        minyar_rc_release(other);
        drain();
        assert(rc_object_count == 4);
        assert(g.interior->values[1] == 19);
        minyar_list_set_traced(g.list, 1, 0);
        drain();
        minyar_rc_release(g.root);
        empty();
    }
}
/* Two disconnected roots: neither certificate can make a disconnected cycle
 * immortal. Insertion into one component cannot transfer the other's tag. */
static void roots(void) {
    Graph a = graph();
    Graph b = graph();
    MinyarRecord *outside = minyar_record_new_traced(1);
    minyar_record_set_reference_traced(outside, 0, slot(outside));
    minyar_rc_release(outside);
    drain();
    assert(rc_object_count == 8);
    minyar_rc_release(a.root);
    drain();
    assert(rc_object_count == 4 && b.interior->values[1] == 19);
    minyar_rc_release(b.root);
    empty();
}
int main(int argc, char **argv) {
    unsigned n = argc > 1 ? (unsigned)strtoul(argv[1], NULL, 10) : 256;
    assert(n == 32 || n == 256 || n == 2048);
    growth(n, 0);
    growth(n, 1);
    registered_growth();
    fresh_owners();
    unknown_children();
    copied_anchor();
    moved_anchor();
    replacement_and_reuse();
    anchor_boundary();
    phases();
    roots();
    printf("additive certificates: n=%u objects=0 bytes=0\n", n);
    return 0;
}
