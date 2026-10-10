/* Short domain-boundary checks. RC heaps remain single-owner; only domain
 * token assignment is concurrent. This is not a sustained load benchmark. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#include <assert.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <pthread.h>
#endif
#define MINYAR_RC_TESTING 1
#include "../build/managed-graphs-engine.c"

static void *domain_token(void *output) {
    *(long long *)output = minyar_callback_domain();
    return NULL;
}
static void *foreign_callback(void *object) {
    minyar_callback_check(object);
    abort();
}
static void *foreign_environment(void *object) {
    minyar_callback_check_environment(object);
    abort();
}
typedef struct { void *(*entry)(void *); void *argument; } ThreadJob;
#ifdef _WIN32
typedef HANDLE Thread;
static DWORD WINAPI thread_start(void *input) {
    ThreadJob *job = input;
    job->entry(job->argument);
    return 0;
}
static int thread_create(Thread *thread, ThreadJob *job) {
    *thread = CreateThread(NULL, 0, thread_start, job, 0, NULL);
    return *thread ? 0 : 1;
}
static int thread_join(Thread thread) {
    DWORD result = WaitForSingleObject(thread, INFINITE);
    CloseHandle(thread);
    return result == WAIT_OBJECT_0 ? 0 : 1;
}
#else
typedef pthread_t Thread;
static int thread_create(Thread *thread, ThreadJob *job) {
    return pthread_create(thread, NULL, job->entry, job->argument);
}
static int thread_join(Thread thread) { return pthread_join(thread, NULL); }
#endif
int main(int argc, char **argv) {
    long long owner = minyar_callback_domain();
    assert(owner > 0 && owner == minyar_callback_domain());
    Thread threads[4];
    ThreadJob jobs[4];
    long long tokens[4] = {0};
    for (size_t at = 0; at < 4; at++) {
        jobs[at] = (ThreadJob){domain_token, tokens + at};
        assert(thread_create(threads + at, jobs + at) == 0);
    }
    for (size_t at = 0; at < 4; at++) {
        assert(thread_join(threads[at]) == 0);
        assert(tokens[at] > 0 && tokens[at] != owner);
        for (size_t previous = 0; previous < at; previous++)
            assert(tokens[at] != tokens[previous]);
    }
    MinyarRecord *environment = minyar_record_new(1);
    minyar_record_set(environment, 0, owner);
    MinyarRecord *callback = minyar_record_new(3);
    minyar_record_set_reference(callback, 1, (long long)(uintptr_t)environment);
    minyar_record_set(callback, 2, owner);
    minyar_callback_check(callback);
    minyar_callback_check_environment(environment);
    if (argc > 1) {
        Thread thread;
        ThreadJob job = strcmp(argv[1], "callback") == 0
            ? (ThreadJob){foreign_callback, callback}
            : (ThreadJob){foreign_environment, environment};
        assert(thread_create(&thread, &job) == 0);
        assert(thread_join(thread) == 0);
        abort(); /* A foreign owner check must terminate before returning. */
    }
    minyar_rc_release(callback);
    minyar_rc_release(environment);
    MinyarRecord *ring[48];
    for (size_t at = 0; at < 48; at++) ring[at] = minyar_record_new_traced(1);
    for (size_t at = 0; at < 48; at++)
        minyar_record_set_reference_traced(ring[at], 0, (long long)(uintptr_t)ring[(at + 1) % 48]);
    for (size_t at = 0; at < 48; at++) minyar_rc_release(ring[at]);
    size_t batches = 0;
    while (minyar_callbackruntime_service()) {
        assert(++batches < 10000);
        assert(rc_bounded_last_work <= MINYAR_RC_POLL_BUDGET);
    }
    assert(rc_object_count == rc_immortal_object_count);
    puts("callback domains passed");
    return 0;
}
