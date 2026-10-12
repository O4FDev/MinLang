/* Backing allocator for bounded reference-count traversal. System calls have
 * no execution-time or reservation guarantee. The optional pool preserves its
 * fixed-capacity bookkeeping contract. Neither backend changes object headers. */
#ifdef MINYAR_SYSTEM_HEAP
#ifndef MINYAR_SYSTEM_SMALL_HEAP
#define MINYAR_SYSTEM_SMALL_HEAP 1
#endif
#if !MINYAR_THREADED && MINYAR_SYSTEM_SMALL_HEAP
#include "minyar_system_small_heap.h"
#endif
#ifdef MINYAR_RC_TESTING
static MINYAR_THREAD_LOCAL size_t rc_heap_allocation_count;
#endif
static inline void *rc_heap_allocate(size_t bytes) {
#if !MINYAR_THREADED && MINYAR_SYSTEM_SMALL_HEAP
    void *pointer = rc_system_allocate(bytes);
#else
    void *pointer = malloc(bytes);
#endif
    if (!pointer) out_of_memory();
    RC_ACCOUNT(rc_heap_allocation_count++);
    return pointer;
}
static inline void rc_heap_deallocate(void *pointer) {
    if (!pointer) return;
    RC_ACCOUNT(rc_heap_allocation_count--);
#if !MINYAR_THREADED && MINYAR_SYSTEM_SMALL_HEAP
    rc_system_deallocate(pointer);
#else
    free(pointer);
#endif
}
static inline void *rc_heap_resize(void *pointer, size_t old_bytes, size_t bytes) {
    if (!pointer) return rc_heap_allocate(bytes);
#if !MINYAR_THREADED && MINYAR_SYSTEM_SMALL_HEAP
    void *resized = rc_system_resize(pointer, old_bytes, bytes);
#else
    (void)old_bytes;
    void *resized = realloc(pointer, bytes);
#endif
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
