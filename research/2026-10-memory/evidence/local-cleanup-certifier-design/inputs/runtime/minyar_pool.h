/* Optional finite heap profile. This is a bounded-depth buddy allocator, not
 * an operating-system or hard wall-clock latency guarantee. Every block is
 * contiguous; external fragmentation and pending reclamation can cause OOM.
 * All storage is reserved and touched before main. It remains available for
 * reuse until process termination; no exit graph traversal is registered. */
#ifndef MINYAR_BOUNDED_HEAP_BYTES
#define MINYAR_BOUNDED_HEAP_BYTES (64u * 1024u * 1024u)
#endif
#define MINYAR_POOL_BYTES ((size_t)MINYAR_BOUNDED_HEAP_BYTES)
#define MINYAR_POOL_MAP_BYTES (MINYAR_POOL_BYTES / MINYAR_POOL_MINIMUM)
#define MINYAR_POOL_MINIMUM 32u
#define MINYAR_POOL_ORDERS (sizeof(size_t) * CHAR_BIT)
_Static_assert(MINYAR_BOUNDED_HEAP_BYTES >= 4096,
               "bounded heap must contain at least 4096 bytes");
_Static_assert((MINYAR_BOUNDED_HEAP_BYTES & (MINYAR_BOUNDED_HEAP_BYTES - 1)) == 0,
               "bounded heap bytes must be a power of two");
_Static_assert(MINYAR_BOUNDED_HEAP_BYTES <= SIZE_MAX / 2,
               "bounded heap is too large");

#if defined(__has_feature)
#if __has_feature(address_sanitizer)
#define MINYAR_POOL_ASAN 1
#endif
#endif
#if defined(__SANITIZE_ADDRESS__) && !defined(MINYAR_POOL_ASAN)
#define MINYAR_POOL_ASAN 1
#endif
#ifdef MINYAR_POOL_ASAN
#include <sanitizer/asan_interface.h>
#define POOL_POISON(p, n) __asan_poison_memory_region((p), (n))
#define POOL_UNPOISON(p, n) __asan_unpoison_memory_region((p), (n))
#else
#define POOL_POISON(p, n) ((void)0)
#define POOL_UNPOISON(p, n) ((void)0)
#endif

typedef struct PoolLink { struct PoolLink *previous, *next; } PoolLink;
#ifdef MINYAR_LAZY_HEAP
#include <sys/mman.h>
#include <errno.h>
static unsigned char *minyar_pool, *minyar_pool_map;
#else
static _Alignas(max_align_t) unsigned char minyar_pool[MINYAR_BOUNDED_HEAP_BYTES];
#endif
/* A start byte contains order+1, with bit7 marking an allocated block.
 * Interior bytes are zero. This map costs one byte per 32 pool bytes. */
#ifndef MINYAR_LAZY_HEAP
static unsigned char minyar_pool_map[MINYAR_BOUNDED_HEAP_BYTES / MINYAR_POOL_MINIMUM];
#endif
#if defined(MINYAR_LAZY_HEAP) && defined(MINYAR_POOL_ASAN)
#ifndef MINYAR_LAZY_ASAN_MAX_BLOCK_BYTES
#define MINYAR_LAZY_ASAN_MAX_BLOCK_BYTES (64u * 1024u * 1024u)
#endif
_Static_assert(MINYAR_LAZY_ASAN_MAX_BLOCK_BYTES >= MINYAR_POOL_MINIMUM &&
               (MINYAR_LAZY_ASAN_MAX_BLOCK_BYTES & (MINYAR_LAZY_ASAN_MAX_BLOCK_BYTES - 1)) == 0,
               "lazy sanitizer block limit must be a power of two at least 32");
#endif
static PoolLink *minyar_pool_free[MINYAR_POOL_ORDERS];
static size_t minyar_pool_mask, minyar_pool_used, minyar_pool_high_water;
static unsigned minyar_pool_max_order;
#ifdef MINYAR_RC_TESTING
static size_t minyar_pool_last_steps, minyar_pool_max_steps, minyar_pool_allocation_count;
#define POOL_STEP() ((void)minyar_pool_last_steps++)
#define POOL_BEGIN() ((void)(minyar_pool_last_steps = 0))
#define POOL_END() ((void)(minyar_pool_max_steps = minyar_pool_last_steps > minyar_pool_max_steps ? minyar_pool_last_steps : minyar_pool_max_steps))
#else
#define POOL_STEP() ((void)0)
#define POOL_BEGIN() ((void)0)
#define POOL_END() ((void)0)
#endif

static size_t pool_offset(const void *pointer) {
    return (size_t)((const unsigned char *)pointer - minyar_pool);
}
static size_t pool_block_size(unsigned order) {
    return (size_t)MINYAR_POOL_MINIMUM << order;
}
static PoolLink pool_read_link(PoolLink *link) {
    POOL_UNPOISON(link, sizeof(*link));
    PoolLink result = *link;
    POOL_POISON(link, sizeof(*link));
    return result;
}
static void pool_write_link(PoolLink *link, PoolLink value) {
    POOL_UNPOISON(link, sizeof(*link));
    *link = value;
    POOL_POISON(link, sizeof(*link));
}
static void pool_insert(PoolLink *link, unsigned order) {
    PoolLink *head = minyar_pool_free[order];
    pool_write_link(link, (PoolLink){NULL, head});
    if (head) {
        PoolLink value = pool_read_link(head);
        value.previous = link;
        pool_write_link(head, value);
    }
    minyar_pool_free[order] = link;
    minyar_pool_mask |= (size_t)1 << order;
    minyar_pool_map[pool_offset(link) / MINYAR_POOL_MINIMUM] = (unsigned char)(order + 1);
}
static void pool_remove(PoolLink *link, unsigned order) {
    PoolLink value = pool_read_link(link);
    if (value.previous) {
        PoolLink before = pool_read_link(value.previous);
        before.next = value.next;
        pool_write_link(value.previous, before);
    } else minyar_pool_free[order] = value.next;
    if (value.next) {
        PoolLink after = pool_read_link(value.next);
        after.previous = value.previous;
        pool_write_link(value.next, after);
    }
    if (!minyar_pool_free[order]) minyar_pool_mask &= ~((size_t)1 << order);
    minyar_pool_map[pool_offset(link) / MINYAR_POOL_MINIMUM] = 0;
}

/* Initialization is intentionally outside ordinary allocation/release calls.
 * Touching pages does not lock them into physical RAM or prevent preemption. */
__attribute__((constructor)) static void minyar_pool_initialize(void) {
#ifdef MINYAR_LAZY_HEAP
    void *heap = mmap(NULL, MINYAR_POOL_BYTES, PROT_READ | PROT_WRITE,
                      MAP_PRIVATE | MAP_ANON, -1, 0);
    if (heap == MAP_FAILED)
        minyar_stop("the lazy heap virtual reservation failed.");
    void *map = mmap(NULL, MINYAR_POOL_MAP_BYTES, PROT_READ | PROT_WRITE,
                     MAP_PRIVATE | MAP_ANON, -1, 0);
    if (map == MAP_FAILED) {
        /* Startup failure: no live graph exists and no runtime owner escapes. */
        int failure = errno;
        munmap(heap, MINYAR_POOL_BYTES);
        errno = failure;
        minyar_stop("the lazy heap metadata reservation failed.");
    }
    minyar_pool = heap;
    minyar_pool_map = map;
#else
    volatile unsigned char *heap_pages = minyar_pool;
    volatile unsigned char *map_pages = minyar_pool_map;
    for (size_t i = 0; i < MINYAR_POOL_BYTES; i += 4096) heap_pages[i] = 0;
    for (size_t i = 0; i < MINYAR_POOL_MAP_BYTES; i += 4096) map_pages[i] = 0;
#endif
    size_t size = MINYAR_POOL_MINIMUM;
    while (size < MINYAR_POOL_BYTES) { size <<= 1; minyar_pool_max_order++; }
#ifndef MINYAR_LAZY_HEAP
    POOL_POISON(minyar_pool, MINYAR_POOL_BYTES);
#endif
    pool_insert((PoolLink *)minyar_pool, minyar_pool_max_order);
}

/* At most max_order+1 size steps and max_order split steps. No search through
 * blocks or attempt to synchronously drain pending objects on failure. */
static void *minyar_pool_try_allocate(size_t size) {
    POOL_BEGIN();
    if (size > MINYAR_POOL_BYTES) { POOL_END(); return NULL; }
#if defined(MINYAR_LAZY_HEAP) && defined(MINYAR_POOL_ASAN)
    if (size > MINYAR_LAZY_ASAN_MAX_BLOCK_BYTES) { POOL_END(); return NULL; }
#endif
    unsigned order = 0;
    size_t block_size = MINYAR_POOL_MINIMUM;
    while (block_size < size) { block_size <<= 1; order++; POOL_STEP(); }
    size_t available = minyar_pool_mask & (~(size_t)0 << order);
    if (!available) { POOL_END(); return NULL; }
    unsigned found = (unsigned)__builtin_ctzll((unsigned long long)available);
    PoolLink *result = minyar_pool_free[found];
    pool_remove(result, found);
    while (found > order) {
        found--;
        pool_insert((PoolLink *)((unsigned char *)result + pool_block_size(found)), found);
        POOL_STEP();
    }
    minyar_pool_map[pool_offset(result) / MINYAR_POOL_MINIMUM] = (unsigned char)(0x80 | (order + 1));
    minyar_pool_used += block_size;
#ifdef MINYAR_RC_TESTING
    minyar_pool_allocation_count++;
#endif
    if (minyar_pool_used > minyar_pool_high_water) minyar_pool_high_water = minyar_pool_used;
    /* Lazy reservations have no global poison sweep. Bound sanitizer shadow
     * work to this allocation's rounded block, then expose only requested bytes.
     * Never-allocated virtual holes are not ASan redzones until allocated. */
#ifdef MINYAR_LAZY_HEAP
    POOL_POISON(result, block_size);
#endif
    POOL_UNPOISON(result, size ? size : 1);
    POOL_END();
    return result;
}
static void *minyar_pool_allocate(size_t size) {
#if defined(MINYAR_LAZY_HEAP) && defined(MINYAR_POOL_ASAN)
    if (size <= MINYAR_POOL_BYTES && size > MINYAR_LAZY_ASAN_MAX_BLOCK_BYTES)
        minyar_stop("this lazy heap allocation exceeds the sanitizer block limit.");
#endif
    void *result = minyar_pool_try_allocate(size);
    if (!result) minyar_stop("the bounded heap is exhausted (including pending cleanup and fragmentation).");
    return result;
}
static unsigned pool_allocated_order(void *pointer) {
    uintptr_t address = (uintptr_t)pointer;
    if (address < (uintptr_t)minyar_pool || address >= (uintptr_t)minyar_pool + MINYAR_POOL_BYTES
        || ((address - (uintptr_t)minyar_pool) % MINYAR_POOL_MINIMUM))
        minyar_stop("an invalid bounded-heap allocation was released.");
    unsigned state = minyar_pool_map[pool_offset(pointer) / MINYAR_POOL_MINIMUM];
    if (!(state & 0x80)) minyar_stop("a bounded-heap allocation was released twice.");
    return (state & 0x7f) - 1;
}
static void minyar_pool_deallocate(void *pointer) {
    POOL_BEGIN();
    if (!pointer) { POOL_END(); return; }
    unsigned order = pool_allocated_order(pointer);
    size_t offset = pool_offset(pointer), size = pool_block_size(order);
    minyar_pool_used -= size;
    POOL_POISON(pointer, size);
    minyar_pool_map[offset / MINYAR_POOL_MINIMUM] = 0;
    while (order < minyar_pool_max_order) {
        size_t buddy = offset ^ pool_block_size(order);
        POOL_STEP();
        if (minyar_pool_map[buddy / MINYAR_POOL_MINIMUM] != order + 1) break;
        pool_remove((PoolLink *)(minyar_pool + buddy), order);
        if (buddy < offset) offset = buddy;
        order++;
    }
    pool_insert((PoolLink *)(minyar_pool + offset), order);
    POOL_END();
}
typedef struct {
    unsigned order, wanted;
    size_t capacity, target, offset;
} PoolResizePlan;

static PoolResizePlan pool_plan_resize(void *pointer, size_t size) {
    PoolResizePlan plan;
    plan.order = pool_allocated_order(pointer);
    plan.wanted = 0;
    plan.capacity = pool_block_size(plan.order);
    plan.target = MINYAR_POOL_MINIMUM;
    plan.offset = pool_offset(pointer);
    if (size > MINYAR_POOL_BYTES)
        minyar_stop("the bounded heap is exhausted (including pending cleanup and fragmentation).");
    while (plan.target < size) {
        plan.target <<= 1;
        plan.wanted++;
        POOL_STEP();
    }
    return plan;
}

/* Common non-relocating resize state machine. A failed upper-buddy scan
 * changes no allocation, free list, payload, accounting, or poison state. */
static void *pool_try_resize_same_base(void *pointer, size_t size, PoolResizePlan plan) {
#ifndef MINYAR_POOL_ASAN
    (void)size;
#endif
    if (plan.wanted <= plan.order) {
        /* Split in place even when the heap has no other free block. */
        POOL_POISON(pointer, plan.capacity);
        minyar_pool_used -= plan.capacity - plan.target;
        while (plan.order > plan.wanted) {
            plan.order--;
            pool_insert((PoolLink *)((unsigned char *)pointer + pool_block_size(plan.order)), plan.order);
            POOL_STEP();
        }
        minyar_pool_map[plan.offset / MINYAR_POOL_MINIMUM] =
            (unsigned char)(0x80 | (plan.wanted + 1));
        POOL_UNPOISON(pointer, size ? size : 1);
        return pointer;
    }
    /* A lower block may grow through free upper buddies. */
    int can_grow = (plan.offset & (plan.target - 1)) == 0;
    for (unsigned next = plan.order; can_grow && next < plan.wanted; next++) {
        size_t buddy = plan.offset + pool_block_size(next);
        can_grow = minyar_pool_map[buddy / MINYAR_POOL_MINIMUM] == next + 1;
        POOL_STEP();
    }
    if (!can_grow) return NULL;
    for (unsigned next = plan.order; next < plan.wanted; next++) {
        pool_remove((PoolLink *)(minyar_pool + plan.offset + pool_block_size(next)), next);
        POOL_STEP();
    }
    minyar_pool_map[plan.offset / MINYAR_POOL_MINIMUM] =
        (unsigned char)(0x80 | (plan.wanted + 1));
    minyar_pool_used += plan.target - plan.capacity;
    if (minyar_pool_used > minyar_pool_high_water) minyar_pool_high_water = minyar_pool_used;
#ifdef MINYAR_LAZY_HEAP
    POOL_POISON((unsigned char *)pointer + plan.capacity, plan.target - plan.capacity);
#endif
    POOL_UNPOISON(pointer, size);
    return pointer;
}

/* Buffer copying and zero initialization take time proportional to byte count. */
static void *minyar_pool_resize(void *pointer, size_t old_size, size_t size) {
    if (!pointer) return minyar_pool_allocate(size);
#if defined(MINYAR_LAZY_HEAP) && defined(MINYAR_POOL_ASAN)
    if (size <= MINYAR_POOL_BYTES && size > MINYAR_LAZY_ASAN_MAX_BLOCK_BYTES)
        minyar_stop("this lazy heap allocation exceeds the sanitizer block limit.");
#endif
    POOL_BEGIN();
    PoolResizePlan plan = pool_plan_resize(pointer, size);
    void *same = pool_try_resize_same_base(pointer, size, plan);
    if (same) {
        POOL_END();
        return same;
    }
#ifdef MINYAR_RC_TESTING
    size_t resize_steps = minyar_pool_last_steps;
#endif
    POOL_END();
    void *result = minyar_pool_allocate(size);
#ifdef MINYAR_RC_TESTING
    resize_steps += minyar_pool_last_steps;
#endif
    memcpy(result, pointer, old_size < size ? old_size : size);
    minyar_pool_deallocate(pointer);
#ifdef MINYAR_RC_TESTING
    minyar_pool_last_steps += resize_steps;
#endif
    POOL_END();
    return result;
}

/* Called only after resize validates an unaligned, growing allocation whose
 * preserved prefix is empty. A failed full-path scan changes no allocation,
 * free-list, payload or poison state; resize owns the work-counter scope. */
static void *minyar_pool_try_grow_lower(size_t offset, unsigned order, unsigned wanted,
                                      size_t capacity, size_t target, size_t size) {
#ifndef MINYAR_POOL_ASAN
    (void)size;
#endif
    size_t merged_offset = offset;
    int can_grow = 1;
    for (unsigned next = order; can_grow && next < wanted; next++) {
        size_t buddy = merged_offset ^ pool_block_size(next);
        can_grow = minyar_pool_map[buddy / MINYAR_POOL_MINIMUM] == next + 1;
        if (buddy < merged_offset) merged_offset = buddy;
        POOL_STEP();
    }
    if (!can_grow) return NULL;
    size_t base = offset;
    for (unsigned next = order; next < wanted; next++) {
        size_t buddy = base ^ pool_block_size(next);
        pool_remove((PoolLink *)(minyar_pool + buddy), next);
        if (buddy < base) base = buddy;
        POOL_STEP();
    }
    minyar_pool_map[offset / MINYAR_POOL_MINIMUM] = 0;
    void *result = minyar_pool + base;
    minyar_pool_map[base / MINYAR_POOL_MINIMUM] = (unsigned char)(0x80 | (wanted + 1));
    minyar_pool_used += target - capacity;
    if (minyar_pool_used > minyar_pool_high_water) minyar_pool_high_water = minyar_pool_used;
    /* The old accessible tail can lie beyond the relocated requested prefix. */
    POOL_POISON(result, target);
    POOL_UNPOISON(result, size);
    return result;
}

/* Dedicated resize for retired frame slot storage: no prior contents must
 * survive and callers retain no interior aliases. Failure is fatal and keeps
 * old storage owned until replacement succeeds. Lower merging adds no
 * allocation or copying. */
static void *minyar_pool_resize_discard(void *pointer, size_t size) {
    if (!pointer) return minyar_pool_allocate(size);
#if defined(MINYAR_LAZY_HEAP) && defined(MINYAR_POOL_ASAN)
    if (size <= MINYAR_POOL_BYTES && size > MINYAR_LAZY_ASAN_MAX_BLOCK_BYTES)
        minyar_stop("this lazy heap allocation exceeds the sanitizer block limit.");
#endif
    POOL_BEGIN();
    PoolResizePlan plan = pool_plan_resize(pointer, size);
    void *same = pool_try_resize_same_base(pointer, size, plan);
    if (same) {
        POOL_END();
        return same;
    }
    /* All ordinary in-place paths have already returned. Empty frame slots
     * may absorb lower buddies; validate the complete path before mutation. */
    if (plan.offset & (plan.target - 1)) {
        void *merged = minyar_pool_try_grow_lower(plan.offset, plan.order, plan.wanted,
                                                  plan.capacity, plan.target, size);
        if (merged) {
            POOL_END();
            return merged;
        }
    }
#ifdef MINYAR_RC_TESTING
    size_t resize_steps = minyar_pool_last_steps;
#endif
    POOL_END();
    void *result = minyar_pool_allocate(size);
#ifdef MINYAR_RC_TESTING
    resize_steps += minyar_pool_last_steps;
#endif
    minyar_pool_deallocate(pointer);
#ifdef MINYAR_RC_TESTING
    minyar_pool_last_steps += resize_steps;
#endif
    POOL_END();
    return result;
}
