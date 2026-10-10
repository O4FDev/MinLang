/* Narrow updater hooks. Policy, hashing and version checks live in update.min.
 * The application owns the protected installation directory. No downloaded
 * path or shell command is ever evaluated. State is the sole active pointer.
 */
#include "../minyar_native.h"
#include "../../vendor/monocypher/monocypher-ed25519.h"
#include <errno.h>
#include <limits.h>
#include <sys/stat.h>
#ifdef _WIN32
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
#else
    int lock;
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

#ifdef _WIN32
static bool wide(const char *path, wchar_t output[UPD_PATH]) {
    return MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path, -1, output, UPD_PATH) > 0;
}
static bool directory(const char *path) {
    wchar_t name[UPD_PATH];
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
    if (!wide(path, name))
        return -1;
    HANDLE file = CreateFileW(name, writing ? GENERIC_WRITE : GENERIC_READ, FILE_SHARE_READ, NULL,
                              writing ? CREATE_NEW : OPEN_EXISTING,
                              FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (file == INVALID_HANDLE_VALUE)
        return -1;
    BY_HANDLE_FILE_INFORMATION info;
    if (!GetFileInformationByHandle(file, &info) ||
        (info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)) {
        CloseHandle(file);
        return -1;
    }
    int fd = _open_osfhandle((intptr_t)file, _O_BINARY | (writing ? _O_WRONLY : _O_RDONLY));
    if (fd < 0)
        CloseHandle(file);
    return fd;
}
static bool replace_file(const char *source, const char *destination) {
    wchar_t from[UPD_PATH], to[UPD_PATH];
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
    if (mkdir(path, 0700) < 0 && errno != EEXIST)
        return problem("cannot create installation directory");
    struct stat status;
    return (lstat(path, &status) == 0 && S_ISDIR(status.st_mode) && status.st_uid == geteuid() &&
            !(status.st_mode & 0022)) ||
           problem("installation directory must be owned, protected and not a symlink");
}
static int open_file(const char *path, bool writing) {
    int fd = open(path, (writing ? O_WRONLY | O_CREAT | O_EXCL : O_RDONLY) | O_NOFOLLOW | O_CLOEXEC,
                  0600);
    struct stat status;
    if (fd >= 0 && (fstat(fd, &status) < 0 || !S_ISREG(status.st_mode))) {
        close(fd);
        return -1;
    }
    return fd;
}
static bool replace_file(const char *source, const char *destination) {
    return rename(source, destination) == 0;
}
static void remove_file(const char *path) {
    unlink(path);
}
static bool sync_directory(const char *path) {
    int fd = open(path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
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
    memcpy(found->root, root->bytes, (size_t)root->byte_length);
    found->root[root->byte_length] = 0;
    char lock_path[UPD_PATH];
    if (!directory(found->root) || !join(lock_path, found->root, ".update-lock"))
        return -1;
#ifdef _WIN32
    wchar_t name[UPD_PATH];
    if (!wide(lock_path, name))
        return -1;
    found->lock = CreateFileW(name, GENERIC_READ | GENERIC_WRITE, 0, NULL, OPEN_ALWAYS,
                              FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (found->lock == INVALID_HANDLE_VALUE) {
        problem("another updater holds the installation lock");
        return -1;
    }
    BY_HANDLE_FILE_INFORMATION info;
    if (!GetFileInformationByHandle(found->lock, &info) ||
        (info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)) {
        CloseHandle(found->lock);
        problem("installation lock is a link");
        return -1;
    }
#else
    found->lock = open(lock_path, O_RDWR | O_CREAT | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (found->lock < 0 || flock(found->lock, LOCK_EX | LOCK_NB) < 0) {
        if (found->lock >= 0)
            close(found->lock);
        problem("another updater holds the installation lock");
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
#else
    close(found->lock);
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
    if (success && executable && fchmod(fd, 0755) < 0)
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
