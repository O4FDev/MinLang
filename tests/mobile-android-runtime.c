/* Test-only cleanup runs on the Java-created model worker after ordinary
 * Minyar main returns; the JVM main thread never enters the managed runtime. */
#define MINYAR_RC_TESTING 1
#include "../build/testing/cycle-runtime.c"
#include "../runtime/minyar_stack_frames.h"
#include <assert.h>
#include <stdatomic.h>

extern int main(int, char **) __attribute__((visibility("hidden")));
int minyar_mobile_entry(void) {
    static atomic_flag started = ATOMIC_FLAG_INIT;
    static char name[] = "Minyar Android JNI test";
    static char *arguments[] = {name, NULL};
    if (atomic_flag_test_and_set_explicit(&started, memory_order_relaxed)) return -1;
    return main(1, arguments);
}

void mobile_android_assert_cleanup(void) {
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
    puts("Android model worker ownership cleanup passed");
    fflush(stdout);
}
