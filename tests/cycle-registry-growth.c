/* Registered owner/callback growth, with an independent explicit-edge oracle. */
#define main additive_fixture_main
#include "cycle-additive.c"
#undef main

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
    if (!strcmp(mode, "safety") || !strcmp(mode, "all")) {
        char *old[] = {(char *)"additive", (char *)"32", NULL};
        additive_fixture_main(2, old);
        conservative_mix();
    }
    printf("registered graph growth n=%u mode=%s objects=0 bytes=0\n", n, mode);
    return 0;
}
