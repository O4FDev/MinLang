#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>

int main(void) {
    MinyarDepthScope outer, inner;
    assert(minyar_calldepth_remaining() == -1);
    minyar_calldepth_begin(&outer, 2);
    assert(minyar_calldepth_remaining() == 2);
    assert(minyar_recovery_enter());
    assert(minyar_calldepth_remaining() == 1);
    minyar_calldepth_begin(&inner, 100);
    assert(minyar_calldepth_remaining() == 1);
    assert(minyar_recovery_enter());
    assert(!minyar_recovery_enter());
    assert(minyar_recovery_pending());
    minyar_stack_leave();
    assert(minyar_calldepth_end(&inner) == 1);
    assert(!minyar_recovery_pending());
    assert(minyar_calldepth_remaining() == 1);
    assert(minyar_recovery_enter());
    minyar_stack_leave();
    minyar_stack_leave();
    assert(minyar_calldepth_end(&outer) == 0);
    assert(minyar_calldepth_remaining() == -1);
    for (int i = 0; i < 100; ++i) {
        minyar_calldepth_begin(&outer, 0);
        assert(!minyar_recovery_enter());
        assert(minyar_calldepth_end(&outer) == 1);
        minyar_calldepth_begin(&outer, -1);
        assert(!minyar_recovery_enter());
        assert(minyar_calldepth_end(&outer) == 1);
    }
    minyar_calldepth_begin(&outer, 0);
    assert(!minyar_recovery_enter());
    minyar_calldepth_reporting_begin();
    assert(minyar_recovery_enter());
    assert(!minyar_recovery_pending());
    minyar_stack_leave();
    minyar_calldepth_reporting_end();
    assert(minyar_recovery_pending());
    assert(minyar_calldepth_end(&outer) == 1);
    /* Exercise the unknown-native-bounds fallback without recursing in C. */
    minyar_stack_low = minyar_stack_high = 0;
    minyar_stack_bounds_ready = 1;
    minyar_depth_limit = MINYAR_FALLBACK_CALL_DEPTH;
    minyar_calldepth_begin(&outer, 1000000);
    size_t accepted = 0;
    while (minyar_recovery_enter()) accepted++;
    assert(accepted == MINYAR_FALLBACK_CALL_DEPTH);
    while (accepted > 0) { accepted--; minyar_stack_leave(); }
    assert(minyar_calldepth_end(&outer) == 1);
    assert(minyar_call_depth == 0);
    return 0;
}
