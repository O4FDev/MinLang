/* Process-level services for the `system` package: wall-clock and monotonic time at sub-millisecond resolution,
 * process identity and resident memory, PTY sessions, and signals delivered as socket readiness.
 *
 * Minyar has no signal handling and no wall clock. A server needs both: SIGPIPE must not kill it when a client
 * disconnects mid-write, SIGHUP should reload, SIGCHLD should reap, SIGTERM/SIGINT should trigger an orderly
 * shutdown from inside its event loop, and SQL's CURRENT_TIMESTAMP needs real time. Signal handlers here only call
 * write(2), which is async-signal-safe; the event loop watches the read end of a socketpair like any other socket.
 *
 * Ported from neo-db's native/dbio.c (2026-10-12). */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE 1
#endif
#ifdef __APPLE__
#define _DARWIN_C_SOURCE 1
#include <mach/mach.h>
#endif
#include "../minyar_native.h"
#if defined(__GLIBC__)
#include <malloc.h>
#endif
#include <errno.h>
#include <limits.h>
#include <stdint.h>

/* Text/Bytes-returning operations expose a per-thread -errno. Returned values
 * are copied; callers must serialize changes to the OS environment. */
static _Thread_local int system_error;
long long minyar_system_lastError(void) { return -system_error; }
static long long system_failure(int code) { system_error = code; return -code; }
static bool system_valid_buffer(const MinyarText *value) {
    return value && value->byte_length >= 0 && (uint64_t)value->byte_length <= SIZE_MAX &&
           (value->byte_length == 0 || value->bytes);
}
static char *system_cstring(const MinyarText *value) {
    if (!system_valid_buffer(value) || (uint64_t)value->byte_length >= SIZE_MAX ||
        (value->byte_length && memchr(value->bytes, 0, (size_t)value->byte_length))) {
        system_error = EINVAL; return NULL;
    }
    char *result = malloc((size_t)value->byte_length + 1);
    if (!result) { system_error = ENOMEM; return NULL; }
    if (value->byte_length) memcpy(result, value->bytes, (size_t)value->byte_length);
    result[value->byte_length] = 0;
    return result;
}

#ifdef _WIN32
#include "system_windows.h"
#else
#include <fcntl.h>
#include <sched.h>
#include <signal.h>
#include <stdatomic.h>
#include <sys/resource.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>
#ifdef __APPLE__
#include <crt_externs.h>
#else
extern char **environ;
#endif

long long minyar_system_wallClockMicroseconds(void) {
    struct timespec t;
    clock_gettime(CLOCK_REALTIME, &t);
    return (long long)t.tv_sec * 1000000LL + t.tv_nsec / 1000;
}

long long minyar_system_monotonicNanoseconds(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (long long)t.tv_sec * 1000000000LL + t.tv_nsec;
}

long long minyar_system_processId(void) { return (long long)getpid(); }

/* Threads safe parallel ranges use (the runtime's pool size). Weak: native fixtures that link this file without
 * the Minyar runtime never call it, and get one thread if they do. */
#ifdef _WIN32
long long minyar_parallel_workers(void);
long long minyar_system_parallelWorkers(void) { return minyar_parallel_workers(); }
#else
__attribute__((weak)) long long minyar_parallel_workers(void);
long long minyar_system_parallelWorkers(void) {
    return minyar_parallel_workers ? minyar_parallel_workers() : 1;
}
#endif

/* Current resident set size in bytes, or -errno. */
long long minyar_system_residentBytes(void) {
#ifdef __APPLE__
    mach_task_basic_info_data_t info;
    mach_msg_type_number_t count = MACH_TASK_BASIC_INFO_COUNT;
    if (task_info(mach_task_self(), MACH_TASK_BASIC_INFO, (task_info_t)&info, &count) != KERN_SUCCESS) return -EIO;
    return (long long)info.resident_size;
#else
    FILE *f = fopen("/proc/self/statm", "r");
    if (!f) return -errno;
    long long size = 0, resident = 0;
    int n = fscanf(f, "%lld %lld", &size, &resident);
    fclose(f);
    if (n != 2) return -EIO;
    return resident * (long long)sysconf(_SC_PAGESIZE);
#endif
}

/* Writes to closed sockets then fail with EPIPE instead of killing the process. */
long long minyar_system_ignoreBrokenPipes(void) {
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = SIG_IGN;
    return sigaction(SIGPIPE, &sa, NULL) == 0 ? 0 : -errno;
}

/* Signals arrive as descriptor readiness. One process-owned socketpair carries the native signal number of every
 * delivery; handlers call nothing but write(2), which is async-signal-safe. signalSocket subscribes to any subset of
 * the portable selectors below and returns the read end; shutdownSignalSocket is the TERM/INT subscription servers
 * already use and returns that same descriptor. A subscription is cumulative and idempotent: the socket and each
 * handler are installed once per process, so a second call adds signals and returns the same descriptor. */
enum { SYSTEM_SIGNAL_SELECTORS = 8 };   /* selectors 1..7; index 0 is unused */

static int system_signal_pair[2] = {-1, -1};
_Static_assert(ATOMIC_INT_LOCK_FREE == 2, "signal handlers require lock-free integer atomics");
static _Atomic int system_signal_writer = -1;
static _Atomic unsigned system_signal_readers;
static unsigned char system_signal_subscribed[SYSTEM_SIGNAL_SELECTORS];

/* Selectors are stable package identifiers, never native signal numbers: SIGHUP is 1 everywhere but SIGUSR1 is 10
 * on Linux and 30 on macOS. */
static int system_signal_number(int selector) {
    switch (selector) {
    case 1: return SIGHUP;
    case 2: return SIGINT;
    case 3: return SIGUSR1;
    case 4: return SIGUSR2;
    case 5: return SIGCHLD;
    case 6: return SIGWINCH;
    case 7: return SIGTERM;
    default: return 0;
    }
}
static int system_signal_selector(int number) {
    for (int selector = 1; selector < SYSTEM_SIGNAL_SELECTORS; selector++)
        if (system_signal_number(selector) == number) return selector;
    return 0;
}
static uint64_t system_signal_u64(const unsigned char *bytes) {
    uint64_t value = 0;
    for (unsigned at = 0; at < 8; at++) value |= (uint64_t)bytes[at] << (at * 8);
    return value;
}

static void system_on_signal(int sig) {
    int saved = errno;
    unsigned char byte = (unsigned char)sig;
    atomic_fetch_add(&system_signal_readers, 1);
    int writer = atomic_load(&system_signal_writer);
    if (writer >= 0) {
        ssize_t n = write(writer, &byte, 1);
        (void)n;
    }
    atomic_fetch_sub(&system_signal_readers, 1);
    errno = saved;
}

static void system_signal_release(void) {
    atomic_store(&system_signal_writer, -1);
    system_signal_pair[0] = system_signal_pair[1] = -1;
}

/* The notification socket, created once and shared by every subscription. It is non-blocking and close-on-exec. */
static int system_signal_socket(bool *created) {
    *created = false;
    if (system_signal_pair[0] >= 0) return system_signal_pair[0];
    int sv[2];
    if (socketpair(AF_UNIX, SOCK_STREAM, 0, sv) != 0) return -errno;
    int error = 0;
    for (int at = 0; at < 2; at++) {
        int flags = fcntl(sv[at], F_GETFD);
        if (flags < 0 || fcntl(sv[at], F_SETFD, flags | FD_CLOEXEC) < 0) { error = errno; break; }
        flags = fcntl(sv[at], F_GETFL);
        if (flags < 0 || fcntl(sv[at], F_SETFL, flags | O_NONBLOCK) < 0) { error = errno; break; }
    }
    if (error) { close(sv[0]); close(sv[1]); return -error; }
    system_signal_pair[0] = sv[0];
    system_signal_pair[1] = sv[1];
    atomic_store(&system_signal_writer, sv[1]);
    *created = true;
    return sv[0];
}

/* Undo a subscription that failed part way. A handler installed by the failed call goes back; a socket created by it
 * is closed only once no handler is still inside its write (a signal may have arrived on another thread while this
 * one was masked), because the descriptor could be reused by an allocation afterwards. */
static void system_signal_rollback(bool created, int *numbers, struct sigaction *previous, size_t installed) {
    while (installed) {
        installed -= 1;
        sigaction(numbers[installed], &previous[installed], NULL);
    }
    if (!created) return;
    /* Invalidate first, then let a handler that is already inside its non-blocking write finish before the endpoints
     * are closed and freed for reuse. */
    int reader = system_signal_pair[0], writer = system_signal_pair[1];
    system_signal_release();
    while (atomic_load(&system_signal_readers)) sched_yield();
    close(reader);
    close(writer);
}

/* Install one call's selectors as one transaction: afterwards either every new handler is in place, or the process
 * looks exactly as it did before the call. Handlers are installed with their signals blocked, so none can run before
 * the writer is published. */
static long long system_signal_subscribe(const long long *selectors, size_t count, bool ignore_pipe) {
    system_error = 0;
    int numbers[SYSTEM_SIGNAL_SELECTORS];
    size_t pending = 0;
    sigset_t blocked;
    sigemptyset(&blocked);
    for (size_t at = 0; at < count; at++) {
        int selector = (int)selectors[at];
        int number = system_signal_number(selector);
        if (!number) return system_failure(EINVAL);
        if (system_signal_subscribed[selector]) continue;
        numbers[pending] = number;
        sigaddset(&blocked, number);
        pending += 1;
    }
    bool created = false;
    int descriptor = system_signal_socket(&created);
    if (descriptor < 0) return system_failure(-descriptor);
    if (!pending) return descriptor;
    sigset_t previous_mask;
    if (sigprocmask(SIG_BLOCK, &blocked, &previous_mask) != 0) {
        int error = errno;
        system_signal_rollback(created, numbers, NULL, 0);
        return system_failure(error);
    }
    struct sigaction previous[SYSTEM_SIGNAL_SELECTORS], action;
    size_t installed = 0;
    int error = 0;
    for (size_t at = 0; at < pending && !error; at++)
        if (sigaction(numbers[at], NULL, &previous[at]) != 0) error = errno;
    memset(&action, 0, sizeof(action));
    action.sa_handler = system_on_signal;
    action.sa_flags = SA_RESTART;
    sigemptyset(&action.sa_mask);
    for (size_t at = 0; at < pending && !error; at++) {
        if (sigaction(numbers[at], &action, NULL) != 0) error = errno;
        else installed += 1;
    }
    /* SIGPIPE belongs to the same transaction: a server that cannot ignore it must not look half subscribed. */
    struct sigaction previous_pipe;
    bool pipe_installed = false;
    if (!error && ignore_pipe) {
        memset(&action, 0, sizeof(action));
        action.sa_handler = SIG_IGN;
        if (sigaction(SIGPIPE, NULL, &previous_pipe) != 0) error = errno;
        else if (sigaction(SIGPIPE, &action, NULL) != 0) error = errno;
        else pipe_installed = true;
    }
    if (!error && sigprocmask(SIG_SETMASK, &previous_mask, NULL) != 0) error = errno;
    if (error) {
        if (pipe_installed) sigaction(SIGPIPE, &previous_pipe, NULL);
        system_signal_rollback(created, numbers, previous, installed);
        sigprocmask(SIG_SETMASK, &previous_mask, NULL);
        return system_failure(error);
    }
    for (size_t at = 0; at < installed; at++)
        system_signal_subscribed[system_signal_selector(numbers[at])] = 1;
    return descriptor;
}

/* Subscribe to the portable selectors packed as little-endian u64 and return the socket that becomes readable. */
long long minyar_system_signalSocketNative(const MinyarBytes *signals) {
    if (!system_valid_buffer(signals) || signals->byte_length % 8) return system_failure(EINVAL);
    size_t count = (size_t)signals->byte_length / 8;
    if (count > SYSTEM_SIGNAL_SELECTORS - 1) return system_failure(EINVAL);
    long long selectors[SYSTEM_SIGNAL_SELECTORS - 1];
    for (size_t at = 0; at < count; at++) {
        uint64_t value = system_signal_u64(signals->bytes + at * 8);
        if (value < 1 || value >= SYSTEM_SIGNAL_SELECTORS || !system_signal_number((int)value))
            return system_failure(EINVAL);
        selectors[at] = (long long)value;
    }
    return system_signal_subscribe(selectors, count, false);
}

/* SIGTERM/SIGINT as readiness, ignoring SIGPIPE (idempotent; returns the shared notification socket). */
long long minyar_system_shutdownSignalSocket(void) {
    static const long long signals[] = {7, 2};
    return system_signal_subscribe(signals, 2, true);
}

/* The next delivered signal's selector (1..7), 0 when none is pending, or -errno. */
long long minyar_system_readSignal(long long handle) {
    if (system_signal_pair[0] < 0 || handle != system_signal_pair[0]) return -EBADF;
    unsigned char byte = 0;
    for (;;) {
        ssize_t n = read(system_signal_pair[0], &byte, 1);
        if (n == 1) return system_signal_selector(byte);
        if (n == 0) return 0;
        if (errno == EINTR) continue;
        if (errno == EAGAIN || errno == EWOULDBLOCK) return 0;
        return -errno;
    }
}

/* The native signal number for a selector, for sendSignal and for raising one from a test. */
long long minyar_system_signalNumber(long long selector) {
    int number = selector > 0 && selector < SYSTEM_SIGNAL_SELECTORS ? system_signal_number((int)selector) : 0;
    return number ? number : system_failure(EINVAL);
}

/* Read every pending signal byte; returns the last native signal number received (15 SIGTERM, 2 SIGINT) or 0. */
long long minyar_system_drainShutdownSignals(void) {
    if (system_signal_pair[0] < 0) return 0;
    unsigned char buf[64];
    long long last = 0;
    for (;;) {
        ssize_t n = read(system_signal_pair[0], buf, sizeof(buf));
        if (n > 0) {
            last = buf[n - 1];
            continue;
        }
        if (n < 0 && errno == EINTR) continue;
        break;
    }
    return last;
}

long long minyar_system_sendSignal(long long pid, long long sig) {
    pid_t native_pid = (pid_t)pid;
    int native_signal = (int)sig;
    if ((long long)native_pid != pid || (long long)native_signal != sig) return -EINVAL;
    return kill(native_pid, native_signal) == 0 ? 0 : -errno;
}

/* Unbuffered write of text to standard error (diagnostics that must not mix with stdout data). */
long long minyar_system_writeStandardError(const MinyarText *text) {
    if (!system_valid_buffer(text)) return -EINVAL;
    long long done = 0;
    while (text && done < text->byte_length) {
        ssize_t n = write(2, text->bytes + done, (size_t)(text->byte_length - done));
        if (n < 0) {
            if (errno == EINTR) continue;
            return -errno;
        }
        if (n == 0) return -EIO;
        done += n;
    }
    return done;
}

/* Raise the soft open-file limit to the hard limit (servers holding many sockets). Returns the new soft limit. */
long long minyar_system_releaseFreeMemory(void) {
#if defined(__GLIBC__)
    return malloc_trim(0) ? 1 : 0;
#else
    return 0;
#endif
}

long long minyar_system_raiseOpenFileLimit(void) {
    struct rlimit r;
    if (getrlimit(RLIMIT_NOFILE, &r) != 0) return -errno;
    rlim_t want = r.rlim_max;
#ifdef __APPLE__
    if (want == RLIM_INFINITY || want > (rlim_t)OPEN_MAX) want = OPEN_MAX; /* macOS rejects larger soft limits */
#endif
    if (r.rlim_cur < want) {
        r.rlim_cur = want;
        if (setrlimit(RLIMIT_NOFILE, &r) != 0) return -errno;
    }
    return r.rlim_cur == RLIM_INFINITY ? 9223372036854775807LL : (long long)r.rlim_cur;
}

MinyarText *minyar_system_getenv(const MinyarText *name) {
    system_error = 0;
    char *key = system_cstring(name);
    const char *value = NULL;
    if (key) {
        if (!*key || strchr(key, '=')) system_error = EINVAL;
        else { value = getenv(key); if (!value) system_error = ENOENT; }
    }
    MinyarText *result = minyar_native_copy_text((const unsigned char *)(value ? value : ""),
                                               value ? (long long)strlen(value) : 0);
    free(key);
    return result;
}
MinyarBytes *minyar_system_environmentEntries(void) {
    system_error = 0;
#ifdef __APPLE__
    char **entries = *_NSGetEnviron();
#else
    char **entries = environ;
#endif
    size_t length = 0;
    for (char **at = entries; at && *at; at++) {
        size_t count = strlen(*at) + 1;
        if (count > (size_t)LLONG_MAX - length) {
            system_error = EOVERFLOW; return minyar_bytes_new(0);
        }
        length += count;
    }
    MinyarBytes *result = minyar_bytes_new((long long)length);
    unsigned char *out = (unsigned char *)result->bytes;
    for (char **at = entries; at && *at; at++) {
        size_t count = strlen(*at) + 1;
        memcpy(out, *at, count); out += count;
    }
    return result;
}
/* Package resource identifiers are stable across OSes, not raw RLIMIT_* values. */
static int system_resource(long long resource) {
    switch (resource) {
    case 0: return RLIMIT_NOFILE;
    case 1: return RLIMIT_CORE;
    case 2: return RLIMIT_CPU;
    case 3: return RLIMIT_DATA;
    case 4: return RLIMIT_STACK;
#ifdef RLIMIT_AS
    case 5: return RLIMIT_AS;
#else
    case 5: system_error = ENOTSUP; return -1;
#endif
    default: system_error = EINVAL; return -1;
    }
}
static long long system_limit_value(rlim_t value) {
    if (value == RLIM_INFINITY) return LLONG_MAX;
    if ((uintmax_t)value > LLONG_MAX) return system_failure(EOVERFLOW);
    return (long long)value;
}
static long long system_get_limit(long long resource, bool hard) {
    system_error = 0;
    int native = system_resource(resource);
    if (native < 0) return -system_error;
    struct rlimit limit;
    if (getrlimit(native, &limit)) return system_failure(errno);
    return system_limit_value(hard ? limit.rlim_max : limit.rlim_cur);
}
long long minyar_system_getSoftLimit(long long resource) { return system_get_limit(resource, false); }
long long minyar_system_getHardLimit(long long resource) { return system_get_limit(resource, true); }
long long minyar_system_setResourceLimit(long long resource, long long soft, long long hard) {
    system_error = 0;
    int native = system_resource(resource);
    if (native < 0) return -system_error;
    if (soft < 0 || hard < 0 || soft > hard) return system_failure(EINVAL);
    struct rlimit limit = {soft == LLONG_MAX ? RLIM_INFINITY : (rlim_t)soft,
                           hard == LLONG_MAX ? RLIM_INFINITY : (rlim_t)hard};
    if ((soft != LLONG_MAX && ((uintmax_t)limit.rlim_cur != (uintmax_t)soft || limit.rlim_cur == RLIM_INFINITY)) ||
        (hard != LLONG_MAX && ((uintmax_t)limit.rlim_max != (uintmax_t)hard || limit.rlim_max == RLIM_INFINITY)))
        return system_failure(EOVERFLOW);
    return setrlimit(native, &limit) ? system_failure(errno) : 0;
}
#endif

#include "system_terminal.h"
#include "system_process.h"
