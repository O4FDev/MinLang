/* Durable file I/O and a background group-commit syncer for the `files` package.
 *
 * Minyar's built-in readBytesFile/writeBytesFile replace whole files with no durability guarantee. Databases,
 * logs and anything crash-safe need open/append/pwrite, fdatasync before acknowledging, atomic rename plus a
 * directory fsync, and a way to fsync without stalling the single Minyar thread. This module provides those.
 *
 * Convention: Integer results are >= 0 on success and -errno on failure. Bytes-returning calls return empty Bytes
 * on failure and record -errno for files.lastError(). Everything except the syncer threads runs on the Minyar
 * thread; a syncer thread never touches managed values, only its own file descriptors and atomics.
 *
 * Ported from neo-db's native/dbio.c (2026-10-12), where it was the database's only C escape hatch. */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE 1
#endif
#ifdef __APPLE__
#define _DARWIN_C_SOURCE 1
#endif
#include "../minyar_native.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>
#if defined(__APPLE__) && defined(F_PREALLOCATE)
#include <sys/attr.h>
#endif
#ifdef __linux__
#include <linux/falloc.h>
#include <linux/magic.h>
#include <sys/vfs.h>
#endif

static int files_last_error; /* negative errno of the last Bytes-returning call, 0 on success */

/* fdatasync where it exists; macOS needs F_FULLFSYNC to reach stable storage. */
static int files_fullsync(int fd);
static int files_datasync(int fd) {
#ifdef __APPLE__
    return files_fullsync(fd);
#else
    return fdatasync(fd);
#endif
}

static int files_fullsync(int fd) {
#ifdef __APPLE__
    int rc;
    do { rc = fcntl(fd, F_FULLFSYNC); } while (rc != 0 && errno == EINTR);
    return rc;
#else
    return fsync(fd);
#endif
}

static int files_cloexec_nonblock(int fd, bool nonblock) {
    int flags = fcntl(fd, F_GETFD);
    if (flags < 0 || fcntl(fd, F_SETFD, flags | FD_CLOEXEC) < 0) return -errno;
    if (nonblock) {
        flags = fcntl(fd, F_GETFL);
        if (flags < 0 || fcntl(fd, F_SETFL, flags | O_NONBLOCK) < 0) return -errno;
    }
    return 0;
}

/* Copy a path into a NUL-terminated buffer. Rejects empty, too long, or embedded NUL. */
static int files_path(const MinyarText *text, char *out) {
    if (!text || text->byte_length <= 0 || text->byte_length >= PATH_MAX) return -ENAMETOOLONG;
    if (memchr(text->bytes, 0, (size_t)text->byte_length)) return -EINVAL;
    memcpy(out, text->bytes, (size_t)text->byte_length);
    out[text->byte_length] = 0;
    return 0;
}

static bool files_valid_fd(long long fd) { return fd >= 0 && fd <= INT_MAX; }

static bool files_valid_range(const MinyarBytes *data, long long offset, long long length) {
    return data && offset >= 0 && length >= 0 && offset <= data->byte_length && length <= data->byte_length - offset;
}

static MinyarBytes *files_empty(int err) {
    files_last_error = err;
    return minyar_bytes_new(0);
}

long long minyar_files_lastError(void) { return files_last_error; }

MinyarText *minyar_files_errorText(long long code) {
    if (code < -(long long)INT_MAX || code > INT_MAX) {
        const char *invalid = "invalid operating-system error code";
        return minyar_native_copy_text((const unsigned char *)invalid, (long long)strlen(invalid));
    }
    const char *s = strerror((int)(code < 0 ? -code : code));
    return minyar_native_copy_text((const unsigned char *)s, (long long)strlen(s));
}

/* ---------------------------------------------------------------- files */

enum { FILES_WRITE = 2, FILES_CREATE = 4, FILES_APPEND = 8, FILES_TRUNCATE = 16, FILES_EXCLUSIVE = 32 };

long long minyar_files_open(const MinyarText *path, long long flags) {
    char p[PATH_MAX];
    int rc = files_path(path, p);
    if (rc) return rc;
    int f = O_CLOEXEC | ((flags & FILES_WRITE) ? O_RDWR : O_RDONLY);
    if (flags & FILES_CREATE) f |= O_CREAT;
    if (flags & FILES_APPEND) f |= O_APPEND;
    if (flags & FILES_TRUNCATE) f |= O_TRUNC;
    if (flags & FILES_EXCLUSIVE) f |= O_EXCL;
    int fd;
    do { fd = open(p, f, 0644); } while (fd < 0 && errno == EINTR);
    return fd < 0 ? -errno : fd;
}

long long minyar_files_close(long long fd) {
    if (!files_valid_fd(fd)) return -EBADF;
    return close((int)fd) == 0 ? 0 : -errno;
}

/* Write all of data[offset, offset+length); position < 0 means write() at the current file position. */
static long long files_write_all(long long fd, const MinyarBytes *data, long long offset, long long length,
                                 long long position) {
    if (!files_valid_fd(fd)) return -EBADF;
    if (!files_valid_range(data, offset, length)) return -EINVAL;
    const unsigned char *p = data->bytes + offset;
    long long done = 0;
    while (done < length) {
        size_t chunk = (size_t)(length - done);
        if (chunk > (1u << 30)) chunk = 1u << 30;
        ssize_t n = position < 0 ? write((int)fd, p + done, chunk)
                                 : pwrite((int)fd, p + done, chunk, (off_t)(position + done));
        if (n < 0) {
            if (errno == EINTR) continue;
            return -errno;
        }
        if (n == 0) return -EIO;
        done += n;
    }
    return length;
}

long long minyar_files_write(long long fd, const MinyarBytes *data, long long offset, long long length) {
    return files_write_all(fd, data, offset, length, -1);
}

long long minyar_files_writeAt(long long fd, const MinyarBytes *data, long long offset, long long length,
                               long long position) {
    if (position < 0) return -EINVAL;
    if (!files_valid_fd(fd)) return -EBADF;
    if (!files_valid_range(data, offset, length)) return -EINVAL;
    if (position > LLONG_MAX - length || (long long)(off_t)(position + length) != position + length)
        return -EOVERFLOW;
    int flags = fcntl((int)fd, F_GETFL);
    if (flags < 0) return -errno;
    if (flags & O_APPEND) return -EINVAL;
    return files_write_all(fd, data, offset, length, position);
}

long long minyar_files_writeStandardOutput(const MinyarText *text) {
    if (!text) return -EINVAL;
    return files_write_all(1, text, 0, text->byte_length, -1);
}

/* Read up to length bytes at position into fresh Bytes (shorter at end of file). */
long long minyar_files_readAppend(long long fd, long long position, MinyarBytes *buffer, long long length) {
    if (!files_valid_fd(fd)) { files_last_error = -EBADF; return -EBADF; }
    if (!buffer || position < 0 || length < 0) { files_last_error = -EINVAL; return -EINVAL; }
    if ((unsigned long long)length >= SIZE_MAX / 2 || position > LLONG_MAX - length ||
        (long long)(off_t)(position + length) != position + length ||
        buffer->byte_length > LLONG_MAX - length) {
        files_last_error = -EOVERFLOW;
        return -EOVERFLOW;
    }
    long long before = buffer->byte_length;
    unsigned char *p = minyar_native_bytes_append(buffer, length);
    long long done = 0;
    while (done < length) {
        size_t chunk = (size_t)(length - done);
        if (chunk > (1u << 30)) chunk = 1u << 30;
        ssize_t n = pread((int)fd, p + done, chunk, (off_t)(position + done));
        if (n < 0) {
            if (errno == EINTR) continue;
            int e = -errno;
            buffer->byte_length = before;
            files_last_error = e;
            return e;
        }
        if (n == 0) break;
        done += n;
    }
    buffer->byte_length = before + done;
    files_last_error = 0;
    return done;
}

MinyarBytes *minyar_files_readAt(long long fd, long long position, long long length) {
    if (!files_valid_fd(fd)) return files_empty(-EBADF);
    if (position < 0 || length < 0) return files_empty(-EINVAL);
    if ((unsigned long long)length >= SIZE_MAX / 2 || position > LLONG_MAX - length ||
        (long long)(off_t)(position + length) != position + length) return files_empty(-EOVERFLOW);
    /* Validate even a zero-length read. Grow only after bytes arrive: callers may ask for a huge range at
     * EOF, and procfs/sysfs files can report size zero while still supplying data. */
    struct stat st;
    if (fstat((int)fd, &st) != 0) return files_empty(-errno);
    MinyarBytes *b = minyar_bytes_new(0);
    unsigned char buffer[65536];
    long long done = 0;
    while (done < length) {
        size_t chunk = (size_t)(length - done);
        if (chunk > sizeof(buffer)) chunk = sizeof(buffer);
        ssize_t n = pread((int)fd, buffer, chunk, (off_t)(position + done));
        if (n < 0) {
            if (errno == EINTR) continue;
            files_last_error = -errno;
            b->byte_length = 0;
            return b;
        }
        if (n == 0) break;
        memcpy(minyar_native_bytes_append(b, n), buffer, (size_t)n);
        done += n;
    }
    b->byte_length = done; /* shrinking keeps capacity in character_length */
    files_last_error = 0;
    return b;
}

MinyarBytes *minyar_files_readFile(const MinyarText *path) {
    char p[PATH_MAX];
    int rc = files_path(path, p);
    if (rc) return files_empty(rc);
    int fd = open(p, O_RDONLY | O_CLOEXEC);
    if (fd < 0) return files_empty(-errno);
    struct stat st;
    if (fstat(fd, &st) != 0) {
        int e = -errno;
        close(fd);
        return files_empty(e);
    }
    /* st_size is not a reliable bound for pseudo-files. */
    MinyarBytes *b = minyar_files_readAt(fd, 0, (long long)(SIZE_MAX / 2 - 1));
    int e = files_last_error;
    close(fd);
    files_last_error = e;
    return b;
}

long long minyar_files_syncData(long long fd) {
    if (!files_valid_fd(fd)) return -EBADF;
    return files_datasync((int)fd) == 0 ? 0 : -errno;
}

long long minyar_files_sync(long long fd) {
    if (!files_valid_fd(fd)) return -EBADF;
    return files_fullsync((int)fd) == 0 ? 0 : -errno;
}

long long minyar_files_size(long long fd) {
    if (!files_valid_fd(fd)) return -EBADF;
    struct stat st;
    return fstat((int)fd, &st) == 0 ? (long long)st.st_size : -errno;
}

long long minyar_files_pathSize(const MinyarText *path) {
    char p[PATH_MAX];
    int rc = files_path(path, p);
    if (rc) return rc;
    struct stat st;
    return stat(p, &st) == 0 ? (long long)st.st_size : -errno;
}

long long minyar_files_truncate(long long fd, long long length) {
    if (!files_valid_fd(fd)) return -EBADF;
    if (length < 0) return -EINVAL;
    if ((long long)(off_t)length != length) return -EOVERFLOW;
    return ftruncate((int)fd, (off_t)length) == 0 ? 0 : -errno;
}

/* Reserve storage without discarding existing bytes or shrinking the file. No durability is implied. */
long long minyar_files_preallocate(long long fd, long long length) {
    if (!files_valid_fd(fd)) return -EBADF;
    if (length < 0) return -EINVAL;
    if ((long long)(off_t)length != length) return -EOVERFLOW;
    struct stat st;
    if (fstat((int)fd, &st) != 0) return -errno;
    if (!S_ISREG(st.st_mode)) return -EINVAL;
    if (!length) return 0;
    int flags = fcntl((int)fd, F_GETFL);
    if (flags < 0) return -errno;
    if ((flags & O_ACCMODE) == O_RDONLY) return -EBADF;
    int rc;
#if defined(__APPLE__) && defined(F_PREALLOCATE)
    /* Darwin's F_PREALLOCATE only reserves from physical EOF; it cannot fill an existing logical hole.
     * Check the requested existing prefix by extent, rather than counting blocks anywhere in the file.
     * F_LOG2PHYS_EXT takes an explicit position and leaves the shared descriptor offset unchanged. */
    long long existing = length < st.st_size ? length : st.st_size;
    if (existing > 0) {
        /* A physical mapping does not establish private writable storage: APFS clones share extents.
         * Require the sharing-status attribute to be explicitly returned; missing metadata is unknown. */
        struct attrlist attributes = {0};
        attributes.bitmapcount = ATTR_BIT_MAP_COUNT;
        attributes.commonattr = ATTR_CMN_RETURNED_ATTRS;
        attributes.forkattr = ATTR_CMNEXT_EXT_FLAGS;
        struct { uint32_t length; attribute_set_t returned; uint64_t flags; } sharing = {0};
        do { rc = fgetattrlist((int)fd, &attributes, &sharing, sizeof(sharing), FSOPT_ATTR_CMN_EXTENDED); }
        while (rc != 0 && errno == EINTR);
        if (rc != 0) return -errno;
        if (sharing.length != sizeof(sharing) || !(sharing.returned.forkattr & ATTR_CMNEXT_EXT_FLAGS))
            return -ENOTSUP;
        if (sharing.flags & (EF_MAY_SHARE_BLOCKS | EF_SHARES_ALL_BLOCKS)) return -ENOTSUP;
    }
    long long at = 0;
    bool flushed = false;
    while (at < existing) {
        struct log2phys mapping = {0};
        mapping.l2p_devoffset = (off_t)at;
        mapping.l2p_contigbytes = (off_t)(existing - at);
        do { rc = fcntl((int)fd, F_LOG2PHYS_EXT, &mapping); } while (rc != 0 && errno == EINTR);
        if (rc != 0) return -errno;
        if (mapping.l2p_devoffset < 0 || mapping.l2p_contigbytes <= 0) {
            /* Delayed allocation can also hide dirty, non-sparse data. Flush once and retry the same extent
             * before declaring a hole unsupported. This weak fsync is not the stable-storage sync promise. */
            if (flushed) return -ENOTSUP;
            do { rc = fsync((int)fd); } while (rc != 0 && errno == EINTR);
            if (rc != 0) return -errno;
            flushed = true;
            continue;
        }
        long long mapped = (long long)mapping.l2p_contigbytes;
        at += mapped < existing - at ? mapped : existing - at;
    }
    if (st.st_size >= length) return 0;
    /* The existing prefix is backed. Reserve the extension from EOF, including a fresh file's whole range.
     * Do not subtract st_blocks: tail data or other reservations do not establish prefix coverage. */
    fstore_t store = {0};
    store.fst_flags = F_ALLOCATEALL;
#ifdef F_ALLOCATEPERSIST
    store.fst_flags |= F_ALLOCATEPERSIST;
#endif
    store.fst_posmode = F_PEOFPOSMODE;
    store.fst_length = (off_t)(length - st.st_size);
    do { rc = fcntl((int)fd, F_PREALLOCATE, &store); } while (rc != 0 && errno == EINTR);
    if (rc != 0) return -errno;
    return minyar_files_truncate(fd, length);
#elif defined(__linux__)
    /* Reserve private storage for existing CoW data before extending the file. Ordinary allocation alone
     * does not unshare reflink extents. Unsupported unsharing is safe to omit only on a known non-CoW backend. */
    long long existing = length < st.st_size ? length : st.st_size;
    if (existing > 0) {
        do { rc = fallocate((int)fd, FALLOC_FL_UNSHARE_RANGE | FALLOC_FL_KEEP_SIZE, 0, (off_t)existing); }
        while (rc != 0 && errno == EINTR);
        if (rc != 0) {
            int error = errno;
            if (error != EOPNOTSUPP) return -error;
            struct statfs filesystem;
            if (fstatfs((int)fd, &filesystem) != 0) return -errno;
            /* ext2/3/4 share this type and do not implement reflink/remap operations. Unknown/Cow-capable
             * filesystems without UNSHARE support cannot establish this guarantee through mappings. */
            if (filesystem.f_type != EXT4_SUPER_MAGIC && filesystem.f_type != TMPFS_MAGIC) return -ENOTSUP;
        }
    }
    /* Use the kernel operation: libc's fallback can overwrite concurrent writes while filling holes. */
    do { rc = fallocate((int)fd, 0, 0, (off_t)length); } while (rc != 0 && errno == EINTR);
    return rc == 0 ? 0 : -errno;
#else
    do { rc = posix_fallocate((int)fd, 0, (off_t)length); } while (rc == EINTR);
    return -rc;
#endif
}

long long minyar_files_rename(const MinyarText *from, const MinyarText *to) {
    char a[PATH_MAX], b[PATH_MAX];
    int rc = files_path(from, a);
    if (rc) return rc;
    rc = files_path(to, b);
    if (rc) return rc;
    return rename(a, b) == 0 ? 0 : -errno;
}

long long minyar_files_remove(const MinyarText *path) {
    char p[PATH_MAX];
    int rc = files_path(path, p);
    if (rc) return rc;
    return unlink(p) == 0 ? 0 : -errno;
}

long long minyar_files_removeDirectory(const MinyarText *path) {
    char p[PATH_MAX];
    int rc = files_path(path, p);
    if (rc) return rc;
    return rmdir(p) == 0 ? 0 : -errno;
}

long long minyar_files_makeDirectory(const MinyarText *path) {
    char p[PATH_MAX];
    int rc = files_path(path, p);
    if (rc) return rc;
    if (mkdir(p, 0755) == 0) return 0;
    int e = errno;
    struct stat st;
    if (e == EEXIST && stat(p, &st) == 0 && S_ISDIR(st.st_mode)) return 0;
    return -e;
}

long long minyar_files_syncDirectory(const MinyarText *path) {
    char p[PATH_MAX];
    int rc = files_path(path, p);
    if (rc) return rc;
    int fd = open(p, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (fd < 0) return -errno;
    int r = fsync(fd) == 0 ? 0 : -errno;
    close(fd);
    return r;
}

/* NUL-delimited entry names represent every legal POSIX filename. */
MinyarBytes *minyar_files_listNames(const MinyarText *path) {
    char p[PATH_MAX];
    int rc = files_path(path, p);
    if (rc) return files_empty(rc);
    DIR *d = opendir(p);
    if (!d) return files_empty(-errno);
    MinyarBytes *out = minyar_bytes_new(0);
    struct dirent *e;
    int error = 0;
    for (;;) {
        errno = 0;
        e = readdir(d);
        if (!e) { error = errno; break; }
        if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, "..")) continue;
        size_t n = strlen(e->d_name);
        unsigned char *dst = minyar_native_bytes_append(out, (long long)n + 1);
        memcpy(dst, e->d_name, n);
        dst[n] = 0;
    }
    if (closedir(d) != 0 && !error) error = errno;
    if (error) out->byte_length = 0;
    files_last_error = -error;
    return out;
}

/* ---------------------------------------------------------------- group-commit syncer
 *
 * One pthread per log. The Minyar thread calls syncerRequest(upTo): a mutex + condvar signal that coalesces to the
 * largest requested offset. The thread runs fdatasync on its own dup of the file WITHOUT holding the lock, then
 * publishes synced = target (atomic, release) and writes one byte to a socketpair, which an `eventloop` watch turns
 * into an ordinary readiness event. Requests that arrive during one fdatasync are covered by the next: group commit.
 *
 * Offsets are caller-defined positions in a logical stream (for a write-ahead log, LSNs). The syncer never writes
 * data; callers write first and then request a sync up to the end of what they wrote.
 *
 * Segment rotation: syncerSwitch(newFd, start) queues a new file. Before using it the thread fdatasyncs the old file
 * (covering everything below start, which the caller guarantees it already wrote), publishes start, and continues
 * with the new file. After a failed fdatasync nothing more is ever reported durable (the error is sticky). */

#ifndef FILES_MAX_SYNCERS
#define FILES_MAX_SYNCERS 4096
#endif
enum { FILES_MAX_PENDING = 64, FILES_SYNCER_STACK = 256 * 1024 };

typedef struct {
    int fd;
    long long start;
} FilesPendingSegment;

typedef struct {
    bool used;
    uint64_t generation;
    pthread_t thread;
    pthread_mutex_t mu;
    pthread_cond_t wake; /* Minyar thread -> syncer: new request, switch or stop */
    pthread_cond_t done; /* syncer -> syncerWait */
    int fd;
    FilesPendingSegment pending[FILES_MAX_PENDING];
    int npending;
    long long requested; /* protected by mu; only grows */
    long long last_start; /* largest accepted rotation, including in-flight ones */
    _Atomic long long synced;
    _Atomic int error;
    bool stop;
    int notify_read, notify_write;
} FilesSyncer;

static FilesSyncer *files_syncers[FILES_MAX_SYNCERS];
static uint64_t files_syncer_generations[FILES_MAX_SYNCERS];

static FilesSyncer *files_syncer(long long handle) {
    if (handle <= 0 || !(handle & 1)) return NULL;
    uint64_t identity = (uint64_t)handle / 2;
    FilesSyncer *s = files_syncers[identity % FILES_MAX_SYNCERS];
    return s && s->used && s->generation == identity / FILES_MAX_SYNCERS ? s : NULL;
}

static void files_notify(FilesSyncer *s) {
    /* Non-blocking: EAGAIN means unread bytes are already pending, so the loop wakes anyway. */
    char byte = 1;
    ssize_t n;
    do { n = write(s->notify_write, &byte, 1); } while (n < 0 && errno == EINTR);
}

static void *files_syncer_main(void *arg) {
    FilesSyncer *s = arg;
    pthread_mutex_lock(&s->mu);
    for (;;) {
        while (!s->stop && s->npending == 0 && s->requested <= atomic_load(&s->synced))
            pthread_cond_wait(&s->wake, &s->mu);
        if (s->npending == 0 && s->requested <= atomic_load(&s->synced)) break; /* stopping, nothing left */
        if (atomic_load(&s->error) != 0) {
            if (s->stop) break;
            pthread_cond_wait(&s->wake, &s->mu);
            continue;
        }
        int fd = s->fd;
        long long target;
        bool switching = s->npending > 0;
        FilesPendingSegment next = {-1, 0};
        if (switching) {
            next = s->pending[0];
            memmove(&s->pending[0], &s->pending[1], (size_t)(s->npending - 1) * sizeof(FilesPendingSegment));
            s->npending--;
            target = next.start;
        } else {
            target = s->requested;
        }
        pthread_mutex_unlock(&s->mu);
        int rc;
        do { rc = files_datasync(fd); } while (rc != 0 && errno == EINTR);
        int err = rc == 0 ? 0 : -errno;
        if (switching) close(fd);
        pthread_mutex_lock(&s->mu);
        if (switching) s->fd = next.fd;
        if (err) {
            atomic_store(&s->error, err);
        } else if (target > atomic_load(&s->synced)) {
            atomic_store_explicit(&s->synced, target, memory_order_release);
        }
        pthread_cond_broadcast(&s->done);
        files_notify(s);
    }
    pthread_mutex_unlock(&s->mu);
    return NULL;
}

long long minyar_files_syncerStart(long long fd) {
    if (!files_valid_fd(fd)) return -EBADF;
    int slot = -1;
    for (int i = 0; i < FILES_MAX_SYNCERS; i++)
        if (!files_syncers[i] && files_syncer_generations[i] <
            ((uint64_t)LLONG_MAX / 2 - FILES_MAX_SYNCERS) / FILES_MAX_SYNCERS) {
            slot = i;
            break;
        }
    if (slot < 0) return -EMFILE;
    /* A closed caller fd must not alias a notification socket allocated here. */
    int dupfd = fcntl((int)fd, F_DUPFD_CLOEXEC, 0);
    if (dupfd < 0) return -errno;
    FilesSyncer *s = calloc(1, sizeof(*s));
    if (!s) { close(dupfd); return -ENOMEM; }
    uint64_t generation = files_syncer_generations[slot];
    s->generation = generation;
    int sv[2];
    if (socketpair(AF_UNIX, SOCK_STREAM, 0, sv) != 0) {
        int error = errno; close(dupfd); free(s); return -error;
    }
    int error = files_cloexec_nonblock(sv[0], true);
    if (!error) error = files_cloexec_nonblock(sv[1], true);
    if (error) goto fail_descriptors;
    s->notify_read = sv[0];
    s->notify_write = sv[1];
    s->fd = dupfd;
    atomic_store(&s->synced, 0);
    atomic_store(&s->error, 0);
    error = -pthread_mutex_init(&s->mu, NULL);
    if (error) goto fail_descriptors;
    error = -pthread_cond_init(&s->wake, NULL);
    if (error) goto fail_mutex;
    error = -pthread_cond_init(&s->done, NULL);
    if (error) goto fail_wake;
    pthread_attr_t attr;
    error = -pthread_attr_init(&attr);
    if (error) goto fail_done;
    error = -pthread_attr_setstacksize(&attr, FILES_SYNCER_STACK);
    if (!error) error = -pthread_create(&s->thread, &attr, files_syncer_main, s);
    pthread_attr_destroy(&attr);
    if (error) goto fail_done;
    s->generation = generation + 1;
    files_syncer_generations[slot] = s->generation;
    files_syncers[slot] = s;
    s->used = true;
    return ((long long)(s->generation * FILES_MAX_SYNCERS) + slot) * 2 + 1;
fail_done:
    pthread_cond_destroy(&s->done);
fail_wake:
    pthread_cond_destroy(&s->wake);
fail_mutex:
    pthread_mutex_destroy(&s->mu);
fail_descriptors:
    close(dupfd);
    close(sv[0]);
    close(sv[1]);
    free(s);
    return error;
}

long long minyar_files_syncerNotifySocket(long long handle) {
    FilesSyncer *s = files_syncer(handle);
    return s ? s->notify_read : -EBADF;
}

long long minyar_files_syncerRequest(long long handle, long long upTo) {
    FilesSyncer *s = files_syncer(handle);
    if (!s) return -EBADF;
    if (upTo < 0) return -EINVAL;
    /* requested only grows and only this thread writes it, so an unlocked read is a safe lower bound. */
    if (upTo <= atomic_load_explicit(&s->synced, memory_order_acquire) || upTo <= s->requested) return 0;
    pthread_mutex_lock(&s->mu);
    if (upTo > s->requested) {
        s->requested = upTo;
        pthread_cond_signal(&s->wake);
    }
    pthread_mutex_unlock(&s->mu);
    return 0;
}

long long minyar_files_syncerSynced(long long handle) {
    FilesSyncer *s = files_syncer(handle);
    return s ? atomic_load_explicit(&s->synced, memory_order_acquire) : -EBADF;
}

long long minyar_files_syncerError(long long handle) {
    FilesSyncer *s = files_syncer(handle);
    return s ? atomic_load(&s->error) : -EBADF;
}

long long minyar_files_syncerDrain(long long handle) {
    FilesSyncer *s = files_syncer(handle);
    if (!s) return -EBADF;
    char buf[256];
    long long total = 0;
    for (;;) {
        ssize_t n = read(s->notify_read, buf, sizeof(buf));
        if (n > 0) {
            total += n;
            continue;
        }
        if (n < 0 && errno == EINTR) continue;
        break;
    }
    return total;
}

long long minyar_files_syncerWait(long long handle, long long upTo, long long timeoutMs) {
    FilesSyncer *s = files_syncer(handle);
    if (!s) return -EBADF;
    if (upTo < 0 || timeoutMs < -1) return -EINVAL;
    struct timespec deadline;
    clock_gettime(CLOCK_REALTIME, &deadline); /* pthread_cond_timedwait default clock (portable to macOS) */
    if (timeoutMs >= 0) {
        deadline.tv_sec += timeoutMs / 1000;
        deadline.tv_nsec += (timeoutMs % 1000) * 1000000L;
        if (deadline.tv_nsec >= 1000000000L) {
            deadline.tv_sec++;
            deadline.tv_nsec -= 1000000000L;
        }
    }
    pthread_mutex_lock(&s->mu);
    if (upTo > s->requested) {
        s->requested = upTo;
        pthread_cond_signal(&s->wake);
    }
    long long result;
    for (;;) {
        long long synced = atomic_load(&s->synced);
        int err = atomic_load(&s->error);
        if (synced >= upTo) {
            result = synced;
            break;
        }
        if (err) {
            result = err;
            break;
        }
        int rc = timeoutMs >= 0 ? pthread_cond_timedwait(&s->done, &s->mu, &deadline)
                                : pthread_cond_wait(&s->done, &s->mu);
        if (rc == ETIMEDOUT) {
            result = -ETIMEDOUT;
            break;
        }
    }
    pthread_mutex_unlock(&s->mu);
    return result;
}

long long minyar_files_syncerSwitch(long long handle, long long newFd, long long startOffset) {
    FilesSyncer *s = files_syncer(handle);
    if (!s) return -EBADF;
    if (startOffset < 0) return -EINVAL;
    if (!files_valid_fd(newFd)) return -EBADF;
    int dupfd = fcntl((int)newFd, F_DUPFD_CLOEXEC, 0);
    if (dupfd < 0) return -errno;
    pthread_mutex_lock(&s->mu);
    if (startOffset < s->requested || startOffset < s->last_start || startOffset < atomic_load(&s->synced)) {
        pthread_mutex_unlock(&s->mu);
        close(dupfd);
        return -EINVAL;
    }
    if (s->npending == FILES_MAX_PENDING) {
        pthread_mutex_unlock(&s->mu);
        close(dupfd);
        return -EBUSY;
    }
    s->pending[s->npending].fd = dupfd;
    s->pending[s->npending].start = startOffset;
    s->last_start = startOffset;
    s->npending++;
    pthread_cond_signal(&s->wake);
    pthread_mutex_unlock(&s->mu);
    return 0;
}

long long minyar_files_syncerStop(long long handle) {
    FilesSyncer *s = files_syncer(handle);
    if (!s) return -EBADF;
    pthread_mutex_lock(&s->mu);
    s->stop = true;
    pthread_cond_signal(&s->wake);
    pthread_mutex_unlock(&s->mu);
    pthread_join(s->thread, NULL);
    for (int i = 0; i < s->npending; i++) close(s->pending[i].fd);
    close(s->fd);
    close(s->notify_read);
    close(s->notify_write);
    int err = atomic_load(&s->error);
    pthread_mutex_destroy(&s->mu);
    pthread_cond_destroy(&s->wake);
    pthread_cond_destroy(&s->done);
    files_syncers[((uint64_t)handle / 2) % FILES_MAX_SYNCERS] = NULL;
    free(s);
    return err;
}

/* ---------------------------------------------------------------- one-shot file preparation
 * The caller exclusively owns the file contents until completion. The worker owns a dup, uses only unmanaged
 * storage, and publishes completion only after zeroing and stable-storage sync (or a sticky failure). Stop joins;
 * it does not cancel a partially prepared file or report it durable before the worker has actually finished. */
enum { FILES_MAX_PREPARES = 16 };
typedef struct {
    bool used;
    uint64_t generation;
    pthread_t thread;
    pthread_mutex_t mu;
    pthread_cond_t done;
    int fd, notify_read, notify_write;
    long long length;
    _Atomic int complete, error;
} FilesPrepare;
static FilesPrepare files_prepares[FILES_MAX_PREPARES];
static FilesPrepare *files_prepare(long long handle) {
    /* Even handles are prepare jobs; odd handles remain syncers. Cross-kind handles are invalid. */
    if (handle <= 0 || (handle & 1)) return NULL;
    uint64_t identity = (uint64_t)handle / 2 - 1;
    FilesPrepare *p = &files_prepares[identity % FILES_MAX_PREPARES];
    return p->used && p->generation == identity / FILES_MAX_PREPARES ? p : NULL;
}
static void *files_prepare_main(void *argument) {
    FilesPrepare *p = argument;
    int error = (int)minyar_files_preallocate(p->fd, p->length);
    if (!error) error = (int)minyar_files_truncate(p->fd, p->length);
    unsigned char zeros[65536] = {0};
    long long at = 0;
    while (!error && at < p->length) {
        size_t count = (size_t)(p->length-at);
        if (count > sizeof(zeros)) count = sizeof(zeros);
        ssize_t n = pwrite(p->fd, zeros, count, (off_t)at);
        if (n < 0) { if (errno == EINTR) continue; error = -errno; }
        else if (!n) error = -EIO;
        else at += n;
    }
    if (!error) {
        int rc;
        do { rc = files_datasync(p->fd); } while (rc != 0 && errno == EINTR);
        if (rc) error = -errno;
    }
    pthread_mutex_lock(&p->mu);
    atomic_store(&p->error, error);
    atomic_store_explicit(&p->complete, 1, memory_order_release);
    /* Publish readiness before releasing waiters, so a successful Wait can immediately drain it. */
    char byte = 1; ssize_t n;
    do { n = write(p->notify_write, &byte, 1); } while (n < 0 && errno == EINTR);
    pthread_cond_broadcast(&p->done);
    pthread_mutex_unlock(&p->mu);
    return NULL;
}
long long minyar_files_prepareStart(long long fd, long long length) {
    if (!files_valid_fd(fd)) return -EBADF;
    if (length < 0) return -EINVAL;
    if ((long long)(off_t)length != length) return -EOVERFLOW;
    /* Check append mode before duplicating; positioned writes must honor their position on every platform. */
    int flags = fcntl((int)fd, F_GETFL);
    if (flags < 0) return -errno;
    if ((flags & O_ACCMODE) == O_RDONLY) return -EBADF;
    if (flags & O_APPEND) return -EINVAL;
    int slot = -1;
    for (int i=0; i<FILES_MAX_PREPARES; i++)
        if (!files_prepares[i].used && files_prepares[i].generation <
            ((uint64_t)LLONG_MAX / 2 - FILES_MAX_PREPARES) / FILES_MAX_PREPARES) { slot=i; break; }
    if (slot < 0) return -EMFILE;
    int dupfd = fcntl((int)fd, F_DUPFD_CLOEXEC, 0);
    if (dupfd < 0) return -errno;
    int sv[2];
    if (socketpair(AF_UNIX, SOCK_STREAM, 0, sv) != 0) { int e=errno; close(dupfd); return -e; }
    int error = files_cloexec_nonblock(sv[0], true);
    if (!error) error = files_cloexec_nonblock(sv[1], true);
    FilesPrepare *p = &files_prepares[slot];
    uint64_t generation = p->generation;
    if (error) goto fail_descriptors;
    memset(p, 0, sizeof(*p)); p->generation=generation;
    p->fd=dupfd; p->length=length; p->notify_read=sv[0]; p->notify_write=sv[1];
    atomic_init(&p->complete, 0); atomic_init(&p->error, 0);
    error = -pthread_mutex_init(&p->mu, NULL);
    if (error) goto fail_descriptors;
    error = -pthread_cond_init(&p->done, NULL);
    if (error) goto fail_mutex;
    error = -pthread_create(&p->thread, NULL, files_prepare_main, p);
    if (error) goto fail_condition;
    p->generation=generation+1; p->used=true;
    return ((long long)p->generation * FILES_MAX_PREPARES + slot + 1) * 2;
fail_condition:
    pthread_cond_destroy(&p->done);
fail_mutex:
    pthread_mutex_destroy(&p->mu);
fail_descriptors:
    close(dupfd); close(sv[0]); close(sv[1]); return error;
}
long long minyar_files_prepareNotifySocket(long long handle) {
    FilesPrepare *p=files_prepare(handle); return p ? p->notify_read : -EBADF;
}
long long minyar_files_prepareDone(long long handle) {
    FilesPrepare *p=files_prepare(handle);
    return p ? atomic_load_explicit(&p->complete, memory_order_acquire) : -EBADF;
}
long long minyar_files_prepareError(long long handle) {
    FilesPrepare *p=files_prepare(handle); return p ? atomic_load(&p->error) : -EBADF;
}
long long minyar_files_prepareDrain(long long handle) {
    FilesPrepare *p=files_prepare(handle); if (!p) return -EBADF;
    char buffer[256]; long long total=0;
    for (;;) {
        ssize_t n=read(p->notify_read, buffer, sizeof(buffer));
        if (n>0) total+=n;
        else if (n<0 && errno==EINTR) continue;
        else if (n<0 && errno!=EAGAIN && errno!=EWOULDBLOCK) return -errno;
        else return total;
    }
}
long long minyar_files_prepareWait(long long handle, long long timeoutMs) {
    FilesPrepare *p=files_prepare(handle); if (!p) return -EBADF;
    if (timeoutMs < -1) return -EINVAL;
    struct timespec deadline; clock_gettime(CLOCK_REALTIME, &deadline);
    if (timeoutMs>=0) {
        deadline.tv_sec+=timeoutMs/1000; deadline.tv_nsec+=(timeoutMs%1000)*1000000L;
        if (deadline.tv_nsec>=1000000000L) { deadline.tv_sec++; deadline.tv_nsec-=1000000000L; }
    }
    int error=0; pthread_mutex_lock(&p->mu);
    while (!atomic_load_explicit(&p->complete, memory_order_acquire)) {
        int rc=timeoutMs<0 ? pthread_cond_wait(&p->done,&p->mu)
                          : pthread_cond_timedwait(&p->done,&p->mu,&deadline);
        if (rc) { error=-rc; break; }
    }
    if (!error) error=atomic_load(&p->error);
    pthread_mutex_unlock(&p->mu); return error ? error : 1;
}
long long minyar_files_prepareStop(long long handle) {
    FilesPrepare *p=files_prepare(handle); if (!p) return -EBADF;
    pthread_join(p->thread,NULL);
    int error=atomic_load(&p->error);
    close(p->fd); close(p->notify_read); close(p->notify_write);
    pthread_cond_destroy(&p->done); pthread_mutex_destroy(&p->mu); p->used=false;
    return error;
}
