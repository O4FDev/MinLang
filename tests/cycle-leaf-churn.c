/* Replacing leaf buffers must not rescan a rooted callback/Core component. */
#define main additive_fixture_main
#include "cycle-additive.c"
#undef main

static MinyarRecord *churn_branch(unsigned value) {
    MinyarRecord *owner = minyar_record_new_traced(1);
    MinyarRecord *leaf = minyar_record_new_traced(1);
    minyar_record_set_traced(leaf, 0, value);
    minyar_record_set_take_traced(owner, 0, slot(leaf));
    return owner;
}
typedef struct { Graph g; MinyarRecord *callback, *buffers; } Churn;
static Churn churn_graph(unsigned n) {
    Churn c = {.g = graph()};
    for (unsigned i = 0; i < n; i++)
        minyar_list_add_take_traced(c.g.list, slot(churn_branch(10000 + i)));
    drain();
    /* callback -> Core(root) -> list -> callback is a real owning cycle. */
    c.callback = minyar_record_new_traced(3);
    minyar_record_set_traced(c.callback, 0, 101);
    minyar_record_set_traced(c.callback, 1, 202);
    minyar_record_set_reference_traced(c.callback, 2, slot(c.g.root));
    minyar_list_add_take_traced(c.g.list, slot(c.callback));
    c.buffers = minyar_record_new_traced(1);
    MinyarList *buffer = minyar_list_new_traced();
    minyar_list_references(buffer);
    minyar_record_set_take_traced(c.buffers, 0, slot(buffer));
    minyar_list_add_take_traced(c.g.list, slot(c.buffers));
    drain();
    assert(rc_object_count == 7u + 2u * n);
    assert(rc_cycle_phase == RC_CYCLE_IDLE && rc_cycle_proof_valid);
    assert(rc_cycle_proof_anchor == rc_cycle_value(c.g.root) && rc_cycle_anchor_held());
    return c;
}
static MinyarList *churn_buffer(Churn c) {
    return (MinyarList *)(uintptr_t)c.buffers->values[0];
}
static void churn_check(Churn c, unsigned n, unsigned children) {
    assert(c.g.list->length == n + 3u);
    assert(c.g.interior->values[1] == 19);
    assert(c.callback->values[0] == 101 && c.callback->values[1] == 202);
    assert(c.callback->values[2] == slot(c.g.root));
    for (unsigned i = 0; i < n; i++) {
        MinyarRecord *owner = (MinyarRecord *)(uintptr_t)c.g.list->values[i + 1];
        MinyarRecord *leaf = (MinyarRecord *)(uintptr_t)owner->values[0];
        assert(leaf->values[0] == 10000 + (long long)i);
    }
    assert(churn_buffer(c)->length == children);
    assert(rc_object_count == 7u + 2u * n + 2u * children);
}
static void churn_borrow(Churn c) {
    minyar_rc_retain_traced(c.g.interior);
    minyar_rc_release(c.g.interior);
    drain();
}
static void churn(unsigned n, const char *mode, unsigned phase) {
    Churn c = churn_graph(n);
    size_t units = rc_cycle_units, epochs = rc_cycle_epochs;
    const unsigned rounds = 8;
    unsigned complete = 0;
    if (!strcmp(mode, "active")) {
        assert(phase >= RC_CYCLE_ROOTS && phase <= RC_CYCLE_SWEEP);
        rc_cycle_request();
        force_phase(phase);
    }
    for (unsigned i = 0; i < rounds; i++) {
        MinyarList *old = churn_buffer(c);
        MinyarList *buffer = minyar_list_new_traced();
        minyar_list_references(buffer);
        unsigned children = !strcmp(mode, "registered");
        if (children)
            minyar_list_add_take_traced(buffer, slot(churn_branch(50000 + i)));
        else {
            /* No traced outgoing edge has ever registered either leaf. */
            assert(!rc_cycle_value(old)->registered && old->length == 0);
            assert(!rc_cycle_value(buffer)->registered && buffer->length == 0);
        }
        minyar_record_replace_traced(c.buffers, 0, slot(buffer), 1);
        complete += !!rc_cycle_proof_valid;
        churn_borrow(c);
        churn_check(c, n, children);
        if (children) {
            MinyarRecord *owner = (MinyarRecord *)(uintptr_t)buffer->values[0];
            MinyarRecord *leaf = (MinyarRecord *)(uintptr_t)owner->values[0];
            assert(leaf->values[0] == 50000 + (long long)i);
        }
    }
    size_t work = rc_cycle_units - units;
    size_t growth = rc_cycle_epochs - epochs;
    fprintf(stderr, "CHURN mode=%s n=%u rounds=%u units=%zu epochs=%zu complete=%u\n",
            mode, n, rounds, work, growth, complete);
    if (!strcmp(mode, "late")) {
        /* An exposed leaf later gains a traced edge. Its old captured parent
         * must rejoin the proof; the new descendant survives independent of
         * marks, and the whole cyclic graph must die with the actual root. */
        MinyarList *buffer = churn_buffer(c);
        assert(!rc_cycle_value(buffer)->registered);
        assert(rc_cycle_value(buffer)->gray_next & 4);
        size_t before = rc_cycle_epochs;
        minyar_list_add_take_traced(buffer, slot(churn_branch(60000)));
        assert(rc_cycle_value(buffer)->registered);
        assert(!rc_cycle_proof_valid || rc_cycle_epochs > before);
        churn_borrow(c);
        assert(rc_cycle_epochs > before);
        churn_check(c, n, 1);
        MinyarRecord *owner = (MinyarRecord *)(uintptr_t)buffer->values[0];
        MinyarRecord *leaf = (MinyarRecord *)(uintptr_t)owner->values[0];
        assert(leaf->values[0] == 60000);
    } else if (!strcmp(mode, "registered") || !strcmp(mode, "active")) {
        assert(growth > 0);
    } else {
        assert(!strcmp(mode, "churn"));
    }
    minyar_rc_release(c.g.root);
    empty(); /* Independent reclamation oracle runs before the work assertion. */
    if (!strcmp(mode, "churn") || !strcmp(mode, "late")) {
        assert(work <= 16u * rounds + 64u);
        assert(complete == rounds);
        assert(growth == 0); /* Existing unchanged 192-unit bound. */
    }
}
int main(int argc, char **argv) {
    assert(argc == 3 || argc == 4);
    unsigned n = (unsigned)strtoul(argv[1], NULL, 10);
    assert(n >= 32 && n <= 2048);
    unsigned phase = argc == 4 ? (unsigned)strtoul(argv[3], NULL, 10) : 0;
    churn(n, argv[2], phase);
    empty();
    return 0;
}
