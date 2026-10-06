/* Finite-pool counterexample to this research-only same-credit policy.
 * Baseline compacts the result and releases a 128 KiB backing block; reuse
 * keeps that block, so the identical next managed allocation cannot fit. */
#define main research_matrix_main
#include "memory-research-credit-relocation.c"
#undef main

int main(int argc, char **argv) {
    assert(argc == 2 && (!strcmp(argv[1], "baseline") || !strcmp(argv[1], "relocated")));
    int relocated = !strcmp(argv[1], "relocated");
    setvbuf(stdout, NULL, _IONBF, 0);
    unsigned char *bytes = rc_allocate_data(65536);
    assert(pool_offset((RcData *)bytes - 1) == 0);
    memset(bytes, 'x', 32768);
    bytes[32768] = 0;
    MinyarText *left = new_text(bytes, 32768, 32768);
    MinyarText *right = copy_c_text("!");
    minyar_rc_enter(MINYAR_RC_POLL_BUDGET + 1);
    minyar_rc_local(0, left);
    for (long long index = 1; index <= MINYAR_RC_POLL_BUDGET; index++)
        minyar_rc_local_take(index, copy_c_text("retired"));
    enum { MAX_FILLERS = MINYAR_BOUNDED_HEAP_BYTES / MINYAR_POOL_MINIMUM };
    void *fillers[MAX_FILLERS];
    size_t count = 0, opened = 0;
    void *next;
    while ((next = minyar_pool_try_allocate(32))) {
        assert(count < MAX_FILLERS);
        fillers[count++] = next;
    }
    assert(minyar_pool_used == MINYAR_POOL_BYTES);
    for (size_t index = 0; index < count; index++) {
        size_t offset = pool_offset(fillers[index]);
        if ((offset >= 262144 && offset < 327680) || offset >= MINYAR_POOL_BYTES - 64) {
            minyar_pool_deallocate(fillers[index]);
            fillers[index] = NULL;
            opened += 32;
        }
    }
    assert(opened == 65536 + 64);
    minyar_rc_leave();
    assert(((RcObject *)left - 1)->ownership >> 3 == 2);
    research_service_calls = research_offered = research_queued = research_immediate = 0;
    research_destroyed = research_object_allocations = research_data_allocations = 0;
    research_data_resizes = 0;
    research_requested_peak = rc_bytes;
    research_active = 1;
    MinyarText *result = research_credit_join(left, right, relocated);
    research_active = 0;
    assert(result->byte_length == 32769 && result->bytes[32768] == '!');
    for (size_t index = 0; index < 32768; index++)
        assert(result->bytes[index] == 'x');
    assert(((RcData *)result->bytes - 1)->size == (size_t)(relocated ? 65536 : 32770));
    assert(!rc_pending_count);
    printf("{\"relocated\":%d,\"budget\":%u,\"result_capacity\":%zu,"
           "\"pool_used_before_next\":%zu,\"requested_before_next\":%zu,"
           "\"service_hooks\":%zu,\"offered_units\":%zu,\"queued_units\":%zu,"
           "\"immediate_units\":%zu,\"next_requested_bytes\":131060}\n",
           relocated, MINYAR_RC_POLL_BUDGET, ((RcData *)result->bytes - 1)->size,
           minyar_pool_used, rc_bytes, research_service_calls, research_offered,
           research_queued, research_immediate);
    void *allocation = rc_allocate_data(131060);
    assert(!relocated);
    rc_free_data(allocation);
    minyar_rc_release(result);
    minyar_rc_release(right);
    while (rc_pending_count)
        minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
    for (size_t index = 0; index < count; index++)
        if (fillers[index])
            minyar_pool_deallocate(fillers[index]);
    clear();
    puts("Recovered complete pool after next allocation.");
    return 0;
}
