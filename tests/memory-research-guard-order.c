/* Baseline constructor/size guard order with preexisting detached debt.
 * Synthetic unallocatable Text/record sizes test C ABI defenses, not a reachable
 * huge generated value. Only managed allocations/service are counted. */
#define main research_matrix_main
#include "memory-research-credit-relocation.c"
#undef main
static MinyarBytes *protected_bytes;
static size_t pending_before;
static int expecting_trap;
__attribute__((destructor)) static void verify_trap_order(void) {
    if (!expecting_trap) return;
    research_active = 0;
    assert(!research_object_allocations && !research_data_allocations && !research_data_resizes);
    assert(!research_service_calls && !research_queued && !research_immediate && !research_destroyed);
    assert(rc_pending_count == pending_before);
    minyar_rc_release(protected_bytes);
    clear();
    puts("{\"managed_allocations\":0,\"managed_service_hooks\":0,\"queued_units\":0,"
         "\"immediate_units\":0,\"pending_before\":1,\"full_recovery\":true}");
}
int main(int argc, char **argv) {
    assert(argc == 2);
    protected_bytes = minyar_bytes_new(16);
    MinyarRecord *debt = minyar_record_new(129);
    minyar_rc_release(debt);
    assert(rc_pending_count == 1);
    pending_before = rc_pending_count;
    research_object_allocations = research_data_allocations = research_data_resizes = 0;
    research_service_calls = research_offered = research_queued = research_immediate = 0;
    research_destroyed = 0;
    research_active = expecting_trap = 1;
    /* Oracle calibration only: this deliberately violates the measured order. */
    if (getenv("MINYAR_RESEARCH_GUARD_INJECT_SERVICE"))
        rc_service_pending(MINYAR_RC_POLL_BUDGET);
    if (!strcmp(argv[1], "bytes-negative")) minyar_bytes_new(-1);
    else if (!strcmp(argv[1], "bytes-max")) minyar_bytes_new(LLONG_MAX);
    else if (!strcmp(argv[1], "bytes-resize-max")) minyar_bytes_resize(protected_bytes, LLONG_MAX);
    else if (!strcmp(argv[1], "bytes-extend-negative")) minyar_bytes_extend(protected_bytes, -1);
    else if (!strcmp(argv[1], "bytes-extend-max")) minyar_bytes_extend(protected_bytes, LLONG_MAX);
    else if (!strcmp(argv[1], "bytes-int64-max-position")) minyar_bytes_set_int64(protected_bytes, LLONG_MAX, 1);
    else if (!strcmp(argv[1], "record-negative")) minyar_record_new(-1);
    else if (!strcmp(argv[1], "record-max")) minyar_record_new(LLONG_MAX);
    else if (!strcmp(argv[1], "record-allocation-overflow")) {
        size_t limit = (SIZE_MAX - sizeof(RcObject) - sizeof(MinyarRecord)) / 9;
        assert(limit < (size_t)LLONG_MAX);
        minyar_record_new((long long)limit + 1);
    } else if (!strcmp(argv[1], "text-copy-overflow") || !strcmp(argv[1], "text-consume-overflow")) {
        MinyarText left = {NULL, LLONG_MAX, -1, NULL, NULL};
        MinyarText right = {NULL, 1, 1, NULL, NULL};
        if (!strcmp(argv[1], "text-copy-overflow")) minyar_join_text(&left, &right);
        else minyar_join_text_take_left(&left, &right);
    } else assert(0 && "unknown guard case");
    assert(0 && "guard must trap");
}
