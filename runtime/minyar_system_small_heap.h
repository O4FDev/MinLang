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
enum { RC_SYSTEM_PAGE_BYTES = 4096, RC_SYSTEM_PAGE_PREFIX = 48,
       RC_SYSTEM_SIZE_CLASSES = 5 };
_Static_assert(sizeof(RcSystemSlot) == 16 && sizeof(RcSystemPage) <= RC_SYSTEM_PAGE_PREFIX,
               "small system backing requires 64-bit metadata");
_Static_assert(_Alignof(max_align_t) <= 16,
               "small system backing must preserve malloc alignment");
static RcSystemPage *rc_system_available[RC_SYSTEM_SIZE_CLASSES];

static inline void rc_system_unlink(RcSystemPage *page) {
    *page->link = page->next;
    if (page->next) page->next->link = page->link;
    page->link = NULL;
}
static inline void rc_system_link(RcSystemPage *page) {
    RcSystemPage **head = &rc_system_available[page->index];
    page->next = *head;
    page->link = head;
    if (*head) (*head)->link = &page->next;
    *head = page;
}
static MINYAR_COLD RcSystemPage *rc_system_new_page(unsigned index) {
    RcSystemPage *page = malloc(RC_SYSTEM_PAGE_BYTES);
    if (!page) out_of_memory();
    page->free_slots = NULL;
    page->live = 0;
    page->index = index;
    page->stride = 64u << index;
    page->used = RC_SYSTEM_PAGE_PREFIX;

    SMALL_HEAP_POISON((unsigned char *)page + RC_SYSTEM_PAGE_PREFIX,
                      RC_SYSTEM_PAGE_BYTES - RC_SYSTEM_PAGE_PREFIX);
    rc_system_link(page);
    return page;
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
    unsigned index = 0;
    size_t stride = 64;
    while (bytes > stride - sizeof(RcSystemSlot)) { stride <<= 1; index++; }
    RcSystemPage *page = rc_system_available[index];
    if (!page) page = rc_system_new_page(index);
    RcSystemSlot *slot = page->free_slots;
    if (slot) page->free_slots = slot->value.next;
    else {
        slot = (RcSystemSlot *)((unsigned char *)page + page->used);
        page->used += page->stride;
        SMALL_HEAP_UNPOISON(slot, sizeof(*slot));
        slot->page = page;
    }
    if (!page->free_slots && page->used + page->stride > RC_SYSTEM_PAGE_BYTES)
        rc_system_unlink(page);
    page->live++;
    slot->value.bytes = bytes;
    SMALL_HEAP_UNPOISON(slot + 1, bytes);
    return slot + 1;
}
static inline void rc_system_deallocate(void *pointer) {
    RcSystemSlot *slot = (RcSystemSlot *)pointer - 1;
    RcSystemPage *page = slot->page;
    if (!page) { free(slot); return; }
    if (--page->live == 0) {
        if (page->link) rc_system_unlink(page);
        free(page);
        return;
    }
    SMALL_HEAP_POISON(pointer, page->stride - sizeof(*slot));
    if (!page->link) rc_system_link(page);
    slot->value.next = page->free_slots;
    page->free_slots = slot;
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

#undef SMALL_HEAP_POISON
#undef SMALL_HEAP_UNPOISON
