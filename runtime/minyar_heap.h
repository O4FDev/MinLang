/* Backing allocator for bounded reference-count traversal. System calls have
 * no execution-time or reservation guarantee. The optional pool preserves its
 * fixed-capacity bookkeeping contract. Neither backend changes object headers. */
#ifdef MINYAR_SYSTEM_HEAP
#ifdef MINYAR_RC_TESTING
static size_t rc_heap_allocation_count;
#endif
static inline void *rc_heap_allocate(size_t bytes) {
    void *pointer = malloc(bytes);
    if (!pointer) out_of_memory();
    RC_ACCOUNT(rc_heap_allocation_count++);
    return pointer;
}
static inline void rc_heap_deallocate(void *pointer) {
    if (!pointer) return;
    RC_ACCOUNT(rc_heap_allocation_count--);
    free(pointer);
}
static inline void *rc_heap_resize(void *pointer, size_t old_bytes, size_t bytes) {
    (void)old_bytes;
    if (!pointer) return rc_heap_allocate(bytes);
    void *resized = realloc(pointer, bytes);
    if (!resized) out_of_memory();
    return resized;
}
static inline size_t rc_heap_charge(void *pointer, size_t requested_bytes) {
    (void)pointer;
    /* Cache cap covers requested storage, not libc rounding or metadata. */
    return requested_bytes;
}
#else
#include "minyar_pool.h"
#define rc_heap_allocate(bytes) minyar_pool_allocate(bytes)
#define rc_heap_deallocate(pointer) minyar_pool_deallocate(pointer)
#define rc_heap_resize(pointer, old_bytes, bytes) minyar_pool_resize(pointer, old_bytes, bytes)
static inline size_t rc_heap_charge(void *pointer, size_t requested_bytes) {
    (void)requested_bytes;
    return pool_block_size(pool_allocated_order(pointer));
}
#endif
