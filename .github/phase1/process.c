#define _GNU_SOURCE 1
#define _DARWIN_C_SOURCE 1
#include "../../runtime/minyar_native.h"
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <spawn.h>
#include <stdint.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static _Thread_local long long phase1_error;

static char *phase1_string(const MinyarText *text) {
    if (!text || text->byte_length < 0 || memchr(text->bytes, 0, (size_t)text->byte_length)) return NULL;
    char *value = malloc((size_t)text->byte_length + 1);
    if (!value) return NULL;
    memcpy(value, text->bytes, (size_t)text->byte_length);
    value[text->byte_length] = 0;
    return value;
}

static long long phase1_int64(const unsigned char *bytes) {
    long long value;
    memcpy(&value, bytes, sizeof(value));
    return value;
}

static void phase1_free_vector(char **items) {
    if (!items) return;
    for (char **item = items; *item; ++item) free(*item);
    free(items);
}

static char **phase1_vector(const MinyarBytes *encoded) {
    if (!encoded || encoded->byte_length < 8) return NULL;
    long long count = phase1_int64(encoded->bytes);
    if (count < 0 || count > 65536) return NULL;
    char **items = calloc((size_t)count + 1, sizeof(char *));
    if (!items) return NULL;
    long long at = 8;
    for (long long index = 0; index < count; ++index) {
        if (encoded->byte_length - at < 8) { phase1_free_vector(items); return NULL; }
        long long length = phase1_int64(encoded->bytes + at);
        at += 8;
        if (length < 0 || encoded->byte_length - at < length || memchr(encoded->bytes + at, 0, (size_t)length)) {
            phase1_free_vector(items);
            return NULL;
        }
        items[index] = malloc((size_t)length + 1);
        if (!items[index]) { phase1_free_vector(items); return NULL; }
        memcpy(items[index], encoded->bytes + at, (size_t)length);
        items[index][length] = 0;
        at += length;
    }
    if (at != encoded->byte_length) { phase1_free_vector(items); return NULL; }
    return items;
}

long long minyar_phase1_lastError(void) { return phase1_error; }

long long minyar_phase1_umask(long long mask) { return (long long)umask((mode_t)(mask & 0777)); }

long long minyar_phase1_makeDirectory(const MinyarText *path, long long mode) {
    char *name = phase1_string(path);
    if (!name) return -EINVAL;
    int result = mkdir(name, (mode_t)(mode & 07777));
    int error = errno;
    free(name);
    return result == 0 ? 0 : -error;
}

long long minyar_phase1_changeMode(const MinyarText *path, long long mode) {
    char *name = phase1_string(path);
    if (!name) return -EINVAL;
    int result = chmod(name, (mode_t)(mode & 07777));
    int error = errno;
    free(name);
    return result == 0 ? 0 : -error;
}

MinyarBytes *minyar_phase1_status(const MinyarText *path, bool follow) {
    phase1_error = 0;
    char *name = phase1_string(path);
    if (!name) { phase1_error = -EINVAL; return minyar_bytes_new(0); }
    struct stat info;
    int result = follow ? stat(name, &info) : lstat(name, &info);
    int error = errno;
    free(name);
    if (result != 0) { phase1_error = -error; return minyar_bytes_new(0); }
    long long values[3];
    values[0] = S_ISREG(info.st_mode) ? 1 : S_ISDIR(info.st_mode) ? 2 : S_ISLNK(info.st_mode) ? 3 : 4;
    values[1] = (long long)(info.st_mode & 07777);
    values[2] = (long long)info.st_size;
    MinyarBytes *encoded = minyar_bytes_new(24);
    memcpy((unsigned char *)encoded->bytes, values, sizeof(values));
    return encoded;
}

bool minyar_phase1_executable(const MinyarText *path) {
    char *name = phase1_string(path);
    if (!name) return false;
    struct stat info;
    bool result = stat(name, &info) == 0 && S_ISREG(info.st_mode) && access(name, X_OK) == 0;
    free(name);
    return result;
}

bool minyar_phase1_descriptorOpen(long long descriptor) {
    if (descriptor < 0 || descriptor > INT32_MAX) return false;
    return fcntl((int)descriptor, F_GETFD) != -1;
}

MinyarText *minyar_phase1_currentDirectory(void) {
    char buffer[4096];
    if (!getcwd(buffer, sizeof(buffer))) return minyar_native_copy_text((const unsigned char *)"", 0);
    return minyar_native_copy_text((const unsigned char *)buffer, (long long)strlen(buffer));
}

long long minyar_phase1_redirect(const MinyarText *path) {
    char *name = phase1_string(path);
    if (!name) return -EINVAL;
    long limit = sysconf(_SC_OPEN_MAX);
    if (limit < 0 || limit > 65536) limit = 65536;
    for (int descriptor = 3; descriptor < limit; ++descriptor) {
        int flags = fcntl(descriptor, F_GETFD);
        if (flags >= 0 && !(flags & FD_CLOEXEC)) fcntl(descriptor, F_SETFD, flags | FD_CLOEXEC);
    }
    int status = fcntl(1, F_DUPFD_CLOEXEC, 3);
    if (status < 0) { int error = errno; free(name); return -error; }
    int log = open(name, O_WRONLY | O_CREAT | O_CLOEXEC, 0600);
    int error = errno;
    free(name);
    if (log < 0) { close(status); return -error; }
    if (dup2(log, 1) < 0 || dup2(log, 2) < 0) { error = errno; close(log); close(status); return -error; }
    close(log);
    return status;
}

long long minyar_phase1_writeAll(long long descriptor, const MinyarBytes *data) {
    if (descriptor < 0 || descriptor > INT32_MAX || !data) return -EINVAL;
    long long written = 0;
    while (written < data->byte_length) {
        ssize_t count = write((int)descriptor, data->bytes + written, (size_t)(data->byte_length - written));
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) return -errno;
        written += count;
    }
    return written;
}

long long minyar_phase1_closeDescriptor(long long descriptor) {
    if (descriptor < 0 || descriptor > INT32_MAX) return -EINVAL;
    return close((int)descriptor) == 0 ? 0 : -errno;
}

long long minyar_phase1_spawnNative(const MinyarText *path, const MinyarBytes *argv, const MinyarBytes *envp,
    const MinyarText *cwd, const MinyarText *output, bool merge) {
    char *file = phase1_string(path), *directory = phase1_string(cwd), *capture = phase1_string(output);
    char **arguments = phase1_vector(argv), **environment = phase1_vector(envp);
    long long result = -EINVAL;
    if (!file || !directory || !capture || !arguments || !arguments[0] || !environment) goto done;
    posix_spawnattr_t attributes;
    posix_spawn_file_actions_t actions;
    int error = posix_spawnattr_init(&attributes);
    if (error) { result = -error; goto done; }
    error = posix_spawn_file_actions_init(&actions);
    if (error) { posix_spawnattr_destroy(&attributes); result = -error; goto done; }
    sigset_t defaults, mask;
    sigemptyset(&mask);
    sigemptyset(&defaults);
    sigaddset(&defaults, SIGPIPE);
    sigaddset(&defaults, SIGXFSZ);
    short flags = POSIX_SPAWN_SETSIGDEF | POSIX_SPAWN_SETSIGMASK;
#ifdef POSIX_SPAWN_SETSID
    flags |= POSIX_SPAWN_SETSID;
#else
    flags |= POSIX_SPAWN_SETPGROUP;
    if (!error) error = posix_spawnattr_setpgroup(&attributes, 0);
#endif
    if (!error) error = posix_spawnattr_setflags(&attributes, flags);
    if (!error) error = posix_spawnattr_setsigdefault(&attributes, &defaults);
    if (!error) error = posix_spawnattr_setsigmask(&attributes, &mask);
    if (!error && directory[0]) error = posix_spawn_file_actions_addchdir_np(&actions, directory);
    if (!error && capture[0]) error = posix_spawn_file_actions_addopen(&actions, 1, capture, O_WRONLY | O_CREAT | O_TRUNC, 0600);
    if (!error && capture[0] && merge) error = posix_spawn_file_actions_adddup2(&actions, 1, 2);
    pid_t pid = 0;
    if (!error) error = posix_spawn(&pid, file, &actions, &attributes, arguments, environment);
    posix_spawn_file_actions_destroy(&actions);
    posix_spawnattr_destroy(&attributes);
    result = error ? -error : (long long)pid;
done:
    free(file);
    free(directory);
    free(capture);
    phase1_free_vector(arguments);
    phase1_free_vector(environment);
    return result;
}

long long minyar_phase1_wait(long long pid, bool block) {
    if (pid <= 0 || pid > INT32_MAX) return -EINVAL;
    int status = 0;
    pid_t result;
    do { result = waitpid((pid_t)pid, &status, block ? 0 : WNOHANG); } while (result < 0 && errno == EINTR);
    if (result < 0) return -errno;
    if (result == 0) return 1048576;
    if (WIFEXITED(status)) return WEXITSTATUS(status);
    if (WIFSIGNALED(status)) return 256 + WTERMSIG(status);
    return 1048576;
}

void minyar_phase1_pause(long long milliseconds) {
    if (milliseconds <= 0) return;
    struct timespec delay = {(time_t)(milliseconds / 1000), (long)(milliseconds % 1000) * 1000000L};
    nanosleep(&delay, NULL);
}
