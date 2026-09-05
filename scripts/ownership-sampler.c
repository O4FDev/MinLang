/* Optional macOS arm64 diagnostic, linked only into a temporary benchmark.
 * Self-sampling avoids debugger attachment. The signal handler only stores a
 * program counter with lock-free atomics; symbol lookup happens at exit. */
#define _DARWIN_C_SOURCE
#include <assert.h>
#include <dlfcn.h>
#include <signal.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/time.h>
#include <sys/ucontext.h>

#if !defined(__APPLE__) || !defined(__aarch64__)
#error This optional sampler is for macOS arm64 only.
#endif

enum { CAPACITY = 65536 };
static _Atomic(uintptr_t) counters[CAPACITY];
static _Atomic(unsigned) count;

static void sample_pc(int signal, siginfo_t *information, void *context) {
    (void)signal;
    (void)information;
    ucontext_t *state = context;
    unsigned index = atomic_fetch_add_explicit(&count, 1, memory_order_relaxed);
    if (index < CAPACITY)
        atomic_store_explicit(&counters[index],
            __darwin_arm_thread_state64_get_pc(state->uc_mcontext->__ss), memory_order_relaxed);
}

__attribute__((constructor)) static void begin_sampling(void) {
    assert(atomic_is_lock_free(&count) && atomic_is_lock_free(&counters[0]));
    struct sigaction action = {0};
    action.sa_sigaction = sample_pc;
    action.sa_flags = SA_SIGINFO | SA_RESTART;
    sigemptyset(&action.sa_mask);
    assert(sigaction(SIGPROF, &action, NULL) == 0);
    struct itimerval timer = {{0, 1000}, {0, 1000}};
    assert(setitimer(ITIMER_PROF, &timer, NULL) == 0);
}

__attribute__((destructor)) static void finish_sampling(void) {
    struct itimerval timer = {{0, 0}, {0, 0}};
    setitimer(ITIMER_PROF, &timer, NULL);
    sigset_t signals;
    sigemptyset(&signals);
    sigaddset(&signals, SIGPROF);
    sigprocmask(SIG_BLOCK, &signals, NULL);
    unsigned length = atomic_load(&count);
    fprintf(stderr, "MINYAR_SAMPLES\t%u\n", length);
    for (unsigned index = 0; index < length && index < CAPACITY; index++) {
        uintptr_t pc = atomic_load(&counters[index]);
        Dl_info symbol = {0};
        dladdr((void *)pc, &symbol);
        fprintf(stderr, "MINYAR_PC\t%s\t%s\n",
                symbol.dli_fname ? symbol.dli_fname : "unknown",
                symbol.dli_sname ? symbol.dli_sname : "unknown");
    }
}
