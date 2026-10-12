/* Exact pointer-free checked OS operations. All failures use negative errno;
 * allocations elsewhere remain process fatal. Preserve the caller's errno. */
#include <errno.h>
#ifndef _WIN32
#include <unistd.h>
#include <time.h>
#ifdef __linux__
#include <sys/ioctl.h>
#endif
#endif
long long minyar_thread_process_id(void) {
    int saved_errno = errno;
#ifdef _WIN32
    long long result = (long long)GetCurrentProcessId();
#else
    long long result = (long long)getpid();
#endif
    errno = saved_errno;
    return result;
}
long long minyar_thread_sleep_ns(long long nanoseconds) {
    int saved_errno = errno;
    long long result = 0;
    if (nanoseconds < 0) result = -EINVAL;
    else if (nanoseconds) {
        rc_thread_domain_drain();
#ifdef _WIN32
        HANDLE timer = CreateWaitableTimerW(NULL, TRUE, NULL);
        if (!timer) result = -EIO;
        else {
            LARGE_INTEGER due;
            /* Ceiling division without overflowing signed Integer. */
            due.QuadPart = -(nanoseconds / 100 + (nanoseconds % 100 != 0));
            if (!SetWaitableTimer(timer, &due, 0, NULL, NULL, FALSE) ||
                WaitForSingleObject(timer, INFINITE) != WAIT_OBJECT_0) result = -EIO;
            CloseHandle(timer);
        }
#else
        long long seconds = nanoseconds / 1000000000;
        if ((long long)(time_t)seconds != seconds) result = -EINVAL;
        else {
            struct timespec request = {(time_t)seconds, (long)(nanoseconds % 1000000000)};
            struct timespec remaining;
            while (nanosleep(&request, &remaining)) {
                int error = errno;
                if (error != EINTR) { result = -(long long)error; break; }
                request = remaining;
            }
        }
#endif
    }
    errno = saved_errno;
    return result;
}
long long minyar_thread_fsync(long long descriptor) {
    int saved_errno = errno;
    long long result;
    if (descriptor < 0 || descriptor > INT_MAX) result = -EINVAL;
    else {
        rc_thread_domain_drain();
#ifdef _WIN32
        result = _commit((int)descriptor) ? -(long long)errno : 0;
#else
        result = fsync((int)descriptor) ? -(long long)errno : 0;
#endif
    }
    errno = saved_errno;
    return result;
}
long long minyar_thread_kernel_run(long long descriptor) {
    int saved_errno = errno;
    long long result;
    if (descriptor < 0 || descriptor > INT_MAX) result = -EINVAL;
    else {
#ifdef __linux__
        rc_thread_domain_drain();
        /* KVM_RUN's argument is exactly zero. No generic ioctl capability. */
        result = ioctl((int)descriptor, 0xAE80, (void *)0) ? -(long long)errno : 0;
#else
        result = -ENOSYS;
#endif
    }
    errno = saved_errno;
    return result;
}
