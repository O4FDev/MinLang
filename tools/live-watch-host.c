/* Project watch supervisor. No managed objects cross a process boundary and
 * filesystem notifications, child exits and shutdown share one blocking loop.
 * Ordinary rebuilds restart the process. Preserve mode leaves the existing hot
 * runtime running, so it can consume its published function map at a boundary.
 */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE 1
#endif
#ifdef __APPLE__
#define _DARWIN_C_SOURCE 1
#include <crt_externs.h>
#include <sys/event.h>
#endif
#include "../runtime/minyar_native.h"
#include <errno.h>
#include <limits.h>
#include <stdint.h>
#if defined(__linux__) || defined(__APPLE__)
#include <dirent.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <spawn.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#ifdef __linux__
#include <sys/inotify.h>
#endif
#ifndef __APPLE__
extern char **environ;
#endif

enum { LW_DEBOUNCE_MS = 120, LW_SHUTDOWN_MS = 1000 };
static volatile sig_atomic_t lw_signal;
static volatile sig_atomic_t lw_writer = -1;
static const int lw_signals[] = { SIGINT, SIGTERM, SIGHUP, SIGCHLD };

static int64_t lw_now(void) {
    struct timespec value;
    if (clock_gettime(CLOCK_MONOTONIC, &value)) return -1;
    return (int64_t)value.tv_sec * 1000 + value.tv_nsec / 1000000;
}

static void lw_handler(int signal) {
    int saved = errno;
    if (signal != SIGCHLD) lw_signal = signal;
    unsigned char byte = (unsigned char)signal;
    int writer = (int)lw_writer;
    if (writer >= 0) { ssize_t count = write(writer, &byte, 1); (void)count; }
    errno = saved;
}

static int lw_fd(int fd, int nonblock) {
    int flags = fcntl(fd, F_GETFD);
    if (flags < 0 || fcntl(fd, F_SETFD, flags | FD_CLOEXEC)) return -1;
    if (nonblock) {
        flags = fcntl(fd, F_GETFL);
        if (flags < 0 || fcntl(fd, F_SETFL, flags | O_NONBLOCK)) return -1;
    }
    return 0;
}

static char *lw_text(const MinyarText *value) {
    if (!value || value->byte_length < 0 || (uint64_t)value->byte_length >= SIZE_MAX ||
        (value->byte_length && (!value->bytes || memchr(value->bytes, 0, (size_t)value->byte_length)))) {
        errno = EINVAL; return NULL;
    }
    char *result = malloc((size_t)value->byte_length + 1);
    if (!result) return NULL;
    if (value->byte_length) memcpy(result, value->bytes, (size_t)value->byte_length);
    result[value->byte_length] = 0;
    return result;
}

static uint64_t lw_u64(const unsigned char *bytes) {
    uint64_t result = 0;
    for (unsigned index = 0; index < 8; index++) result |= (uint64_t)bytes[index] << (index * 8);
    return result;
}

static void lw_free_vector(char **items) {
    if (!items) return;
    for (size_t index = 0; items[index]; index++) free(items[index]);
    free(items);
}

static char **lw_vector(const MinyarBytes *encoded) {
    if (!encoded || !encoded->bytes || encoded->byte_length < 8 ||
        (uint64_t)encoded->byte_length > SIZE_MAX) { errno = EINVAL; return NULL; }
    size_t size = (size_t)encoded->byte_length, offset = 8;
    uint64_t count = lw_u64(encoded->bytes);
    if (count > 65536 || count > (size - 8) / 8) { errno = EINVAL; return NULL; }
    char **items = calloc((size_t)count + 1, sizeof(*items));
    if (!items) return NULL;
    for (size_t index = 0; index < count; index++) {
        if (size - offset < 8) goto invalid;
        uint64_t length = lw_u64(encoded->bytes + offset); offset += 8;
        if (length > size - offset || memchr(encoded->bytes + offset, 0, (size_t)length)) goto invalid;
        items[index] = malloc((size_t)length + 1);
        if (!items[index]) { lw_free_vector(items); return NULL; }
        memcpy(items[index], encoded->bytes + offset, (size_t)length);
        items[index][length] = 0;
        offset += (size_t)length;
    }
    if (offset != size) goto invalid;
    return items;
invalid:
    lw_free_vector(items); errno = EINVAL; return NULL;
}

static char **lw_command(char *first, char *second, char **tail) {
    size_t count = 0;
    while (tail[count]) count++;
    char **result = calloc(count + (second ? 3 : 2), sizeof(*result));
    if (!result) return NULL;
    result[0] = first;
    size_t start = 1;
    if (second) result[start++] = second;
    for (size_t index = 0; index < count; index++) result[start + index] = tail[index];
    return result;
}

typedef struct { char *path; int descriptor; } LWEntry;
typedef struct { int descriptor; int wake; LWEntry *entries; size_t count; } LWWatcher;

static int lw_excluded(const char *name) {
    return !strcmp(name, ".") || !strcmp(name, "..") || !strcmp(name, ".git") ||
           !strcmp(name, "target") || !strcmp(name, "build");
}

static int lw_source(const char *name) {
    size_t length = strlen(name);
    return !strcmp(name, "Minyar.toml") || (length >= 4 && !strcmp(name + length - 4, ".min"));
}

static void lw_watcher_close(LWWatcher *watcher) {
    for (size_t index = 0; index < watcher->count; index++) {
#ifdef __APPLE__
        close(watcher->entries[index].descriptor);
#endif
        free(watcher->entries[index].path);
    }
    free(watcher->entries);
    watcher->entries = NULL; watcher->count = 0;
    if (watcher->descriptor >= 0) close(watcher->descriptor);
    watcher->descriptor = -1;
}

static int lw_add(LWWatcher *watcher, const char *path, int directory) {
    for (size_t index = 0; index < watcher->count; index++) {
        if (!strcmp(watcher->entries[index].path, path)) return 0;
    }
    if (watcher->count >= 100000) { errno = E2BIG; return -1; }
    char *copy = strdup(path);
    if (!copy) return -1;
    LWEntry *entries = realloc(watcher->entries, (watcher->count + 1) * sizeof(*entries));
    if (!entries) { free(copy); return -1; }
    watcher->entries = entries;
    int descriptor;
#ifdef __linux__
    (void)directory;
    descriptor = inotify_add_watch(watcher->descriptor, path,
        IN_CLOSE_WRITE | IN_MOVED_TO | IN_MOVED_FROM | IN_CREATE | IN_DELETE |
        IN_DELETE_SELF | IN_MOVE_SELF | IN_ATTRIB | IN_ONLYDIR | IN_DONT_FOLLOW);
#else
    (void)directory;
    descriptor = open(path, O_EVTONLY | O_CLOEXEC | O_NOFOLLOW);
    if (descriptor >= 0) {
        struct kevent change;
        EV_SET(&change, (uintptr_t)descriptor, EVFILT_VNODE, EV_ADD | EV_CLEAR,
               NOTE_WRITE | NOTE_DELETE | NOTE_RENAME | NOTE_ATTRIB | NOTE_REVOKE, 0, NULL);
        if (kevent(watcher->descriptor, &change, 1, NULL, 0, NULL)) {
            int saved = errno; close(descriptor); descriptor = -1; errno = saved;
        }
    }
#endif
    if (descriptor < 0) { free(copy); return errno == ENOENT ? 0 : -1; }
    watcher->entries[watcher->count++] = (LWEntry){copy, descriptor};
    return 0;
}

static int lw_scan(LWWatcher *watcher, const char *path, unsigned depth) {
    if (depth > 256) { errno = ELOOP; return -1; }
    struct stat info;
    if (lstat(path, &info)) return errno == ENOENT ? 0 : -1;
    if (!S_ISDIR(info.st_mode)) {
#ifdef __APPLE__
        if (S_ISREG(info.st_mode)) {
            const char *base = strrchr(path, '/');
            if (lw_source(base ? base + 1 : path)) return lw_add(watcher, path, 0);
        }
#endif
        return 0;
    }
    if (lw_add(watcher, path, 1)) return -1;
    DIR *directory = opendir(path);
    if (!directory) return errno == ENOENT ? 0 : -1;
    int result = 0;
    for (;;) {
        errno = 0;
        struct dirent *entry = readdir(directory);
        if (!entry) { if (errno) result = -1; break; }
        if (lw_excluded(entry->d_name)) continue;
        size_t length = strlen(path) + strlen(entry->d_name) + 2;
        char *child = malloc(length);
        if (!child) { result = -1; break; }
        snprintf(child, length, "%s/%s", path, entry->d_name);
        result = lw_scan(watcher, child, depth + 1);
        free(child);
        if (result) break;
    }
    int saved = errno;
    closedir(directory); errno = saved;
    return result;
}

static int lw_watcher_reset(LWWatcher *watcher, const char *root, char **roots) {
    lw_watcher_close(watcher);
#ifdef __linux__
    watcher->descriptor = inotify_init1(IN_CLOEXEC | IN_NONBLOCK);
#else
    watcher->descriptor = kqueue();
    if (watcher->descriptor >= 0 && lw_fd(watcher->descriptor, 0)) {
        int saved = errno; close(watcher->descriptor); watcher->descriptor = -1; errno = saved;
    }
    if (watcher->descriptor >= 0) {
        struct kevent change;
        EV_SET(&change, (uintptr_t)watcher->wake, EVFILT_READ, EV_ADD | EV_CLEAR, 0, 0, NULL);
        if (kevent(watcher->descriptor, &change, 1, NULL, 0, NULL)) return -1;
    }
#endif
    if (watcher->descriptor < 0 || lw_scan(watcher, root, 0)) return -1;
    for (size_t index = 0; roots[index]; index++) {
        if (lw_scan(watcher, roots[index], 0)) return -1;
    }
    return 0;
}

// Result bits: 1 = source/directory change, 2 = signal/child notification.
static int lw_events(LWWatcher *watcher, int timeout) {
#ifdef __linux__
    struct pollfd descriptors[2] = {{watcher->descriptor, POLLIN, 0}, {watcher->wake, POLLIN, 0}};
    int count = poll(descriptors, 2, timeout);
    if (count < 0) return errno == EINTR ? 2 : -1;
    if ((descriptors[0].revents | descriptors[1].revents) & (POLLERR | POLLHUP | POLLNVAL)) {
        errno = EIO; return -1;
    }
    int result = descriptors[1].revents ? 2 : 0;
    if (!(descriptors[0].revents & POLLIN)) return result;
    union { struct inotify_event alignment; unsigned char data[65536]; } buffer;
    for (;;) {
        ssize_t size = read(watcher->descriptor, buffer.data, sizeof(buffer.data));
        if (size < 0) {
            if (errno == EINTR) continue;
            if (errno == EAGAIN) return result;
            return -1;
        }
        if (size == 0) { errno = EIO; return -1; }
        for (size_t offset = 0; offset < (size_t)size;) {
            struct inotify_event *event = (struct inotify_event *)(buffer.data + offset);
            if (event->mask & (IN_Q_OVERFLOW | IN_DELETE_SELF | IN_MOVE_SELF)) result |= 1;
            else if (!(event->mask & IN_IGNORED) && event->len && !lw_excluded(event->name) &&
                     ((event->mask & IN_ISDIR) || lw_source(event->name))) result |= 1;
            offset += sizeof(*event) + event->len;
        }
    }
#else
    struct timespec delay = {timeout / 1000, (timeout % 1000) * 1000000L};
    struct kevent events[64];
    int count = kevent(watcher->descriptor, NULL, 0, events, 64, timeout < 0 ? NULL : &delay);
    if (count < 0) return errno == EINTR ? 2 : -1;
    int result = 0;
    for (int index = 0; index < count; index++) {
        if (events[index].flags & EV_ERROR) { errno = (int)events[index].data; return -1; }
        result |= events[index].filter == EVFILT_READ ? 2 : 1;
    }
    return result;
#endif
}

static pid_t lw_spawn(char **arguments, const char *root, const char *roots_file,
                      const char *publication_file, bool application_running) {
    posix_spawn_file_actions_t actions;
    posix_spawnattr_t attributes;
    int error = posix_spawn_file_actions_init(&actions);
    if (error) { errno = error; return -1; }
    error = posix_spawnattr_init(&attributes);
    if (error) { posix_spawn_file_actions_destroy(&actions); errno = error; return -1; }
    sigset_t defaults, mask;
    sigemptyset(&defaults); sigemptyset(&mask);
    for (size_t index = 0; index < sizeof(lw_signals) / sizeof(*lw_signals); index++) sigaddset(&defaults, lw_signals[index]);
    sigaddset(&defaults, SIGPIPE);
    if (!error) error = posix_spawn_file_actions_addchdir_np(&actions, root);
    if (!error) error = posix_spawnattr_setsigdefault(&attributes, &defaults);
    if (!error) error = posix_spawnattr_setsigmask(&attributes, &mask);
    if (!error) error = posix_spawnattr_setpgroup(&attributes, 0);
    if (!error) error = posix_spawnattr_setflags(&attributes,
        POSIX_SPAWN_SETSIGDEF | POSIX_SPAWN_SETSIGMASK | POSIX_SPAWN_SETPGROUP);
    pid_t child = -1;
#ifdef __APPLE__
    char **environment = *_NSGetEnviron();
#else
    char **environment = environ;
#endif
    char **override = NULL;
    char *setting = NULL;
    char *publication_setting = NULL;
    char running_setting[] = "MINYAR_WATCH_RUNNING=0";
    running_setting[sizeof(running_setting) - 2] = application_running ? '1' : '0';
    if (!error && roots_file) {
        const char prefix[] = "MINYAR_WATCH_ROOTS=";
        const char publication_prefix[] = "MINYAR_WATCH_PUBLICATION=";
        const char running_prefix[] = "MINYAR_WATCH_RUNNING=";
        size_t count = 0;
        while (environment[count]) count++;
        override = calloc(count + 4, sizeof(*override));
        setting = malloc(sizeof(prefix) + strlen(roots_file));
        publication_setting = malloc(sizeof(publication_prefix) + strlen(publication_file));
        if (!override || !setting || !publication_setting) error = ENOMEM;
        else {
            snprintf(setting, sizeof(prefix) + strlen(roots_file), "%s%s", prefix, roots_file);
            snprintf(publication_setting, sizeof(publication_prefix) + strlen(publication_file),
                     "%s%s", publication_prefix, publication_file);
            size_t next = 0;
            for (size_t index = 0; index < count; index++) {
                if (strncmp(environment[index], prefix, sizeof(prefix) - 1) &&
                    strncmp(environment[index], publication_prefix, sizeof(publication_prefix) - 1) &&
                    strncmp(environment[index], running_prefix, sizeof(running_prefix) - 1))
                    override[next++] = environment[index];
            }
            override[next++] = setting;
            override[next++] = publication_setting;
            override[next] = running_setting;
            environment = override;
        }
    }
    if (!error) error = posix_spawn(&child, arguments[0], &actions, &attributes, arguments, environment);
    free(override); free(setting); free(publication_setting);
    posix_spawnattr_destroy(&attributes);
    posix_spawn_file_actions_destroy(&actions);
    if (error) { errno = error; return -1; }
    return child;
}

static void lw_drain(int descriptor) {
    unsigned char buffer[256];
    while (read(descriptor, buffer, sizeof(buffer)) > 0) {}
}

static void lw_stop(pid_t child, int wake) {
    if (child <= 0) return;
    kill(-child, SIGTERM);
    int64_t until = lw_now() + LW_SHUTDOWN_MS;
    int status;
    for (;;) {
        pid_t result = waitpid(child, &status, WNOHANG);
        if (result == child || (result < 0 && errno == ECHILD)) break;
        if (result < 0 && errno != EINTR) break;
        int64_t left = until - lw_now();
        if (left <= 0) break;
        struct pollfd descriptor = {wake, POLLIN, 0};
        if (poll(&descriptor, 1, (int)left) > 0) lw_drain(wake);
    }
    // Descendants cannot outlive a replaced program, even if their parent exits
    // before handling SIGTERM. Reap the direct child exactly once.
    kill(-child, SIGKILL);
    while (waitpid(child, &status, 0) < 0 && errno == EINTR) {}
}

static int lw_status(int status) {
    return WIFEXITED(status) ? WEXITSTATUS(status) : (WIFSIGNALED(status) ? 128 + WTERMSIG(status) : 1);
}

// The project builder writes resolved absolute package roots, each followed by
// NUL, to MINYAR_WATCH_ROOTS. It is private to the supervisor and is never given
// to the application. Empty files allow custom launchers to use the input roots.
static int lw_roots_read(const char *path, char ***result) {
    int descriptor = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (descriptor < 0) return -1;
    struct stat info;
    if (fstat(descriptor, &info) || !S_ISREG(info.st_mode) || info.st_size < 0 || info.st_size > 16777216) {
        int saved = errno ? errno : EINVAL; close(descriptor); errno = saved; return -1;
    }
    size_t size = (size_t)info.st_size;
    if (!size) { close(descriptor); return 0; }
    char *data = malloc(size);
    if (!data) { close(descriptor); return -1; }
    size_t offset = 0;
    while (offset < size) {
        ssize_t count = read(descriptor, data + offset, size - offset);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) {
            int saved = count < 0 ? errno : EIO;
            free(data); close(descriptor); errno = saved; return -1;
        }
        offset += (size_t)count;
    }
    close(descriptor);
    size_t count = 0;
    for (size_t index = 0; index < size; index++) { if (!data[index]) count++; }
    if (data[size - 1] || count > 65536) { free(data); errno = EINVAL; return -1; }
    char **roots = calloc(count + 1, sizeof(*roots));
    if (!roots) { free(data); return -1; }
    offset = 0;
    for (size_t index = 0; index < count; index++) {
        size_t length = strlen(data + offset);
        if (!length || data[offset] != '/') { errno = EINVAL; goto failed; }
        roots[index] = strdup(data + offset);
        if (!roots[index]) goto failed;
        offset += length + 1;
    }
    free(data); *result = roots; return 1;
failed: {
        int saved = errno;
        free(data); lw_free_vector(roots); errno = saved; return -1;
    }
}

static int lw_roots_equal(char **first, char **second) {
    size_t index = 0;
    while (first[index] && second[index]) {
        if (strcmp(first[index], second[index])) return 0;
        index++;
    }
    return !first[index] && !second[index];
}

static int lw_owned(const struct stat *info) {
    return S_ISREG(info->st_mode) && info->st_uid == geteuid() &&
           info->st_size >= 0 && info->st_size <= 16777216;
}

static int lw_reset_record(const char *path) {
    int descriptor = open(path, O_WRONLY | O_CLOEXEC | O_NOFOLLOW);
    if (descriptor < 0) return -1;
    struct stat info;
    int result = fstat(descriptor, &info);
    if (!result && !lw_owned(&info)) { errno = EINVAL; result = -1; }
    if (!result) result = ftruncate(descriptor, 0);
    int saved = errno;
    if (close(descriptor) && !result) return -1;
    errno = saved;
    return result;
}

// Builders prepare a candidate table, then write candidate\0current\0 here.
// Only this supervisor promotes it, after accepting the completed generation.
// A stale/failed build loses its candidate without touching the current table.
static int lw_publication(const char *path, int promote) {
    int descriptor = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (descriptor < 0) return -1;
    struct stat info;
    int result = fstat(descriptor, &info);
    if (!result && !lw_owned(&info)) { errno = EINVAL; result = -1; }
    if (result) { int saved = errno; close(descriptor); errno = saved; return -1; }
    size_t size = (size_t)info.st_size;
    if (!size) { close(descriptor); return 0; }
    char *data = malloc(size);
    if (!data) { close(descriptor); return -1; }
    size_t offset = 0;
    while (offset < size) {
        ssize_t count = read(descriptor, data + offset, size - offset);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) {
            int saved = count < 0 ? errno : EIO;
            free(data); close(descriptor); errno = saved; return -1;
        }
        offset += (size_t)count;
    }
    close(descriptor);
    char *separator = memchr(data, 0, size);
    char *current = separator ? separator + 1 : NULL;
    if (data[0] != '/' || !current || current >= data + size || current[0] != '/' ||
        memchr(current, 0, (size_t)(data + size - current)) != data + size - 1 ||
        !strcmp(data, current)) { errno = EINVAL; result = -1; goto done; }
    if (lstat(data, &info)) { result = -1; goto done; }
    if (!lw_owned(&info)) { errno = EINVAL; result = -1; goto done; }
    if (!promote) { result = unlink(data); goto done; }
    if (!lstat(current, &info)) {
        if (!lw_owned(&info)) { errno = EINVAL; result = -1; goto done; }
    } else if (errno != ENOENT) { result = -1; goto done; }
    result = rename(data, current);
done: {
        int saved = errno;
        free(data); errno = saved; return result;
    }
}

static int lw_supervise(char *launcher, char *root, char **roots, char **arguments,
                        char **options, char *output, bool preserve) {
    if (lw_writer >= 0) { errno = EBUSY; return -1; }
    char **build = lw_command(launcher, NULL, options);
    char **program = lw_command(output, NULL, arguments);
    char **current_roots = roots;
    char roots_file[] = "/tmp/minyar-watch-roots.XXXXXX";
    char publication_file[sizeof(roots_file) + sizeof(".publication")] = {0};
    int roots_descriptor = -1;
    int roots_created = 0;
    int publication_created = 0;
    int wake[2] = {-1, -1};
    LWWatcher watcher = {-1, -1, NULL, 0};
    struct sigaction previous[4];
    size_t installed = 0;
    pid_t building = 0, running = 0;
    int result = -1;
    if (!build || !program || pipe(wake) || lw_fd(wake[0], 1) || lw_fd(wake[1], 1)) goto cleanup;
    roots_descriptor = mkstemp(roots_file);
    if (roots_descriptor < 0) goto cleanup;
    roots_created = 1;
    if (lw_fd(roots_descriptor, 0)) goto cleanup;
    if (close(roots_descriptor)) { roots_descriptor = -1; goto cleanup; }
    roots_descriptor = -1;
    snprintf(publication_file, sizeof(publication_file), "%s.publication", roots_file);
    roots_descriptor = open(publication_file, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (roots_descriptor < 0) goto cleanup;
    publication_created = 1;
    if (close(roots_descriptor)) { roots_descriptor = -1; goto cleanup; }
    roots_descriptor = -1;
    watcher.wake = wake[0];
    if (lw_watcher_reset(&watcher, root, roots)) goto cleanup;
    lw_signal = 0; lw_writer = wake[1];
    struct sigaction action;
    memset(&action, 0, sizeof(action));
    action.sa_handler = lw_handler;
    sigemptyset(&action.sa_mask);
    action.sa_flags = SA_NOCLDSTOP;
    for (; installed < sizeof(lw_signals) / sizeof(*lw_signals); installed++) {
        if (sigaction(lw_signals[installed], &action, &previous[installed])) goto cleanup;
    }
    fprintf(stderr, "[watch] Watching for changes in %s (%s).\n", root,
            preserve ? "preserving runtime state" : "restarting after successful builds");
    unsigned long long generation = 1, build_generation = 0;
    int dirty = 1;
    int64_t rebuild_at = lw_now();
    for (;;) {
        if (lw_signal) { result = 128 + (int)lw_signal; break; }
        int status;
        if (running > 0) {
            pid_t exited = waitpid(running, &status, WNOHANG);
            if (exited == running) {
                kill(-running, SIGKILL);
                running = 0;
                fprintf(stderr, "[watch] Program exited (%d); waiting for an edit.\n", lw_status(status));
            } else if (exited < 0 && errno != EINTR) goto cleanup;
        }
        if (building > 0) {
            pid_t exited = waitpid(building, &status, WNOHANG);
            if (exited == building) {
                kill(-building, SIGKILL); building = 0;
                int code = lw_status(status);
                int changed = 0;
                for (;;) {
                    int pending = lw_events(&watcher, 0);
                    if (pending < 0) goto cleanup;
                    if (pending & 2) lw_drain(wake[0]);
                    if (pending & 1) changed = 1;
                    if (!pending || lw_signal) break;
                }
                if (changed) {
                    generation++; dirty = 1; rebuild_at = lw_now() + LW_DEBOUNCE_MS;
                }
                if (!code) {
                    char **updated = NULL;
                    int loaded = lw_roots_read(roots_file, &updated);
                    if (loaded < 0) goto cleanup;
                    if (loaded && !lw_roots_equal(current_roots, updated)) {
                        if (current_roots != roots) lw_free_vector(current_roots);
                        current_roots = updated;
                        changed = 1;
                    } else lw_free_vector(updated);
                }
                if (changed && lw_watcher_reset(&watcher, root, current_roots)) goto cleanup;
                int accepted = !code && build_generation == generation && !lw_signal;
                if (lw_publication(publication_file, accepted) < 0 && !code) {
                    fprintf(stderr, "[watch] Cannot publish update: %s\n", strerror(errno));
                    code = 1;
                }
                // The drain may have consumed an application-exit notification
                // that arrived after the loop's first child check.
                if (running > 0) {
                    pid_t finished = waitpid(running, &status, WNOHANG);
                    if (finished == running) { kill(-running, SIGKILL); running = 0; }
                    else if (finished < 0 && errno != EINTR) goto cleanup;
                }
                if (code) fprintf(stderr, "[watch] Build failed (%d); keeping the current program.\n", code);
                else if (accepted && preserve && running > 0) {
                    fprintf(stderr, "[watch] Reload ready.\n");
                } else if (accepted) {
                    lw_stop(running, wake[0]); running = 0;
                    if (lw_signal) continue;
                    running = lw_spawn(program, root, NULL, NULL, false);
                    if (running < 0) goto cleanup;
                    fprintf(stderr, "[watch] Program started (pid %ld).\n", (long)running);
                }
                // Recheck both children before blocking after draining SIGCHLD.
                continue;
            } else if (exited < 0 && errno != EINTR) goto cleanup;
        }
        int64_t now = lw_now();
        if (now < 0) goto cleanup;
        if (dirty && !building && now >= rebuild_at) {
            fprintf(stderr, "[watch] Building...\n");
            if (lw_reset_record(roots_file) || lw_reset_record(publication_file)) goto cleanup;
            building = lw_spawn(build, root, roots_file, publication_file, running > 0);
            if (building < 0) goto cleanup;
            build_generation = generation; dirty = 0;
        }
        int timeout = -1;
        if (dirty && !building) {
            int64_t left = rebuild_at - lw_now();
            timeout = left <= 0 ? 0 : (left > INT_MAX ? INT_MAX : (int)left);
        }
        int events = lw_events(&watcher, timeout);
        if (events < 0) goto cleanup;
        if (events & 2) lw_drain(wake[0]);
        if (events & 1) {
            generation++; dirty = 1; rebuild_at = lw_now() + LW_DEBOUNCE_MS;
            if (lw_watcher_reset(&watcher, root, current_roots)) goto cleanup;
        }
    }
cleanup: {
        int saved = errno;
        lw_stop(building, wake[0]);
        lw_stop(running, wake[0]);
        while (installed) { installed--; sigaction(lw_signals[installed], &previous[installed], NULL); }
        lw_writer = -1;
        lw_watcher_close(&watcher);
        if (wake[0] >= 0) close(wake[0]);
        if (wake[1] >= 0) close(wake[1]);
        if (roots_descriptor >= 0) close(roots_descriptor);
        if (publication_created) { (void)lw_publication(publication_file, 0); unlink(publication_file); }
        if (roots_created) unlink(roots_file);
        if (current_roots != roots) lw_free_vector(current_roots);
        free(build); free(program);
        errno = saved;
        return result;
    }
}
#endif

long long minyar_livewatch_supervise(const MinyarText *launcher_value, const MinyarText *root_value,
        const MinyarBytes *root_values, const MinyarBytes *argument_values,
        const MinyarBytes *option_values, const MinyarText *output_value, bool preserve) {
#if defined(__linux__) || defined(__APPLE__)
    char *launcher = lw_text(launcher_value), *root = lw_text(root_value), *output = lw_text(output_value);
    char **roots = lw_vector(root_values), **arguments = lw_vector(argument_values), **options = lw_vector(option_values);
    int result = -1;
    if (launcher && root && output && roots && arguments && options && *launcher && *root && *output) {
        result = lw_supervise(launcher, root, roots, arguments, options, output, preserve);
    } else if (launcher && root && output && (!*launcher || !*root || !*output)) errno = EINVAL;
    if (result < 0) { fprintf(stderr, "[watch] %s\n", strerror(errno)); result = 1; }
    free(launcher); free(root); free(output);
    lw_free_vector(roots); lw_free_vector(arguments); lw_free_vector(options);
    return result;
#else
    (void)launcher_value; (void)root_value; (void)root_values;
    (void)argument_values; (void)option_values; (void)output_value; (void)preserve;
    fprintf(stderr, "[watch] Source watching requires Linux or macOS.\n");
    return 1;
#endif
}
