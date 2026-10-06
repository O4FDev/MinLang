/* Opaque full-value consumer, separately compiled without LTO. */
#include <stddef.h>
#include <stdint.h>
#include <string.h>

__attribute__((noinline)) uint64_t research_checksum(const long long *values, size_t count,
                                                     uintptr_t shared) {
    uint64_t checksum = UINT64_C(0xcbf29ce484222325);
    for (size_t i = 0; i < count; i++) {
        uint64_t word;
        memcpy(&word, &values[i], sizeof(word));
        if (shared)
            word = word == (uint64_t)shared;
        checksum = (checksum ^ word) * UINT64_C(0x100000001b3);
    }
    return checksum;
}
