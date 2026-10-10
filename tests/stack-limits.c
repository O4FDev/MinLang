/* Exercise configured logical limits even when native bounds are unavailable. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#include <stdlib.h>

#ifdef MINYAR_TEST_NO_STACK_BOUNDS
static unsigned stack_queries;
#ifdef _WIN32
#include <windows.h>
static void WINAPI test_stack_limits(PULONG_PTR low, PULONG_PTR high) {
    stack_queries++;
    *low = 0;
    *high = 0;
}
#define GetCurrentThreadStackLimits test_stack_limits
#elif defined(__APPLE__)
#include <pthread.h>
static void *test_stack_address(pthread_t thread) {
    (void)thread;
    stack_queries++;
    return NULL;
}
static size_t test_stack_size(pthread_t thread) {
    (void)thread;
    return 0;
}
#define pthread_get_stackaddr_np test_stack_address
#define pthread_get_stacksize_np test_stack_size
#elif defined(__linux__)
#include <pthread.h>
static int test_stack_attributes(pthread_t thread, pthread_attr_t *attributes) {
    (void)thread;
    (void)attributes;
    stack_queries++;
    return 1;
}
#define pthread_getattr_np test_stack_attributes
#endif
#endif

#include "../runtime/minyar_runtime.c"

int main(int argc, char **argv) {
    if (argc != 2)
        return 2;
    unsigned count = (unsigned)strtoul(argv[1], NULL, 10);
    for (unsigned i = 0; i < count; i++)
        minyar_stack_enter();
    for (unsigned i = 0; i < count; i++)
        minyar_stack_leave();
#ifdef MINYAR_TEST_NO_STACK_BOUNDS
    if (stack_queries != 1)
        return 3;
#endif
    return minyar_call_depth != 0;
}
