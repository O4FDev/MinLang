/* Cache headers must outlive every retired slot, view and cycle field. */
#define MINYAR_RC_TESTING 1
#ifdef MINYAR_TEST_CYCLES
#include "../build/thread-cycle-engine.c"
#else
#include "../runtime/minyar_runtime.c"
#endif
#include <assert.h>
int main(void) {
    rc_thread_domain_init();
    minyar_rc_enter(128);
    MinyarText *integer = minyar_integer_text(12345);
    for (long long i = 0; i < 127; i++) minyar_rc_local(i, integer);
    MinyarText *view = minyar_text_slice(integer, 1, 3);
    assert(minyar_text_length(view) == 2);
    minyar_rc_local_take(127, view);
#ifdef MINYAR_TEST_CYCLES
    MinyarRecord *cycle = minyar_record_new_traced(3);
    minyar_record_set_reference_traced(cycle, 0, (long long)(uintptr_t)cycle);
    minyar_record_set_reference_traced(cycle, 1, (long long)(uintptr_t)integer);
    minyar_record_set_reference_traced(cycle, 2, (long long)(uintptr_t)view);
    minyar_rc_release(cycle);
#endif
    minyar_rc_release(integer);
    minyar_rc_leave();
#if defined(MINYAR_BOUNDED_RC) && MINYAR_RC_POLL_BUDGET < 128
    assert(rc_pending_count); /* The default32 and K1 cannot retire128 slots. */
#endif
    rc_thread_domain_dispose();
    assert(!rc_object_count && !rc_bytes && !rc_immortal_object_count);
#ifdef MINYAR_BOUNDED_RC
    assert(!rc_heap_allocation_count);
#endif
    puts("cache headers survived deferred frame, view and cycle teardown");
}
