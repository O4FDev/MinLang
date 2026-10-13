#define _GNU_SOURCE 1
#include "../../runtime/minyar_native.h"
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <sys/stat.h>
#include <unistd.h>

static char *sortbench_path(const MinyarText *path) {
    if (!path || path->byte_length < 1 || (unsigned long long)path->byte_length >= SIZE_MAX ||
        memchr(path->bytes, 0, (size_t)path->byte_length)) return NULL;
    char *name = malloc((size_t)path->byte_length + 1);
    if (!name) return NULL;
    memcpy(name, path->bytes, (size_t)path->byte_length);
    name[path->byte_length] = 0;
    return name;
}
long long minyar_sortbench_lock(const MinyarText *path) {
    char *name = sortbench_path(path);
    if (!name) return -EINVAL;
    struct stat inherited, selected;
    if (!fstat(9, &inherited) && !stat(name, &selected) &&
        inherited.st_dev == selected.st_dev && inherited.st_ino == selected.st_ino) {
        free(name);
        return S_ISREG(inherited.st_mode) ? 9 : -EINVAL;
    }
    free(name);
    return -EXDEV;
}
long long minyar_sortbench_parentPid(void) { return getppid(); }
MinyarBytes *minyar_sortbench_readLink(const MinyarText *path) {
    char *name = sortbench_path(path);
    if (!name) return minyar_bytes_new(0);
    size_t capacity = 256;
    for (;;) {
        char *buffer = malloc(capacity);
        if (!buffer) { free(name); return minyar_bytes_new(0); }
        ssize_t length = readlink(name, buffer, capacity);
        if (length < 0) { free(buffer); free(name); return minyar_bytes_new(0); }
        if ((size_t)length < capacity) {
            MinyarBytes *result = minyar_bytes_new(length);
            memcpy((void *)result->bytes, buffer, (size_t)length);
            free(buffer);
            free(name);
            return result;
        }
        free(buffer);
        if (capacity > SIZE_MAX / 2) { free(name); return minyar_bytes_new(0); }
        capacity *= 2;
    }
}
