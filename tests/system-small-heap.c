#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_SYSTEM_SMALL_HEAP 1
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>
int main(void) {
    const size_t sizes[] = {0, 1, 48, 49, 112, 113, 240, 241, 496, 497, 1008, 1009, 8192};
    for (size_t round = 0; round < 100; round++) {
        void *pointers[257];
        for (size_t i = 0; i < 257; i++) {
            size_t size = sizes[i % (sizeof(sizes) / sizeof(*sizes))];
            pointers[i] = rc_heap_allocate(size);
            assert((uintptr_t)pointers[i] % _Alignof(max_align_t) == 0);
            memset(pointers[i], (unsigned char)i, size);
        }
        for (size_t i = 0; i < 257; i++) {
            size_t index = (i * 17) % 257;
            size_t size = sizes[index % (sizeof(sizes) / sizeof(*sizes))];
            size_t bigger = size + 2048;
            unsigned char *p = rc_heap_resize(pointers[index], size, bigger);
            for (size_t j = 0; j < size; j++) assert(p[j] == (unsigned char)index);
            memset(p, 7, bigger);
            p = rc_heap_resize(p, bigger, 17);
            for (size_t j = 0; j < 17; j++) assert(p[j] == 7);
            rc_heap_deallocate(p);
        }
        assert(rc_heap_allocation_count == 0);
        for (size_t i = 0; i < RC_SYSTEM_SIZE_CLASSES; i++) assert(!rc_system_available[i]);
    }
    puts("small heap alignment, size boundaries, resizing and page recovery passed");
}
