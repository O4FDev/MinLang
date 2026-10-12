#include <stdint.h>
typedef struct SystemKernelAction {
    unsigned long handler, flags;
#ifdef __x86_64__
    unsigned long restorer;
#endif
    uint64_t mask;
} SystemKernelAction;
