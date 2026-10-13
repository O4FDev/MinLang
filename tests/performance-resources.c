#include <errno.h>
#include <stdint.h>
#include <sys/resource.h>
#include <unistd.h>
#include <fcntl.h>

struct PerformanceUsage {
    int64_t userMicroseconds;
    int64_t systemMicroseconds;
    int64_t maximumRss;
    int64_t error;
};

struct PerformanceUsage minyar_performanceresources_usage(void) {
    struct rusage value;
    struct PerformanceUsage result = {0, 0, 0, 0};
    if (getrusage(RUSAGE_CHILDREN, &value) != 0) {
        result.error = -errno;
        return result;
    }
    result.userMicroseconds = (int64_t)value.ru_utime.tv_sec * 1000000 + value.ru_utime.tv_usec;
    result.systemMicroseconds = (int64_t)value.ru_stime.tv_sec * 1000000 + value.ru_stime.tv_usec;
    result.maximumRss = value.ru_maxrss;
    return result;
}

int64_t minyar_performanceresources_duplicate(int64_t descriptor) {
    if (descriptor < 0 || descriptor > INT32_MAX) return -EINVAL;
    int result = fcntl((int)descriptor, F_DUPFD_CLOEXEC, 3);
    return result < 0 ? -errno : result;
}

int64_t minyar_performanceresources_duplicateTo(int64_t descriptor, int64_t target) {
    if (descriptor < 0 || descriptor > INT32_MAX || target < 0 || target > INT32_MAX) return -EINVAL;
    int result = dup2((int)descriptor, (int)target);
    return result < 0 ? -errno : result;
}
