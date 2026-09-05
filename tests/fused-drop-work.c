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
    assert(minyar_rc_poll(32)==32);
    assert(generic_drop_calls-before==1);
    assert(rc_object_count==1 && rc_pending_count==1 && !rc_bounded_active);
    assert(minyar_rc_poll(32)==2);
    assert(!rc_object_count&&!rc_bytes&&!rc_pending_count&&!rc_heap_allocation_count);
}
