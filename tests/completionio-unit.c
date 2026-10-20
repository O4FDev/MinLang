/* Kernel-boundary controls, not kernel proof. Never installed as a provider.
 * COMPLETIONIO_MINYAR_FIXTURE reuses this boundary for O0/O2 managed-ABI tests. */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE 1
#endif
#include "../runtime/minyar_native.h"
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#if defined(__linux__) && !defined(COMPLETIONIO_FORCE_UNSUPPORTED)
#if __has_include(<linux/io_uring.h>)
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/socket.h>
#include <linux/io_uring.h>
#if defined(IORING_SETUP_R_DISABLED)
static long mock_setup(unsigned n, struct io_uring_params *p);
static long mock_register(int fd, unsigned op, const void *arg, unsigned n);
static long mock_enter(int fd, unsigned n, unsigned minimum, unsigned flags);
static void *mock_map(size_t length, int fd, off_t offset);
static int mock_unmap(void *address, size_t length);
#define CIO_SETUP(n, p) mock_setup((n), (p))
#define CIO_REGISTER(fd, op, arg, n) mock_register((fd), (op), (arg), (n))
#define CIO_ENTER(fd, n, minimum, flags) mock_enter((fd), (n), (minimum), (flags))
#define CIO_MAP(length, fd, offset) mock_map((length), (fd), (offset))
#define CIO_UNMAP(address, length) mock_unmap((address), (length))
#endif
#endif
#endif
#include "../runtime/native/completionio.c"

#ifndef COMPLETIONIO_MINYAR_FIXTURE
/* Tiny caller-owned Bytes stand-in. Production ABI fixtures use the real GC. */
MinyarBytes *minyar_bytes_new(long long length) {
    assert(length >= 0);
    MinyarBytes *out = calloc(1, sizeof(*out));
    assert(out);
    out->bytes = calloc(1, length ? (size_t)length : 1);
    assert(out->bytes);
    out->byte_length = out->character_length = length;
    return out;
}
static void release_result(MinyarBytes *out) { free((void *)out->bytes); free(out); }
static long long field(const MinyarBytes *out, unsigned offset) {
    assert(offset + 8 <= (unsigned long long)out->byte_length);
    uint64_t bits = 0;
    for (unsigned i = 0; i < 8; ++i) bits |= (uint64_t)out->bytes[offset + i] << (8 * i);
    long long value;
    memcpy(&value, &bits, 8);
    return value;
}
#endif

#ifdef COMPLETIONIO_HAS_URING
static struct io_uring_params mock_params;
static int mock_setup_error, mock_register_failure, mock_map_failure;
static int mock_register_count, mock_map_count, mock_live_maps, mock_ring_fd;
static int mock_single_map = 1, mock_bad_shape, mock_bad_mask;
static uint32_t mock_initial;
static unsigned mock_limit = UINT_MAX, mock_consumed, mock_enter_count;
static int mock_enter_error, mock_consume_before_error, mock_hold;
static int mock_forced_result, mock_result;
static unsigned char mock_allowed_flags, mock_allowed_ops[256];

static long mock_setup(unsigned n, struct io_uring_params *p) {
    assert(p->flags == IORING_SETUP_R_DISABLED);
    if (mock_setup_error) { errno = mock_setup_error; return -1; }
    unsigned rounded = 1;
    while (rounded < n) rounded *= 2;
    p->sq_entries = rounded; p->cq_entries = rounded * 2;
    if (mock_bad_shape) p->cq_entries = 1;
    p->features = mock_single_map ? IORING_FEAT_SINGLE_MMAP : 0;
    p->sq_off.head = 0; p->sq_off.tail = 4; p->sq_off.ring_mask = 8;
    p->sq_off.ring_entries = 12; p->sq_off.dropped = 16; p->sq_off.array = 64;
    p->cq_off.head = 32; p->cq_off.tail = 36; p->cq_off.ring_mask = 40;
    p->cq_off.ring_entries = 44; p->cq_off.overflow = 48;
    p->cq_off.cqes = (64 + rounded * 4 + 7) & ~7u;
    mock_params = *p;
    mock_register_count = mock_map_count = 0;
    memset(mock_allowed_ops, 0, sizeof(mock_allowed_ops)); mock_allowed_flags = 0;
    mock_ring_fd = open("/dev/null", O_RDONLY | O_CLOEXEC);
    assert(mock_ring_fd >= 0);
    return mock_ring_fd;
}
static void mock_word(void *map, unsigned offset, uint32_t value) { memcpy((unsigned char *)map + offset, &value, 4); }
static void mock_sq(void *map) {
    mock_word(map, mock_params.sq_off.head, mock_initial);
    mock_word(map, mock_params.sq_off.tail, mock_initial);
    mock_word(map, mock_params.sq_off.ring_mask, mock_bad_mask ? 9999 : mock_params.sq_entries - 1);
    mock_word(map, mock_params.sq_off.ring_entries, mock_params.sq_entries);
}
static void mock_cq(void *map) {
    mock_word(map, mock_params.cq_off.head, mock_initial);
    mock_word(map, mock_params.cq_off.tail, mock_initial);
    mock_word(map, mock_params.cq_off.ring_mask, mock_params.cq_entries - 1);
    mock_word(map, mock_params.cq_off.ring_entries, mock_params.cq_entries);
}
static void *mock_map(size_t length, int fd, off_t offset) {
    assert(fd == mock_ring_fd);
    if (++mock_map_count == mock_map_failure) { errno = ENOMEM; return MAP_FAILED; }
    void *map = calloc(1, length);
    assert(map); mock_live_maps++;
    if (offset == IORING_OFF_SQ_RING) { mock_sq(map); if (mock_single_map) mock_cq(map); }
    else if (offset == IORING_OFF_CQ_RING) mock_cq(map);
    else assert(offset == IORING_OFF_SQES);
    return map;
}
static int mock_unmap(void *address, size_t length) {
    (void)length; assert(address != MAP_FAILED); assert(mock_live_maps > 0);
    free(address); mock_live_maps--; return 0;
}
static long mock_register(int fd, unsigned op, const void *arg, unsigned n) {
    assert(fd == mock_ring_fd);
    if (++mock_register_count == mock_register_failure) { errno = EPERM; return -1; }
    if (op == IORING_REGISTER_RESTRICTIONS) {
        assert(mock_register_count == 1 && n == 4);
        const struct io_uring_restriction *r = arg;
        for (unsigned i = 0; i < n; ++i) {
            if (r[i].opcode == IORING_RESTRICTION_SQE_OP) mock_allowed_ops[r[i].sqe_op] = 1;
            else { assert(r[i].opcode == IORING_RESTRICTION_SQE_FLAGS_ALLOWED); mock_allowed_flags = r[i].sqe_flags; }
        }
        assert(mock_allowed_ops[IORING_OP_READ] && mock_allowed_ops[IORING_OP_WRITE] && mock_allowed_ops[IORING_OP_FSYNC]);
        assert(mock_allowed_flags == IOSQE_IO_DRAIN);
    } else {
        assert(op == IORING_REGISTER_ENABLE_RINGS && mock_register_count == 2 && !arg && !n);
    }
    return 0;
}
static CioQueue *mock_queue_fd(int fd) {
    for (unsigned i = 0; i < CIO_MAX_QUEUES; ++i) if (cio_queues[i] && cio_queues[i]->fd == fd) return cio_queues[i];
    assert(0); return NULL;
}
static void mock_complete(CioQueue *q, uint64_t id, int result) {
    uint32_t tail = cio_acquire(q->cq_tail);
    assert((uint32_t)(tail - cio_acquire(q->cq_head)) < q->cq_entries);
    q->cqes[tail & (q->cq_entries - 1)] = (struct io_uring_cqe){.user_data = id, .res = result};
    cio_release(q->cq_tail, tail + 1);
}
static int mock_execute(const struct io_uring_sqe *sqe) {
    if (!mock_allowed_ops[sqe->opcode] || (sqe->flags & ~mock_allowed_flags)) return -EACCES;
    if (mock_forced_result) return mock_result;
    /* Deliberately synchronous TEST boundary. Production has only io_uring. */
    ssize_t n;
    if (sqe->opcode == IORING_OP_READ) n = pread(sqe->fd, (void *)(uintptr_t)sqe->addr, sqe->len, (off_t)sqe->off);
    else if (sqe->opcode == IORING_OP_WRITE) n = pwrite(sqe->fd, (void *)(uintptr_t)sqe->addr, sqe->len, (off_t)sqe->off);
    else { assert(sqe->opcode == IORING_OP_FSYNC && sqe->flags == IOSQE_IO_DRAIN); n = fsync(sqe->fd); }
    return n < 0 ? -errno : (int)n;
}
static long mock_enter(int fd, unsigned n, unsigned minimum, unsigned flags) {
    CioQueue *q = mock_queue_fd(fd);
    mock_enter_count++;
    assert((!flags && !minimum) || (flags == IORING_ENTER_GETEVENTS && !n && minimum <= 1));
    uint32_t head = cio_acquire(q->sq_head), tail = cio_acquire(q->sq_tail);
    assert(n <= (uint32_t)(tail - head));
    unsigned consume = n < mock_limit ? n : mock_limit;
    if (mock_enter_error) consume = mock_consume_before_error && n ? 1 : 0;
    for (unsigned i = 0; i < consume; ++i) {
        unsigned index = q->sq_array[head & (q->sq_entries - 1)];
        assert(index < q->sq_entries);
        struct io_uring_sqe sqe = q->sqes[index];
        int result = mock_hold ? 0 : mock_execute(&sqe);
        cio_release(q->sq_head, ++head);
        if (!mock_hold) mock_complete(q, sqe.user_data, result);
        mock_consumed++;
    }
    if (mock_enter_error) { errno = mock_enter_error; return -1; }
    return consume;
}

#ifndef COMPLETIONIO_MINYAR_FIXTURE
#include <pthread.h>
static int temporary_file(void) {
    char name[] = "/tmp/minyar-completionio-control-XXXXXX";
    int fd = mkstemp(name); assert(fd >= 0); assert(unlink(name) == 0); return fd;
}
static void check_completion(long long queue, long long id, long long token, int kind, int result, const char *data, size_t length) {
    MinyarBytes *out = minyar_completionio_collectNative(queue, true);
    assert(field(out, 0) == 1 && field(out, 8) == id && field(out, 16) == token);
    assert(field(out, 24) == kind && field(out, 32) == result);
    assert(out->byte_length == (long long)(40 + length));
    if (length) assert(memcmp(out->bytes + 40, data, length) == 0);
    release_result(out);
}
static void controls_setup(void) {
    assert(minyar_completionio_open(0, 1) == -EINVAL);
    assert(minyar_completionio_open(1025, 1) == -EINVAL);
    assert(minyar_completionio_open(1, -1) == -EINVAL);
    assert(minyar_completionio_open(1, CIO_MAX_BYTES + 1LL) == -EINVAL);
    for (int i = 0; i < 2; ++i) {
        mock_setup_error = i ? EPERM : ENOSYS;
        assert(minyar_completionio_open(2, 10) == -mock_setup_error);
        assert(!mock_live_maps);
    }
    mock_setup_error = 0;
    for (int single = 0; single < 2; ++single) {
        mock_single_map = single;
        for (int step = 1; step <= (single ? 2 : 3); ++step) {
            mock_map_failure = step;
            assert(minyar_completionio_open(2, 10) == -ENOMEM);
            assert(!mock_live_maps && fcntl(mock_ring_fd, F_GETFD) == -1 && errno == EBADF);
        }
        mock_map_failure = 0;
        for (int step = 1; step <= 2; ++step) {
            mock_register_failure = step;
            assert(minyar_completionio_open(2, 10) == -EPERM);
            assert(!mock_live_maps && fcntl(mock_ring_fd, F_GETFD) == -1 && errno == EBADF);
        }
        mock_register_failure = 0;
        long long queue = minyar_completionio_open(2, 10);
        assert(queue > 0 && minyar_completionio_close(queue) == 0 && !mock_live_maps);
    }
    mock_bad_shape = 1;
    assert(minyar_completionio_open(3, 10) == -EIO); mock_bad_shape = 0;
    mock_bad_mask = 1;
    assert(minyar_completionio_open(3, 10) == -EIO); mock_bad_mask = 0;
    assert(!mock_live_maps);
}
static void controls_ownership(void) {
    long long queue = minyar_completionio_open(3, 6);
    assert(queue > 0);
    int fd = temporary_file(), verify = dup(fd);
    unsigned char input[] = "abc";
    MinyarBytes bytes = {input, 3, 3, NULL, NULL};
    long long first = minyar_completionio_queueWrite(queue, fd, 0, &bytes, -99);
    assert(first > 0);
    CioQueue *q = cio_queue(queue);
    assert(q->operations[0].buffer != input && q->sqes[0].addr != (uint64_t)(uintptr_t)input);
    int owned = q->operations[0].fd;
    memcpy(input, "def", 3);
    long long second = minyar_completionio_queueWrite(queue, fd, 3, &bytes, 22);
    long long sync = minyar_completionio_queueSync(queue, fd, 33);
    assert(second > first && sync > second && close(fd) == 0);
    int reused = temporary_file(); /* Reusing the caller fd must not redirect I/O. */
    assert(minyar_completionio_close(queue) == -EBUSY);
    assert(minyar_completionio_queueRead(queue, verify, 0, 1, 0) == -EAGAIN);
    MinyarBytes *none = minyar_completionio_collectNative(queue, false);
    assert(field(none, 0) == 0); release_result(none);
    none = minyar_completionio_collectNative(queue, true);
    assert(field(none, 0) == -EAGAIN); release_result(none);
    mock_limit = 1;
    assert(minyar_completionio_submit(queue) == 1 && minyar_completionio_staged(queue) == 2);
    assert(fcntl(owned, F_GETFD) >= 0); /* completion posted, still not observed */
    assert(minyar_completionio_close(queue) == -EBUSY);
    assert(minyar_completionio_queueSync(queue, verify, 0) == -EAGAIN);
    check_completion(queue, first, -99, CIO_WRITE, 3, NULL, 0);
    assert(fcntl(owned, F_GETFD) == -1 && errno == EBADF);
    mock_limit = UINT_MAX;
    assert(minyar_completionio_submit(queue) == 2 && minyar_completionio_staged(queue) == 0);
    check_completion(queue, second, 22, CIO_WRITE, 3, NULL, 0);
    check_completion(queue, sync, 33, CIO_SYNC, 0, NULL, 0);
    char actual[6]; assert(pread(verify, actual, sizeof(actual), 0) == 6 && !memcmp(actual, "abcdef", 6));
    struct stat empty; assert(fstat(reused, &empty) == 0 && empty.st_size == 0 && close(reused) == 0);
    long long read_id = minyar_completionio_queueRead(queue, verify, 0, 6, 44);
    assert(read_id > sync && minyar_completionio_queueRead(queue, verify, 0, 1, 0) == -EAGAIN);
    assert(minyar_completionio_submit(queue) == 1);
    check_completion(queue, read_id, 44, CIO_READ, 6, "abcdef", 6);
    read_id = minyar_completionio_queueRead(queue, verify, 99, 6, 55);
    assert(minyar_completionio_submit(queue) == 1);
    check_completion(queue, read_id, 55, CIO_READ, 0, NULL, 0);
    assert(minyar_completionio_pending(queue) == 0 && minyar_completionio_close(queue) == 0);
    assert(minyar_completionio_close(queue) == -EBADF && minyar_completionio_submit(queue) == -EBADF);
    long long replacement = minyar_completionio_open(1, 0);
    assert(replacement > queue && minyar_completionio_pending(queue) == -EBADF);
    assert(minyar_completionio_close(replacement) == 0 && close(verify) == 0 && !mock_live_maps);
}
static void controls_interrupt_wrap_order(void) {
    mock_initial = UINT32_MAX - 1;
    long long queue = minyar_completionio_open(3, 12);
    CioQueue *q = cio_queue(queue); int fd = temporary_file();
    long long a = minyar_completionio_queueRead(queue, fd, 0, 4, 1);
    long long b = minyar_completionio_queueRead(queue, fd, 0, 4, 2);
    long long c = minyar_completionio_queueSync(queue, fd, 3);
    assert(cio_acquire(q->sq_tail) == 1 && minyar_completionio_staged(queue) == 3);
    unsigned before = mock_consumed;
    mock_enter_error = EINTR; mock_consume_before_error = 1;
    assert(minyar_completionio_submit(queue) == -EINTR && minyar_completionio_staged(queue) == 2);
    assert(q->pending == 3 && q->buffered == 8 && minyar_completionio_close(queue) == -EBUSY);
    check_completion(queue, a, 1, CIO_READ, 0, NULL, 0);
    mock_enter_error = EIO; mock_consume_before_error = 0;
    assert(minyar_completionio_submit(queue) == -EIO && minyar_completionio_staged(queue) == 2);
    mock_enter_error = 0; mock_hold = 1;
    assert(minyar_completionio_submit(queue) == 2 && mock_consumed == before + 3);
    assert(cio_acquire(q->sq_head) == 1 && minyar_completionio_staged(queue) == 0);
    unsigned calls = mock_enter_count;
    mock_enter_error = EINTR;
    MinyarBytes *interrupted = minyar_completionio_collectNative(queue, true);
    assert(field(interrupted, 0) == -EINTR && mock_enter_count == calls + 1 && q->pending == 2);
    release_result(interrupted); mock_enter_error = 0;
    memcpy(q->operations[1].buffer, "ok!", 3);
    mock_complete(q, (uint64_t)c, -ENOSPC);
    mock_complete(q, (uint64_t)b, 3);
    check_completion(queue, c, 3, CIO_SYNC, -ENOSPC, NULL, 0);
    check_completion(queue, b, 2, CIO_READ, 3, "ok!", 3);
    assert(cio_acquire(q->cq_head) == 1 && !q->buffered);
    mock_hold = 0; mock_initial = 0;
    assert(minyar_completionio_close(queue) == 0 && close(fd) == 0);
}
static void controls_restrictions_and_errors(void) {
    long long queue = minyar_completionio_open(1, 4);
    int fd = temporary_file();
    long long id = minyar_completionio_queueSync(queue, fd, 7);
    mock_allowed_flags = 0; /* Reproduce the neo-vm flags-allowlist failure. */
    assert(minyar_completionio_submit(queue) == 1);
    check_completion(queue, id, 7, CIO_SYNC, -EACCES, NULL, 0);
    mock_allowed_flags = IOSQE_IO_DRAIN;
    id = minyar_completionio_queueSync(queue, fd, 8);
    assert(minyar_completionio_submit(queue) == 1);
    check_completion(queue, id, 8, CIO_SYNC, 0, NULL, 0);
    MinyarBytes bytes = {(const unsigned char *)"data", 4, 4, NULL, NULL};
    id = minyar_completionio_queueWrite(queue, fd, 0, &bytes, 9);
    mock_forced_result = 1; mock_result = 2;
    assert(minyar_completionio_submit(queue) == 1);
    check_completion(queue, id, 9, CIO_WRITE, 2, NULL, 0); /* no hidden full-write retry */
    mock_forced_result = 0;
    assert(minyar_completionio_queueRead(queue, fd, -1, 1, 0) == -EINVAL);
    assert(minyar_completionio_queueRead(queue, fd, LLONG_MAX, 1, 0) == -EINVAL);
    assert(minyar_completionio_queueRead(queue, fd, 0, -1, 0) == -EINVAL);
    assert(minyar_completionio_queueRead(queue, LLONG_MAX, 0, 1, 0) == -EBADF);
    assert(minyar_completionio_queueWrite(queue, fd, 0, NULL, 0) == -EINVAL);
    int pipes[2]; assert(pipe(pipes) == 0);
    assert(minyar_completionio_queueRead(queue, pipes[0], 0, 1, 0) == -ENOTSUP);
    close(pipes[0]); close(pipes[1]);
    int sockets[2]; assert(socketpair(AF_UNIX, SOCK_STREAM, 0, sockets) == 0);
    assert(minyar_completionio_queueRead(queue, sockets[0], 0, 1, 0) == -ENOTSUP);
    close(sockets[0]); close(sockets[1]);
    int directory = open("/tmp", O_RDONLY | O_DIRECTORY);
    assert(directory >= 0 && minyar_completionio_queueSync(queue, directory, 0) == -ENOTSUP); close(directory);
    int flags = fcntl(fd, F_GETFL); assert(flags >= 0);
    assert(fcntl(fd, F_SETFL, flags | O_APPEND) == 0);
    assert(minyar_completionio_queueWrite(queue, fd, 0, &bytes, 0) == -ENOTSUP);
    assert(fcntl(fd, F_SETFL, flags) == 0);
    if (fcntl(fd, F_SETFL, flags | O_DIRECT) == 0) {
        assert(minyar_completionio_queueRead(queue, fd, 0, 1, 0) == -ENOTSUP);
        assert(fcntl(fd, F_SETFL, flags) == 0);
    }
    CioQueue *q = cio_queue(queue);
    *q->cq_overflow = 1;
    assert(minyar_completionio_submit(queue) == -EOVERFLOW);
    *q->cq_overflow = 0; *q->sq_dropped = 1;
    assert(minyar_completionio_queueSync(queue, fd, 0) == -EOVERFLOW);
    *q->sq_dropped = 0;
    id = minyar_completionio_queueRead(queue, fd, 0, 1, 10);
    mock_hold = 1; assert(minyar_completionio_submit(queue) == 1); mock_hold = 0;
    mock_complete(q, (uint64_t)id, 2); /* Reject an impossible read length. */
    uint32_t head = cio_acquire(q->cq_head);
    int owned = q->operations[0].fd;
    struct io_uring_cqe *cqe = &q->cqes[head & (q->cq_entries - 1)];
    for (unsigned malformed = 0; malformed < 3; ++malformed) {
        if (malformed == 1) { cqe->res = 0; cqe->user_data = (uint64_t)id + 1; }
        if (malformed == 2) { cqe->user_data = (uint64_t)id; cqe->flags = IORING_CQE_F_MORE; }
        MinyarBytes *bad = minyar_completionio_collectNative(queue, false);
        assert(field(bad, 0) == -EIO && cio_acquire(q->cq_head) == head);
        assert(q->pending == 1 && q->buffered == 1 && fcntl(owned, F_GETFD) >= 0);
        assert(minyar_completionio_close(queue) == -EBUSY); release_result(bad);
    }
    cqe->flags = 0;
    check_completion(queue, id, 10, CIO_READ, 0, NULL, 0);
    q->next_id = LLONG_MAX;
    id = minyar_completionio_queueSync(queue, fd, 0);
    assert(id == LLONG_MAX && minyar_completionio_submit(queue) == 1);
    check_completion(queue, id, 0, CIO_SYNC, 0, NULL, 0);
    assert(minyar_completionio_queueSync(queue, fd, 0) == -EOVERFLOW);
    assert(minyar_completionio_close(queue) == 0 && close(fd) == 0);
}
static void *foreign_thread(void *value) {
    long long queue = *(long long *)value;
    assert(minyar_completionio_pending(queue) == -EBADF && minyar_completionio_close(queue) == -EBADF);
    long long own = minyar_completionio_open(1, 0);
    assert(own > queue && minyar_completionio_close(own) == 0);
    return NULL;
}
int main(void) {
    controls_setup(); controls_ownership(); controls_interrupt_wrap_order(); controls_restrictions_and_errors();
    long long queue = minyar_completionio_open(1, 0);
    pthread_t peer; assert(pthread_create(&peer, NULL, foreign_thread, &queue) == 0);
    assert(pthread_join(peer, NULL) == 0 && minyar_completionio_close(queue) == 0);
    long long handles[CIO_MAX_QUEUES];
    for (unsigned i = 0; i < CIO_MAX_QUEUES; ++i) { handles[i] = minyar_completionio_open(1, 0); assert(handles[i] > 0); }
    assert(minyar_completionio_open(1, 0) == -EMFILE);
    for (unsigned i = 0; i < CIO_MAX_QUEUES; ++i) assert(minyar_completionio_close(handles[i]) == 0);
    atomic_store_explicit(&cio_next_handle, LLONG_MAX, memory_order_relaxed);
    queue = minyar_completionio_open(1, 0);
    assert(queue == LLONG_MAX && minyar_completionio_close(queue) == 0);
    assert(minyar_completionio_open(1, 0) == -EOVERFLOW && !mock_live_maps);
    puts("completionio mocked controls: passed (not kernel proof)");
    return 0;
}
#endif
#elif !defined(COMPLETIONIO_MINYAR_FIXTURE)
int main(void) {
    assert(minyar_completionio_open(2, 8) == -ENOTSUP);
    assert(minyar_completionio_queueRead(1, 0, 0, 1, 0) == -ENOTSUP);
    assert(minyar_completionio_queueWrite(1, 0, 0, NULL, 0) == -ENOTSUP);
    assert(minyar_completionio_queueSync(1, 0, 0) == -ENOTSUP);
    assert(minyar_completionio_pending(1) == -ENOTSUP && minyar_completionio_staged(1) == -ENOTSUP);
    assert(minyar_completionio_submit(1) == -ENOTSUP && minyar_completionio_close(1) == -ENOTSUP);
    MinyarBytes *out = minyar_completionio_collectNative(1, true);
    assert(field(out, 0) == -ENOTSUP && out->byte_length == 40); release_result(out);
    puts("completionio unsupported controls: passed (not kernel proof)");
    return 0;
}
#endif
