/* First registration must rediscover an owning path from old certified roots. */
#define main additive_fixture_main
#define empty additive_empty
#include "cycle-additive.c"
#undef empty
#undef main

typedef struct {
    Graph main;
    MinyarRecord *parent;
    void *receiver;
    int kind, topology;
} Late;
static void empty(void) {
    additive_empty();
    assert(!rc_cycle_known_head && !rc_cycle_known_tail && !rc_cycle_tail);
    assert(!rc_cycle_temporary_anchor && !rc_cycle_local_requested);
}
static Late setup(int kind, int topology) {
    Late s = {0};
    s.kind = kind;
    s.topology = topology;
    if (topology)
        s.main = graph();
    s.receiver = kind ? (void *)minyar_record_new_traced(1) : (void *)minyar_list_new_traced();
    if (!kind) {
        minyar_list_references(s.receiver);
        list_reserve(s.receiver, 2);
    }
    if (topology < 2) {
        s.parent = minyar_record_new_traced(2);
        minyar_record_set_take_traced(s.parent, 0, slot(s.receiver));
        minyar_record_set_traced(s.parent, 1, 77);
        if (!topology) {
            rc_cycle_request();
            drain();
            assert(rc_cycle_proof_anchor == rc_cycle_value(s.parent));
            assert(rc_cycle_proven(rc_cycle_value(s.parent)));
        } else {
            rc_cycle_request_local();
            drain();
            assert(!rc_cycle_proven(rc_cycle_value(s.parent)));
        }
    }
    assert(rc_cycle_proof_valid && !rc_cycle_value(s.receiver)->registered);
    assert(rc_cycle_value(s.receiver)->incoming == (size_t)(topology < 2));
    return s;
}
static void publish(Late s, MinyarRecord *payload, int copied, int exact) {
    if (!exact) {
        if (s.kind) {
            if (copied)
                minyar_record_set_reference_traced(s.receiver, 0, slot(payload));
            else
                minyar_record_set_take_traced(s.receiver, 0, slot(payload));
        } else {
            if (copied)
                minyar_list_add_traced(s.receiver, slot(payload));
            else
                minyar_list_add_take_traced(s.receiver, slot(payload));
        }
    } else {
        /* The exact public retain / incoming / store / publication ordering,
         * stopped before its automatic service to inspect each local phase. */
        if (copied)
            minyar_rc_retain_traced(payload);
        if (s.kind) {
            MinyarRecord *r = s.receiver;
            unsigned char *map = (unsigned char *)(r->values + r->length);
            map[0] = 1;
            rc_cycle_edge_insert(r, payload);
            if (s.topology < 2)
                assert(!rc_cycle_proof_valid);
            else if (rc_cycle_phase != RC_CYCLE_SWEEP)
                assert(rc_cycle_proof_valid);
            r->values[0] = slot(payload);
            rc_cycle_commit_insert(r, payload);
        } else {
            MinyarList *l = s.receiver;
            rc_cycle_edge_insert(l, payload);
            if (s.topology < 2)
                assert(!rc_cycle_proof_valid);
            else if (rc_cycle_phase != RC_CYCLE_SWEEP)
                assert(rc_cycle_proof_valid);
            l->values[l->length++] = slot(payload);
            rc_cycle_commit_insert(l, payload);
        }
    }
    if (copied)
        rc_drop(payload);
}
static MinyarRecord *outside_chain(unsigned n) {
    MinyarRecord *next = NULL;
    for (unsigned i = 0; i < n; i++) {
        MinyarRecord *p = minyar_record_new_traced(1);
        MinyarRecord *child = next ? next : minyar_record_new_traced(1);
        minyar_record_set_take_traced(p, 0, slot(child));
        next = p;
    }
    return next;
}
static void check(Late s, MinyarRecord *payload, MinyarRecord *captured, size_t objects) {
    assert(rc_object_count == objects);
    if (s.parent)
        assert(s.parent->values[0] == slot(s.receiver) && s.parent->values[1] == 77);
    if (s.kind)
        assert(((MinyarRecord *)s.receiver)->values[0] == slot(payload));
    else {
        MinyarList *l = s.receiver;
        assert(l->length == 1 && l->values[0] == slot(payload));
    }
    assert(payload->values[1] == slot(captured) && payload->values[2] == 123);
    assert(rc_cycle_value(s.receiver)->registered);
}
static void run_case(int kind, int topology, int copied, int borrowed, unsigned phase) {
    Late s = setup(kind, topology);
    MinyarRecord *captured = topology ? s.main.root : s.parent;
    MinyarRecord *payload = minyar_record_new_traced(3);
    minyar_record_set_traced(payload, 0, 1);
    minyar_record_set_reference_traced(payload, 1, slot(captured));
    minyar_record_set_traced(payload, 2, 123);
    assert(rc_cycle_value(payload)->registered);
    MinyarRecord *outside = NULL;
    if (borrowed)
        minyar_rc_retain_traced(s.receiver);
    if (phase != RC_CYCLE_IDLE) {
        outside = outside_chain(16);
        rc_cycle_request_local();
        size_t steps = 0;
        do {
            assert(++steps < 10000);
            size_t before = rc_cycle_units;
            rc_cycle_unit();
            assert(rc_cycle_units == before + 1);
        } while (rc_cycle_phase != phase);
        assert(rc_cycle_local_job && rc_cycle_proof_valid);
    }
    size_t objects = rc_object_count;
    publish(s, payload, copied, phase != RC_CYCLE_IDLE);
    if (borrowed)
        rc_drop(s.receiver);
    drain();
    check(s, payload, captured, objects);
    if (outside) {
        minyar_rc_release(outside);
        drain();
        check(s, payload, captured, objects - 17);
    }
    if (topology < 2)
        minyar_rc_release(s.parent);
    else
        minyar_rc_release(s.receiver);
    if (topology)
        minyar_rc_release(s.main.root);
    empty();
}
int main(void) {
    for (int kind = 0; kind < 2; kind++)
        for (int topology = 0; topology < 3; topology++)
            for (int copied = 0; copied < 2; copied++)
                for (int borrowed = 0; borrowed < 2; borrowed++)
                    for (unsigned phase = RC_CYCLE_IDLE; phase <= RC_CYCLE_SWEEP; phase++)
                        run_case(kind, topology, copied, borrowed, phase);
    fprintf(stderr, "late registration 96 owning-path schedules exact cleanup zero\n");
    return 0;
}
