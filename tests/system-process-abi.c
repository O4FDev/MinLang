/* Actual provider declaration and pinned kernel declaration are supplied by
 * the boundary runner. Freestanding target compilation needs no libc/sysroot. */
#include <stddef.h>
#include "system-action.h"
#include "kernel-action.h"

#if defined(__aarch64__)
_Static_assert(sizeof(SystemKernelAction) == 32, "arm64 kernel action is 32 bytes");
_Static_assert(offsetof(SystemKernelAction, mask) == 24, "arm64 kernel mask is at byte 24");
#elif defined(__x86_64__)
_Static_assert(sizeof(SystemKernelAction) == 32, "x86_64 kernel action is 32 bytes");
_Static_assert(offsetof(SystemKernelAction, mask) == 24, "x86_64 kernel mask is at byte 24");
#else
#error "unsupported Linux kernel action target"
#endif
_Static_assert(sizeof(long) == 8 && sizeof(void *) == 8, "kernel action requires LP64");
_Static_assert(sizeof(SystemKernelAction) == sizeof(struct sigaction), "provider/kernel action size matches");
_Static_assert(_Alignof(SystemKernelAction) == _Alignof(struct sigaction), "provider/kernel action alignment matches");
_Static_assert(offsetof(SystemKernelAction, handler) == offsetof(struct sigaction, sa_handler), "handler offset matches kernel");
_Static_assert(offsetof(SystemKernelAction, flags) == offsetof(struct sigaction, sa_flags), "flags offset matches kernel");
_Static_assert(offsetof(SystemKernelAction, restorer) == offsetof(struct sigaction, sa_restorer), "restorer offset matches kernel");
_Static_assert(offsetof(SystemKernelAction, mask) == offsetof(struct sigaction, sa_mask), "mask offset matches kernel");
