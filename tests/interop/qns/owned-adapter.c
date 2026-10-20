#define _GNU_SOURCE
#include "../../../runtime/minyar_native.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <openssl/evp.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <sys/file.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

extern char **environ;

#define OWNED_CLOSE_RANGE_CLOEXEC (1U << 2)

static int owned_errno;

long long minyar_ownedadapter_lastErrno(void) { return owned_errno; }

static long long failed(void) {
    owned_errno = errno;
    return -(long long)errno;
}

static char *owned_text(const MinyarText *text) {
    size_t length = (size_t)text->byte_length;
    if (memchr(text->bytes, 0, length)) { errno = EINVAL; return NULL; }
    char *copy = malloc(length + 1);
    if (!copy) { errno = ENOMEM; return NULL; }
    memcpy(copy, text->bytes, length);
    copy[length] = 0;
    return copy;
}

static int owned_directory_path(char *path, int create) {
    int fd = open(path[0] == '/' ? "/" : ".", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    char *part = path;
    if (path[0] == '/') part++;
    while (fd >= 0 && *part) {
        char *slash = strchr(part, '/');
        if (slash) *slash = 0;
        if (!part[0] || !strcmp(part, ".") || !strcmp(part, "..")) {
            errno = EINVAL;
            close(fd);
            return -1;
        }
        int next = openat(fd, part, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        if (next < 0 && create && errno == ENOENT) {
            if (mkdirat(fd, part, 0777) != 0 && errno != EEXIST) {
                int code = errno;
                close(fd);
                errno = code;
                return -1;
            }
            next = openat(fd, part, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        }
        int code = errno;
        close(fd);
        errno = code;
        fd = next;
        if (!slash) break;
        part = slash + 1;
    }
    return fd;
}

long long minyar_ownedadapter_archiveCreate(const MinyarText *root, const MinyarText *relative,
                                             bool directory, long long mode) {
    char *base = owned_text(root), *name = base ? owned_text(relative) : NULL;
    if (!name) {
        int code = errno;
        free(base);
        errno = code;
        return failed();
    }
    int fd = owned_directory_path(base, 1);
    char *part = name;
    if (fd >= 0 && (!part[0] || part[0] == '/')) {
        if (part[0]) errno = EINVAL;
        if (part[0]) { close(fd); fd = -1; }
    }
    while (fd >= 0 && *part) {
        char *slash = strchr(part, '/');
        if (slash) *slash = 0;
        if (!part[0] || !strcmp(part, ".") || !strcmp(part, "..")) {
            errno = EINVAL;
            close(fd);
            fd = -1;
            break;
        }
        int last = !slash;
        int next;
        if (last && !directory) {
            next = openat(fd, part, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC,
                          (mode_t)mode);
        } else {
            next = openat(fd, part, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
            if (next < 0 && errno == ENOENT) {
                if (mkdirat(fd, part, 0777) != 0 && errno != EEXIST) next = -1;
                else next = openat(fd, part, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
            }
        }
        int code = errno;
        close(fd);
        errno = code;
        fd = next;
        if (!slash) break;
        part = slash + 1;
    }
    int code = errno;
    free(base);
    free(name);
    errno = code;
    if (fd < 0) return failed();
    if (directory || !relative->byte_length) {
        close(fd);
        return 0;
    }
    return fd;
}

static MinyarText *result_text(const char *value) {
    return minyar_native_copy_text((const unsigned char *)value, (long long)strlen(value));
}

static char **owned_vector(const MinyarBytes *bytes, char **storage) {
    size_t length = (size_t)bytes->byte_length, count = 0;
    for (size_t i = 0; i < length; i++) if (bytes->bytes[i] == 0) count++;
    if (!length || bytes->bytes[length - 1] != 0) { errno = EINVAL; return NULL; }
    char **values = calloc(count + 1, sizeof(*values));
    char *copy = malloc(length);
    if (!values || !copy) { free(values); free(copy); errno = ENOMEM; return NULL; }
    memcpy(copy, bytes->bytes, length);
    size_t at = 0;
    for (size_t i = 0; i < count; i++) { values[i] = copy + at; at += strlen(copy + at) + 1; }
    *storage = copy;
    return values;
}

long long minyar_ownedadapter_pidfdOpen(long long pid) {
    long result = syscall(SYS_pidfd_open, (pid_t)pid, 0);
    return result < 0 ? failed() : result;
}

long long minyar_ownedadapter_pidfdSend(long long fd, long long signal) {
    return syscall(SYS_pidfd_send_signal, (int)fd, (int)signal, NULL, 0) < 0 ? failed() : 0;
}

long long minyar_ownedadapter_pidfdReady(long long fd) {
    struct pollfd probe = {(int)fd, POLLIN, 0};
    int result = poll(&probe, 1, 0);
    if (result < 0) return failed();
    if (result > 0 && (probe.revents & POLLNVAL)) { errno = EBADF; return failed(); }
    return result > 0;
}

long long minyar_ownedadapter_closeFd(long long fd) {
    return close((int)fd) < 0 ? failed() : 0;
}

long long minyar_ownedadapter_subreaperGet(void) {
    int value = 0;
    return prctl(PR_GET_CHILD_SUBREAPER, &value, 0, 0, 0) != 0 ? failed() : value;
}

long long minyar_ownedadapter_subreaperSet(long long value) {
    return prctl(PR_SET_CHILD_SUBREAPER, (unsigned long)value, 0, 0, 0) != 0 ? failed() : 0;
}

long long minyar_ownedadapter_deathSignal(void) {
    int value = 0;
    return prctl(PR_GET_PDEATHSIG, &value, 0, 0, 0) != 0 ? failed() : value;
}

long long minyar_ownedadapter_exitedNoWait(long long pid) {
    siginfo_t info;
    memset(&info, 0, sizeof(info));
    if (waitid(P_PID, (id_t)pid, &info, WEXITED | WNOHANG | WNOWAIT) != 0) return failed();
    return info.si_pid != 0;
}

long long minyar_ownedadapter_reapNoHang(long long pid) {
    int status = 0;
    pid_t result = waitpid((pid_t)pid, &status, WNOHANG);
    if (result < 0) return failed();
    if (result == 0) return 0;
    if (WIFEXITED(status)) return 1000000 + WEXITSTATUS(status);
    if (WIFSIGNALED(status)) return 1000000 - WTERMSIG(status);
    return 1000000 + 255;
}

struct owned_kernel_action { unsigned long handler, flags, restorer, mask; };

long long minyar_ownedadapter_sigchldQuery(void) {
    struct owned_kernel_action action;
    memset(&action, 0, sizeof(action));
    if (syscall(SYS_rt_sigaction, SIGCHLD, NULL, &action, 8) != 0) return failed();
    long long kind = action.handler == 0 ? 0 : action.handler == 1 ? 1 : 2;
    return (kind << 32) | (long long)(action.flags & 0xffffffffUL);
}

long long minyar_ownedadapter_sigchldSet(bool ignore) {
    struct sigaction action;
    memset(&action, 0, sizeof(action));
    action.sa_handler = ignore ? SIG_IGN : SIG_DFL;
    sigemptyset(&action.sa_mask);
    return sigaction(SIGCHLD, &action, NULL) != 0 ? failed() : 0;
}

long long minyar_ownedadapter_pipePair(void) {
    int fds[2];
    if (pipe2(fds, O_CLOEXEC) != 0) return failed();
    return ((long long)fds[0] << 32) | (long long)fds[1];
}

static void child_fail(int report) {
    int code = errno;
    ssize_t ignored = write(report, &code, sizeof(code));
    (void)ignored;
    _exit(127);
}

static int lift(int fd) {
    if (fd < 0) return -1;
    return fcntl(fd, F_DUPFD, 20);
}

long long minyar_ownedadapter_spawnNative(const MinyarText *path, const MinyarBytes *arguments, const MinyarBytes *environment,
    long long input, long long output, long long error, long long gate, long long flags) {
    char *storage = NULL, *environment_storage = NULL, *executable = owned_text(path);
    char **argv = executable ? owned_vector(arguments, &storage) : NULL;
    char **envp = environ;
    if (argv && environment->byte_length > 0) envp = owned_vector(environment, &environment_storage);
    if (!argv || !envp) {
        int code = errno;
        free(executable); free(argv); free(storage);
        errno = code;
        return failed();
    }
    int report[2];
    if (pipe2(report, O_CLOEXEC) != 0) {
        int code = errno;
        free(executable); free(argv); free(storage);
        if (envp != environ) { free(envp); free(environment_storage); }
        errno = code;
        return failed();
    }
    pid_t parent = getpid();
    pid_t child = fork();
    if (child < 0) {
        int code = errno;
        close(report[0]); close(report[1]); free(executable); free(argv); free(storage);
        if (envp != environ) { free(envp); free(environment_storage); }
        errno = code;
        return failed();
    }
    if (child == 0) {
        close(report[0]);
        if ((flags & 2) && prctl(PR_SET_PDEATHSIG, SIGKILL, 0, 0, 0) != 0) child_fail(report[1]);
        if ((flags & 2) && getppid() != parent) _exit(125);
        if ((flags & 1) && setsid() < 0) child_fail(report[1]);
        sigset_t empty;
        sigemptyset(&empty);
        sigprocmask(SIG_SETMASK, &empty, NULL);
        struct sigaction standard;
        memset(&standard, 0, sizeof(standard));
        standard.sa_handler = SIG_DFL;
        sigaction(SIGPIPE, &standard, NULL);
        sigaction(SIGXFSZ, &standard, NULL);
        int sources[4] = {lift((int)input), lift((int)output), lift((int)error), lift((int)gate)};
        for (int target = 0; target < 4; target++) {
            if (sources[target] < 0) continue;
            if (dup2(sources[target], target) < 0) child_fail(report[1]);
        }
        unsigned int keep = gate >= 0 ? 4 : 3;
        if (syscall(SYS_close_range, keep, ~0U, OWNED_CLOSE_RANGE_CLOEXEC) != 0)
            for (int fd = (int)keep; fd < 65536; fd++) fcntl(fd, F_SETFD, FD_CLOEXEC);
        execve(executable, argv, envp);
        child_fail(report[1]);
    }
    close(report[1]);
    free(executable); free(argv); free(storage);
    if (envp != environ) { free(envp); free(environment_storage); }
    int code = 0;
    ssize_t got;
    do { got = read(report[0], &code, sizeof(code)); } while (got < 0 && errno == EINTR);
    close(report[0]);
    if (got == (ssize_t)sizeof(code)) {
        int status;
        while (waitpid(child, &status, 0) < 0 && errno == EINTR) {}
        errno = code;
        return failed();
    }
    return child;
}

MinyarBytes *minyar_ownedadapter_readSome(long long fd, long long limit) {
    owned_errno = 0;
    if (limit <= 0) return minyar_bytes_new(0);
    unsigned char *buffer = malloc((size_t)limit);
    if (!buffer) { owned_errno = ENOMEM; return minyar_bytes_new(0); }
    ssize_t got;
    do { got = read((int)fd, buffer, (size_t)limit); } while (got < 0 && errno == EINTR);
    if (got < 0) { owned_errno = errno; free(buffer); return minyar_bytes_new(0); }
    MinyarBytes *result = minyar_bytes_new(got);
    if (got) memcpy((unsigned char *)result->bytes, buffer, (size_t)got);
    free(buffer);
    return result;
}

MinyarBytes *minyar_ownedadapter_readAt(long long fd, long long offset, long long limit) {
    owned_errno = 0;
    if (limit <= 0) return minyar_bytes_new(0);
    unsigned char *buffer = malloc((size_t)limit);
    if (!buffer) { owned_errno = ENOMEM; return minyar_bytes_new(0); }
    ssize_t got;
    do { got = pread((int)fd, buffer, (size_t)limit, (off_t)offset); } while (got < 0 && errno == EINTR);
    if (got < 0) { owned_errno = errno; free(buffer); return minyar_bytes_new(0); }
    MinyarBytes *result = minyar_bytes_new(got);
    if (got) memcpy((unsigned char *)result->bytes, buffer, (size_t)got);
    free(buffer);
    return result;
}

MinyarBytes *minyar_ownedadapter_pollReadable(const MinyarBytes *fds, long long timeout) {
    size_t count = (size_t)fds->byte_length / 4;
    struct pollfd *probes = calloc(count ? count : 1, sizeof(*probes));
    MinyarBytes *result = minyar_bytes_new((long long)count);
    owned_errno = 0;
    if (!probes) { owned_errno = ENOMEM; return result; }
    for (size_t i = 0; i < count; i++) {
        int32_t value;
        memcpy(&value, fds->bytes + i * 4, 4);
        probes[i].fd = value;
        probes[i].events = POLLIN;
    }
    int ready;
    do { ready = poll(probes, (nfds_t)count, (int)timeout); } while (ready < 0 && errno == EINTR);
    if (ready < 0) owned_errno = errno;
    else for (size_t i = 0; i < count; i++)
        ((unsigned char *)result->bytes)[i] = probes[i].revents & (POLLIN | POLLHUP | POLLERR | POLLNVAL) ? 1 : 0;
    free(probes);
    return result;
}

long long minyar_ownedadapter_writeSome(long long fd, const MinyarBytes *data, long long offset) {
    if (offset < 0 || offset > data->byte_length) { errno = EINVAL; return failed(); }
    ssize_t wrote;
    do { wrote = write((int)fd, data->bytes + offset, (size_t)(data->byte_length - offset)); } while (wrote < 0 && errno == EINTR);
    return wrote < 0 ? failed() : wrote;
}

long long minyar_ownedadapter_writeAll(long long fd, const MinyarBytes *data) {
    long long at = 0;
    while (at < data->byte_length) {
        long long wrote = minyar_ownedadapter_writeSome(fd, data, at);
        if (wrote < 0) return wrote;
        if (wrote == 0) { errno = EIO; return failed(); }
        at += wrote;
    }
    return at;
}

long long minyar_ownedadapter_pollWritable(long long fd, long long timeout) {
    struct pollfd probe = {(int)fd, POLLOUT, 0};
    int ready;
    do { ready = poll(&probe, 1, (int)timeout); } while (ready < 0 && errno == EINTR);
    return ready < 0 ? failed() : ready > 0;
}

long long minyar_ownedadapter_getBlocking(long long fd) {
    int flags = fcntl((int)fd, F_GETFL);
    return flags < 0 ? failed() : !(flags & O_NONBLOCK);
}

long long minyar_ownedadapter_setBlocking(long long fd, bool blocking) {
    int flags = fcntl((int)fd, F_GETFL);
    if (flags < 0) return failed();
    flags = blocking ? flags & ~O_NONBLOCK : flags | O_NONBLOCK;
    return fcntl((int)fd, F_SETFL, flags) < 0 ? failed() : 0;
}

long long minyar_ownedadapter_openFile(const MinyarText *path, long long flags, long long mode) {
    char *name = owned_text(path);
    if (!name) return failed();
    int open_flags = O_CLOEXEC;
    if (flags & 32) open_flags |= O_NOFOLLOW;
    open_flags |= (flags & 1) ? ((flags & 16) ? O_RDWR : O_WRONLY) : O_RDONLY;
    if (flags & 2) open_flags |= O_CREAT;
    if (flags & 4) open_flags |= O_TRUNC;
    if (flags & 8) open_flags |= O_EXCL;
    if (flags & 16) open_flags |= O_APPEND;
    int fd = open(name, open_flags, (mode_t)mode);
    int code = errno;
    free(name);
    errno = code;
    return fd < 0 ? failed() : fd;
}

long long minyar_ownedadapter_flockTry(long long fd) {
    return flock((int)fd, LOCK_EX | LOCK_NB) != 0 ? failed() : 0;
}

long long minyar_ownedadapter_flockRelease(long long fd) {
    return flock((int)fd, LOCK_UN) != 0 ? failed() : 0;
}

long long minyar_ownedadapter_renameNoReplace(const MinyarText *source, const MinyarText *target) {
    char *from = owned_text(source), *to = from ? owned_text(target) : NULL;
    if (!to) { int code = errno; free(from); errno = code; return failed(); }
    long result = syscall(SYS_renameat2, AT_FDCWD, from, AT_FDCWD, to, 1U);
    int code = errno;
    free(from); free(to);
    errno = code;
    return result != 0 ? failed() : 0;
}

long long minyar_ownedadapter_renameReplace(const MinyarText *source, const MinyarText *target) {
    char *from = owned_text(source), *to = from ? owned_text(target) : NULL;
    if (!to) { int code = errno; free(from); errno = code; return failed(); }
    int result = rename(from, to);
    int code = errno;
    free(from); free(to);
    errno = code;
    return result != 0 ? failed() : 0;
}

long long minyar_ownedadapter_createSession(void) {
    pid_t session = setsid();
    return session < 0 ? failed() : session;
}

long long minyar_ownedadapter_parentProcess(void) { return getppid(); }
long long minyar_ownedadapter_processGroup(void) { return getpgrp(); }

long long minyar_ownedadapter_processGroupOf(long long pid) {
    pid_t group = getpgid((pid_t)pid);
    return group < 0 ? failed() : group;
}

MinyarText *minyar_ownedadapter_machine(void) {
    struct utsname name;
    if (uname(&name) != 0) return result_text("");
    return result_text(name.machine);
}

MinyarText *minyar_ownedadapter_readLink(const MinyarText *path) {
    char *name = owned_text(path);
    char buffer[PATH_MAX + 1];
    owned_errno = 0;
    if (!name) { owned_errno = errno; return result_text(""); }
    ssize_t length = readlink(name, buffer, PATH_MAX);
    if (length < 0) owned_errno = errno;
    free(name);
    if (length < 0) return result_text("");
    buffer[length] = 0;
    return result_text(buffer);
}

MinyarText *minyar_ownedadapter_realPath(const MinyarText *path) {
    char *name = owned_text(path);
    owned_errno = 0;
    if (!name) { owned_errno = errno; return result_text(""); }
    char *resolved = realpath(name, NULL);
    if (!resolved) owned_errno = errno;
    free(name);
    if (!resolved) return result_text("");
    MinyarText *result = result_text(resolved);
    free(resolved);
    return result;
}

MinyarBytes *minyar_ownedadapter_statPath(const MinyarText *path, bool follow) {
    MinyarBytes *result = minyar_bytes_new(40);
    long long values[5] = {0, 0, 0, 0, 0};
    char *name = owned_text(path);
    struct stat info;
    if (!name) values[0] = errno;
    else if ((follow ? stat(name, &info) : lstat(name, &info)) != 0) values[0] = errno;
    else {
        values[1] = S_ISREG(info.st_mode) ? 1 : S_ISDIR(info.st_mode) ? 2 : S_ISLNK(info.st_mode) ? 3 : 4;
        values[2] = info.st_mode & 07777;
        values[3] = (long long)info.st_size;
        values[4] = (long long)info.st_ino;
    }
    free(name);
    memcpy((unsigned char *)result->bytes, values, sizeof(values));
    return result;
}

long long minyar_ownedadapter_changeMode(const MinyarText *path, long long mode) {
    char *name = owned_text(path);
    if (!name) return failed();
    int result = chmod(name, (mode_t)mode);
    int code = errno;
    free(name);
    errno = code;
    return result != 0 ? failed() : 0;
}

long long minyar_ownedadapter_makeDirectoryNative(const MinyarText *path, long long mode) {
    char *name = owned_text(path);
    if (!name) return failed();
    int result = mkdir(name, (mode_t)mode);
    int code = errno;
    free(name);
    errno = code;
    return result != 0 ? failed() : 0;
}

long long minyar_ownedadapter_removeFile(const MinyarText *path) {
    char *name = owned_text(path);
    if (!name) return failed();
    int result = unlink(name);
    int code = errno;
    free(name);
    errno = code;
    return result != 0 ? failed() : 0;
}

long long minyar_ownedadapter_removeDirectory(const MinyarText *path) {
    char *name = owned_text(path);
    if (!name) return failed();
    int result = rmdir(name);
    int code = errno;
    free(name);
    errno = code;
    return result != 0 ? failed() : 0;
}

MinyarText *minyar_ownedadapter_temporaryDirectory(const MinyarText *directory, const MinyarText *prefix) {
    owned_errno = 0;
    size_t length = (size_t)directory->byte_length + (size_t)prefix->byte_length + 8;
    if (memchr(directory->bytes, 0, (size_t)directory->byte_length) || memchr(prefix->bytes, 0, (size_t)prefix->byte_length) ||
        memchr(prefix->bytes, '/', (size_t)prefix->byte_length)) { owned_errno = EINVAL; return result_text(""); }
    char *template = malloc(length + 1);
    if (!template) { owned_errno = ENOMEM; return result_text(""); }
    memcpy(template, directory->bytes, (size_t)directory->byte_length);
    template[directory->byte_length] = '/';
    memcpy(template + directory->byte_length + 1, prefix->bytes, (size_t)prefix->byte_length);
    memcpy(template + directory->byte_length + 1 + prefix->byte_length, "XXXXXX", 7);
    char *made = mkdtemp(template);
    if (!made) owned_errno = errno;
    MinyarText *result = result_text(made ? made : "");
    free(template);
    return result;
}

#define OWNED_DIRECTORIES 64
static DIR *owned_directories[OWNED_DIRECTORIES];

long long minyar_ownedadapter_directoryOpen(const MinyarText *path) {
    char *name = owned_text(path);
    if (!name) return failed();
    int slot = -1;
    for (int i = 0; i < OWNED_DIRECTORIES; i++) if (!owned_directories[i]) { slot = i; break; }
    if (slot < 0) { free(name); errno = EMFILE; return failed(); }
    int fd = open(name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    int code = errno;
    free(name);
    if (fd < 0) { errno = code; return failed(); }
    DIR *directory = fdopendir(fd);
    if (!directory) { code = errno; close(fd); errno = code; return failed(); }
    owned_directories[slot] = directory;
    return slot + 1;
}

MinyarText *minyar_ownedadapter_directoryNext(long long handle) {
    owned_errno = 0;
    if (handle < 1 || handle > OWNED_DIRECTORIES || !owned_directories[handle - 1]) { owned_errno = EBADF; return result_text(""); }
    for (;;) {
        errno = 0;
        struct dirent *entry = readdir(owned_directories[handle - 1]);
        if (!entry) { owned_errno = errno; return result_text(""); }
        if (strcmp(entry->d_name, ".") && strcmp(entry->d_name, "..")) return result_text(entry->d_name);
    }
}

long long minyar_ownedadapter_directoryClose(long long handle) {
    if (handle < 1 || handle > OWNED_DIRECTORIES || !owned_directories[handle - 1]) { errno = EBADF; return failed(); }
    int result = closedir(owned_directories[handle - 1]);
    owned_directories[handle - 1] = NULL;
    return result != 0 ? failed() : 0;
}

long long minyar_ownedadapter_sleepMilliseconds(long long milliseconds) {
    struct timespec delay = {(time_t)(milliseconds / 1000), (long)(milliseconds % 1000) * 1000000L};
    while (nanosleep(&delay, &delay) != 0 && errno == EINTR) {}
    return 0;
}

long long minyar_ownedadapter_exitNow(long long status) {
    _exit((int)status);
}

long long minyar_ownedadapter_gateExecNative(long long fd, const MinyarBytes *arguments, long long timeout) {
    struct pollfd probe = {(int)fd, POLLIN, 0};
    int ready;
    do { ready = poll(&probe, 1, (int)timeout); } while (ready < 0 && errno == EINTR);
    if (ready <= 0) return 125;
    unsigned char permit = 0;
    ssize_t got;
    do { got = read((int)fd, &permit, 1); } while (got < 0 && errno == EINTR);
    if (got != 1 || permit != 'G') return 125;
    close((int)fd);
    char *storage = NULL;
    char **argv = owned_vector(arguments, &storage);
    if (!argv || !argv[0]) return 125;
    execv(argv[0], argv);
    return 125;
}

MinyarText *minyar_ownedadapter_sha1Hex(const MinyarBytes *data) {
    unsigned char digest[EVP_MAX_MD_SIZE];
    unsigned int length = 0;
    char hex[2 * EVP_MAX_MD_SIZE + 1];
    if (!EVP_Digest(data->bytes, (size_t)data->byte_length, digest, &length, EVP_sha1(), NULL)) minyar_native_stop("SHA-1 digest failed");
    for (unsigned int i = 0; i < length; i++) snprintf(hex + 2 * i, 3, "%02x", digest[i]);
    hex[2 * length] = 0;
    return result_text(hex);
}
