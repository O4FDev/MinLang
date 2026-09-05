#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>
int main(void) {
    rc_bounded_last_work=123;
    MinyarRecord *r=minyar_record_new_scalar(1);
    assert(rc_bounded_last_work==0);
    rc_bounded_last_work=123;
    void *bytes=rc_allocate_data(8);
    assert(rc_bounded_last_work==0);
    rc_bounded_last_work=123;
    bytes=rc_reallocate_data(bytes,16);
    assert(rc_bounded_last_work==0);rc_free_data(bytes);
    rc_bounded_last_work=123;
    minyar_rc_release(NULL);assert(rc_bounded_last_work==0);
    minyar_rc_release(r);assert(rc_bounded_last_work==1);
    MinyarRecord *older=minyar_record_new(4096);
    rc_drop(older);
    assert(rc_pending_count);
    r=minyar_record_new_scalar(1);
    assert(rc_bounded_last_work==MINYAR_RC_POLL_BUDGET);
    minyar_rc_release(r);
    assert(rc_bounded_last_work==MINYAR_RC_POLL_BUDGET);
    while(rc_pending_count) assert(minyar_rc_poll(1)==1);
    assert(!rc_object_count&&!rc_bytes&&!rc_heap_allocation_count);
    puts("idle service avoids polling while resetting instrumentation; pending service retains exact caps");
}
