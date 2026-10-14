#define _GNU_SOURCE
#include "../runtime/minyar_native.h"
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <openssl/evp.h>
#include <stdio.h>
#include <sys/stat.h>
#include <unistd.h>

static int release_path(const MinyarText *text, char *out) {
    if (text->byte_length <= 0 || text->byte_length >= PATH_MAX) return -ENAMETOOLONG;
    if (memchr(text->bytes, 0, (size_t)text->byte_length)) return -EINVAL;
    memcpy(out, text->bytes, (size_t)text->byte_length);
    out[text->byte_length] = 0;
    return 0;
}

static MinyarText *release_text(const char *value) {
    return minyar_native_copy_text((const unsigned char *)value, (long long)strlen(value));
}

long long minyar_releasenative_kindOf(const MinyarText *path) {
    char p[PATH_MAX];
    int rc = release_path(path, p);
    if (rc) return rc;
    struct stat st;
    if (lstat(p, &st) != 0) return errno == ENOENT || errno == ENOTDIR ? 0 : -errno;
    if (S_ISREG(st.st_mode)) return 1;
    if (S_ISDIR(st.st_mode)) return 2;
    if (S_ISLNK(st.st_mode)) return 3;
    return 4;
}

MinyarText *minyar_releasenative_realpath(const MinyarText *path) {
    char p[PATH_MAX], resolved[PATH_MAX];
    if (release_path(path, p) || !realpath(p, resolved)) return release_text("");
    return release_text(resolved);
}

MinyarText *minyar_releasenative_readLink(const MinyarText *path) {
    char p[PATH_MAX], target[PATH_MAX];
    if (release_path(path, p)) return release_text("");
    ssize_t length = readlink(p, target, sizeof(target) - 1);
    if (length < 0) return release_text("");
    target[length] = 0;
    return release_text(target);
}

MinyarText *minyar_releasenative_currentDirectory(void) {
    char directory[PATH_MAX];
    if (!getcwd(directory, sizeof(directory))) return release_text("");
    return release_text(directory);
}

MinyarText *minyar_releasenative_temporaryDirectory(const MinyarText *parent, const MinyarText *prefix) {
    char p[PATH_MAX], name[PATH_MAX];
    if (release_path(parent, p) || prefix->byte_length <= 0 || prefix->byte_length > 64) return release_text("");
    char start[65];
    minyar_native_text(prefix, start, sizeof(start));
    if (snprintf(name, sizeof(name), "%s/%sXXXXXXXX", p, start) >= (int)sizeof(name)) return release_text("");
    if (!mkdtemp(name)) return release_text("");
    return release_text(name);
}

long long minyar_releasenative_exclusiveRename(const MinyarText *from, const MinyarText *to) {
    char a[PATH_MAX], b[PATH_MAX];
    int rc = release_path(from, a);
    if (rc) return rc;
    rc = release_path(to, b);
    if (rc) return rc;
#if defined(__APPLE__)
    return renamex_np(a, b, RENAME_EXCL) == 0 ? 0 : -errno;
#elif defined(__linux__)
    return renameat2(AT_FDCWD, a, AT_FDCWD, b, RENAME_NOREPLACE) == 0 ? 0 : -errno;
#else
    return -ENOSYS;
#endif
}

MinyarText *minyar_releasenative_sha1(const MinyarBytes *data) {
    unsigned char digest[EVP_MAX_MD_SIZE];
    unsigned int length = 0;
    if (!EVP_Digest(data->bytes, (size_t)data->byte_length, digest, &length, EVP_sha1(), NULL))
        minyar_native_stop("SHA-1 digest failed");
    char hex[2 * EVP_MAX_MD_SIZE + 1];
    for (unsigned int i = 0; i < length; i++) snprintf(hex + 2 * i, 3, "%02x", digest[i]);
    return release_text(hex);
}
