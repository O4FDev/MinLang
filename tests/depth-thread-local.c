/* Depth-only dependency test: no managed allocation or collector access. */
#include "../runtime/minyar_runtime.c"
#include <assert.h>
#include <pthread.h>
static pthread_mutex_t depth_mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t depth_condition = PTHREAD_COND_INITIALIZER;
static int depth_ready;

static void *guarded_thread(void *unused) {
    (void)unused;
    assert(minyar_call_depth == 0);
    assert(minyar_stack_bounds_ready == 0);
    assert(minyar_depth_limit == 0);
    for (int i = 0; i < 80; ++i) minyar_stack_enter();
    assert(minyar_call_depth == 80);
    assert(minyar_stack_bounds_ready == 1);
    assert(minyar_stack_high > minyar_stack_low);
    assert(pthread_mutex_lock(&depth_mutex) == 0);
    depth_ready++;
    assert(pthread_cond_broadcast(&depth_condition) == 0);
    while (depth_ready < 4) assert(pthread_cond_wait(&depth_condition, &depth_mutex) == 0);
    assert(pthread_mutex_unlock(&depth_mutex) == 0);
    assert(minyar_call_depth == 80);
    for (int i = 0; i < 80; ++i) minyar_stack_leave();
    assert(minyar_call_depth == 0);
    return NULL;
}

int main(void) {
    for (int round = 0; round < 8; ++round) {
        pthread_t threads[4];
        depth_ready = 0;
        for (int i = 0; i < 4; ++i) assert(pthread_create(&threads[i], NULL, guarded_thread, NULL) == 0);
        for (int i = 0; i < 4; ++i) assert(pthread_join(threads[i], NULL) == 0);
        assert(minyar_call_depth == 0);
        assert(minyar_stack_low == 0 && minyar_stack_high == 0);
        assert(minyar_stack_bounds_ready == 0 && minyar_depth_limit == 0);
    }
    return 0;
}
