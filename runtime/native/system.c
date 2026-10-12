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
#include <fcntl.h>
#include <limits.h>
#include <sched.h>
#include <signal.h>
#include <stdatomic.h>
#include <sys/resource.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

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
