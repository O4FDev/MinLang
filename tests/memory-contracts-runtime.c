/* TEST ONLY: normal program return must release every owned value. Deferred
 * cleanup is drained here solely to distinguish debt from leaked ownership.
 * Explicit language exit/runtime errors do not unwind, so are checked by the
 * invoking test's exit-status oracle instead. Never ship this runtime. */
#if defined(MINYAR_LAZY_HEAP) && defined(__linux__) && !defined(_DEFAULT_SOURCE)
#define _DEFAULT_SOURCE 1
#endif
#include <stdlib.h>
#include <assert.h>
static int contract_explicit_exit;
static _Noreturn void contract_exit(int status);
#define exit contract_exit
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#undef exit

static _Noreturn void contract_exit(int status) {
    contract_explicit_exit = 1;
    exit(status);
}

__attribute__((destructor)) static void check_memory_contract(void) {
    if (contract_explicit_exit) return;
    assert(rc_frames == NULL);
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count) assert(minyar_rc_poll(MINYAR_RC_POLL_BUDGET) > 0);
#else
    assert(rc_pending_count == 0);
#endif
    assert(rc_object_count == rc_immortal_object_count);
}
