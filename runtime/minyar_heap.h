/* Backing allocator for bounded reference-count traversal. System calls have
 * no execution-time or reservation guarantee. The optional pool preserves its
 * fixed-capacity bookkeeping contract. Neither backend changes object headers. */
#if defined(MINYAR_SYSTEM_HEAP) || defined(MINYAR_EAGER_SYSTEM_HEAP)
#ifndef MINYAR_SYSTEM_SMALL_HEAP
#if defined(__has_feature)
#if __has_feature(address_sanitizer)
#define MINYAR_SYSTEM_SMALL_HEAP 0
#endif
#endif
#if defined(__SANITIZE_ADDRESS__)
#define MINYAR_SYSTEM_SMALL_HEAP 0
#endif
#ifndef MINYAR_SYSTEM_SMALL_HEAP
#define MINYAR_SYSTEM_SMALL_HEAP 1
#endif
#endif
#if MINYAR_SYSTEM_SMALL_HEAP
#include "minyar_system_small_heap.h"
#endif
/* Whether every managed object rc_heap_allocate returns sits behind a small-heap
 * slot header, where the bounded scheduler keeps a dead object's cursor. Each
 * thread allocates its objects from its own small heap, so this holds in
 * thread programs too (only movable Bytes storage uses rc_heap_allocate_data). */
#define MINYAR_OBJECT_SLOT_HEADERS MINYAR_SYSTEM_SMALL_HEAP
#ifdef MINYAR_RC_TESTING
static MINYAR_THREAD_LOCAL size_t rc_heap_allocation_count;
#endif
static inline void *rc_heap_allocate(size_t bytes) {
#if MINYAR_SYSTEM_SMALL_HEAP
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
#if MINYAR_SYSTEM_SMALL_HEAP
    rc_system_deallocate(pointer);
#else
    free(pointer);
#endif
}
static inline void *rc_heap_resize(void *pointer, size_t old_bytes, size_t bytes) {
    if (!pointer) return rc_heap_allocate(bytes);
#if MINYAR_SYSTEM_SMALL_HEAP
    void *resized = rc_system_resize(pointer, old_bytes, bytes);
#else
    (void)old_bytes;
    void *resized = realloc(pointer, bytes);
#endif
    if (!resized) out_of_memory();
    return resized;
}
#if MINYAR_SYSTEM_SMALL_HEAP && MINYAR_THREADED
/* Thread programs: buffer storage (Bytes, Text and List data) can move to
 * another thread (sendBytes, freezeBytesTake), which frees it there, so it
 * always uses large slots (plain malloc). Objects and frames stay on this
 * thread's small pages. */
#define MINYAR_HEAP_DATA_DEFINED 1
static inline void *rc_heap_allocate_data(size_t bytes) {
    if (bytes > SIZE_MAX - sizeof(RcSystemSlot)) out_of_memory();
    RcSystemSlot *slot = malloc(sizeof(*slot) + bytes);
    if (!slot) out_of_memory();
    slot->page = NULL;
    slot->value.bytes = bytes;
    /* Thread programs only; spelled apart from rc_heap_allocate's event, which tools probe. */
    RC_ACCOUNT(rc_heap_allocation_count += 1);
    return slot + 1;
}
static inline void *rc_heap_resize_data(void *pointer, size_t old_bytes, size_t bytes) {
    if (!pointer) return rc_heap_allocate_data(bytes);
    RcSystemSlot *slot = (RcSystemSlot *)pointer - 1;
    if (slot->page) {
        /* Storage that began as a small slot becomes movable as it grows. */
        void *moved = rc_heap_allocate_data(bytes);
        memcpy(moved, pointer, old_bytes < bytes ? old_bytes : bytes);
        rc_heap_deallocate(pointer);
        return moved;
    }
    if (bytes > SIZE_MAX - sizeof(*slot)) out_of_memory();
    slot = realloc(slot, sizeof(*slot) + bytes);
    if (!slot) out_of_memory();
    slot->value.bytes = bytes;
    return slot + 1;
}
#endif
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
#ifndef MINYAR_HEAP_DATA_DEFINED
#define rc_heap_allocate_data(bytes) rc_heap_allocate(bytes)
#define rc_heap_resize_data(pointer, old_bytes, bytes) rc_heap_resize((pointer), (old_bytes), (bytes))
#endif
