#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>

static MINYAR_NO_ADDRESS_SANITIZE void reject_physical(int preflight) {
    unsigned char marker;
    uintptr_t low = minyar_stack_low, high = minyar_stack_high;
    minyar_stack_low = (uintptr_t)&marker - MINYAR_STACK_RESERVE_BYTES + 8192;
    minyar_stack_high = (uintptr_t)&marker + 16384;
    if (preflight) assert(!minyar_calldepth_reporting_begin());
    else assert(!minyar_recovery_enter());
    minyar_stack_low = low;
    minyar_stack_high = high;
}

int main(int argc, char **argv) {
    assert(argc == 2);
    minyar_stack_enter(); /* The compiled main's accepted frame. */
    if (!strcmp(argv[1], "escape")) {
        reject_physical(1);
        assert(minyar_recovery_pending() && !minyar_depth_reporting);
        assert(!minyar_recovery_enter());
        minyar_stack_leave();
        assert(!minyar_call_depth && !minyar_depth_scope);
        puts("escaped pending status 2");
        return 0;
    }
    if (!strcmp(argv[1], "fallback")) {
        minyar_stack_low = minyar_stack_high = 0;
        minyar_stack_bounds_ready = 1;
        minyar_depth_limit = MINYAR_FALLBACK_CALL_DEPTH;
    }
    MinyarDepthScope outer, inner;
    minyar_calldepth_begin(&outer, 100);
    assert(minyar_recovery_enter());
    size_t held = 1;
    if (!strcmp(argv[1], "fallback")) {
        while (minyar_call_depth < MINYAR_FALLBACK_CALL_DEPTH) {
            assert(minyar_recovery_enter());
            held++;
        }
        assert(minyar_calldepth_remaining() == 85);
    }
    size_t base = minyar_call_depth;
    minyar_calldepth_begin(&inner, 100);
    assert(!minyar_recovery_enter());
    assert(minyar_calldepth_end(&inner) == 1);
    assert(!minyar_recovery_pending());
    minyar_calldepth_reporting_begin();
    minyar_calldepth_begin(&inner, 0);
    assert(!minyar_recovery_enter());
    assert(minyar_calldepth_end(&inner) == 1);
    assert(!minyar_recovery_pending());
    /* The real factory's nested guarded calls need room past either cap. */
    for (int i = 0; i < 6; ++i) assert(minyar_recovery_enter());
    for (int i = 0; i < 6; ++i) minyar_stack_leave();
    int propagate = !strcmp(argv[1], "bounded") || !strcmp(argv[1], "physical");
    if (!strcmp(argv[1], "bounded")) {
        size_t accepted = 0;
        while (minyar_recovery_enter()) accepted++;
        assert(accepted == MINYAR_DEPTH_REPORT_FRAMES);
        assert(minyar_recovery_pending());
        while (accepted--) minyar_stack_leave();
    }
    if (!strcmp(argv[1], "physical")) reject_physical(0);
    minyar_calldepth_reporting_end();
    assert(minyar_call_depth == base && minyar_recovery_pending() == propagate);
    while (held--) minyar_stack_leave();
    assert(minyar_calldepth_end(&outer) == propagate);
    minyar_calldepth_begin(&outer, 1);
    assert(minyar_recovery_enter());
    minyar_stack_leave();
    assert(minyar_calldepth_end(&outer) == 0);
    minyar_stack_leave();
    assert(minyar_call_depth == 0 && minyar_depth_scope == NULL && minyar_depth_reporting == 0);
    assert(!minyar_depth_report_base && !minyar_depth_report_parent &&
           !minyar_depth_report_failed && !minyar_depth_escaped);
    puts("nested failure; success; alive");
}
