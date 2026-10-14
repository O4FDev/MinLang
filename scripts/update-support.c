#include "../runtime/minyar_native.h"
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdint.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>
#if defined(__APPLE__) || defined(__linux__)
#include <sys/xattr.h>
#endif

#if defined(__APPLE__)
#define SUPPORT_MTIME(info) ((long long)(info).st_mtimespec.tv_sec * 1000000000LL + (long long)(info).st_mtimespec.tv_nsec)
#define SUPPORT_CTIME(info) ((long long)(info).st_ctimespec.tv_sec * 1000000000LL + (long long)(info).st_ctimespec.tv_nsec)
#else
#define SUPPORT_MTIME(info) ((long long)(info).st_mtim.tv_sec * 1000000000LL + (long long)(info).st_mtim.tv_nsec)
#define SUPPORT_CTIME(info) ((long long)(info).st_ctim.tv_sec * 1000000000LL + (long long)(info).st_ctim.tv_nsec)
#endif

static int support_path(const MinyarText *text, char *out) {
    if (!text || text->byte_length <= 0) return -ENOENT;
    if (text->byte_length >= PATH_MAX) return -ENAMETOOLONG;
    if (memchr(text->bytes, 0, (size_t)text->byte_length)) return -EINVAL;
    memcpy(out, text->bytes, (size_t)text->byte_length);
    out[text->byte_length] = 0;
    return 0;
}

static void support_put(unsigned char *target, long long value) {
    unsigned long long raw = (unsigned long long)value;
    for (int index = 0; index < 8; index++) target[index] = (unsigned char)(raw >> (8 * index));
}

static MinyarBytes *support_result(long long status, const char *text, size_t length) {
    MinyarBytes *result = minyar_bytes_new(0);
    support_put(minyar_bytes_extend(result, 8), status);
    if (length) memcpy(minyar_bytes_extend(result, (long long)length), text, length);
    return result;
}

static MinyarBytes *support_status(int error, const struct stat *info) {
    MinyarBytes *result = minyar_bytes_new(0);
    unsigned char *slots = minyar_bytes_extend(result, 64);
    if (error) {
        support_put(slots, error);
        return result;
    }
    support_put(slots, 0);
    support_put(slots + 8, (long long)info->st_dev);
    support_put(slots + 16, (long long)info->st_ino);
    support_put(slots + 24, (long long)info->st_mode);
    support_put(slots + 32, (long long)info->st_size);
    support_put(slots + 40, SUPPORT_MTIME(*info));
    support_put(slots + 48, SUPPORT_CTIME(*info));
    support_put(slots + 56, (long long)info->st_nlink);
    return result;
}

MinyarBytes *minyar_updatesupport_statusNative(const MinyarText *path, bool follow) {
    char buffer[PATH_MAX];
    struct stat info;
    int rc = support_path(path, buffer);
    if (rc) return support_status(rc, NULL);
    if ((follow ? stat(buffer, &info) : lstat(buffer, &info)) != 0) return support_status(-errno, NULL);
    return support_status(0, &info);
}

MinyarBytes *minyar_updatesupport_descriptorStatusNative(long long fd) {
    struct stat info;
    if (fd < 0 || fd > INT_MAX) return support_status(-EBADF, NULL);
    if (fstat((int)fd, &info) != 0) return support_status(-errno, NULL);
    return support_status(0, &info);
}

long long minyar_updatesupport_openRead(const MinyarText *path, bool noFollow) {
    char buffer[PATH_MAX];
    int rc = support_path(path, buffer);
    if (rc) return rc;
    int flags = O_RDONLY | O_CLOEXEC;
    if (noFollow) flags |= O_NOFOLLOW;
    int fd;
    do { fd = open(buffer, flags); } while (fd < 0 && errno == EINTR);
    return fd < 0 ? -errno : fd;
}

long long minyar_updatesupport_createFile(const MinyarText *path) {
    char buffer[PATH_MAX];
    int rc = support_path(path, buffer);
    if (rc) return rc;
    int fd;
    do { fd = open(buffer, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0666); } while (fd < 0 && errno == EINTR);
    return fd < 0 ? -errno : fd;
}

long long minyar_updatesupport_makeDirectory(const MinyarText *path) {
    char buffer[PATH_MAX];
    int rc = support_path(path, buffer);
    if (rc) return rc;
    return mkdir(buffer, 0777) == 0 ? 0 : -errno;
}

long long minyar_updatesupport_openDirectory(const MinyarText *path) {
    char buffer[PATH_MAX];
    int rc = support_path(path, buffer);
    if (rc) return rc;
    int fd;
    do { fd = open(buffer, O_RDONLY | O_DIRECTORY | O_CLOEXEC); } while (fd < 0 && errno == EINTR);
    return fd < 0 ? -errno : fd;
}

long long minyar_updatesupport_syncDescriptor(long long fd) {
    if (fd < 0 || fd > INT_MAX) return -EBADF;
    int rc;
    do { rc = fsync((int)fd); } while (rc != 0 && errno == EINTR);
    return rc == 0 ? 0 : -errno;
}

long long minyar_updatesupport_closeDescriptor(long long fd) {
    if (fd < 0 || fd > INT_MAX) return -EBADF;
    return close((int)fd) == 0 ? 0 : -errno;
}

MinyarBytes *minyar_updatesupport_attributesNative(const MinyarText *path) {
    char buffer[PATH_MAX];
    int rc = support_path(path, buffer);
    if (rc) return support_result(rc, NULL, 0);
#if defined(__APPLE__) || defined(__linux__)
    for (int attempt = 0; attempt < 8; attempt++) {
#if defined(__APPLE__)
        ssize_t size = listxattr(buffer, NULL, 0, XATTR_NOFOLLOW);
#else
        ssize_t size = llistxattr(buffer, NULL, 0);
#endif
        if (size < 0) return support_result(-errno, NULL, 0);
        if (size == 0) return support_result(0, NULL, 0);
        char *names = malloc((size_t)size);
        if (!names) return support_result(-ENOMEM, NULL, 0);
#if defined(__APPLE__)
        ssize_t filled = listxattr(buffer, names, (size_t)size, XATTR_NOFOLLOW);
#else
        ssize_t filled = llistxattr(buffer, names, (size_t)size);
#endif
        if (filled < 0) {
            int error = errno;
            free(names);
            if (error == ERANGE) continue;
            return support_result(-error, NULL, 0);
        }
        MinyarBytes *result = support_result(0, names, (size_t)filled);
        free(names);
        return result;
    }
    return support_result(-ERANGE, NULL, 0);
#else
    return support_result(0, NULL, 0);
#endif
}

MinyarBytes *minyar_updatesupport_resolveNative(const MinyarText *path) {
    char buffer[PATH_MAX];
    char resolved[PATH_MAX];
    int rc = support_path(path, buffer);
    if (rc) return support_result(rc, NULL, 0);
    if (!realpath(buffer, resolved)) return support_result(-errno, NULL, 0);
    return support_result(0, resolved, strlen(resolved));
}

static int support_template(const MinyarText *directory, const MinyarText *prefix, char *out) {
    char base[PATH_MAX];
    int rc = support_path(directory, base);
    if (rc) return rc;
    if (!prefix || prefix->byte_length <= 0 || memchr(prefix->bytes, 0, (size_t)prefix->byte_length) || memchr(prefix->bytes, '/', (size_t)prefix->byte_length)) return -EINVAL;
    size_t used = strlen(base);
    if (used + 1 + (size_t)prefix->byte_length + 6 >= PATH_MAX) return -ENAMETOOLONG;
    memcpy(out, base, used);
    out[used++] = '/';
    memcpy(out + used, prefix->bytes, (size_t)prefix->byte_length);
    used += (size_t)prefix->byte_length;
    memcpy(out + used, "XXXXXX", 7);
    return 0;
}

MinyarBytes *minyar_updatesupport_temporaryFileNative(const MinyarText *directory, const MinyarText *prefix) {
    char path[PATH_MAX];
    int rc = support_template(directory, prefix, path);
    if (rc) return support_result(rc, NULL, 0);
    int fd = mkstemp(path);
    if (fd < 0) return support_result(-errno, NULL, 0);
    fcntl(fd, F_SETFD, FD_CLOEXEC);
    return support_result(fd, path, strlen(path));
}

MinyarBytes *minyar_updatesupport_temporaryDirectoryNative(const MinyarText *directory, const MinyarText *prefix) {
    char path[PATH_MAX];
    int rc = support_template(directory, prefix, path);
    if (rc) return support_result(rc, NULL, 0);
    if (!mkdtemp(path)) return support_result(-errno, NULL, 0);
    return support_result(0, path, strlen(path));
}

MinyarBytes *minyar_updatesupport_currentDirectoryNative(void) {
    char path[PATH_MAX];
    if (!getcwd(path, sizeof(path))) return support_result(-errno, NULL, 0);
    return support_result(0, path, strlen(path));
}

MinyarText *minyar_updatesupport_platform(void) {
#if defined(__APPLE__)
    const char *name = "darwin";
#elif defined(__linux__)
    const char *name = "linux";
#else
    const char *name = "other";
#endif
    return minyar_native_copy_text((const unsigned char *)name, (long long)strlen(name));
}

long long minyar_updatesupport_pause(long long milliseconds) {
    if (milliseconds < 0) return -EINVAL;
    struct timespec delay = { (time_t)(milliseconds / 1000), (long)(milliseconds % 1000) * 1000000L };
    while (nanosleep(&delay, &delay) != 0) {
        if (errno != EINTR) return -errno;
    }
    return 0;
}
