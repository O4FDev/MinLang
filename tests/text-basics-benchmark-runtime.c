#define _GNU_SOURCE 1
#include "../runtime/minyar_native.h"
#include <errno.h>
#include <fcntl.h>
#include <time.h>
#include <poll.h>
#include <sys/syscall.h>
#include <unistd.h>

void minyar_rc_release(void *value);

MinyarBytes *minyar_textbenchmark_startCapture(const MinyarText *path) {
    if (!path || path->byte_length < 1 || memchr(path->bytes, 0, (size_t)path->byte_length)) return minyar_bytes_new(0);
    MinyarBytes *token = minyar_bytes_new(16);
    char *name = malloc((size_t)path->byte_length + 5);
    if (!name) { minyar_rc_release(token); return minyar_bytes_new(0); }
    memcpy(name, path->bytes, (size_t)path->byte_length);
    name[path->byte_length] = 0;
    int output = open(name, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0600);
    memcpy(name + path->byte_length, ".err", 5);
    int error = open(name, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0600);
    free(name);
    int saved_output = fcntl(STDOUT_FILENO, F_DUPFD_CLOEXEC, 3);
    int saved_error = fcntl(STDERR_FILENO, F_DUPFD_CLOEXEC, 3);
    if (output < 0 || error < 0 || saved_output < 0 || saved_error < 0) {
        if (output >= 0) close(output);
        if (error >= 0) close(error);
        if (saved_output >= 0) close(saved_output);
        if (saved_error >= 0) close(saved_error);
        minyar_rc_release(token);
        return minyar_bytes_new(0);
    }
    if (dup2(output, STDOUT_FILENO) < 0 || dup2(error, STDERR_FILENO) < 0) {
        dup2(saved_output, STDOUT_FILENO);
        dup2(saved_error, STDERR_FILENO);
        close(output);
        close(error);
        close(saved_output);
        close(saved_error);
        minyar_rc_release(token);
        return minyar_bytes_new(0);
    }
    close(output);
    close(error);
    long long descriptors[2] = {saved_output, saved_error};
    memcpy((void *)token->bytes, descriptors, sizeof(descriptors));
    return token;
}

long long minyar_textbenchmark_finishCapture(const MinyarBytes *token) {
    if (!token || token->byte_length != 16) return -EINVAL;
    long long descriptors[2];
    memcpy(descriptors, token->bytes, sizeof(descriptors));
    int output = dup2((int)descriptors[0], STDOUT_FILENO);
    int error = dup2((int)descriptors[1], STDERR_FILENO);
    close((int)descriptors[0]);
    close((int)descriptors[1]);
    return output < 0 || error < 0 ? -EIO : 0;
}

long long minyar_textbenchmark_waitForExit(long long pid, long long milliseconds) {
    int fd = (int)syscall(SYS_pidfd_open, (pid_t)pid, 0);
    if (fd < 0) return -errno;
    struct pollfd descriptor = {fd, POLLIN, 0};
    struct timespec start, now;
    clock_gettime(CLOCK_MONOTONIC, &start);
    long long deadline = (long long)start.tv_sec * 1000 + start.tv_nsec / 1000000 + milliseconds;
    int status;
    do {
        clock_gettime(CLOCK_MONOTONIC, &now);
        long long remaining = deadline - ((long long)now.tv_sec * 1000 + now.tv_nsec / 1000000);
        if (remaining < 0) remaining = 0;
        status = poll(&descriptor, 1, (int)remaining);
    } while (status < 0 && errno == EINTR);
    int error = errno;
    close(fd);
    return status < 0 ? -error : status;
}

bool minyar_textbenchmark_sameBytes(const MinyarBytes *left, const MinyarBytes *right) {
    return left->byte_length == right->byte_length &&
        (left->byte_length == 0 || !memcmp(left->bytes, right->bytes, (size_t)left->byte_length));
}
