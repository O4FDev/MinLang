#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>
int main(int argc,char **argv) {
    MinyarRecord *scalar=minyar_record_new_scalar(3);
    if(argc>1){minyar_record_set_scalar(scalar,!strcmp(argv[1],"negative")?-1:3,0);return 2;}
    MinyarRecord *older=minyar_record_new(4096);
    rc_drop(older);minyar_rc_poll(1);
    size_t cursor=rc_bounded_cursor;
    minyar_record_set_scalar(scalar,0,LLONG_MIN);
    minyar_record_set_scalar(scalar,1,LLONG_MAX);
    minyar_record_set_scalar(scalar,2,19);
    assert(rc_bounded_cursor==cursor);
    assert(minyar_record_get(scalar,0)==LLONG_MIN && minyar_record_get(scalar,1)==LLONG_MAX && minyar_record_get(scalar,2)==19);
    MinyarRecord *mixed=minyar_record_new(2);
    minyar_record_set(mixed,0,42);
    assert(rc_bounded_last_work==MINYAR_RC_POLL_BUDGET);
    minyar_record_set_reference(mixed,1,(long long)(uintptr_t)scalar);
    minyar_rc_release(mixed);minyar_rc_release(scalar);
    while(rc_pending_count)minyar_rc_poll(1);
    assert(!rc_bytes&&!rc_object_count&&!rc_heap_allocation_count);
    puts("scalar-only setter preserves bounds/values; mixed-record scalar fields still service pending work");
}
