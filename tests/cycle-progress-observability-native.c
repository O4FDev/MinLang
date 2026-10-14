#define _GNU_SOURCE 1
#include "../runtime/minyar_native.h"
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <math.h>
#include <signal.h>
#include <stdint.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#ifdef __linux__
#include <sys/prctl.h>
#endif

static char *copy_text(const MinyarText *text) {
    char *result = malloc((size_t)text->byte_length + 1);
    if (!result) return NULL;
    memcpy(result, text->bytes, (size_t)text->byte_length);
    result[text->byte_length] = 0;
    return result;
}

static char **split_vector(const MinyarBytes *packed, char **storage) {
    long long count = 0;
    for (long long index = 0; index < packed->byte_length; ++index) if (!packed->bytes[index]) count++;
    char **items = calloc((size_t)count + 1, sizeof(char *));
    *storage = malloc((size_t)packed->byte_length + 1);
    if (!items || !*storage) { free(items); return NULL; }
    memcpy(*storage, packed->bytes, (size_t)packed->byte_length);
    long long item = 0, start = 0;
    for (long long index = 0; index < packed->byte_length; ++index) {
        if (!(*storage)[index]) { items[item++] = *storage + start; start = index + 1; }
    }
    return items;
}

static void put64(MinyarBytes *bytes, int slot, long long value) {
    unsigned char *target = (unsigned char *)bytes->bytes + slot * 8;
    unsigned long long raw = (unsigned long long)value;
    for (int index = 0; index < 8; ++index) target[index] = (unsigned char)(raw >> (8 * index));
}

static bool valid_descriptor(long long value) {
    return value >= 0 && value <= INT_MAX;
}

static int redirect(const char *path, int flags, int target) {
    int descriptor = open(path, flags, 0600);
    if (descriptor < 0) return errno;
    if (descriptor != target) {
        if (dup2(descriptor, target) < 0) return errno;
        close(descriptor);
    }
    return 0;
}

static void report(int descriptor, int value) {
    ssize_t written;
    do written = write(descriptor, &value, sizeof(value)); while (written < 0 && errno == EINTR);
}

static int receive(int descriptor, int *value) {
    size_t received = 0;
    unsigned char *target = (unsigned char *)value;
    while (received < sizeof(*value)) {
        ssize_t count = read(descriptor, target + received, sizeof(*value) - received);
        if (count < 0 && errno == EINTR) continue;
        if (count < 0) return -errno;
        if (count == 0) break;
        received += (size_t)count;
    }
    return (int)received;
}

MinyarBytes *minyar_idleowner_pipeNative(void) {
    MinyarBytes *result = minyar_bytes_new(24);
    int ends[2];
#ifdef __linux__
    if (pipe2(ends, O_CLOEXEC)) { put64(result, 0, -errno); return result; }
#else
    if (pipe(ends)) { put64(result, 0, -errno); return result; }
    fcntl(ends[0], F_SETFD, FD_CLOEXEC);
    fcntl(ends[1], F_SETFD, FD_CLOEXEC);
#endif
    put64(result, 1, ends[0]);
    put64(result, 2, ends[1]);
    return result;
}

long long minyar_idleowner_spawnNative(const MinyarText *path, const MinyarBytes *arguments, const MinyarBytes *environment,
    const MinyarText *directory, const MinyarText *outputPath, const MinyarText *errorPath,
    long long resumeRead, long long resumeWrite, long long reportRead, long long reportWrite) {
    if (!valid_descriptor(resumeRead) || !valid_descriptor(resumeWrite) || !valid_descriptor(reportRead) ||
        !valid_descriptor(reportWrite)) return -EBADF;
    char *argument_storage = NULL, *environment_storage = NULL;
    char *program = copy_text(path), *cwd = copy_text(directory), *out = copy_text(outputPath), *err = copy_text(errorPath);
    char **argv = split_vector(arguments, &argument_storage);
    char **envp = split_vector(environment, &environment_storage);
    long long result = -ENOMEM;
    pid_t child = -1;
    if (!program || !cwd || !out || !err || !argv || !envp || !argv[0]) {
        close((int)resumeRead);
        close((int)reportWrite);
        goto done;
    }
    child = fork();
    if (child == 0) {
        int error = 0;
        struct sigaction action;
        memset(&action, 0, sizeof(action));
        action.sa_handler = SIG_DFL;
        sigaction(SIGPIPE, &action, NULL);
        sigaction(SIGXFSZ, &action, NULL);
        close((int)resumeWrite);
        close((int)reportRead);
#ifdef SYS_close_range
        syscall(SYS_close_range, 3U, ~0U, 4U);
#else
        long limit = sysconf(_SC_OPEN_MAX);
        if (limit < 0 || limit > 65536) limit = 65536;
        for (int descriptor = 3; descriptor < limit; ++descriptor) fcntl(descriptor, F_SETFD, FD_CLOEXEC);
#endif
        if (setsid() < 0) error = errno;
        if (!error) error = redirect("/dev/null", O_RDONLY, 0);
        if (!error && out[0]) error = redirect(out, O_WRONLY | O_CREAT | O_TRUNC, 1);
        if (!error && err[0]) error = redirect(err, O_WRONLY | O_CREAT | O_TRUNC, 2);
        if (!error && cwd[0] && chdir(cwd) < 0) error = errno;
        report((int)reportWrite, error);
        if (error) _exit(127);
        char go = 0;
        ssize_t count;
        do count = read((int)resumeRead, &go, 1); while (count < 0 && errno == EINTR);
        if (count != 1 || go != 'G') _exit(125);
        execve(program, argv, envp);
        report((int)reportWrite, errno);
        _exit(127);
    }
    int saved = errno;
    close((int)resumeRead);
    close((int)reportWrite);
    if (child < 0) { result = -saved; goto done; }
    int status = 0;
    int received = receive((int)reportRead, &status);
    if (received == (int)sizeof(status) && status == 0) {
        result = child;
    } else {
        kill(child, SIGKILL);
        while (waitpid(child, NULL, 0) < 0 && errno == EINTR) {}
        result = received == (int)sizeof(status) ? -status : received < 0 ? received : -EPIPE;
    }
done:
    free(program); free(cwd); free(out); free(err);
    free(argv); free(argument_storage); free(envp); free(environment_storage);
    return result;
}

long long minyar_idleowner_groupNative(long long pid) {
    if (pid <= 0 || pid > INT_MAX) return -EINVAL;
    pid_t group = getpgid((pid_t)pid);
    return group < 0 ? -errno : group;
}

long long minyar_idleowner_resumeNative(long long resumeWrite, long long reportRead) {
    if (!valid_descriptor(resumeWrite) || !valid_descriptor(reportRead)) return -EBADF;
    char go = 'G';
    ssize_t written;
    do written = write((int)resumeWrite, &go, 1); while (written < 0 && errno == EINTR);
    if (written != 1) return written < 0 ? -errno : -EPIPE;
    int status = 0;
    int received = receive((int)reportRead, &status);
    if (received == 0) return 0;
    if (received == (int)sizeof(status)) return -status;
    return received < 0 ? received : -EPIPE;
}

MinyarBytes *minyar_idleowner_reapNative(long long pid) {
    MinyarBytes *result = minyar_bytes_new(16);
    if (pid <= 0 || pid > INT_MAX) { put64(result, 0, 3); put64(result, 1, EINVAL); return result; }
    for (;;) {
        int status = 0;
        pid_t done = waitpid(-1, &status, WNOHANG);
        if (done < 0 && errno == EINTR) continue;
        if (done <= 0) return result;
        if (done != (pid_t)pid) continue;
        if (WIFEXITED(status)) { put64(result, 0, 1); put64(result, 1, WEXITSTATUS(status)); }
        else if (WIFSIGNALED(status)) { put64(result, 0, 2); put64(result, 1, WTERMSIG(status)); }
    }
}

long long minyar_idleowner_releaseNative(long long descriptor) {
    if (!valid_descriptor(descriptor)) return -EBADF;
    return close((int)descriptor) == 0 ? 0 : -errno;
}

long long minyar_idleowner_adoptNative(void) {
#ifdef __linux__
    return prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) == 0 ? 0 : -errno;
#else
    return -ENOTSUP;
#endif
}

long long minyar_idleowner_kindNative(const MinyarText *path) {
    char *name = copy_text(path);
    if (!name) return -ENOMEM;
    struct stat info;
    int status = lstat(name, &info);
    free(name);
    if (status) return -errno;
    return S_ISREG(info.st_mode) ? 1 : S_ISDIR(info.st_mode) ? 2 : S_ISLNK(info.st_mode) ? 3 : 4;
}

bool minyar_idleowner_linuxNative(void) {
#ifdef __linux__
    return true;
#else
    return false;
#endif
}

long long minyar_idleowner_sleepNative(long long nanoseconds) {
    if (nanoseconds < 0) return -EINVAL;
    struct timespec interval = {(time_t)(nanoseconds / 1000000000LL), (long)(nanoseconds % 1000000000LL)};
    while (nanosleep(&interval, &interval) < 0) if (errno != EINTR) return -errno;
    return 0;
}

double minyar_idleowner_parseFloatNative(const MinyarText *text) {
    char *source = copy_text(text);
    if (!source) return NAN;
    char *end = NULL;
    errno = 0;
    double value = strtod(source, &end);
    bool complete = source[0] && end && !*end && (size_t)(end - source) == (size_t)text->byte_length;
    free(source);
    return complete ? value : NAN;
}
