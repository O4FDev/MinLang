/* Bounded, caller-thread-owned completion I/O. No managed pointer enters a SQE.
 * The only backend is Linux io_uring; there is deliberately no fallback. */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE 1
#endif
#include "../minyar_native.h"
#include <errno.h>
#include <limits.h>
#include <stdint.h>

#if defined(__linux__) && !defined(COMPLETIONIO_FORCE_UNSUPPORTED)
#if __has_include(<linux/io_uring.h>)
#include <linux/io_uring.h>
#include <sys/syscall.h>
#if defined(IORING_SETUP_R_DISABLED) && defined(__NR_io_uring_setup) && defined(__NR_io_uring_enter) && defined(__NR_io_uring_register)
#define COMPLETIONIO_HAS_URING 1
#endif
#endif
#endif

/* Native result packet: status, id, token, kind, result (little-endian i64),
 * followed by read data. Allocated and copied only on the calling thread. */
static void cio_i64(unsigned char *out, long long value) {
    uint64_t bits = (uint64_t)value;
    for (unsigned i = 0; i < 8; ++i) out[i] = (unsigned char)(bits >> (8 * i));
}
static MinyarBytes *cio_result(long long status, long long id, long long token,
                               long long kind, long long result,
                               const void *data, size_t length) {
    MinyarBytes *out = minyar_bytes_new(40 + (long long)length);
    unsigned char *bytes = (unsigned char *)out->bytes;
    cio_i64(bytes, status); cio_i64(bytes + 8, id); cio_i64(bytes + 16, token);
    cio_i64(bytes + 24, kind); cio_i64(bytes + 32, result);
    if (length) memcpy(bytes + 40, data, length);
    return out;
}

#ifdef COMPLETIONIO_HAS_URING
#include <fcntl.h>
#include <stdatomic.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

/* Overrides are used only by the host control test, which includes this file.
 * They replace the kernel boundary, never the queue implementation. */
#ifndef CIO_SETUP
#define CIO_SETUP(n, p) syscall(__NR_io_uring_setup, (n), (p))
#endif
#ifndef CIO_REGISTER
#define CIO_REGISTER(fd, op, arg, n) syscall(__NR_io_uring_register, (fd), (op), (arg), (n))
#endif
#ifndef CIO_ENTER
#define CIO_ENTER(fd, n, minimum, flags) syscall(__NR_io_uring_enter, (fd), (n), (minimum), (flags), NULL, 0)
#endif
#ifndef CIO_MAP
#define CIO_MAP(length, fd, offset) mmap(NULL, (length), PROT_READ | PROT_WRITE, MAP_SHARED, (fd), (offset))
#endif
#ifndef CIO_UNMAP
#define CIO_UNMAP(address, length) munmap((address), (length))
#endif

enum { CIO_MAX_QUEUES = 64, CIO_MAX_ENTRIES = 1024, CIO_MAX_BYTES = 64 * 1024 * 1024 };
enum { CIO_READ = 1, CIO_WRITE = 2, CIO_SYNC = 3 };
typedef struct {
    uint64_t id;
    long long token;
    unsigned char *buffer;
    uint32_t length;
    int fd, kind;
} CioOperation;
typedef struct {
    long long handle;
    uint64_t next_id;
    int fd;
    uint32_t capacity, pending, sq_entries, cq_entries;
    size_t budget, buffered;
    void *sq_map, *cq_map, *sqes_map;
    size_t sq_size, cq_size, sqes_size;
    uint32_t *sq_head, *sq_tail, *sq_array, *sq_dropped;
    uint32_t *cq_head, *cq_tail, *cq_overflow;
    struct io_uring_sqe *sqes;
    struct io_uring_cqe *cqes;
    CioOperation *operations;
} CioQueue;

/* Thread affinity also avoids races between collect/close and managed copying.
 * A process-wide monotone handle prevents a closed/foreign handle aliasing a new
 * queue, even on a different thread. Explicit close is required before exit. */
static _Thread_local CioQueue *cio_queues[CIO_MAX_QUEUES];
static _Atomic uint64_t cio_next_handle = 1;
static CioQueue *cio_queue(long long handle) {
    if (handle <= 0) return NULL;
    for (unsigned i = 0; i < CIO_MAX_QUEUES; ++i)
        if (cio_queues[i] && cio_queues[i]->handle == handle) return cio_queues[i];
    return NULL;
}
static uint32_t cio_acquire(const uint32_t *word) { return __atomic_load_n(word, __ATOMIC_ACQUIRE); }
static void cio_release(uint32_t *word, uint32_t value) { __atomic_store_n(word, value, __ATOMIC_RELEASE); }
static bool cio_power_two(uint32_t n) { return n && !(n & (n - 1)); }
static bool cio_word(uint32_t offset, size_t size) { return !(offset & 3) && (uint64_t)offset + 4 <= size; }
static void cio_destroy(CioQueue *q) {
    /* Only used before publishing a handle, or with zero outstanding owners. */
    if (q->sqes_map != MAP_FAILED) CIO_UNMAP(q->sqes_map, q->sqes_size);
    if (q->cq_map != MAP_FAILED && q->cq_map != q->sq_map) CIO_UNMAP(q->cq_map, q->cq_size);
    if (q->sq_map != MAP_FAILED) CIO_UNMAP(q->sq_map, q->sq_size);
    if (q->fd >= 0) close(q->fd); /* never retry close on EINTR */
    free(q->operations);
    free(q);
}
static int cio_health(CioQueue *q) {
    if (cio_acquire(q->sq_dropped) || cio_acquire(q->cq_overflow)) return -EOVERFLOW;
    uint32_t staged = cio_acquire(q->sq_tail) - cio_acquire(q->sq_head);
    uint32_t ready = cio_acquire(q->cq_tail) - cio_acquire(q->cq_head);
    if (staged > q->pending || staged > q->sq_entries || ready > q->pending || ready > q->cq_entries)
        return -EIO;
    return 0;
}

long long minyar_completionio_open(long long capacity, long long maximumBytes) {
    if (capacity < 1 || capacity > CIO_MAX_ENTRIES || maximumBytes < 0 || maximumBytes > CIO_MAX_BYTES)
        return -EINVAL;
    unsigned slot = 0;
    while (slot < CIO_MAX_QUEUES && cio_queues[slot]) ++slot;
    if (slot == CIO_MAX_QUEUES) return -EMFILE;
    CioQueue *q = calloc(1, sizeof(*q));
    if (!q) return -ENOMEM;
    q->fd = -1;
    q->sq_map = q->cq_map = q->sqes_map = MAP_FAILED;
    q->capacity = (uint32_t)capacity; q->budget = (size_t)maximumBytes; q->next_id = 1;
    q->operations = calloc(q->capacity, sizeof(*q->operations));
    int error = -ENOMEM;
    if (!q->operations) goto failed;
    struct io_uring_params p = {0};
    p.flags = IORING_SETUP_R_DISABLED;
    q->fd = (int)CIO_SETUP(q->capacity, &p);
    if (q->fd < 0) { error = -errno; goto failed; }
    if (fcntl(q->fd, F_SETFD, FD_CLOEXEC) < 0) { error = -errno; goto failed; }
    if (!cio_power_two(p.sq_entries) || p.sq_entries < q->capacity || p.sq_entries > CIO_MAX_ENTRIES ||
        !cio_power_two(p.cq_entries) || p.cq_entries < q->capacity || p.cq_entries > 65536) {
        error = -EIO; goto failed;
    }
    q->sq_entries = p.sq_entries; q->cq_entries = p.cq_entries;
    q->sq_size = (size_t)p.sq_off.array + p.sq_entries * sizeof(uint32_t);
    q->cq_size = (size_t)p.cq_off.cqes + p.cq_entries * sizeof(struct io_uring_cqe);
    q->sqes_size = p.sq_entries * sizeof(struct io_uring_sqe);
    if (q->sq_size > 16 * 1024 * 1024 || q->cq_size > 16 * 1024 * 1024 ||
        !cio_word(p.sq_off.head, q->sq_size) || !cio_word(p.sq_off.tail, q->sq_size) ||
        !cio_word(p.sq_off.ring_mask, q->sq_size) || !cio_word(p.sq_off.ring_entries, q->sq_size) ||
        !cio_word(p.sq_off.dropped, q->sq_size) || (p.sq_off.array & 3) ||
        !cio_word(p.cq_off.head, q->cq_size) || !cio_word(p.cq_off.tail, q->cq_size) ||
        !cio_word(p.cq_off.ring_mask, q->cq_size) || !cio_word(p.cq_off.ring_entries, q->cq_size) ||
        !cio_word(p.cq_off.overflow, q->cq_size) || (p.cq_off.cqes & 7)) {
        error = -EIO; goto failed;
    }
    if (p.features & IORING_FEAT_SINGLE_MMAP) {
        if (q->cq_size > q->sq_size) q->sq_size = q->cq_size;
        q->sq_map = CIO_MAP(q->sq_size, q->fd, IORING_OFF_SQ_RING);
        q->cq_map = q->sq_map;
    } else {
        q->sq_map = CIO_MAP(q->sq_size, q->fd, IORING_OFF_SQ_RING);
        if (q->sq_map == MAP_FAILED) { error = -errno; goto failed; }
        q->cq_map = CIO_MAP(q->cq_size, q->fd, IORING_OFF_CQ_RING);
    }
    if (q->sq_map == MAP_FAILED || q->cq_map == MAP_FAILED) { error = -errno; goto failed; }
    q->sqes_map = CIO_MAP(q->sqes_size, q->fd, IORING_OFF_SQES);
    if (q->sqes_map == MAP_FAILED) { error = -errno; goto failed; }
    unsigned char *sq = q->sq_map, *cq = q->cq_map;
    if (cio_acquire((uint32_t *)(sq + p.sq_off.ring_entries)) != p.sq_entries ||
        cio_acquire((uint32_t *)(sq + p.sq_off.ring_mask)) != p.sq_entries - 1 ||
        cio_acquire((uint32_t *)(cq + p.cq_off.ring_entries)) != p.cq_entries ||
        cio_acquire((uint32_t *)(cq + p.cq_off.ring_mask)) != p.cq_entries - 1) {
        error = -EIO; goto failed;
    }
    q->sq_head = (uint32_t *)(sq + p.sq_off.head); q->sq_tail = (uint32_t *)(sq + p.sq_off.tail);
    q->sq_array = (uint32_t *)(sq + p.sq_off.array); q->sq_dropped = (uint32_t *)(sq + p.sq_off.dropped);
    q->cq_head = (uint32_t *)(cq + p.cq_off.head); q->cq_tail = (uint32_t *)(cq + p.cq_off.tail);
    q->cq_overflow = (uint32_t *)(cq + p.cq_off.overflow);
    q->sqes = q->sqes_map; q->cqes = (struct io_uring_cqe *)(cq + p.cq_off.cqes);
    /* Flags are an allowlist too. Omitting this IO_DRAIN entry is the real
     * neo-vm failure that made every restricted-ring flush complete EACCES. */
    struct io_uring_restriction restrictions[4] = {0};
    const unsigned char ops[3] = {IORING_OP_READ, IORING_OP_WRITE, IORING_OP_FSYNC};
    for (unsigned i = 0; i < 3; ++i) {
        restrictions[i].opcode = IORING_RESTRICTION_SQE_OP;
        restrictions[i].sqe_op = ops[i];
    }
    restrictions[3].opcode = IORING_RESTRICTION_SQE_FLAGS_ALLOWED;
    restrictions[3].sqe_flags = IOSQE_IO_DRAIN;
    if (CIO_REGISTER(q->fd, IORING_REGISTER_RESTRICTIONS, restrictions, 4) < 0 ||
        CIO_REGISTER(q->fd, IORING_REGISTER_ENABLE_RINGS, NULL, 0) < 0) {
        error = -errno; goto failed;
    }
    uint64_t handle = atomic_load_explicit(&cio_next_handle, memory_order_relaxed);
    do {
        if (handle > LLONG_MAX) { error = -EOVERFLOW; goto failed; }
    } while (!atomic_compare_exchange_weak_explicit(&cio_next_handle, &handle, handle + 1,
                                                    memory_order_relaxed, memory_order_relaxed));
    q->handle = (long long)handle;
    cio_queues[slot] = q;
    return q->handle;
failed:
    cio_destroy(q);
    return error;
}

static long long cio_enqueue(long long handle, long long fd, long long offset,
                             long long length, const unsigned char *input,
                             long long token, int kind) {
    CioQueue *q = cio_queue(handle);
    if (!q) return -EBADF;
    int error = cio_health(q);
    if (error) return error;
    if (fd < 0 || fd > INT_MAX) return -EBADF;
    if (offset < 0 || length < 0 || length > CIO_MAX_BYTES || offset > LLONG_MAX - length)
        return -EINVAL;
    if (q->pending == q->capacity || (size_t)length > q->budget - q->buffered) return -EAGAIN;
    if (q->next_id > LLONG_MAX) return -EOVERFLOW;
    uint32_t tail = cio_acquire(q->sq_tail), head = cio_acquire(q->sq_head);
    if ((uint32_t)(tail - head) >= q->sq_entries) return -EAGAIN;
    unsigned slot = 0;
    while (slot < q->capacity && q->operations[slot].id) ++slot;
    if (slot == q->capacity) return -EIO;
    int owned = fcntl((int)fd, F_DUPFD_CLOEXEC, 0);
    if (owned < 0) return -errno;
    struct stat st;
    if (fstat(owned, &st) < 0) { error = -errno; close(owned); return error; }
    if (!S_ISREG(st.st_mode)) { close(owned); return -ENOTSUP; }
    int flags = fcntl(owned, F_GETFL);
    if (flags < 0) { error = -errno; close(owned); return error; }
    if ((kind != CIO_SYNC && (flags & O_DIRECT)) || (kind == CIO_WRITE && (flags & O_APPEND))) {
        close(owned); return -ENOTSUP;
    }
    unsigned char *buffer = length ? malloc((size_t)length) : NULL;
    if (length && !buffer) { close(owned); return -ENOMEM; }
    if (input && length) memcpy(buffer, input, (size_t)length);
    CioOperation *op = &q->operations[slot];
    *op = (CioOperation){q->next_id++, token, buffer, (uint32_t)length, owned, kind};
    uint32_t index = tail & (q->sq_entries - 1);
    struct io_uring_sqe *sqe = &q->sqes[index];
    memset(sqe, 0, sizeof(*sqe));
    sqe->opcode = kind == CIO_READ ? IORING_OP_READ : kind == CIO_WRITE ? IORING_OP_WRITE : IORING_OP_FSYNC;
    sqe->flags = kind == CIO_SYNC ? IOSQE_IO_DRAIN : 0;
    sqe->fd = owned; sqe->off = (uint64_t)offset;
    sqe->addr = (uint64_t)(uintptr_t)buffer; sqe->len = (uint32_t)length; sqe->user_data = op->id;
    q->sq_array[index] = index;
    q->pending++; q->buffered += (size_t)length;
    cio_release(q->sq_tail, tail + 1); /* publish SQE, array, and C owner first */
    return (long long)op->id;
}
long long minyar_completionio_queueRead(long long queue, long long fd, long long offset, long long length, long long token) {
    return cio_enqueue(queue, fd, offset, length, NULL, token, CIO_READ);
}
long long minyar_completionio_queueWrite(long long queue, long long fd, long long offset, const MinyarBytes *data, long long token) {
    if (!data || data->byte_length < 0 || (data->byte_length && !data->bytes)) return -EINVAL;
    return cio_enqueue(queue, fd, offset, data->byte_length, data->bytes, token, CIO_WRITE);
}
long long minyar_completionio_queueSync(long long queue, long long fd, long long token) {
    return cio_enqueue(queue, fd, 0, 0, NULL, token, CIO_SYNC);
}
long long minyar_completionio_pending(long long handle) {
    CioQueue *q = cio_queue(handle);
    return q ? (long long)q->pending : -EBADF;
}
long long minyar_completionio_staged(long long handle) {
    CioQueue *q = cio_queue(handle);
    if (!q) return -EBADF;
    int error = cio_health(q);
    return error ? error : (long long)(uint32_t)(cio_acquire(q->sq_tail) - cio_acquire(q->sq_head));
}
long long minyar_completionio_submit(long long handle) {
    CioQueue *q = cio_queue(handle);
    if (!q) return -EBADF;
    long long n = minyar_completionio_staged(handle);
    if (n <= 0) return n;
    /* Shared head is the source of truth, even on partial success or EINTR.
     * Never reset the tail, replay an SQE, or release an owner here. */
    long result = CIO_ENTER(q->fd, (unsigned)n, 0, 0);
    return result < 0 ? -errno : result;
}
MinyarBytes *minyar_completionio_collectNative(long long handle, bool wait) {
    CioQueue *q = cio_queue(handle);
    if (!q) return cio_result(-EBADF, 0, 0, 0, 0, NULL, 0);
    int error = cio_health(q);
    if (error) return cio_result(error, 0, 0, 0, 0, NULL, 0);
    uint32_t head = cio_acquire(q->cq_head);
    if (head == cio_acquire(q->cq_tail) && q->pending) {
        uint32_t staged = cio_acquire(q->sq_tail) - cio_acquire(q->sq_head);
        /* Waiting cannot make an entirely unsubmitted queue progress. */
        if (staged == q->pending) return cio_result(wait ? -EAGAIN : 0, 0, 0, 0, 0, NULL, 0);
        if (CIO_ENTER(q->fd, 0, wait ? 1 : 0, IORING_ENTER_GETEVENTS) < 0)
            return cio_result(-errno, 0, 0, 0, 0, NULL, 0);
        error = cio_health(q);
        if (error) return cio_result(error, 0, 0, 0, 0, NULL, 0);
    }
    if (head == cio_acquire(q->cq_tail)) return cio_result(0, 0, 0, 0, 0, NULL, 0);
    struct io_uring_cqe cqe = q->cqes[head & (q->cq_entries - 1)];
    CioOperation *op = NULL;
    for (unsigned i = 0; i < q->capacity; ++i)
        if (q->operations[i].id == cqe.user_data && cqe.user_data) { op = &q->operations[i]; break; }
    if (!op || cqe.flags || (cqe.res > 0 && ((uint32_t)cqe.res > op->length || op->kind == CIO_SYNC)))
        return cio_result(-EIO, 0, 0, 0, 0, NULL, 0); /* retain owners on broken invariants */
    size_t length = op->kind == CIO_READ && cqe.res > 0 ? (size_t)cqe.res : 0;
    MinyarBytes *out = cio_result(1, (long long)op->id, op->token, op->kind, cqe.res, op->buffer, length);
    cio_release(q->cq_head, head + 1); /* read kernel data before returning CQ space */
    q->buffered -= op->length; q->pending--;
    close(op->fd);
    free(op->buffer);
    memset(op, 0, sizeof(*op));
    return out;
}
long long minyar_completionio_close(long long handle) {
    CioQueue *q = cio_queue(handle);
    if (!q) return -EBADF;
    if (q->pending) return -EBUSY;
    for (unsigned i = 0; i < CIO_MAX_QUEUES; ++i) if (cio_queues[i] == q) cio_queues[i] = NULL;
    cio_destroy(q);
    return 0;
}
#else
/* Buildable on other hosts and with old/missing Linux headers. No fake queue. */
long long minyar_completionio_open(long long capacity, long long maximumBytes) {
    (void)capacity; (void)maximumBytes; return -ENOTSUP;
}
long long minyar_completionio_queueRead(long long queue, long long fd, long long offset, long long length, long long token) {
    (void)queue; (void)fd; (void)offset; (void)length; (void)token; return -ENOTSUP;
}
long long minyar_completionio_queueWrite(long long queue, long long fd, long long offset, const MinyarBytes *data, long long token) {
    (void)queue; (void)fd; (void)offset; (void)data; (void)token; return -ENOTSUP;
}
long long minyar_completionio_queueSync(long long queue, long long fd, long long token) {
    (void)queue; (void)fd; (void)token; return -ENOTSUP;
}
long long minyar_completionio_pending(long long queue) { (void)queue; return -ENOTSUP; }
long long minyar_completionio_staged(long long queue) { (void)queue; return -ENOTSUP; }
long long minyar_completionio_submit(long long queue) { (void)queue; return -ENOTSUP; }
long long minyar_completionio_close(long long queue) { (void)queue; return -ENOTSUP; }
MinyarBytes *minyar_completionio_collectNative(long long queue, bool wait) {
    (void)queue; (void)wait; return cio_result(-ENOTSUP, 0, 0, 0, 0, NULL, 0);
}
#endif
