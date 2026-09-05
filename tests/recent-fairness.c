#define MINYAR_BOUNDED_HEAP 1
#define MINYAR_LAZY_HEAP 1
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>
int main(void) {
    enum { N=512, OLD=8192 };
    MinyarRecord *older=minyar_record_new(OLD);
    MinyarRecord *newer[N];
    MinyarRecord *shared=minyar_record_new_scalar(1);
    for(size_t i=0;i<N;i++) {
        newer[i]=minyar_record_new(130);
        minyar_record_set_reference(newer[i],129,(long long)(uintptr_t)shared);
    }
    rc_drop(older);
    assert(minyar_rc_poll(1)==1);
    RcObject *old=(RcObject *)older-1;
    for(size_t i=0;i<N;i++) {
        rc_drop(newer[i]);
        assert(minyar_rc_poll(1)==1);
        assert(rc_bounded_active==old);
        assert(rc_bounded_cursor>=1+i/2);
    }
    /* Captured old work continues with a constantly growing recent stack. */
    assert(rc_bounded_cursor>=N/2);
    while(rc_pending_count) assert(minyar_rc_poll(1)==1);
    assert(((RcObject *)shared-1)->ownership>>3==1);
    minyar_rc_release(shared);
    assert(!rc_bytes&&!rc_object_count&&!minyar_pool_used);
    puts("oldest cursor progresses despite new arrivals; suspended record aliases recover");
}
