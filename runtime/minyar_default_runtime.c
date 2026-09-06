/* Standard launcher configuration. Custom profiles use an invocation-local
 * wrapper around the same implementation and compiler-private stack ABI. */
#undef MINYAR_COMPILER_ARENA
#undef MINYAR_SYSTEM_HEAP
#undef MINYAR_BOUNDED_HEAP
#undef MINYAR_LAZY_HEAP
#undef MINYAR_BOUNDED_RC
#undef MINYAR_RC_POLL_BUDGET
#undef MINYAR_BOUNDED_HEAP_BYTES
#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_RC_POLL_BUDGET 32
_Static_assert(sizeof(void *) == 8, "configured memory profiles require a 64-bit target");
#include "minyar_runtime.c"
#include "minyar_stack_frames.h"
