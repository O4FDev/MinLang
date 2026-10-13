#include <stdint.h>

struct PerformanceUsage {
    int64_t userMicroseconds;
    int64_t systemMicroseconds;
    int64_t maximumRss;
    int64_t error;
};

struct PerformanceUsage minyar_performanceresources_usage(void);
void *minyar_c_record_copy(const void *source, long long size);

void *minyar_c_value_minyar_performanceresources_usage(void) {
    struct PerformanceUsage value = minyar_performanceresources_usage();
    return minyar_c_record_copy(&value, sizeof(value));
}
