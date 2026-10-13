#define _GNU_SOURCE 1
#include "../runtime/minyar_native.h"
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <signal.h>
#include <stdint.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

typedef struct { char **items; char *storage; } Vector;

static char *copy_text(const MinyarText *text) {
    char *result = malloc((size_t)text->byte_length + 1);
    if (!result) return NULL;
    memcpy(result, text->bytes, (size_t)text->byte_length);
    result[text->byte_length] = 0;
    return result;
}

static bool split_vector(const MinyarBytes *packed, Vector *vector) {
    long long count = 0;
    for (long long index = 0; index < packed->byte_length; ++index) if (!packed->bytes[index]) count++;
    vector->items = calloc((size_t)count + 1, sizeof(char *));
    vector->storage = malloc((size_t)packed->byte_length + 1);
    if (!vector->items || !vector->storage) return false;
    memcpy(vector->storage, packed->bytes, (size_t)packed->byte_length);
    long long item = 0, start = 0;
    for (long long index = 0; index < packed->byte_length; ++index) {
        if (!vector->storage[index]) { vector->items[item++] = vector->storage + start; start = index + 1; }
    }
    return true;
}

static void put64(MinyarBytes *bytes, int slot, long long value) {
    unsigned char *target = (unsigned char *)bytes->bytes + slot * 8;
    unsigned long long raw = (unsigned long long)value;
    for (int index = 0; index < 8; ++index) target[index] = (unsigned char)(raw >> (8 * index));
}

static int redirect(const char *path, int flags, off_t offset, int target) {
    int descriptor = open(path, flags, 0600);
    if (descriptor < 0) return errno;
    if (offset > 0 && lseek(descriptor, offset, SEEK_SET) < 0) return errno;
    if (descriptor != target) {
        if (dup2(descriptor, target) < 0) return errno;
        close(descriptor);
    }
    return 0;
}

long long minyar_evidencesupport_launch(const MinyarText *path, const MinyarBytes *arguments,
    const MinyarBytes *environment, const MinyarText *directory, long long input,
    const MinyarText *inputPath, long long inputOffset, const MinyarText *outputPath, const MinyarText *errorPath) {
    Vector argv = {0}, envp = {0};
    char *program = copy_text(path), *cwd = copy_text(directory), *in = copy_text(inputPath);
    char *out = copy_text(outputPath), *err = copy_text(errorPath);
    long long result = -ENOMEM;
    int report[2] = {-1, -1};
    if (!program || !cwd || !in || !out || !err || !split_vector(arguments, &argv) || !split_vector(environment, &envp)) goto done;
    if (pipe(report)) { result = -errno; goto done; }
    fcntl(report[0], F_SETFD, FD_CLOEXEC);
    fcntl(report[1], F_SETFD, FD_CLOEXEC);
    pid_t child = fork();
    if (child < 0) { result = -errno; goto done; }
    if (child == 0) {
        int error = 0;
        struct sigaction action;
        memset(&action, 0, sizeof(action));
        action.sa_handler = SIG_DFL;
        sigaction(SIGPIPE, &action, NULL);
        sigaction(SIGXFSZ, &action, NULL);
        if (setsid() < 0) error = errno;
#ifdef SYS_close_range
        syscall(SYS_close_range, 3U, ~0U, 4U);
#endif
        if (!error && input == 0) error = redirect("/dev/null", O_RDONLY, 0, 0);
        if (!error && input == 1) error = redirect(in, O_RDONLY, (off_t)inputOffset, 0);
        if (!error && out[0]) error = redirect(out, O_WRONLY | O_CREAT | O_TRUNC, 0, 1);
        if (!error && err[0]) error = redirect(err, O_WRONLY | O_CREAT | O_TRUNC, 0, 2);
        if (!error && cwd[0] && chdir(cwd) < 0) error = errno;
        if (!error) { execve(program, argv.items, envp.items); error = errno; }
        while (write(report[1], &error, sizeof(error)) < 0 && errno == EINTR) {}
        _exit(127);
    }
    close(report[1]);
    report[1] = -1;
    int error = 0;
    ssize_t received;
    do received = read(report[0], &error, sizeof(error)); while (received < 0 && errno == EINTR);
    if (received == (ssize_t)sizeof(error)) {
        while (waitpid(child, NULL, 0) < 0 && errno == EINTR) {}
        result = -error;
    } else {
        result = child;
    }
done:
    if (report[0] >= 0) close(report[0]);
    if (report[1] >= 0) close(report[1]);
    free(program); free(cwd); free(in); free(out); free(err);
    free(argv.items); free(argv.storage); free(envp.items); free(envp.storage);
    return result;
}

MinyarBytes *minyar_evidencesupport_reap(long long pid, long long nanoseconds) {
    MinyarBytes *result = minyar_bytes_new(24);
    struct timespec start, now;
    clock_gettime(CLOCK_MONOTONIC, &start);
    long long delay = 1000000;
    for (;;) {
        int status = 0;
        pid_t done = waitpid((pid_t)pid, &status, nanoseconds < 0 ? 0 : WNOHANG);
        if (done < 0) {
            if (errno == EINTR) continue;
            put64(result, 0, 3); put64(result, 1, errno);
            return result;
        }
        if (done == (pid_t)pid) {
            if (WIFEXITED(status)) { put64(result, 0, 1); put64(result, 1, WEXITSTATUS(status)); return result; }
            if (WIFSIGNALED(status)) { put64(result, 0, 2); put64(result, 1, WTERMSIG(status)); return result; }
            continue;
        }
        clock_gettime(CLOCK_MONOTONIC, &now);
        long long elapsed = (long long)(now.tv_sec - start.tv_sec) * 1000000000LL + (now.tv_nsec - start.tv_nsec);
        if (elapsed >= nanoseconds) return result;
        long long pause = nanoseconds - elapsed < delay ? nanoseconds - elapsed : delay;
        struct timespec interval = {(time_t)(pause / 1000000000LL), (long)(pause % 1000000000LL)};
        nanosleep(&interval, NULL);
        if (delay < 20000000) delay *= 2;
    }
}

long long minyar_evidencesupport_terminate(long long pid, bool group) {
    if (pid <= 0 || pid > INT_MAX) return -EINVAL;
    int status = group ? killpg((pid_t)pid, SIGKILL) : kill((pid_t)pid, SIGKILL);
    if (status == 0 || errno == ESRCH) return 0;
    return -errno;
}

MinyarText *minyar_evidencesupport_resolveNative(const MinyarText *path) {
    char *name = copy_text(path);
    char *resolved = name ? realpath(name, NULL) : NULL;
    MinyarText *result = resolved ? minyar_native_copy_text((const unsigned char *)resolved, (long long)strlen(resolved))
                                  : minyar_native_copy_text((const unsigned char *)"", 0);
    free(name);
    free(resolved);
    return result;
}

MinyarBytes *minyar_evidencesupport_inspect(const MinyarText *path, bool follow) {
    MinyarBytes *result = minyar_bytes_new(48);
    char *name = copy_text(path);
    struct stat info;
    if (!name) { put64(result, 0, -ENOMEM); return result; }
    int status = follow ? stat(name, &info) : lstat(name, &info);
    free(name);
    if (status) { put64(result, 0, -errno); return result; }
    long long type = S_ISREG(info.st_mode) ? 1 : S_ISDIR(info.st_mode) ? 2 : S_ISLNK(info.st_mode) ? 3 : 4;
#ifdef __APPLE__
    long long modified = (long long)info.st_mtimespec.tv_sec * 1000000000LL + info.st_mtimespec.tv_nsec;
#else
    long long modified = (long long)info.st_mtim.tv_sec * 1000000000LL + info.st_mtim.tv_nsec;
#endif
    put64(result, 1, type);
    put64(result, 2, (long long)info.st_size);
    put64(result, 3, modified);
    put64(result, 4, (long long)info.st_ino);
    put64(result, 5, (long long)info.st_mode);
    return result;
}

MinyarText *minyar_evidencesupport_platform(void) {
#if defined(__linux__)
    const char *name = "linux";
#elif defined(__APPLE__)
    const char *name = "darwin";
#elif defined(_WIN32)
    const char *name = "win32";
#else
    const char *name = "unknown";
#endif
    return minyar_native_copy_text((const unsigned char *)name, (long long)strlen(name));
}

MinyarText *minyar_evidencesupport_byteOrder(void) {
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
    const char *name = "big";
#else
    const char *name = "little";
#endif
    return minyar_native_copy_text((const unsigned char *)name, (long long)strlen(name));
}
