#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#ifdef __linux__
#include <sys/prctl.h>
#endif
#include "../runtime/minyar_native.h"

#define SOAK_PENDING (-1000LL)

static volatile sig_atomic_t pending_interrupt;
static struct sigaction previous_terminate, previous_interrupt;
static int handlers_installed;

static void record_interrupt(int value) { pending_interrupt = value; }

static char **unpack(const MinyarBytes *packed, char **storage) {
    long long count = 0;
    for (long long index = 0; index < packed->byte_length; index++) if (packed->bytes[index] == 0) count++;
    char *copy = malloc((size_t)packed->byte_length + 1);
    char **items = calloc((size_t)count + 1, sizeof *items);
    if (!copy || !items) {
        free(copy);
        free(items);
        return NULL;
    }
    memcpy(copy, packed->bytes, (size_t)packed->byte_length);
    copy[packed->byte_length] = 0;
    long long at = 0;
    for (long long item = 0; item < count; item++) {
        items[item] = copy + at;
        at += (long long)strlen(copy + at) + 1;
    }
    *storage = copy;
    return items;
}

static int open_output(const char *path) {
    return path[0] ? open(path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644) : open("/dev/null", O_WRONLY | O_CLOEXEC);
}

long long minyar_soakobserver_launchNative(const MinyarBytes *argv, const MinyarBytes *envp, const MinyarText *standard, const MinyarText *errors, long long output) {
    char path[4096], target[4096];
    minyar_native_text(errors, path, sizeof path);
    minyar_native_text(standard, target, sizeof target);
    char *argument_storage = NULL, *environment_storage = NULL;
    char **arguments = unpack(argv, &argument_storage);
    char **environment = unpack(envp, &environment_storage);
    int report[2] = {-1, -1};
    long long result = -EINVAL;
    if (!arguments || !environment || !arguments[0] || output < -1 || output > 65535) goto done;
    if (pipe(report) != 0) {
        result = -errno;
        goto done;
    }
    fcntl(report[0], F_SETFD, FD_CLOEXEC);
    fcntl(report[1], F_SETFD, FD_CLOEXEC);
    pid_t child = fork();
    if (child == 0) {
        struct sigaction standard;
        memset(&standard, 0, sizeof standard);
        standard.sa_handler = SIG_DFL;
        sigemptyset(&standard.sa_mask);
        sigaction(SIGPIPE, &standard, NULL);
        sigset_t none;
        sigemptyset(&none);
        sigprocmask(SIG_SETMASK, &none, NULL);
        int code = 0;
        if (setsid() < 0) goto failed;
        int stream = output >= 0 ? (int)output : open_output(target);
        if (stream < 0 || (stream != 1 && dup2(stream, 1) < 0)) goto failed;
        if (stream != 1) close(stream);
        int diagnostics = open_output(path);
        if (diagnostics < 0 || dup2(diagnostics, 2) < 0) goto failed;
        execve(arguments[0], arguments, environment);
    failed:
        code = errno;
        (void)!write(report[1], &code, sizeof code);
        _exit(127);
    }
    if (child < 0) {
        result = -errno;
        goto done;
    }
    close(report[1]);
    report[1] = -1;
    int code = 0;
    ssize_t got;
    do got = read(report[0], &code, sizeof code); while (got < 0 && errno == EINTR);
    if (got == (ssize_t)sizeof code) {
        while (waitpid(child, NULL, 0) < 0 && errno == EINTR) {}
        result = -code;
    } else {
        result = child;
    }
done:
    if (report[0] >= 0) close(report[0]);
    if (report[1] >= 0) close(report[1]);
    free(arguments);
    free(environment);
    free(argument_storage);
    free(environment_storage);
    return result;
}

long long minyar_soakobserver_reapNative(long long process, bool block) {
    int status = 0;
    pid_t result;
    do result = waitpid((pid_t)process, &status, block ? 0 : WNOHANG); while (result < 0 && errno == EINTR);
    if (result == 0) return SOAK_PENDING;
    if (result < 0) return SOAK_PENDING - errno;
    if (WIFEXITED(status)) return WEXITSTATUS(status);
    if (WIFSIGNALED(status)) return -WTERMSIG(status);
    return SOAK_PENDING;
}

long long minyar_soakobserver_installInterrupts(void) {
    if (handlers_installed) return -EBUSY;
    struct sigaction action;
    memset(&action, 0, sizeof action);
    action.sa_handler = record_interrupt;
    sigemptyset(&action.sa_mask);
    pending_interrupt = 0;
    if (sigaction(SIGTERM, &action, &previous_terminate) != 0) return -errno;
    if (sigaction(SIGINT, &action, &previous_interrupt) != 0) {
        int error = errno;
        sigaction(SIGTERM, &previous_terminate, NULL);
        return -error;
    }
    handlers_installed = 1;
    return 0;
}

long long minyar_soakobserver_restoreInterrupts(void) {
    if (!handlers_installed) return 0;
    handlers_installed = 0;
    if (sigaction(SIGTERM, &previous_terminate, NULL) != 0) return -errno;
    if (sigaction(SIGINT, &previous_interrupt, NULL) != 0) return -errno;
    return 0;
}

long long minyar_soakobserver_takeInterrupt(void) {
    long long value = pending_interrupt;
    pending_interrupt = 0;
    return value;
}

long long minyar_soakobserver_disposition(long long value) {
    struct sigaction current;
    if (sigaction((int)value, NULL, &current) != 0) return -errno;
    if (current.sa_handler == SIG_DFL) return 0;
    if (current.sa_handler == SIG_IGN) return 1;
    if (current.sa_handler == record_interrupt) return 2;
    return 3;
}

long long minyar_soakobserver_setDisposition(long long value, long long kind) {
    struct sigaction action;
    memset(&action, 0, sizeof action);
    action.sa_handler = kind == 1 ? SIG_IGN : SIG_DFL;
    sigemptyset(&action.sa_mask);
    return sigaction((int)value, &action, NULL) == 0 ? 0 : -errno;
}

long long minyar_soakobserver_nap(long long milliseconds) {
    if (milliseconds < 0) milliseconds = 0;
    return poll(NULL, 0, (int)milliseconds) < 0 ? -errno : 0;
}

long long minyar_soakobserver_clockTicks(void) { return sysconf(_SC_CLK_TCK); }

long long minyar_soakobserver_pageSize(void) { return sysconf(_SC_PAGESIZE); }

long long minyar_soakobserver_subreaper(long long value) {
#ifdef __linux__
    int previous = 0;
    if (prctl(PR_GET_CHILD_SUBREAPER, &previous, 0, 0, 0) != 0) return -errno;
    if (prctl(PR_SET_CHILD_SUBREAPER, (unsigned long)value, 0, 0, 0) != 0) return -errno;
    return previous;
#else
    (void)value;
    return -ENOTSUP;
#endif
}

long long minyar_soakobserver_loadAverage(long long index) {
    double values[3];
    if (index < 0 || index > 2 || getloadavg(values, 3) != 3) return -1;
    return (long long)(values[index] * 1000000.0);
}
