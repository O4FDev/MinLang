#include <stdint.h>
typedef struct SystemKernelAction {
    unsigned long handler, flags;
    /* Both Linux x86_64 and arm64 kernel UAPIs carry this slot, even when
     * libc hides SA_RESTORER. It remains zero for the default disposition. */
    unsigned long restorer;
    uint64_t mask;
} SystemKernelAction;
