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
long long minyar_thread_process_id(void) { return minyar_runtime_processId(); }
long long minyar_thread_sleep_ns(long long value) { return minyar_runtime_sleepNanoseconds(value); }
long long minyar_thread_fsync(long long descriptor) { return minyar_runtime_sync(descriptor); }
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
