#define _GNU_SOURCE 1
#include <errno.h>
#include <poll.h>
#include <sched.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

long long minyar_mapsbaseline_pinCPU(void) {
    cpu_set_t allowed, selected;
    if (sched_getaffinity(0, sizeof(allowed), &allowed)) return -errno;
    for (int cpu = 0; cpu < CPU_SETSIZE; ++cpu) {
        if (!CPU_ISSET(cpu, &allowed)) continue;
        CPU_ZERO(&selected);
        CPU_SET(cpu, &selected);
        if (sched_setaffinity(0, sizeof(selected), &selected)) return -errno;
        return cpu;
    }
    return -EINVAL;
}

double minyar_mapsbaseline_childCPU(void) {
    struct rusage usage;
    if (getrusage(RUSAGE_CHILDREN, &usage)) return -1.0;
    return (double)usage.ru_utime.tv_sec + (double)usage.ru_utime.tv_usec / 1000000.0
        + (double)usage.ru_stime.tv_sec + (double)usage.ru_stime.tv_usec / 1000000.0;
}

long long minyar_mapsbaseline_waitForExit(long long pid, long long milliseconds) {
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
