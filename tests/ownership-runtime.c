/* Native programs linked with this test runtime must release every owned
 * object before normal process exit. ASan also checks this runtime's accesses. */
#define MINYAR_RC_TESTING
#include "../runtime/minyar_runtime.c"
#include <assert.h>

__attribute__((destructor)) static void check_program_cleanup(void) {
    assert(rc_frames == NULL);
    assert(rc_pending_count == 0);
    assert(rc_object_count == rc_immortal_object_count);
}
