/* Narrow updater hooks. Policy, hashing and version checks live in update.min.
 * The application owns the protected installation directory. No downloaded
 * path or shell command is ever evaluated. State is the sole active pointer.
 */
#include "../minyar_native.h"
#include "../../vendor/monocypher/monocypher-ed25519.h"
#include <errno.h>
#include <limits.h>
#include <sys/stat.h>
#include <stdint.h>
#ifdef _WIN32
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0601
#endif
#include <windows.h>
#include <io.h>
#include <fcntl.h>
#define upd_close _close
#define upd_read _read
#define upd_write _write
#define upd_commit _commit
#else
#include <fcntl.h>
#include <sys/file.h>
#include <unistd.h>
#include <dirent.h>
#include <sys/wait.h>
#include <sys/resource.h>
#define upd_close close
#define upd_read read
#define upd_write write
#define upd_commit fsync
#endif

enum { UPD_PATH = 2048, UPD_STATE = 4096, UPD_ARTIFACT = 134217728, UPD_HANDLES = 8 };
typedef struct {
    long long id;
    char root[UPD_PATH];
#ifdef _WIN32
    HANDLE lock;
    HANDLE anchors[64];
    size_t anchor_count;
#else
    int lock;
    int root_fd;
#endif
} UpdateSession;
static UpdateSession sessions[UPD_HANDLES];
static long long next_id;
static char last_error[256];
#ifdef MINYAR_UPDATE_TEST_HOOK
extern void minyar_update_test_hook(const char *point);
#define UPDATE_HOOK(point) minyar_update_test_hook(point)
#else
#define UPDATE_HOOK(point) ((void)0)
#endif

static bool problem(const char *message) {
    snprintf(last_error, sizeof(last_error), "%s", message);
    return false;
}

MinyarText *minyar_update_lastError(void) {
    return minyar_native_copy_text((const unsigned char *)last_error,
                                   (long long)strlen(last_error));
}

MinyarText *minyar_update_hostTarget(void) {
#ifdef _WIN32
    const char *system = "windows-";
#elif defined(__APPLE__)
    const char *system = "macos-";
#elif defined(__linux__)
    const char *system = "linux-";
#else
    const char *system = "unsupported-";
#endif
#if defined(__aarch64__) || defined(_M_ARM64)
    const char *architecture = "arm64";
#else
    const char *architecture = "x86_64";
#endif
    char target[40];
    snprintf(target, sizeof(target), "%s%s", system, architecture);
    return minyar_native_copy_text((const unsigned char *)target, (long long)strlen(target));
}

static UpdateSession *session(long long id) {
    for (int i = 0; i < UPD_HANDLES; i++)
        if (sessions[i].id == id && id > 0)
            return &sessions[i];
    problem("invalid or closed update session");
    return NULL;
}

bool minyar_update_verify(const MinyarBytes *message, const MinyarBytes *signature,
                          const MinyarBytes *key) {
    if (message->byte_length < 0 || message->byte_length > 8192 || signature->byte_length != 64 ||
        key->byte_length != 32)
        return false;
    /* A configured public key must be a real generated key, never zero bytes. */
    unsigned char nonzero = 0;
    for (int i = 0; i < 32; i++)
        nonzero |= key->bytes[i];
    return nonzero && crypto_ed25519_check(signature->bytes, key->bytes, message->bytes,
                                           (size_t)message->byte_length) == 0;
}

#ifndef _WIN32
/* Every operation below starts from the pinned root descriptor. Intermediate
 * components are opened one at a time without following links. */
static int safe_parent(const char *path, char leaf[UPD_PATH]) {
    const char *relative = path;
    int parent = -1;
    for (int i = 0; i < UPD_HANDLES; i++) {
        size_t n = strlen(sessions[i].root);
        if (sessions[i].id && n && !strncmp(path, sessions[i].root, n) && path[n] == '/') {
            parent = fcntl(sessions[i].root_fd, F_DUPFD_CLOEXEC, 3);
            relative = path + n + 1;
            break;
        }
    }
    if (parent < 0) {
        if (path[0] != '/') {
            errno = EINVAL;
            return -1;
        }
        parent = open("/", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
        relative = path + 1;
    }
    if (parent < 0)
        return -1;
    size_t n = strlen(relative);
    if (n >= UPD_PATH) {
        close(parent);
        errno = ENAMETOOLONG;
        return -1;
    }
    memcpy(leaf, relative, n + 1);
    char *component = leaf, *slash;
    while ((slash = strchr(component, '/'))) {
        *slash = 0;
        if (!*component || !strcmp(component, ".") || !strcmp(component, "..")) {
            close(parent);
            errno = EINVAL;
            return -1;
        }
        int next = openat(parent, component, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        close(parent);
        if (next < 0)
            return -1;
        parent = next;
        component = slash + 1;
    }
    if (!*component || !strcmp(component, ".") || !strcmp(component, "..")) {
        close(parent);
        errno = EINVAL;
        return -1;
    }
    memmove(leaf, component, strlen(component) + 1);
    return parent;
}
static int directory_fd(const char *path) {
    char leaf[UPD_PATH];
    int parent = safe_parent(path, leaf);
    if (parent < 0)
        return -1;
    int fd = openat(parent, leaf, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    close(parent);
    return fd;
}
#endif
#ifdef _WIN32
static bool wide(const char *path, wchar_t output[UPD_PATH]) {
    return MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path, -1, output, UPD_PATH) > 0;
}
/* Pin every Windows ancestor without delete sharing. Junctions, volume
 * mount reparse points, UNC roots and relative/dot paths are refused. */
static bool windows_ancestors(const char *path, bool include_leaf, UpdateSession *owner) {
    size_t n = strlen(path);
    if (n < 3 || !((path[0] >= 'A' && path[0] <= 'Z') || (path[0] >= 'a' && path[0] <= 'z')) ||
        path[1] != ':' || (path[2] != '/' && path[2] != '\\'))
        return problem("root must be an absolute local drive path");
    char part[UPD_PATH];
    if (n >= sizeof(part))
        return problem("installation path is too long");
    memcpy(part, path, n + 1);
    HANDLE temporary[64];
    size_t count = 0, start = 3;
    bool success = true;
    for (size_t i = 3; i <= n; i++) {
        if (i < n && part[i] != '/' && part[i] != '\\')
            continue;
        size_t size = i - start;
        if (!size || (size == 1 && part[start] == '.') ||
            (size == 2 && part[start] == '.' && part[start + 1] == '.')) {
            success = false;
            break;
        }
        if (i == n && !include_leaf)
            break;
        char save = part[i];
        part[i] = 0;
        wchar_t name[UPD_PATH];
        if (count == 64 || !wide(part, name)) {
            success = false;
            part[i] = save;
            break;
        }
        HANDLE handle =
            CreateFileW(name, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, NULL);
        BY_HANDLE_FILE_INFORMATION info;
        if (handle == INVALID_HANDLE_VALUE || !GetFileInformationByHandle(handle, &info) ||
            !(info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) ||
            (info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)) {
            if (handle != INVALID_HANDLE_VALUE)
                CloseHandle(handle);
            success = false;
            part[i] = save;
            break;
        }
        temporary[count++] = handle;
        part[i] = save;
        start = i + 1;
    }
    if (success && owner) {
        memcpy(owner->anchors, temporary, count * sizeof(HANDLE));
        owner->anchor_count = count;
    } else
        for (size_t i = 0; i < count; i++)
            CloseHandle(temporary[i]);
    return success || problem("installation ancestor is missing, relative or a reparse point");
}
static bool directory(const char *path) {
    wchar_t name[UPD_PATH];
    if (!windows_ancestors(path, false, NULL))
        return false;
    if (!wide(path, name))
        return problem("invalid installation path encoding");
    if (!CreateDirectoryW(name, NULL) && GetLastError() != ERROR_ALREADY_EXISTS)
        return problem("cannot create installation directory");
    DWORD attrs = GetFileAttributesW(name);
    return (attrs != INVALID_FILE_ATTRIBUTES && (attrs & FILE_ATTRIBUTE_DIRECTORY) &&
            !(attrs & FILE_ATTRIBUTE_REPARSE_POINT)) ||
           problem("installation directory is a link or not a directory");
}
static int open_file(const char *path, bool writing) {
    wchar_t name[UPD_PATH];
    if (!windows_ancestors(path, false, NULL))
        return -1;
    if (!wide(path, name))
        return -1;
    HANDLE file = CreateFileW(name, writing ? GENERIC_WRITE : GENERIC_READ, FILE_SHARE_READ, NULL,
                              writing ? CREATE_NEW : OPEN_EXISTING,
                              FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (file == INVALID_HANDLE_VALUE)
        return -1;
    BY_HANDLE_FILE_INFORMATION info;
    if (!GetFileInformationByHandle(file, &info) ||
        (info.dwFileAttributes & (FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DIRECTORY)) ||
        info.nNumberOfLinks != 1) {
        CloseHandle(file);
        return -1;
    }
    int fd = _open_osfhandle((intptr_t)file,
                             _O_BINARY | _O_NOINHERIT | (writing ? _O_WRONLY : _O_RDONLY));
    if (fd < 0)
        CloseHandle(file);
    return fd;
}
static bool replace_file(const char *source, const char *destination) {
    wchar_t from[UPD_PATH], to[UPD_PATH];
    if (!windows_ancestors(source, false, NULL) || !windows_ancestors(destination, false, NULL))
        return false;
    return wide(source, from) && wide(destination, to) &&
           MoveFileExW(from, to, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH);
}
static void remove_file(const char *path) {
    wchar_t name[UPD_PATH];
    if (wide(path, name))
        DeleteFileW(name);
}
static bool sync_directory(const char *path) {
    (void)path;
    return true;
}
#else
static bool directory(const char *path) {
    char leaf[UPD_PATH];
    int parent = safe_parent(path, leaf);
    if (parent < 0)
        return problem("unsafe installation directory path");
    bool success = mkdirat(parent, leaf, 0700) == 0 || errno == EEXIST;
    int fd = success ? openat(parent, leaf, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC) : -1;
    close(parent);
    struct stat status;
    success = fd >= 0 && fstat(fd, &status) == 0 && S_ISDIR(status.st_mode) &&
              status.st_uid == geteuid() && !(status.st_mode & 0022);
    if (fd >= 0)
        close(fd);
    return success || problem("installation directory must be owned, protected and not a symlink");
}
static int open_file(const char *path, bool writing) {
    char leaf[UPD_PATH];
    int parent = safe_parent(path, leaf);
    if (parent < 0)
        return -1;
    int fd =
        openat(parent, leaf,
               (writing ? O_WRONLY | O_CREAT | O_EXCL : O_RDONLY) | O_NOFOLLOW | O_CLOEXEC, 0600);
    int saved = errno;
    close(parent);
    errno = saved;
    struct stat status;
    if (fd >= 0 &&
        (fstat(fd, &status) < 0 || !S_ISREG(status.st_mode) || status.st_uid != geteuid() ||
         (status.st_mode & 0022) || status.st_nlink != 1)) {
        close(fd);
        errno = EPERM;
        return -1;
    }
    return fd;
}
static bool replace_file(const char *source, const char *destination) {
    char from[UPD_PATH], to[UPD_PATH];
    int a = safe_parent(source, from), b = safe_parent(destination, to);
    bool success = a >= 0 && b >= 0 && renameat(a, from, b, to) == 0;
    if (a >= 0)
        close(a);
    if (b >= 0)
        close(b);
    return success;
}
static void remove_file(const char *path) {
    char leaf[UPD_PATH];
    int parent = safe_parent(path, leaf);
    if (parent >= 0) {
        unlinkat(parent, leaf, 0);
        close(parent);
    }
}
static bool sync_directory(const char *path) {
    int fd = directory_fd(path);
    if (fd < 0)
        return false;
    bool success = fsync(fd) == 0;
    close(fd);
    return success;
}
#endif

static bool join(char output[UPD_PATH], const char *root, const char *leaf) {
    int length = snprintf(output, UPD_PATH, "%s/%s", root, leaf);
    return (length >= 0 && length < UPD_PATH) || problem("installation path is too long");
}

long long minyar_update_begin(const MinyarText *root) {
    last_error[0] = 0;
    if (root->byte_length < 1 || root->byte_length > UPD_PATH - 160 ||
        memchr(root->bytes, 0, (size_t)root->byte_length)) {
        problem("invalid installation directory");
        return -1;
    }
    UpdateSession *found = NULL;
    for (int i = 0; i < UPD_HANDLES; i++)
        if (!sessions[i].id) {
            found = &sessions[i];
            break;
        }
    if (!found || next_id == LLONG_MAX) {
        problem("too many update sessions");
        return -1;
    }
    if (root->bytes[0] != '/') {
#ifdef _WIN32
        /* Windows accepts an absolute drive path below. */
        if (root->byte_length < 3 || root->bytes[1] != ':' ||
            (root->bytes[2] != '/' && root->bytes[2] != '\\')) {
            problem("installation directory must be absolute");
            return -1;
        }
#else
        problem("installation directory must be absolute");
        return -1;
#endif
    }
    memcpy(found->root, root->bytes, (size_t)root->byte_length);
    found->root[root->byte_length] = 0;
#ifdef __APPLE__
    /* macOS has root-owned OS aliases /var and /tmp. Normalize only these
     * known prefixes; arbitrary application symlink ancestors still fail. */
    if (!strncmp(found->root, "/var/", 5) || !strncmp(found->root, "/tmp/", 5)) {
        char alias[5];
        memcpy(alias, found->root, 4);
        alias[4] = 0;
        struct stat status;
        char target[32];
        ssize_t size = readlink(alias, target, sizeof(target) - 1);
        if (size >= 0)
            target[size] = 0;
        const char *expected = alias[1] == 'v' ? "private/var" : "private/tmp";
        char absolute_expected[32];
        snprintf(absolute_expected, sizeof(absolute_expected), "/%s", expected);
        if (lstat(alias, &status) < 0 || status.st_uid != 0 || !S_ISLNK(status.st_mode) ||
            size < 0 || (strcmp(target, expected) && strcmp(target, absolute_expected))) {
            problem("unsafe macOS system path alias");
            return -1;
        }
        char canonical[UPD_PATH];
        int length = snprintf(canonical, sizeof(canonical), "/private%s", found->root);
        if (length < 0 || length >= (int)sizeof(canonical)) {
            problem("installation path is too long");
            return -1;
        }
        /* Only the OS alias is replaced. Every remaining component is still
         * opened without following links; realpath would launder child links. */
        snprintf(found->root, sizeof(found->root), "%s", canonical);
    }
#endif
    char lock_path[UPD_PATH];
#ifndef _WIN32
    found->root_fd = directory_fd(found->root);
    if (found->root_fd < 0) {
        problem("installation root or ancestor is a link or missing");
        return -1;
    }
#endif
    if (!directory(found->root) || !join(lock_path, found->root, ".update-lock")) {
#ifndef _WIN32
        close(found->root_fd);
#endif
        return -1;
    }
#ifdef _WIN32
    found->anchor_count = 0;
    if (!windows_ancestors(found->root, true, found))
        return -1;
    wchar_t name[UPD_PATH];
    if (!wide(lock_path, name))
        return -1;
    found->lock = CreateFileW(name, GENERIC_READ | GENERIC_WRITE, 0, NULL, OPEN_ALWAYS,
                              FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (found->lock == INVALID_HANDLE_VALUE) {
        for (size_t i = 0; i < found->anchor_count; i++)
            CloseHandle(found->anchors[i]);
        found->anchor_count = 0;
        problem("another updater holds the installation lock");
        return -1;
    }
    BY_HANDLE_FILE_INFORMATION info;
    if (!GetFileInformationByHandle(found->lock, &info) ||
        (info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)) {
        CloseHandle(found->lock);
        for (size_t i = 0; i < found->anchor_count; i++)
            CloseHandle(found->anchors[i]);
        found->anchor_count = 0;
        problem("installation lock is a link");
        return -1;
    }
#else
    found->lock =
        openat(found->root_fd, ".update-lock", O_RDWR | O_CREAT | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (found->lock < 0 || flock(found->lock, LOCK_EX | LOCK_NB) < 0) {
        if (found->lock >= 0)
            close(found->lock);
        close(found->root_fd);
        problem("another updater holds the installation lock");
        return -1;
    }
    struct stat lock_status;
    if (fstat(found->lock, &lock_status) < 0 || !S_ISREG(lock_status.st_mode) ||
        lock_status.st_uid != geteuid() || (lock_status.st_mode & 0022) ||
        lock_status.st_nlink != 1) {
        close(found->lock);
        close(found->root_fd);
        problem("installation lock must be an owned regular file");
        return -1;
    }
#endif
    found->id = ++next_id;
    return found->id;
}

void minyar_update_end(long long id) {
    UpdateSession *found = session(id);
    if (!found)
        return;
#ifdef _WIN32
    CloseHandle(found->lock);
    for (size_t i = 0; i < found->anchor_count; i++)
        CloseHandle(found->anchors[i]);
    found->anchor_count = 0;
#else
    close(found->lock);
    close(found->root_fd);
#endif
    found->id = 0;
}

MinyarBytes *minyar_update_readState(long long id) {
    last_error[0] = 0;
    MinyarBytes *result = minyar_bytes_new(0);
    UpdateSession *found = session(id);
    char path[UPD_PATH];
    if (!found || !join(path, found->root, "state"))
        return result;
    int fd = open_file(path, false);
    if (fd < 0) {
#ifdef _WIN32
        if (GetLastError() != ERROR_FILE_NOT_FOUND)
            problem("cannot safely read update state");
#else
        if (errno != ENOENT)
            problem("cannot safely read update state");
#endif
        return result;
    }
    unsigned char buffer[UPD_STATE + 1];
    size_t total = 0;
    while (total < sizeof(buffer)) {
        int count = (int)upd_read(fd, buffer + total, (unsigned int)(sizeof(buffer) - total));
        if (count < 0 && errno == EINTR)
            continue;
        if (count < 0) {
            problem("cannot read update state");
            break;
        }
        if (!count)
            break;
        total += (size_t)count;
    }
    upd_close(fd);
    if (total > UPD_STATE || total == 0)
        problem("update state is empty or too large");
    if (!last_error[0])
        memcpy(minyar_bytes_extend(result, (long long)total), buffer, total);
    return result;
}

static bool publish(UpdateSession *found, const char *destination, const MinyarBytes *data,
                    bool executable) {
    char temporary[UPD_PATH], leaf[128];
    snprintf(leaf, sizeof(leaf), ".update-%lld-%lld.tmp",
             (long long)
#ifdef _WIN32
                 GetCurrentProcessId(),
#else
                 getpid(),
#endif
             found->id);
    if (!join(temporary, found->root, leaf))
        return false;
    int fd = open_file(temporary, true);
    if (fd < 0)
        return problem("cannot create update staging file");
    long long written = 0;
    bool success = true;
    while (written < data->byte_length) {
        unsigned int amount =
            (unsigned int)((data->byte_length - written) > 65536 ? 65536
                                                                 : data->byte_length - written);
        int count = (int)upd_write(fd, data->bytes + written, amount);
        if (count < 0 && errno == EINTR)
            continue;
        if (count <= 0) {
            success = false;
            break;
        }
        written += count;
    }
#ifndef _WIN32
    if (success && executable && fchmod(fd, 0555) < 0)
        success = false;
#else
    (void)executable;
#endif
    if (success && upd_commit(fd) < 0)
        success = false;
    if (upd_close(fd) < 0)
        success = false;
    if (success)
        UPDATE_HOOK(executable ? "artifact-before-replace" : "state-before-replace");
    if (success)
        success = replace_file(temporary, destination);
    if (success)
        success = sync_directory(found->root);
    if (!success) {
        remove_file(temporary);
        return problem("atomic update publication failed");
    }
    return true;
}

bool minyar_update_storeState(long long id, const MinyarBytes *state) {
    last_error[0] = 0;
    UpdateSession *found = session(id);
    char path[UPD_PATH];
    if (!found || state->byte_length < 1 || state->byte_length > UPD_STATE ||
        !join(path, found->root, "state"))
        return problem("invalid update state");
    return publish(found, path, state, false);
}

bool minyar_update_activate(long long id, const MinyarText *digest, const MinyarBytes *artifact,
                            const MinyarBytes *state) {
    UpdateSession *found = session(id);
    if (!found || digest->byte_length != 64 || artifact->byte_length < 1 ||
        artifact->byte_length > UPD_ARTIFACT || state->byte_length < 1 ||
        state->byte_length > UPD_STATE)
        return problem("invalid activation arguments");
    for (int i = 0; i < 64; i++)
        if (!((digest->bytes[i] >= '0' && digest->bytes[i] <= '9') ||
              (digest->bytes[i] >= 'a' && digest->bytes[i] <= 'f')))
            return problem("invalid artifact digest");
    char versions[UPD_PATH], path[UPD_PATH], name[80];
    if (!join(versions, found->root, "versions") || !directory(versions))
        return false;
    memcpy(name, digest->bytes, 64);
#ifdef _WIN32
    memcpy(name + 64, ".exe", 5);
#else
    memcpy(name + 64, ".bin", 5);
#endif
    if (!join(path, versions, name) || !publish(found, path, artifact, true) ||
        !sync_directory(versions))
        return false;
    UPDATE_HOOK("artifact-after-replace");
    /* Only this state replacement activates the new immutable executable.
     * An interruption before it leaves the previous active generation intact. */
    bool success = minyar_update_storeState(id, state);
    if (success)
        UPDATE_HOOK("state-after-replace");
    return success;
}

#include "update_bundle.h"

static bool digest_name(const MinyarText *digest, char out[65]) {
    if (digest->byte_length != 64)
        return problem("invalid generation digest");
    for (size_t i = 0; i < 64; i++)
        if (!((digest->bytes[i] >= '0' && digest->bytes[i] <= '9') ||
              (digest->bytes[i] >= 'a' && digest->bytes[i] <= 'f')))
            return problem("invalid generation digest");
    memcpy(out, digest->bytes, 64);
    out[64] = 0;
    return true;
}
static bool generation_path(UpdateSession *found, const MinyarText *digest, const char *suffix,
                            char path[UPD_PATH]) {
    char hash[65], leaf[160];
    if (!digest_name(digest, hash))
        return false;
    snprintf(leaf, sizeof(leaf), "versions/%s%s", hash, suffix);
    return join(path, found->root, leaf);
}
static MinyarBytes *read_bounded(const char *path, size_t limit) {
    MinyarBytes *bytes = minyar_bytes_new(0);
    int fd = open_file(path, false);
    if (fd < 0) {
        problem("cannot safely open generation file");
        return bytes;
    }
    struct stat status;
#ifdef _WIN32
    struct _stat64 info;
    bool success = _fstat64(fd, &info) == 0 && info.st_size >= 0 && (uint64_t)info.st_size <= limit;
    size_t expected = success ? (size_t)info.st_size : 0;
    (void)status;
#else
    bool success =
        fstat(fd, &status) == 0 && status.st_size >= 0 && (uint64_t)status.st_size <= limit;
    size_t expected = success ? (size_t)status.st_size : 0;
#endif
    if (success) {
        unsigned char *destination = minyar_bytes_extend(bytes, (long long)expected);
        size_t at = 0;
        while (at < expected) {
            int n = (int)upd_read(fd, destination + at,
                                  (unsigned int)((expected - at) > 65536 ? 65536 : expected - at));
            if (n < 0 && errno == EINTR)
                continue;
            if (n <= 0) {
                success = false;
                break;
            }
            at += (size_t)n;
        }
        unsigned char extra;
        if (success && upd_read(fd, &extra, 1) != 0)
            success = false;
    }
    upd_close(fd);
    if (!success)
        problem("generation file is incomplete or exceeds its size limit");
    return bytes;
}
static bool same_bytes(int fd, const unsigned char *expected, size_t length) {
#ifdef _WIN32
    if (_lseeki64(fd, 0, SEEK_SET) < 0)
        return false;
#else
    if (lseek(fd, 0, SEEK_SET) < 0)
        return false;
#endif
    size_t at = 0;
    unsigned char buffer[65536];
    while (at < length) {
        size_t amount = length - at;
        if (amount > sizeof(buffer))
            amount = sizeof(buffer);
        int n = (int)upd_read(fd, buffer, (unsigned int)amount);
        if (n < 0 && errno == EINTR)
            continue;
        if (n <= 0 || memcmp(buffer, expected + at, (size_t)n))
            return false;
        at += (size_t)n;
    }
    int n;
    do {
        n = (int)upd_read(fd, buffer, 1);
    } while (n < 0 && errno == EINTR);
    return n == 0;
}
static bool native_image(const unsigned char *bytes, size_t size) {
    if (size < 4)
        return false;
#ifdef _WIN32
    return bytes[0] == 'M' && bytes[1] == 'Z';
#elif defined(__APPLE__)
    uint32_t magic;
    memcpy(&magic, bytes, 4);
    return magic == 0xfeedface || magic == 0xcefaedfe || magic == 0xfeedfacf ||
           magic == 0xcffaedfe || magic == 0xcafebabe || magic == 0xbebafeca ||
           magic == 0xcafebabf || magic == 0xbfbafeca;
#else
    return !memcmp(bytes,
                   "\x7f"
                   "ELF",
                   4);
#endif
}
static bool write_new(const char *path, const unsigned char *bytes, size_t size, bool executable) {
    int fd = open_file(path, true);
    if (fd < 0)
        return problem("cannot create bundle file");
    bool success = true;
    size_t at = 0;
    while (at < size) {
        size_t amount = size - at;
        if (amount > 65536)
            amount = 65536;
        int n = (int)upd_write(fd, bytes + at, (unsigned int)amount);
        if (n < 0 && errno == EINTR)
            continue;
        if (n <= 0) {
            success = false;
            break;
        }
        at += (size_t)n;
    }
#ifndef _WIN32
    if (success && fchmod(fd, executable ? 0555 : 0444) < 0)
        success = false;
#else
    (void)executable;
#endif
    if (success && upd_commit(fd) < 0)
        success = false;
    if (upd_close(fd) < 0)
        success = false;
    return success || problem("cannot durably write bundle file");
}
static bool bundle_file_path(const char *payload, const BundleEntry *entry, char out[UPD_PATH]) {
    return join(out, payload, entry->path);
}

#ifdef _WIN32
static int pin_directory(const char *path) {
    wchar_t name[UPD_PATH];
    if (!windows_ancestors(path, false, NULL))
        return -1;
    if (!wide(path, name))
        return -1;
    HANDLE handle = CreateFileW(name, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                                FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (handle == INVALID_HANDLE_VALUE)
        return -1;
    BY_HANDLE_FILE_INFORMATION info;
    if (!GetFileInformationByHandle(handle, &info) ||
        !(info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) ||
        (info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)) {
        CloseHandle(handle);
        return -1;
    }
    int fd = _open_osfhandle((intptr_t)handle, _O_RDONLY | _O_BINARY);
    if (fd < 0)
        CloseHandle(handle);
    return fd;
}
#else
static int pin_directory(const char *path) {
    return directory_fd(path);
}
#endif

static bool identity_matches(int original, const char *path, bool is_directory) {
    int current = is_directory ? pin_directory(path) : open_file(path, false);
    if (current < 0)
        return false;
#ifdef _WIN32
    BY_HANDLE_FILE_INFORMATION a, b;
    bool success = GetFileInformationByHandle((HANDLE)_get_osfhandle(original), &a) &&
                   GetFileInformationByHandle((HANDLE)_get_osfhandle(current), &b) &&
                   a.dwVolumeSerialNumber == b.dwVolumeSerialNumber &&
                   a.nFileIndexHigh == b.nFileIndexHigh && a.nFileIndexLow == b.nFileIndexLow;
#else
    struct stat a, b;
    bool success = fstat(original, &a) == 0 && fstat(current, &b) == 0 && a.st_dev == b.st_dev &&
                   a.st_ino == b.st_ino;
#endif
    upd_close(current);
    return success;
}
static bool tree_contains(const UpdateBundle *bundle, const char *path, bool directory_entry) {
    for (size_t i = 0; i < bundle->count; i++)
        if (!strcmp(bundle->entries[i].path, path) &&
            (bundle->entries[i].type == 'D') == directory_entry)
            return true;
    return false;
}
/* Enumerate as well as check indexed files: extra loader code/resources fail
 * closed rather than being silently accepted beside the authenticated tree. */
static bool tree_exact(const char *payload, const char *relative, const UpdateBundle *bundle,
                       size_t *count) {
    char path[UPD_PATH];
    if (relative[0]) {
        if (!join(path, payload, relative))
            return false;
    } else if (snprintf(path, sizeof(path), "%s", payload) >= (int)sizeof(path))
        return false;
#ifdef _WIN32
    wchar_t search[UPD_PATH];
    char pattern[UPD_PATH];
    if (!join(pattern, path, "*") || !wide(pattern, search))
        return false;
    WIN32_FIND_DATAW info;
    HANDLE stream = FindFirstFileW(search, &info);
    if (stream == INVALID_HANDLE_VALUE)
        return GetLastError() == ERROR_FILE_NOT_FOUND;
    bool success = true;
    do {
        if (!wcscmp(info.cFileName, L".") || !wcscmp(info.cFileName, L".."))
            continue;
        char leaf[UPD_BUNDLE_PATH + 1];
        if (!WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, info.cFileName, -1, leaf,
                                 sizeof(leaf), NULL, NULL)) {
            success = false;
            break;
        }
        char child[UPD_BUNDLE_PATH + 1];
        int n = snprintf(child, sizeof(child), "%s%s%s", relative, relative[0] ? "/" : "", leaf);
        bool dir = (info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
        if (n < 0 || n > UPD_BUNDLE_PATH ||
            (info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) ||
            !tree_contains(bundle, child, dir) || ++*count > bundle->count ||
            (dir && !tree_exact(payload, child, bundle, count))) {
            success = false;
            break;
        }
    } while (FindNextFileW(stream, &info));
    DWORD error = GetLastError();
    FindClose(stream);
    return success && error == ERROR_NO_MORE_FILES;
#else
    int fd = directory_fd(path);
    if (fd < 0)
        return false;
    DIR *stream = fdopendir(fd);
    if (!stream) {
        close(fd);
        return false;
    }
    bool success = true;
    struct dirent *entry;
    errno = 0;
    while ((entry = readdir(stream))) {
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, ".."))
            continue;
        char child[UPD_BUNDLE_PATH + 1];
        int n = snprintf(child, sizeof(child), "%s%s%s", relative, relative[0] ? "/" : "",
                         entry->d_name);
        struct stat status;
        if (n < 0 || n > UPD_BUNDLE_PATH ||
            fstatat(fd, entry->d_name, &status, AT_SYMLINK_NOFOLLOW) < 0 ||
            (!S_ISDIR(status.st_mode) && !S_ISREG(status.st_mode)) ||
            !tree_contains(bundle, child, S_ISDIR(status.st_mode)) || ++*count > bundle->count ||
            (S_ISDIR(status.st_mode) && !tree_exact(payload, child, bundle, count))) {
            success = false;
            break;
        }
        errno = 0;
    }
    if (!entry && errno)
        success = false;
    closedir(stream);
    return success;
#endif
}
static bool bundle_check(const char *payload, const UpdateBundle *bundle, int *pins) {
    for (size_t i = 0; i < bundle->count; i++) {
        char path[UPD_PATH];
        const BundleEntry *entry = &bundle->entries[i];
        if (!bundle_file_path(payload, entry, path))
            return false;
        int fd = entry->type == 'D' ? pin_directory(path) : open_file(path, false);
        if (fd < 0)
            return problem("bundle entry is missing, unsafe or locked by a writer");
        pins[i] = fd;
        if (entry->type == 'F' && !same_bytes(fd, entry->data, entry->size))
            return problem("bundle file differs from authenticated package");
#ifndef _WIN32
        struct stat status;
        if (fstat(fd, &status) < 0 || status.st_uid != geteuid() ||
            (entry->type == 'D' ? (status.st_mode & 0022) != 0
                                : (status.st_mode & 0777) != (entry->executable ? 0555 : 0444)))
            return problem("bundle entry has unexpected permissions");
#endif
    }
    size_t count = 0;
    return (tree_exact(payload, "", bundle, &count) && count == bundle->count) ||
           problem("bundle contains an unexpected file, directory or link");
}
static void unpin(int *pins, size_t count) {
    for (size_t i = 0; i < count; i++)
        if (pins[i] >= 0)
            upd_close(pins[i]);
    free(pins);
}
static int *pin_array(size_t count) {
    int *pins = malloc(count * sizeof(int));
    if (pins)
        for (size_t i = 0; i < count; i++)
            pins[i] = -1;
    return pins;
}

bool minyar_update_activateChecked(long long id, const MinyarText *digest,
                                   const MinyarBytes *artifact, const MinyarBytes *receipt,
                                   const MinyarText *receipt_hash, const MinyarBytes *state) {
    last_error[0] = 0;
    UpdateSession *found = session(id);
    char hash[65], meta[65];
    if (!found || !digest_name(digest, hash) || !digest_name(receipt_hash, meta) ||
        artifact->byte_length < 1 || artifact->byte_length > UPD_ARTIFACT ||
        receipt->byte_length <= 64 || receipt->byte_length > UPD_STATE + 64 ||
        state->byte_length < 1 || state->byte_length > UPD_STATE)
        return problem("invalid authenticated activation arguments");
    char versions[UPD_PATH], destination[UPD_PATH], receipt_path[UPD_PATH], leaf[180];
    if (!join(versions, found->root, "versions") || !directory(versions))
        return false;
    snprintf(leaf, sizeof(leaf), "versions/%s.%s.receipt", hash, meta);
    if (!join(receipt_path, found->root, leaf))
        return false;
    UpdateBundle bundle = {0};
    bool success = true;
    if (artifact->byte_length >= 7 && !memcmp(artifact->bytes, "MINYAR-", 7) &&
        !is_bundle(artifact))
        return problem("unsupported or truncated bundle header");
    if (is_bundle(artifact)) {
        if (!bundle_parse(artifact, &bundle))
            return false;
        const BundleEntry *main = &bundle.entries[bundle.main];
        if (!native_image(main->data, main->size)) {
            bundle_free(&bundle);
            return problem("bundle entrypoint is not a native host executable");
        }
        if (!generation_path(found, digest, ".bundle", destination)) {
            bundle_free(&bundle);
            return false;
        }
        int existing = pin_directory(destination);
        if (existing >= 0) {
            upd_close(existing);
            char path[UPD_PATH], payload[UPD_PATH];
            int *pins = pin_array(bundle.count);
            int file = -1;
            success = pins && join(path, destination, "artifact") &&
                      join(payload, destination, "payload") &&
                      (file = open_file(path, false)) >= 0 &&
                      same_bytes(file, artifact->bytes, (size_t)artifact->byte_length) &&
                      bundle_check(payload, &bundle, pins);
            if (file >= 0)
                upd_close(file);
            if (pins)
                unpin(pins, bundle.count);
            if (!success)
                problem("existing generation is incomplete or changed");
        } else {
            char stage[UPD_PATH], payload[UPD_PATH], path[UPD_PATH], staging_leaf[128];
            snprintf(staging_leaf, sizeof(staging_leaf), ".update-bundle-%lld-%lld",
#ifdef _WIN32
                     (long long)GetCurrentProcessId(),
#else
                     (long long)getpid(),
#endif
                     found->id);
            success = join(stage, found->root, staging_leaf) && directory(stage) &&
                      join(payload, stage, "payload") && directory(payload);
            for (size_t i = 0; success && i < bundle.count; i++) {
                BundleEntry *entry = &bundle.entries[i];
                success = bundle_file_path(payload, entry, path) &&
                          (entry->type == 'D'
                               ? directory(path)
                               : write_new(path, entry->data, entry->size, entry->executable != 0));
                if (success)
                    UPDATE_HOOK("bundle-entry-written");
            }
            if (success)
                success = join(path, stage, "artifact") &&
                          write_new(path, artifact->bytes, (size_t)artifact->byte_length, false);
            for (size_t i = bundle.count; success && i > 0; i--) {
                BundleEntry *entry = &bundle.entries[i - 1];
                if (entry->type == 'D')
                    success = bundle_file_path(payload, entry, path) && sync_directory(path);
            }
            if (success)
                success = sync_directory(payload) && sync_directory(stage);
            if (success)
                UPDATE_HOOK("bundle-before-replace");
            /* Never replace a prior generation directory. The root lock makes
             * publication exclusive; a stale or linked destination is refused. */
#ifdef _WIN32
            wchar_t from[UPD_PATH], to[UPD_PATH];
            if (success)
                success = wide(stage, from) && wide(destination, to) &&
                          MoveFileExW(from, to, MOVEFILE_WRITE_THROUGH);
#else
            char from[UPD_PATH], to[UPD_PATH];
            int a = -1, b = -1;
            if (success) {
                a = safe_parent(stage, from);
                b = safe_parent(destination, to);
                struct stat status;
                success = a >= 0 && b >= 0 && fstatat(b, to, &status, AT_SYMLINK_NOFOLLOW) < 0 &&
                          errno == ENOENT && renameat(a, from, b, to) == 0;
            }
            if (a >= 0)
                close(a);
            if (b >= 0)
                close(b);
#endif
            if (success)
                success = sync_directory(versions) && sync_directory(found->root);
            if (success)
                UPDATE_HOOK("bundle-after-replace");
            /* Interrupted staging directories are inert. Never follow or
             * recursively delete them: an administrator can clean them offline. */
        }
        bundle_free(&bundle);
    } else {
#ifdef _WIN32
        const char *suffix = ".exe";
#else
        const char *suffix = ".bin";
#endif
        if (!generation_path(found, digest, suffix, destination))
            return false;
        int existing = open_file(destination, false);
        if (existing >= 0) {
            success = same_bytes(existing, artifact->bytes, (size_t)artifact->byte_length);
            upd_close(existing);
            if (!success)
                problem("existing immutable executable was changed");
        } else {
#ifndef _WIN32
            if (errno != ENOENT)
                return problem("unsafe executable generation destination");
#endif
            success = publish(found, destination, artifact, true) && sync_directory(versions);
        }
        if (success)
            UPDATE_HOOK("artifact-after-replace");
    }
    if (!success)
        return false;
    /* Receipt identity is separate from artifact identity, so a crash during a
     * version bump reusing the same artifact cannot invalidate the old receipt. */
    int previous = open_file(receipt_path, false);
    if (previous >= 0) {
        success = same_bytes(previous, receipt->bytes, (size_t)receipt->byte_length);
        upd_close(previous);
        if (!success)
            return problem("existing signed receipt differs");
    } else {
#ifndef _WIN32
        if (errno != ENOENT)
            return problem("unsafe signed receipt destination");
#endif
        success = publish(found, receipt_path, receipt, false) && sync_directory(versions);
    }
    if (!success)
        return false;
    UPDATE_HOOK("receipt-after-replace");
    success = minyar_update_storeState(id, state);
    if (success)
        UPDATE_HOOK("state-after-replace");
    return success;
}

MinyarBytes *minyar_update_readArtifact(long long id, const MinyarText *digest) {
    last_error[0] = 0;
    UpdateSession *found = session(id);
    char path[UPD_PATH], bundle[UPD_PATH];
    if (!found || !generation_path(found, digest, ".bundle", bundle))
        return minyar_bytes_new(0);
    int directory_handle = pin_directory(bundle);
    if (directory_handle >= 0) {
        upd_close(directory_handle);
        if (!join(path, bundle, "artifact"))
            return minyar_bytes_new(0);
    } else {
#ifdef _WIN32
        const char *suffix = ".exe";
#else
        const char *suffix = ".bin";
#endif
        if (!generation_path(found, digest, suffix, path))
            return minyar_bytes_new(0);
    }
    return read_bounded(path, UPD_ARTIFACT);
}
MinyarBytes *minyar_update_readReceipt(long long id, const MinyarText *digest,
                                       const MinyarText *receipt_hash) {
    last_error[0] = 0;
    UpdateSession *found = session(id);
    char hash[65], meta[65], leaf[180], path[UPD_PATH];
    if (!found || !digest_name(digest, hash) || !digest_name(receipt_hash, meta))
        return minyar_bytes_new(0);
    snprintf(leaf, sizeof(leaf), "versions/%s.%s.receipt", hash, meta);
    if (!join(path, found->root, leaf))
        return minyar_bytes_new(0);
    return read_bounded(path, UPD_STATE + 64);
}

typedef struct {
    long long id;
#ifdef _WIN32
    HANDLE process;
#else
    pid_t process;
#endif
} UpdateChild;
static UpdateChild children[UPD_HANDLES];
static long long next_child;

#ifndef _WIN32
extern char **environ;
static char **launch_environment(void) {
    size_t count = 0;
    while (environ[count])
        count++;
    char **result = calloc(count + 2, sizeof(char *));
    if (!result)
        return NULL;
    size_t at = 0;
    for (size_t i = 0; i < count; i++)
        if (strncmp(environ[i], "LD_", 3) && strncmp(environ[i], "DYLD_", 5))
            result[at++] = environ[i];
    result[at] = NULL;
    return result;
}
#endif

long long minyar_update_launchChecked(long long id, const MinyarText *digest,
                                      const MinyarBytes *artifact, const MinyarBytes *arguments,
                                      bool replace) {
    last_error[0] = 0;
    UpdateSession *found = session(id);
    if (!found || artifact->byte_length < 4 || artifact->byte_length > UPD_ARTIFACT ||
        arguments->byte_length < 0 || arguments->byte_length > 32768) {
        problem("invalid checked launch arguments");
        return -1;
    }
    UpdateChild *child = NULL;
    if (!replace) {
        for (size_t i = 0; i < UPD_HANDLES; i++)
            if (!children[i].id) {
                child = &children[i];
                break;
            }
        if (!child || next_child == LLONG_MAX) {
            problem("too many unwaited update children");
            return -1;
        }
    }
    char *argv[257];
    char *storage = malloc((size_t)arguments->byte_length + 1);
    if (!storage) {
        problem("cannot allocate launch arguments");
        return -1;
    }
    memcpy(storage, arguments->bytes, (size_t)arguments->byte_length);
    storage[arguments->byte_length] = 0;
    size_t argc = 1, at = 0;
    while (at < (size_t)arguments->byte_length) {
        size_t left = (size_t)arguments->byte_length - at;
        char *end = memchr(storage + at, 0, left);
        if (!end || argc >= 256) {
            free(storage);
            problem("invalid launch argument vector");
            return -1;
        }
        argv[argc++] = storage + at;
        at = (size_t)(end - storage) + 1;
    }
    argv[argc] = NULL;
    UpdateBundle bundle = {0};
    int *pins = NULL, executable = -1, cwd = -1;
    bool success = true;
    char path[UPD_PATH], payload[UPD_PATH], generation[UPD_PATH];
    if (is_bundle(artifact)) {
        success = bundle_parse(artifact, &bundle) &&
                  generation_path(found, digest, ".bundle", generation) &&
                  join(payload, generation, "payload");
        if (success) {
            cwd = pin_directory(payload);
            pins = pin_array(bundle.count);
            success = cwd >= 0 && pins && bundle_check(payload, &bundle, pins) &&
                      bundle_file_path(payload, &bundle.entries[bundle.main], path);
            if (success)
                executable = pins[bundle.main];
        }
    } else {
#ifdef _WIN32
        const char *suffix = ".exe";
#else
        const char *suffix = ".bin";
#endif
        success = generation_path(found, digest, suffix, path);
        if (success)
            executable = open_file(path, false);
        cwd = pin_directory(found->root);
        success = success && executable >= 0 && cwd >= 0 &&
                  same_bytes(executable, artifact->bytes, (size_t)artifact->byte_length);
        snprintf(payload, sizeof(payload), "%s", found->root);
    }
    const unsigned char *image =
        bundle.entries ? bundle.entries[bundle.main].data : artifact->bytes;
    size_t image_size =
        bundle.entries ? bundle.entries[bundle.main].size : (size_t)artifact->byte_length;
    if (success)
        success = native_image(image, image_size);
    if (!success && !last_error[0])
        problem("active executable is incomplete, changed or not a native host image");
    if (success) {
        UPDATE_HOOK("launch-before-exec");
        success = identity_matches(cwd, payload, true) &&
                  identity_matches(executable, path, false) &&
                  same_bytes(executable, image, image_size);
        if (success && bundle.entries) {
            for (size_t i = 0; success && i < bundle.count; i++) {
                char entry_path[UPD_PATH];
                BundleEntry *entry = &bundle.entries[i];
                success = bundle_file_path(payload, entry, entry_path) &&
                          identity_matches(pins[i], entry_path, entry->type == 'D') &&
                          (entry->type == 'D' || same_bytes(pins[i], entry->data, entry->size));
            }
            size_t count = 0;
            success = success && tree_exact(payload, "", &bundle, &count) && count == bundle.count;
        }
        if (!success)
            problem("active generation changed during launch verification");
    }
    argv[0] = path;
    long long result = -1;
#ifdef _WIN32
    if (success) {
        /* Quote according to the Microsoft CRT argv rules, including empty
         * arguments and backslashes before quotes. lpApplicationName is explicit. */
        char utf8[65536];
        size_t used = 0;
        for (size_t i = 0; success && i < argc; i++) {
            if (used + 3 >= sizeof(utf8)) {
                success = false;
                break;
            }
            if (i)
                utf8[used++] = ' ';
            utf8[used++] = '"';
            size_t slash = 0;
            for (const char *p = argv[i];; p++) {
                if (*p == '\\') {
                    slash++;
                    continue;
                }
                size_t emit = (*p == '"' || !*p) ? slash * 2 : slash;
                if (used + emit + 3 >= sizeof(utf8)) {
                    success = false;
                    break;
                }
                while (emit--)
                    utf8[used++] = '\\';
                slash = 0;
                if (*p == '"')
                    utf8[used++] = '\\';
                if (!*p)
                    break;
                utf8[used++] = *p;
            }
            if (success)
                utf8[used++] = '"';
        }
        utf8[used] = 0;
        wchar_t application[UPD_PATH], working[UPD_PATH], *command = NULL;
        int length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, utf8, -1, NULL, 0);
        if (success && length > 0 && length <= 32767)
            command = malloc((size_t)length * sizeof(wchar_t));
        success = success && command && wide(path, application) && wide(payload, working) &&
                  MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, utf8, -1, command, length) > 0;
        STARTUPINFOEXW startup;
        memset(&startup, 0, sizeof(startup));
        startup.StartupInfo.cb = sizeof(startup);
        HANDLE handles[3] = {NULL, NULL, NULL};
        size_t handle_count = 0;
        SIZE_T attributes = 0;
        bool attributes_ready = false;
        if (success) {
            DWORD ids[3] = {STD_INPUT_HANDLE, STD_OUTPUT_HANDLE, STD_ERROR_HANDLE};
            HANDLE *slots[3] = {&startup.StartupInfo.hStdInput, &startup.StartupInfo.hStdOutput,
                                &startup.StartupInfo.hStdError};
            for (size_t i = 0; i < 3; i++) {
                HANDLE original = GetStdHandle(ids[i]);
                if (original && original != INVALID_HANDLE_VALUE) {
                    HANDLE duplicate;
                    if (!DuplicateHandle(GetCurrentProcess(), original, GetCurrentProcess(),
                                         &duplicate, 0, TRUE, DUPLICATE_SAME_ACCESS)) {
                        success = false;
                        break;
                    }
                    handles[handle_count++] = duplicate;
                    *slots[i] = duplicate;
                } else
                    *slots[i] = NULL;
            }
            InitializeProcThreadAttributeList(NULL, 1, 0, &attributes);
            startup.lpAttributeList = malloc(attributes);
            attributes_ready =
                startup.lpAttributeList &&
                InitializeProcThreadAttributeList(startup.lpAttributeList, 1, 0, &attributes);
            success = success && attributes_ready;
            if (success && handle_count) {
                success = UpdateProcThreadAttribute(startup.lpAttributeList, 0,
                                                    PROC_THREAD_ATTRIBUTE_HANDLE_LIST, handles,
                                                    handle_count * sizeof(HANDLE), NULL, NULL) != 0;
                startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
            }
        }
        PROCESS_INFORMATION process;
        memset(&process, 0, sizeof(process));
        if (success)
            success = CreateProcessW(application, command, NULL, NULL, handle_count ? TRUE : FALSE,
                                     EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT,
                                     NULL, working, &startup.StartupInfo, &process) != 0;
        if (attributes_ready)
            DeleteProcThreadAttributeList(startup.lpAttributeList);
        free(startup.lpAttributeList);
        for (size_t i = 0; i < handle_count; i++)
            CloseHandle(handles[i]);
        free(command);
        if (success) {
            CloseHandle(process.hThread);
            if (replace) {
                CloseHandle(process.hProcess);
                ExitProcess(0);
            }
            child->process = process.hProcess;
            child->id = ++next_child;
            result = child->id;
        } else
            problem("checked Windows process creation failed");
    }
#else
    char **environment = NULL;
    if (success) {
        environment = launch_environment();
        if (!environment) {
            success = false;
            problem("cannot allocate clean launch environment");
        }
    }
    if (success) {
        int report[2] = {-1, -1};
        if (pipe(report) < 0 || fcntl(report[0], F_SETFD, FD_CLOEXEC) < 0 ||
            fcntl(report[1], F_SETFD, FD_CLOEXEC) < 0) {
            success = false;
            problem("cannot create checked launch status pipe");
            if (report[0] >= 0)
                close(report[0]);
            if (report[1] >= 0)
                close(report[1]);
        }
        struct rlimit limit;
        long bound = 65536;
        if (getrlimit(RLIMIT_NOFILE, &limit) == 0 && limit.rlim_cur < (rlim_t)INT_MAX)
            bound = (long)limit.rlim_cur;
        pid_t process = success ? fork() : -1;
        if (process == 0) {
            int error = 0;
            close(report[0]);
            if (fchdir(cwd) < 0)
                error = errno;
#ifdef __APPLE__
            if (!error && !identity_matches(executable, path, false))
                error = ESTALE;
#endif
            /* Close all nonstandard inherited descriptors; retain only the
             * authenticated image and close-on-exec status pipe. */
            for (int fd = 3; fd < bound; fd++)
                if (fd != executable && fd != report[1])
                    close(fd);
            if (!error) {
#ifdef __APPLE__
                /* Darwin lacks fexecve. The retained descriptor and immutable
                 * protected tree are checked again immediately before exec. */
                execve(path, argv, environment);
#else
                fexecve(executable, argv, environment);
#endif
                if (!error)
                    error = errno;
            }
            ssize_t ignored = write(report[1], &error, sizeof(error));
            (void)ignored;
            _exit(127);
        } else if (process > 0) {
            close(report[1]);
            int error = 0;
            size_t total = 0;
            while (total < sizeof(error)) {
                ssize_t n = read(report[0], (unsigned char *)&error + total, sizeof(error) - total);
                if (n < 0 && errno == EINTR)
                    continue;
                if (n <= 0)
                    break;
                total += (size_t)n;
            }
            close(report[0]);
            if (total) {
                int status;
                while (waitpid(process, &status, 0) < 0 && errno == EINTR) {
                }
                problem("authenticated executable could not start");
            } else {
                if (replace)
                    _exit(0);
                child->process = process;
                child->id = ++next_child;
                result = child->id;
            }
        } else if (success)
            problem("cannot fork checked update process");
    }
    free(environment);
#endif
    if (pins)
        unpin(pins, bundle.count);
    else if (executable >= 0)
        upd_close(executable);
    if (cwd >= 0)
        upd_close(cwd);
    bundle_free(&bundle);
    free(storage);
    return result;
}
long long minyar_update_waitChild(long long id) {
    last_error[0] = 0;
    UpdateChild *child = NULL;
    for (size_t i = 0; i < UPD_HANDLES; i++)
        if (children[i].id == id && id > 0) {
            child = &children[i];
            break;
        }
    if (!child) {
        problem("invalid or consumed update child token");
        return -1;
    }
#ifdef _WIN32
    DWORD status;
    bool success = WaitForSingleObject(child->process, INFINITE) == WAIT_OBJECT_0 &&
                   GetExitCodeProcess(child->process, &status);
    CloseHandle(child->process);
    child->id = 0;
    if (!success) {
        problem("cannot wait for update child");
        return -1;
    }
    return (long long)status;
#else
    int status;
    pid_t waited;
    do {
        waited = waitpid(child->process, &status, 0);
    } while (waited < 0 && errno == EINTR);
    child->id = 0;
    if (waited < 0) {
        problem("cannot wait for update child");
        return -1;
    }
    return WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
#endif
}
