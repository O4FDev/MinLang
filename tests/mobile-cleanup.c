/* Test-only ownership oracle. Use the generated production cycle engine,
 * including the compiler-private stack owner ABI selected by the runner. */
#define MINYAR_RC_TESTING 1
#include "../build/testing/cycle-runtime.c"
#include "../runtime/minyar_stack_frames.h"
#include <assert.h>

void mobile_bridge_assert_finished(void);

__attribute__((destructor)) static void mobile_check_cleanup(void) {
    mobile_bridge_assert_finished();
    assert(rc_frames == NULL);
    size_t steps = 0;
    while (minyar_callbackruntime_service()) {
        assert(++steps < 100000);
#ifdef MINYAR_BOUNDED_RC
        assert(rc_bounded_last_work <= MINYAR_RC_POLL_BUDGET);
#endif
    }
    assert(rc_pending_count == 0 && rc_cycle_pending == 0);
    assert(rc_object_count == rc_immortal_object_count);
}
