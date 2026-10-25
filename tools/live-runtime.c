// Development-only function dispatch. Loaded images stay resident: an older
// frame, closure or literal can still refer to any successful generation.
// Each generated wrapper calls through its own slot. The watcher bumps a
// counter in `<manifest>.epoch` after it publishes an update; wrappers compare
// that mapped counter with the last one seen, so an ordinary call costs a few
// loads and no system call, and the first call after a publication loads it.
// Managed threads and parallel loop workers may call wrappers concurrently:
// slots and the seen epoch are read atomically and every update happens under
// live_lock. The seen epoch is stored after the slots it covers (release) and
// read with acquire, so a wrapper that sees a publication's epoch also sees its
// retargeted slots. Slots are retargeted one at a time: a call already running
// across the update can still reach an old body of another function.
//
// A published table (`current`) is NUL-separated text:
//   minyar-live-table-v2, the executable's build id, the image path (or "-"
//   for the executable's own functions), then key/symbol pairs.
// A table for another executable (another build, or a session that was
// replaced) is refused, so a copy only ever runs code built against its own
// wrappers.
#ifndef _GNU_SOURCE
#define _GNU_SOURCE 1
#endif
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

extern const char minyar_live_manifest[];
extern const char minyar_live_build[];
// MINYAR_LIVE_STATE relocates the live state directory recorded at build time,
// for a copy of the binary and its state deployed elsewhere. Image paths in a
// published table that lie under the recorded directory are read from it.
static const char *live_manifest = minyar_live_manifest;
static char *live_relocated;
static size_t live_recorded_length;
struct live_entry { const char *key; void *address; };
struct live_image { void *handle; struct live_image *previous; };
static pthread_mutex_t live_lock = PTHREAD_MUTEX_INITIALIZER;
static struct live_entry *live_entries;
static size_t live_count;
static struct live_image *live_images;
static struct stat live_seen;
static int live_have_seen;
static struct stat live_failed;
static int live_have_failed;
// Every wrapper slot that has been bound, so an update can retarget it.
struct live_slot { void **slot; const char *key; void *initial; };
static struct live_slot *live_slots;
static size_t live_slot_count, live_slot_capacity;
static int live_mapped;
static uint64_t live_epoch_unmapped;
// Read by every generated wrapper.
const uint64_t *minyar_live_epoch = &live_epoch_unmapped;
uint64_t minyar_live_epoch_seen;

static int live_compare(const void *left, const void *right) {
    return strcmp(((const struct live_entry *)left)->key,
                  ((const struct live_entry *)right)->key);
}
static char *live_part(char **cursor, char *end) {
    if (*cursor >= end) return NULL;
    char *value = *cursor;
    char *zero = memchr(value, 0, (size_t)(end - value));
    if (!zero || zero == value) return NULL;
    *cursor = zero + 1;
    return value;
}
static int live_same(const struct stat *a, const struct stat *b) {
#ifdef __APPLE__
    return a->st_ino == b->st_ino && a->st_size == b->st_size &&
        a->st_mtimespec.tv_sec == b->st_mtimespec.tv_sec &&
        a->st_mtimespec.tv_nsec == b->st_mtimespec.tv_nsec;
#else
    return a->st_ino == b->st_ino && a->st_size == b->st_size &&
        a->st_mtim.tv_sec == b->st_mtim.tv_sec &&
        a->st_mtim.tv_nsec == b->st_mtim.tv_nsec;
#endif
}
static void *live_lookup(const char *key, void *initial) {
    struct live_entry needle = { key, NULL };
    struct live_entry *found = live_count ?
        bsearch(&needle, live_entries, live_count, sizeof *live_entries, live_compare) : NULL;
    return found ? found->address : initial;
}
// Retries of the same failing publication stay quiet after the first report.
static void live_report(int repeated, const char *problem, const char *detail) {
    if (repeated) return;
    if (detail) fprintf(stderr, "minyar live: %s: %s\n", problem, detail);
    else fprintf(stderr, "minyar live: %s; keeping current code\n", problem);
}
// Called with live_lock held.
static void live_refresh(void) {
    struct stat info;
    if (stat(live_manifest, &info) ||
        (live_have_seen && live_same(&info, &live_seen))) return;
    int repeated = live_have_failed && live_same(&info, &live_failed);
    live_failed = info; live_have_failed = 1;
    int fd = open(live_manifest, O_RDONLY | O_CLOEXEC);
    if (fd < 0) return;
    if (fstat(fd, &info) || !S_ISREG(info.st_mode) || info.st_size <= 0 ||
        info.st_size > 16 * 1024 * 1024) { close(fd); return; }
    size_t length = (size_t)info.st_size;
    char *storage = malloc(length);
    if (!storage) { close(fd); return; }
    size_t offset = 0;
    while (offset < length) {
        ssize_t got = read(fd, storage + offset, length - offset);
        if (got < 0 && errno == EINTR) continue;
        if (got <= 0) break;
        offset += (size_t)got;
    }
    close(fd);
    // Atomic publication is required; the descriptor pins exactly one version.
    if (offset != length || storage[length - 1] != 0) { free(storage); return; }
    char *cursor = storage, *end = storage + length;
    char *format = live_part(&cursor, end);
    if (!format || strcmp(format, "minyar-live-table-v2")) {
        live_report(repeated, "update has an unknown table format", NULL);
        free(storage); return;
    }
    char *build = live_part(&cursor, end);
    if (!build || strcmp(build, minyar_live_build)) {
        live_report(repeated, "update was built for another executable", NULL);
        free(storage); return;
    }
    char *path = live_part(&cursor, end);
    size_t count = 0;
    for (char *p = cursor; p < end; ++p) if (!*p) ++count;
    // Messages describe a change to code this process has already run.
    int running = live_slot_count != 0;
    if (path && !strcmp(path, "-") && !count) {
        // Every edit reverted, or `minyar patch --undo` back to the original
        // program: every slot returns to the body it was created with.
        free(storage);
        int replaced = live_count != 0;
        free(live_entries);
        live_entries = NULL; live_count = 0;
        for (size_t i = 0; i < live_slot_count; ++i)
            __atomic_store_n(live_slots[i].slot, live_slots[i].initial, __ATOMIC_RELEASE);
        live_seen = info; live_have_seen = 1; live_have_failed = 0;
        if (replaced && running) fprintf(stderr, "Restored original functions; program state preserved\n");
        return;
    }
    if (!path || count % 2 || !count) {
        live_report(repeated, "update has an invalid function table", NULL);
        free(storage); return;
    }
    count /= 2;
    struct live_entry *entries = calloc(count, sizeof *entries);
    struct live_image *image = malloc(sizeof *image);
    if (!entries || !image) { free(entries); free(image); free(storage); return; }
    char *located = NULL;
    if (live_relocated && !strncmp(path, minyar_live_manifest, live_recorded_length) &&
        path[live_recorded_length] == '/') {
        size_t prefix = strlen(live_relocated), rest = strlen(path + live_recorded_length);
        located = malloc(prefix + rest + 1);
        if (!located) { free(entries); free(image); free(storage); return; }
        memcpy(located, live_relocated, prefix);
        memcpy(located + prefix, path + live_recorded_length, rest + 1);
    }
    void *handle = dlopen(located ? located : path, RTLD_NOW | RTLD_LOCAL);
    free(located);
    if (!handle) {
        live_report(repeated, "cannot load update", dlerror());
        free(entries); free(image); free(storage); return;
    }
    int valid = 1;
    for (size_t i = 0; i < count; ++i) {
        entries[i].key = live_part(&cursor, end);
        char *symbol = live_part(&cursor, end);
        if (!entries[i].key || !symbol) { valid = 0; break; }
        dlerror();
        entries[i].address = dlsym(handle, symbol);
        if (!entries[i].address || dlerror()) { valid = 0; break; }
    }
    if (valid) {
        qsort(entries, count, sizeof *entries, live_compare);
        for (size_t i = 1; i < count; ++i)
            if (!strcmp(entries[i - 1].key, entries[i].key)) valid = 0;
    }
    if (!valid) {
        live_report(repeated, "update has an invalid function table", NULL);
        dlclose(handle); free(entries); free(image); free(storage); return;
    }
    image->handle = handle; image->previous = live_images; live_images = image;
    // Each table is complete: a function it omits runs its original body.
    // Earlier tables stay allocated, like their images.
    free(live_entries);
    live_entries = entries; live_count = count;
    for (size_t i = 0; i < live_slot_count; ++i)
        __atomic_store_n(live_slots[i].slot, live_lookup(live_slots[i].key, live_slots[i].initial),
                         __ATOMIC_RELEASE);
    live_seen = info; live_have_seen = 1; live_have_failed = 0;
    if (running) fprintf(stderr, "Reloaded %zu functions; program state preserved\n", count);
}
static void live_map(void) {
    live_mapped = 1;
    const char *relocated = getenv("MINYAR_LIVE_STATE");
    const char *slash = strrchr(minyar_live_manifest, '/');
    if (relocated && *relocated && slash) {
        // Resolved once, into memory of our own: a later chdir or setenv in the
        // program cannot move the directory this copy watches.
        char *resolved = realpath(relocated, NULL);
        char *manifest = resolved ? malloc(strlen(resolved) + strlen(slash) + 1) : NULL;
        if (!manifest) {
            fprintf(stderr, "minyar live: cannot use MINYAR_LIVE_STATE=%s: %s; keeping current code\n",
                    relocated, strerror(resolved ? ENOMEM : errno));
            free(resolved);
            return;
        }
        strcpy(manifest, resolved);
        strcat(manifest, slash);
        live_manifest = manifest;
        live_relocated = resolved;
        live_recorded_length = (size_t)(slash - minyar_live_manifest);
    }
    size_t length = strlen(live_manifest);
    char *path = malloc(length + sizeof ".epoch");
    int descriptor = -1, missing = 0;
    if (path) {
        memcpy(path, live_manifest, length);
        memcpy(path + length, ".epoch", sizeof ".epoch");
        descriptor = open(path, O_RDWR | O_CREAT | O_CLOEXEC, 0600);
        // A read-only deployment (or another service user) can still follow
        // publications through an existing counter.
        if (descriptor < 0 && (errno == EACCES || errno == EROFS || errno == EPERM))
            descriptor = open(path, O_RDONLY | O_CLOEXEC);
        missing = descriptor < 0 && errno == ENOENT;
        free(path);
    }
    struct stat info;
    void *page = MAP_FAILED;
    if (descriptor >= 0 && !fstat(descriptor, &info) &&
        (info.st_size >= (off_t)sizeof(uint64_t) || !ftruncate(descriptor, sizeof(uint64_t))))
        page = mmap(NULL, sizeof(uint64_t), PROT_READ, MAP_SHARED, descriptor, 0);
    if (descriptor >= 0) close(descriptor);
    if (page == MAP_FAILED) {
        // A later build --hot or plain build of the same output removes this
        // build's session; nothing can publish to it any more.
        if (!missing || live_relocated)
            fprintf(stderr, "minyar live: cannot watch for updates; keeping current code\n");
        return;
    }
    __atomic_store_n(&minyar_live_epoch_seen, __atomic_load_n((const uint64_t *)page, __ATOMIC_ACQUIRE),
                     __ATOMIC_RELEASE);
    __atomic_store_n(&minyar_live_epoch, (const uint64_t *)page, __ATOMIC_RELEASE);
    // A copy started after a publication runs it from its first call.
    live_refresh();
}
// Wrappers call here for their first call and after each publication: load
// any new update, retarget every bound slot, then bind this one.
void *minyar_live_bind(const char *key, void *initial, void **slot) {
    pthread_mutex_lock(&live_lock);
    if (!live_mapped) live_map();
    uint64_t epoch = __atomic_load_n(minyar_live_epoch, __ATOMIC_ACQUIRE);
    if (epoch != minyar_live_epoch_seen) {
        // Each epoch is tried once, so calls stay on the fast path even when a
        // publication cannot load yet (say, its files are still arriving); the
        // failure is reported and the next epoch bump retries it.
        live_refresh();
        __atomic_store_n(&minyar_live_epoch_seen, epoch, __ATOMIC_RELEASE);
    }
    void *address = __atomic_load_n(slot, __ATOMIC_ACQUIRE);
    if (!address) {
        address = live_lookup(key, initial);
        if (live_slot_count == live_slot_capacity) {
            size_t capacity = live_slot_capacity ? live_slot_capacity * 2 : 256;
            struct live_slot *grown = realloc(live_slots, capacity * sizeof *grown);
            if (grown) { live_slots = grown; live_slot_capacity = capacity; }
        }
        // Without room the slot stays empty and the next call binds again.
        if (live_slot_count < live_slot_capacity) {
            live_slots[live_slot_count++] = (struct live_slot){ slot, key, initial };
            __atomic_store_n(slot, address, __ATOMIC_RELEASE);
        }
    }
    pthread_mutex_unlock(&live_lock);
    return address;
}
