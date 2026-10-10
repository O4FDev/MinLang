/* Process-isolated managed workers. Native queues contain copied bytes only;
 * no managed pointer or RC operation crosses an execution-domain boundary.
 * The coordinator API is single-owner. Child stdout is a framed transport. */
#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif
#ifdef __APPLE__
#define _DARWIN_C_SOURCE 1
#endif
#include "../minyar_native.h"
#include <errno.h>
#include <limits.h>
#include <stdint.h>

enum { WORK_OK, WORK_BLOCK, WORK_EOF, WORK_FAILURE };
enum { WORK_MAX_MESSAGE = 16 * 1024 * 1024, WORK_MAX_QUEUE = 32 * 1024 * 1024 };
static void worker_put32(unsigned char *out, uint32_t value) {
    for (unsigned at = 0; at < 4; at++)
        out[at] = (unsigned char)(value >> (at * 8));
}
static uint32_t worker_get32(const unsigned char *input) {
    uint32_t value = 0;
    for (unsigned at = 0; at < 4; at++)
        value |= (uint32_t)input[at] << (at * 8);
    return value;
}
static MinyarBytes *worker_scalar(unsigned status, int code, long long value) {
    MinyarBytes *result = minyar_bytes_new(16);
    unsigned char *out = (unsigned char *)result->bytes;
    worker_put32(out, status);
    worker_put32(out + 4, (uint32_t)code);
    for (unsigned at = 0; at < 8; at++)
        out[8 + at] = (unsigned char)((uint64_t)value >> (at * 8));
    return result;
}
static MinyarBytes *worker_data(unsigned status, int code, const void *data, size_t length) {
    MinyarBytes *result = minyar_bytes_new((long long)length + 8);
    unsigned char *out = (unsigned char *)result->bytes;
    worker_put32(out, status);
    worker_put32(out + 4, (uint32_t)code);
    if (length)
        memcpy(out + 8, data, length);
    return result;
}

#ifdef _WIN32
#include "workers_windows.h"
#else
#include <fcntl.h>
#include <poll.h>
#include <pthread.h>
#include <signal.h>
#include <spawn.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#ifdef __APPLE__
#include <libproc.h>
#endif
extern char **environ;

typedef struct WorkerProcess {
    pid_t pid;
    int input, output;
    uint32_t generation;
    unsigned char *queue, *message;
    size_t queue_length, queue_sent, message_received;
    uint32_t message_length;
    unsigned char header[4];
    unsigned header_received;
    int failed, eof;
} WorkerProcess;
static WorkerProcess *worker_processes;
static size_t worker_capacity;
static uint32_t worker_generation;
static int worker_cleanup_installed;

/* A closed pipe is an operational failure. Avoid changing process-global
 * SIGPIPE policy or discarding a signal already pending on this thread. */
static ssize_t worker_write(int fd, const void *buffer, size_t size) {
    sigset_t set, prior, pending;
    sigemptyset(&set);
    sigaddset(&set, SIGPIPE);
    int mask = pthread_sigmask(SIG_BLOCK, &set, &prior);
    if (mask) {
        errno = mask;
        return -1;
    }
    sigpending(&pending);
    int was_pending = sigismember(&pending, SIGPIPE);
    ssize_t written;
    do {
        written = write(fd, buffer, size);
    } while (written < 0 && errno == EINTR);
    int code = errno;
    if (written < 0 && code == EPIPE && !was_pending) {
        sigpending(&pending);
        if (sigismember(&pending, SIGPIPE)) {
            int signal;
            (void)sigwait(&set, &signal);
        }
    }
    pthread_sigmask(SIG_SETMASK, &prior, NULL);
    errno = code;
    return written;
}
static void worker_destroy(WorkerProcess *worker) {
    if (!worker->pid)
        return;
    close(worker->input);
    close(worker->output);
    if (kill(worker->pid, SIGKILL) != 0 &&
        errno != ESRCH) { /* wait still reaps if already exited */
    }
    int status;
    while (waitpid(worker->pid, &status, 0) < 0 && errno == EINTR) {
    }
    free(worker->queue);
    free(worker->message);
    memset(worker, 0, sizeof(*worker));
}
static void worker_cleanup(void) {
    for (size_t at = 0; at < worker_capacity; at++)
        worker_destroy(worker_processes + at);
    free(worker_processes);
    worker_processes = NULL;
    worker_capacity = 0;
}
static WorkerProcess *worker_lookup(long long handle) {
    uint64_t identity = (uint64_t)handle;
    uint32_t slot = (uint32_t)identity;
    uint32_t generation = (uint32_t)(identity >> 32);
    if (handle <= 0 || !slot || slot > worker_capacity)
        return NULL;
    WorkerProcess *worker = worker_processes + slot - 1;
    return worker->pid && worker->generation == generation ? worker : NULL;
}
static int worker_configure(int descriptor) {
    int flags = fcntl(descriptor, F_GETFL);
    return flags < 0 || fcntl(descriptor, F_SETFL, flags | O_NONBLOCK) < 0 ||
                   fcntl(descriptor, F_SETFD, FD_CLOEXEC) < 0
               ? errno
               : 0;
}
static char *worker_text(const MinyarText *text) {
    if (text->byte_length < 0 || text->byte_length > 1024 * 1024 ||
        memchr(text->bytes, 0, (size_t)text->byte_length)) {
        errno = EINVAL;
        return NULL;
    }
    char *out = malloc((size_t)text->byte_length + 1);
    if (!out) {
        errno = ENOMEM;
        return NULL;
    }
    memcpy(out, text->bytes, (size_t)text->byte_length);
    out[text->byte_length] = 0;
    return out;
}
static MinyarBytes *worker_spawn(const char *path, const char *mode) {
    int input[2], output[2];
    if (pipe(input) != 0)
        return worker_scalar(WORK_FAILURE, errno, 0);
    if (pipe(output) != 0) {
        int code = errno;
        close(input[0]);
        close(input[1]);
        return worker_scalar(WORK_FAILURE, code, 0);
    }
    int code = worker_configure(input[1]);
    if (!code)
        code = worker_configure(output[0]);
    posix_spawn_file_actions_t actions;
    int initialized = 0;
    if (!code) {
        code = posix_spawn_file_actions_init(&actions);
        initialized = !code;
    }
    if (!code)
        code = posix_spawn_file_actions_adddup2(&actions, input[0], STDIN_FILENO);
    if (!code)
        code = posix_spawn_file_actions_adddup2(&actions, output[1], STDOUT_FILENO);
    if (!code)
        code = posix_spawn_file_actions_addclose(&actions, input[0]);
    if (!code)
        code = posix_spawn_file_actions_addclose(&actions, input[1]);
    if (!code)
        code = posix_spawn_file_actions_addclose(&actions, output[0]);
    if (!code)
        code = posix_spawn_file_actions_addclose(&actions, output[1]);
    pid_t pid = 0;
    char *arguments[] = {(char *)path, "--minyar-worker", (char *)mode, NULL};
    if (!code)
        code = posix_spawn(&pid, path, &actions, NULL, arguments, environ);
    if (initialized)
        posix_spawn_file_actions_destroy(&actions);
    close(input[0]);
    close(output[1]);
    if (code) {
        close(input[1]);
        close(output[0]);
        return worker_scalar(WORK_FAILURE, code, 0);
    }
    size_t slot = 0;
    while (slot < worker_capacity && worker_processes[slot].pid)
        slot++;
    if (slot == worker_capacity) {
        size_t capacity = worker_capacity ? worker_capacity * 2 : 8;
        WorkerProcess *grown = realloc(worker_processes, capacity * sizeof(*grown));
        if (!grown) {
            close(input[1]);
            close(output[0]);
            kill(pid, SIGKILL);
            waitpid(pid, NULL, 0);
            return worker_scalar(WORK_FAILURE, ENOMEM, 0);
        }
        memset(grown + worker_capacity, 0, (capacity - worker_capacity) * sizeof(*grown));
        worker_processes = grown;
        worker_capacity = capacity;
    }
    if (worker_generation == INT32_MAX) {
        close(input[1]);
        close(output[0]);
        kill(pid, SIGKILL);
        waitpid(pid, NULL, 0);
        return worker_scalar(WORK_FAILURE, EOVERFLOW, 0);
    }
    WorkerProcess *worker = worker_processes + slot;
    worker->pid = pid;
    worker->input = input[1];
    worker->output = output[0];
    worker->generation = ++worker_generation;
    if (!worker_cleanup_installed) {
        atexit(worker_cleanup);
        worker_cleanup_installed = 1;
    }
    uint64_t handle = ((uint64_t)worker->generation << 32) | (slot + 1);
    return worker_scalar(WORK_OK, 0, (long long)handle);
}
bool minyar_workers_supported(void) {
    return true;
}
MinyarBytes *minyar_workers_spawnNative(const MinyarText *path, const MinyarText *mode) {
    char *executable = worker_text(path);
    if (!executable)
        return worker_scalar(WORK_FAILURE, errno, 0);
    char *argument = worker_text(mode);
    if (!argument) {
        int code = errno;
        free(executable);
        return worker_scalar(WORK_FAILURE, code, 0);
    }
    MinyarBytes *result = worker_spawn(executable, argument);
    free(executable);
    free(argument);
    return result;
}
MinyarBytes *minyar_workers_spawnSelfNative(const MinyarText *mode) {
    char executable[PATH_MAX + 1];
#ifdef __APPLE__
    if (proc_pidpath(getpid(), executable, sizeof(executable)) <= 0)
        return worker_scalar(WORK_FAILURE, errno ? errno : ENOENT, 0);
#else
    ssize_t length = readlink("/proc/self/exe", executable, sizeof(executable) - 1);
    if (length < 0)
        return worker_scalar(WORK_FAILURE, errno, 0);
    if ((size_t)length >= sizeof(executable) - 1)
        return worker_scalar(WORK_FAILURE, ENAMETOOLONG, 0);
    executable[length] = 0;
#endif
    char *argument = worker_text(mode);
    if (!argument)
        return worker_scalar(WORK_FAILURE, errno, 0);
    MinyarBytes *result = worker_spawn(executable, argument);
    free(argument);
    return result;
}
static int worker_flush(WorkerProcess *worker) {
    while (worker->queue_sent < worker->queue_length) {
        ssize_t count = worker_write(worker->input, worker->queue + worker->queue_sent,
                                     worker->queue_length - worker->queue_sent);
        if (count < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK)
                return 0;
            worker->failed = errno;
            return worker->failed;
        }
        worker->queue_sent += (size_t)count;
    }
    free(worker->queue);
    worker->queue = NULL;
    worker->queue_length = worker->queue_sent = 0;
    return 0;
}
MinyarBytes *minyar_workers_sendNative(long long handle, const MinyarBytes *message) {
    WorkerProcess *worker = worker_lookup(handle);
    if (!worker)
        return worker_scalar(WORK_FAILURE, ESRCH, 0);
    if (worker->failed || worker->eof)
        return worker_scalar(WORK_FAILURE, worker->failed ? worker->failed : EPIPE, 0);
    if (message->byte_length < 0 || message->byte_length > WORK_MAX_MESSAGE)
        return worker_scalar(WORK_FAILURE, EMSGSIZE, 0);
    if (worker_flush(worker))
        return worker_scalar(WORK_FAILURE, worker->failed, 0);
    size_t pending = worker->queue_length - worker->queue_sent;
    size_t frame = (size_t)message->byte_length + 4;
    if (pending > WORK_MAX_QUEUE - frame)
        return worker_scalar(WORK_BLOCK, EAGAIN, 0);
    unsigned char *queue = malloc(pending + frame);
    if (!queue)
        return worker_scalar(WORK_FAILURE, ENOMEM, 0);
    if (pending)
        memcpy(queue, worker->queue + worker->queue_sent, pending);
    worker_put32(queue + pending, (uint32_t)message->byte_length);
    if (message->byte_length)
        memcpy(queue + pending + 4, message->bytes, (size_t)message->byte_length);
    free(worker->queue);
    worker->queue = queue;
    worker->queue_sent = 0;
    worker->queue_length = pending + frame;
    int code = worker_flush(worker);
    return worker_scalar(code ? WORK_FAILURE : WORK_OK, code, message->byte_length);
}
static int64_t worker_milliseconds(void) {
    struct timespec time;
    clock_gettime(CLOCK_MONOTONIC, &time);
    return (int64_t)time.tv_sec * 1000 + time.tv_nsec / 1000000;
}
MinyarBytes *minyar_workers_receiveNative(long long handle, long long timeout) {
    WorkerProcess *worker = worker_lookup(handle);
    if (!worker)
        return worker_data(WORK_FAILURE, ESRCH, NULL, 0);
    if (timeout < -1 || timeout > INT_MAX)
        return worker_data(WORK_FAILURE, EINVAL, NULL, 0);
    int64_t deadline = timeout < 0 ? INT64_MAX : worker_milliseconds() + timeout;
    for (;;) {
        if (worker->failed)
            return worker_data(WORK_FAILURE, worker->failed, NULL, 0);
        if (worker->eof)
            return worker_data(WORK_EOF, 0, NULL, 0);
        if (worker_flush(worker))
            return worker_data(WORK_FAILURE, worker->failed, NULL, 0);
        void *target;
        size_t remaining;
        if (worker->header_received < 4) {
            target = worker->header + worker->header_received;
            remaining = 4 - worker->header_received;
        } else {
            target = worker->message + worker->message_received;
            remaining = worker->message_length - worker->message_received;
        }
        ssize_t count = read(worker->output, target, remaining);
        if (count > 0) {
            if (worker->header_received < 4) {
                worker->header_received += (unsigned)count;
                if (worker->header_received == 4) {
                    worker->message_length = worker_get32(worker->header);
                    if (worker->message_length > WORK_MAX_MESSAGE) {
                        worker->failed = EMSGSIZE;
                        continue;
                    }
                    worker->message = malloc(worker->message_length ? worker->message_length : 1);
                    if (!worker->message) {
                        worker->failed = ENOMEM;
                        continue;
                    }
                }
            } else {
                worker->message_received += (size_t)count;
            }
            if (worker->header_received == 4 &&
                worker->message_received == worker->message_length) {
                MinyarBytes *result =
                    worker_data(WORK_OK, 0, worker->message, worker->message_length);
                free(worker->message);
                worker->message = NULL;
                worker->header_received = 0;
                worker->message_received = 0;
                worker->message_length = 0;
                return result;
            }
            continue;
        }
        if (count == 0) {
            if (worker->header_received || worker->message_received)
                worker->failed = EPROTO;
            else
                worker->eof = 1;
            continue;
        }
        if (errno == EINTR)
            continue;
        if (errno != EAGAIN && errno != EWOULDBLOCK) {
            worker->failed = errno;
            continue;
        }
        int64_t now = worker_milliseconds();
        if (timeout >= 0 && now >= deadline)
            return worker_data(WORK_BLOCK, EAGAIN, NULL, 0);
        struct pollfd descriptors[2] = {{worker->output, POLLIN, 0}, {worker->input, POLLOUT, 0}};
        nfds_t count_fds = worker->queue_length > worker->queue_sent ? 2 : 1;
        int wait = timeout < 0 ? -1 : (int)(deadline - now);
        if (poll(descriptors, count_fds, wait) < 0 && errno != EINTR) {
            worker->failed = errno;
        }
    }
}
MinyarBytes *minyar_workers_closeNative(long long handle) {
    WorkerProcess *worker = worker_lookup(handle);
    if (!worker)
        return worker_scalar(WORK_FAILURE, ESRCH, 0);
    worker_destroy(worker);
    return worker_scalar(WORK_OK, 0, 1);
}
static int worker_read_exact(int descriptor, void *buffer, size_t size, int *clean_eof) {
    size_t at = 0;
    while (at < size) {
        ssize_t count = read(descriptor, (unsigned char *)buffer + at, size - at);
        if (count == 0) {
            *clean_eof = at == 0;
            return EPROTO;
        }
        if (count < 0) {
            if (errno == EINTR)
                continue;
            return errno;
        }
        at += (size_t)count;
    }
    return 0;
}
MinyarBytes *minyar_workers_readMessageNative(void) {
    unsigned char header[4];
    int clean_eof = 0;
    int code = worker_read_exact(STDIN_FILENO, header, 4, &clean_eof);
    if (code)
        return worker_data(clean_eof ? WORK_EOF : WORK_FAILURE, clean_eof ? 0 : code, NULL, 0);
    uint32_t length = worker_get32(header);
    if (length > WORK_MAX_MESSAGE)
        return worker_data(WORK_FAILURE, EMSGSIZE, NULL, 0);
    unsigned char *message = malloc(length ? length : 1);
    if (!message)
        return worker_data(WORK_FAILURE, ENOMEM, NULL, 0);
    code = worker_read_exact(STDIN_FILENO, message, length, &clean_eof);
    MinyarBytes *result =
        worker_data(code ? WORK_FAILURE : WORK_OK, code, code ? NULL : message, code ? 0 : length);
    free(message);
    return result;
}
MinyarBytes *minyar_workers_replyNative(const MinyarBytes *message) {
    if (message->byte_length < 0 || message->byte_length > WORK_MAX_MESSAGE)
        return worker_scalar(WORK_FAILURE, EMSGSIZE, 0);
    unsigned char header[4];
    worker_put32(header, (uint32_t)message->byte_length);
    size_t at = 0;
    while (at < sizeof(header)) {
        ssize_t count = worker_write(STDOUT_FILENO, header + at, sizeof(header) - at);
        if (count < 0)
            return worker_scalar(WORK_FAILURE, errno, 0);
        at += (size_t)count;
    }
    at = 0;
    while (at < (size_t)message->byte_length) {
        ssize_t count =
            worker_write(STDOUT_FILENO, message->bytes + at, (size_t)message->byte_length - at);
        if (count < 0)
            return worker_scalar(WORK_FAILURE, errno, 0);
        at += (size_t)count;
    }
    return worker_scalar(WORK_OK, 0, message->byte_length);
}
#endif
