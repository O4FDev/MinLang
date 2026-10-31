/* Runtime-level close check for frozen Text views: after the view, the frozen
 * handle and the source Bytes are released, no object may be left over. */
#define MINYAR_RC_TESTING 1
#define MINYAR_THREADED 1
#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_MAP_CYCLE_RUNTIME 1
#define MINYAR_NOINLINE __attribute__((noinline))
#include "minyar_runtime.c"
int main(void) {
    MinyarBytes *b = minyar_bytes_new(5);
    memcpy((void *)b->bytes, "alpha", 5);
    RcThreadLeaf *f = minyar_frozen_bytes_copy(b);
    MinyarText *v = minyar_runtime_frozenText(f, 0, 5);
    printf("view=%.5s objects=%zu immortal=%zu\n", (const char *)v->bytes, rc_object_count,
           rc_immortal_object_count);
    minyar_rc_release(v);
    minyar_rc_release(f);
    minyar_rc_release(b);
    printf("after release objects=%zu immortal=%zu\n", rc_object_count, rc_immortal_object_count);
    return rc_object_count == rc_immortal_object_count ? 0 : 1;
}
