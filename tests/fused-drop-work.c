#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>
int main(void) {
    void *root=NULL;
    for(size_t i=0;i<17;i++) {
        MinyarRecord *r=minyar_record_new(1);
        minyar_record_set_take(r,0,(long long)(uintptr_t)root);root=r;
    }
    rc_drop(root);size_t before=generic_drop_calls;
    /* One unit retires up to RC_SMALL_RECORD_UNIT_OBJECTS small records of the
     * chain: the child at the unit's object boundary follows the generic drop
     * and is queued, so a unit enters that body exactly once. */
    size_t units=minyar_rc_poll(32);
    assert(units==3);
    assert(generic_drop_calls-before==units);
    assert(!rc_object_count && !rc_pending_count && !rc_bounded_active);
    assert(minyar_rc_poll_idle(32)==0);
    assert(!rc_object_count&&!rc_bytes&&!rc_pending_count&&!rc_heap_allocation_count);
}
