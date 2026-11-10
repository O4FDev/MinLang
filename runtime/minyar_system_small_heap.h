#if defined(__has_feature)
#if __has_feature(address_sanitizer)
#define MINYAR_SMALL_HEAP_ASAN 1
#endif
#endif
#if defined(__SANITIZE_ADDRESS__) && !defined(MINYAR_SMALL_HEAP_ASAN)
#define MINYAR_SMALL_HEAP_ASAN 1
#endif
#ifdef MINYAR_SMALL_HEAP_ASAN
#include <sanitizer/asan_interface.h>
#define SMALL_HEAP_POISON(p, n) __asan_poison_memory_region((p), (n))
#define SMALL_HEAP_UNPOISON(p, n) __asan_unpoison_memory_region((p), (n))
#else
#define SMALL_HEAP_POISON(p, n) ((void)0)
#define SMALL_HEAP_UNPOISON(p, n) ((void)0)
#endif

typedef struct RcSystemPage RcSystemPage;
typedef struct RcSystemSlot {
    RcSystemPage *page;
    union { struct RcSystemSlot *next; size_t bytes; } value;
} RcSystemSlot;
struct RcSystemPage {
    RcSystemPage *next;
    RcSystemPage **link;
    RcSystemSlot *free_slots;
    size_t live;
    unsigned stride, index, used;
};
enum { RC_SYSTEM_PAGE_BYTES = 4096, RC_SYSTEM_PAGE_PREFIX = 48 };
#if MINYAR_THREADED
/* Thread programs keep five power-of-two strides: a join task carries one page
 * list per class (RcSystemHeap) inside its fixed generated storage. */
enum { RC_SYSTEM_SIZE_CLASSES = 5 };
static const unsigned short rc_system_strides[RC_SYSTEM_SIZE_CLASSES] = {64, 128, 256, 512, 1024};
static const unsigned char rc_system_classes[64] = {
    0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4};
#else
enum { RC_SYSTEM_SIZE_CLASSES = 18 };
/* Slot strides, header included. Steps of 16 bytes up to 128, then four per
 * doubling, so a slot wastes at most a quarter of its payload (powers of two
 * wasted up to half: a 52-byte record took a 128-byte slot, now 80). Every
 * stride is a multiple of 16, so each slot keeps malloc alignment. */
static const unsigned short rc_system_strides[RC_SYSTEM_SIZE_CLASSES] = {
    48, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, 448, 512, 640, 768, 896, 1024};
/* The class of a payload of up to 1008 bytes, indexed by its size in 16-byte
 * units rounded up: the first stride holding the payload behind the header. */
static const unsigned char rc_system_classes[64] = {
    0, 0, 0, 1, 2, 3, 4, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 10, 10, 11, 11, 11, 11,
    12, 12, 12, 12, 13, 13, 13, 13, 14, 14, 14, 14, 14, 14, 14, 14, 15, 15, 15, 15, 15, 15, 15, 15,
    16, 16, 16, 16, 16, 16, 16, 16, 17, 17, 17, 17, 17, 17, 17, 17};
#endif
_Static_assert(sizeof(RcSystemSlot) == 16 && sizeof(RcSystemPage) <= RC_SYSTEM_PAGE_PREFIX,
               "small system backing requires 64-bit metadata");
_Static_assert(_Alignof(max_align_t) <= 16,
               "small system backing must preserve malloc alignment");
/* Pages belong to one thread: in a thread program each thread allocates and
 * frees only its own slots (buffers that cross threads are moved to large
 * slots first, see rc_thread_detach). */
static MINYAR_THREAD_LOCAL RcSystemPage *rc_system_available[RC_SYSTEM_SIZE_CLASSES];
/* Live small slots in every class. */
static MINYAR_THREAD_LOCAL size_t rc_system_live;
/* Pages kept empty in a class's available list, to skip the sweep when none. */
static MINYAR_THREAD_LOCAL size_t rc_system_kept;
#if !MINYAR_THREADED
/* One page of static storage per class, so that allocating and freeing a
 * single object of a class does not malloc and free a 4 KiB page each time.
 * Static storage is never heap: a program that frees everything it allocated
 * has no heap bytes left. Thread programs keep malloc'd pages, because their
 * pages move between threads (rc_system_swap/rc_system_adopt). */
static MINYAR_THREAD_LOCAL _Alignas(max_align_t)
    unsigned char rc_system_static_page[RC_SYSTEM_SIZE_CLASSES][RC_SYSTEM_PAGE_BYTES];
static MINYAR_THREAD_LOCAL unsigned char rc_system_static_used[RC_SYSTEM_SIZE_CLASSES];
/* Set when a class first frees a page: a program's first page of a class still
 * comes from malloc, and a repeated allocate-and-free of one object then does
 * not malloc a page at all. */
static MINYAR_THREAD_LOCAL unsigned char rc_system_static_ready[RC_SYSTEM_SIZE_CLASSES];
#endif

static inline void rc_system_unlink(RcSystemPage *page) {
    if (!page->link) abort(); /* An unlinked page must never be removed twice. */
    *page->link = page->next;
    if (page->next) page->next->link = page->link;
    page->link = NULL;
}
/* Allocation takes the class's first page. A page regaining free slots goes
 * second, so consecutive allocations stay on one page until it fills rather
 * than following each free; objects allocated together share pages. */
static inline void rc_system_link(RcSystemPage *page) {
    RcSystemPage **head = &rc_system_available[page->index];
    if (*head) head = &(*head)->next;
    page->next = *head;
    page->link = head;
    if (*head) (*head)->link = &page->next;
    *head = page;
}
static MINYAR_COLD RcSystemPage *rc_system_new_page(unsigned index) {
#if !MINYAR_THREADED
    if (rc_system_static_ready[index] && !rc_system_static_used[index]) {
        RcSystemPage *page = (RcSystemPage *)(void *)rc_system_static_page[index];
        rc_system_static_used[index] = 1;
        page->free_slots = NULL;
        page->live = 0;
        page->index = index;
        page->stride = rc_system_strides[index];
        page->used = RC_SYSTEM_PAGE_PREFIX;
        page->next = NULL;
        page->link = NULL;
        SMALL_HEAP_POISON((unsigned char *)page + RC_SYSTEM_PAGE_PREFIX,
                          RC_SYSTEM_PAGE_BYTES - RC_SYSTEM_PAGE_PREFIX);
        rc_system_link(page);
        return page;
    }
#endif
    RcSystemPage *page = malloc(RC_SYSTEM_PAGE_BYTES);
    if (!page) out_of_memory();
    page->free_slots = NULL;
    page->live = 0;
    page->index = index;
    page->stride = rc_system_strides[index];
    page->used = RC_SYSTEM_PAGE_PREFIX;

    SMALL_HEAP_POISON((unsigned char *)page + RC_SYSTEM_PAGE_PREFIX,
                      RC_SYSTEM_PAGE_BYTES - RC_SYSTEM_PAGE_PREFIX);
    rc_system_link(page);
    return page;
}
/* The smallest class whose stride holds `bytes` (at most 1008) behind a slot
 * header: one table load. */
static inline unsigned rc_system_size_class(size_t bytes) {
    return rc_system_classes[(bytes + 15) >> 4];
}
MINYAR_HOT void *rc_system_allocate(size_t bytes) {
    if (bytes > 1024u - sizeof(RcSystemSlot)) {
        if (bytes > SIZE_MAX - sizeof(RcSystemSlot)) out_of_memory();
        RcSystemSlot *slot = malloc(sizeof(*slot) + bytes);
        if (!slot) out_of_memory();
        slot->page = NULL;
        slot->value.bytes = bytes;
        return slot + 1;
    }
    unsigned index = rc_system_size_class(bytes);
    RcSystemPage *page = rc_system_available[index];
    if (!page) page = rc_system_new_page(index);
    /* A page leaves the available list when it has neither a free slot nor
     * room for another: test that only where the free list or room ran out. */
    RcSystemSlot *slot = page->free_slots;
    if (slot) {
        RcSystemSlot *next = slot->value.next;
        page->free_slots = next;
        if (!next && page->used + page->stride > RC_SYSTEM_PAGE_BYTES) rc_system_unlink(page);
    } else {
        slot = (RcSystemSlot *)((unsigned char *)page + page->used);
        page->used += page->stride;
        SMALL_HEAP_UNPOISON(slot, sizeof(*slot));
        slot->page = page;
        if (page->used + page->stride > RC_SYSTEM_PAGE_BYTES) rc_system_unlink(page);
    }
    page->live++;
    rc_system_live++;
    slot->value.bytes = bytes;
    SMALL_HEAP_UNPOISON(slot + 1, bytes);
    return slot + 1;
}
static inline void rc_system_deallocate(void *pointer) {
    RcSystemSlot *slot = (RcSystemSlot *)pointer - 1;
    RcSystemPage *page = slot->page;
    if (!page) { free(slot); return; }
    rc_system_live--;
    if (--page->live == 0) {
        RcSystemPage *head = rc_system_available[page->index];
        if (rc_system_live && (head == page || (!head && !page->link))) {
            /* While other small objects live, the class's only available
             * page stays, emptied: a loop whose temporaries alone occupy it
             * would otherwise free and allocate (or reset and re-take) a page
             * per iteration. Its slots simply return to its free list. */
            SMALL_HEAP_POISON(pointer, page->stride - sizeof(*slot));
            if (!page->link) rc_system_link(page);
            slot->value.next = page->free_slots;
            page->free_slots = slot;
            rc_system_kept++;
            return;
        }
#if !MINYAR_THREADED
        if (page == (RcSystemPage *)(void *)rc_system_static_page[page->index]) {
            /* Static storage is never freed: reset it for the class's next
             * object, which takes it again instead of allocating a page. */
            if (page->link) rc_system_unlink(page);
            rc_system_static_used[page->index] = 0;
            page->free_slots = NULL;
            page->used = RC_SYSTEM_PAGE_PREFIX;
            page->next = NULL;
            page->link = NULL;
            SMALL_HEAP_POISON((unsigned char *)page + RC_SYSTEM_PAGE_PREFIX,
                              RC_SYSTEM_PAGE_BYTES - RC_SYSTEM_PAGE_PREFIX);
        } else {
#endif
            /* Another page of the class is available, or nothing small is
             * live: this empty page goes back to the system. */
            if (page->link) rc_system_unlink(page);
#if !MINYAR_THREADED
            /* This class may take its static page next instead of malloc. */
            rc_system_static_ready[page->index] = 1;
#endif
            free(page);
#if !MINYAR_THREADED
        }
#endif
        /* Nothing small is live: no empty page stays either. */
        if (!rc_system_live && rc_system_kept) {
            rc_system_kept = 0;
            for (unsigned index = 0; index < RC_SYSTEM_SIZE_CLASSES; index++) {
                RcSystemPage *kept = rc_system_available[index];
                if (!kept || kept->live) continue;
                rc_system_unlink(kept);
#if !MINYAR_THREADED
                if (kept == (RcSystemPage *)(void *)rc_system_static_page[index]) {
                    /* Static storage is never freed: it waits, reset, for the
                     * class's next object. */
                    rc_system_static_used[index] = 0;
                    kept->free_slots = NULL;
                    kept->used = RC_SYSTEM_PAGE_PREFIX;
                    kept->next = NULL;
                    SMALL_HEAP_POISON((unsigned char *)kept + RC_SYSTEM_PAGE_PREFIX,
                                      RC_SYSTEM_PAGE_BYTES - RC_SYSTEM_PAGE_PREFIX);
                    continue;
                }
#endif
                free(kept);
            }
        }
        return;
    }
    SMALL_HEAP_POISON(pointer, page->stride - sizeof(*slot));
    if (!page->link) rc_system_link(page);
    slot->value.next = page->free_slots;
    page->free_slots = slot;
}
static inline void rc_system_deallocate_fast(void *pointer) {
    RcSystemSlot *slot = (RcSystemSlot *)pointer - 1;
    RcSystemPage *page = slot->page;
    if (page && page->live > 1 && page->link) {
        rc_system_live--;
        page->live--;
        SMALL_HEAP_POISON(pointer, page->stride - sizeof(*slot));
        slot->value.next = page->free_slots;
        page->free_slots = slot;
        return;
    }
    /* Also inline: the class's available page empties while other small
     * objects live, as a loop's temporaries do once per iteration when they
     * alone occupy their class. The page stays (see rc_system_deallocate). */
    if (page && page->link && rc_system_available[page->index] == page && rc_system_live > 1) {
        rc_system_live--;
        page->live = 0;
        rc_system_kept++;
        SMALL_HEAP_POISON(pointer, page->stride - sizeof(*slot));
        slot->value.next = page->free_slots;
        page->free_slots = slot;
        return;
    }
    rc_system_deallocate(pointer);
}
static inline void *rc_system_resize(void *pointer, size_t old_bytes, size_t bytes) {
    RcSystemSlot *slot = (RcSystemSlot *)pointer - 1;
    RcSystemPage *page = slot->page;
    if (page && bytes <= page->stride - sizeof(*slot)) {
        SMALL_HEAP_UNPOISON(pointer, bytes);
        if (bytes < old_bytes) SMALL_HEAP_POISON((unsigned char *)pointer + bytes, old_bytes - bytes);
        slot->value.bytes = bytes;
        return pointer;
    }
    if (!page && bytes > 1024u - sizeof(*slot)) {
        if (bytes > SIZE_MAX - sizeof(*slot)) out_of_memory();
        slot = realloc(slot, sizeof(*slot) + bytes);
        if (!slot) out_of_memory();
        slot->value.bytes = bytes;
        return slot + 1;
    }
    void *resized = rc_system_allocate(bytes);
    memcpy(resized, pointer, old_bytes < bytes ? old_bytes : bytes);
    rc_system_deallocate(pointer);
    return resized;
}

#if MINYAR_THREADED && !defined(MINYAR_MAP_CYCLE_RUNTIME)
/* A detached set of small pages: a join branch stolen by a pool worker
 * allocates on fresh pages and hands them, with the live result, to the
 * joining thread, which adopts them as its own. */
typedef struct {
    RcSystemPage *available[RC_SYSTEM_SIZE_CLASSES];
    size_t live;
} RcSystemHeap;

/* Exchanges this thread's page lists with `heap`. */
static void rc_system_swap(RcSystemHeap *heap) {
    for (unsigned index = 0; index < RC_SYSTEM_SIZE_CLASSES; index++) {
        RcSystemPage *mine = rc_system_available[index];
        RcSystemPage *theirs = heap->available[index];
        rc_system_available[index] = theirs;
        if (theirs) theirs->link = &rc_system_available[index];
        heap->available[index] = mine;
        if (mine) mine->link = &heap->available[index];
    }
    size_t live = rc_system_live;
    rc_system_live = heap->live;
    heap->live = live;
}

/* Takes every page of `heap` into this thread's lists. Full pages are on no
 * list; they join the list of whichever thread later frees into them, which
 * is this one, since the live objects on them are now this thread's. */
static void rc_system_adopt(RcSystemHeap *heap) {
    rc_system_live += heap->live;
    heap->live = 0;
    for (unsigned index = 0; index < RC_SYSTEM_SIZE_CLASSES; index++) {
        RcSystemPage *page = heap->available[index];
        heap->available[index] = NULL;
        while (page) {
            RcSystemPage *next = page->next;
            page->link = NULL;
            if (page->live) rc_system_link(page);
            else free(page);
            page = next;
        }
    }
}
#endif

#undef SMALL_HEAP_POISON
#undef SMALL_HEAP_UNPOISON
