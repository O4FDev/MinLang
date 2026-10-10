#if __has_feature(address_sanitizer) || __has_feature(undefined_behavior_sanitizer) || __has_feature(thread_sanitizer)
#error Unexpected sanitizer
#endif
#include "memory-research-list-bulk-cpu.c"
