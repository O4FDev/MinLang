#ifndef _GNU_SOURCE
#define _GNU_SOURCE 1
#endif
#ifdef __APPLE__
#define _DARWIN_C_SOURCE 1
#include <crt_externs.h>
#include <mach-o/dyld.h>
#endif
#include "../runtime/minyar_native.h"
#include <errno.h>
#include <fcntl.h>
#include <ftw.h>
#include <limits.h>
#include <signal.h>
#include <spawn.h>
#include <stdint.h>
#include <sys/stat.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#ifndef __APPLE__
extern char **environ;
#endif

static int host_error;
static char **host_temporaries;
static size_t host_temporary_count;
static char *host_capture;
static volatile sig_atomic_t host_signal;
static struct sigaction host_previous[2];
static int host_guarded;
static const int host_signals[2] = {SIGTERM, SIGHUP};

long long minyar_driverhost_lastError(void) { return -host_error; }

static MinyarText *host_text(const char *value) {
    return minyar_native_copy_text((const unsigned char *)value, (long long)strlen(value));
}

static char *host_cstring(const MinyarText *value) {
    if (!value || value->byte_length < 0 || (value->byte_length && memchr(value->bytes, 0, (size_t)value->byte_length))) {
        host_error = EINVAL;
        return NULL;
    }
    char *result = malloc((size_t)value->byte_length + 1);
    if (!result) { host_error = ENOMEM; return NULL; }
    if (value->byte_length) memcpy(result, value->bytes, (size_t)value->byte_length);
    result[value->byte_length] = 0;
    return result;
}

MinyarText *minyar_driverhost_hostNameNative(void) {
    struct utsname name;
    if (uname(&name)) return host_text("");
    return host_text(name.sysname);
}

MinyarText *minyar_driverhost_hostMachine(void) {
    struct utsname name;
    if (uname(&name)) return host_text("");
    return host_text(name.machine);
}

MinyarText *minyar_driverhost_errorText(long long code) {
    return host_text(strerror((int)(code < 0 ? -code : code)));
}

static char *host_resolve(const char *path) {
    char *resolved = realpath(path, NULL);
    if (resolved) return resolved;
    if (errno != ENOENT && errno != ENOTDIR) return NULL;
    size_t length = strlen(path);
    while (length > 1 && path[length - 1] == '/') length--;
    size_t slash = length;
    while (slash > 0 && path[slash - 1] != '/') slash--;
    const char *name = path + slash;
    size_t name_length = length - slash;
    char *parent;
    if (slash == 0) {
        parent = getcwd(NULL, 0);
    } else {
        char *prefix = malloc(slash + 1);
        if (!prefix) return NULL;
        memcpy(prefix, path, slash);
        prefix[slash] = 0;
        size_t end = slash;
        while (end > 1 && prefix[end - 1] == '/') prefix[--end] = 0;
        parent = host_resolve(prefix);
        free(prefix);
    }
    if (!parent) return NULL;
    if ((name_length == 1 && name[0] == '.') || name_length == 0) return parent;
    if (name_length == 2 && name[0] == '.' && name[1] == '.') {
        char *last = strrchr(parent, '/');
        if (last && last != parent) *last = 0;
        else if (last) parent[1] = 0;
        return parent;
    }
    size_t parent_length = strlen(parent);
    int separator = parent_length > 0 && parent[parent_length - 1] != '/';
    char *joined = malloc(parent_length + (size_t)separator + name_length + 1);
    if (!joined) { free(parent); return NULL; }
    memcpy(joined, parent, parent_length);
    if (separator) joined[parent_length] = '/';
    memcpy(joined + parent_length + separator, name, name_length);
    joined[parent_length + separator + name_length] = 0;
    free(parent);
    return joined;
}

MinyarText *minyar_driverhost_resolvePath(const MinyarText *path) {
    char *name = host_cstring(path);
    if (!name || !name[0]) { free(name); host_error = EINVAL; return host_text(""); }
    char *resolved = host_resolve(name);
    if (!resolved) host_error = errno;
    free(name);
    MinyarText *result = host_text(resolved ? resolved : "");
    free(resolved);
    return result;
}

MinyarText *minyar_driverhost_statusNative(const MinyarText *path) {
    char *name = host_cstring(path);
    if (!name) return host_text("");
    struct stat info;
    int failed = stat(name, &info);
    if (failed) host_error = errno;
    free(name);
    if (failed) return host_text("");
#ifdef __APPLE__
    long long modified = (long long)info.st_mtimespec.tv_sec * 1000000000LL + info.st_mtimespec.tv_nsec;
    long long changed = (long long)info.st_ctimespec.tv_sec * 1000000000LL + info.st_ctimespec.tv_nsec;
#else
    long long modified = (long long)info.st_mtim.tv_sec * 1000000000LL + info.st_mtim.tv_nsec;
    long long changed = (long long)info.st_ctim.tv_sec * 1000000000LL + info.st_ctim.tv_nsec;
#endif
    char buffer[256];
    snprintf(buffer, sizeof buffer, "%c %llu %llu %lld %lld %lld",
             S_ISREG(info.st_mode) ? 'f' : S_ISDIR(info.st_mode) ? 'd' : 'o',
             (unsigned long long)info.st_dev, (unsigned long long)info.st_ino,
             (long long)info.st_size, modified, changed);
    return host_text(buffer);
}

bool minyar_driverhost_executable(const MinyarText *path) {
    char *name = host_cstring(path);
    if (!name) return false;
    struct stat info;
    bool result = !stat(name, &info) && S_ISREG(info.st_mode) && !access(name, X_OK);
    free(name);
    return result;
}

MinyarText *minyar_driverhost_selfPath(void) {
#ifdef __APPLE__
    uint32_t size = 0;
    _NSGetExecutablePath(NULL, &size);
    char *buffer = malloc(size + 1);
    if (!buffer || _NSGetExecutablePath(buffer, &size)) { free(buffer); return host_text(""); }
    char *resolved = realpath(buffer, NULL);
    free(buffer);
#else
    char *resolved = realpath("/proc/self/exe", NULL);
#endif
    MinyarText *result = host_text(resolved ? resolved : "");
    free(resolved);
    return result;
}

MinyarText *minyar_driverhost_makeTemporary(const MinyarText *directory, const MinyarText *prefix) {
    char *parent = host_cstring(directory);
    char *stem = host_cstring(prefix);
    MinyarText *result;
    if (!parent || !stem) result = host_text("");
    else {
        size_t length = strlen(parent) + strlen(stem) + 9;
        char *pattern = malloc(length);
        if (!pattern) { host_error = ENOMEM; result = host_text(""); }
        else {
            snprintf(pattern, length, "%s/%sXXXXXX", parent, stem);
            if (mkdtemp(pattern)) result = host_text(pattern);
            else { host_error = errno; result = host_text(""); }
            free(pattern);
        }
    }
    free(parent);
    free(stem);
    return result;
}

static int host_remove_entry(const char *path, const struct stat *info, int flag, struct FTW *walk);

static long long host_remove(const char *name) {
    host_error = 0;
    struct stat info;
    if (lstat(name, &info)) return errno == ENOENT ? 0 : -(long long)errno;
    if (S_ISDIR(info.st_mode)) {
        if (nftw(name, host_remove_entry, 32, FTW_DEPTH | FTW_PHYS) && !host_error) host_error = errno;
    } else if (unlink(name) && errno != ENOENT) host_error = errno;
    return -host_error;
}

long long minyar_driverhost_registerTemporary(const MinyarText *path) {
    char *name = host_cstring(path);
    if (!name) return -host_error;
    char **grown = realloc(host_temporaries, (host_temporary_count + 1) * sizeof *grown);
    if (!grown) { free(name); return -ENOMEM; }
    host_temporaries = grown;
    host_temporaries[host_temporary_count++] = name;
    return 0;
}

long long minyar_driverhost_releaseTemporary(const MinyarText *path) {
    char *name = host_cstring(path);
    if (!name) return -host_error;
    long long result = host_remove(name);
    size_t kept = 0;
    for (size_t index = 0; index < host_temporary_count; index++) {
        if (strcmp(host_temporaries[index], name)) host_temporaries[kept++] = host_temporaries[index];
        else free(host_temporaries[index]);
    }
    host_temporary_count = kept;
    if (host_capture && !strcmp(host_capture, name)) { free(host_capture); host_capture = NULL; }
    free(name);
    return result;
}

long long minyar_driverhost_cleanupTemporaries(void) {
    while (host_temporary_count) {
        char *name = host_temporaries[--host_temporary_count];
        host_remove(name);
        free(name);
    }
    free(host_capture);
    host_capture = NULL;
    return 0;
}

MinyarText *minyar_driverhost_captureDirectoryNative(void) { return host_text(host_capture ? host_capture : ""); }

long long minyar_driverhost_rememberCapture(const MinyarText *path) {
    char *name = host_cstring(path);
    if (!name) return -host_error;
    free(host_capture);
    host_capture = name;
    return 0;
}

long long minyar_driverhost_makeDirectory(const MinyarText *path) {
    char *name = host_cstring(path);
    if (!name) return -host_error;
    long long result = mkdir(name, 0777) ? -(long long)errno : 0;
    free(name);
    return result;
}

static int host_remove_entry(const char *path, const struct stat *info, int flag, struct FTW *walk) {
    (void)info;
    (void)walk;
    int failed = flag == FTW_DP ? rmdir(path) : unlink(path);
    if (failed && errno != ENOENT) host_error = errno;
    return 0;
}


static void host_interrupt(int number) { host_signal = number; }

long long minyar_driverhost_guard(bool enabled) {
    if (enabled && !host_guarded) {
        struct sigaction action;
        memset(&action, 0, sizeof action);
        action.sa_handler = host_interrupt;
        sigemptyset(&action.sa_mask);
        for (int index = 0; index < 2; index++) sigaction(host_signals[index], &action, &host_previous[index]);
        host_guarded = 1;
    } else if (!enabled && host_guarded) {
        for (int index = 0; index < 2; index++) sigaction(host_signals[index], &host_previous[index], NULL);
        host_guarded = 0;
    }
    return 0;
}

long long minyar_driverhost_pendingSignal(void) { return host_signal; }

static char **host_vector(const MinyarBytes *encoded) {
    const unsigned char *data = encoded->bytes;
    long long size = encoded->byte_length, offset = 8, count;
    if (size < 8) return NULL;
    memcpy(&count, data, 8);
    if (count < 0 || count > 65536) return NULL;
    char **vector = calloc((size_t)count + 1, sizeof *vector);
    if (!vector) return NULL;
    for (long long index = 0; index < count; index++) {
        long long length;
        if (offset + 8 > size) goto invalid;
        memcpy(&length, data + offset, 8);
        offset += 8;
        if (length < 0 || offset + length > size || memchr(data + offset, 0, (size_t)length)) goto invalid;
        vector[index] = malloc((size_t)length + 1);
        if (!vector[index]) goto invalid;
        memcpy(vector[index], data + offset, (size_t)length);
        vector[index][length] = 0;
        offset += length;
    }
    return vector;
invalid:
    for (long long index = 0; index < count; index++) free(vector[index]);
    free(vector);
    return NULL;
}

static void host_free_vector(char **vector) {
    if (!vector) return;
    for (char **item = vector; *item; item++) free(*item);
    free(vector);
}

static long long host_finish(int status) {
    if (WIFSIGNALED(status)) return 128 + WTERMSIG(status);
    return WEXITSTATUS(status);
}

long long minyar_driverhost_execute(const MinyarBytes *arguments, const MinyarBytes *environment,
                                    bool inherit, const MinyarText *output, const MinyarText *errors,
                                    long long timeout) {
    char **argv = host_vector(arguments);
    char **envp = inherit ? NULL : host_vector(environment);
    char *out = output->byte_length ? host_cstring(output) : NULL;
    char *err = errors->byte_length ? host_cstring(errors) : NULL;
    long long result;
    if (!argv || !argv[0] || (!inherit && !envp) || (output->byte_length && !out) || (errors->byte_length && !err)) {
        result = -EINVAL;
        goto done;
    }
    posix_spawn_file_actions_t actions;
    posix_spawn_file_actions_init(&actions);
    if (out) posix_spawn_file_actions_addopen(&actions, 1, out, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (err) posix_spawn_file_actions_addopen(&actions, 2, err, O_WRONLY | O_CREAT | O_TRUNC, 0644);
#ifdef __APPLE__
    char **current = *_NSGetEnviron();
#else
    char **current = environ;
#endif
    pid_t child;
    int failed = posix_spawnp(&child, argv[0], &actions, NULL, argv, inherit ? current : envp);
    posix_spawn_file_actions_destroy(&actions);
    if (failed) {
        result = -failed;
        goto done;
    }
    struct timespec start;
    clock_gettime(CLOCK_MONOTONIC, &start);
    for (;;) {
        int status;
        pid_t waited = waitpid(child, &status, timeout > 0 ? WNOHANG : 0);
        if (waited == child) {
            result = host_guarded && host_signal ? -(200000 + (long long)host_signal) : host_finish(status);
            break;
        }
        if (waited < 0 && errno != EINTR) {
            result = -(long long)errno;
            break;
        }
        if (host_guarded && host_signal) {
            kill(child, SIGKILL);
            while (waitpid(child, &status, 0) < 0 && errno == EINTR) {}
            result = -(200000 + (long long)host_signal);
            break;
        }
        if (timeout > 0) {
            struct timespec now;
            clock_gettime(CLOCK_MONOTONIC, &now);
            long long elapsed = (now.tv_sec - start.tv_sec) * 1000LL + (now.tv_nsec - start.tv_nsec) / 1000000LL;
            if (elapsed >= timeout) {
                kill(child, SIGKILL);
                while (waitpid(child, &status, 0) < 0 && errno == EINTR) {}
                result = -100000;
                break;
            }
            struct timespec pause = {0, 2000000};
            nanosleep(&pause, NULL);
        }
    }
done:
    host_free_vector(argv);
    host_free_vector(envp);
    free(out);
    free(err);
    return result;
}

typedef struct {
    uint32_t state[8];
    uint64_t length;
    unsigned char block[64];
    size_t used;
} HostSha256;

static const uint32_t host_rounds[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
};

static uint32_t host_rotate(uint32_t value, int count) { return (value >> count) | (value << (32 - count)); }

static void host_sha_block(HostSha256 *hash, const unsigned char *block) {
    uint32_t words[64];
    for (int index = 0; index < 16; index++)
        words[index] = (uint32_t)block[index * 4] << 24 | (uint32_t)block[index * 4 + 1] << 16 |
                       (uint32_t)block[index * 4 + 2] << 8 | block[index * 4 + 3];
    for (int index = 16; index < 64; index++) {
        uint32_t low = host_rotate(words[index - 15], 7) ^ host_rotate(words[index - 15], 18) ^ (words[index - 15] >> 3);
        uint32_t high = host_rotate(words[index - 2], 17) ^ host_rotate(words[index - 2], 19) ^ (words[index - 2] >> 10);
        words[index] = words[index - 16] + low + words[index - 7] + high;
    }
    uint32_t a = hash->state[0], b = hash->state[1], c = hash->state[2], d = hash->state[3];
    uint32_t e = hash->state[4], f = hash->state[5], g = hash->state[6], h = hash->state[7];
    for (int index = 0; index < 64; index++) {
        uint32_t first = h + (host_rotate(e, 6) ^ host_rotate(e, 11) ^ host_rotate(e, 25)) + ((e & f) ^ (~e & g)) +
                         host_rounds[index] + words[index];
        uint32_t second = (host_rotate(a, 2) ^ host_rotate(a, 13) ^ host_rotate(a, 22)) + ((a & b) ^ (a & c) ^ (b & c));
        h = g; g = f; f = e; e = d + first; d = c; c = b; b = a; a = first + second;
    }
    hash->state[0] += a; hash->state[1] += b; hash->state[2] += c; hash->state[3] += d;
    hash->state[4] += e; hash->state[5] += f; hash->state[6] += g; hash->state[7] += h;
}

static void host_sha_start(HostSha256 *hash) {
    static const uint32_t initial[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                                        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
    memcpy(hash->state, initial, sizeof initial);
    hash->length = 0;
    hash->used = 0;
}

static void host_sha_update(HostSha256 *hash, const unsigned char *data, size_t length) {
    hash->length += length;
    while (length) {
        size_t take = 64 - hash->used;
        if (take > length) take = length;
        memcpy(hash->block + hash->used, data, take);
        hash->used += take;
        data += take;
        length -= take;
        if (hash->used == 64) {
            host_sha_block(hash, hash->block);
            hash->used = 0;
        }
    }
}

static MinyarText *host_sha_finish(HostSha256 *hash) {
    uint64_t bits = hash->length * 8;
    unsigned char pad = 0x80, zero = 0, size[8];
    host_sha_update(hash, &pad, 1);
    while (hash->used != 56) host_sha_update(hash, &zero, 1);
    for (int index = 0; index < 8; index++) size[index] = (unsigned char)(bits >> (56 - index * 8));
    host_sha_update(hash, size, 8);
    char hex[65];
    for (int index = 0; index < 32; index++)
        snprintf(hex + index * 2, 3, "%02x", (hash->state[index / 4] >> (24 - (index % 4) * 8)) & 0xff);
    return host_text(hex);
}

MinyarText *minyar_driverhost_hashBytes(const MinyarBytes *data) {
    HostSha256 hash;
    host_sha_start(&hash);
    host_sha_update(&hash, data->bytes, (size_t)data->byte_length);
    return host_sha_finish(&hash);
}

MinyarText *minyar_driverhost_hashFileNative(const MinyarText *path) {
    char *name = host_cstring(path);
    if (!name) return host_text("");
    int file = open(name, O_RDONLY);
    if (file < 0) host_error = errno;
    free(name);
    if (file < 0) return host_text("");
    HostSha256 hash;
    host_sha_start(&hash);
    unsigned char *buffer = malloc(1 << 20);
    if (!buffer) { close(file); host_error = ENOMEM; return host_text(""); }
    for (;;) {
        ssize_t count = read(file, buffer, 1 << 20);
        if (count < 0 && errno == EINTR) continue;
        if (count < 0) { host_error = errno; free(buffer); close(file); return host_text(""); }
        if (!count) break;
        host_sha_update(&hash, buffer, (size_t)count);
    }
    free(buffer);
    close(file);
    return host_sha_finish(&hash);
}
