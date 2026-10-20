/* Compiler-private scope ABI v1. Cells are initialized before registration,
 * remain on the native stack, and never enter a deferred queue or cache. */
#ifndef MINYAR_SCOPE_TYPES_V1
#define MINYAR_SCOPE_TYPES_V1
#ifndef MINYAR_COMPILER_ARENA
typedef struct MinyarRcScope {
    struct MinyarRcScope *previous;
    void **values;
    size_t count;
} MinyarRcScope;
_Static_assert(sizeof(MinyarRcScope) == 24 && _Alignof(MinyarRcScope) <= 8,
               "scope ownership ABI v1 requires an aligned 24-byte header");
static MINYAR_THREAD_LOCAL MinyarRcScope *rc_scopes;
#endif
#endif
