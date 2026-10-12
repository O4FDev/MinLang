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

static void files_cloexec_nonblock(int fd, bool nonblock) {
    fcntl(fd, F_SETFD, FD_CLOEXEC);
    if (nonblock) fcntl(fd, F_SETFL, fcntl(fd, F_GETFL) | O_NONBLOCK);
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
    return files_write_all(fd, data, offset, length, position);
}

long long minyar_files_writeStandardOutput(const MinyarText *text) {
    if (!text) return -EINVAL;
    return files_write_all(1, text, 0, text->byte_length, -1);
}

/* Read up to length bytes at position into fresh Bytes (shorter at end of file). */
MinyarBytes *minyar_files_readAt(long long fd, long long position, long long length) {
    if (!files_valid_fd(fd) || position < 0 || length < 0) return files_empty(-EINVAL);
    MinyarBytes *b = minyar_bytes_new(length);
    unsigned char *p = (unsigned char *)b->bytes;
    long long done = 0;
    while (done < length) {
        size_t chunk = (size_t)(length - done);
        if (chunk > (1u << 30)) chunk = 1u << 30;
        ssize_t n = pread((int)fd, p + done, chunk, (off_t)(position + done));
        if (n < 0) {
            if (errno == EINTR) continue;
            files_last_error = -errno;
            b->byte_length = 0;
            return b;
        }
        if (n == 0) break;
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
    MinyarBytes *b = minyar_files_readAt(fd, 0, (long long)st.st_size);
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
    if (!files_valid_fd(fd) || length < 0) return -EINVAL;
    return ftruncate((int)fd, (off_t)length) == 0 ? 0 : -errno;
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

/* Newline-separated entry names (excluding . and ..); the Minyar wrapper splits them. */
MinyarBytes *minyar_files_listNames(const MinyarText *path) {
    char p[PATH_MAX];
    int rc = files_path(path, p);
    if (rc) return files_empty(rc);
    DIR *d = opendir(p);
    if (!d) return files_empty(-errno);
    MinyarBytes *out = minyar_bytes_new(0);
    struct dirent *e;
    while ((e = readdir(d)) != NULL) {
        if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, "..")) continue;
        size_t n = strlen(e->d_name);
        unsigned char *dst = minyar_native_bytes_append(out, (long long)n + 1);
        memcpy(dst, e->d_name, n);
        dst[n] = '\n';
    }
    closedir(d);
    files_last_error = 0;
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

enum { FILES_MAX_SYNCERS = 16, FILES_MAX_PENDING = 64 };

typedef struct {
    int fd;
    long long start;
} FilesPendingSegment;

typedef struct {
    bool used;
    pthread_t thread;
    pthread_mutex_t mu;
    pthread_cond_t wake; /* Minyar thread -> syncer: new request, switch or stop */
    pthread_cond_t done; /* syncer -> syncerWait */
    int fd;
    FilesPendingSegment pending[FILES_MAX_PENDING];
    int npending;
    long long requested; /* protected by mu; only grows */
    _Atomic long long synced;
    _Atomic int error;
    bool stop;
    int notify_read, notify_write;
} FilesSyncer;

static FilesSyncer files_syncers[FILES_MAX_SYNCERS];

static FilesSyncer *files_syncer(long long handle) {
    if (handle < 1 || handle > FILES_MAX_SYNCERS) return NULL;
    FilesSyncer *s = &files_syncers[handle - 1];
    return s->used ? s : NULL;
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
        if (!files_syncers[i].used) {
            slot = i;
            break;
        }
    if (slot < 0) return -EMFILE;
    FilesSyncer *s = &files_syncers[slot];
    memset(s, 0, sizeof(*s));
    int sv[2];
    if (socketpair(AF_UNIX, SOCK_STREAM, 0, sv) != 0) return -errno;
    files_cloexec_nonblock(sv[0], true);
    files_cloexec_nonblock(sv[1], true);
    int dupfd = fcntl((int)fd, F_DUPFD_CLOEXEC, 0);
    if (dupfd < 0) {
        int e = -errno;
        close(sv[0]);
        close(sv[1]);
        return e;
    }
    s->notify_read = sv[0];
    s->notify_write = sv[1];
    s->fd = dupfd;
    atomic_store(&s->synced, 0);
    atomic_store(&s->error, 0);
    pthread_mutex_init(&s->mu, NULL);
    pthread_cond_init(&s->wake, NULL);
    pthread_cond_init(&s->done, NULL);
    s->used = true;
    int rc = pthread_create(&s->thread, NULL, files_syncer_main, s);
    if (rc != 0) {
        s->used = false;
        close(dupfd);
        close(sv[0]);
        close(sv[1]);
        return -rc;
    }
    return slot + 1;
}

long long minyar_files_syncerNotifySocket(long long handle) {
    FilesSyncer *s = files_syncer(handle);
    return s ? s->notify_read : -EBADF;
}

long long minyar_files_syncerRequest(long long handle, long long upTo) {
    FilesSyncer *s = files_syncer(handle);
    if (!s) return -EBADF;
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
    if (!files_valid_fd(newFd)) return -EBADF;
    int dupfd = fcntl((int)newFd, F_DUPFD_CLOEXEC, 0);
    if (dupfd < 0) return -errno;
    pthread_mutex_lock(&s->mu);
    if (s->npending == FILES_MAX_PENDING) {
        pthread_mutex_unlock(&s->mu);
        close(dupfd);
        return -EBUSY;
    }
    s->pending[s->npending].fd = dupfd;
    s->pending[s->npending].start = startOffset;
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
    s->used = false;
    return err;
}
