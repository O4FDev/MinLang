#include "../runtime/minyar_native.h"
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <sys/stat.h>
#include <time.h>

#if defined(__APPLE__)
#define TOOLCHAIN_MTIME(info) ((long long)(info).st_mtimespec.tv_sec * 1000000000LL + (long long)(info).st_mtimespec.tv_nsec)
#define TOOLCHAIN_ATIME(info) ((long long)(info).st_atimespec.tv_sec * 1000000000LL + (long long)(info).st_atimespec.tv_nsec)
#else
#define TOOLCHAIN_MTIME(info) ((long long)(info).st_mtim.tv_sec * 1000000000LL + (long long)(info).st_mtim.tv_nsec)
#define TOOLCHAIN_ATIME(info) ((long long)(info).st_atim.tv_sec * 1000000000LL + (long long)(info).st_atim.tv_nsec)
#endif

static int toolchain_path(const MinyarText *text, char *out) {
    if (!text || text->byte_length <= 0) return -ENOENT;
    if (text->byte_length >= PATH_MAX) return -ENAMETOOLONG;
    if (memchr(text->bytes, 0, (size_t)text->byte_length)) return -EINVAL;
    memcpy(out, text->bytes, (size_t)text->byte_length);
    out[text->byte_length] = 0;
    return 0;
}

static int toolchain_stat(const MinyarText *path, struct stat *info) {
    char buffer[PATH_MAX];
    int error = toolchain_path(path, buffer);
    if (error) return error;
    if (stat(buffer, info) != 0) return -errno;
    return 0;
}

long long minyar_toolchainfiles_modified(const MinyarText *path) {
    struct stat info;
    int error = toolchain_stat(path, &info);
    return error ? error : TOOLCHAIN_MTIME(info);
}

long long minyar_toolchainfiles_accessed(const MinyarText *path) {
    struct stat info;
    int error = toolchain_stat(path, &info);
    return error ? error : TOOLCHAIN_ATIME(info);
}

long long minyar_toolchainfiles_setTimes(const MinyarText *path, long long accessed, long long modified) {
    char buffer[PATH_MAX];
    int error = toolchain_path(path, buffer);
    if (error) return error;
    if (accessed < 0 || modified < 0) return -EINVAL;
    struct timespec times[2];
    times[0].tv_sec = (time_t)(accessed / 1000000000LL);
    times[0].tv_nsec = (long)(accessed % 1000000000LL);
    times[1].tv_sec = (time_t)(modified / 1000000000LL);
    times[1].tv_nsec = (long)(modified % 1000000000LL);
    if (utimensat(AT_FDCWD, buffer, times, 0) != 0) return -errno;
    return 0;
}

MinyarText *minyar_toolchainfiles_identity(const MinyarText *path) {
    struct stat info;
    char text[64];
    int length = 0;
    if (toolchain_stat(path, &info) == 0) {
        length = snprintf(text, sizeof text, "%llu:%llu", (unsigned long long)info.st_dev, (unsigned long long)info.st_ino);
        if (length < 0 || length >= (int)sizeof text) length = 0;
    }
    return minyar_native_copy_text((const unsigned char *)text, length);
}

long long minyar_toolchainfiles_pause(long long milliseconds) {
    if (milliseconds < 0) return -EINVAL;
    struct timespec delay = { (time_t)(milliseconds / 1000), (long)(milliseconds % 1000) * 1000000L };
    while (nanosleep(&delay, &delay) != 0) {
        if (errno != EINTR) return -errno;
    }
    return 0;
}
