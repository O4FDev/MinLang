/*
 * Guard-page stack overflow detection.
 *
 * On hosted Linux and macOS, generated functions carry no per-call depth
 * counter. Every thread stack the language runs on ends in an inaccessible
 * guard region (the kernel's gap for the main thread, a 1 MiB guard for the
 * threads the runtime starts), wider than any language frame, so running out
 * of stack faults inside that region. A SIGSEGV/SIGBUS handler on
 * an alternate signal stack recognises a fault there and reports the same
 * call-depth failure the counter did; any other fault goes to the previous
 * handler or the default action.
 *
 * The main thread installs this from minyar_initialize_arguments with a
 * mapped alternate stack. Each thread the runtime starts for language code
 * takes a pooled alternate stack on entry and returns it on exit: one
 * sigaltstack call each way, about 0.3 us. Recoverable call-depth programs
 * (calldepth.run) and targets without guard pages (WebAssembly, freestanding)
 * keep the exact counter in minyar_stack_enter.
 */
#if (defined(__linux__) || defined(__APPLE__)) && (!defined(__STDC_HOSTED__) || __STDC_HOSTED__) && \
    !defined(__wasm__)
#define MINYAR_STACK_GUARD 1
#include <sys/mman.h>
#include <unistd.h>

/* The fault addresses that count as running out of this thread's stack. */
static _Thread_local uintptr_t minyar_guard_low, minyar_guard_high;
static struct sigaction minyar_guard_previous[2];
static pthread_once_t minyar_guard_once = PTHREAD_ONCE_INIT;
static int minyar_guard_reported;

/* Enough for the stop report: message, stack trace and exit handlers. */
#define MINYAR_GUARD_ALTSTACK_BYTES (64u * 1024u)
/* Generated code does not probe its frames, so a frame must not be able to
 * step over a guard into other memory. Threads the runtime starts get a guard
 * larger than any language frame; Linux keeps a 1 MiB gap below the main
 * stack and refuses to grow it past its limit. A fault up to this far below
 * the lowest usable stack address is stack exhaustion. */
#define MINYAR_GUARD_BELOW_BYTES (1024u * 1024u)
/* Some thread libraries report their guard inside the stack: a fault this far
 * above the lowest usable address also counts. */
#define MINYAR_GUARD_ABOVE_BYTES (64u * 1024u)

static void minyar_guard_forward(int signal, siginfo_t *info, void *context) {
    struct sigaction *previous = &minyar_guard_previous[signal == SIGBUS];
    if ((previous->sa_flags & SA_SIGINFO) && previous->sa_sigaction) {
        previous->sa_sigaction(signal, info, context);
        return;
    }
    if (!(previous->sa_flags & SA_SIGINFO) && previous->sa_handler != SIG_DFL &&
        previous->sa_handler != SIG_IGN) {
        previous->sa_handler(signal);
        return;
    }
    /* Default action: returning re-executes the faulting instruction, which
     * now ends the process with the original signal. A sent signal has no
     * instruction to repeat, so raise it again. */
    struct sigaction fallback;
    memset(&fallback, 0, sizeof fallback);
    fallback.sa_handler = SIG_DFL;
    sigemptyset(&fallback.sa_mask);
    sigaction(signal, &fallback, NULL);
    if (info->si_code <= 0) raise(signal);
}

static void minyar_guard_handler(int signal, siginfo_t *info, void *context) {
    uintptr_t address = (uintptr_t)info->si_addr;
    if (minyar_guard_high && address >= minyar_guard_low && address < minyar_guard_high) {
        /* Parallel workers can exhaust their stacks together: one reports,
         * the others wait for it to end the process. */
        if (__atomic_exchange_n(&minyar_guard_reported, 1, __ATOMIC_ACQ_REL))
            for (;;) pause();
        minyar_stop("the program exceeded the maximum call depth.");
    }
    minyar_guard_forward(signal, info, context);
}

static void minyar_guard_install_handlers(void) {
    struct sigaction action;
    memset(&action, 0, sizeof action);
    action.sa_sigaction = minyar_guard_handler;
    action.sa_flags = SA_SIGINFO | SA_ONSTACK;
    sigemptyset(&action.sa_mask);
    sigaction(SIGSEGV, &action, &minyar_guard_previous[0]);
    sigaction(SIGBUS, &action, &minyar_guard_previous[1]);
}

static void minyar_guard_set_range(uintptr_t low, uintptr_t below, uintptr_t above) {
    pthread_once(&minyar_guard_once, minyar_guard_install_handlers);
    minyar_guard_low = low > below ? low - below : 0;
    minyar_guard_high = low + above;
}

/* An alternate stack someone else installed (a host, a sanitizer) is kept. */
static int minyar_guard_has_altstack(void) {
    stack_t current;
    return sigaltstack(NULL, &current) == 0 && !(current.ss_flags & SS_DISABLE) &&
           current.ss_size >= MINYAR_GUARD_ALTSTACK_BYTES;
}

/* The main thread: exact bounds and a mapped alternate stack, once per process. */
static void minyar_stack_guard_attach(void) {
    if (minyar_guard_high) return;
    /* Query directly: the counter's bounds are shared by every thread in a
     * runtime built without managed threads. */
    uintptr_t low = 0, high = 0;
    minyar_query_stack_bounds(&low, &high);
    if (!low || !high) return;
    uintptr_t below = MINYAR_GUARD_BELOW_BYTES, above = MINYAR_GUARD_ABOVE_BYTES;
#ifdef __linux__
    {
        pthread_attr_t attributes;
        size_t guard = 0;
        if (pthread_getattr_np(pthread_self(), &attributes) == 0) {
            if (pthread_attr_getguardsize(&attributes, &guard) == 0) {
                if (guard > below) below = guard;
                if (guard > above) above = guard;
            }
            pthread_attr_destroy(&attributes);
        }
    }
#endif
    if (!minyar_guard_has_altstack()) {
        size_t page = (size_t)sysconf(_SC_PAGESIZE);
        size_t bytes = MINYAR_GUARD_ALTSTACK_BYTES;
        if (bytes < (size_t)SIGSTKSZ) bytes = (size_t)SIGSTKSZ;
        bytes = (bytes + page - 1) / page * page;
        /* One inaccessible page below catches a handler that overruns it. */
        unsigned char *mapping = mmap(NULL, bytes + page, PROT_READ | PROT_WRITE,
                                      MAP_PRIVATE | MAP_ANON, -1, 0);
        if (mapping == MAP_FAILED) return;
        if (mprotect(mapping, page, PROT_NONE) != 0) {
            munmap(mapping, bytes + page);
            return;
        }
        stack_t alternate;
        memset(&alternate, 0, sizeof alternate);
        alternate.ss_sp = mapping + page;
        alternate.ss_size = bytes;
        if (sigaltstack(&alternate, NULL) != 0) {
            munmap(mapping, bytes + page);
            return;
        }
    }
    minyar_guard_set_range(low, below, above);
}

/* The stack size of threads started with minyar_guarded_thread_attributes;
 * zero when those attributes could not be made. */
static size_t minyar_guard_thread_stack_bytes;
static _Thread_local void *minyar_guard_thread_altstack;
/* Alternate stacks of finished threads, reused so that starting a thread
 * neither maps memory nor faults in fresh pages; linked through their first
 * word while unused. */
static pthread_mutex_t minyar_guard_pool_lock = PTHREAD_MUTEX_INITIALIZER;
static void *minyar_guard_pool;

/* Attributes for a thread that runs language code: a guard no frame skips. */
static pthread_attr_t *minyar_guarded_thread_attributes(pthread_attr_t *attributes) {
    size_t bytes = 0;
    if (pthread_attr_init(attributes) != 0) return NULL;
    if (pthread_attr_setguardsize(attributes, MINYAR_GUARD_BELOW_BYTES) != 0 ||
        pthread_attr_getstacksize(attributes, &bytes) != 0) {
        pthread_attr_destroy(attributes);
        __atomic_store_n(&minyar_guard_thread_stack_bytes, 0, __ATOMIC_RELAXED);
        return NULL;
    }
    __atomic_store_n(&minyar_guard_thread_stack_bytes, bytes, __ATOMIC_RELAXED);
    return attributes;
}

/* A runtime-started thread, first thing in its entry function: one pooled
 * alternate stack and one sigaltstack call, no bounds query. The entry frame
 * is within a few KiB of the stack's top, so its address minus the configured
 * size lies just below the lowest usable address, well inside the recognised
 * range. Threads started without the attributes query their bounds. */
static void minyar_stack_guard_attach_thread(void) {
    size_t stack = __atomic_load_n(&minyar_guard_thread_stack_bytes, __ATOMIC_RELAXED);
    uintptr_t frame = (uintptr_t)__builtin_frame_address(0), low = 0, high = 0;
    if (stack && frame > stack) low = frame - stack;
    else minyar_query_stack_bounds(&low, &high);
    if (!low) return;
#if defined(__SANITIZE_ADDRESS__) || defined(__SANITIZE_THREAD__) || \
    (defined(__has_feature) && (__has_feature(address_sanitizer) || __has_feature(thread_sanitizer) || __has_feature(memory_sanitizer)))
    /* Sanitizers give their threads an alternate stack and unmap it at exit. */
    if (minyar_guard_has_altstack()) {
        minyar_guard_set_range(low, MINYAR_GUARD_BELOW_BYTES, MINYAR_GUARD_ABOVE_BYTES);
        return;
    }
#endif
    pthread_mutex_lock(&minyar_guard_pool_lock);
    void *storage = minyar_guard_pool;
    if (storage) minyar_guard_pool = *(void **)storage;
    pthread_mutex_unlock(&minyar_guard_pool_lock);
    if (!storage && !(storage = malloc(MINYAR_GUARD_ALTSTACK_BYTES))) return;
    stack_t alternate;
    memset(&alternate, 0, sizeof alternate);
    alternate.ss_sp = storage;
    alternate.ss_size = MINYAR_GUARD_ALTSTACK_BYTES;
    if (sigaltstack(&alternate, NULL) != 0) {
        free(storage);
        return;
    }
    minyar_guard_thread_altstack = storage;
    minyar_guard_set_range(low, MINYAR_GUARD_BELOW_BYTES, MINYAR_GUARD_ABOVE_BYTES);
}

/* Last thing before a runtime-started thread's entry returns. */
static void minyar_stack_guard_detach(void) {
    minyar_guard_low = minyar_guard_high = 0;
    void *storage = minyar_guard_thread_altstack;
    if (!storage) return;
    minyar_guard_thread_altstack = NULL;
    stack_t disable;
    memset(&disable, 0, sizeof disable);
    disable.ss_flags = SS_DISABLE;
    if (sigaltstack(&disable, NULL) != 0) return; /* still in use: keep it */
    pthread_mutex_lock(&minyar_guard_pool_lock);
    *(void **)storage = minyar_guard_pool;
    minyar_guard_pool = storage;
    pthread_mutex_unlock(&minyar_guard_pool_lock);
}
#else
static void minyar_stack_guard_attach(void) {}
static void minyar_stack_guard_attach_thread(void) {}
static void minyar_stack_guard_detach(void) {}
#if defined(__linux__) || defined(__APPLE__)
static pthread_attr_t *minyar_guarded_thread_attributes(pthread_attr_t *attributes) {
    (void)attributes;
    return NULL;
}
#endif
#endif
