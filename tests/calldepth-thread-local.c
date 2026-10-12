#include "../runtime/minyar_runtime.c"
#include <assert.h>
#include <pthread.h>
static pthread_mutex_t scope_mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t scope_condition = PTHREAD_COND_INITIALIZER;
static int scope_ready;

static void *scope_thread(void *argument) {
    size_t limit = (size_t)argument;
    MinyarDepthScope scope;
    assert(minyar_calldepth_remaining() == -1);
    assert(!minyar_depth_report_base && !minyar_depth_report_parent &&
           !minyar_depth_report_failed && !minyar_depth_escaped);
    minyar_calldepth_begin(&scope, (long long)limit);
    for (size_t i = 0; i < limit; ++i) assert(minyar_recovery_enter());
    assert(!minyar_recovery_enter());
    assert(minyar_recovery_pending());
    if (limit == 3) minyar_calldepth_reporting_begin();
    assert(pthread_mutex_lock(&scope_mutex) == 0);
    scope_ready++;
    assert(pthread_cond_broadcast(&scope_condition) == 0);
    while (scope_ready < 4) assert(pthread_cond_wait(&scope_condition, &scope_mutex) == 0);
    assert(pthread_mutex_unlock(&scope_mutex) == 0);
    if (limit == 3) {
        assert(minyar_depth_reporting == 1);
        assert(!minyar_recovery_pending());
        minyar_calldepth_reporting_end();
    } else {
        assert(minyar_depth_reporting == 0);
    }
    assert(minyar_recovery_pending());
    assert(minyar_call_depth == limit);
    while (limit--) minyar_stack_leave();
    assert(minyar_calldepth_end(&scope) == 1);
    assert(!minyar_recovery_pending());
    assert(minyar_calldepth_remaining() == -1);
    return NULL;
}

int main(void) {
    pthread_t threads[4];
    for (size_t i = 0; i < 4; ++i)
        assert(pthread_create(&threads[i], NULL, scope_thread, (void *)(i * 2 + 3)) == 0);
    for (int i = 0; i < 4; ++i) assert(pthread_join(threads[i], NULL) == 0);
    assert(minyar_call_depth == 0);
    assert(minyar_depth_scope == NULL && minyar_depth_reporting == 0);
    return 0;
}
