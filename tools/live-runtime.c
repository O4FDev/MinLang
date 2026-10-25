// Development-only function dispatch. Loaded images stay resident: an older
// frame, closure or literal can still refer to any successful generation.
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
static unsigned live_generation;
struct live_cached { const char *key; void *address; unsigned generation; };
static struct live_cached live_cache[1024];

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
// Every call reads this clock, so prefer the coarse variants: they read a
// kernel-maintained value instead of the hardware clock source. Updates are
// still noticed within 25 ms plus one clock tick.
static int live_clock(struct timespec *now) {
#if defined(CLOCK_MONOTONIC_COARSE)
    return clock_gettime(CLOCK_MONOTONIC_COARSE, now);
#elif defined(CLOCK_MONOTONIC_RAW_APPROX)
    return clock_gettime(CLOCK_MONOTONIC_RAW_APPROX, now);
#else
    return clock_gettime(CLOCK_MONOTONIC, now);
#endif
}
static long long live_elapsed(const struct timespec *now, const struct timespec *before) {
    return (long long)(now->tv_sec - before->tv_sec) * 1000000000LL + now->tv_nsec - before->tv_nsec;
}
static void live_refresh(struct timespec now) {
    long long elapsed = live_elapsed(&now, &live_checked);
    if (elapsed >= 0 && elapsed < 25000000) return;
    live_checked = now;
    struct stat info;
    if (stat(minyar_live_manifest, &info) ||
        (live_have_seen && live_same(&info, &live_seen))) return;
    long long retry_elapsed = live_elapsed(&now, &live_retry_checked);
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
    ++live_generation;
    live_seen = info; live_have_seen = 1; live_have_failed = 0;
    fprintf(stderr, "Reloaded %zu functions; program state preserved\n", count);
}
// Every function call resolves its target here. Hot mode only accepts
// single-threaded programs, so between update checks the published table
// cannot change: lookups skip the lock and are cached by key address.
void *minyar_live_resolve(const char *key, void *initial) {
    struct timespec now;
    if (!live_clock(&now) && live_elapsed(&now, &live_checked) >= 25000000) {
        pthread_mutex_lock(&live_lock);
        live_refresh(now);
        pthread_mutex_unlock(&live_lock);
    }
    if (!live_count) return initial;
    struct live_cached *slot = &live_cache[((uint64_t)(uintptr_t)key * UINT64_C(0x9E3779B97F4A7C15)) >> 54];
    if (slot->key == key && slot->generation == live_generation) return slot->address;
    struct live_entry needle = { key, NULL };
    struct live_entry *found =
        bsearch(&needle, live_entries, live_count, sizeof *live_entries, live_compare);
    slot->key = key; slot->generation = live_generation;
    slot->address = found ? found->address : initial;
    return slot->address;
}
