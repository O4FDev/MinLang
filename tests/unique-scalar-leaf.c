#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>
int main(void) {
    for(size_t owners=1;owners<=8;owners++) {
        MinyarRecord *record=minyar_record_new_scalar(3);
        minyar_record_set_scalar(record,0,1771);
        for(size_t i=1;i<owners;i++)minyar_rc_retain(record);
        for(size_t i=owners;i>1;i--) {
            minyar_rc_release(record);
            assert(rc_bounded_last_work==0);
            assert((((RcObject *)record-1)->ownership>>3)==i-1);
            assert(minyar_record_get(record,0)==1771);
        }
        assert(((RcObject *)record-1)->ownership==(8|RC_SCALAR_RECORD));
        minyar_rc_release(record);assert(rc_bounded_last_work==1);
        assert(!rc_object_count&&!rc_bytes&&!rc_heap_allocation_count);
    }
    MinyarRecord *root=minyar_record_new(3);
    MinyarRecord *shared=minyar_record_new_scalar(1);
    minyar_record_set_reference(root,0,(long long)(uintptr_t)shared);
    minyar_record_set_reference(root,2,(long long)(uintptr_t)shared);
    minyar_rc_release(root);
    while(rc_pending_count)assert(minyar_rc_poll(1)==1);
    assert((((RcObject *)shared-1)->ownership>>3)==1);
    minyar_rc_release(shared);
    assert(!rc_object_count&&!rc_bytes&&!rc_heap_allocation_count);
    puts("unique scalar fast free preserves1..8owners, mixed parents and exact units");
}
