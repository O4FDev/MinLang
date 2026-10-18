#define _GNU_SOURCE 1
#ifdef __APPLE__
#define _DARWIN_C_SOURCE 1
#include <mach-o/dyld.h>
#endif
#include "../runtime/minyar_native.h"
#include <errno.h>
#include <sys/stat.h>
#include <unistd.h>

static MinyarText *testing_text(const char *value) {
    return minyar_native_copy_text((const unsigned char *)value, (long long)strlen(value));
}
static char *host_resolve(const char *path) {
    char *resolved = realpath(path, NULL);
    if (resolved)
        return resolved;
    if (errno != ENOENT && errno != ENOTDIR)
        return NULL;
    size_t length = strlen(path);
    while (length > 1 && path[length - 1] == '/')
        length--;
    size_t slash = length;
    while (slash > 0 && path[slash - 1] != '/')
        slash--;
    const char *name = path + slash;
    size_t name_length = length - slash;
    char *parent;
    if (slash == 0) {
        parent = getcwd(NULL, 0);
    } else {
        char *prefix = malloc(slash + 1);
        if (!prefix)
            return NULL;
        memcpy(prefix, path, slash);
        prefix[slash] = 0;
        size_t end = slash;
        while (end > 1 && prefix[end - 1] == '/')
            prefix[--end] = 0;
        parent = host_resolve(prefix);
        free(prefix);
    }
    if (!parent)
        return NULL;
    if ((name_length == 1 && name[0] == '.') || name_length == 0)
        return parent;
    if (name_length == 2 && name[0] == '.' && name[1] == '.') {
        char *last = strrchr(parent, '/');
        if (last && last != parent)
            *last = 0;
        else if (last)
            parent[1] = 0;
        return parent;
    }
    size_t parent_length = strlen(parent);
    int separator = parent_length > 0 && parent[parent_length - 1] != '/';
    char *joined = malloc(parent_length + (size_t)separator + name_length + 1);
    if (!joined) {
        free(parent);
        return NULL;
    }
    memcpy(joined, parent, parent_length);
    if (separator)
        joined[parent_length] = '/';
    memcpy(joined + parent_length + separator, name, name_length);
    joined[parent_length + separator + name_length] = 0;
    free(parent);
    return joined;
}

MinyarText *minyar_testinghost_resolvePath(const MinyarText *path) {
    if (!path || path->byte_length <= 0 || memchr(path->bytes, 0, (size_t)path->byte_length))
        return testing_text("");
    char *name = malloc((size_t)path->byte_length + 1);
    if (!name)
        return testing_text("");
    memcpy(name, path->bytes, (size_t)path->byte_length);
    name[path->byte_length] = 0;
    char *resolved = host_resolve(name);
    free(name);
    MinyarText *result = testing_text(resolved ? resolved : "");
    free(resolved);
    return result;
}
MinyarText *minyar_testinghost_selfPath(void) {
#ifdef __APPLE__
    uint32_t size = 0;
    _NSGetExecutablePath(NULL, &size);
    char *buffer = malloc(size + 1);
    if (!buffer || _NSGetExecutablePath(buffer, &size)) {
        free(buffer);
        return testing_text("");
    }
    char *resolved = realpath(buffer, NULL);
    free(buffer);
#else
    char *resolved = realpath("/proc/self/exe", NULL);
#endif
    MinyarText *result = testing_text(resolved ? resolved : "");
    free(resolved);
    return result;
}
