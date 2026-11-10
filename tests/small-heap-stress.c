/* Random allocate, free and resize on the small-object heap that every
 * default program uses, checking each block's contents before it is released
 * or moved and that nothing stays live. Sanitizer builds normally compile this
 * heap out (runtime/minyar_heap.h), so no ASan gate ran it: the sanitizer
 * build of this file forces it on with -DMINYAR_SYSTEM_SMALL_HEAP=1, where the
 * heap poisons free slots and ASan reports a use after free or an overflow
 * into a neighbouring slot. */
#define MINYAR_SYSTEM_HEAP 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>
#include <stdio.h>
static uint64_t s = 0x243f6a8885a308d3u;
static uint64_t next(void) { s ^= s << 13; s ^= s >> 7; s ^= s << 17; return s; }
enum { LIVE = 4096 };
static unsigned char *block[LIVE]; static size_t size[LIVE]; static unsigned char tag[LIVE];
static void check(int i) { for (size_t k = 0; k < size[i]; k++) if (block[i][k] != tag[i]) { printf("CORRUPT block %d size %zu at %zu\n", i, size[i], k); abort(); } }
static size_t pick(void) { unsigned k = next() % 10; if (k < 6) return next() % 130; if (k < 9) return next() % 1100; return 900 + next() % 400; }
int main(void) {
    unsigned long long ops = 0;
    for (int round = 0; round < 2000000; round++) {
        int i = (int)(next() % (round % 200000 < 100000 ? LIVE : 24));
        unsigned op = next() % 8;
        if (!block[i]) {
            size[i] = pick(); tag[i] = (unsigned char)next();
            block[i] = rc_system_allocate(size[i]);
            assert(((uintptr_t)block[i] & 15) == 0);
            memset(block[i], tag[i], size[i]);
        } else if (op < 2) {
            check(i); size_t bigger = pick(); size_t keep = bigger < size[i] ? bigger : size[i];
            block[i] = rc_system_resize(block[i], size[i], bigger);
            for (size_t k = 0; k < keep; k++) assert(block[i][k] == tag[i]);
            size[i] = bigger; memset(block[i], tag[i], size[i]);
        } else {
            check(i);
            if (op & 1) rc_system_deallocate(block[i]); else rc_system_deallocate_fast(block[i]);
            block[i] = NULL;
        }
        ops++;
        if (round % 1000003 == 0) { for (int j = 0; j < LIVE; j++) if (block[j]) { check(j); rc_system_deallocate(block[j]); block[j] = NULL; } assert(rc_system_live == 0); }
    }
    for (int j = 0; j < LIVE; j++) if (block[j]) { check(j); rc_system_deallocate_fast(block[j]); block[j] = NULL; }
    assert(rc_system_live == 0);
    printf("small heap: %llu operations, contents intact, live 0\n", ops);
    return 0;
}
