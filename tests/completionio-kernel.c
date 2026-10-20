/* Strict Linux kernel proof. Exit 77 is UNAVAILABLE, never a passing proof.
 * Includes the production provider; no syscall or mapping override is defined. */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE 1
#endif
#include "../runtime/native/completionio.c"
#include <assert.h>

MinyarBytes *minyar_bytes_new(long long length) {
    assert(length >= 0);
    MinyarBytes *out = calloc(1, sizeof(*out)); assert(out);
    out->bytes = calloc(1, length ? (size_t)length : 1); assert(out->bytes);
    out->byte_length = out->character_length = length;
    return out;
}
static long long field(const MinyarBytes *out, unsigned offset) {
    uint64_t bits = 0;
    for (unsigned i = 0; i < 8; ++i) bits |= (uint64_t)out->bytes[offset + i] << (8 * i);
    long long value; memcpy(&value, &bits, 8); return value;
}
static void release_result(MinyarBytes *out) { free((void *)out->bytes); free(out); }

#ifdef COMPLETIONIO_HAS_URING
static void submit_all(long long queue) {
    /* Finite guard; positive progress consumes at least one of <=1024 entries.
     * EINTR is visible and retried with the queue's preserved shared head. */
    unsigned attempts = 0;
    while (minyar_completionio_staged(queue) > 0) {
        assert(++attempts <= 2048);
        long long result = minyar_completionio_submit(queue);
        assert(result > 0 || result == -EINTR);
    }
}
static MinyarBytes *collect_one(long long queue) {
    for (unsigned attempt = 0; attempt < 64; ++attempt) {
        MinyarBytes *out = minyar_completionio_collectNative(queue, true);
        if (field(out, 0) == -EINTR) { release_result(out); continue; }
        assert(field(out, 0) == 1); return out;
    }
    assert(0); return NULL;
}
int main(void) {
    alarm(30); /* A real-kernel hang fails this executable, not the whole lane. */
    long long queue = minyar_completionio_open(3, 16);
    if (queue < 0) {
        fprintf(stderr, "completionio kernel UNAVAILABLE: open returned %lld; no kernel proof\n", queue);
        return 77;
    }
    char path[] = "/tmp/minyar-completionio-kernel-XXXXXX";
    int fd = mkstemp(path); assert(fd >= 0); assert(unlink(path) == 0);
    int verify = dup(fd); assert(verify >= 0);
    unsigned char buffer[] = "ABCD";
    MinyarBytes data = {buffer, 4, 4, NULL, NULL};
    long long a = minyar_completionio_queueWrite(queue, fd, 0, &data, 101);
    memcpy(buffer, "EFGH", 4);
    long long b = minyar_completionio_queueWrite(queue, fd, 4, &data, -202);
    long long sync = minyar_completionio_queueSync(queue, fd, 303);
    assert(a > 0 && b > a && sync > b && close(fd) == 0);
    memset(buffer, 'x', 4); /* No managed/caller buffer may remain in an SQE. */
    assert(minyar_completionio_close(queue) == -EBUSY);
    assert(minyar_completionio_queueRead(queue, verify, 0, 1, 0) == -EAGAIN);
    submit_all(queue);
    unsigned seen = 0;
    for (unsigned i = 0; i < 3; ++i) {
        MinyarBytes *out = collect_one(queue);
        long long id = field(out, 8);
        if (id == a) { assert(!(seen & 1) && field(out, 16) == 101 && field(out, 24) == CIO_WRITE && field(out, 32) == 4); seen |= 1; }
        else if (id == b) { assert(!(seen & 2) && field(out, 16) == -202 && field(out, 24) == CIO_WRITE && field(out, 32) == 4); seen |= 2; }
        else {
            /* Actual restricted-ring IO_DRAIN must succeed after both writes.
             * Missing the flags allowlist turns this into -EACCES. */
            assert(id == sync && !(seen & 4) && field(out, 16) == 303 && field(out, 24) == CIO_SYNC && field(out, 32) == 0);
            char actual[8]; assert(pread(verify, actual, 8, 0) == 8 && !memcmp(actual, "ABCDEFGH", 8));
            seen |= 4;
        }
        assert(out->byte_length == 40); release_result(out);
    }
    assert(seen == 7 && minyar_completionio_pending(queue) == 0);
    long long read_id = minyar_completionio_queueRead(queue, verify, 0, 8, 404);
    long long eof_id = minyar_completionio_queueRead(queue, verify, 100, 8, 505);
    assert(read_id > sync && eof_id > read_id); submit_all(queue);
    seen = 0;
    for (unsigned i = 0; i < 2; ++i) {
        MinyarBytes *out = collect_one(queue);
        if (field(out, 8) == read_id) {
            assert(!(seen & 1) && field(out, 16) == 404 && field(out, 24) == CIO_READ && field(out, 32) == 8);
            assert(out->byte_length == 48 && !memcmp(out->bytes + 40, "ABCDEFGH", 8)); seen |= 1;
        } else {
            assert(!(seen & 2) && field(out, 8) == eof_id && field(out, 16) == 505 && field(out, 32) == 0 && out->byte_length == 40); seen |= 2;
        }
        release_result(out);
    }
    assert(seen == 3);
    /* A regular descriptor with the wrong access mode fails in the CQE. */
    char readonly_path[64]; snprintf(readonly_path, sizeof(readonly_path), "/proc/self/fd/%d", verify);
    int readonly = open(readonly_path, O_RDONLY | O_CLOEXEC); assert(readonly >= 0);
    long long failed_id = minyar_completionio_queueWrite(queue, readonly, 0, &data, 606);
    assert(failed_id > eof_id && close(readonly) == 0); submit_all(queue);
    MinyarBytes *failure = collect_one(queue);
    assert(field(failure, 8) == failed_id && field(failure, 32) == -EBADF && failure->byte_length == 40); release_result(failure);
    assert(close(verify) == 0 && minyar_completionio_close(queue) == 0);
    assert(minyar_completionio_close(queue) == -EBADF);
    long long another = minyar_completionio_open(1, 0);
    assert(another > queue && minyar_completionio_pending(queue) == -EBADF && minyar_completionio_close(another) == 0);
    puts("completionio real Linux io_uring: passed (restricted READ/WRITE/FSYNC + IO_DRAIN)");
    return 0;
}
#else
int main(void) {
    /* Still inspect the explicit unsupported ABI; do not relabel it a proof. */
    MinyarBytes *out = minyar_completionio_collectNative(1, false);
    assert(field(out, 0) == -ENOTSUP); release_result(out);
    fputs("completionio kernel UNAVAILABLE: build has no Linux io_uring backend; no kernel proof\n", stderr);
    return 77;
}
#endif
