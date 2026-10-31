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
    printf("start objects=%zu\n", rc_object_count);
    MinyarText *v = minyar_runtime_frozenText(f, 0, 5);
    printf("after decode objects=%zu f_own=%llu v_own=%llu o_own=%llu back=%p f=%p\n", rc_object_count,
           (unsigned long long)((RcObject *)f - 1)->ownership,
           (unsigned long long)((RcObject *)v - 1)->ownership,
           (unsigned long long)((RcObject *)v->backing - 1)->ownership,
           (void *)v->backing, (void *)f);
    printf("before release v_back=%p o_back=%p\n", (void*)v->backing, v->backing ? (void*)((MinyarText*)v->backing)->backing : NULL);
    minyar_rc_release(v);
    printf("after view objects=%zu f_own=%llu\n", rc_object_count, (unsigned long long)((RcObject *)f - 1)->ownership);
    minyar_rc_release(f);
    printf("after frozen objects=%zu\n", rc_object_count);
    minyar_rc_release(b);
    printf("after bytes objects=%zu immortal=%zu\n", rc_object_count, rc_immortal_object_count);
    return 0;
}
