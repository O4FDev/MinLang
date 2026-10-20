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
/* Generated code reserves an opaque 24-byte, eight-aligned header. */
_Static_assert(sizeof(MinyarRcScope) == (sizeof(void *) == 4 ? 12 : 24) &&
                   _Alignof(MinyarRcScope) <= 8,
               "scope ownership ABI v1 requires an aligned header within 24 bytes");
static MINYAR_THREAD_LOCAL MinyarRcScope *rc_scopes;
#endif
#endif
