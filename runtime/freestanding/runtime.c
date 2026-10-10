/* The standard runtime configuration for `--freestanding` programs, built
 * against the small C library in this directory instead of the host's. */
#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_RC_POLL_BUDGET 32
_Static_assert(sizeof(void *) == 8, "configured memory profiles require a 64-bit target");
/* -ffreestanding implies -fno-builtin, so clang would compile every memcpy
 * here, even a 4-byte Float32 or Text-compare load, into a call to the shim.
 * The builtins keep them inline; calls LLVM cannot inline still reach it. */
#include <string.h>
#define memcpy(destination, source, count) __builtin_memcpy(destination, source, count)
#define memmove(destination, source, count) __builtin_memmove(destination, source, count)
#define memset(destination, value, count) __builtin_memset(destination, value, count)
#include "../minyar_runtime.c"
#include "../minyar_stack_frames.h"
