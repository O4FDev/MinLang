/* Sticky exposure distinguishes captured inbound paths from fresh cohorts. */
#define MINYAR_LATE_REGISTRATION_NO_MAIN 1
#include "cycle-late-registration.c"

static void *receiver_new(int kind) {
    if (kind)
        return minyar_record_new_traced(1);
    MinyarList *list = minyar_list_new_traced();
    minyar_list_references(list);
    list_reserve(list, 4);
    return list;
}
static MinyarRecord *payload_new(MinyarRecord *core) {
    MinyarRecord *p = minyar_record_new_traced(2);
    minyar_record_set_reference_traced(p, 0, slot(core));
    minyar_record_set_traced(p, 1, 431);
    return p;
}
static void receiver_check(void *receiver, int kind, MinyarRecord *payload) {
    if (kind)
        assert(((MinyarRecord *)receiver)->values[0] == slot(payload));
    else {
        MinyarList *l = receiver;
        assert(l->length == 1 && l->values[0] == slot(payload));
    }
    assert(payload->values[1] == 431);
}
static void receiver_publish(void *receiver, int kind, MinyarRecord *payload, int copied,
                             int borrowed, int preserve) {
    if (borrowed)
        minyar_rc_retain_traced(receiver);
    if (copied)
        minyar_rc_retain_traced(payload);
    if (kind) {
        MinyarRecord *r = receiver;
        unsigned char *map = (unsigned char *)(r->values + r->length);
        map[0] = 1;
    }
    rc_cycle_edge_insert(receiver, payload);
    assert(!!rc_cycle_proof_valid == preserve);
    if (kind) {
        MinyarRecord *r = receiver;
        unsigned char *map = (unsigned char *)(r->values + r->length);
        map[0] = 1;
        r->values[0] = slot(payload);
    } else {
        MinyarList *l = receiver;
        l->values[l->length++] = slot(payload);
    }
    rc_cycle_commit_insert(receiver, payload);
    if (copied)
        rc_drop(payload);
    if (borrowed)
        rc_drop(receiver);
    drain();
    receiver_check(receiver, kind, payload);
}
static MinyarRecord *parent_new(Graph g, void *receiver, int attach) {
    MinyarRecord *p = minyar_record_new_traced(3);
    minyar_record_set_reference_traced(p, 0, slot(g.root));
    if (attach)
        minyar_record_set_take_traced(p, 1, slot(receiver));
    minyar_record_set_traced(p, 2, 99);
    return p;
}
static void parent_commit(Graph g, MinyarRecord *parent) {
    minyar_rc_retain_traced(parent);
    rc_cycle_edge_insert(g.list, parent);
    g.list->values[g.list->length++] = slot(parent);
    rc_cycle_commit_insert(g.list, parent);
    rc_drop(parent);
    assert(rc_cycle_proven(rc_cycle_value(parent)));
    int found = 0;
    for (RcCycle *c = rc_cycle_head; c; c = c->next)
        found |= c == rc_cycle_value(parent);
    assert(found);
    for (RcCycle *c = rc_cycle_known_head; c; c = c->next)
        assert(c != rc_cycle_value(parent));
}
static void fresh_or_scanned(int kind, int copied, int borrowed, int exposure) {
    Graph g = graph();
    void *receiver = receiver_new(kind);
    MinyarRecord *parent = parent_new(g, receiver, 1);
    MinyarRecord *payload = payload_new(g.root);
    assert(!rc_cycle_value(receiver)->registered && rc_cycle_value(receiver)->incoming == 1);
    if (exposure) {
        rc_cycle_request_local();
        drain();
        assert(rc_cycle_value(receiver)->gray_next & 4);
    }
    receiver_publish(receiver, kind, payload, copied, borrowed, !exposure);
    assert(rc_object_count == 7 && parent->values[1] == slot(receiver));
    assert(parent->values[0] == slot(g.root) && parent->values[2] == 99);
    assert(payload->values[0] == slot(g.root));
    minyar_rc_release(parent);
    minyar_rc_release(g.root);
    empty();
}
/* A direct certificate does not move a fresh source out of its unknown
 * registry cohort. Before MARK skips its empty child, the later registered
 * child must survive through that source and a subsequent finite cohort. */
static void delayed_direct_certificate(int kind, int copied, int borrowed, int captured) {
    Graph g = graph();
    void *receiver = receiver_new(kind);
    MinyarRecord *parent = parent_new(g, receiver, 1);
    MinyarRecord *payload = payload_new(g.root);
    parent_commit(g, parent);
    if (captured) {
        rc_cycle_request_local();
        size_t steps = 0;
        do {
            assert(++steps < 10000);
            rc_cycle_unit();
        } while (rc_cycle_cursor != rc_cycle_value(parent));
        assert(rc_cycle_phase == RC_CYCLE_ROOTS && rc_cycle_local_job);
        rc_cycle_unit();
        assert(rc_cycle_value(parent)->marked == 1);
    }
    assert(!(rc_cycle_value(receiver)->gray_next & 4));
    receiver_publish(receiver, kind, payload, copied, borrowed, 1);
    assert(rc_object_count == 7 && parent->values[1] == slot(receiver));
    assert(parent->values[0] == slot(g.root) && payload->values[0] == slot(g.root));
    minyar_rc_release(g.root);
    empty();
}
static void captured_publication(int kind, int copied, int borrowed, int completed) {
    Graph g = graph();
    void *receiver = receiver_new(kind);
    MinyarRecord *parent = parent_new(g, receiver, 0);
    MinyarRecord *payload = payload_new(g.root);
    rc_cycle_request_local();
    size_t steps = 0;
    if (completed) {
        do {
            assert(++steps < 10000);
            rc_cycle_unit();
        } while (rc_cycle_value(parent)->marked != 2);
        assert(rc_cycle_phase == RC_CYCLE_MARK);
    } else {
        do {
            assert(++steps < 10000);
            rc_cycle_unit();
        } while (rc_cycle_cursor != rc_cycle_value(parent));
        assert(rc_cycle_phase == RC_CYCLE_ROOTS);
        rc_cycle_unit();
        assert(rc_cycle_value(parent)->marked == 1);
    }
    minyar_record_set_take_traced(parent, 1, slot(receiver));
    assert(!rc_cycle_value(receiver)->registered && (rc_cycle_value(receiver)->gray_next & 4));
    receiver_publish(receiver, kind, payload, copied, borrowed, 0);
    assert(rc_object_count == 7 && parent->values[1] == slot(receiver));
    minyar_rc_release(parent);
    minyar_rc_release(g.root);
    empty();
}
/* The newly appended child lies outside the captured List scan limit.
 * Subsequent direct certification can restart the index but not that limit. */
static void append_beyond_mark_limit(int kind, int copied, int borrowed) {
    Graph g = graph();
    MinyarList *parent = minyar_list_new_traced();
    minyar_list_references(parent);
    list_reserve(parent, 4);
    MinyarRecord *leaf = minyar_record_new_traced(1);
    minyar_record_set_traced(leaf, 0, 808);
    minyar_list_add_traced(parent, slot(leaf));
    minyar_list_add_traced(parent, slot(leaf));
    minyar_rc_release(leaf);
    void *receiver = receiver_new(kind);
    MinyarRecord *payload = payload_new(g.root);
    rc_cycle_request_local();
    size_t steps = 0;
    do {
        assert(++steps < 10000);
        rc_cycle_unit();
    } while (rc_cycle_active != rc_cycle_value(parent) || rc_cycle_index != 1);
    assert(rc_cycle_phase == RC_CYCLE_MARK && rc_cycle_limit == 2);
    rc_cycle_edge_insert(parent, receiver);
    parent->values[parent->length++] = slot(receiver);
    rc_cycle_commit_insert(parent, receiver);
    assert(rc_cycle_value(receiver)->gray_next & 4);
    minyar_rc_retain_traced(parent);
    rc_cycle_edge_insert(g.list, parent);
    g.list->values[g.list->length++] = slot(parent);
    rc_cycle_commit_insert(g.list, parent);
    rc_drop(parent);
    assert(rc_cycle_proven(rc_cycle_value(parent)) && rc_cycle_limit == 2);
    drain();
    assert(rc_cycle_proven(rc_cycle_value(parent)));
    receiver_publish(receiver, kind, payload, copied, borrowed, 0);
    assert(rc_object_count == 8 && parent->length == 3);
    assert(parent->values[2] == slot(receiver) && leaf->values[0] == 808);
    minyar_rc_release(g.root);
    empty();
}
static void shared_exposure(int kind, int copied, int borrowed) {
    Graph g = graph();
    void *receiver = receiver_new(kind);
    MinyarRecord *old = parent_new(g, receiver, 1);
    rc_cycle_request_local();
    drain();
    assert(rc_cycle_value(receiver)->gray_next & 4);
    MinyarRecord *fresh = parent_new(g, NULL, 0);
    minyar_record_set_reference_traced(fresh, 1, slot(receiver));
    assert(rc_cycle_value(receiver)->incoming == 2);
    rc_cycle_edge_remove(receiver);
    old->values[1] = 0;
    rc_drop(receiver);
    assert(rc_cycle_value(receiver)->incoming == 1 && (rc_cycle_value(receiver)->gray_next & 4));
    minyar_rc_release(old);
    drain();
    for (int epoch = 0; epoch < 3; epoch++) {
        rc_cycle_request();
        drain();
        assert(!rc_cycle_value(receiver)->registered && (rc_cycle_value(receiver)->gray_next & 4));
    }
    MinyarRecord *payload = payload_new(g.root);
    receiver_publish(receiver, kind, payload, copied, borrowed, 0);
    assert(rc_object_count == 7 && fresh->values[1] == slot(receiver));
    minyar_rc_release(fresh);
    minyar_rc_release(g.root);
    empty();
}
static void reused_receiver(int kind) {
    for (int i = 0; i < 32; i++) {
        Graph g = graph();
        void *receiver = receiver_new(kind);
        MinyarRecord *old = parent_new(g, receiver, 1);
        rc_cycle_request_local();
        drain();
        assert(rc_cycle_value(receiver)->gray_next & 4);
        minyar_rc_release(old);
        drain();
        rc_cycle_request();
        drain();
        assert(rc_cycle_proof_valid);
        void *fresh = receiver_new(kind);
        assert(!rc_cycle_value(fresh)->gray_next && !rc_cycle_value(fresh)->incoming);
        MinyarRecord *parent = parent_new(g, fresh, 1);
        MinyarRecord *payload = payload_new(g.root);
        receiver_publish(fresh, kind, payload, 0, 1, 1);
        assert(rc_object_count == 7 && parent->values[1] == slot(fresh));
        minyar_rc_release(parent);
        minyar_rc_release(g.root);
        empty();
    }
}
/* A canceled local MARK can finish a known root outside its sweep cohort.
 * Moving its last external owner before the next full ROOTS visit must
 * retain the snapshot path, even though its stale completed mark is 2. */
static void move_stale_root_before_visit(int kind) {
    Late s = setup(0, 0);
    MinyarRecord *payload = minyar_record_new_traced(3);
    minyar_record_set_traced(payload, 0, 1);
    minyar_record_set_reference_traced(payload, 1, slot(s.parent));
    minyar_record_set_traced(payload, 2, 123);
    rc_cycle_request_local();
    rc_cycle_unit();
    assert(rc_cycle_phase == RC_CYCLE_ROOTS && rc_cycle_local_job);
    publish(s, payload, 0, 1);
    size_t steps = 0;
    while (rc_cycle_phase != RC_CYCLE_IDLE) {
        assert(++steps < 10000);
        rc_cycle_unit();
    }
    RcCycle *root = rc_cycle_value(s.parent);
    assert(root->marked == 2 && rc_cycle_rescan && rc_cycle_pending);
    rc_cycle_unit();
    assert(rc_cycle_phase == RC_CYCLE_ROOTS && !rc_cycle_local_job);
    void *owner = receiver_new(kind);
    if (kind) {
        MinyarRecord *r = owner;
        unsigned char *map = (unsigned char *)(r->values + r->length);
        map[0] = 1;
    }
    rc_cycle_edge_insert(owner, s.parent);
    assert(root->marked == 1);
    if (kind)
        ((MinyarRecord *)owner)->values[0] = slot(s.parent);
    else {
        MinyarList *l = owner;
        l->values[l->length++] = slot(s.parent);
    }
    rc_cycle_commit_insert(owner, s.parent);
    drain();
    check(s, payload, s.parent, 4);
    if (kind)
        assert(((MinyarRecord *)owner)->values[0] == slot(s.parent));
    else
        assert(((MinyarList *)owner)->values[0] == slot(s.parent));
    minyar_rc_release(owner);
    empty();
}
int main(void) {
    queued_full_root();
    move_stale_root_before_visit(0);
    move_stale_root_before_visit(1);
    for (int kind = 0; kind < 2; kind++) {
        for (int copied = 0; copied < 2; copied++)
            for (int borrowed = 0; borrowed < 2; borrowed++) {
                for (int exposed = 0; exposed < 2; exposed++) {
                    fresh_or_scanned(kind, copied, borrowed, exposed);
                    delayed_direct_certificate(kind, copied, borrowed, exposed);
                    captured_publication(kind, copied, borrowed, exposed);
                }
                append_beyond_mark_limit(kind, copied, borrowed);
                shared_exposure(kind, copied, borrowed);
            }
        reused_receiver(kind);
    }
    for (int kind = 0; kind < 2; kind++)
        for (int topology = 0; topology < 3; topology++)
            for (int copied = 0; copied < 2; copied++)
                for (int borrowed = 0; borrowed < 2; borrowed++)
                    for (unsigned phase = RC_CYCLE_IDLE; phase <= RC_CYCLE_SWEEP; phase++)
                        run_case(kind, topology, copied, borrowed, phase);
    fprintf(stderr, "registration exposure owning paths and queue integrity exact cleanup zero\n");
    return 0;
}
