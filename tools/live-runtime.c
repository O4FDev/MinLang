// Development-only function dispatch. Loaded images stay resident: an older
// frame, closure or literal can still refer to any successful generation.
#ifndef _GNU_SOURCE
#define _GNU_SOURCE 1
#endif
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

extern const char minyar_live_manifest[];
struct live_entry { const char *key; void *address; };
struct live_image { void *handle; struct live_image *previous; };
static pthread_mutex_t live_lock = PTHREAD_MUTEX_INITIALIZER;
static struct live_entry *live_entries;
static size_t live_count;
static char *live_storage;
static struct live_image *live_images;
static struct stat live_seen;
static int live_have_seen;
static struct stat live_failed;
static int live_have_failed;
static struct timespec live_retry_checked;
static struct timespec live_checked;

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
static void live_refresh(void) {
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now)) return;
    long long elapsed = (long long)(now.tv_sec - live_checked.tv_sec) * 1000000000LL +
        now.tv_nsec - live_checked.tv_nsec;
    if (elapsed >= 0 && elapsed < 25000000) return;
    live_checked = now;
    struct stat info;
    if (stat(minyar_live_manifest, &info) ||
        (live_have_seen && live_same(&info, &live_seen))) return;
    long long retry_elapsed = (long long)(now.tv_sec - live_retry_checked.tv_sec) * 1000000000LL +
        now.tv_nsec - live_retry_checked.tv_nsec;
    if (live_have_failed && live_same(&info, &live_failed) &&
        retry_elapsed >= 0 && retry_elapsed < 1000000000LL) return;
    live_failed = info; live_have_failed = 1; live_retry_checked = now;
    int fd = open(minyar_live_manifest, O_RDONLY | O_CLOEXEC);
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
    char *path = live_part(&cursor, end);
    size_t count = 0;
    for (char *p = cursor; p < end; ++p) if (!*p) ++count;
    if (!path || count % 2 || !count) { free(storage); return; }
    count /= 2;
    struct live_entry *entries = calloc(count, sizeof *entries);
    struct live_image *image = malloc(sizeof *image);
    if (!entries || !image) { free(entries); free(image); free(storage); return; }
    void *handle = dlopen(path, RTLD_NOW | RTLD_LOCAL);
    if (!handle) {
        fprintf(stderr, "minyar live: cannot load update: %s\n", dlerror());
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
        fprintf(stderr, "minyar live: update has an invalid function table; keeping current code\n");
        dlclose(handle); free(entries); free(image); free(storage); return;
    }
    image->handle = handle; image->previous = live_images; live_images = image;
    free(live_entries); free(live_storage);
    live_entries = entries; live_count = count; live_storage = storage;
    live_seen = info; live_have_seen = 1; live_have_failed = 0;
    fprintf(stderr, "Reloaded %zu functions; program state preserved\n", count);
}
void *minyar_live_resolve(const char *key, void *initial) {
    pthread_mutex_lock(&live_lock);
    live_refresh();
    struct live_entry needle = { key, NULL };
    struct live_entry *found = live_count ?
        bsearch(&needle, live_entries, live_count, sizeof *live_entries, live_compare) : NULL;
    void *address = found ? found->address : initial;
    pthread_mutex_unlock(&live_lock);
    return address;
}
