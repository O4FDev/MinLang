
/* Deliberately conservative self-cycle growth: correctness, not a linear
 * performance claim. This fixture records the regime retained for e2 ROOTS. */
#define main additive_fixture_main
#include "cycle-additive.c"
#undef main
int main(int argc, char **argv) {
    unsigned n = argc > 1 ? (unsigned)strtoul(argv[1], NULL, 10) : 256;
    assert(n == 32 || n == 256 || n == 2048);
    Graph g = graph();
    size_t before = rc_cycle_units, epochs = rc_cycle_epochs;
    for (unsigned i = 0; i < n; i++) {
        MinyarRecord *child = minyar_record_new_traced(3);
        minyar_record_set_reference_traced(child, 0, slot(child));
        minyar_record_set_reference_traced(child, 1, slot(g.root));
        minyar_record_set_traced(child, 2, 6000 + i);
        minyar_list_add_take_traced(g.list, slot(child));
        minyar_rc_retain_traced(g.interior);
        for (unsigned call = 0; call < 64; call++) poll_one();
        rc_drop(g.interior);
        drain();
        assert(rc_object_count == 5u + i);
        assert(child->values[0] == slot(child));
        assert(child->values[1] == slot(g.root));
        assert(child->values[2] == 6000 + (long long)i);
    }
    size_t units = rc_cycle_units - before;
    fprintf(stderr,"residual self cycles n=%u units=%zu epochs=%zu\n",n,units,rc_cycle_epochs-epochs);
    assert(rc_cycle_epochs > epochs);
    for (unsigned i = 0; i < n; i += 2) minyar_list_set_traced(g.list, i + 1, 0);
    drain();
    assert(rc_object_count == 4u + n / 2);
    minyar_rc_release(g.root);
    empty();
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
    assert(!rc_cycle_known_head && !rc_cycle_known_tail && !rc_cycle_tail);
#endif
    puts("residual graph objects=0 bytes=0 debt=0");
    return 0;
}
