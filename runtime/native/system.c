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
#include <signal.h>
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

static void system_on_shutdown(int sig) {
    int saved = errno;
    unsigned char byte = (unsigned char)sig;
    ssize_t n = write(system_signal_pair[1], &byte, 1);
    (void)n;
    errno = saved;
}

/* Install SIGTERM/SIGINT handlers and return a socket that becomes readable when one arrives (idempotent). */
long long minyar_system_shutdownSignalSocket(void) {
    if (system_signal_pair[0] >= 0) return system_signal_pair[0];
    int sv[2];
    if (socketpair(AF_UNIX, SOCK_STREAM, 0, sv) != 0) return -errno;
    for (int i = 0; i < 2; i++) {
        fcntl(sv[i], F_SETFD, FD_CLOEXEC);
        fcntl(sv[i], F_SETFL, fcntl(sv[i], F_GETFL) | O_NONBLOCK);
    }
    system_signal_pair[0] = sv[0];
    system_signal_pair[1] = sv[1];
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = system_on_shutdown;
    sa.sa_flags = SA_RESTART;
    sigemptyset(&sa.sa_mask);
    if (sigaction(SIGTERM, &sa, NULL) != 0 || sigaction(SIGINT, &sa, NULL) != 0) return -errno;
    minyar_system_ignoreBrokenPipes();
    return system_signal_pair[0];
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
    return kill((pid_t)pid, (int)sig) == 0 ? 0 : -errno;
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
