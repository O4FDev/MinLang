/* TEST ORACLE ONLY. Production bounded heaps do not drain at process exit.
 * Drain pending debt here to distinguish valid deferred cleanup from leaked
 * ownership. It must never be linked into a production runtime artifact. */
#define MINYAR_BOUNDED_HEAP 1
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>

__attribute__((destructor)) static void check_bounded_program_cleanup(void) {
    assert(rc_frames == NULL);
    while (rc_pending_count) assert(minyar_rc_poll(MINYAR_RC_POLL_BUDGET) > 0);
    assert(rc_object_count == rc_immortal_object_count);
}
