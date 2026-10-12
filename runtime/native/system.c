/* Process-level services for the `system` package: wall-clock and monotonic time at sub-millisecond resolution,
 * process identity and resident memory, and shutdown signals delivered as socket readiness.
 *
 * Minyar has no signal handling and no wall clock. A server needs both: SIGPIPE must not kill it when a client
 * disconnects mid-write, SIGTERM/SIGINT should trigger an orderly shutdown from inside its event loop, and SQL's
 * CURRENT_TIMESTAMP needs real time. Signal handlers here only call write(2), which is async-signal-safe; the
 * event loop watches the read end of a socketpair like any other socket.
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

static int system_signal_pair[2] = {-1, -1};
_Static_assert(ATOMIC_INT_LOCK_FREE == 2, "shutdown handlers require lock-free integer atomics");
static _Atomic int system_signal_writer = -1;
static _Atomic unsigned system_signal_readers;

static void system_on_shutdown(int sig) {
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

/* Install SIGTERM/SIGINT handlers and return a socket that becomes readable when one arrives (idempotent). */
long long minyar_system_shutdownSignalSocket(void) {
    if (system_signal_pair[0] >= 0) return system_signal_pair[0];
    int sv[2];
    if (socketpair(AF_UNIX, SOCK_STREAM, 0, sv) != 0) return -errno;
    int error;
    for (int i = 0; i < 2; i++) {
        int flags = fcntl(sv[i], F_GETFD);
        if (flags < 0 || fcntl(sv[i], F_SETFD, flags | FD_CLOEXEC) < 0) goto fail_descriptors;
        flags = fcntl(sv[i], F_GETFL);
        if (flags < 0 || fcntl(sv[i], F_SETFL, flags | O_NONBLOCK) < 0) goto fail_descriptors;
    }
    sigset_t blocked, previous_mask;
    sigemptyset(&blocked);
    sigaddset(&blocked, SIGTERM); sigaddset(&blocked, SIGINT); sigaddset(&blocked, SIGPIPE);
    if (sigprocmask(SIG_BLOCK, &blocked, &previous_mask) != 0) goto fail_descriptors;
    struct sigaction old_term, old_int, old_pipe;
    bool installed_term = false, installed_int = false, installed_pipe = false;
    if (sigaction(SIGTERM, NULL, &old_term) != 0 || sigaction(SIGINT, NULL, &old_int) != 0 ||
        sigaction(SIGPIPE, NULL, &old_pipe) != 0) goto fail_handlers;
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = system_on_shutdown;
    sa.sa_flags = SA_RESTART;
    sigemptyset(&sa.sa_mask);
    if (sigaction(SIGTERM, &sa, NULL) != 0) goto fail_handlers;
    installed_term = true;
    if (sigaction(SIGINT, &sa, NULL) != 0) goto fail_handlers;
    installed_int = true;
    long long pipe_status = minyar_system_ignoreBrokenPipes();
    if (pipe_status) { errno = (int)-pipe_status; goto fail_handlers; }
    installed_pipe = true;
    /* The handler sees no endpoint until every installation step succeeds.
     * Failed transactions leave the writer unpublished throughout rollback. */
    system_signal_pair[0] = sv[0];
    system_signal_pair[1] = sv[1];
    atomic_store(&system_signal_writer, sv[1]);
    if (sigprocmask(SIG_SETMASK, &previous_mask, NULL) != 0) {
        atomic_store(&system_signal_writer, -1);
        system_signal_pair[0] = system_signal_pair[1] = -1;
        goto fail_handlers;
    }
    return system_signal_pair[0];
fail_handlers:
    error = errno;
    if (installed_pipe) sigaction(SIGPIPE, &old_pipe, NULL);
    if (installed_int) sigaction(SIGINT, &old_int, NULL);
    if (installed_term) sigaction(SIGTERM, &old_term, NULL);
    /* A handler may run on an existing native syncer thread while this owner
     * is masked. Invalidate first, then let its nonblocking write finish
     * before closing an endpoint that another allocation could reuse. */
    while (atomic_load(&system_signal_readers)) sched_yield();
    close(sv[0]); close(sv[1]);
    sigprocmask(SIG_SETMASK, &previous_mask, NULL);
    return -error;
fail_descriptors:
    error = errno;
    close(sv[0]); close(sv[1]);
    return -error;
}

/* Read every pending signal byte; returns the last signal number received (15 SIGTERM, 2 SIGINT) or 0. */
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

#include "system_process.h"
